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


class SkillDistributionTests(unittest.TestCase):
    def source(self):
        value={'version':'1.2.3rc1','greaVersion':'1.2.3rc1','requiredOperations':['session']}
        manifest=json.dumps({'name':'grea','version':'1.2.3rc1'})
        return {k:(v.encode(),0o100644) for k,v in {
            'plugin/skills/grea/SKILL.md':'---\nname: grea\ndescription: Test\n---\n[流程](../grea-port/references/Unity-恢复.md) [说明](../../../docs/使用.md#示例) [共用](../../shared/共用.md)\n',
            'plugin/skills/grea-port/SKILL.md':'---\nname: grea-port\ndescription: Port\n---\n[流程](references/Unity-恢复.md)\n',
            'plugin/skills/grea-port/references/Unity-恢复.md':'# 恢复\n[入口](../../grea/SKILL.md)\n',
            'plugin/shared/共用.md':'# 共用\n',
            'plugin/.gitignore':'__pycache__/\n',
            'plugin/.codex-plugin/plugin.json':manifest,'plugin/.claude-plugin/plugin.json':manifest,
            'plugin/version.json':json.dumps(value),'docs/使用.md':'# 示例\n','LICENSE':'MIT\n'}.items()}
    def test_current_skill_manifest_declares_available_operations(self):
        from grea.contracts import CONTRACTS
        from grea import __version__
        value=json.loads((ROOT/'plugin/version.json').read_text());self.assertEqual(value['version'],__version__);self.assertEqual(value['greaVersion'],__version__)
        self.assertTrue(set(value['requiredOperations']) <= set(CONTRACTS))
    def test_tool_modules_import_without_execution(self):
        # These modules formerly parsed argv/wrote output during import.
        with tempfile.TemporaryDirectory() as tmp:
            result=subprocess.run([sys.executable,'-c','import grea.tools.shader_probe, grea.tools.unpack_xapk'],cwd=tmp,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(list(Path(tmp).iterdir()),[])

if __name__=='__main__':unittest.main()
