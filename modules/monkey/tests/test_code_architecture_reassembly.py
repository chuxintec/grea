import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from monkey import code_architecture_modules as modules
import monkey.code_architecture_reassembly as reassembly
from monkey.code_architecture_reassembly import reassemble
from monkey.io import encoded, load, sha
from monkey.sources.compiled import ParseError


class ArchitectureReassemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/private/tmp')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'Candidate07'
        self.source.mkdir()
        self._source_file('Assets/Game/Content/Config/Base/values.json', b'{"coin":1}\n')
        self._source_file('ProjectSettings/ProjectVersion.txt', b'm_EditorVersion: 6000.6.2f1\n')
        self._source_file('Packages/manifest.json', b'{"dependencies":{}}\n')
        source_manifest = encoded({
            'schemaVersion': 1, 'targetProfile': 'unity-6000.6.2f1-ugui',
            'namespace': 'Fixture.Reassembly', 'scopeMode': 'whole-input', 'files': self.source_rows,
        })
        (self.source / 'manifest.json').write_bytes(source_manifest)
        self.source_pin = sha(source_manifest)

        self.architecture = self.base / 'Architecture'
        self.architecture.mkdir()
        self.plan = {
            'schemaVersion': 'monkey-native-code-architecture/1',
            'sourceManifestSha256': self.source_pin,
            'rootNamespace': 'Game',
            'modules': [{'id': 'Core', 'classIds': ['player'], 'sourceUnitIds': ['unit-a'],
                         'responsibility': 'Player domain'}],
            'classes': [{'id': 'player', 'name': 'PlayerState', 'layer': 'Domain', 'module': 'Core',
                         'sourceUnitIds': ['unit-a'], 'fields': [], 'methods': []}],
        }
        self.plan_raw = encoded(self.plan)
        (self.architecture / 'architecture.json').write_bytes(self.plan_raw)
        self.plan_pin = sha(self.plan_raw)
        self.validation = {
            'valid': True, 'classPaths': {'player': 'Assets/Game/Domain/Core/PlayerState.cs'},
            'assemblyReferences': {'Domain': [], 'Gameplay': ['Domain'],
                'Presentation': ['Domain', 'Gameplay'], 'Services': ['Domain', 'Gameplay'],
                'Bootstrap': ['Domain', 'Gameplay', 'Presentation', 'Services']},
        }
        self.validation_raw = encoded(self.validation)
        (self.architecture / 'validation.json').write_bytes(self.validation_raw)
        self.validation_pin = sha(self.validation_raw)
        self.pins = {
            'sourceManifestSha256': self.source_pin,
            'architectureSha256': self.plan_pin,
            'validationSha256': self.validation_pin,
            'catalogSha256': 'a' * 64,
            'contractSha256': 'b' * 64,
        }
        self.stage = {'root': self.architecture,
            'request': {'sourceRoot': str(self.source)}, 'pins': self.pins,
            'plan': self.plan, 'validation': self.validation}

        self.pipeline = self.base / 'Pipeline'
        self.pipeline.mkdir()
        self.task = self.pipeline / 'Modules/0001'
        self.task.mkdir(parents=True)
        self.code = b'namespace Game.Domain.Core { public sealed class PlayerState { public int Coins; } }\n'
        self.target_path = 'Assets/Game/Domain/Core/PlayerState.cs'
        self._make_task_manifest()
        task_receipt = self.task / 'Task/manifest.json'
        task_receipt.parent.mkdir(parents=True, exist_ok=True)
        task_receipt.write_bytes(encoded({
            'schemaVersion': 1, 'status': 'partial', 'outcome': 'future_worker_outcome_v9',
            'responseSummary': 'Implementation stops at a documented integration boundary.',
            'unresolved': ['No runtime JSON reader is wired.', 'Round-rank receipt state is not implemented.', 'UI integration remains pending.'],
            'exitCode': 0, 'stopReason': None,
        }))
        self.task_receipt_pin = sha(task_receipt.read_bytes())
        self.request = {
            'schemaVersion': 1, 'architectureStage': str(self.architecture),
            **self.pins, 'moduleOrder': ['Core'], 'externalReferences': {}, 'retainedSupportPaths': [],
        }
        (self.pipeline / 'request.json').write_bytes(encoded(self.request))
        self.state = {'status': 'candidate_assembled_unvalidated', 'modules': [
            {'id': 'Core', 'status': 'generated_unreviewed', 'task': 'Modules/0001',
             'manifestSha256': self.module_pin}],
        }
        (self.pipeline / 'state.json').write_bytes(encoded(self.state))
        self.output = self.base / 'Reclassified'

    def _source_file(self, path, raw):
        if not hasattr(self, 'source_rows'):
            self.source_rows = []
        target = self.source / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        self.source_rows.append({'path': path, 'sha256': sha(raw), 'bytes': len(raw), 'owner': 'generated'})

    def _make_task_manifest(self, *, output=None):
        output = self.code if output is None else output
        self.code = output
        target = self.task / self.target_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(output)
        manifest = {
            'schemaVersion': 'monkey-native-architecture-module/1', 'moduleId': 'Core',
            'classes': [{'classId': 'player', 'path': self.target_path,
                         'sha256': sha(output), 'bytes': len(output), 'status': 'generated_unreviewed',
                         'sourceUnitIds': ['unit-a'], 'sourceMemberIds': [], 'seedSha256': 'e' * 64}],
            'files': [{'classId': 'player', 'targetPath': self.target_path, 'artifactPath': self.target_path,
                       'sha256': sha(output), 'bytes': len(output), 'status': 'generated_unreviewed'}],
            'compilation': 'not_run', 'runtime': 'not_run', 'acceptance': 'not_reviewed',
        }
        raw = encoded(manifest)
        (self.task / modules.MANIFEST).write_bytes(raw)
        (self.task / modules.MANIFEST_SHA).write_text(sha(raw) + '\n')
        self.module_pin = sha(raw)

    def _recheck_receipt(self, classification='generated_unreviewed'):
        row = {'classId': 'player', 'path': self.target_path,
               'sourceUnitIds': ['unit-a'], 'sourceMemberIds': [], 'sha256': sha(self.code),
               'bytes': len(self.code), 'priorStatus': 'generated_unreviewed',
               'classification': classification, 'completenessDiagnostics': []}
        return {'status': 'rechecked', 'moduleId': 'Core', 'oldManifestSha256': self.module_pin,
                'taskManifestSha256': self.task_receipt_pin,
                'classification': classification, 'classificationCounts': {classification: 1},
                'files': [row], 'compilation': 'not_run', 'runtime': 'not_run',
                'semanticValidation': 'not_performed'}

    def _run_reassembly(self, *, classification='generated_unreviewed'):
        report = self._recheck_receipt(classification)
        with patch.object(modules, '_pin_stage', return_value=self.stage), \
             patch.object(modules, 'status', return_value={'manifestSha256': self.module_pin, 'status': 'generated_unreviewed'}), \
             patch.object(modules, 'recheck', return_value=report):
            return reassemble(self.pipeline, self.output)

    def test_pipeline_collection_with_full_source_coverage_stays_explicitly_unreviewed(self):
        from monkey import code_architecture_pipeline as pipeline
        from monkey.code_architecture_candidate import assemble_native_candidate
        with patch.object(modules, 'status', return_value={
                'manifestSha256': self.module_pin, 'status': 'generated_unreviewed'}):
            aggregate, pin = pipeline._collect(self.pipeline, self.stage, self.state)
        collected = load((aggregate / 'manifest.json').read_bytes())
        self.assertEqual(collected['files'][0]['sourceUnitIds'], ['unit-a'])
        self.assertEqual(collected['files'][0]['status'], 'partial')
        self.assertEqual(collected['files'][0].get('unresolved'),
                         ['Generated output remains semantically unreviewed.'])
        report = assemble_native_candidate(
            self.source, self.source_pin,
            self.architecture / 'architecture.json', self.plan_pin,
            self.architecture / 'validation.json', self.validation_pin,
            aggregate, pin, self.output, allow_partial=True)
        self.assertEqual(report['status'], 'partial')
        self.assertEqual((self.output / self.target_path).read_bytes(), self.code)

    def test_reassembles_only_reclassified_outputs_and_preserves_old_inputs(self):
        prior_state = (self.pipeline / 'state.json').read_bytes()
        prior_manifest = (self.task / modules.MANIFEST).read_bytes()
        report = self._run_reassembly()
        self.assertEqual(report['status'], 'candidate_assembled_unvalidated')
        self.assertEqual(report['implementationStatus'], 'partial_unreviewed')
        self.assertEqual(report['compileStatus'], 'not_run')
        self.assertEqual(report['runtimeStatus'], 'not_run')
        self.assertEqual(report['generatedFilePins'][0]['classification'], 'generated_unreviewed')
        self.assertEqual(report['generatedFilePins'][0]['sha256'], sha(self.code))
        self.assertEqual(report['generatedFilePins'][0]['priorStatus'], 'generated_unreviewed')
        self.assertEqual(report['generatedFilePins'][0]['completenessDiagnostics'], [])
        self.assertEqual(report['modules'][0]['taskManifestSha256'], self.task_receipt_pin)
        self.assertEqual(report['modules'][0]['taskReceipt']['outcome'], 'future_worker_outcome_v9')
        self.assertEqual(report['modules'][0]['taskReceipt']['unresolved'], [
            'No runtime JSON reader is wired.', 'Round-rank receipt state is not implemented.', 'UI integration remains pending.'])
        assembled = self.output / 'UnityProject/Assets/Game/Domain/Core/PlayerState.cs'
        self.assertEqual(assembled.read_bytes(), self.code)
        implementation_manifest = load((self.output / 'Implementation/manifest.json').read_bytes())
        self.assertEqual(implementation_manifest['modules'][0]['responseSummary'],
                         'Implementation stops at a documented integration boundary.')
        unity_manifest = load((self.output / 'UnityProject/manifest.json').read_bytes())
        self.assertEqual(unity_manifest['moduleReceipts'][0]['unresolved'], report['modules'][0]['taskReceipt']['unresolved'])
        self.assertEqual((self.pipeline / 'state.json').read_bytes(), prior_state)
        self.assertEqual((self.task / modules.MANIFEST).read_bytes(), prior_manifest)

    def test_non_generated_classification_remains_missing(self):
        report = self._run_reassembly(classification='unimplemented_seed')
        self.assertEqual(report['generatedFilePins'], [])
        self.assertEqual(report['missingOrRejectedFiles'][0]['classification'], 'unimplemented_seed')
        self.assertEqual(report['assemblyStatus'], 'partial')

    def test_incomplete_pipeline_is_rejected_before_output_creation(self):
        self.state['modules'][0]['status'] = 'checkpoint'
        self.state['status'] = 'running'
        (self.pipeline / 'state.json').write_bytes(encoded(self.state))
        with patch.object(modules, '_pin_stage', return_value=self.stage):
            with self.assertRaises(ParseError) as caught:
                reassemble(self.pipeline, self.output)
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REASSEMBLY_NOT_TERMINAL')
        self.assertFalse(self.output.exists())

    def test_explicit_stopped_checkpoint_records_unfinished_classes_without_shells(self):
        self.plan['modules'].append(dict(id='Later',classIds=['later'],sourceUnitIds=[]))
        self.plan['classes'].append(dict(id='later',name='LaterState',layer='Domain',module='Later',sourceUnitIds=[],fields=[],methods=[]))
        later='Assets/Game/Domain/Later/LaterState.cs'
        self.validation['classPaths']['later']=later
        self.plan_raw=encoded(self.plan);self.plan_pin=sha(self.plan_raw)
        (self.architecture/'architecture.json').write_bytes(self.plan_raw)
        self.validation_raw=encoded(self.validation);self.validation_pin=sha(self.validation_raw)
        (self.architecture/'validation.json').write_bytes(self.validation_raw)
        self.pins.update(architectureSha256=self.plan_pin,validationSha256=self.validation_pin)
        self.request.update(self.pins,moduleOrder=['Core','Later'])
        (self.pipeline/'request.json').write_bytes(encoded(self.request))
        self.state['status']='integration_checkpoint'
        self.state['modules'].append(dict(id='Later',status='pending',task='Modules/0002'))
        old_state=encoded(self.state);(self.pipeline/'state.json').write_bytes(old_state)
        receipt=self._recheck_receipt()
        with patch.object(modules,'_pin_stage',return_value=self.stage), \
             patch.object(modules,'status',return_value=dict(status='generated_unreviewed',manifestSha256=self.module_pin)), \
             patch.object(modules,'recheck',return_value=receipt):
            report=reassemble(self.pipeline,self.output,allow_incomplete=True)
        self.assertTrue(report['incompleteCheckpoint'])
        self.assertFalse((self.output/'UnityProject'/later).exists())
        manifest=load((self.output/'UnityProject/manifest.json').read_bytes())
        self.assertIn(later,manifest['missingClassPaths'])
        self.assertEqual(report['modules'][1]['classification'],'not_generated')
        self.assertEqual((self.pipeline/'state.json').read_bytes(),old_state)

    def test_checkpoint_option_does_not_allow_a_running_writer(self):
        self.state['status']='running';self.state['modules'][0]['status']='running'
        (self.pipeline/'state.json').write_bytes(encoded(self.state))
        with patch.object(modules,'_pin_stage',return_value=self.stage):
            with self.assertRaises(ParseError) as error:reassemble(self.pipeline,self.output,allow_incomplete=True)
        self.assertEqual(error.exception.code,'CODE_ARCH_REASSEMBLY_NOT_STOPPED')
        self.assertFalse(self.output.exists())

    def test_module_manifest_pin_mismatch_rejects_without_output(self):
        self.state['modules'][0]['manifestSha256'] = 'f' * 64
        (self.pipeline / 'state.json').write_bytes(encoded(self.state))
        with patch.object(modules, '_pin_stage', return_value=self.stage), \
             patch.object(modules, 'status', return_value={'manifestSha256': self.module_pin, 'status': 'generated_unreviewed'}):
            with self.assertRaises(ParseError) as caught:
                reassemble(self.pipeline, self.output)
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REASSEMBLY_MODULE_PIN')
        self.assertFalse(self.output.exists())

    def test_recheck_file_hash_drift_rejects_without_output(self):
        bad = self._recheck_receipt()
        bad['files'][0]['sha256'] = '0' * 64
        with patch.object(modules, '_pin_stage', return_value=self.stage), \
             patch.object(modules, 'status', return_value={'manifestSha256': self.module_pin, 'status': 'generated_unreviewed'}), \
             patch.object(modules, 'recheck', return_value=bad):
            with self.assertRaises(ParseError) as caught:
                reassemble(self.pipeline, self.output)
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REASSEMBLY_ARTIFACT_PIN')
        self.assertFalse(self.output.exists())

    def test_task_receipt_drift_during_assembly_rejects_and_cleans_output(self):
        receipt = self._recheck_receipt()
        original_assembler = reassembly.assemble_native_candidate

        def assemble_then_tamper(*args, **kwargs):
            result = original_assembler(*args, **kwargs)
            (self.task / 'Task/manifest.json').write_bytes(encoded({
                'schemaVersion': 1, 'status': 'partial', 'outcome': 'tampered',
                'responseSummary': 'changed', 'unresolved': ['changed'],
            }))
            return result

        with patch.object(modules, '_pin_stage', return_value=self.stage), \
             patch.object(modules, 'status', return_value={'manifestSha256': self.module_pin, 'status': 'generated_unreviewed'}), \
             patch.object(modules, 'recheck', return_value=receipt), \
             patch.object(reassembly, 'assemble_native_candidate', side_effect=assemble_then_tamper):
            with self.assertRaises(ParseError) as caught:
                reassemble(self.pipeline, self.output)
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REASSEMBLY_TASK_RECEIPT_RACE')
        self.assertFalse(self.output.exists())

    def test_large_standard_manifest_survives_receipt_handoff(self):
        original_assembler = reassembly.assemble_native_candidate
        extra = 'resource provenance ' * 500000

        def assemble_large_manifest(*args, **kwargs):
            result = original_assembler(*args, **kwargs)
            path = Path(args[8]) / 'manifest.json'
            manifest = load(path.read_bytes())
            manifest['retainedResourceProvenance'] = extra
            path.write_bytes(encoded(manifest))
            return result

        with patch.object(reassembly, 'assemble_native_candidate', side_effect=assemble_large_manifest):
            report = self._run_reassembly()
        path = self.output / 'UnityProject/manifest.json'
        manifest = load(path.read_bytes())
        self.assertGreater(path.stat().st_size, 8 * 1024 * 1024)
        self.assertEqual(manifest['retainedResourceProvenance'], extra)
        self.assertEqual(manifest['moduleReceipts'][0]['unresolved'],
                         load((self.task / 'Task/manifest.json').read_bytes())['unresolved'])
        self.assertEqual(report['unityProjectManifestSha256'], sha(path.read_bytes()))

    def test_rejects_class_claimed_by_wrong_module(self):
        self.plan['classes'][0]['module'] = 'Other'
        self.stage['plan'] = self.plan
        with patch.object(modules, '_pin_stage', return_value=self.stage), \
             patch.object(modules, 'status', return_value={'manifestSha256': self.module_pin, 'status': 'generated_unreviewed'}), \
             patch.object(modules, 'recheck', return_value=self._recheck_receipt()):
            with self.assertRaises(ParseError) as caught:
                reassemble(self.pipeline, self.output)
        self.assertEqual(caught.exception.code, 'CODE_ARCH_REASSEMBLY_CLASS_OWNERSHIP')
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
