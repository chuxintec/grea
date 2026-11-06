import tempfile
import unittest
from pathlib import Path

from grea.recovery.sources.compiled import ParseError
from grea.recovery.targets.cocos import _validate_extension_dependencies


class CreatorExtensionDependenciesTests(unittest.TestCase):
    def test_generated_module_name_must_resolve_in_emitted_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'owned-import-undo.js').write_text('module.exports={};')
            caller = root / 'static-layout-completion.js'
            caller.write_text("require('./CreatorOwnedImportUndo.js');")
            with self.assertRaisesRegex(ParseError, 'CREATOR_EXTENSION_DEPENDENCY_MISSING'):
                _validate_extension_dependencies(root)
            caller.write_text("require('./owned-import-undo.js'); require('cc');")
            _validate_extension_dependencies(root)

    def test_only_declared_source_fallback_and_disabled_feature_are_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'owned-import-undo.js').write_text(
                "try { require('./editor-undo-diagnostics.js'); } "
                "catch (_) { require('./CreatorEditorUndoDiagnostics.js'); }")
            (root / 'editor-undo-diagnostics.js').write_text('module.exports={};')
            (root / 'scene.js').write_text("require('./static-time-materials.js');")
            _validate_extension_dependencies(root)
            with self.assertRaisesRegex(ParseError, 'CREATOR_EXTENSION_DEPENDENCY_MISSING'):
                _validate_extension_dependencies(root, static_time_materials=True)
            (root / 'static-time-materials.js').write_text('module.exports={};')
            _validate_extension_dependencies(root, static_time_materials=True)

    def test_relative_import_cannot_escape_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scene.js').write_text("require('../outside.js');")
            with self.assertRaisesRegex(ParseError, 'CREATOR_EXTENSION_DEPENDENCY_ESCAPE'):
                _validate_extension_dependencies(root)

    def test_build_teardown_requires_its_emitted_saved_scene_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'owned-build-scene-teardown.js').write_text(
                "try { require('./creator-saved-scene-scope.js'); } "
                "catch (_) { require('./CreatorSavedSceneScope.js'); }")
            with self.assertRaisesRegex(ParseError, 'CREATOR_EXTENSION_DEPENDENCY_MISSING'):
                _validate_extension_dependencies(root)
            (root / 'creator-saved-scene-scope.js').write_text('module.exports={};')
            _validate_extension_dependencies(root)
