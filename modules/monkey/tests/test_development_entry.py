import contextlib
import io
import json
import unittest

from monkey import __version__
from monkey.cli import main


class DevelopmentEntryTests(unittest.TestCase):
    def test_version_identifies_monkey_and_bundled_engineering(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["develop", "--version"]), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["producer"]["name"], "monkey")
        self.assertEqual(result["producer"]["version"], __version__)
        self.assertEqual(result["data"]["version"], __version__)
        self.assertTrue(result["data"]["engineeringVersion"])

    def test_invalid_engineering_command_preserves_structured_failure(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["develop", "intake", "not-an-operation"]), 3)
        result = json.loads(output.getvalue())
        self.assertEqual(result["diagnostics"][0]["code"], "CLI_USAGE")
        self.assertEqual(result["actualChanges"], [])
