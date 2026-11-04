from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION = ROOT / "src/monkey/targets/UnitySystemFonts.cs"
RUNTIME_COMPONENT = ROOT / "src/monkey/targets/NativeStaticTextOutline.cs"


def normalized_outline(source_width, font_point_size, label_font_size, gradient_scale):
    return source_width * font_point_size / label_font_size / (gradient_scale - 1)


class UnitySystemFontOutlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = IMPLEMENTATION.read_text(encoding="utf-8")
        cls.runtime = RUNTIME_COMPONENT.read_text(encoding="utf-8")
        cls.method = cls.source.split("public static OutlineReadback ApplySourceOutline", 1)[1].split(
            "public static Readback Import(BindingSet bindingSet, string staticSdfGenerationReceiptPath", 1
        )[0]

    def test_outline_api_is_label_binding_driven_and_not_asset_or_name_special_cased(self):
        self.assertIn("ApplySourceOutline(TMP_Text label, BindingSet bindingSet", self.source)
        self.assertIn("sourceLabelId", self.method)
        self.assertIn("binding.nativeFallbackAssetPaths", self.method)
        self.assertIn("AddComponent<NativeStaticTextOutline>", self.method)
        self.assertIn("component.Configure(label, sourceOutlineWidth, sourceOutlineColor, sourceLabelId)", self.method)
        self.assertIn('serializedOutline.FindProperty("sourceOutlineWidth")', self.method)
        self.assertIn('serializedOutline.FindProperty("sourceOutlineColor")', self.method)
        self.assertIn('native.status == "not_visible_empty_text"', self.method)
        self.assertIn('native.status == "not_visible_empty_text"', self.method)
        self.assertNotIn("55960f08", self.method)
        self.assertNotIn("label_wait", self.method)

    def test_each_actual_glyph_font_uses_its_own_gradient_and_unclamped_source_width(self):
        primary = normalized_outline(4, 90, 36, 10)
        fallback = normalized_outline(4, 90, 36, 65)
        self.assertAlmostEqual(primary, 1.1111111111)
        self.assertAlmostEqual(fallback, 0.15625)
        self.assertIn("font.material.GetFloat(\"_GradientScale\")", self.runtime)
        self.assertIn("sourceOutlineWidth * pointSize / labelFontSize / (gradient - 1f)", self.runtime)
        self.assertNotIn("Mathf.Clamp", self.runtime)
        self.assertIn("TMP_MaterialManager.GetFallbackMaterial", self.runtime)
        self.assertIn("submesh.fontAsset != font", self.runtime)

    def test_glyph_assignment_uses_tmp_reported_face_and_checks_local_glyph_ownership(self):
        self.assertIn("string path = AssetDatabase.GetAssetPath(row.fontAsset)", self.method)
        self.assertIn("allowedPaths.Contains(path, StringComparer.Ordinal)", self.method)
        self.assertIn("row.fontAsset.HasCharacter(unicode)", self.method)
        self.assertNotIn("expectedPath", self.method)
        self.assertIn("TMP's textInfo reports the face it actually selected", self.method)

    def test_face_dilate_comes_from_each_target_face_and_width_and_color_read_back(self):
        self.assertIn('font.material.GetFloat("_FaceDilate")', self.runtime)
        self.assertIn('material.SetFloat("_OutlineWidth", width)', self.runtime)
        self.assertIn('material.SetColor("_OutlineColor", sourceOutlineColor)', self.runtime)
        self.assertIn("normalizedOutlineWidth = width", self.runtime)
        self.assertIn("faceDilate = faceDilate", self.runtime)
        self.assertIn("[ExecuteAlways]", self.runtime)
        self.assertIn("OnPreRenderText += HandlePreRenderText", self.runtime)
        self.assertIn("target.ForceMeshUpdate(true, true)", self.runtime)
        self.assertIn('NotVisible("not_visible_empty_text"', self.runtime)
        self.assertIn("target.ForceMeshUpdate(true, true)", self.runtime)
        self.assertIn('NotVisible("not_visible_empty_text"', self.runtime)
        self.assertNotIn("UnityEditor", self.runtime)

    def test_unity_validation_callbacks_defer_mesh_generation_and_cancel_pending_work(self):
        on_validate = self.runtime.split("void OnValidate()", 1)[1].split("void ScheduleSafeRefresh()", 1)[0]
        on_enable = self.runtime.split("void OnEnable()", 1)[1].split("void OnDisable()", 1)[0]
        late_update = self.runtime.split("void LateUpdate()", 1)[1].split("void BindTarget()", 1)[0]
        configure = self.runtime.split("public void Configure(TMP_Text text, float width, Color color, string sourceLabelId)", 1)[1].split("void OnEnable()", 1)[0]
        for callback in (on_validate, on_enable):
            self.assertNotIn("RefreshNow()", callback)
            self.assertNotIn("ForceMeshUpdate", callback)
        self.assertIn("ScheduleSafeRefresh()", on_validate)
        self.assertIn("ScheduleSafeRefresh()", on_enable)
        self.assertIn("[NonSerialized] bool refreshPending", self.runtime)
        self.assertIn("if (!refreshPending) return", late_update)
        self.assertIn("RefreshNow()", late_update)
        self.assertIn("CancelSafeRefresh()", self.runtime.split("void OnDisable()", 1)[1].split("void OnDestroy()", 1)[0])
        self.assertIn("CancelSafeRefresh()", self.runtime.split("void OnDestroy()", 1)[1].split("void OnValidate()", 1)[0])
        self.assertIn("RefreshNow()", configure)
        self.assertIn("refreshPending = false", self.runtime.split("public Readback RefreshNow()", 1)[1].split("void Apply(TMP_TextInfo", 1)[0])

    def test_primary_and_destroyed_fallback_materials_are_repaired_before_tmp_mesh_generation(self):
        refresh = self.runtime.split("public Readback RefreshNow()", 1)[1].split("void Apply(TMP_TextInfo", 1)[0]
        prepare = self.runtime.split("void PreparePrimaryMaterialForMesh()", 1)[1].split("void Apply(TMP_TextInfo", 1)[0]
        self.assertLess(refresh.index("PreparePrimaryMaterialForMesh()"), refresh.index("target.ForceMeshUpdate(true, true)"))
        self.assertIn("var primary = GetVariant(target.font)", prepare)
        self.assertIn("target.fontSharedMaterial = primary", prepare)
        self.assertIn("NATIVE_STATIC_TEXT_OUTLINE_PRIMARY_MATERIAL_PREPARE_FAILED", refresh)
        self.assertIn("existing.material != null", self.runtime.split("Material GetVariant(", 1)[1].split("bool ConfigureMaterial", 1)[0])
        apply = self.runtime.split("void Apply(TMP_TextInfo", 1)[1].split("Material GetVariant(", 1)[0]
        self.assertIn("baselineSource == null || IsOwnedMaterial(baselineSource)", apply)
        self.assertIn("baselineSource = font.material", apply)
        self.assertIn("baselineFallback = null", apply)

    def test_generated_variants_are_per_font_cached_and_recreated_from_font_baselines(self):
        self.assertIn("readonly Dictionary<TMP_FontAsset, MaterialVariant> variants", self.runtime)
        self.assertIn("font.material", self.runtime)
        self.assertIn("ReleaseVariants()", self.runtime)
        self.assertIn("target.fontSharedMaterial = target.font.material", self.runtime)
        self.assertIn("HideFlags.HideAndDontSave", self.runtime)
        self.assertIn("public void Configure(TMP_Text text, float width, Color color)", self.runtime)
        self.assertIn("[NonSerialized] string diagnosticSourceLabelId", self.runtime)
        self.assertNotIn("sourceText", self.runtime)

    def test_inactive_outline_targets_are_reported_as_non_rendered_not_material_readback(self):
        refresh = self.runtime.split("public Readback RefreshNow()", 1)[1].split("void Apply(TMP_TextInfo", 1)[0]
        inactive_check = refresh.index("!target.enabled || !target.gameObject.activeInHierarchy")
        mesh_update = refresh.index("target.ForceMeshUpdate(true, true)")
        self.assertLess(inactive_check, mesh_update)
        self.assertIn('NotVisible("not_visible_inactive"', refresh)
        self.assertIn("sourceLabelId = diagnosticSourceLabelId", self.runtime)
        self.assertIn("activeInHierarchy=", self.runtime)
        self.assertIn("textInfoCharacters=", self.runtime)
        self.assertIn('native.status == "not_visible_inactive"', self.method)
        self.assertIn("!label.enabled || !label.gameObject.activeInHierarchy", self.method)
        self.assertIn("NATIVE_STATIC_TEXT_OUTLINE_TEXT_INFO_MISSING", self.runtime)


if __name__ == "__main__":
    unittest.main()
