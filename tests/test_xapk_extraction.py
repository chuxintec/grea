import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from grea.tools import unpack_xapk
from grea.common import GreaError


def archive(entries):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as z:
        for name,raw in entries:z.writestr(name,raw)
    return buffer.getvalue()


class XapkExtraction(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.apk=archive([('AndroidManifest.xml',b'manifest'),('classes.dex',b'dex'),('assets/data',b'asset'),('lib/arm64-v8a/libgame.so',b'native')])
        self.source=self.root/'input.xapk'
        self.source.write_bytes(archive([('base.apk',self.apk),('split.apk',self.apk),('main.obb',b'opaque')]))

    def test_full_and_legacy_scopes_keep_every_identity(self):
        for scope in ['assets','all-entries']:
            output=self.root/scope
            report=unpack_xapk.unpack(self.source,output,scope=scope)
            self.assertEqual(report['apk_count'],2)
            self.assertEqual(len(report['entries']),8)
            self.assertTrue((output/'Reference/main.obb').is_file())
            self.assertEqual((output/'Analysis/unpacked/base/classes.dex').exists(),scope=='all-entries')
            self.assertTrue(all(row['sha256'] and row['crc32'] for row in report['entries']))
            self.assertFalse(report['game_recovery_proven'])
            with self.assertRaises((ValueError,FileExistsError)):unpack_xapk.unpack(self.source,output,scope=scope)

    def test_empty_container_duplicates_and_budget_reject(self):
        for entries in [[('readme',b'not apk')],[('../escape.apk',self.apk)],[('base.apk',self.apk),('BASE.apk',self.apk)]]:
            self.source.write_bytes(archive(entries));out=self.root/'bad'
            with self.assertRaises(ValueError):unpack_xapk.unpack(self.source,out)
            self.assertFalse(out.exists())
        self.source.write_bytes(archive([('base.apk',self.apk)]))
        with self.assertRaises(ValueError):unpack_xapk.unpack(self.source,self.root/'limit',max_bytes=3)

    def test_direct_apk_and_missing_source(self):
        self.source.write_bytes(self.apk)
        result=unpack_xapk.unpack(self.source,self.root/'direct',scope='all-entries')
        self.assertEqual(result['container_format'],'apk')
        with self.assertRaises((ValueError,OSError,GreaError)):unpack_xapk.unpack(self.root/'missing',self.root/'never')


if __name__=='__main__':unittest.main()
