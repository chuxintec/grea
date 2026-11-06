"""All maintained Skill examples must resolve against the executable public interface."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from check_skill_commands import check


class SkillExamplesTests(unittest.TestCase):
    def test_examples_use_real_commands_and_parameters(self):
        report = check(ROOT/"plugin/skills")
        self.assertTrue(report["ok"], report["errors"])
        self.assertGreater(report["examples"], 0)
