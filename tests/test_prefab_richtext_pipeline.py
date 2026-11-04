import unittest

from monkey.prefab_richtext_pipeline import _selected_richtext_components


class RichTextPipelineSelectionTests(unittest.TestCase):
    def setUp(self):
        self.a = {"type": "cc.RichText", "sourceId": "asset#1"}
        self.b = {"type": "cc.RichText", "sourceId": "asset#2"}
        self.other = {"type": "cc.Label", "sourceId": "asset#3"}
        self.plan = {"components": [self.a, self.b, self.other]}

    def test_default_selects_all_richtext_components(self):
        self.assertEqual(_selected_richtext_components(self.plan, None), [self.a, self.b])

    def test_explicit_selection_only_binds_named_source_richtext(self):
        self.assertEqual(_selected_richtext_components(self.plan, ["asset#2"]), [self.b])

    def test_explicit_selection_rejects_unknown_or_nontype_sources(self):
        for selection in (["missing"], ["asset#3"], ["asset#1", "asset#1"], [1]):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                _selected_richtext_components(self.plan, selection)


if __name__ == "__main__":
    unittest.main()
