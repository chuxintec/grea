import tempfile
import unittest
from pathlib import Path

from monkey.candidate_snapshot import snapshot, verify
from monkey.code_architecture_revision import SCHEMA, revise_native_candidate
from monkey.io import encoded, load, sha
from monkey.sources.compiled import ParseError


class ArchitectureRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.candidate = self.base / 'NativeCandidate'
        self.candidate.mkdir()
        self.original_code = b'namespace Game.Domain.Core { public sealed class PlayerState { public int Coins; } }\n'
        self._write_source('Assets/Game/Domain/Core/PlayerState.cs', self.original_code,
                           owner='generated', sourceKind='architecture-module',
                           provenance={'classId': 'player', 'module': 'Core', 'layer': 'Domain'})
        self._write_source('Assets/Game/Content/Config/Base/values.json', b'{"coin":1}\n', owner='retained', sourceKind='candidate-resource')
        self._write_source('Assets/Game/Content/Config/Base/values.json.meta',
                           b'fileFormatVersion: 2\nguid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n',
                           owner='retained', sourceKind='candidate-resource')
        self._write_source('Packages/manifest.json', b'{"dependencies":{"com.unity.ugui":"2.6.0"}}\n', owner='retained')
        self._write_source('ProjectSettings/ProjectVersion.txt', b'm_EditorVersion: 6000.6.2f1\n', owner='retained')
        self.architecture_sha = 'b' * 64
        self.manifest_raw = encoded({
            'schemaVersion': 1, 'targetProfile': 'unity-6000.6.2f1-ugui',
            'namespace': 'Fixture.NativeRevision', 'scopeMode': 'whole-input',
            'architectureSchemaVersion': 'monkey-native-architecture-candidate/1',
            'status': 'partial', 'compileStatus': 'not_run', 'runtimeStatus': 'not_run',
            'classPaths': {'player': 'Assets/Game/Domain/Core/PlayerState.cs'},
            'implementedClassPaths': ['Assets/Game/Domain/Core/PlayerState.cs'], 'missingClassPaths': [],
            'provenance': {'kind': 'native-architecture-assembly',
                           'architecturePlanSha256': self.architecture_sha,
                           'sourceCandidateManifestSha256': 'd' * 64},
            'files': self.rows,
        })
        (self.candidate / 'manifest.json').write_bytes(self.manifest_raw)
        self.base_sha = sha(self.manifest_raw)
        self.revision = self.base / 'Revision01'
        self.revision.mkdir()
        self.output = self.base / 'RevisedCandidate'
        self.replacement = b'namespace Game.Domain.Core { public sealed class PlayerState { public int Coins; public bool IsActive; } }\n'
        self.helper = b'namespace Game.Domain.Core { public static class PlayerRules { public static bool IsValid(int coins) => coins >= 0; } }\n'
        self._plan([
            self._change('Assets/Game/Domain/Core/PlayerState.cs', 'artifacts/PlayerState.cs',
                         self.original_code, self.replacement, 'player', 'Core', 'Domain', 'replace'),
            self._change('Assets/Game/Domain/Core/PlayerRules.cs', 'artifacts/PlayerRules.cs',
                         None, self.helper, 'player-rules', 'Core', 'Domain', 'new-helper'),
        ])

    def _write_source(self, path, raw, *, owner='generated', sourceKind=None, provenance=None):
        if not hasattr(self, 'rows'):
            self.rows = []
        target = self.candidate / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        row = {'path': path, 'sha256': sha(raw), 'bytes': len(raw), 'owner': owner}
        if sourceKind is not None:
            row['sourceKind'] = sourceKind
        if provenance is not None:
            row['provenance'] = provenance
        self.rows.append(row)

    def _change(self, path, artifact, old, new, class_id, module, layer, role, **kwargs):
        target = self.revision / artifact
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(new)
        return {'path': path, 'artifactPath': artifact,
                'oldSha256': sha(old) if old is not None else None,
                'newSha256': sha(new), 'bytes': len(new), 'classId': class_id,
                'module': module, 'layer': layer, 'role': role,
                'provenance': {'sourceUnitIds': ['unit-player'], **kwargs}}

    def _plan(self, files, *, base_sha=None, architecture_sha=None, evidence_pins=None):
        declared = {row['artifactPath'] for row in files}
        for item in list(self.revision.rglob('*')):
            if item.is_file() and item.name != 'revision-plan.json' and item.relative_to(self.revision).as_posix() not in declared:
                item.unlink()
        document = {'schemaVersion': SCHEMA, 'revisionId': 'NativeContentRevision01',
                    'baseManifestSha256': base_sha or self.base_sha,
                    'architecturePlanSha256': architecture_sha or self.architecture_sha,
                    'files': files}
        if evidence_pins is not None:
            document['sourceEvidencePins'] = evidence_pins
        raw = encoded(document)
        (self.revision / 'revision-plan.json').write_bytes(raw)
        self.plan_sha = sha(raw)

    def revise(self):
        return revise_native_candidate(self.candidate, self.base_sha, self.revision, self.plan_sha, self.output)

    def test_revision_is_a_verified_standard_candidate_and_preserves_resources(self):
        source_json = (self.candidate / 'Assets/Game/Content/Config/Base/values.json').read_bytes()
        report = self.revise()
        self.assertEqual(report['implementationStatus'], 'partial_unreviewed')
        self.assertEqual(report['compileStatus'], 'not_run')
        self.assertEqual(report['runtimeStatus'], 'not_run')
        root, manifest, files, _ = snapshot(self.output)
        verify(root, files)
        self.assertEqual(manifest['architectureRevision']['revisionPlanSha256'], self.plan_sha)
        self.assertEqual((self.output / 'Assets/Game/Domain/Core/PlayerState.cs').read_bytes(), self.replacement)
        self.assertEqual((self.output / 'Assets/Game/Domain/Core/PlayerRules.cs').read_bytes(), self.helper)
        self.assertEqual((self.output / 'Assets/Game/Content/Config/Base/values.json').read_bytes(), source_json)
        self.assertEqual((self.output / 'Packages/manifest.json').read_bytes(),
                         (self.candidate / 'Packages/manifest.json').read_bytes())
        meta = (self.output / 'Assets/Game/Domain/Core/PlayerRules.cs.meta').read_bytes()
        self.assertRegex(meta.decode(), r'guid: [0-9a-f]{32}')
        self.assertEqual(files['Assets/Game/Domain/Core/PlayerRules.cs.meta']['owner'], 'generated')

    def test_revision_refreshes_script_identity_hash_without_changing_existing_guid(self):
        path='Assets/Game/Domain/Core/PlayerState.cs'
        meta=b'fileFormatVersion: 2\nguid: eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee\n'
        self._write_source(path+'.meta',meta,owner='generated',sourceKind='architecture-script-meta',
            provenance={'classId':'player','scriptPath':path,'scriptSha256':sha(self.original_code),'guid':'e'*32})
        manifest=load(self.manifest_raw)
        manifest.update(files=self.rows,scriptIdentitySchema='monkey-native-script-identities/1',
            scriptIdentities={'player':dict(path=path,sha256=sha(self.original_code),metaPath=path+'.meta',
                metaSha256=sha(meta),guid='e'*32,unityTypeStatus='not_compiled')})
        self.manifest_raw=encoded(manifest);(self.candidate/'manifest.json').write_bytes(self.manifest_raw)
        self.base_sha=sha(self.manifest_raw)
        plan=load((self.revision/'revision-plan.json').read_bytes());self._plan(plan['files'])
        report=self.revise()
        self.assertEqual(report['scriptIdentities']['player']['sha256'],sha(self.replacement))
        self.assertEqual(report['scriptIdentities']['player']['guid'],'e'*32)
        self.assertEqual((self.output/(path+'.meta')).read_bytes(),meta)
        helper=report['scriptIdentities']['player-rules']
        self.assertEqual(helper['sha256'],sha(self.helper))
        self.assertEqual(helper['unityTypeStatus'],'not_compiled')
        row=next(row for row in report['files'] if row['path']==path+'.meta')
        self.assertEqual(row['provenance']['scriptSha256'],sha(self.replacement))
        self.assertEqual((self.candidate / 'Assets/Game/Domain/Core/PlayerState.cs').read_bytes(), self.original_code)

    def test_manual_changed_base_bytes_are_rejected_without_output(self):
        (self.candidate / 'Assets/Game/Domain/Core/PlayerState.cs').write_bytes(self.original_code + b'// manual edit\n')
        with self.assertRaises(ParseError) as caught:
            self.revise()
        self.assertEqual(caught.exception.code, 'CANDIDATE_DRIFT')
        self.assertFalse(self.output.exists())

    def test_new_helper_requires_explicit_owner_matching_its_semantic_path(self):
        files = [self._change('Assets/Game/Domain/Other/PlayerRules.cs', 'artifacts/Other.cs',
                              None, self.helper, 'player-rules', 'Core', 'Domain', 'new-helper')]
        self._plan(files)
        with self.assertRaises(ParseError) as caught:
            self.revise()
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REVISION_OWNER_PATH')
        self.assertFalse(self.output.exists())

    def test_new_helper_namespace_must_match_declared_layer_and_module(self):
        helper = b'namespace OtherRoot.Domain.Core { public static class PlayerRules { public static bool IsValid(int coins) => coins >= 0; } }\n'
        self._plan([self._change('Assets/Game/Domain/Core/PlayerRules.cs', 'artifacts/PlayerRules.cs',
                                 None, helper, 'player-rules', 'Core', 'Domain', 'new-helper')])
        with self.assertRaises(ParseError) as caught:
            self.revise()
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REVISION_SEMANTIC_OWNER')
        self.assertFalse(self.output.exists())

    def test_time_and_system_numerics_are_allowed_in_domain(self):
        code = b'''using System.Numerics;
namespace Game.Domain.Core {
 public sealed class PlayerState {
   public int Time { get; set; }
   public Vector3 Position;
   public string Notes = $"UnityEngine dynamic Dictionary<string, object> {Time}";
   public string Raw = """
     UnityEngine dynamic Dictionary<string, object>
   """;
 }
}
'''
        self._plan([self._change('Assets/Game/Domain/Core/PlayerState.cs', 'artifacts/PlayerState.cs',
                                 self.original_code, code, 'player', 'Core', 'Domain', 'replace')])
        result = self.revise()
        revised = (self.output / 'Assets/Game/Domain/Core/PlayerState.cs').read_bytes()
        self.assertEqual(revised, code)
        self.assertEqual(result['implementationStatus'], 'partial_unreviewed')

    def test_replacement_must_preserve_exact_original_namespace(self):
        code = b'namespace OtherRoot.Domain.Core { public sealed class PlayerState { public int Coins; } }\n'
        self._plan([self._change('Assets/Game/Domain/Core/PlayerState.cs', 'artifacts/PlayerState.cs',
                                 self.original_code, code, 'player', 'Core', 'Domain', 'replace')])
        with self.assertRaises(ParseError) as caught:
            self.revise()
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REVISION_SEMANTIC_OWNER')
        self.assertFalse(self.output.exists())

    def test_existing_helper_meta_is_preserved_exactly(self):
        meta_path = 'Assets/Game/Domain/Core/PlayerRules.cs.meta'
        meta_raw = b'fileFormatVersion: 2\nguid: cccccccccccccccccccccccccccccccc\n'
        self._write_source(meta_path, meta_raw, owner='generated', sourceKind='existing-meta')
        self.manifest_raw = encoded({
            'schemaVersion': 1, 'targetProfile': 'unity-6000.6.2f1-ugui',
            'namespace': 'Fixture.NativeRevision', 'scopeMode': 'whole-input',
            'architectureSchemaVersion': 'monkey-native-architecture-candidate/1',
            'status': 'partial', 'compileStatus': 'not_run', 'runtimeStatus': 'not_run',
            'classPaths': {'player': 'Assets/Game/Domain/Core/PlayerState.cs'},
            'implementedClassPaths': ['Assets/Game/Domain/Core/PlayerState.cs'], 'missingClassPaths': [],
            'provenance': {'kind': 'native-architecture-assembly', 'architecturePlanSha256': self.architecture_sha},
            'files': self.rows,
        })
        (self.candidate / 'manifest.json').write_bytes(self.manifest_raw)
        self.base_sha = sha(self.manifest_raw)
        helper_change = self._change('Assets/Game/Domain/Core/PlayerRules.cs', 'artifacts/PlayerRules.cs',
                                     None, self.helper, 'player-rules', 'Core', 'Domain', 'new-helper')
        self._plan([helper_change])
        self.revise()
        self.assertEqual((self.output / meta_path).read_bytes(), meta_raw)

    def test_missing_reserved_audio_class_can_be_completed_only_at_its_original_path(self):
        reserved = 'Assets/Game/Services/Audio/UnityAudioService.cs'
        manifest = load((self.candidate / 'manifest.json').read_bytes())
        manifest['classPaths']['audio-service'] = reserved
        manifest['missingClassPaths'] = [reserved]
        base_raw = encoded(manifest)
        (self.candidate / 'manifest.json').write_bytes(base_raw)
        self.base_sha = sha(base_raw)
        audio = b'namespace Game.Services.Audio { public sealed class UnityAudioService { public bool IsAvailable() => true; } }\n'
        change = self._change(reserved, 'artifacts/UnityAudioService.cs', None, audio,
                              'audio-service', 'Audio', 'Services', 'new-helper')
        self._plan([change])
        self.revise()
        output_manifest = load((self.output / 'manifest.json').read_bytes())
        self.assertEqual(output_manifest['classPaths']['audio-service'], reserved)
        self.assertIn(reserved, output_manifest['implementedClassPaths'])
        self.assertNotIn(reserved, output_manifest['missingClassPaths'])

    def test_missing_reserved_class_cannot_be_rehomed_to_another_path(self):
        reserved = 'Assets/Game/Services/Audio/UnityAudioService.cs'
        manifest = load((self.candidate / 'manifest.json').read_bytes())
        manifest['classPaths']['audio-service'] = reserved
        manifest['missingClassPaths'] = [reserved]
        base_raw = encoded(manifest)
        (self.candidate / 'manifest.json').write_bytes(base_raw)
        self.base_sha = sha(base_raw)
        wrong = 'Assets/Game/Services/Audio/AudioServiceAdapter.cs'
        audio = b'namespace Game.Services.Audio { public sealed class AudioServiceAdapter { public bool IsAvailable() => true; } }\n'
        self._plan([self._change(wrong, 'artifacts/AudioServiceAdapter.cs', None, audio,
                                 'audio-service', 'Audio', 'Services', 'new-helper')])
        with self.assertRaises(ParseError) as caught:
            self.revise()
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REVISION_CLASS_PATHS')
        self.assertFalse(self.output.exists())

    def test_manifest_class_id_cannot_point_away_from_generated_owner_path(self):
        manifest = load((self.candidate / 'manifest.json').read_bytes())
        manifest['classPaths']['player'] = 'Assets/Game/Domain/Core/OtherPlayerState.cs'
        raw = encoded(manifest)
        (self.candidate / 'manifest.json').write_bytes(raw)
        self.base_sha = sha(raw)
        with self.assertRaises(ParseError) as caught:
            self.revise()
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REVISION_CLASS_PATHS')
        self.assertFalse(self.output.exists())

    def test_implemented_and_missing_lists_must_match_owned_file_presence(self):
        manifest = load((self.candidate / 'manifest.json').read_bytes())
        path = 'Assets/Game/Domain/Core/PlayerState.cs'
        manifest['implementedClassPaths'] = []
        manifest['missingClassPaths'] = [path]
        raw = encoded(manifest)
        (self.candidate / 'manifest.json').write_bytes(raw)
        self.base_sha = sha(raw)
        with self.assertRaises(ParseError) as caught:
            self.revise()
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REVISION_CLASS_PATHS')
        self.assertFalse(self.output.exists())

    def test_domain_engine_dynamic_and_untyped_map_are_rejected(self):
        for forbidden in (
            b'using UnityEngine; namespace Game.Domain.Core { public sealed class PlayerState { public int Coins; } }',
            b'namespace Game.Domain.Core { public sealed class PlayerState { public dynamic Value; } }',
            b'using System.Collections.Generic; namespace Game.Domain.Core { public sealed class PlayerState { public Dictionary<string, object> Values; } }',
        ):
            with self.subTest(forbidden=forbidden):
                self._plan([self._change('Assets/Game/Domain/Core/PlayerState.cs', 'artifacts/PlayerState.cs',
                                         self.original_code, forbidden, 'player', 'Core', 'Domain', 'replace')])
                with self.assertRaises(ParseError) as caught:
                    self.revise()
                self.assertEqual(caught.exception.code, 'CODE_ARCH_REVISION_CORE_DEPENDENCY')
                self.assertFalse(self.output.exists())

    def test_revision_artifact_hash_tamper_is_rejected(self):
        (self.revision / 'artifacts/PlayerState.cs').write_bytes(self.replacement + b'// tampered\n')
        with self.assertRaises(ParseError) as caught:
            self.revise()
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REVISION_NEW_HASH')
        self.assertFalse(self.output.exists())

    def test_revision_plan_and_source_evidence_pins_are_strict(self):
        self._plan([
            self._change('Assets/Game/Domain/Core/PlayerState.cs', 'artifacts/PlayerState.cs',
                         self.original_code, self.replacement, 'player', 'Core', 'Domain', 'replace')],
            evidence_pins={'Assets/Game/Content/Config/Base/values.json': 'f' * 64})
        with self.assertRaises(ParseError) as caught:
            self.revise()
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REVISION_SOURCE_EVIDENCE')

    def test_ordinary_or_adopted_candidate_is_not_a_revision_base(self):
        manifest = load((self.candidate / 'manifest.json').read_bytes())
        manifest['provenance']['kind'] = 'adopted-project'
        raw = encoded(manifest)
        (self.candidate / 'manifest.json').write_bytes(raw)
        self.base_sha = sha(raw)
        with self.assertRaises(ParseError) as caught:
            self.revise()
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REVISION_CANDIDATE_KIND')
        self.assertFalse(self.output.exists())

    def test_replacement_cannot_claim_another_class_owner(self):
        replacement = self._change('Assets/Game/Domain/Core/PlayerState.cs', 'artifacts/PlayerState.cs',
                                   self.original_code, self.replacement, 'another-class', 'Core', 'Domain', 'replace')
        self._plan([replacement])
        with self.assertRaises(ParseError) as caught:
            self.revise()
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REVISION_OWNER')
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
