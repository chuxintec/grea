import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTLINE = ROOT / "src/monkey/targets/NativeStaticTextOutline.cs"


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


class PersistentTextOutlineVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = OUTLINE.read_text(encoding="utf-8")

    def test_variant_contract_is_serialized_and_binds_exact_sources_and_style(self):
        self.assertIn("[SerializeField] List<PersistentMaterialVariant> persistentVariants", self.source)
        for field in (
            "TMP_FontAsset font;", "Material material;", "Material parentFontMaterial;",
            "Material sourceFontMaterial;", "Texture atlas;", "float fontSize;",
            "float outlineWidth;", "Color outlineColor;",
        ):
            self.assertIn(field, self.source)
        register = _body(self.source, "public bool RegisterPersistentMaterialVariant(")
        for proof in (
            "target.fontSize != fontSize", "target.font != font", "parentFontMaterial != target.fontSharedMaterial",
            "FontOwnsAtlas(font, atlas)", "HasConfiguredStyle(material, font, fontSize)",
            "row.font == font", "row.sourceFontMaterial == font.material", "row.atlas == atlas",
            "row.outlineWidth == sourceOutlineWidth", "row.outlineColor == sourceOutlineColor",
        ):
            self.assertIn(proof, register)

    def test_runtime_reuses_matching_assets_without_mutation_and_falls_back_on_changed_parameters(self):
        lookup = _body(self.source, "bool TryGetPersistentVariant(")
        for proof in (
            "row.font == font", "row.parentFontMaterial == parentFontMaterial",
            "row.sourceFontMaterial == font.material", "row.atlas == atlas",
            "row.fontSize == target.fontSize", "row.outlineWidth == sourceOutlineWidth",
            "row.outlineColor == sourceOutlineColor", "candidate.GetTexture(\"_MainTex\") != atlas",
            "HasConfiguredStyle(candidate, font, target.fontSize)",
        ):
            self.assertIn(proof, lookup)
        primary = _body(self.source, "void PreparePrimaryMaterialForMesh(")
        apply = _body(self.source, "void Apply(TMP_TextInfo textInfo)")
        self.assertIn("hasPersistentPrimary ? false : ConfigureMaterial", primary)
        self.assertIn("if (!hasPersistentPrimary) primary = GetVariant", primary)
        self.assertIn("if (!hasPersistentFallback) requiresPaddingUpdate |= ConfigureMaterial", apply)
        self.assertIn("if (!hasPersistentFallback) material = GetVariant", apply)
        self.assertIn("public bool ConfigureCaptureCandidate(", self.source)
        selected = _body(self.source, "public bool IsPersistentMaterialVariantSelected(")
        self.assertIn("TryGetPersistentVariant(font, parentFontMaterial, atlas, out var selected)", selected)
        self.assertIn("selected == candidate", selected)

    def test_readonly_runtime_selection_cannot_create_or_destroy_persistent_assets(self):
        self.assertNotIn("using UnityEditor", self.source)
        release = _body(self.source, "void ReleaseVariants(")
        self.assertIn("foreach (var row in variants.Values)", release)
        self.assertNotIn("persistentVariants", release)
        self.assertIn("if (Application.isPlaying) Destroy(row.material)", release)
        owned = _body(self.source, "bool IsOwnedMaterial(")
        self.assertIn("variants.Values", owned)
        self.assertNotIn("persistentVariants", owned)
        self.assertIn("public bool RegisterPersistentMaterialVariant(", self.source)

    def test_capture_helpers_register_only_verified_persistent_owner_and_fallback_materials(self):
        editor_source = (ROOT / "src/monkey/targets/UnityStaticSortTextSource.cs").read_text(encoding="utf-8")
        runtime_source = (ROOT / "src/monkey/targets/NativeStaticSortTextSource.cs").read_text(encoding="utf-8")
        self.assertIn("public bool persistentFallbackVariantRegistered;", runtime_source)
        owner_capture = _body(editor_source, "public static bool CaptureOwnerFontMaterial(")
        self.assertIn("expectedFingerprint != liveFingerprint", owner_capture)
        self.assertIn("outline.RegisterPersistentMaterialVariant(sourceFont, saved, null", owner_capture)
        fallback_capture = _body(editor_source, "public static bool CaptureFallbackMaterial(")
        self.assertIn("outlineDriver.ConfigureCaptureCandidate(profileOutput, fallbackFont", fallback_capture)
        self.assertIn("TMPro.ShaderUtilities.GetPadding(profileOutput, owner.extraPadding, owner.isUsingBold)", fallback_capture)
        self.assertIn("transientFingerprint != sdkFingerprint", fallback_capture)
        self.assertIn("outlineDriver.RegisterPersistentMaterialVariant(fallbackFont, baked, sourceBase", fallback_capture)
        self.assertIn("EditorUtility.SetDirty(outlineDriver)", fallback_capture)

    def test_module_remains_sample_neutral(self):
        self.assertNotIn(".private/", self.source)
        self.assertNotIn("ThirtySamples", self.source)
        self.assertNotRegex(self.source, r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


if __name__ == "__main__":
    unittest.main()
