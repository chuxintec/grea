import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from monkey.code_regeneration import plan_modules, select_reuse, _fingerprints, _validate_requests, _candidate_inventory
from monkey.io import sha
from monkey.sources.compiled import ParseError


GENERATOR = 'a' * 64


def fp(label):
    return hashlib.sha256(label.encode()).hexdigest()


def module(mid, src, deps, paths):
    return dict(id=mid, sourceFingerprint=fp(src), dependencies=deps, targetPaths=paths)


def create_candidate(root, modules, generator=GENERATOR, bodies=None):
    bodies = bodies or {}
    specs, order, _ = _validate_requests(modules, generator)
    fingerprints = _fingerprints(specs, order, generator)
    file_rows = []
    records = []
    for item in modules:
        mid = item['id']
        owned = []
        for path in item['targetPaths']:
            body = bodies.get(path, ('// ' + mid + '\n').encode())
            dest = root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body)
            row = dict(path=path, sha256=sha(body), bytes=len(body), owner=mid)
            file_rows.append(row)
            owned.append(path)
        records.append(dict(id=mid, sourceFingerprint=item['sourceFingerprint'],
                            dependencyFingerprint=fingerprints[mid]['dependencyFingerprint'],
                            cacheKey=fingerprints[mid]['cacheKey'], dependencies=sorted(set(x for x in item['dependencies'] if x != mid)),
                            targetPaths=sorted(item['targetPaths']), files=sorted(owned),
                            sourceMethodMappings=[dict(sourceMethodId='old:1', targetMethodId='NewType.Call')]))
    manifest = dict(schemaVersion=1, scopeMode='code-modules-only', files=file_rows,
                    codeModules=records, codeGeneratorSignature=generator)
    raw = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    (root / 'manifest.json').write_bytes(raw)
    return sha(raw)


class CodeRegenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.root = Path(self.tmp.name) / 'candidate'
        self.root.mkdir()
        self.modules = [module('callee', 'callee-v1', [], ['Assets/Game/Logic/Rules.cs']),
                        module('caller', 'caller-v1', ['callee'], ['Assets/Game/Logic/Orders.cs']),
                        module('unrelated', 'other-v1', [], ['Assets/Game/UI/Hud.cs'])]
        self.manifest_sha = create_candidate(self.root, self.modules)

    def tearDown(self):
        self.tmp.cleanup()

    def choose(self, modules=None, generator=GENERATOR, expected=None):
        return select_reuse(self.root, expected or self.manifest_sha,
                            modules if modules is not None else self.modules, generator)

    def test_identical_inputs_reuse_files_and_preserve_method_map(self):
        result = self.choose()
        self.assertTrue(all(item['action'] == 'reuse' for item in result['moduleRecords']))
        self.assertEqual(result['reusableFiles']['Assets/Game/Logic/Rules.cs'], b'// callee\n')
        caller = next(row for row in result['moduleRecords'] if row['id'] == 'caller')
        self.assertEqual(caller['sourceMethodMappings'][0]['sourceMethodId'], 'old:1')

    def test_whole_draft_budget_requires_exact_candidate_kind_and_retains_guard(self):
        manifest=json.loads((self.root/'manifest.json').read_bytes())
        manifest['scopeMode']='whole-input'
        manifest['candidateKind']='unrelated-candidate'
        with self.assertRaisesRegex(ParseError,'MANIFEST'):
            _candidate_inventory(self.root,manifest)
        manifest['candidateKind']='full-source-csharp-drafts'
        # Exercise declared budget accounting without allocating hundreds of MiB.
        manifest['files'][0]['bytes']=300*1024**2
        _candidate_inventory(self.root,manifest)
        manifest['scopeMode']='code-modules-only'
        with self.assertRaisesRegex(ParseError,'TOTAL_BUDGET'):
            _candidate_inventory(self.root,manifest)
        manifest['scopeMode']='whole-input'
        manifest['files']=manifest['files'][:1]*28
        for i,row in enumerate(manifest['files']):
            manifest['files'][i]=dict(row,path='SourceRecovery/CSharp/File'+str(i)+'.cs')
        with self.assertRaisesRegex(ParseError,'TOTAL_BUDGET'):
            _candidate_inventory(self.root,manifest)

    def test_whole_draft_reuse_keeps_dirty_file_protection(self):
        manifest=json.loads((self.root/'manifest.json').read_bytes())
        manifest.update(scopeMode='whole-input',candidateKind='full-source-csharp-drafts')
        raw=json.dumps(manifest).encode();(self.root/'manifest.json').write_bytes(raw)
        self.assertTrue(all(r['action']=='reuse'for r in self.choose(expected=sha(raw))['moduleRecords']))
        path=self.root/self.modules[0]['targetPaths'][0];path.write_text('// human edit')
        result=self.choose(expected=sha(raw))
        self.assertEqual(result['actions']['callee']['action'],'blocked')
        self.assertEqual(path.read_text(),'// human edit')

    def test_changed_callee_regenerates_caller_but_not_unrelated_module(self):
        changed = [module('callee', 'callee-v2', [], ['Assets/Game/Logic/Rules.cs']),
                   self.modules[1], self.modules[2]]
        result = self.choose(changed)
        actions = {mid: record['action'] for mid, record in result['actions'].items()}
        self.assertEqual(actions, {'callee': 'regenerate', 'caller': 'regenerate', 'unrelated': 'reuse'})
        reasons = {mid: record['reason'] for mid, record in result['actions'].items()}
        self.assertEqual(reasons['caller'], 'dependency_fingerprint_changed')

    def test_generator_change_invalidates_every_module(self):
        result = self.choose(generator=fp('generator-v2'))
        self.assertTrue(all(row['action'] == 'regenerate' for row in result['moduleRecords']))
        self.assertEqual(result['actions']['callee']['reason'], 'generator_signature_changed')

    def test_source_and_target_path_drift_are_independent(self):
        changed = [self.modules[0], self.modules[1],
                   module('unrelated', 'other-v1', [], ['Assets/Game/UI/Hud2.cs'])]
        changed[0] = module('callee', 'callee-v2', [], ['Assets/Game/Logic/Rules.cs'])
        result = self.choose(changed)
        actions = {mid: record['action'] for mid, record in result['actions'].items()}
        self.assertEqual(actions, {'callee': 'regenerate', 'caller': 'regenerate', 'unrelated': 'regenerate'})
        self.assertEqual(result['actions']['unrelated']['reason'], 'target_paths_changed')

    def test_changed_or_manual_candidate_file_blocks_owner(self):
        path = self.root / 'Assets/Game/Logic/Rules.cs'
        path.write_text('// human edit\n')
        result = self.choose()
        self.assertEqual(result['actions']['callee']['action'], 'blocked')
        self.assertIn('hash_changed', result['actions']['callee']['reason'])
        # A declared manual owner is protected even if bytes match the manifest.
        manifest_path = self.root / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        row = next(x for x in manifest['files'] if x['path'].endswith('Rules.cs'))
        body = path.read_bytes()
        row.update(sha256=sha(body), bytes=len(body), owner='manual')
        raw = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
        manifest_path.write_bytes(raw)
        result = self.choose(expected=sha(raw))
        self.assertEqual(result['actions']['callee']['action'], 'blocked')
        self.assertIn('manual_or_wrong_owner', result['actions']['callee']['reason'])

    def test_inventory_mismatch_and_missing_or_cyclic_dependency_block(self):
        (self.root / 'stray.txt').write_text('unknown')
        result = self.choose()
        self.assertTrue(all(row['action'] == 'blocked' for row in result['moduleRecords']))
        missing = [module('caller', 'x', ['ghost'], ['Assets/X.cs'])]
        self.assertEqual(self.choose(missing)['actions']['caller']['reason'], 'missing_dependency:ghost')
        cycle = [module('a', 'a', ['b'], ['Assets/A.cs']), module('b', 'b', ['a'], ['Assets/B.cs'])]
        self.assertTrue(all(row['reason'] == 'dependency_cycle' for row in self.choose(cycle)['moduleRecords']))

    def test_duplicate_ids_collisions_unicode_and_path_traversal_rejected(self):
        cases = [
            [module('x', 'x', [], ['Assets/A.cs']), module('x', 'y', [], ['Assets/B.cs'])],
            [module('x', 'x', [], ['Assets/A.cs']), module('y', 'y', [], ['assets/a.CS'])],
            [module('x', 'x', [], ['Assets/../Escape.cs'])],
            [module('x', 'x', [], ['Assets/Cafe\u0301.cs'])],
        ]
        for request in cases:
            with self.subTest(request=request), self.assertRaises(ParseError):
                self.choose(request)

    def test_candidate_manifest_path_attack_and_read_budget_rejected(self):
        manifest_path = self.root / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files'][0]['path'] = '../../outside.cs'
        raw = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
        manifest_path.write_bytes(raw)
        with self.assertRaises(ParseError):
            self.choose(expected=sha(raw))
        self.assertEqual((self.root / 'manifest.json').read_bytes(), raw)

    def test_candidate_declared_total_read_budget_rejected(self):
        manifest_path = self.root / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files'][0]['bytes'] = 256 * 1024 * 1024
        raw = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
        manifest_path.write_bytes(raw)
        with self.assertRaises(ParseError):
            self.choose(expected=sha(raw))

    def test_fresh_plan_and_graph_diagnostics_leave_unrelated_modules_ready(self):
        graph = [module('cycle_a', 'a', ['cycle_b'], ['Assets/A.cs']),
                 module('cycle_b', 'b', ['cycle_a'], ['Assets/B.cs']),
                 module('downstream', 'd', ['cycle_a'], ['Assets/D.cs']),
                 module('independent', 'i', [], ['Assets/I.cs'])]
        result = plan_modules(graph, GENERATOR)
        self.assertEqual(result['actions']['cycle_a']['action'], 'blocked')
        self.assertEqual(result['actions']['cycle_b']['action'], 'blocked')
        self.assertEqual(result['actions']['downstream']['action'], 'blocked')
        self.assertEqual(result['actions']['independent']['action'], 'regenerate')
        self.assertEqual([d['code'] for d in result['diagnostics']], ['dependency_cycle', 'dependency_cycle'])
        self.assertNotIn('candidateManifestSha256', result)
        self.assertNotIn('reusableFiles', result)

    def test_iterative_module_graph_handles_depth_above_python_recursion_limit(self):
        count = 1800
        graph = [module(f'm{i:04d}', f'source-{i}', [f'm{i - 1:04d}'] if i else [],
                        [f'Assets/M{i:04d}.cs']) for i in range(count)]
        result = plan_modules(graph, GENERATOR)
        self.assertEqual(len(result['moduleRecords']), count)
        self.assertEqual(result['status'], 'planned')
        self.assertTrue(all(item['action'] == 'regenerate' for item in result['moduleRecords']))

        candidate = Path(self.tmp.name) / 'deep-candidate'
        candidate.mkdir()
        manifest_sha = create_candidate(candidate, graph)
        selected = select_reuse(candidate, manifest_sha, graph, GENERATOR)
        self.assertEqual(selected['status'], 'planned')
        self.assertTrue(all(row['action'] == 'reuse' for row in selected['moduleRecords']))

    def test_declared_graph_edge_limit_fails_with_bounded_diagnostic(self):
        graph = [module('large', 's', ['ghost'] * 200_001, ['Assets/Large.cs']),
                 module('independent', 'i', [], ['Assets/Independent.cs'])]
        with self.assertRaises(ParseError) as caught:
            plan_modules(graph, GENERATOR)
        self.assertEqual(caught.exception.code, 'CODE_REGENERATION_GRAPH_BUDGET')


if __name__ == '__main__':
    unittest.main()
