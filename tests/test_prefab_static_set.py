import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from grea.features.prefab.verify_static_set import freeze_expectations, selection_rows


class StaticSetTests(unittest.TestCase):
    def test_identity_and_reference_owner_are_pinned_before_unity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root/"Assets/Test.prefab"
            asset.parent.mkdir()
            raw = b"%YAML 1.1\n--- !u!1 &1\nGameObject:\n--- !u!114 &42\nMonoBehaviour:\n  m_Script: {fileID: 11500000, guid: " + b"b"*32 + b", type: 3}\n"
            asset.write_bytes(raw)
            Path(str(asset)+".meta").write_text("guid: "+"a"*32+"\n")
            row = {"assetPath":"Assets/Test.prefab","guid":"a"*32,"sourceNodes":1,"sha256":hashlib.sha256(raw).hexdigest()}
            freeze_expectations(root, selection_rows(json.dumps(row).encode()), root)
            self.assertIn("42:"+"b"*32+":11500000", (root/"references.tsv").read_text())
            with self.assertRaises(ValueError):
                selection_rows((json.dumps(row)+"\n"+json.dumps(row)).encode())
            with self.assertRaises(ValueError):
                selection_rows(json.dumps(dict(row,assetPath="../outside.prefab")).encode())
