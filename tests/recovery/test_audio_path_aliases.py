import tempfile
import unittest
from pathlib import Path
from grea.recovery import io
from grea.recovery.layout import standard
from grea.recovery.layout.records import resource_paths
from grea.recovery.sources.compiled import ParseError


class AudioPathAliasTests(unittest.TestCase):
    def fixture(self, project, engine):
        root = standard.ROOTS[engine]['content']
        target = root + '/Audio/Music/Shared/theme.mp3'
        reserved = root + '/Audio/Music/Shared/theme_duplicate.mp3'
        raw = b'ID3-exact-shared-audio'
        (project / target).parent.mkdir(parents=True)
        (project / target).write_bytes(raw)
        io.write_json(project / standard.analysis('package-name-map.json'), dict(records=[
            dict(sourceId='source:second', target=reserved, type='music', kind='native', originalPath='Audio/theme')]))
        io.write_json(project / standard.analysis('resource-ledger.json'), dict(files=[
            dict(sourceId='source:second', category='Audio', disposition='deduplicated',
                 target=target, targetState='pending_native_import', bytes=len(raw), sha256=io.sha(raw))]))
        return target, reserved

    def test_each_source_address_resolves_the_verified_emitted_audio_in_both_engines(self):
        for engine in ('unity', 'creator'):
            with self.subTest(engine=engine), tempfile.TemporaryDirectory() as temp:
                project = Path(temp).resolve()
                target, reserved = self.fixture(project, engine)
                resource_paths(project, engine)
                row = io.load(io.read(project / standard.analysis('resource-paths.json')))['assets'][0]
                self.assertEqual(row['sourceId'], 'source:second')
                self.assertEqual(row['path'], target)
                self.assertEqual(row['reservedPath'], reserved)
                self.assertTrue(row['loadKey'].endswith('/theme'))
                self.assertEqual(row['state'], 'exported')
                self.assertFalse((project / reserved).exists())

    def test_missing_or_changed_canonical_bytes_cannot_borrow_alias_proof(self):
        for missing in (False, True):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temp:
                project = Path(temp).resolve()
                target, _ = self.fixture(project, 'unity')
                if missing: (project / target).unlink()
                else: (project / target).write_bytes(b'ID3-different-audio')
                with self.assertRaisesRegex(ParseError, 'AUDIO_ALIAS_TARGET_CHANGED'):
                    resource_paths(project, 'unity')
