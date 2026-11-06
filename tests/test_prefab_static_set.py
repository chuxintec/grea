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

    def test_nested_handles_pin_sources_separately_from_direct_component_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root/"Assets/Nested.prefab"
            asset.parent.mkdir()
            raw = (b"%YAML 1.1\n--- !u!1 &9\nGameObject:\n--- !u!1001 &50\nPrefabInstance:\n"
                   b"  m_SourcePrefab: {fileID: 100100000, guid: "+b"c"*32+b", type: 3}\n"
                   b"--- !u!224 &76 stripped\nRectTransform:\n")
            asset.write_bytes(raw)
            Path(str(asset)+".meta").write_text("guid: "+"a"*32+"\n")
            row = dict(assetPath="Assets/Nested.prefab",guid="a"*32,sourceNodes=1,
                       sha256=hashlib.sha256(raw).hexdigest())
            freeze_expectations(root,[row],root)
            self.assertEqual((root/"roots.tsv").read_text().splitlines()[0].split("\t")[3:],
                             ["9","","50:"+"c"*32])
            self.assertEqual((root/"references.tsv").read_text(),"")
