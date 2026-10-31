from pathlib import Path
import tempfile
import unittest

from monkey.native_selection import _shader_include_paths
from monkey.sources.compiled import ParseError


class ShaderIncludeSelectionTests(unittest.TestCase):
    def test_relative_and_builtin_includes_are_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'Assets/Shaders').mkdir(parents=True)
            (root / 'Assets/Shaders/Surface.cginc').write_text('// shared declarations\n')
            raw = b'#include "Surface.cginc"\n#include "UnityCG.cginc"\n// #include "ignored"\n'
            project, builtin = _shader_include_paths(raw, 'Assets/Shaders/Example.shader', root)
            self.assertEqual(['Assets/Shaders/Surface.cginc'], project)
            self.assertEqual(['UnityCG.cginc'], builtin)

    def test_local_builtin_named_file_must_be_included_not_whitelisted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'Assets').mkdir()
            (root / 'Assets/UnityCG.cginc').write_text('// explicit project file')
            self.assertEqual((['Assets/UnityCG.cginc'], []),
                _shader_include_paths(b'#include "UnityCG.cginc"', 'Assets/A.shader', root))

    def test_macro_unknown_and_escaping_paths_are_not_silently_skipped(self):
        for directive in [b'#include DYNAMIC_PATH', b'#include "missing.cginc"',
                          b'#include "/tmp/foreign.cginc"', b'#include "../../foreign.cginc"']:
            with self.subTest(directive=directive), self.assertRaises(ParseError):
                _shader_include_paths(directive, 'Assets/A.shader', Path('/private/tmp'))

    def test_non_shader_data_and_block_comments_are_not_dependencies(self):
        self.assertEqual(([], []), _shader_include_paths(b'#include "missing"', 'Assets/X.json', Path('/private/tmp')))
        self.assertEqual(([], []), _shader_include_paths(b'/*\n#include "missing"\n*/', 'Assets/X.shader', Path('/private/tmp')))
