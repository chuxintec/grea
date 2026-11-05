"""Check probe source/meta identity in an explicitly supplied built wheel."""

from __future__ import annotations

import os
from pathlib import Path
import re
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PROBE_FILES = (
    "monkey/targets/behaviors/probes/UnityBehaviorProbe.cs",
    "monkey/targets/behaviors/probes/UnityBehaviorProbe.cs.meta",
    "monkey/targets/behaviors/probes/Editor/MonkeyBehaviorProbeBootstrap.cs",
    "monkey/targets/behaviors/probes/Editor/MonkeyBehaviorProbeBootstrap.cs.meta",
)


class PackagedProbeMetadataTests(unittest.TestCase):
    def test_probe_sources_and_meta_are_preserved_in_built_wheel(self) -> None:
        wheel_value = os.environ.get("MONKEY_AUDIT_WHEEL")
        if not wheel_value:
            self.skipTest("set MONKEY_AUDIT_WHEEL to the isolated candidate wheel")

        wheel = Path(wheel_value).expanduser().resolve(strict=True)
        self.assertTrue(wheel.is_file(), wheel)
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
            for relative in PROBE_FILES:
                with self.subTest(path=relative):
                    self.assertEqual(names.count(relative), 1, f"wheel member count: {relative}")
                    source = ROOT / "src" / relative
                    self.assertEqual(
                        archive.read(relative),
                        source.read_bytes(),
                        f"wheel bytes differ from pinned source: {relative}",
                    )

            for metadata in (PROBE_FILES[1], PROBE_FILES[3]):
                with self.subTest(guid=metadata):
                    if names.count(metadata) != 1:
                        self.fail(f"Unity metadata is missing or duplicated in wheel: {metadata}")
                    data = archive.read(metadata).decode("utf-8")
                    match = re.search(r"(?m)^guid: ([0-9a-f]{32})$", data)
                    self.assertIsNotNone(match, f"invalid Unity meta GUID: {metadata}")
                    self.assertEqual(len(re.findall(r"(?m)^guid: ", data)), 1)


if __name__ == "__main__":
    unittest.main()
