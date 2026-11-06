import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEXT_SOURCE = ROOT / "src/grea/recovery/targets/UnityStaticSortTextSource.cs"
QUEUE_SOURCE = ROOT / "src/grea/recovery/targets/UnityStaticSortQueueProxy.cs"
RUNTIME_SOURCE = ROOT / "src/grea/recovery/targets/NativeStaticSortTextSource.cs"


def _body(source, signature):
    start = source.find(signature)
    if start < 0:
        raise AssertionError(f"missing source API: {signature}")
    opening = source.find("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    raise AssertionError(f"unclosed C# method body: {signature}")


class UnityStaticSortTextRoleRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = TEXT_SOURCE.read_text(encoding="utf-8")
        cls.queue = QUEUE_SOURCE.read_text(encoding="utf-8")
        cls.runtime = RUNTIME_SOURCE.read_text(encoding="utf-8")

    def test_role_classifier_uses_slot_asset_identity_and_exact_atlas_provenance(self):
        classify = _body(self.text, "public static bool TryClassifyCaptureSlotRole(")
        for role in (
            'role = "sprite"', 'role = "primary-font"',
            'role = "fallback-font-same-asset-multi-atlas"',
            '"fallback-font-persistent" : "fallback-font-transient"',
        ):
            self.assertIn(role, classify)
        self.assertIn("row.sourceAssetKind", classify)
        self.assertIn("row.sourceAssetGuid", classify)
        self.assertIn("row.atlasGuid", classify)
        self.assertIn("row.sourceGraphicMaterialGuid", classify)
        self.assertIn('FindProperty("m_AtlasRenderMode")', classify)
        self.assertIn("GlyphRenderMode.RASTER", classify)
        self.assertIn("binding.outlineTargetMatchesOwner", classify)
        self.assertIn("SetDesiredRegistrationRoute(binding)", classify)
        self.assertNotIn("rows[0]", classify)
        self.assertNotIn("sourceComponentId ==", classify)
        self.assertNotIn("sourceComponentId.Contains", classify)

    def test_registration_dispatch_validates_skips_and_only_registers_distinct_fallback_fonts(self):
        register = _body(self.text, "public static bool RegisterCapturedFallbackVariant(")
        self.assertIn("TryClassifyCaptureSlotRole(binding", register)
        self.assertIn("CapturedMaterialIdentityMatches(binding", register)
        self.assertIn("var expectedRequired = RequiresFallbackVariantRegistration(binding)", register)
        self.assertIn("if (!expectedRequired)", register)
        skip = _body(self.text, "static string RegistrationSkipReason(")
        self.assertIn('"primary-font-slot-does-not-use-fallback-variant"', skip)
        self.assertIn('"sprite-slot-does-not-use-font-fallback-variant"', skip)
        self.assertIn('"same-font-multi-atlas-route-does-not-register-fallback-variant"', skip)
        self.assertIn('"outline-driver-absent"', skip)
        self.assertIn("binding.registrationSkipReason != reason", register)
        self.assertIn("binding.fallbackFontAsset == binding.owner.font", register)
        self.assertIn("driver.Target != binding.owner", register)
        self.assertIn("driver.IsPersistentMaterialVariantSelected", register)
        self.assertIn("RequiresFallbackVariantRegistration(binding)", register)
        self.assertNotIn("variant-already-selected-and-verified", register)
        self.assertNotIn("binding.fallbackFontAsset == null ||", register.split("if (!expectedRequired)", 1)[0])
        required = register.split("if (!expectedRequired)", 1)[1]
        early_guard = required.split("var driver =", 1)[0]
        self.assertNotIn("persistentFallbackVariantRegistered", early_guard)
        self.assertLess(required.index("CapturedMaterialIdentityMatches(binding"),
                        required.index("if (binding.persistentFallbackVariantRegistered)"))
        registered = required.split("if (binding.persistentFallbackVariantRegistered)", 1)[1]
        self.assertIn("!binding.requiresPersistentFallbackRegistration", registered)
        self.assertIn('binding.registrationOutcome != "registered"', registered)
        self.assertIn("driver.IsPersistentMaterialVariantSelected", registered)

    def test_fresh_final_slots_copy_origin_role_only_through_pinned_registered_profile_transition(self):
        carry = _body(self.text, "public static bool CarryCaptureSlotRoute(")
        self.assertIn('captured.captureRole == "fallback-font-transient"', carry)
        self.assertIn('current.observedRole == "fallback-font-persistent"', carry)
        self.assertIn("captured.persistentFallbackVariantRegistered", carry)
        self.assertIn("captured.bakedProxyMaterialGuid", carry)
        self.assertIn("finalRow.sourceGraphicMaterialFingerprint == captured.bakedProxyMaterialFingerprint", carry)
        self.assertIn('"transient-to-persistent-registered"', carry)
        self.assertIn("current.captureRole = captured.captureRole", carry)
        self.assertIn("current.registrationDisposition = captured.registrationDisposition", carry)
        queue = _body(self.queue, "static List<TextSlotBinding> CaptureAndRebindTextSlots(")
        self.assertIn("CarryTextCaptureRoutes(captureProofs, firstFinalSlots", queue)
        self.assertIn("CarryTextCaptureRoutes(captureProofs, finalSlots", queue)
        rebind = _body(self.text, "public static bool RebindCapturedSlot(")
        self.assertIn("CarryCaptureSlotRoute(capturedProof, current", rebind)

    def test_lifecycle_records_role_matrix_and_empty_placeholder_skip_reason(self):
        begin = _body(self.text, "public static NativeStaticSortTextCaptureLifecycle BeginCaptureLifecycle(")
        phase = _body(self.text, "static NativeStaticSortTextCaptureSlot CaptureLifecycleSlot(")
        validation = _body(self.text, "static bool EmptySlotRoutesMatch(")
        self.assertIn('"monkey-static-sort-text-slot-role-routing/1"', begin)
        self.assertIn('captureRole = "empty-placeholder"', begin)
        self.assertIn('"empty-placeholder-has-no-drawable-binding"', begin)
        for field in ("captureRole", "observedRole", "roleTransition", "fontAtlasRenderMode",
                      "fontAssetIsRasterBitmap", "generatedSubmesh", "outlineDriverPresent",
                      "outlineTargetMatchesOwner", "registrationDisposition", "registrationOutcome",
                      "registrationSkipReason"):
            self.assertIn(field + " = binding." + field, phase)
        self.assertIn("fallbackAtlasIndex = binding.tmpFallbackAtlasIndex", phase)
        self.assertIn('route.captureRole == "empty-placeholder"', validation)
        self.assertIn('route.registrationDisposition == "not-required"', validation)
        self.assertIn('route.registrationOutcome == "skipped"', validation)

    def test_lifecycle_route_validation_uses_exact_aggregate_and_per_slot_denominators(self):
        routes = _body(self.text, "static bool CaptureLifecycleRoutesMatch(")
        self.assertIn("phase.slot < 0 ? drawableIds : new[] { phase.slot }", routes)
        self.assertIn("actualPhaseSlots.Distinct().Count() != actualPhaseSlots.Length", routes)
        self.assertIn("value.slot < 0 || value.slot == slotId", routes)
        self.assertIn("phase.slot >= 0 && !drawableIds.Contains(phase.slot)", routes)


if __name__ == "__main__":
    unittest.main()
