import copy
import unittest

from monkey.code_architecture_contract import validate_architecture
from monkey.sources.compiled import ParseError


SHA = 'a' * 64


def fixture():
    classes = [
        dict(id='domain-entity', name='PlayerState', layer='Domain', module='Model', kind='class',
             responsibility='Owns player state', stateOwnership='PlayerState owns health', lifecycle='Created from configuration',
             dependsOn=[], sourceUnitIds=['unit-a'], fields=[dict(name='hp', type='int', role='current health')],
             methods=[dict(name='Damage', returnType='int', parameters=[dict(name='amount', type='int')], sourceMemberIds=['member-a'])]),
        dict(id='game-loop', name='CombatLoop', layer='Gameplay', module='Combat', kind='class',
             responsibility='Applies combat rules', stateOwnership='Mutates PlayerState through methods', lifecycle='Called by presentation events',
             dependsOn=['Domain'], sourceUnitIds=['unit-b'], fields=[],
             methods=[dict(name='ApplyDamage', returnType='int', parameters=[dict(name='amount', type='int')], sourceMemberIds=[])]),
        dict(id='view', name='CombatPanel', layer='Presentation', module='CombatUI', kind='class',
             responsibility='Presents combat state', stateOwnership='No authoritative state', lifecycle='Bound by bootstrap',
             dependsOn=['Domain', 'Gameplay'], sourceUnitIds=['unit-b'], fields=[], methods=[]),
        dict(id='startup', name='GameStartup', layer='Bootstrap', module='Entry', kind='class',
             responsibility='Connects application services', stateOwnership='Owns initialization only', lifecycle='One startup per scene',
             dependsOn=['Domain', 'Gameplay', 'Presentation'], sourceUnitIds=[], fields=[], methods=[]),
    ]
    plan = dict(
        schemaVersion='monkey-native-code-architecture/1', sourceManifestSha256=SHA,
        rootNamespace='Game',
        modules=[
            dict(id='Model', responsibility='Domain state', sourceUnitIds=['unit-a'], classIds=['domain-entity']),
            dict(id='Combat', responsibility='Gameplay rules', sourceUnitIds=['unit-b'], classIds=['game-loop']),
            dict(id='CombatUI', responsibility='Views', sourceUnitIds=['unit-b'], classIds=['view']),
            dict(id='Entry', responsibility='Startup composition', sourceUnitIds=[], classIds=['startup']),
        ],
        classes=classes,
        sourceCoverage=[
            dict(sourceUnitId='unit-a', disposition='planned', classIds=['domain-entity'], reason='Represented by state model'),
            dict(sourceUnitId='unit-b', disposition='planned', classIds=['game-loop', 'view'], reason='Rules and view separated'),
        ],
        entryPoint=dict(classId='startup', initializationOrder=['startup', 'game-loop', 'view']),
        integrationChains=[dict(id='combat-entry', classIds=['startup', 'game-loop', 'domain-entity', 'view'],
                                configPaths=['Assets/Game/Content/Config/combat.json'], assetPaths=['Assets/Game/Content/UI/combat.png'],
                                behavior='Load combat config, connect state and render the combat panel', sourceUnitIds=['unit-a', 'unit-b'])],
        limitations=['Architecture only; no code generation or compile claim'],
    )
    for record in classes:record['typeDependencies']=[]
    catalog = dict(sourceManifestSha256=SHA, sourceUnits=[dict(id='unit-a',members=[dict(id='member-a')]), dict(id='unit-b',members=[])])
    return plan, catalog


