import hashlib
import json
import unittest

import grea.recovery.code_configuration as configuration
from grea.recovery.extensions.legacy_foodstreet import configuration as legacy_configuration
from grea.recovery.sources.compiled import ParseError


def row(row_id, dish_id, ingredients, *, cookware=-1, duration=12, cook_type=1):
    return dict(id=row_id, elementOrderId=cookware,
                needElements={str(key): value for key, value in ingredients},
                elementIdWeight={str(dish_id): 0}, duration=duration,
                cookType=cook_type, addElementStorage=1, speedUpCost=1)


class ElementMultiOrderPoolTests(unittest.TestCase):
    def setUp(self):
        self.original_table_sha = legacy_configuration.TABLE_SHA256
        self.original_source_sha = legacy_configuration.SOURCE_SHA256
        self.original_spans = legacy_configuration.SOURCE_SPANS
        source = bytearray(b'fixture-source:')
        spans = {}
        for name in legacy_configuration.SOURCE_SPANS:
            fragment = ('static-fixture-span:' + name).encode()
            start = len(source)
            source.extend(fragment)
            spans[name] = dict(byteOffset=start, byteLength=len(fragment),
                               sha256=hashlib.sha256(fragment).hexdigest())
        self.source = bytes(source)
        legacy_configuration.SOURCE_SPANS = spans
        self.document = {
            # The keys are deliberately non-numeric insertion order. The source
            # `for...in` decoder visits canonical integer keys in numeric order.
            '10': row(10, 900, [(4, 1), (901, 2), (7, 1)], cook_type=0),
            '2': row(2, 901, [(4, 3), (5, 1)]),
        }
        self.table = json.dumps(self.document, separators=(',', ':')).encode()
        legacy_configuration.TABLE_SHA256 = hashlib.sha256(self.table).hexdigest()
        legacy_configuration.SOURCE_SHA256 = hashlib.sha256(self.source).hexdigest()

    def tearDown(self):
        legacy_configuration.TABLE_SHA256 = self.original_table_sha
        legacy_configuration.SOURCE_SHA256 = self.original_source_sha
        legacy_configuration.SOURCE_SPANS = self.original_spans

    def map(self, document=None):
        table = self.table if document is None else json.dumps(document, separators=(',', ':')).encode()
        if document is not None:
            legacy_configuration.TABLE_SHA256 = hashlib.sha256(table).hexdigest()
        return configuration.map_payload(table, self.source,
                    expected_table_sha256=legacy_configuration.TABLE_SHA256,
                    expected_source_sha256=legacy_configuration.SOURCE_SHA256, root_dish_id=900)

    def test_maps_exact_recipe_fields_and_recursive_first_seen_leaf_order(self):
        result = self.map()
        self.assertEqual(result['status'], 'validated-finite-source-subset')
        self.assertEqual(result['table']['rowCount'], 2)
        self.assertEqual([r['sourceRowId'] for r in result['recipes']], [2, 10])
        root = next(r for r in result['recipes'] if r['sourceRowId'] == 10)
        self.assertEqual(root['recipe'], dict(id=10, dish=900, ingredients=[[4, 1], [7, 1], [901, 2]]))
        # Kp's source expression explicitly normalizes non-positive cookType to 1.
        self.assertEqual(root['cookType'], 1)
        self.assertEqual(result['representative'], dict(
            rootDishId=900, rootSourceRowId=10, expandedRecipeDishIds=[900, 901],
            leafOccurrences=[4, 7, 4, 5], flattenedLeaves=[4, 7, 5]))
        self.assertFalse(result['source']['sourceExecuted'])

    def test_duplicate_dish_and_numeric_key_collisions_are_rejected(self):
        duplicate_dish = {'1': row(1, 900, [(4, 1)]), '2': row(2, 900, [(5, 1)])}
        with self.assertRaises(ParseError) as caught:
            self.map(duplicate_dish)
        self.assertEqual(caught.exception.code, 'CODE_CONFIG_DUPLICATE_DISH')
        collided_keys = row(1, 900, [(4, 1), (4, 2)])
        collided_keys['needElements'] = {'4': 1, '04': 2}
        with self.assertRaises(ParseError) as caught:
            self.map({'1': collided_keys})
        self.assertEqual(caught.exception.code, 'CODE_CONFIG_DUPLICATE_INGREDIENT')
        duplicate_prefix = {'1': row(1, 900, [(4, 1)])}
        duplicate_prefix['1']['elementIdWeight'] = {'900': 1, '900_2': 2}
        with self.assertRaises(ParseError) as caught:
            self.map(duplicate_prefix)
        self.assertEqual(caught.exception.code, 'CODE_CONFIG_DUPLICATE_DISH')

    def test_cycles_and_unsupported_shapes_are_rejected(self):
        cycle = {'1': row(1, 900, [(901, 1)]), '2': row(2, 901, [(900, 1)])}
        with self.assertRaises(ParseError) as caught:
            self.map(cycle)
        self.assertEqual(caught.exception.code, 'CODE_CONFIG_RECIPE_CYCLE')
        unsupported = {'1': row(1, 900, [(4, True)])}
        with self.assertRaises(ParseError) as caught:
            self.map(unsupported)
        self.assertEqual(caught.exception.code, 'CODE_CONFIG_VALUE')

    def test_wrong_source_identity_and_unrecognized_code_shape_are_rejected(self):
        with self.assertRaises(ParseError) as caught:
            configuration.map_payload(self.table, self.source, expected_table_sha256='0' * 64,
                expected_source_sha256=legacy_configuration.SOURCE_SHA256, root_dish_id=900)
        self.assertEqual(caught.exception.code, 'CODE_CONFIG_TABLE_IDENTITY')
        span = legacy_configuration.SOURCE_SPANS['flattenIngredientsOf']
        bad_source = bytearray(self.source)
        bad_source[span['byteOffset']] ^= 1
        bad_source = bytes(bad_source)
        legacy_configuration.SOURCE_SHA256 = hashlib.sha256(bad_source).hexdigest()
        with self.assertRaises(ParseError) as caught:
            configuration.map_payload(self.table, bad_source,
                expected_table_sha256=legacy_configuration.TABLE_SHA256,
                expected_source_sha256=hashlib.sha256(bad_source).hexdigest(), root_dish_id=900)
        self.assertEqual(caught.exception.code, 'CODE_CONFIG_SOURCE_CONTRACT')

    def test_extension_binding_is_exact_and_returns_only_opt_in_output_contract(self):
        from grea.recovery.code_semantics import NUMBER, Type

        catalog = {
            'id': 'module-recipe-catalog',
            'targetClass': 'RecipeCatalog',
            '_class': {'name': 'qp'},
            '_fields': {'_dishMap': Type('Map', (NUMBER, Type('Recipe')))},
        }
        context = {'records': {'Recipe': {'ingredients': Type('Map', (NUMBER, NUMBER))}}}
        descriptor = configuration.validate_module_binding('Game.Domain.Recovered', [catalog], context)
        self.assertEqual(descriptor['catalogModuleId'], 'module-recipe-catalog')
        self.assertEqual(descriptor['extensionId'], 'legacy_foodstreet')
        self.assertEqual(descriptor['scope'], 'legacy-project-specific')
        self.assertIn('extensions/legacy_foodstreet/extension.json', descriptor['generatorFiles'])
        self.assertIn('extensions/legacy_foodstreet/RecipeJsonConfiguration.cs', descriptor['generatorFiles'])

        for bad_namespace, bad_class, bad_field, bad_record in (
            ('Other.Namespace', 'qp', catalog['_fields'], context['records']),
            ('Game.Domain.Recovered', 'other', catalog['_fields'], context['records']),
            ('Game.Domain.Recovered', 'qp', {'_dishMap': Type('Map', (NUMBER, NUMBER))}, context['records']),
            ('Game.Domain.Recovered', 'qp', catalog['_fields'], {'Recipe': {'ingredients': Type('List', (NUMBER,))}}),
        ):
            rejected = {**catalog, '_class': {'name': bad_class}, '_fields': bad_field}
            with self.assertRaisesRegex(ParseError, 'CODE_CONFIG_MODULE_BINDING'):
                configuration.validate_module_binding(bad_namespace, [rejected], {'records': bad_record})


if __name__ == '__main__':
    unittest.main()
