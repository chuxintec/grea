import unittest


class RawScriptTests(unittest.TestCase):
    def test_raw_textasset_surrogateescape_roundtrip(self):
        from monkey.toolkit.export_config_tables import raw_script
        raw=bytes([255,0,3,9]);self.assertEqual(raw_script(raw.decode('utf8','surrogateescape')),raw)


if __name__=='__main__':unittest.main()
