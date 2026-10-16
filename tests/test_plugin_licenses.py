import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))


class RuntimeLicenseTests(unittest.TestCase):
    def fixture(self):
        return {'license_path':'licenses/LICENSE.cpython.txt','build_info':{'extensions':{
            name:[{'variant':'default','license_paths':['licenses/LICENSE.zlib.txt','licenses/LICENSE.zlib-ng.txt'],
                   'links':[{'name':'z','system':True}]}] for name in ('_sqlite3','_tkinter','binascii','zlib')}}}

    def module(self):
        self.assertTrue((ROOT/'scripts/runtime_licenses.py').is_file(), 'Runtime license closure is missing')
        import runtime_licenses
        return runtime_licenses

    def test_only_proven_system_zlib_metadata_exception_is_allowed(self):
        value=self.module().check_license_closure(self.fixture(),{'licenses/LICENSE.cpython.txt','licenses/LICENSE.zlib.txt'})
        self.assertEqual(value[0]['path'],'licenses/LICENSE.zlib-ng.txt')
        self.assertEqual(value[0]['system_library'],'z')

    def test_unknown_missing_license_or_static_zlib_is_rejected(self):
        module=self.module()
        available={'licenses/LICENSE.cpython.txt','licenses/LICENSE.zlib.txt'}
        data=self.fixture();data['license_path']='licenses/UNKNOWN.txt'
        with self.assertRaises(ValueError):module.check_license_closure(data,available)
        data=self.fixture();data['build_info']['extensions']['zlib'][0]['links']=[{'name':'z','path_static':'build/lib/z.a'}]
        with self.assertRaises(ValueError):module.check_license_closure(data,available)

    def test_complete_license_set_needs_no_exception(self):
        self.assertEqual(self.module().check_license_closure(self.fixture(),{
            'licenses/LICENSE.cpython.txt','licenses/LICENSE.zlib.txt','licenses/LICENSE.zlib-ng.txt'}),[])