class CodeArchitectureContractTests(unittest.TestCase):
    def test_first_chain_keeps_real_json_requirement_while_optional_chain_can_use_prefab_tuning(self):
        from copy import deepcopy
        plan,catalog=fixture();extra=deepcopy(plan['integrationChains'][0]);extra.update(id='prefab-contact',configPaths=[])
        plan['integrationChains'].append(extra)
        self.assertTrue(validate_architecture(plan,catalog)['valid'])
        plan['integrationChains'][0]['configPaths']=[]
        with self.assertRaisesRegex(ParseError,'first core integration chain'):validate_architecture(plan,catalog)

    def test_field_member_identity_and_analysis_inputs_cannot_be_invented(self):
        plan,catalog=fixture();field=plan['classes'][0]['fields'][0];field['sourceMemberIds']=['member-a']
        self.assertTrue(validate_architecture(plan,catalog)['valid'])
        field['sourceMemberIds']=['fabricated-member']
        with self.assertRaisesRegex(ParseError,'Field source IDs'):validate_architecture(plan,catalog)
        field['sourceMemberIds']=[];plan['classes'][0]['sourceInputUnitIds']=['fabricated-unit']
        with self.assertRaisesRegex(ParseError,'Unknown analysis'):validate_architecture(plan,catalog)

    def test_typed_record_plan_remains_subject_to_core_dependency_rules(self):
        plan,catalog=fixture();plan['classes'][0]['kind']='record'
        self.assertTrue(validate_architecture(plan,catalog)['valid'])
        plan['classes'][0]['baseType']=None
        self.assertTrue(validate_architecture(plan,catalog)['valid'])
        plan['classes'][0]['fields'][0]['type']='UnityEngine.Vector2'
        with self.assertRaisesRegex(ParseError,'Core Domain/Gameplay'):validate_architecture(plan,catalog)

    def test_actual_type_dependencies_and_source_members_cannot_be_invented(self):
        plan,catalog=fixture();plan['classes'][1]['typeDependencies']=['domain-entity']
        self.assertTrue(validate_architecture(plan,catalog)['valid'])
        plan['classes'][1]['typeDependencies']=['missing-class']
        with self.assertRaisesRegex(ParseError,'Unknown target class'):validate_architecture(plan,catalog)
        plan,catalog=fixture();plan['classes'][0]['typeDependencies']=['view']
        with self.assertRaisesRegex(ParseError,'crosses'):validate_architecture(plan,catalog)
        plan,catalog=fixture();plan['classes'][1]['methods'][0]['sourceMemberIds']=['member-a']
        with self.assertRaisesRegex(ParseError,'this class source units'):validate_architecture(plan,catalog)
        plan,catalog=fixture();plan['classes'][0]['sourceUnitIds']=['unit-b']
        with self.assertRaisesRegex(ParseError,'module inputs'):validate_architecture(plan,catalog)

    def test_pure_numerics_types_are_not_misclassified_as_unity_dependencies(self):
        plan,catalog=fixture();plan['classes'][0]['fields'][0]['type']='System.Numerics.Vector2'
        self.assertTrue(validate_architecture(plan,catalog)['valid'])

    def test_valid_plan_returns_deterministic_paths_and_fixed_assembly_edges(self):
        plan, catalog = fixture()
        result = validate_architecture(plan, catalog)
        self.assertTrue(result['valid'])
        self.assertEqual(result['counts']['classes'], 4)
        self.assertEqual(result['classPaths']['domain-entity'], 'Assets/Game/Domain/Model/PlayerState.cs')
        self.assertEqual(result['assemblyReferences']['Presentation'], ['Domain', 'Gameplay'])
        self.assertEqual(result['assemblyReferences']['Domain'], [])

    def test_rejects_layer_violation_and_core_dynamic_type(self):
        plan, catalog = fixture()
        plan['classes'][0]['dependsOn'] = ['Presentation']
        with self.assertRaisesRegex(ParseError, 'CODE_ARCHITECTURE_CONTRACT'):
            validate_architecture(plan, catalog)
        plan, catalog = fixture()
        plan['classes'][0]['fields'][0]['type'] = 'dynamic'
        with self.assertRaisesRegex(ParseError, 'Core Domain/Gameplay'):
            validate_architecture(plan, catalog)
        plan, catalog = fixture()
        plan['classes'][0]['baseType'] = 'UnityEngine.MonoBehaviour'
        with self.assertRaisesRegex(ParseError, 'Core Domain/Gameplay'):
            validate_architecture(plan, catalog)

    def test_rejects_mismatched_manifest_hash_and_duplicate_class(self):
        plan, catalog = fixture()
        catalog['sourceManifestSha256'] = 'b' * 64
        with self.assertRaisesRegex(ParseError, 'does not match the catalog'):
            validate_architecture(plan, catalog)
        plan, catalog = fixture()
        plan['classes'].append(copy.deepcopy(plan['classes'][0]))
        with self.assertRaisesRegex(ParseError, 'Duplicate id'):
            validate_architecture(plan, catalog)

    def test_requires_complete_unique_source_coverage(self):
        plan, catalog = fixture()
        plan['sourceCoverage'].pop()
        with self.assertRaisesRegex(ParseError, 'missing'):
            validate_architecture(plan, catalog)
        plan, catalog = fixture()
        plan['sourceCoverage'].append(copy.deepcopy(plan['sourceCoverage'][0]))
        with self.assertRaisesRegex(ParseError, 'Duplicate coverage row'):
            validate_architecture(plan, catalog)

    def test_rejects_unsafe_integration_paths_and_missing_layer_or_config(self):
        plan, catalog = fixture()
        plan['integrationChains'][0]['configPaths'] = ['../../secrets/config.json']
        with self.assertRaisesRegex(ParseError, 'must not traverse'):
            validate_architecture(plan, catalog)
        plan, catalog = fixture()
        plan['integrationChains'][0]['classIds'].remove('view')
        with self.assertRaisesRegex(ParseError, 'must include classIds'):
            validate_architecture(plan, catalog)
        plan, catalog = fixture()
        plan['integrationChains'][0]['configPaths'] = ['Assets/Game/Content/Config']
        with self.assertRaisesRegex(ParseError, 'JSON file'):
            validate_architecture(plan, catalog)

    def test_rejects_invalid_bootstrap_entry_or_planned_row_without_class(self):
        plan, catalog = fixture()
        plan['entryPoint']['classId'] = 'game-loop'
        with self.assertRaisesRegex(ParseError, 'Bootstrap class'):
            validate_architecture(plan, catalog)
        plan, catalog = fixture()
        plan['sourceCoverage'][0]['classIds'] = []
        with self.assertRaisesRegex(ParseError, 'planned source units'):
            validate_architecture(plan, catalog)


if __name__ == '__main__':
    unittest.main()
