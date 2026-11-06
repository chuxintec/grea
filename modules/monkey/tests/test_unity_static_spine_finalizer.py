import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "src/monkey/targets/spine/UnitySpineGraphicMaterialPresentation.cs"


class UnityStaticSpineFinalizerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_apply_exact_bindings_returns_the_computed_material_verification(self):
        start = self.source.index("public Readback ApplyExactBindings()")
        end = self.source.index("public Readback ReadSaved()", start)
        block = self.source[start:end]
        self.assertIn("nativeMaterialVerified = verified", block)
        self.assertIn("lastGaps, pose, pairsVerified, status, verified", block)
        self.assertNotIn("BuildReadback(instructionType, instructions == null ? 0 : instructions.Length, rows, lastGaps, pose, pairsVerified);", block)

    def test_apply_exact_bindings_does_not_clear_or_ignore_failed_gaps(self):
        start = self.source.index("public Readback ApplyExactBindings()")
        end = self.source.index("public Readback ReadSaved()", start)
        block = self.source[start:end]
        self.assertIn("lastGaps = gaps.Distinct(StringComparer.Ordinal).ToArray()", block)
        self.assertIn("lastGaps.Length == 0", block)
        self.assertIn("sdk_zero_submesh_pose_not_proven_initialized_and_empty", block)
