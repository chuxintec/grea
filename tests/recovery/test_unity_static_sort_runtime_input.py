"""Static contract checks for proxy-to-source EventSystem raycasting.

These assertions inspect source structure only. They do not compile Unity code
or establish native Pointer, Drag, Scroll, Canvas-filter, or sorting behavior.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
RAYCASTER = ROOT / "src/grea/recovery/targets/NativeStaticSortQueueProxyRaycaster.cs"
INPUT_SURFACE = ROOT / "src/grea/recovery/targets/NativeStaticSortInputSurface.cs"


class UnityStaticSortRuntimeInputContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = RAYCASTER.read_text(encoding="utf-8")

    def test_register_requires_runtime_and_one_existing_active_canvas_raycaster(self):
        register = self.source.split("public static bool Register(", 1)[1].split(
            "/// <summary>Remove a presenter's", 1
        )[0]
        self.assertIn("!Application.isPlaying", register)
        self.assertIn("canvas.GetComponents<GraphicRaycaster>()", register)
        self.assertIn("activeSources.Length != 1", register)
        self.assertIn("CopySettings(settingsSources[canvas])", register)
        self.assertIn("registered.settingsSource != activeSources[0]", register)

    def test_only_registered_proxy_graphics_are_temporarily_raycastable(self):
        raycast = self.source.split("public override void Raycast(", 1)[1].split(
            "void CopySettings(", 1
        )[0]
        self.assertIn("registry.presenters.Values", raycast)
        self.assertIn("proxy.raycastTarget = true", raycast)
        self.assertIn("base.Raycast(eventData, proxyHits)", raycast)
        self.assertIn("finally", raycast)
        self.assertIn("entry.Key.raycastTarget = entry.Value", raycast)
        self.assertIn("raycastInProgress", raycast)

    def test_hits_require_live_source_and_ancestor_aware_source_raycast_then_map_back(self):
        raycast = self.source.split("public override void Raycast(", 1)[1].split(
            "void CopySettings(", 1
        )[0]
        self.assertIn("TryGetEligibleTarget(source, eventData.position, eventCamera, out var target)", raycast)
        self.assertIn("seenSources.Add(target)", raycast)
        self.assertIn("mappedHit.gameObject = target", raycast)
        eligibility = self.source.split("static bool TryGetEligibleTarget(", 1)[1]
        self.assertIn("source.enabled", eligibility)
        self.assertIn("source.gameObject.activeInHierarchy", eligibility)
        self.assertIn("source.raycastTarget", eligibility)
        self.assertIn("source.Raycast(screenPosition, camera)", eligibility)

    def test_typed_selectable_input_surface_maps_to_owner_without_event_simulation(self):
        raycast = self.source.split("static bool TryGetEligibleTarget(", 1)[1]
        self.assertIn("source as NativeStaticSortInputSurface", raycast)
        self.assertIn("inputSurface.owner.isActiveAndEnabled", raycast)
        self.assertIn("target = inputSurface.owner.gameObject", raycast)
        self.assertNotIn("owner.interactable", raycast)
        self.assertNotIn("ExecuteEvents", self.source)
        self.assertNotIn("ExecuteEvents", INPUT_SURFACE.read_text(encoding="utf-8"))

    def test_transparent_input_surface_keeps_quad_raycastable_and_owner_nonserialized(self):
        surface = INPUT_SURFACE.read_text(encoding="utf-8")
        self.assertIn("[NonSerialized] public Selectable owner", surface)
        self.assertIn("canvasRenderer.cullTransparentMesh = false", surface)
        self.assertIn("new Color32(0, 0, 0, 0)", surface)
        self.assertIn("helper.AddTriangle(0, 1, 2)", surface)
        self.assertIn("helper.AddTriangle(2, 3, 0)", surface)
        self.assertNotIn("raycastTarget =", surface)

    def test_only_mirrored_display_families_and_typed_input_surfaces_are_accepted(self):
        supported = self.source.split("static bool IsSupportedSource(", 1)[1]
        self.assertIn("source is Image", supported)
        self.assertIn("source is TMPro.TextMeshProUGUI", supported)
        self.assertIn("source is NativeStaticSortInputSurface", supported)
        self.assertNotIn("NativeInputBlocker", supported)
        raycast = self.source.split("public override void Raycast(", 1)[1].split(
            "void CopySettings(", 1
        )[0]
        self.assertIn("!proxySources.TryGetValue(proxy, out var source)", raycast)
        self.assertIn("source.rectTransform", self.source)
        self.assertIn("RectTransformUtility.RectangleContainsScreenPoint", self.source)

    def test_cleanup_only_destroys_component_created_by_this_module(self):
        cleanup = self.source.split("public static void Unregister(", 1)[1].split(
            "static void DestroyUnusedRegistry(", 1
        )[0]
        self.assertIn("DestroyUnusedRegistry(pair.Key, registry)", cleanup)
        destroy_unused = self.source.split("static void DestroyUnusedRegistry(", 1)[1].split(
            "protected override void OnDisable()", 1
        )[0]
        self.assertIn("registry.ownsRaycaster", destroy_unused)
        self.assertIn("registry.raycaster.enabled = false", destroy_unused)
        destroy = self.source.split("static IEnumerator DestroyUnusedAfterFrame(", 1)[1].split(
            "public override void Raycast(", 1
        )[0]
        self.assertIn("Object.Destroy(registry.raycaster)", destroy)
        self.assertIn("registry.ownsRaycaster", destroy)

    def test_disable_keeps_registry_and_same_frame_reregister_cancels_deferred_cleanup(self):
        on_disable = self.source.split("protected override void OnDisable()", 1)[1].split(
            "static IEnumerator DestroyUnusedAfterFrame(", 1
        )[0]
        self.assertIn("base.OnDisable()", on_disable)
        self.assertNotIn("Registries.Remove", on_disable)
        self.assertNotIn("Destroy(", on_disable)
        register = self.source.split("public static bool Register(", 1)[1].split(
            "/// <summary>Remove a presenter's", 1
        )[0]
        self.assertIn("registry.pendingDestroy = false", register)
        self.assertIn("registry.raycaster.enabled = true", register)
        deferred = self.source.split("static IEnumerator DestroyUnusedAfterFrame(", 1)[1].split(
            "public override void Raycast(", 1
        )[0]
        self.assertIn("yield return null", deferred)
        self.assertIn("registry.lifecycleVersion != generation", deferred)
        self.assertIn("!registry.pendingDestroy", deferred)
        self.assertIn("registry.presenters.Count != 0", deferred)
        self.assertIn("registry.lifecycleVersion++", register)

    def test_owned_runtime_raycaster_is_marked_nonsave_and_unknown_disabled_component_is_not_enabled(self):
        self.assertIn("raycaster.hideFlags |= HideFlags.DontSave", self.source)
        register = self.source.split("public static bool Register(", 1)[1].split(
            "/// <summary>Remove a presenter's", 1
        )[0]
        self.assertIn("!ownRaycaster.enabled && !IsOwnedRuntimeRaycaster(ownRaycaster)", register)
        ownership = self.source.split("static bool IsOwnedRuntimeRaycaster(", 1)[1]
        self.assertIn("HideFlags.DontSave", ownership)

    def test_each_raycast_revalidates_unique_settings_owner_and_refreshes_its_latest_values(self):
        raycast = self.source.split("public override void Raycast(", 1)[1].split(
            "void CopySettings(", 1
        )[0]
        self.assertIn("!TryRefreshSettingsSource(registry)", raycast)
        refresh = self.source.split("bool TryRefreshSettingsSource(", 1)[1].split(
            "static bool IsSupportedSource(", 1
        )[0]
        self.assertIn("activeSources.Length != 1", refresh)
        self.assertIn("activeSources[0] != registry.settingsSource", refresh)
        self.assertIn("CopySettings(registry.settingsSource)", refresh)

    def test_play_session_reset_discards_static_registrations_without_destroying_unknown_objects(self):
        reset = self.source.split("static void ResetRegistriesForPlaySession()", 1)[1].split(
            "/// <summary>", 1
        )[0]
        self.assertIn("RuntimeInitializeLoadType.SubsystemRegistration", self.source)
        self.assertIn("Registries.Clear()", reset)
        self.assertNotIn("Destroy", reset)


if __name__ == "__main__":
    unittest.main()
