import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import shutil
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reference',ROOT/'src/grea/tools/unity_reference.py');ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)


class ReferenceDistributionTests(unittest.TestCase):
    def test_reference_metadata_and_assembly_boundaries(self):
        files=ref.source_files();guids=set();assemblies={}
        version=json.loads(files['distribution-manifest.json'])['version']
        builder=files['Assets/Reference/Editor/ReferenceBuilder.cs'].decode()
        self.assertIn('PlayerVersion = "'+version+'"',builder)
        self.assertIn('PlayerSettings.bundleVersion=PlayerVersion',builder)
        self.assertIn('version=PlayerVersion',builder)
        for name,data in files.items():
            if name.endswith('.meta'):
                guid=re.search(rb'^guid: ([0-9a-f]{32})$',data,re.M)
                self.assertIsNotNone(guid,name);self.assertNotIn(guid[1],guids,name);guids.add(guid[1])
            if name.startswith('Assets/') and not name.endswith('.meta'):
                self.assertIn(name+'.meta',files)
            if name.endswith('.asmdef'):
                definition=json.loads(data);assemblies[definition['name']]=definition
                if definition['name'].endswith('Tests'):
                    self.assertIn('UNITY_INCLUDE_TESTS',definition['defineConstraints'])
                    self.assertIn('TestAssemblies',definition['optionalUnityReferences'])
        self.assertTrue(assemblies['Grea.Reference.Domain']['noEngineReferences'])
        self.assertEqual(assemblies['Grea.Reference.Editor']['includePlatforms'],['Editor'])
        visiting=set();done=set()
        def visit(name):
            self.assertNotIn(name,visiting,'Assembly dependency cycle')
            if name in done:return
            visiting.add(name)
            for dep in assemblies[name].get('references',[]):
                if not name.endswith(('Tests','Editor')):
                    self.assertFalse(dep.endswith(('Tests','Editor')),(name,dep))
                if dep in assemblies:visit(dep)
            visiting.remove(name);done.add(name)
        for name in assemblies:visit(name)
    def test_archive_restore_integrity_and_no_external_file_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();archive=root/'source.zip';ref.archive(archive);files=ref.read_archive(archive)
            dest=root/'独立 restore';ref.write_project(dest,files)
            for name,data in files.items():self.assertEqual((dest/name).read_bytes(),data)
            self.assertTrue((dest/'Packages/com.grea.foundation/package.json').is_file())
            self.assertTrue((dest/'Assets/Reference/Scenes/Reference.unity').is_file())
            self.assertFalse((dest/'Library').exists())
            manifest=json.loads((dest/'Packages/manifest.json').read_text())
            self.assertTrue(all(not v.startswith(('file:','git:','http')) for v in manifest['dependencies'].values()))
            with self.assertRaises(ValueError):ref.write_project(dest,files)
    def test_tampered_source_and_missing_entries_fail_before_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();files=ref.source_files();files['LICENSE.md']=b'tampered'
            archive=root/'bad.zip'
            with zipfile.ZipFile(archive,'w') as z:
                for name,data in files.items():z.writestr(name,data)
            with self.assertRaises(ValueError):ref.read_archive(archive)
    def test_zip_slip_symlinks_and_case_collision_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            for index,names in enumerate([['../escape'],['/absolute'],['A.txt','a.txt'],['con.txt']]):
                path=root/f'bad{index}.zip'
                with zipfile.ZipFile(path,'w') as z:
                    for name in names:z.writestr(name,b'x')
                with self.assertRaises(ValueError):ref.read_archive(path)
            path=root/'link.zip'
            with zipfile.ZipFile(path,'w') as z:
                info=zipfile.ZipInfo('link');info.create_system=3;info.external_attr=0o120777<<16;z.writestr(info,'outside')
            with self.assertRaises(ValueError):ref.read_archive(path)
    def test_framework_lock_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            framework=Path(tmp)/'packages';shutil.copytree(ref.FRAMEWORK,framework)
            with (framework/'com.grea.foundation/package.json').open('a') as f:f.write(' ')
            with patch.object(ref,'FRAMEWORK',framework):
                with self.assertRaises(ValueError):ref.source_files()
    def test_accidental_source_cache_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source';shutil.copytree(ref.SOURCE,source)
            (source/'Library').mkdir();(source/'Library/cache').write_text('local-only')
            with patch.object(ref,'SOURCE',source):
                with self.assertRaises(ValueError):ref.source_files()
    def test_archive_is_reproducible_and_contains_no_caches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();one=root/'one.zip';two=root/'two.zip';ref.archive(one);ref.archive(two)
            self.assertEqual(one.read_bytes(),two.read_bytes())
            for name in ref.read_archive(one):self.assertFalse(any(part in ('Library','Temp','.private','UserSettings','Logs') for part in Path(name).parts))


if __name__=='__main__':unittest.main()
