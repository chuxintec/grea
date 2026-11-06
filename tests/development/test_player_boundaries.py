from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch
from grea.development.io import write_json
from grea.development.output_limits import digest_file
from grea.development.player import run
from grea.development.errors import BeaverError


class PlayerBoundaryTests(unittest.TestCase):
    def test_manifest_pin_payload_drift_and_unknown_files_reject_before_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();app=root/'build/player/Test.app';(app/'Contents/MacOS').mkdir(parents=True)
            exe=app/'Contents/MacOS/Test';exe.write_bytes(b'self-authored non-executed fixture');exe.chmod(0o755)
            info=app/'Contents/Info.plist';info.write_bytes(plistlib.dumps({'CFBundleExecutable':'Test'}))
            manifest=root/'build/artifact-manifest.json'
            write_json(manifest,dict(schemaVersion=1,sourceSha256='a'*64,files=[dict(path=p.relative_to(root/'build').as_posix(),sha256=digest_file(p),bytes=p.stat().st_size) for p in (exe,info)]))
            with patch('grea.development.player.subprocess.Popen') as process:
                with self.assertRaises(BeaverError) as error:run(manifest,root/'run',expected='0'*64)
                self.assertEqual(error.exception.code,'PLAYER_MANIFEST_DRIFT')
                original=exe.read_bytes();exe.write_bytes(b'later change')
                with self.assertRaises(BeaverError) as error:run(manifest,root/'run',expected=digest_file(manifest))
                self.assertEqual(error.exception.code,'PLAYER_ARTIFACT_DRIFT')
                exe.write_bytes(original);(app/'Contents/unknown.txt').write_text('unowned')
                with self.assertRaises(BeaverError) as error:run(manifest,root/'run',expected=digest_file(manifest))
                self.assertEqual(error.exception.code,'PLAYER_UNKNOWN_FILE')
                process.assert_not_called()
