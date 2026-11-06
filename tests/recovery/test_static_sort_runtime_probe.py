import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
PROBE = ROOT / "tests/recovery/native/StaticSortRuntimeProbe.cs"
DRIVER = ROOT / "tests/recovery/native/StaticSortRuntimeProbeDriver.cs"
BASELINE = "a458790a68d57108b4cfe038d8aa565d5cc1599b"


class StaticSortRuntimeProbeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.probe = PROBE.read_text(encoding="utf-8")
        cls.code = cls.probe + DRIVER.read_text(encoding="utf-8")

    def test_editor_entry_runs_isolated_playmode_and_writes_requested_json(self):
        self.assertIn("namespace Monkey.Tests", self.probe)
        self.assertIn("public static void Run()", self.probe)
        self.assertIn('Argument("-monkeyProbeOutput")', self.probe)
        self.assertIn("EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single)", self.probe)
        self.assertIn("EditorApplication.isPlaying = true", self.probe)
        self.assertIn("File.WriteAllText(path, json)", self.probe)
        self.assertIn("EditorApplication.Exit(SessionState.GetInt(ExitKey, 1))", self.probe)

    def test_receipt_covers_runtime_changes_native_raycast_and_mesh_immutability(self):
        for observation in (
            "imageFillAndRectRefreshed", "imageSpriteAndColorRefreshed", "textLengthColorRefreshed",
            "sourceDeactivateReactivateRefreshed", "canvasGroupAlphaProjected", "maskBindingPresent",
            "sourceButtonRaycastMapped", "sourceButtonClickExecutedOnce", "blocksRaycastsRejected",
            "disabledProxyRaycasterRejected", "instancesIsolated", "bakedMeshAssetUnchanged",
            "sourceTreeUnmodified", "pixelReadbackVerified", "maskClippingVerified", "maskStencilMaterialVerified",
            "maskPixelReadback",
        ):
            with self.subTest(observation=observation):
                self.assertIn(observation, self.code)
        self.assertIn("EventSystem.RaycastAll", self.code)
        self.assertIn("ExecuteEvents.Execute", self.code)
        self.assertIn("canvasRenderer.GetMesh()", self.code)
        self.assertIn("MeshDigest(state.bakedMesh)", self.code)
        self.assertIn("FindProxyRaycaster", self.code)
        self.assertNotIn("NativeStaticSortQueueProxyRaycaster", self.code)
        self.assertNotIn(".Register(", self.code)

    def test_probe_is_game_neutral_and_does_not_claim_physical_input(self):
        for forbidden in ("肥鹅", "projects/20-", "Assets/Game", "Mouse.current", "Input.GetMouse"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.code)
        self.assertIn("no physical pointer or device input is claimed", self.code)
        self.assertIn("TMP fallback/multiple material slots are reported only", self.code)

    def test_pinned_old_presenter_is_a_static_only_negative_control(self):
        result = subprocess.run(
            ["git", "show", f"{BASELINE}:src/monkey/targets/NativeStaticSortQueueProxyPresenter.cs"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        old_presenter = result.stdout
        self.assertIn("Canvas.willRenderCanvases += SuppressSources", old_presenter)
        self.assertIn("sourceCanvasRenderer.cull = true", old_presenter)
        self.assertNotIn("CanvasRenderer.GetMesh()", old_presenter)
        self.assertNotIn("CanvasRenderer.SetMesh", old_presenter)
        old_raycaster = subprocess.run(
            ["git", "show", f"{BASELINE}:src/monkey/targets/NativeStaticSortQueueProxyRaycaster.cs"],
            cwd=ROOT, check=False, capture_output=True, text=True,
        )
        self.assertNotEqual(old_raycaster.returncode, 0)


if __name__ == "__main__":
    unittest.main()
