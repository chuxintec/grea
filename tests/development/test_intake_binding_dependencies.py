"""Actual graph boundary guards; no Editor or fake target states."""
import unittest
from grea.development.errors import BeaverError
from grea.development.intake_binding_dependencies import closure, ordered_groups, script_root, runtime_field

class DependencyGroupsTests(unittest.TestCase):
    def test_support_without_native_reference_is_included_transitively(self):
        graph={'prefab_script':{'helper'},'helper':{'contract'},'contract':set(),'unrelated':set()}
        self.assertEqual(closure({'prefab_script'},graph),{'prefab_script','helper','contract'})

    def test_dependency_order_is_preserved_and_batch_limit_applies(self):
        graph={f'Code{i:02}':({f'Code{i-1:02}'} if i else set()) for i in range(35)}
        batches,blocked=ordered_groups(graph)
        self.assertFalse(blocked)
        self.assertEqual([len(b) for b in batches],[16,16,3])
        flat=[n for batch in batches for n in batch]
        self.assertEqual(flat,[f'Code{i:02}' for i in range(35)])

    def test_unknown_support_blocks_its_dependants_but_not_independent_code(self):
        batches,blocked=ordered_groups({'dependent':{'interface_not_declarable'},'downstream':{'dependent'},'carrier':set()})
        self.assertEqual(batches,[['carrier']])
        self.assertEqual({p for r in blocked for p in r['paths']},{'dependent','downstream'})

    def test_large_cycle_is_never_split_to_bypass_limit(self):
        graph={str(i):{str((i+1)%17)} for i in range(17)}
        batches,blocked=ordered_groups(graph)
        self.assertFalse(batches)
        self.assertEqual(blocked[0]['reason'],'cycle_exceeds_batch_limit')

class ScriptMappingTests(unittest.TestCase):
    def test_prefix_is_taken_from_actual_mapping(self):
        self.assertEqual(script_root([dict(source='Assets/Game/Icon.png',target='Assets/Imported/Game/Icon.png')]),'Assets/Imported')
    def test_nonuniform_mapping_needs_explicit_root(self):
        with self.assertRaises(BeaverError):script_root([dict(source='Assets/Game/Icon.png',target='Assets/Flat/Icon.png')])
        self.assertEqual(script_root([], 'Assets/Code'),'Assets/Code')

class RuntimeFieldIdentityTests(unittest.TestCase):
    def test_facade_scalar_uses_actual_core_library_typedef(self):
        self.assertEqual(runtime_field(dict(name='count',type='System.Int32',assembly='netstandard'),dict(assembly='mscorlib',types={'System.Int32'}))['assembly'],'mscorlib')
    def test_unproven_facade_and_generic_do_not_create_native_expectations(self):
        for name in ('System.String','System.Collections.Generic.List`1[[System.String, netstandard, Version=2.1.0.0]]'):
            with self.assertRaises(BeaverError):runtime_field(dict(name='field',type=name,assembly='netstandard'),None)
