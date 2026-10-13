#!/usr/bin/env python3
"""Synthetic checks for skill documentation contracts; no Unity or external services."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (Path(__file__).resolve().parents[2] / 'scripts/check_skill.py')


class SkillChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / '工作区'
        self.skill = self.root / '.agents/skills/game-build'
        (self.skill / 'references').mkdir(parents=True)
        (self.root / 'tools/bin').mkdir(parents=True)
        (self.root / 'tools/game-building/scripts').mkdir(parents=True)
        (self.root / 'tools/bin/recovery').write_text("local=set()\nskill={'audit'}\n")
        (self.root / 'tools/registry.json').write_text(json.dumps({'tools': [{'id': 'audit'}]}))
        (self.root / 'tools/game-building/scripts/audit.py').write_text('# never executed\n')
        (self.skill / 'SKILL.md').write_text('[主题](references/1-主题.md#中文标题)\n`recovery audit --help`\n')
        (self.skill / 'references/1-主题.md').write_text('# 中文标题\n')

    def tearDown(self):
        self.temp.cleanup()

    def run_check(self, skill=None):
        command = [sys.executable, str(SCRIPT), '--workspace-root', str(self.root), '--json']
        if skill:
            command += ['--skill-dir', str(skill)]
        process = subprocess.run(command, cwd=self.temp.name, capture_output=True, text=True, timeout=10)
        return process.returncode, json.loads(process.stdout)

    def test_valid_inline_link_and_cli(self):
        code, result = self.run_check()
        self.assertEqual(code, 0)
        self.assertEqual(result['recovery_ids'], ['audit'])

    def test_candidate_routes_external_links_to_workspace(self):
        import shutil
        candidate = Path(self.temp.name) / 'candidate'
        shutil.copytree(self.skill, candidate)
        with (candidate / 'SKILL.md').open('a') as f:
            f.write('[工具](../../../tools/registry.json)\n')
        code, result = self.run_check(candidate)
        self.assertEqual((code, result['errors']), (0, []))

    def test_missing_file_anchor_tool_and_unreachable_reference(self):
        with (self.skill / 'SKILL.md').open('a') as f:
            f.write('[缺文件](missing.md)\n[坏锚点](references/1-主题.md#错)\n`recovery unknown --help`\n')
        (self.skill / 'references/2-孤立.md').write_text('# Unreachable\n')
        code, result = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual({x['code'] for x in result['errors']},
                         {'missing_link_target', 'missing_heading_anchor',
                          'unknown_recovery_id', 'unreachable_reference'})

    def test_missing_implementation_and_duplicate_registry(self):
        (self.root / 'tools/game-building/scripts/audit.py').unlink()
        (self.root / 'tools/registry.json').write_text(json.dumps({'tools': [{'id': 'audit'}, {'id': 'audit'}]}))
        code, result = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual({x['code'] for x in result['errors']},
                         {'missing_tool_implementation', 'duplicate_registry_id'})

    def test_history_optional_but_escape_is_error(self):
        with (self.skill / 'SKILL.md').open('a') as f:
            f.write('[历史](../../../projects/not-distributed/source.md)\n[越界](../../../../outside.md)\n')
        code, result = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual(result['warnings'][0]['code'], 'historical_project_source_unavailable')
        self.assertEqual(result['errors'][0]['code'], 'link_outside_workspace')

    def test_invalid_input_and_symlink_escape(self):
        code, result = self.run_check(Path(self.temp.name) / 'absent')
        self.assertEqual(code, 2)
        outside = Path(self.temp.name) / 'outside.md'
        outside.write_text('# Secret outside scope\n')
        (self.skill / 'references/2-link.md').symlink_to(outside)
        code, result = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('skill_symlink_escape', {x['code'] for x in result['errors']})
        (self.skill / 'SKILL.md').unlink()
        (self.skill / 'SKILL.md').symlink_to(outside)
        code, result = self.run_check()
        self.assertEqual(code, 2)


if __name__ == '__main__':
    unittest.main()
