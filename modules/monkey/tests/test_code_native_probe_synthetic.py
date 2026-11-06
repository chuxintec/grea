import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from monkey.code_native_probe import prepare
from monkey.sources.compiled import ParseError


class NativeProbeSyntheticBoundaryTests(unittest.TestCase):
    def test_unapproved_source_identity_is_rejected_before_candidate_files_are_read(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory) / "candidate"
            root.mkdir()
            manifest = {
                "schemaVersion": 1,
                "source": {"sha256": "0" * 64, "bytes": 1},
                "files": [],
            }
            raw = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
            (root / "manifest.json").write_bytes(raw)

            with self.assertRaises(ParseError) as caught:
                prepare(root, hashlib.sha256(raw).hexdigest(), Path(directory) / "output")

            self.assertEqual(caught.exception.code, "CODE_NATIVE_SOURCE_IDENTITY")
            self.assertFalse((Path(directory) / "output").exists())


if __name__ == "__main__":
    unittest.main()
