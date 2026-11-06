import json
import os
import subprocess
import sys
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

from grea.recovery.code_profiles import load_profile, profile_capabilities
from grea.recovery.io import encoded
from grea.recovery.sources.compiled import ParseError


# Compatibility identifiers: public callers may already select these exact profiles.
COMPATIBILITY_PROFILE_IDS = (
    "foodstreet-demand-health-v1",
    "foodstreet-motion-math-v1",
)


class BuiltInCodeProfileTests(unittest.TestCase):
    def test_allowlisted_profiles_are_packaged_canonical_and_source_bound(self):
        for profile_name in COMPATIBILITY_PROFILE_IDS:
            with self.subTest(profile=profile_name):
                raw = files("grea.recovery.extensions.legacy_foodstreet").joinpath("code_profiles", profile_name + ".json").read_bytes()
                profile = json.loads(raw)
                self.assertEqual(encoded(profile), raw)
                self.assertEqual(profile["profileName"], profile_name)
                self.assertRegex(profile["sourceSha256"], r"^[0-9a-f]{64}$")
                self.assertGreater(profile["sourceBytes"], 0)
                text = raw.decode("utf-8")
                for forbidden in (".private", "/Users/", "/private/", "game.js", "SourceRecovery"):
                    self.assertNotIn(forbidden, text)
        extension = json.loads(files("grea.recovery.extensions.legacy_foodstreet").joinpath("extension.json").read_bytes())
        declared = {row["profileName"]: row for row in extension["profiles"]}
        demand = json.loads(files("grea.recovery.extensions.legacy_foodstreet").joinpath("code_profiles", COMPATIBILITY_PROFILE_IDS[0] + ".json").read_bytes())
        motion = json.loads(files("grea.recovery.extensions.legacy_foodstreet").joinpath("code_profiles", COMPATIBILITY_PROFILE_IDS[1] + ".json").read_bytes())
        for profile_name, profile in ((COMPATIBILITY_PROFILE_IDS[0], demand), (COMPATIBILITY_PROFILE_IDS[1], motion)):
            row = declared[profile_name]
            raw = files("grea.recovery.extensions.legacy_foodstreet").joinpath(row["resource"]).read_bytes()
            self.assertEqual(row["bytes"], len(raw))
            self.assertEqual(row["sha256"], __import__("hashlib").sha256(raw).hexdigest())
        self.assertEqual(len(demand["records"]), 3)
        self.assertEqual(sum(len(module["methods"]) for module in demand["modules"]), 12)
        self.assertEqual(len(motion["modules"]), 1)
        self.assertEqual(len(motion["modules"][0]["methods"]), 4)

    def test_unknown_profile_is_rejected_before_reading_source(self):
        with self.assertRaises(ParseError) as caught:
            load_profile("demo-unknown-v2", "missing-source.js")
        self.assertEqual(caught.exception.code, "CODE_PROFILE_UNKNOWN")

    def test_source_sha_or_size_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            wrong = Path(directory) / "wrong.js"
            wrong.write_bytes(b"not the pinned source")
            with self.assertRaises(ParseError) as caught:
                load_profile(COMPATIBILITY_PROFILE_IDS[0], wrong)
            self.assertEqual(caught.exception.code, "CODE_PROFILE_SOURCE_IDENTITY")

    def test_exact_profile_selection_remains_explicit_and_refuses_source_drift(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            wrong = Path(directory) / "wrong.js"
            wrong.write_bytes(b"different extension source")
            with self.assertRaises(ParseError) as caught:
                load_profile(COMPATIBILITY_PROFILE_IDS[1], wrong)
            self.assertEqual(caught.exception.code, "CODE_PROFILE_SOURCE_IDENTITY")

    def test_capability_listing_reads_opt_in_metadata_without_importing_provider(self):
        with patch("grea.recovery.code_profiles.import_module", side_effect=AssertionError("provider activation")):
            capabilities = profile_capabilities()
        self.assertEqual(set(capabilities["profiles"]), set(COMPATIBILITY_PROFILE_IDS))
        extension = next(row for row in capabilities["extensions"] if row["extensionId"] == "legacy_foodstreet")
        self.assertEqual(extension["scope"], "legacy-project-specific")
        self.assertFalse(extension["defaultEnabled"])
        self.assertTrue(extension["explicitOptIn"])

    def test_core_adapter_import_and_capabilities_do_not_activate_legacy_provider(self):
        code = (
            "import sys; import grea.recovery.code_configuration; "
            "from grea.recovery.code_profiles import profile_capabilities; profile_capabilities(); "
            "assert 'grea.recovery.extensions.legacy_foodstreet.configuration' not in sys.modules"
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
        completed = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[2],
                                   env=env, capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
