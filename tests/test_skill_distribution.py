"""Skill is independently relocatable, versioned and tied to immutable source."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import build_skill


class SkillDistributionTests(unittest.TestCase):
    def source(self):
        value={'version':'1.2.3rc1','greaVersion':'1.2.3rc1','requiredOperations':['session']}
        return {k:(v.encode(),0o100644) for k,v in {
            'skill/SKILL.md':'---\nname: grea\ndescription: Test\n---\n[流程](references/Unity-恢复.md) [说明](../docs/使用.md#示例)\n',
            'skill/.gitignore':'__pycache__/\n',
            'skill/references/Unity-恢复.md':'# 恢复\n[入口](../SKILL.md)\n',
            'skill/version.json':json.dumps(value),'docs/使用.md':'# 示例\n','LICENSE':'MIT\n'}.items()}
    def test_versioned_relocatable_and_reproducible(self):
        source=self.source();files=build_skill.render(source,'1.2.3rc1','a'*40)
        entry=files['grea/SKILL.md'].decode();self.assertIn('/'+'a'*40+'/',entry);self.assertNotIn('../docs/',entry);self.assertNotIn('grea/.gitignore',files)
        manifest=json.loads(files['grea/skill-manifest.json']);self.assertEqual(manifest['version'],'1.2.3rc1');self.assertEqual(len(manifest['files']),4)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();a=root/'a.zip';b=root/'b.zip';stamp=datetime(2026,10,13,tzinfo=timezone.utc)
            build_skill.write_archive(a,files,stamp);build_skill.write_archive(b,files,stamp);self.assertEqual(a.read_bytes(),b.read_bytes())
            build_skill.verify_archive(a,files,root/'unrelated');actual={str(p.relative_to(root/'unrelated')):p.read_bytes() for p in (root/'unrelated').rglob('*') if p.is_file()}
            build_skill.validate_local_links(actual);self.assertEqual(actual,files)
            with self.assertRaises(ValueError):build_skill.verify_archive(a,files,root/'unrelated')
    def test_version_missing_link_and_local_escape_rejected(self):
        for kind in ['version','missing','absolute']:
            source=self.source()
            if kind=='version':source['skill/version.json']=(b'{"version":"9","greaVersion":"9"}',0o100644)
            else:source['skill/SKILL.md']=(('[bad]('+('missing.md' if kind=='missing' else '/local/file')+')').encode(),0o100644)
            with self.assertRaises(ValueError):build_skill.render(source,'1.2.3rc1','a'*40)
    def test_tamper_and_extra_path_fail_before_extraction(self):
        files=build_skill.render(self.source(),'1.2.3rc1','a'*40)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();archive=root/'skill.zip';build_skill.write_archive(archive,files,datetime(2026,10,13,tzinfo=timezone.utc))
            with zipfile.ZipFile(archive,'a') as z:z.writestr('../escape',b'bad')
            with self.assertRaises(ValueError):build_skill.verify_archive(archive,files,root/'output')
            self.assertFalse((root/'output').exists())
    def test_current_skill_manifest_declares_available_operations(self):
        from grea.contracts import CONTRACTS
        from grea import __version__
        value=json.loads((ROOT/'skill/version.json').read_text());self.assertEqual(value['version'],__version__);self.assertEqual(value['greaVersion'],__version__)
        self.assertTrue(set(value['requiredOperations']) <= set(CONTRACTS))
    def test_tool_modules_import_without_execution(self):
        # These modules formerly parsed argv/wrote output during import.
        with tempfile.TemporaryDirectory() as tmp:
            result=subprocess.run([sys.executable,'-c','import grea.tools.shader_probe, grea.tools.unpack_xapk'],cwd=tmp,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(list(Path(tmp).iterdir()),[])

if __name__=='__main__':unittest.main()
