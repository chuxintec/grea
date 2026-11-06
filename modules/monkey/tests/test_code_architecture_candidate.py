import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from monkey import code_architecture_candidate as candidate_builder
from monkey.code_architecture_candidate import assemble_native_candidate, script_guid
from monkey.candidate_snapshot import snapshot, verify
from monkey.io import encoded, sha
from monkey.sources.compiled import ParseError


class ArchitectureCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.candidate = self.root / 'Candidate07'
        self.candidate.mkdir()
        self.modules = self.root / 'Modules'
        self.modules.mkdir()
        self.plan_path = self.root / 'architecture.json'
        self.validation_path = self.root / 'validation.json'
        self.output = self.root / 'Assembled'

        resources = {
            'Assets/Game/Content/Config/Base/values.json': b'{"coin":1}\n',
            'Assets/Game/Content/Config/Base/values.json.meta': b'fileFormatVersion: 2\nguid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n',
            'Assets/Game/Content/Scenes/Main.unity': b'%YAML 1.1\n',
            'Assets/Game/Content/Prefabs/Layout.prefab': b'--- !u!114 &1\nMonoBehaviour:\n  m_Script: {fileID: 11500000, guid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb}\n',
            'ProjectSettings/ProjectVersion.txt': b'm_EditorVersion: 6000.6.2f1\n',
            'Packages/manifest.json': b'{"dependencies":{"com.unity.ugui":"2.6.0"}}\n',
            'Assets/Game/Gameplay/OldDraft.cs': b'class OldDraft {}\n',
            'SourceRecovery/Code/old.js': b'function old() {}\n',
            'Assets/Game/Presentation/Common/Layout/NativeLinearLayoutGroup.cs': b'public sealed class NativeLinearLayoutGroup {}\npublic sealed class NativeChildLayoutGroup {}\n',
            'Assets/Game/Presentation/Common/Layout/NativeLinearLayoutGroup.cs.meta': b'fileFormatVersion: 2\nguid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n',
        }
        self.candidate_rows = []
        for path, raw in resources.items():
            target = self.candidate / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            self.candidate_rows.append(dict(path=path, sha256=sha(raw), bytes=len(raw), owner='generated'))
        manifest_raw = encoded(dict(schemaVersion=1, targetProfile='unity-6000.6.2f1-ugui',
                                    namespace='Fixture.Native', scopeMode='whole-input', files=self.candidate_rows))
        (self.candidate / 'manifest.json').write_bytes(manifest_raw)
        self.candidate_pin = sha(manifest_raw)

        self.plan = {
            'schemaVersion': 'monkey-native-code-architecture/1',
            'sourceManifestSha256': self.candidate_pin,
            'rootNamespace': 'Game',
            'modules': [{'id': 'Core', 'sourceUnitIds': ['unit-a'], 'classIds': ['state'],
                         'responsibility': 'Own model state'}],
            'classes': [{'id': 'state', 'name': 'PlayerState', 'layer': 'Domain', 'module': 'Core',
                         'sourceUnitIds': ['unit-a'], 'fields': [],
                         'methods': [{'name': 'Add', 'sourceMemberIds': ['member-a']}]}],
        }
        self.plan_raw = encoded(self.plan)
        self.plan_path.write_bytes(self.plan_raw)
        self.plan_pin = sha(self.plan_raw)
        self.validation = {
            'valid': True,
            'classPaths': {'state': 'Assets/Game/Domain/Core/PlayerState.cs'},
            'assemblyReferences': {
                'Domain': [], 'Gameplay': ['Domain'],
                'Presentation': ['Domain', 'Gameplay'], 'Services': ['Domain', 'Gameplay'],
                'Bootstrap': ['Domain', 'Gameplay', 'Presentation', 'Services'],
            },
        }
        self.validation_raw = encoded(self.validation)
        self.validation_path.write_bytes(self.validation_raw)
        self.validation_pin = sha(self.validation_raw)
        self.class_source = b'namespace Game.Domain.Core { public sealed class PlayerState { public int Coins; } }\n'
        self._write_module_manifest(self.class_source)

    def _write_module_manifest(self, raw, *, path='Assets/Game/Domain/Core/PlayerState.cs', class_id='state',
                               status='complete', source_units=None, source_members=None,
                               unresolved_units=None, unresolved_members=None):
        for item in sorted(self.modules.rglob('*'), reverse=True):
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                item.rmdir()
        target = self.modules / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        manifest_raw = encoded({
            'schemaVersion': 1,
            'sourceManifestSha256': self.candidate_pin,
            'architectureSha256': self.plan_pin,
            'modules': [{'id': 'Core', 'status': status}],
            'files': [dict(path=path, sha256=sha(raw), bytes=len(raw), classId=class_id,
                           sourceUnitIds=['unit-a'] if source_units is None else source_units,
                           sourceMemberIds=['member-a'] if source_members is None else source_members,
                           unresolvedSourceUnitIds=[] if unresolved_units is None else unresolved_units,
                           unresolvedSourceMemberIds=[] if unresolved_members is None else unresolved_members,
                           status=status)],
        })
        (self.modules / 'manifest.json').write_bytes(manifest_raw)
        self.module_pin = sha(manifest_raw)

    def assemble(self, **kwargs):
        return assemble_native_candidate(
            self.candidate, self.candidate_pin, self.plan_path, self.plan_pin,
            self.validation_path, self.validation_pin, self.modules, self.module_pin,
            self.output, **kwargs)

    def test_builds_only_pinned_resources_and_implemented_planned_code(self):
        report = self.assemble()
        self.assertEqual(report['status'], 'assembled')
        self.assertEqual(report['compileStatus'], 'not_run')
        self.assertFalse(report['compiled'])
        self.assertTrue((self.output / 'Assets/Game/Content/Scenes/Main.unity').is_file())
        self.assertTrue((self.output / 'Assets/Game/Content/Config/Base/values.json.meta').is_file())
        self.assertTrue((self.output / 'Packages/manifest.json').is_file())
        self.assertTrue((self.output / 'ProjectSettings/ProjectVersion.txt').is_file())
        self.assertFalse((self.output / 'Assets/Game/Gameplay/OldDraft.cs').exists())
        self.assertFalse((self.output / 'SourceRecovery/Code/old.js').exists())
        self.assertFalse((self.output / 'Assets/Game/Presentation/Common/Layout/NativeLinearLayoutGroup.cs').exists())
        asmdef = json.loads((self.output / 'Assets/Game/Domain/Domain.asmdef').read_bytes())
        self.assertEqual(asmdef['references'], [])
        self.assertTrue(asmdef['noEngineReferences'])
        src = self.modules / 'Assets/Game/Domain/Core/PlayerState.cs'
        dst = self.output / 'Assets/Game/Domain/Core/PlayerState.cs'
        self.assertNotEqual(src.stat().st_ino, dst.stat().st_ino)

    def test_output_manifest_is_readable_by_standard_candidate_snapshot(self):
        self.assemble()
        root, manifest, files, digest = snapshot(self.output)
        verify(root, files)
        self.assertEqual(manifest['schemaVersion'], 1)
        self.assertEqual(manifest['targetProfile'], 'unity-6000.6.2f1-ugui')
        self.assertEqual(manifest['namespace'], 'Fixture.Native')
        self.assertEqual(manifest['scopeMode'], 'whole-input')
        self.assertEqual(manifest['architectureSchemaVersion'], 'monkey-native-architecture-candidate/1')
        self.assertEqual(manifest['provenance']['architecturePlanSha256'], self.plan_pin)
        self.assertEqual(files['Assets/Game/Domain/Core/PlayerState.cs']['owner'], 'generated')
        self.assertEqual(files['Assets/Game/Content/Scenes/Main.unity']['owner'], 'retained')
        self.assertTrue(digest)

    def test_explicit_partial_is_recorded_without_compile_claim(self):
        self._write_module_manifest(self.class_source, status='partial', source_members=[], unresolved_members=['member-a'])
        report = self.assemble(allow_partial=True)
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['partialClassPaths'], ['Assets/Game/Domain/Core/PlayerState.cs'])
        self.assertEqual(report['compileStatus'], 'not_run')

    def test_generated_script_meta_is_stable_across_output_and_code_revision(self):
        first=self.assemble()
        script='Assets/Game/Domain/Core/PlayerState.cs'
        meta=(self.output/(script+'.meta')).read_bytes()
        self.assertFalse((self.modules/(script+'.meta')).exists())
        identity=first['scriptIdentities']['state']
        self.assertEqual(identity['sha256'],sha(self.class_source))
        self.assertEqual(identity['metaSha256'],sha(meta))
        self.assertEqual(identity['unityTypeStatus'],'not_compiled')
        guids=[row['provenance']['guid'] for row in first['files']
               if row['sourceKind'] in ('architecture-script-meta','architecture-assembly-meta')]
        self.assertEqual(len(guids),6)
        self.assertEqual(len(set(guids)),6)
        self.output=self.output.with_name('second-output')
        changed=self.class_source.replace(b'int Coins;',b'long Coins;')
        self._write_module_manifest(changed)
        second=self.assemble()
        self.assertEqual((self.output/(script+'.meta')).read_bytes(),meta)
        self.assertNotEqual(second['scriptIdentities']['state']['sha256'],identity['sha256'])
        self.assertEqual(second['scriptIdentities']['state']['guid'],identity['guid'])

    def test_generated_script_guid_collision_with_resource_is_rejected(self):
        path='Assets/Game/Content/Config/Base/values.json.meta'
        raw=('fileFormatVersion: 2\nguid: '+script_guid('Fixture.Native','Game','state')+'\n').encode()
        (self.candidate/path).write_bytes(raw)
        for row in self.candidate_rows:
            if row['path']==path:row.update(sha256=sha(raw),bytes=len(raw))
        candidate=json.loads((self.candidate/'manifest.json').read_bytes());candidate['files']=self.candidate_rows
        (self.candidate/'manifest.json').write_bytes(encoded(candidate))
        self.candidate_pin=sha((self.candidate/'manifest.json').read_bytes())
        self.plan['sourceManifestSha256']=self.candidate_pin
        self.plan_raw=encoded(self.plan);self.plan_path.write_bytes(self.plan_raw);self.plan_pin=sha(self.plan_raw)
        self._write_module_manifest(self.class_source)
        with self.assertRaises(ParseError) as caught:self.assemble()
        self.assertEqual(caught.exception.code,'ARCH_CANDIDATE_DUPLICATE_GUID')
        self.assertFalse(self.output.exists())

    def _pin_candidate_update(self, module_source=None):
        raw = encoded(dict(schemaVersion=1, targetProfile='unity-6000.6.2f1-ugui',
                           namespace='Fixture.Native', scopeMode='whole-input', files=self.candidate_rows))
        (self.candidate / 'manifest.json').write_bytes(raw)
        self.candidate_pin = sha(raw)
        self.plan['sourceManifestSha256'] = self.candidate_pin
        self.plan_raw = encoded(self.plan); self.plan_path.write_bytes(self.plan_raw); self.plan_pin = sha(self.plan_raw)
        self._write_module_manifest(self.class_source if module_source is None else module_source)

    def test_csharp9_record_and_init_generate_one_domain_compiler_support_file(self):
        source = b'''namespace Game.Domain.Core {
public record PlayerState(int Coins) { public int Level { get; init; } }
}'''
        self._write_module_manifest(source)
        report = self.assemble()
        path = candidate_builder.EXTERNAL_INIT_PATH
        meta_path = path + '.meta'
        self.assertTrue((self.output / path).is_file())
        self.assertEqual((self.output / path).read_bytes(), candidate_builder.EXTERNAL_INIT_SOURCE)
        self.assertEqual(report['compilerSupport']['status'] if 'status' in report['compilerSupport'] else 'generated', 'generated')
        self.assertEqual(report['compilerSupport']['path'], path)
        self.assertEqual(report['compilerSupport']['guid'], script_guid(
            'Fixture.Native', 'Game', candidate_builder.EXTERNAL_INIT_ID))
        self.assertNotIn(path, report['classPaths'].values())
        row = next(row for row in report['files'] if row['path'] == path)
        self.assertEqual(row['owner'], 'generated')
        self.assertEqual(row['sourceKind'], 'compiler-compatibility-support')
        self.assertNotIn('classId', row)
        meta_row = next(row for row in report['files'] if row['path'] == meta_path)
        self.assertEqual(meta_row['sourceKind'], 'compiler-compatibility-support-meta')
        self.assertEqual(meta_row['provenance']['guid'], report['compilerSupport']['guid'])
        self.assertEqual(sum(row['sourceKind'] == 'compiler-compatibility-support' for row in report['files']), 1)
        root, _manifest, files, _digest = snapshot(self.output); verify(root, files)
        meta = (self.output / meta_path).read_bytes()
        self.output = self.output.with_name('AssembledAgain')
        second = self.assemble()
        self.assertEqual((self.output / meta_path).read_bytes(), meta)
        self.assertEqual(second['compilerSupport']['guid'], report['compilerSupport']['guid'])

    def test_record_or_init_words_inside_comments_and_strings_do_not_add_shim(self):
        source = b'''namespace Game.Domain.Core {
public sealed class PlayerState { public string Note => "record Fake { get; init; }"; /* record Fake */ }
}'''
        self._write_module_manifest(source)
        report = self.assemble()
        self.assertFalse((self.output / candidate_builder.EXTERNAL_INIT_PATH).exists())
        self.assertEqual(report['compilerSupport']['status'], 'not_required')
        self.assertNotIn(candidate_builder.EXTERNAL_INIT_PATH,
                         {row['path'] for row in report['files']})

    def test_module_output_cannot_sneak_in_a_second_external_init_type(self):
        source = b'''namespace System.Runtime.CompilerServices {
public static class IsExternalInit { }
}
namespace Game.Domain.Core { public record PlayerState(int Coins); }'''
        self._write_module_manifest(source)
        with self.assertRaises(ParseError) as caught:
            self.assemble()
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_COMPILER_SUPPORT_DUPLICATE')
        self.assertFalse(self.output.exists())

    def test_reserved_candidate_manifest_path_cannot_shadow_generated_shim(self):
        source = b'namespace Game.Domain.Core { public record PlayerState(int Coins); }'
        self._write_module_manifest(source)
        target = self.candidate / candidate_builder.EXTERNAL_INIT_PATH
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(b'public class IsExternalInit {}')
        self.candidate_rows.append(dict(path=candidate_builder.EXTERNAL_INIT_PATH,
            sha256=sha(target.read_bytes()), bytes=target.stat().st_size, owner='generated'))
        self._pin_candidate_update(source)
        with self.assertRaises(ParseError) as caught:
            self.assemble()
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_COMPILER_SUPPORT_PATH')
        self.assertFalse(self.output.exists())

    def test_generated_support_meta_guid_collision_with_candidate_resource_is_rejected(self):
        source = b'namespace Game.Domain.Core { public record PlayerState(int Coins); }'
        self._write_module_manifest(source)
        guid = script_guid('Fixture.Native', 'Game', candidate_builder.EXTERNAL_INIT_ID)
        path = 'Assets/Game/Content/Config/Base/values.json.meta'
        raw = f'fileFormatVersion: 2\nguid: {guid}\n'.encode()
        (self.candidate / path).write_bytes(raw)
        for row in self.candidate_rows:
            if row['path'] == path:
                row.update(sha256=sha(raw), bytes=len(raw))
        self._pin_candidate_update(source)
        with self.assertRaises(ParseError) as caught:
            self.assemble()
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_DUPLICATE_GUID')
        self.assertFalse(self.output.exists())

    def test_pinned_unity_csharp9_references_fail_record_without_shim_and_pass_with_it(self):
        repo = Path(__file__).resolve().parents[1]
        response_path = repo / '.private/v060-architecture-first-20261027/NativeAudioNativeProbe01/Evidence/editor-compile.rsp'
        dotnet = shutil.which('dotnet')
        if not response_path.is_file() or not dotnet:
            self.skipTest('Pinned Unity C# compiler response or dotnet SDK is unavailable')
        sdks = subprocess.run([dotnet, '--list-sdks'], capture_output=True, text=True, check=False)
        sdk_entries = []
        for line in sdks.stdout.splitlines():
            match = re.fullmatch(r'([^ ]+) \[(.+)/sdk\]', line.strip())
            if match:
                sdk_entries.append(Path(match.group(2)) / 'sdk' / match.group(1) / 'Roslyn/bincore/csc.dll')
        csc_files = sorted(path for path in sdk_entries if path.is_file())
        if not csc_files:
            self.skipTest('Roslyn csc.dll is unavailable')
        lines = response_path.read_text(encoding='utf-8').splitlines()
        switches = [line.strip('"') for line in lines if line.startswith((
            '"/reference:', '"-reference:', '"/langversion:', '"-langversion:',
            '"/nostdlib', '"-nostdlib', '"/define:', '"-define:', '"/unsafe', '"-unsafe'))]
        refs = [line.split(':', 1)[1] for line in switches if line.startswith(('/reference:', '-reference:'))]
        if not any('/Applications/Unity/Hub/Editor/6000.6.2f1/' in ref for ref in refs):
            self.skipTest('Response does not pin Unity 6000.6.2f1 managed references')
        if not any('/ref/netstandard2.1/' in ref for ref in refs):
            self.skipTest('Response does not pin netstandard2.1 reference assemblies')
        if any(not Path(ref).is_file() for ref in refs):
            self.skipTest('One or more pinned managed references are unavailable')
        self.assertTrue(any('/langversion:9' in line for line in switches))
        self.assertFalse(any(line.startswith(('/define:', '-define:')) for line in switches))
        source = 'namespace Probe { public record Row(int Value) { public int Next { get; init; } } }\n'
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory); probe = root / 'Probe.cs'; probe.write_text(source, encoding='utf-8')
            response = root / 'probe.rsp'
            base = switches + ['/nologo', '/target:library', f'/out:{root}/Probe.dll', str(probe)]
            response.write_text('\n'.join(base) + '\n', encoding='utf-8')
            missing = subprocess.run([dotnet, str(csc_files[-1]), '@' + str(response)],
                                     capture_output=True, text=True, check=False)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn('CS0518', missing.stdout + missing.stderr)
            shim = root / 'IsExternalInit.cs'; shim.write_bytes(candidate_builder.EXTERNAL_INIT_SOURCE)
            response.write_text('\n'.join(base + [str(shim)]) + '\n', encoding='utf-8')
            supplied = subprocess.run([dotnet, str(csc_files[-1]), '@' + str(response)],
                                      capture_output=True, text=True, check=False)
            self.assertEqual(supplied.returncode, 0, supplied.stdout + supplied.stderr)

    def test_empty_placeholder_type_is_rejected(self):
        self._write_module_manifest(b'// planned implementation goes here\n')
        with self.assertRaises(ParseError) as caught:
            self.assemble()
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_EMPTY_IMPLEMENTATION')

    def test_missing_implementation_requires_explicit_partial_assembly(self):
        for item in sorted(self.modules.rglob('*'), reverse=True):
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                item.rmdir()
        (self.modules / 'manifest.json').write_bytes(encoded({
            'sourceManifestSha256': self.candidate_pin,
            'architectureSha256': self.plan_pin,
            'files': [], 'modules': [{'id': 'Core', 'status': 'partial'}],
        }))
        self.module_pin = sha((self.modules / 'manifest.json').read_bytes())
        with self.assertRaises(ParseError) as caught:
            self.assemble()
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_MISSING_IMPLEMENTATION')
        report = self.assemble(allow_partial=True)
        self.assertEqual(report['status'], 'partial')
        self.assertEqual(report['missingClassPaths'], ['Assets/Game/Domain/Core/PlayerState.cs'])

    def test_rejects_unplanned_class_path_and_wrong_module_owner(self):
        other = 'Assets/Game/Domain/Core/Unexpected.cs'
        self._write_module_manifest(b'public class PlayerState {}\n', path=other)
        with self.assertRaises(ParseError) as caught:
            self.assemble()
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_MODULE_PATH')

    def test_native_layout_support_is_retained_only_as_explicit_cs_meta_pair(self):
        pair = [
            'Assets/Game/Presentation/Common/Layout/NativeLinearLayoutGroup.cs',
            'Assets/Game/Presentation/Common/Layout/NativeLinearLayoutGroup.cs.meta',
        ]
        report = self.assemble(retained_support_paths=pair)
        support = self.output / pair[0]
        self.assertTrue(support.is_file())
        self.assertIn('NativeChildLayoutGroup', support.read_text())
        record = next(row for row in report['files'] if row['path'] == pair[0])
        self.assertEqual(record['owner'], 'retained')
        self.assertEqual(record['sourceKind'], 'existing-implementation')
        self.assertEqual(record['provenance']['kind'], 'native-layout-support')
        self.assertEqual(report['retainedSupportPaths'], sorted(pair))

    def test_support_rejects_unapproved_paths_and_missing_meta_pair(self):
        with self.assertRaises(ParseError) as caught:
            self.assemble(retained_support_paths=['Assets/Game/Presentation/Common/Layout/NativeLinearLayoutGroup.cs'])
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_SUPPORT_PATHS')
        with self.assertRaises(ParseError) as caught:
            self.assemble(retained_support_paths=[
                'Assets/Game/Presentation/Common/Layout/OtherHelper.cs',
                'Assets/Game/Presentation/Common/Layout/OtherHelper.cs.meta'])
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_SUPPORT_PATHS')

    def test_module_manifest_pins_and_source_mapping_are_bound_to_plan(self):
        self._write_module_manifest(self.class_source, source_units=['unit-other'])
        with self.assertRaises(ParseError) as caught:
            self.assemble()
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_MODULE_MAPPING')
        self._write_module_manifest(self.class_source)
        doc = json.loads((self.modules / 'manifest.json').read_bytes())
        doc['architectureSha256'] = 'd' * 64
        raw = encoded(doc)
        (self.modules / 'manifest.json').write_bytes(raw)
        self.module_pin = sha(raw)
        with self.assertRaises(ParseError) as caught:
            self.assemble()
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_MODULE_ARCHITECTURE_PIN')

    def test_complete_rows_must_cover_planned_members_and_cannot_add_unknown_members(self):
        self._write_module_manifest(self.class_source, source_members=[])
        with self.assertRaises(ParseError) as caught:
            self.assemble()
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_MODULE_MAPPING')
        self._write_module_manifest(self.class_source, source_members=['member-a', 'unplanned-member'])
        with self.assertRaises(ParseError) as caught:
            self.assemble()
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_MODULE_MAPPING')

    def test_plan_source_pin_must_match_candidate_manifest(self):
        plan = dict(self.plan)
        plan['sourceManifestSha256'] = 'd' * 64
        raw = encoded(plan)
        self.plan_path.write_bytes(raw)
        self.plan_pin = sha(raw)
        self._write_module_manifest(self.class_source)
        with self.assertRaises(ParseError) as caught:
            self.assemble()
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_PLAN_SOURCE_PIN')

    def test_empty_class_shell_is_rejected_but_does_not_claim_business_completeness(self):
        self._write_module_manifest(b'public sealed class PlayerState { }\n')
        with self.assertRaises(ParseError) as caught:
            self.assemble()
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_EMPTY_IMPLEMENTATION')

    def test_rejects_stale_source_and_output_conflict(self):
        (self.candidate / 'Assets/Game/Content/Scenes/Main.unity').write_bytes(b'changed')
        with self.assertRaises(ParseError) as caught:
            self.assemble()
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_SOURCE_CHANGED')
        (self.candidate / 'Assets/Game/Content/Scenes/Main.unity').write_bytes(b'%YAML 1.1\n')
        self.output.mkdir()
        with self.assertRaises(ParseError) as caught:
            self.assemble()
        self.assertEqual(caught.exception.code, 'ARCH_CANDIDATE_OUTPUT_EXISTS')


if __name__ == '__main__':
    unittest.main()
