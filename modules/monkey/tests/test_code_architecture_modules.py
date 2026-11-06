import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from monkey import code_architecture, code_architecture_modules as modules
from monkey.code_architecture_contract import validate_architecture
from monkey.io import encoded, sha
from monkey.sources.compiled import ParseError


class ArchitectureModuleWorkflowTests(unittest.TestCase):
    def test_pinned_inherited_members_count_without_clearing_layer_guards(self):
        parent = dict(classId='ViewBase', name='ViewBase', kind='class', layer='Presentation',
                      module='UI', namespace='Demo.Presentation.UI', path='Base.cs',
                      plannedMethods=[], plannedFields=[])
        child = dict(parent, classId='View', name='View', path='View.cs',
                     plannedMethods=[{'name':'Bind'}], plannedFields=[{'name':'Snapshot'}])
        sources = {
            'Base.cs': b'namespace Demo.Presentation.UI { public class ViewBase { public void Bind() {} protected int Snapshot { get; set; } } }',
            'View.cs': b'using Demo.Services.Store; namespace Demo.Presentation.UI { public class View : ViewBase { public int Local; } }',
        }
        evidence = modules._module_inheritance_evidence([parent,child], sources)['View']
        direct = modules._implementation_markers(sources['View.cs'], child)
        self.assertIn('planned-method-declaration-missing:Bind', direct)
        checked = modules._implementation_markers(sources['View.cs'], child, inheritance_evidence=evidence)
        self.assertEqual(checked, ['layer-dependency-reference:Services'])
        changed = sources['View.cs'].replace(b'Local', b'Changed')
        self.assertIn('planned-method-declaration-missing:Bind',
                      modules._implementation_markers(changed, child, inheritance_evidence=evidence))
        sources['Base.cs'] = b'using Demo.Services.Store; ' + sources['Base.cs']
        blocked = modules._module_inheritance_evidence([parent,child], sources)['View']
        self.assertTrue(blocked['blockers'])
        self.assertIn('planned-method-declaration-missing:Bind',
                      modules._implementation_markers(sources['View.cs'], child, inheritance_evidence=blocked))

    def test_private_parent_and_unrelated_classes_cannot_supply_planned_api(self):
        parent = dict(classId='Base', name='Base', kind='class', layer='Presentation',
                      module='UI', namespace='Demo.Presentation.UI', path='Base.cs',
                      plannedMethods=[], plannedFields=[])
        child = dict(parent, classId='View', name='View', path='View.cs',
                     plannedMethods=[{'name':'Bind'}])
        sources = {
            'Base.cs': b'namespace Demo.Presentation.UI { public class Base { private void Bind() {} } }',
            'View.cs': b'namespace Demo.Presentation.UI { public class View : Base { public int Local; } }',
        }
        evidence = modules._module_inheritance_evidence([parent,child], sources)['View']
        self.assertIn('planned-method-declaration-missing:Bind',
                      modules._implementation_markers(sources['View.cs'], child, inheritance_evidence=evidence))
        sources['Base.cs'] = sources['Base.cs'].replace(b'private', b'public')
        sources['View.cs'] = sources['View.cs'].replace(b' : Base', b'')
        evidence = modules._module_inheritance_evidence([parent,child], sources)['View']
        self.assertIn('planned-method-declaration-missing:Bind',
                      modules._implementation_markers(sources['View.cs'], child, inheritance_evidence=evidence))

    def test_gameplay_cannot_construct_service_store_but_services_can_implement_gameplay_port(self):
        record=dict(name='Coordinator',kind='class',layer='Gameplay',module='Session',
                    namespace='Demo.Gameplay.Session',plannedMethods=[],plannedFields=[])
        bad=b'using Demo.Services.Session; namespace Demo.Gameplay.Session { public class Coordinator { private VersionedStore store; } }'
        self.assertIn('layer-dependency-reference:Services',modules._implementation_markers(bad,record))
        harmless=b'namespace Demo.Gameplay.Session { public class Coordinator { /* Demo.Services.Session */ public string Note = "Demo.Services.Session"; } }'
        self.assertNotIn('layer-dependency-reference:Services',modules._implementation_markers(harmless,record))
        service=dict(record,layer='Services',namespace='Demo.Services.Session')
        allowed=b'using Demo.Gameplay.Session; namespace Demo.Services.Session { public class Coordinator { public int Revision; } }'
        self.assertEqual(modules._implementation_markers(allowed,service),[])

    def _prepare_recoverable_module(self, root):
        stage, _, _, _, _ = self.make_stage(root)
        out = root / 'Module'
        with patch.object(modules.worker, 'prepare', side_effect=self.fake_worker_prepare):
            modules.prepare(stage, 'Recipe', out)
        module_request = json.loads((out / 'request.json').read_bytes())
        module_manifest = json.loads((out / modules.MANIFEST).read_bytes())
        task_root = out / 'Task'; workspace = task_root / 'workspace'
        selected = []
        for row in module_manifest['files']:
            path = row['targetPath']; seed = (out / 'Seed' / path).read_bytes()
            selected.append({'path': path, 'bytes': len(seed), 'sha256': sha(seed),
                             'sourceKind': 'architecture-seed'})
        worker_context = {}
        for name, pin in module_request['contextFiles'].items():
            workspace_name = '__Context/' + name
            worker_context[workspace_name] = {'sourcePath': name, 'sha256': pin['sha256'], 'bytes': pin['bytes']}
            copy = workspace / workspace_name
            copy.chmod(0o400)
        for directory in sorted((workspace / '__Context').rglob('*'), reverse=True):
            if directory.is_dir():
                directory.chmod(0o500)
        (workspace / '__Context').chmod(0o500)
        modules.worker._init_isolated_git(workspace)
        baseline = {}
        for path in workspace.rglob('*'):
            relative = path.relative_to(workspace).as_posix()
            if relative == '.git' or relative.startswith('.git/') or path.is_dir():
                continue
            baseline[relative] = sha(path.read_bytes())
        (task_root / 'baseline.json').write_bytes(encoded(baseline))
        codex = root / 'codex'; codex.write_text('#!/bin/sh\nexit 0\n'); codex.chmod(0o755)
        _, codex_identity = modules.worker._resolve_codex(codex)
        seed_manifest_raw = (out / 'Seed/manifest.json').read_bytes()
        seed_identity = json.loads(seed_manifest_raw)['identity']
        task_request = {
            'schemaVersion': 1, 'state': 'prepared', 'runId': str(uuid.uuid4()),
            'taskSha256': 'a' * 64, 'codexPath': str(codex), 'codexIdentity': codex_identity,
            'base': {'candidateRoot': str(out / 'Seed'), 'manifestPath': 'manifest.json',
                     'manifestSha256': sha(seed_manifest_raw), 'candidateIdentity': seed_identity},
            'selected': selected, 'contextFiles': worker_context,
            'workspaceBudgetBytes': 64 * 1024 * 1024, 'selectedFileMaxBytes': 16 * 1024 * 1024,
            'projectBatch': False, 'projectResultLedger': False,
            'producer': {'version': 'test'},
        }
        (task_root / 'request.json').write_bytes(encoded(task_request))
        rel = selected[0]['path']; generated = b'namespace Demo.Domain.Recipe { public sealed class RecipeCatalog { public int Count; public int GetCount() => 7; } }\n'
        (workspace / rel).write_bytes(generated)
        response = {'status': 'partial', 'changedPaths': [rel], 'unresolved': ['review pending'],
                    'summary': 'Completed isolated response awaiting review.'}
        events = [
            {'type': 'thread.started', 'thread_id': '123e4567-e89b-42d3-a456-426614174000'},
            {'type': 'item.completed', 'item': {'id': 'item_1', 'type': 'agent_message',
             'text': json.dumps(response)}},
            {'type': 'turn.completed', 'usage': {'input_tokens': 4, 'output_tokens': 5}},
        ]
        (task_root / 'events.jsonl').write_bytes(b''.join(
            (json.dumps(event, separators=(',', ':')) + '\n').encode() for event in events))
        process = {'state': 'running', 'pid': 2147483000, 'attempt': 0, 'sessionId': None,
                   'startedAtUnix': 1.0}
        (task_root / 'process.json').write_bytes(encoded(process))
        active = root / 'active.json'
        active.write_bytes(encoded({'state': 'running', 'pid': process['pid'], 'attempt': 0}))
        return out, task_root, module_request, rel, generated, active

    def make_stage(self, root):
        stage = root / 'Global'
        (stage / 'Evidence' / 'Sources').mkdir(parents=True)
        (stage / 'Evidence' / 'Config').mkdir()
        (stage / 'Task' / 'workspace' / 'Analysis' / 'Architecture').mkdir(parents=True)
        (stage / 'Task').mkdir(exist_ok=True)

        candidate = root / 'FrozenCandidate'
        (candidate / 'Packages').mkdir(parents=True)
        (candidate / 'ProjectSettings').mkdir()
        package_raw = b'{"dependencies":{"com.unity.ugui":"2.6.0"}}\n'
        version_raw = b'm_EditorVersion: 6000.6.2f1\n'
        source = b'function recipe(){ return 7; }'
        source_path = 'SourceRecovery/Code/Source/Source.js'
        config_raw = b'{"items":[1,2]}'
        config_path = 'Assets/Game/Content/Config/Recipe.json'
        (candidate / 'Packages/manifest.json').write_bytes(package_raw)
        (candidate / 'ProjectSettings/ProjectVersion.txt').write_bytes(version_raw)
        source_file = candidate / source_path
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_bytes(source)
        config_file = candidate / config_path
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_bytes(config_raw)
        candidate_manifest = encoded({'schemaVersion': 1, 'targetProfile': 'unity-6000.6.2f1-ugui',
            'namespace': 'Demo', 'scopeMode': 'whole-input', 'files': [
                {'path': 'Packages/manifest.json', 'sha256': sha(package_raw), 'bytes': len(package_raw), 'owner': 'generated'},
                {'path': 'ProjectSettings/ProjectVersion.txt', 'sha256': sha(version_raw), 'bytes': len(version_raw), 'owner': 'generated'},
                {'path': source_path, 'sha256': sha(source), 'bytes': len(source), 'owner': 'retained'},
                {'path': config_path, 'sha256': sha(config_raw), 'bytes': len(config_raw), 'owner': 'generated'}]})
        (candidate / 'manifest.json').write_bytes(candidate_manifest)
        source_pin = sha(candidate_manifest)

        source_hash = sha(source)
        member_id = '21af08e48846:methods@0:30'
        unit_id = 'module:21af08e48846:0:30'
        class_record = {
            'id': 'RecipeCatalog', 'name': 'RecipeCatalog', 'layer': 'Domain', 'module': 'Recipe',
            'kind': 'class', 'responsibility': 'Own recipe lookup rules',
            'stateOwnership': 'RecipeCatalog is the only owner of recipe lookup state',
            'lifecycle': 'Constructed by the composition root and retained for gameplay use',
            'dependsOn': [], 'typeDependencies': [], 'sourceUnitIds': [unit_id],
            'fields': [{'name': 'Count', 'type': 'int', 'role': 'Source-backed recipe count'}],
            'methods': [{'name': 'GetCount', 'returnType': 'int', 'parameters': [], 'sourceMemberIds': [member_id]}],
        }
        bootstrap_record = {
            'id': 'AppStartup', 'name': 'AppStartup', 'layer': 'Bootstrap', 'module': 'App',
            'kind': 'class', 'responsibility': 'Compose the application',
            'stateOwnership': 'Owns application composition only', 'lifecycle': 'Created at application startup',
            'dependsOn': ['Domain'], 'typeDependencies': ['RecipeCatalog'], 'sourceUnitIds': [],
            'fields': [], 'methods': [],
        }
        gameplay_record = {
            'id': 'RecipeRules', 'name': 'RecipeRules', 'layer': 'Gameplay', 'module': 'RecipeFlow',
            'kind': 'class', 'responsibility': 'Coordinate recipe gameplay rules',
            'stateOwnership': 'Owns no persistent state', 'lifecycle': 'Created by application composition',
            'dependsOn': ['Domain'], 'typeDependencies': ['RecipeCatalog'], 'sourceUnitIds': [],
            'fields': [], 'methods': [],
        }
        presentation_record = {
            'id': 'RecipePanel', 'name': 'RecipePanel', 'layer': 'Presentation', 'module': 'RecipeUI',
            'kind': 'class', 'responsibility': 'Present recipe information',
            'stateOwnership': 'Owns transient presentation state', 'lifecycle': 'Created with the recipe screen',
            'dependsOn': ['Gameplay'], 'typeDependencies': ['RecipeRules'], 'sourceUnitIds': [],
            'fields': [], 'methods': [],
        }
        plan = {
            'schemaVersion': code_architecture.SCHEMA, 'sourceManifestSha256': source_pin,
            'rootNamespace': 'Demo', 'modules': [{'id': 'Recipe', 'responsibility': 'Recipe lookup',
                'sourceUnitIds': [unit_id], 'classIds': ['RecipeCatalog']},
                {'id': 'App', 'responsibility': 'Compose runtime services and gameplay entry points',
                 'sourceUnitIds': [], 'classIds': ['AppStartup']},
                {'id': 'RecipeFlow', 'responsibility': 'Coordinate recipe flow',
                 'sourceUnitIds': [], 'classIds': ['RecipeRules']},
                {'id': 'RecipeUI', 'responsibility': 'Present recipe data',
                 'sourceUnitIds': [], 'classIds': ['RecipePanel']}],
            'classes': [class_record, bootstrap_record, gameplay_record, presentation_record],
            'sourceCoverage': [{'sourceUnitId': unit_id, 'disposition': 'planned',
                'classIds': ['RecipeCatalog'], 'reason': 'Mapped to the typed recipe catalog.'}],
            'entryPoint': {'classId': 'AppStartup', 'initializationOrder': ['AppStartup']},
            'integrationChains': [{'id': 'recipe-config-chain', 'classIds': ['RecipeCatalog', 'RecipeRules', 'RecipePanel', 'AppStartup'],
                'configPaths': [config_path], 'assetPaths': [], 'behavior': 'Loads recipe configuration.',
                'sourceUnitIds': [unit_id]}],
            'limitations': ['This synthetic plan is for isolated API tests only.'],
        }
        member = {'id': member_id, 'kind': 'methods', 'name': 'GetCount',
                  'sourceBytes': {'start': 0, 'end': len(source)}, 'sourceSha256': source_hash,
                  'parameters': [], 'sourceType': 'int', 'static': False}
        unit = {'id': unit_id, 'kind': 'registered-source-module', 'sourceNames': ['recipe'],
                'sourceIds': ['synthetic:recipe'], 'sourceSha256': source_hash,
                'sourceBytes': {'start': 0, 'end': len(source)}, 'spanSha256': source_hash,
                'memberCount': 1, 'members': [member]}
        catalog = {'schemaVersion': 1, 'sourceManifestSha256': source_pin,
                   'sourceRoot': str(candidate), 'sourceManifestName': 'manifest.json',
                   'sourceUnits': [unit], 'sources': [{'sha256': source_hash, 'bytes': len(source),
                       'sourcePath': 'SourceRecovery/Code/Source/Source.js',
                       'contextPath': '__Context/Sources/source.js', 'snapshotPaths': ['snapshot/game.js']}],
                   'configurations': [{'path': config_path, 'sha256': sha(config_raw), 'bytes': len(config_raw),
                       'contextPath': '__Context/Config/0.json'}], 'assets': [], 'memberShards': [],
                   'registeredMemberCount': 1, 'sourceExecuted': False}
        contract = code_architecture._contract('Demo')
        plan_raw, catalog_raw, contract_raw = encoded(plan), encoded(catalog), encoded(contract)
        validation = validate_architecture(plan, catalog)
        validation_raw = encoded(validation)

        (stage / 'Evidence' / 'source-catalog.json').write_bytes(catalog_raw)
        (stage / 'Evidence' / 'architecture-contract.json').write_bytes(contract_raw)
        (stage / 'Evidence' / 'Sources' / 'source.js').write_bytes(source)
        (stage / 'Evidence' / 'Config' / '0.json').write_bytes(config_raw)
        (stage / 'architecture.json').write_bytes(plan_raw)
        (stage / 'validation.json').write_bytes(validation_raw)
        (stage / 'Task' / 'workspace' / code_architecture.PLAN_PATH).write_bytes(plan_raw)
        (stage / 'Task' / 'manifest.json').write_bytes(encoded({'actualChanges': [
            {'path': code_architecture.PLAN_PATH, 'afterSha256': sha(plan_raw)}]}))
        (stage / 'Task' / 'request.json').write_bytes(encoded({'state': 'completed', 'contextFiles': {
            '__Context/source-catalog.json': {'sha256': sha(catalog_raw), 'bytes': len(catalog_raw)},
            '__Context/architecture-contract.json': {'sha256': sha(contract_raw), 'bytes': len(contract_raw)},
        }}))
        (stage / 'request.json').write_bytes(encoded({'sourceManifestSha256': source_pin,
            'catalogSha256': sha(catalog_raw), 'sourceRoot': str(candidate)}))
        (stage / 'state.json').write_bytes(encoded({'status': 'architecture_designed'}))
        return stage, source, config_raw, class_record, plan

    @staticmethod
    def fake_worker_prepare(candidate, selected, expected, output, task, **kwargs):
        candidate = Path(candidate); output = Path(output); output.mkdir(parents=True)
        workspace = output / 'workspace'; workspace.mkdir()
        for rel in selected:
            target = workspace / rel; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((candidate / rel).read_bytes())
        context_workspace = workspace / '__Context'
        for rel in kwargs['context_files']:
            target = context_workspace / rel; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((Path(kwargs['context_root']) / rel).read_bytes())
        (output / 'request.json').write_bytes(encoded({'state': 'prepared'}))
        return SimpleNamespace(output=output)

    def test_class_owned_config_is_supplied_without_representative_chain(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory)
            stage_path, _, config, _, _ = self.make_stage(root)
            stage = modules._pin_stage(stage_path)
            cls = stage['plan']['classes'][0]
            config_path = stage['catalog']['configurations'][0]['path']
            cls['configPaths'] = [config_path, config_path]
            stage['plan']['integrationChains'][0]['configPaths'] = []
            files, summary = modules._copy_stage_context(stage, [cls], stage['plan']['modules'][0], root / 'Context')
            self.assertEqual(summary['configPaths'], [config_path])
            self.assertEqual(len(summary['configFiles']), 1)
            self.assertEqual((root / 'Context/Config/000.json').read_bytes(), config)
            self.assertEqual(files['Config/000.json']['sha256'], sha(config))

    def test_class_owned_config_keeps_hash_and_catalog_guards(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory)
            stage_path, _, _, _, _ = self.make_stage(root)
            stage = modules._pin_stage(stage_path)
            cls = stage['plan']['classes'][0]
            cls['configPaths'] = [stage['catalog']['configurations'][0]['path']]
            stage['plan']['integrationChains'][0]['configPaths'] = []
            (stage_path / 'Evidence/Config/0.json').write_bytes(b'{"items":[999]}')
            with self.assertRaises(ParseError) as caught:
                modules._copy_stage_context(stage, [cls], stage['plan']['modules'][0], root / 'Context')
            self.assertEqual(caught.exception.code, 'CODE_ARCH_MODULE_CONFIG')

    def test_failed_new_prepare_preserves_evidence_outside_pipeline_slot(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory)
            stage, _, _, _, _ = self.make_stage(root)
            output = root / 'Module'
            def fail_after_copy(*args, **kwargs):
                raise ParseError('CODE_ARCH_ASSET_BUDGET', 'module-asset-bindings.json', 'Too large')
            with patch.object(modules.asset_contexts, 'write_module_context', side_effect=fail_after_copy), \
                    patch.object(modules.worker, 'prepare') as worker_prepare:
                with self.assertRaises(ParseError):
                    modules.prepare(stage, 'Recipe', output)
            worker_prepare.assert_not_called()
            self.assertFalse(output.exists())
            archives = list(root.glob('Module.prepare-failed-*'))
            self.assertEqual(len(archives), 1)
            self.assertEqual((archives[0] / 'Evidence/Config/000.json').read_bytes(), b'{"items":[1,2]}')
            failure = json.loads((archives[0] / 'prepare-failure.json').read_bytes())
            self.assertEqual(failure['errorCode'], 'CODE_ARCH_ASSET_BUDGET')
            self.assertFalse(failure['modelInvoked'])

    def test_existing_prepare_output_is_never_archived(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory)
            stage, _, _, _, _ = self.make_stage(root)
            output = root / 'Module'; output.mkdir()
            (output / 'keep.txt').write_bytes(b'owned by caller')
            with self.assertRaises(ParseError):
                modules.prepare(stage, 'Recipe', output)
            self.assertEqual((output / 'keep.txt').read_bytes(), b'owned by caller')
            self.assertEqual(list(root.glob('Module.prepare-failed-*')), [])

    def test_supplemental_native_integration_api_is_pinned_readonly_context_not_source_ownership(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root=Path(directory);stage,_,_,_,_=self.make_stage(root);out=root/'Module'
            helper=root/'NativeCoordinator.cs';raw=b'namespace Demo.Gameplay { public class NativeCoordinator { public int Revision; } }'
            helper.write_bytes(raw)
            with patch.object(modules.worker,'prepare',side_effect=self.fake_worker_prepare):
                modules.prepare(stage,'Recipe',out,supplemental_sources=[dict(path=str(helper),sha256=sha(raw))])
            request=json.loads((out/'request.json').read_text())
            copied=out/'Evidence/SupplementalNative'/f'{sha(raw)}.cs'
            self.assertEqual(copied.read_bytes(),raw)
            listing=json.loads((out/'Evidence/supplemental-native-inputs.json').read_text())
            self.assertEqual(listing['files'][0]['role'],'native-integration-input;not-original-source-ownership')
            self.assertEqual(helper.read_bytes(),raw)
            self.assertIn(f'SupplementalNative/{sha(raw)}.cs',request['contextFiles'])
            # Drift in the frozen context is rejected before a model can run.
            copied.write_bytes(raw+b'changed')
            with patch.object(modules.worker,'run') as running:
                with self.assertRaises(ParseError):modules.run(out)
                running.assert_not_called()

    def test_supplemental_hash_mismatch_never_starts_model_and_preserves_failure(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root=Path(directory);stage,_,_,_,_=self.make_stage(root);out=root/'Module'
            helper=root/'Native.cs';helper.write_text('namespace Demo { class Native {} }')
            with patch.object(modules.worker,'prepare') as preparing:
                with self.assertRaises(ParseError) as error:
                    modules.prepare(stage,'Recipe',out,supplemental_sources=[dict(path=str(helper),sha256='0'*64)])
                preparing.assert_not_called()
            self.assertEqual(error.exception.code,'CODE_ARCH_MODULE_SUPPLEMENT')
            self.assertFalse(out.exists());self.assertEqual(len(list(root.glob('Module.prepare-failed-*'))),1)

    def test_prepare_pins_exact_module_source_config_and_empty_seed(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory)
            stage, source, config, record, _ = self.make_stage(root)
            out = root / 'Module'
            with patch.object(modules.worker, 'prepare', side_effect=self.fake_worker_prepare) as prepare:
                result = modules.prepare(stage, 'Recipe', out)
            self.assertEqual(result['status'], 'prepared')
            manifest = json.loads((out / modules.MANIFEST).read_text())
            self.assertEqual(manifest['sourceUnitIds'], record['sourceUnitIds'])
            self.assertEqual(manifest['classes'][0]['namespace'], 'Demo.Domain.Recipe')
            self.assertIn('methods@0:30', manifest['sourceMemberIds'][0])
            self.assertEqual(manifest['sourceContexts'][0]['sourceSha256'], sha(source))
            self.assertEqual(manifest['sourceContexts'][0]['spanSha256'], sha(source))
            selected = prepare.call_args.args[1]
            self.assertEqual(selected, ['Assets/Game/Domain/Recipe/RecipeCatalog.cs'])
            context_files = prepare.call_args.kwargs['context_files']
            self.assertIn('architecture.json', context_files)
            self.assertIn('module-source-map.json', context_files)
            self.assertIn('module-config-map.json', context_files)
            self.assertIn('module-asset-bindings.json', context_files)
            asset_report = json.loads((out / 'Evidence' / 'module-asset-bindings.json').read_text())
            self.assertEqual(asset_report['status'], 'no-code-bindings-for-selected-owners')
            self.assertIn('typed serialized native references', asset_report['runtimeUse'])
            self.assertEqual(manifest['assetBindingContext']['path'], '__Context/module-asset-bindings.json')
            self.assertIn('UnityEnvironment/Packages/manifest.json', context_files)
            self.assertIn('UnityEnvironment/ProjectSettings/ProjectVersion.txt', context_files)
            summary = json.loads((out / 'Evidence' / 'architecture.json').read_text())
            self.assertNotIn('classes', summary)
            reconstructed = {key: value for key, value in summary.items() if key not in ('classCount', 'classShards')}
            classes = []
            for shard in summary['classShards']:
                shard_path = out / 'Evidence' / shard['path'].removeprefix('__Context/')
                shard_raw = shard_path.read_bytes()
                self.assertEqual(sha(shard_raw), shard['sha256'])
                self.assertEqual(len(shard_raw), shard['bytes'])
                classes.extend(json.loads(shard_raw)['classes'])
            reconstructed['classes'] = classes
            self.assertEqual(reconstructed, json.loads((stage / 'architecture.json').read_text()))
            self.assertEqual((out / 'Evidence' / 'Sources' / f"{sha(source)[:12]}-0-{len(source)}.js").read_bytes(), source)
            self.assertEqual((out / 'Evidence' / 'Config' / '000.json').read_bytes(), config)
            seed = (out / 'Seed' / selected[0]).read_bytes()
            self.assertIn(b'NOT IMPLEMENTED', seed)
            self.assertNotIn(b'public sealed class RecipeCatalog', seed)
            app_out = root / 'AppModule'
            with patch.object(modules.worker, 'prepare', side_effect=self.fake_worker_prepare):
                modules.prepare(stage, 'App', app_out)
            app_manifest = json.loads((app_out / modules.MANIFEST).read_text())
            self.assertEqual(app_manifest['pendingImplementations'], ['RecipeCatalog'])
            self.assertEqual(app_manifest['dependencies'], [])

    def test_run_materializes_unreviewed_module_and_refuses_context_drift(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory)
            stage, _, _, _, _ = self.make_stage(root)
            out = root / 'Module'
            with patch.object(modules.worker, 'prepare', side_effect=self.fake_worker_prepare):
                modules.prepare(stage, 'Recipe', out)
            context_path = next((out / 'Evidence').glob('Sources/*.js'))
            original_context = context_path.read_bytes()

            def fake_run(task_root, *, session_id=None):
                task_root = Path(task_root)
                selected = task_root / 'workspace' / 'Assets/Game/Domain/Recipe/RecipeCatalog.cs'
                generated = b'namespace Demo.Domain.Recipe { public sealed class RecipeCatalog { public int Count; public int GetCount() => 7; } }\n'
                selected.write_bytes(generated)
                (task_root / 'request.json').write_bytes(encoded({'state': 'completed'}))
                return {'status': 'complete', 'actualChanges': [{'path': 'Assets/Game/Domain/Recipe/RecipeCatalog.cs',
                    'afterSha256': sha(generated)}], 'declaredChangedPaths': ['Assets/Game/Domain/Recipe/RecipeCatalog.cs'],
                    'gitBoundary': {'valid': True}, 'unresolved': []}

            with patch.object(modules.worker, 'run', side_effect=fake_run):
                result = modules.run(out)
            self.assertEqual(result['status'], 'generated_unreviewed')
            self.assertEqual(result['compilation'], 'not_run')
            manifest = json.loads((out / modules.MANIFEST).read_text())
            self.assertEqual(manifest['classes'][0]['status'], 'generated_unreviewed')
            self.assertEqual((out / manifest['files'][0]['artifactPath']).read_bytes(),
                             b'namespace Demo.Domain.Recipe { public sealed class RecipeCatalog { public int Count; public int GetCount() => 7; } }\n')
            app_out = root / 'AppModule'
            with patch.object(modules.worker, 'prepare', side_effect=self.fake_worker_prepare):
                modules.prepare(stage, 'App', app_out, dependency_roots=[out])
            app_manifest = json.loads((app_out / modules.MANIFEST).read_text())
            self.assertEqual(app_manifest['dependencies'][0]['reviewStatus'], 'generated_unreviewed')
            self.assertEqual(app_manifest['pendingImplementations'], [])
            module_manifest = json.loads((out / modules.MANIFEST).read_text())
            module_manifest['classes'][0]['status'] = 'accepted'
            module_manifest['acceptance'] = 'accepted'
            tampered = encoded(module_manifest)
            (out / modules.MANIFEST).write_bytes(tampered)
            (out / modules.MANIFEST_SHA).write_text(sha(tampered) + '\n')
            with patch.object(modules.worker, 'prepare', side_effect=self.fake_worker_prepare):
                with self.assertRaises(ParseError):
                    modules.prepare(stage, 'App', root / 'AppModule2', dependency_roots=[out])

    def test_recover_materializes_completed_worker_output_and_recheck_is_read_only(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory); out, task_root, _, rel, _, active = self._prepare_recoverable_module(root)
            with patch.object(modules.worker, 'GLOBAL_LOCK_PATH', root / 'worker.lock'), \
                    patch.object(modules.worker, 'ACTIVE_PROCESS_PATH', active):
                result = modules.recover(out)
                self.assertEqual(result['status'], 'generated_unreviewed')
                manifest = json.loads((out / modules.MANIFEST).read_bytes())
                self.assertEqual(manifest['workerRecovery']['status'], 'completed-event-recovered')
                self.assertEqual(manifest['workerRecovery']['exitCode'], None)
                self.assertEqual(manifest['workerRecovery']['returnCode'], None)
                protected = [out / modules.MANIFEST, out / modules.MANIFEST_SHA, out / 'state.json',
                             out / 'worker-active-original.json',
                             out / rel, task_root / 'request.json', task_root / 'process.json',
                             task_root / 'manifest.json', task_root / 'recovery-receipt.json']
                before = [sha(path.read_bytes()) for path in protected]
                checked = modules.recheck(out)
                after = [sha(path.read_bytes()) for path in protected]
            self.assertEqual(before, after)
            self.assertEqual(checked['status'], 'rechecked')
            self.assertEqual(checked['workerRecovery']['exitStatus'], 'exit-not-recorded')

    def test_recover_rejects_incomplete_event_stream_without_materializing(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory); out, task_root, _, rel, _, active = self._prepare_recoverable_module(root)
            (task_root / 'events.jsonl').write_bytes(b'{"type":"item.completed"}\n')
            state_before = (out / 'state.json').read_bytes()
            with patch.object(modules.worker, 'GLOBAL_LOCK_PATH', root / 'worker.lock'), \
                    patch.object(modules.worker, 'ACTIVE_PROCESS_PATH', active):
                with self.assertRaises(ParseError):
                    modules.recover(out)
            self.assertEqual((out / 'state.json').read_bytes(), state_before)
            self.assertFalse((out / rel).exists())
            self.assertFalse((task_root / 'manifest.json').exists())

    def test_recover_rejects_global_active_attempt_or_run_mismatch(self):
        for field, value in (('attempt', 9), ('runId', '123e4567-e89b-42d3-a456-426614174001')):
            with self.subTest(field=field), tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
                root = Path(directory); out, task_root, _, rel, _, active = self._prepare_recoverable_module(root)
                active_record = json.loads(active.read_bytes())
                active_record[field] = value
                active.write_bytes(encoded(active_record))
                with patch.object(modules.worker, 'GLOBAL_LOCK_PATH', root / 'worker.lock'), \
                        patch.object(modules.worker, 'ACTIVE_PROCESS_PATH', active), \
                        patch.object(modules.worker, 'recover_completed') as worker_recover:
                    with self.assertRaises(ParseError):
                        modules.recover(out)
                worker_recover.assert_not_called()
                self.assertFalse((task_root / 'manifest.json').exists())
                self.assertFalse((out / rel).exists())

    def test_read_only_recheck_still_rejects_ordinary_nonzero_worker_exit(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory); out, task_root, _, _, _, _ = self._prepare_recoverable_module(root)
            (task_root / 'request.json').write_bytes(encoded({'state': 'finalized', 'exitCode': 7}))
            (task_root / 'process.json').write_bytes(encoded({'state': 'exited', 'returnCode': 7}))
            (task_root / 'manifest.json').write_bytes(encoded({'status': 'partial', 'exitCode': 7,
                'stopReason': 'nonzero-exit', 'contextFiles': {}, 'actualChanges': [],
                'declaredChangedPaths': [], 'gitBoundary': {'valid': True}}))
            with self.assertRaises(ParseError):
                modules.recheck(out)

    def test_recover_rejects_forged_worker_recovery_hash_without_materializing(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory); out, task_root, _, rel, _, active = self._prepare_recoverable_module(root)
            with patch.object(modules.worker, 'GLOBAL_LOCK_PATH', root / 'worker.lock'), \
                    patch.object(modules.worker, 'ACTIVE_PROCESS_PATH', active):
                worker_receipt = modules.worker.recover_completed(task_root)
                forged = {**worker_receipt, 'completionEvidence': {
                    **worker_receipt['completionEvidence'], 'eventsSha256': '0' * 64}}
                (task_root / 'manifest.json').write_bytes(encoded(forged))
                state_before = (out / 'state.json').read_bytes()
                with patch.object(modules.worker, 'recover_completed', return_value=forged):
                    with self.assertRaises(ParseError):
                        modules.recover(out)
            self.assertEqual((out / 'state.json').read_bytes(), state_before)
            self.assertFalse((out / rel).exists())

            with tempfile.TemporaryDirectory(dir='/private/tmp') as second:
                stage2, _, _, _, _ = self.make_stage(Path(second))
                out2 = Path(second) / 'Module'
                with patch.object(modules.worker, 'prepare', side_effect=self.fake_worker_prepare):
                    modules.prepare(stage2, 'Recipe', out2)
                summary = json.loads((out2 / 'Evidence' / 'architecture.json').read_text())
                shard_path = out2 / 'Evidence' / summary['classShards'][0]['path'].removeprefix('__Context/')
                shard_path.write_bytes(b'{}')
                with patch.object(modules.worker, 'run') as run:
                    with self.assertRaises(ParseError):
                        modules.run(out2)
                run.assert_not_called()

    def test_global_stage_must_be_accepted_and_plan_worker_payload_must_match(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory); stage, _, _, _, _ = self.make_stage(root)
            (stage / 'state.json').write_bytes(encoded({'status': 'prepared'}))
            with self.assertRaises(ParseError):
                modules._pin_stage(stage)
            (stage / 'state.json').write_bytes(encoded({'status': 'architecture_designed'}))
            (stage / 'Task' / 'workspace' / code_architecture.PLAN_PATH).write_bytes(b'{}')
            with self.assertRaises(ParseError):
                modules._pin_stage(stage)

    def test_class_shards_roundtrip_all_classes_and_split_large_module(self):
        class_a = {'id': 'ClassA', 'name': 'ClassA', 'module': 'Big', 'layer': 'Domain',
                   'kind': 'class', 'sourceUnitIds': ['unit:a'], 'fields': [],
                   'methods': [{'name': 'MethodA', 'sourceMemberIds': ['member:a']}],
                   'responsibility': 'A' * 350}
        class_b = {'id': 'ClassB', 'name': 'ClassB', 'module': 'Big', 'layer': 'Domain',
                   'kind': 'class', 'sourceUnitIds': ['unit:b'], 'fields': [],
                   'methods': [{'name': 'MethodB', 'sourceMemberIds': ['member:b']}],
                   'responsibility': 'B' * 350}
        plan = {'schemaVersion': code_architecture.SCHEMA, 'sourceManifestSha256': 'c' * 64,
                'rootNamespace': 'Demo', 'modules': [{'id': 'Big', 'responsibility': 'large feature',
                    'sourceUnitIds': ['unit:a', 'unit:b'], 'classIds': ['ClassA', 'ClassB']}],
                'classes': [class_a, class_b], 'sourceCoverage': [{'sourceUnitId': 'unit:a'},
                    {'sourceUnitId': 'unit:b'}], 'entryPoint': {'classId': 'App', 'initializationOrder': []},
                'integrationChains': [{'id': 'chain', 'classIds': ['ClassA'], 'configPaths': [], 'assetPaths': []}],
                'limitations': []}
        stage = {'plan': plan, 'pins': {'sourceManifestSha256': 'c' * 64}}
        captured = {}
        def add(name, raw):
            captured[name] = raw
        with patch.object(modules, 'ARCHITECTURE_SHARD_BYTES', 1200):
            index = modules._architecture_context(stage, add)
        self.assertGreaterEqual(len(index), 2)
        summary = json.loads(captured['architecture.json'])
        rebuilt = {key: value for key, value in summary.items() if key not in ('classCount', 'classShards')}
        rows = []
        for shard in index:
            raw = captured[shard['path'].removeprefix('__Context/')]
            self.assertLessEqual(len(raw), 1200)
            self.assertEqual(sha(raw), shard['sha256'])
            rows.extend(json.loads(raw)['classes'])
        rebuilt['classes'] = rows
        self.assertEqual(rebuilt, plan)

    def test_global_plan_larger_than_worker_single_file_limit_is_pinned(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory); stage, _, _, _, plan = self.make_stage(root)
            large_plan = {**plan, 'largeReviewedNote': 'z' * (9 * 1024 * 1024)}
            raw = encoded(large_plan)
            self.assertGreater(len(raw), 8 * 1024 * 1024)
            (stage / 'architecture.json').write_bytes(raw)
            (stage / 'Task' / 'workspace' / code_architecture.PLAN_PATH).write_bytes(raw)
            (stage / 'Task' / 'manifest.json').write_bytes(encoded({'actualChanges': [
                {'path': code_architecture.PLAN_PATH, 'afterSha256': sha(raw)}]}))
            pinned = modules._pin_stage(stage)
            self.assertEqual(pinned['pins']['architectureSha256'], sha(raw))
            self.assertEqual(pinned['plan']['largeReviewedNote'], large_plan['largeReviewedNote'])

    def test_lexical_core_gate_ignores_comments_strings_and_typed_collections(self):
        record = {'name': 'RecipeCatalog', 'kind': 'class', 'layer': 'Domain',
                  'namespace': 'Demo.Domain.Recipe', 'plannedMethods': [{'name': 'GetCount'}],
                  'plannedFields': [{'name': 'Count'}]}
        code = b'''namespace Demo.Domain.Recipe {
public sealed class RecipeCatalog {
    public int Count;
    public int GetCount() => Count;
    public System.Numerics.Vector2 Position;
    public Dictionary<string, Recipe> Recipes;
    public string Notes => "dynamic UnityEngine UnityEditor MonoBehaviour ScriptableObject Dictionary<string, object>";
    // dynamic UnityEngine UnityEditor MonoBehaviour ScriptableObject Dictionary<string, object>
}
}'''
        self.assertEqual(modules._implementation_markers(code, record), [])

    def test_unavailable_user_messages_are_not_seed_markers_but_real_todo_is(self):
        record = {'name': 'UnavailableGameBackend', 'kind': 'class', 'layer': 'Services',
                  'namespace': 'Demo.Services.Session', 'plannedMethods': [{'name': 'SubmitAsync'}],
                  'plannedFields': []}
        unavailable = b'''namespace Demo.Services.Session {
public sealed class UnavailableGameBackend {
    public string SubmitAsync() => "Remote service is not implemented; backend unavailable.";
    public string Explain() => "not implemented by this client; return an unavailable result";
}
}'''
        self.assertEqual(modules._implementation_markers(unavailable, record), [])
        actual_todo = unavailable.replace(b'    public string Explain()', b'    // TODO: preserve the documented unavailable result.\n    public string Explain()')
        self.assertIn('implementation-placeholder-remains', modules._implementation_markers(actual_todo, record))
        throwing_stub = unavailable.replace(b'"Remote service is not implemented; backend unavailable."',
            b'"not implemented"; throw new System.NotImplementedException();')
        self.assertIn('implementation-placeholder-remains', modules._implementation_markers(throwing_stub, record))
        seed = b'// ARCHITECTURE SEED ONLY. NOT IMPLEMENTED; NEVER ACCEPT AS WORKING CODE.\n'
        self.assertIn('seed-marker-remains', modules._implementation_markers(seed, record))

    def test_read_only_recheck_refreshes_classification_without_rewriting_artifacts(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory); stage, _, _, _, _ = self.make_stage(root); out = root / 'Module'
            with patch.object(modules.worker, 'prepare', side_effect=self.fake_worker_prepare):
                modules.prepare(stage, 'Recipe', out)

            def fake_run(task_root, *, session_id=None):
                task_root = Path(task_root)
                rel = 'Assets/Game/Domain/Recipe/RecipeCatalog.cs'
                path = task_root / 'workspace' / rel
                body = b'''namespace Demo.Domain.Recipe {
public sealed class RecipeCatalog {
    public int Count;
    public int GetCount() => Count;
    public string Availability => "not implemented for this local adapter; unavailable";
}
}'''
                path.write_bytes(body)
                (task_root / 'request.json').write_bytes(encoded({'state': 'completed'}))
                return {'status': 'complete', 'actualChanges': [{'path': rel, 'afterSha256': sha(body)}],
                    'declaredChangedPaths': [rel], 'gitBoundary': {'valid': True}, 'unresolved': []}

            with patch.object(modules.worker, 'run', side_effect=fake_run):
                modules.run(out)
            task_root = out / 'Task'
            task_request = json.loads((task_root / 'request.json').read_text())
            module_request = json.loads((out / 'request.json').read_text())
            task_context = {'__Context/' + name: {'sourcePath': name, 'sha256': pin['sha256'], 'bytes': pin['bytes']}
                            for name, pin in module_request['contextFiles'].items()}
            task_request.update(state='finalized', exitCode=0, contextFiles=task_context)
            (task_root / 'request.json').write_bytes(encoded(task_request))
            (task_root / 'process.json').write_bytes(encoded({'state': 'exited', 'returnCode': 0}))
            rel = 'Assets/Game/Domain/Recipe/RecipeCatalog.cs'
            body = (task_root / 'workspace' / rel).read_bytes()
            revision = {'status': 'complete', 'exitCode': 0, 'stopReason': None,
                'unexpectedPaths': [], 'workspaceIntegrityErrors': [], 'sourceVerificationErrors': [],
                'gitBoundary': {'valid': True}, 'contextFiles': task_context,
                'actualChanges': [{'path': rel, 'afterSha256': sha(body), 'afterBytes': len(body)}],
                'declaredChangedPaths': [rel]}
            (task_root / 'manifest.json').write_bytes(encoded(revision))

            protected = [out / modules.MANIFEST, out / modules.MANIFEST_SHA, out / 'state.json',
                         out / rel, task_root / 'request.json', task_root / 'manifest.json']
            before = [sha(path.read_bytes()) for path in protected]
            result = modules.recheck(out)
            after = [sha(path.read_bytes()) for path in protected]
            self.assertEqual(before, after)
            self.assertEqual(result['status'], 'rechecked')
            self.assertEqual(result['classification'], 'generated_unreviewed')
            self.assertEqual(result['files'][0]['classification'], 'generated_unreviewed')
            self.assertEqual(result['files'][0]['completenessDiagnostics'], [])
            self.assertEqual(result['semanticValidation'], 'not_performed')
            self.assertFalse(result['manifestRewritten'])

    def test_read_only_recheck_refuses_nonfinalized_task(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory); stage, _, _, _, _ = self.make_stage(root); out = root / 'Module'
            with patch.object(modules.worker, 'prepare', side_effect=self.fake_worker_prepare):
                modules.prepare(stage, 'Recipe', out)
            manifest_before = sha((out / modules.MANIFEST).read_bytes())
            with self.assertRaises(ParseError):
                modules.recheck(out)
            self.assertEqual(sha((out / modules.MANIFEST).read_bytes()), manifest_before)

    def test_lexical_core_gate_flags_engine_dynamic_untyped_and_namespace_gaps(self):
        record = {'name': 'RecipeCatalog', 'kind': 'class', 'layer': 'Gameplay',
                  'namespace': 'Demo.Gameplay.Recipe', 'plannedMethods': [{'name': 'GetCount'}],
                  'plannedFields': [{'name': 'Count'}]}
        code = b'''namespace Demo.Gameplay.Recipe {
public sealed class RecipeCatalog : UnityEngine.MonoBehaviour {
    public dynamic Value;
    public Dictionary<string, object> Data;
    // GetCount() and Count in comments do not satisfy the contract.
}
}'''
        markers = modules._implementation_markers(code, record)
        self.assertIn('core-engine-reference:UnityEngine', markers)
        self.assertIn('core-engine-reference:MonoBehaviour', markers)
        self.assertIn('core-dynamic-keyword', markers)
        self.assertIn('core-untyped-string-object-dictionary', markers)
        self.assertIn('planned-method-declaration-missing:GetCount', markers)
        self.assertIn('planned-field-declaration-missing:Count', markers)
        file_scoped = code.replace(b'namespace Demo.Gameplay.Recipe {', b'namespace Demo.Gameplay.Recipe;')
        self.assertIn('file-scoped-namespace-not-allowed', modules._implementation_markers(file_scoped, record))
        wrong_namespace = code.replace(b'Demo.Gameplay.Recipe', b'Demo.Domain.Recipe')
        self.assertIn('planned-type-or-namespace-declaration-missing', modules._implementation_markers(wrong_namespace, record))
        call_sites_only = b'''namespace Demo.Gameplay.Recipe {
public sealed class RecipeCatalog {
    public int Invoke() { return GetCount(); }
    public string Show() => Count.ToString();
}
}'''
        call_markers = modules._implementation_markers(call_sites_only, record)
        self.assertIn('planned-method-declaration-missing:GetCount', call_markers)
        self.assertIn('planned-field-declaration-missing:Count', call_markers)

    def test_run_marks_forbidden_core_constructs_incomplete(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory); stage, _, _, _, _ = self.make_stage(root); out = root / 'Module'
            with patch.object(modules.worker, 'prepare', side_effect=self.fake_worker_prepare):
                modules.prepare(stage, 'Recipe', out)
            def fake_run(task_root, *, session_id=None):
                task_root = Path(task_root)
                path = task_root / 'workspace' / 'Assets/Game/Domain/Recipe/RecipeCatalog.cs'
                body = b'namespace Demo.Domain.Recipe { public sealed class RecipeCatalog { public int Count; public dynamic GetCount() => 7; } }\n'
                path.write_bytes(body)
                (task_root / 'request.json').write_bytes(encoded({'state': 'completed'}))
                return {'status': 'complete', 'actualChanges': [{'path': 'Assets/Game/Domain/Recipe/RecipeCatalog.cs',
                    'afterSha256': sha(body)}], 'declaredChangedPaths': ['Assets/Game/Domain/Recipe/RecipeCatalog.cs'],
                    'gitBoundary': {'valid': True}, 'unresolved': []}
            with patch.object(modules.worker, 'run', side_effect=fake_run):
                result = modules.run(out)
            manifest = json.loads((out / modules.MANIFEST).read_text())
            self.assertEqual(result['status'], 'partial_unimplemented_seed')
            self.assertEqual(manifest['classes'][0]['status'], 'incomplete_contract')
            self.assertIn('core-dynamic-keyword', manifest['classes'][0]['completenessDiagnostics'])
    def test_unimplemented_marker_survives_as_partial_not_accepted(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory); stage, _, _, _, _ = self.make_stage(root); out = root / 'Module'
            with patch.object(modules.worker, 'prepare', side_effect=self.fake_worker_prepare):
                modules.prepare(stage, 'Recipe', out)
            def fake_run(task_root, *, session_id=None):
                task_root = Path(task_root)
                path = task_root / 'workspace' / 'Assets/Game/Domain/Recipe/RecipeCatalog.cs'
                pending = b'// NOT IMPLEMENTED\n'
                path.write_bytes(pending)
                (task_root / 'request.json').write_bytes(encoded({'state': 'completed'}))
                return {'status': 'complete', 'actualChanges': [{'path': 'Assets/Game/Domain/Recipe/RecipeCatalog.cs',
                    'afterSha256': sha(pending)}], 'declaredChangedPaths': ['Assets/Game/Domain/Recipe/RecipeCatalog.cs'],
                    'gitBoundary': {'valid': True}, 'unresolved': []}
            with patch.object(modules.worker, 'run', side_effect=fake_run):
                result = modules.run(out)
            self.assertEqual(result['status'], 'partial_unimplemented_seed')

    def test_worker_cannot_claim_changes_outside_module_paths(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root = Path(directory); stage, _, _, _, _ = self.make_stage(root); out = root / 'Module'
            with patch.object(modules.worker, 'prepare', side_effect=self.fake_worker_prepare):
                modules.prepare(stage, 'Recipe', out)
            def fake_run(task_root, *, session_id=None):
                task_root = Path(task_root)
                selected = task_root / 'workspace' / 'Assets/Game/Domain/Recipe/RecipeCatalog.cs'
                generated = b'namespace Demo.Domain.Recipe { public sealed class RecipeCatalog { public int Count; public int GetCount() => 7; } }\n'
                selected.write_bytes(generated)
                (task_root / 'request.json').write_bytes(encoded({'state': 'completed'}))
                return {'status': 'complete', 'actualChanges': [
                    {'path': 'Assets/Game/Domain/Recipe/RecipeCatalog.cs', 'afterSha256': sha(generated)},
                    {'path': 'Assets/Game/Domain/Recipe/Unexpected.cs', 'afterSha256': sha(b'')},
                ], 'declaredChangedPaths': ['Assets/Game/Domain/Recipe/RecipeCatalog.cs', 'Assets/Game/Domain/Recipe/Unexpected.cs'],
                    'gitBoundary': {'valid': True}, 'unresolved': []}
            with patch.object(modules.worker, 'run', side_effect=fake_run):
                with self.assertRaises(ParseError):
                    modules.run(out)


if __name__ == '__main__':
    unittest.main()
