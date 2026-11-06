"""Real Roslyn gates and exact worker-scope regressions; no compiler mocks."""
import json
from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import unittest

from grea.development import csharp_rewrite as rewrite
from grea.development.errors import BeaverError
from grea.development.io import sha, encoded, write_json
from grea.development.project_profile import setup_plan, setup_apply

UNITY = Path('/Applications/Unity/Hub/Editor/6000.6.2f1/Unity.app/Contents')
MONO = UNITY / 'Resources/Scripting/MonoBleedingEdge/lib/mono/unityjit-macos'
CORE = UNITY / 'Resources/Scripting/Managed/UnityEngine/UnityEngine.CoreModule.dll'


@unittest.skipUnless(CORE.is_file() and shutil.which('dotnet'), 'Local Unity SDK and .NET SDK required')
class RewriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name).resolve()
        cls.project = cls.root / 'UnityProject'
        p = cls.project
        (p / 'Assets/Scripts').mkdir(parents=True)
        (p / 'Packages').mkdir(); (p / 'ProjectSettings').mkdir()
        (p / 'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.6.2f1\n')
        write_json(p / 'Packages/manifest.json', dict(dependencies={}))
        cls.path = 'Assets/Scripts/Widget.cs'
        cls.code = 'using UnityEngine; public sealed class Widget : MonoBehaviour { public float amount; public void Show() { transform.localScale = Vector3.one; } }\n'
        (p / cls.path).write_text(cls.code)
        (p / (cls.path + '.meta')).write_text('fileFormatVersion: 2\nguid: 0123456789abcdef0123456789abcdef\n')
        cls.evidence = cls.root / 'original.cs'; cls.evidence.write_text(cls.code)
        cls.setup = cls.root / 'project-spec.json'
        write_json(cls.setup, dict(schemaVersion=1, engine='unity', name='RewriteTest', writableRoots=['Assets/Scripts'], generatedRoots=[]))
        plan = setup_plan(p, cls.setup, cls.root / 'setup-plan')
        setup_apply(plan['report'], plan['planSha256'], cls.root / 'setup-apply')
        refs = [str(MONO / n) for n in ('mscorlib.dll', 'System.dll', 'System.Core.dll', 'Facades/netstandard.dll')]
        refs.append(str(CORE))
        cls.toolchain = dict(assemblies=[dict(name='Assembly-CSharp', sourceFiles=[cls.path], references=refs)])
        cls.spec = dict(contract=rewrite.REQUEST, instances=[], sources=[dict(path=str(cls.evidence), sha256=sha(cls.evidence.read_bytes()), sourceId='widget-original')],
                        scripts=[dict(path=cls.path, sha256=sha(cls.code.encode()), metaSha256=sha((p/(cls.path+'.meta')).read_bytes()), guid='0123456789abcdef0123456789abcdef', assembly='Assembly-CSharp', fullType='Widget')],
                        expectedBehavior=[dict(description='Show restores scale', sourceIds=['widget-original'])], profile=str(p/'.beaver/project.json'))
        write_json(cls.root/'request.json', cls.spec)
        cls.prepared = rewrite.prepare(p, cls.root/'request.json', cls.root/'prepared', cls.toolchain)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.case = Path(tempfile.mkdtemp(dir=self.root))
        self.workspace = self.case/'work'
        shutil.copytree(self.root/'prepared', self.workspace)

    def change(self, code):
        (self.workspace/'files'/self.path).write_text(code)
        write_json(self.workspace/'result.json', dict(contract=rewrite.RESULT, changedPaths=[self.path], limitations=['Runtime behavior requires owner acceptance'], behaviorEvidence=self.spec['expectedBehavior']))

    def plan(self):
        return rewrite.plan(self.workspace/'workspace.json', self.prepared['workspaceSha256'], self.case/'plan')

    def reject(self, code):
        with self.assertRaises(BeaverError) as found: self.plan()
        self.assertEqual(found.exception.code, code)
        self.assertEqual((self.project/self.path).read_text(), self.code)

    def test_real_compile_and_reviewable_patch_without_project_write(self):
        self.change(self.code.replace('Vector3.one', 'Vector3.one * 2f'))
        result = self.plan()
        self.assertEqual(result['status'], 'planned')
        report = json.loads(Path(result['report']).read_text())
        self.assertEqual(report['native'], 'not_run')
        self.assertEqual(report['behavior'], 'not_verified')
        self.assertEqual(len(report['compatibility'][0]['fieldMappings']), 1)
        self.assertIn('Vector3.one * 2f', (Path(result['report']).parent/'changes.patch').read_text())
        self.assertEqual((self.project/self.path).read_text(), self.code)

    def test_compile_error_blocks(self):
        self.change(self.code.replace('Vector3.one', 'DoesNotExist.Value'))
        self.reject('REWRITE_PATCH_COMPILE')

    def test_serialized_field_change_blocks(self):
        self.change(self.code.replace('float amount', 'double amount'))
        self.reject('REWRITE_FIELD_MIGRATION')

    def test_nonserialized_attribute_blocks_field_loss(self):
        self.change(self.code.replace('public float amount', '[System.NonSerialized] public float amount'))
        self.reject('REWRITE_FIELD_MIGRATION')

    def test_serialization_mode_change_blocks(self):
        self.change(self.code.replace('public float amount', '[SerializeReference] public float amount'))
        self.reject('REWRITE_FIELD_MIGRATION')

    def test_event_method_removal_blocks(self):
        self.change(self.code.replace('void Show()', 'void Hidden()'))
        self.reject('REWRITE_EVENT_METHOD')

    def test_wrong_type_blocks(self):
        self.change(self.code.replace('class Widget', 'class OtherWidget'))
        self.reject('REWRITE_TYPE_IDENTITY')

    def test_extra_file_blocks_before_compilation(self):
        self.change(self.code.replace('Vector3.one', 'Vector3.zero'))
        (self.workspace/'extra.cs').write_text('class Extra {}')
        self.reject('REWRITE_WORKER_SCOPE')

    def test_context_edit_blocks(self):
        self.change(self.code.replace('Vector3.one', 'Vector3.zero'))
        (self.workspace/'context/request.json').write_text('{}')
        self.reject('REWRITE_WORKER_SCOPE')

    def test_symlink_directory_blocks(self):
        self.change(self.code.replace('Vector3.one', 'Vector3.zero'))
        (self.workspace/'escape').symlink_to(self.project, target_is_directory=True)
        self.reject('REWRITE_WORKER_SCOPE')

    def test_false_changed_ledger_blocks(self):
        self.change(self.code.replace('Vector3.one', 'Vector3.zero'))
        path = self.workspace/'result.json'; data=json.loads(path.read_text()); data['changedPaths']=[];write_json(path,data)
        self.reject('REWRITE_CHANGED_PATHS')

    def test_pinned_source_drift_blocks(self):
        self.change(self.code.replace('Vector3.one', 'Vector3.zero'))
        original = self.evidence.read_bytes()
        try:
            self.evidence.write_bytes(original+b'// changed\n')
            self.reject('REWRITE_SOURCE_HASH')
        finally: self.evidence.write_bytes(original)

    def test_workspace_hash_blocks(self):
        self.change(self.code.replace('Vector3.one', 'Vector3.zero'))
        path = self.workspace/'workspace.json'; path.write_bytes(path.read_bytes()+b' ')
        self.reject('REWRITE_WORKSPACE_IDENTITY')


