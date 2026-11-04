import tomllib
import unittest
from pathlib import Path

from monkey import __version__


class ReleaseVersionTests(unittest.TestCase):
    def test_package_metadata_and_runtime_version_match(self):
        metadata_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        metadata = tomllib.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(metadata["project"]["version"], __version__)
        self.assertRegex(__version__, r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:\.dev[1-9][0-9]*)?$")


if __name__ == "__main__":
    unittest.main()
