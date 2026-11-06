import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from monkey import output_limits as limits
from monkey.candidate_snapshot import snapshot
from monkey.io import write_json, sha
from monkey.sources.compiled import ParseError


class OutputPolicyTests(unittest.TestCase):
    def test_whole_input_inventory_accepts_large_manifest_but_selection_stays_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            rows=[dict(path='Assets/Game/Content/Data/Main/F'+str(i)+'.bytes',sha256='a'*64,bytes=40_000,owner='generated') for i in range(21_000)]
            m=dict(schemaVersion=1,targetProfile='unity-6000.6.2f1-ugui',namespace='large',scopeMode='whole-input',files=rows)
            write_json(root/'manifest.json',m)
            self.assertEqual(len(snapshot(root)[2]),21000)
            m.pop('scopeMode');write_json(root/'manifest.json',m)
            with self.assertRaises(ParseError):snapshot(root)

    def test_case_collision_and_forged_manifest_limits_cannot_expand_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();rows=[dict(path='Assets/a',sha256='a'*64,bytes=1),dict(path='Assets/A',sha256='b'*64,bytes=1)]
            m=dict(schemaVersion=1,targetProfile='unity-6000.6.2f1-ugui',namespace='x',files=rows,scopeMode='whole-input')
            write_json(root/'manifest.json',m)
            with self.assertRaises(ParseError):snapshot(root)
            m['files']=[dict(path='Assets/a',sha256='a'*64,bytes=limits.FILE_BYTES+1)];m['limits']={'maxOwnedFileBytes':10**15};write_json(root/'manifest.json',m)
            with self.assertRaises(ParseError):snapshot(root)

    def test_streamed_copy_rejects_identity_drift_without_replacing_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();a=root/'a';b=root/'b';a.write_bytes(b'new');b.write_bytes(b'old')
            with self.assertRaises(ParseError):limits.copy_verified(a,b,sha(b'wrong'),3)
            self.assertEqual(b.read_bytes(),b'old');self.assertEqual(list(root.glob('.monkey-copy-*')),[])
            limits.copy_verified(a,b,sha(b'new'),3);self.assertEqual(b.read_bytes(),b'new')

    def test_hash_reads_files_larger_than_the_old_32mb_read_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp).resolve()/'large';p.write_bytes(b'x'*(33*1024**2))
            expected=sha(p.read_bytes());self.assertEqual(limits.digest_file(p),expected)
            with self.assertRaises(ParseError):limits.digest_file(p,max_bytes=32*1024**2)