class NativeReceiptTests(unittest.TestCase):
    def setUp(self):
        self.instance=dict(prefabPath='Assets/Widget.prefab',prefabGuid='1'*32,nodeLocalId=11,componentLocalId=-12,fullType='Widget',sourceIdField='sourceId',sourceId='original#2')
        self.script=dict(path='Assets/Widget.cs',fullType='Widget',assembly='Assembly-CSharp',guid='2'*32)
        self.data=dict(projectRoot='/project',instances=[self.instance],compatibility=[self.script],fileEdits=[dict(path='Assets/Widget.cs',sha256='b'*64)],pins=[dict(path='/project/Assets/Widget.cs',sha256='a'*64)])
        row=dict(prefabPath='Assets/Widget.prefab',prefabGuid='1'*32,nodeLocalId=11,componentLocalId=-12,fullType='Widget',nodePath='Root/Widget',assembly='Assembly-CSharp',scriptGuid='2'*32,scriptPath='Assets/Widget.cs',scriptSha256='a'*64,getClassVerified=True,enabled=False,properties=[dict(path='sourceId',kind='String',type='string',value='original#2'),dict(path='onClick.m_PersistentCalls.m_Calls.Array.data[0].m_Target',kind='ObjectReference',type='PPtr',value='3'*32+'#100|Widget@Assembly-CSharp')])
        self.before=dict(scriptCoverage=[dict(fullType='Widget',prefabPaths=['Assets/Widget.prefab'],instanceCount=1,scannedPrefabs=1,complete=True)],scriptInstances=[row],prefabs=[dict(path='Assets/Widget.prefab',guid='1'*32,contentSha256='c'*64,serializedTreeSha256='d'*64,nodes=[],missingScripts=0)])
        self.after=deepcopy(self.before);self.after['scriptInstances'][0]['scriptSha256']='b'*64

    def test_changed_source_with_same_native_instances_passes(self):
        rewrite._instances(self.before,self.data,False);rewrite._instances(self.after,self.data,True)
        rewrite._compare_native(self.before,self.after)

    def test_wrong_node_refused(self):
        self.after['scriptInstances'][0]['nodeLocalId']=99
        with self.assertRaises(BeaverError) as found:rewrite._instances(self.after,self.data,True)
        self.assertEqual(found.exception.code,'REWRITE_INSTANCE_IDENTITY')

    def test_event_target_refused(self):
        self.after['scriptInstances'][0]['properties'][-1]['value']='null'
        with self.assertRaises(BeaverError) as found:rewrite._compare_native(self.before,self.after)
        self.assertEqual(found.exception.code,'REWRITE_NATIVE_VALUES')

    def test_duplicate_instance_refused(self):
        self.after['scriptInstances'].append(deepcopy(self.after['scriptInstances'][0]))
        with self.assertRaises(BeaverError) as found:rewrite._instances(self.after,self.data,True)
        self.assertEqual(found.exception.code,'REWRITE_INSTANCE_COUNT')

    def test_incomplete_project_consumer_coverage_refused(self):
        self.after['scriptCoverage'][0]['instanceCount']=2
        with self.assertRaises(BeaverError) as found:rewrite._instances(self.after,self.data,True)
        self.assertEqual(found.exception.code,'REWRITE_INSTANCE_COVERAGE')
