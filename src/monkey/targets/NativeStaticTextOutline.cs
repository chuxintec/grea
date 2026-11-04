using System;
using System.Collections.Generic;
using System.Linq;
using TMPro;
using UnityEngine;

// Persistent, source-declared TMP outline state for static native previews.
// The component owns only presentation values; it never executes source behavior.
[ExecuteAlways]
[DisallowMultipleComponent]
public sealed class NativeStaticTextOutline : MonoBehaviour
{
    [Serializable]
    public sealed class FaceReadback
    {
        [NonSerialized] public TMP_FontAsset fontAsset;
        public string fontName;
        public string materialName;
        public int[] assignedUnicode;
        public float pointSize;
        public float gradientScale;
        public float faceDilate;
        public float sourceOutlineWidth;
        public float normalizedOutlineWidth;
        public Color outlineColor;
        public bool materialValuesVerified;
    }

    [Serializable]
    public sealed class Readback
    {
        public string status, sourceLabelId;
        public float sourceOutlineWidth;
        public Color sourceOutlineColor;
        public FaceReadback[] faces;
        public string[] diagnostics;
    }

    [SerializeField] TMP_Text target;
    [SerializeField, Min(0f)] float sourceOutlineWidth;
    [SerializeField] Color sourceOutlineColor = Color.black;
    [SerializeField] List<PersistentMaterialVariant> persistentVariants = new List<PersistentMaterialVariant>();

    readonly Dictionary<TMP_FontAsset, MaterialVariant> variants = new Dictionary<TMP_FontAsset, MaterialVariant>();
    readonly Dictionary<TMP_SubMeshUI, SubmeshBaseline> submeshBaselines = new Dictionary<TMP_SubMeshUI, SubmeshBaseline>();
    TMP_Text subscribedTarget;
    [NonSerialized] string diagnosticSourceLabelId;
    bool applying;
    [NonSerialized] bool refreshPending;
    Readback lastReadback = new Readback { status = "not_run" };

    sealed class MaterialVariant
    {
        public TMP_FontAsset font;
        public Material material;
    }

    [Serializable]
    sealed class PersistentMaterialVariant
    {
        public TMP_FontAsset font;
        public Material material;
        public Material parentFontMaterial;
        public Material sourceFontMaterial;
        public Texture atlas;
        public float fontSize;
        public float outlineWidth;
        public Color outlineColor;
    }

    sealed class SubmeshBaseline
    {
        public TMP_SubMeshUI submesh;
        public Material sourceMaterial;
        public Material fallbackMaterial;
    }

    public TMP_Text Target { get { return target; } }
    public float SourceOutlineWidth { get { return sourceOutlineWidth; } }
    public Color SourceOutlineColor { get { return sourceOutlineColor; } }
    public Readback LastReadback { get { return lastReadback; } }

    /// <summary>
    /// Register a verified, owned persistent material produced during capture.
    /// A null parent material identifies the primary face; fallback faces bind
    /// to the exact persistent primary material used to derive TMP's fallback.
    /// Runtime reuse remains gated by every serialized style/resource identity.
    /// </summary>
    public bool RegisterPersistentMaterialVariant(TMP_FontAsset font, Material material,
        Material parentFontMaterial, float fontSize, Texture atlas, out string diagnostic)
    {
        diagnostic = null;
        if (target == null || font == null || font.material == null || material == null || atlas == null ||
            !Finite(fontSize) || fontSize <= 0f || target.fontSize != fontSize ||
            !Finite(sourceOutlineWidth) || sourceOutlineWidth < 0f)
            return FailRegistration("NATIVE_STATIC_TEXT_OUTLINE_PERSISTENT_VARIANT_INPUT_INVALID", out diagnostic);
        if (parentFontMaterial == null)
        {
            if (target.font != font || !FontOwnsAtlas(font, atlas) || material.GetTexture("_MainTex") != atlas)
                return FailRegistration("NATIVE_STATIC_TEXT_OUTLINE_PRIMARY_VARIANT_SOURCE_MISMATCH", out diagnostic);
        }
        else if (parentFontMaterial != target.fontSharedMaterial || target.font == font || !FontOwnsAtlas(font, atlas) ||
                 material.GetTexture("_MainTex") != atlas)
            return FailRegistration("NATIVE_STATIC_TEXT_OUTLINE_FALLBACK_VARIANT_SOURCE_MISMATCH", out diagnostic);
        if (!HasConfiguredStyle(material, font, fontSize))
            return FailRegistration("NATIVE_STATIC_TEXT_OUTLINE_PERSISTENT_VARIANT_STYLE_MISMATCH", out diagnostic);
        if (persistentVariants == null) persistentVariants = new List<PersistentMaterialVariant>();
        var existing = persistentVariants.Find(row => row != null && row.font == font && row.material != null &&
            row.parentFontMaterial == parentFontMaterial && row.sourceFontMaterial == font.material && row.atlas == atlas &&
            row.fontSize == fontSize && row.outlineWidth == sourceOutlineWidth && row.outlineColor == sourceOutlineColor);
        if (existing == null)
        {
            persistentVariants.Add(new PersistentMaterialVariant {
                font = font,
                material = material,
                parentFontMaterial = parentFontMaterial,
                sourceFontMaterial = font.material,
                atlas = atlas,
                fontSize = fontSize,
                outlineWidth = sourceOutlineWidth,
                outlineColor = sourceOutlineColor,
            });
        }
        else if (existing.material != material)
            return FailRegistration("NATIVE_STATIC_TEXT_OUTLINE_PERSISTENT_VARIANT_COLLISION", out diagnostic);
        return true;
    }

    /// <summary>Capture-only style application to a temporary material candidate.</summary>
    public bool ConfigureCaptureCandidate(Material material, TMP_FontAsset font, float fontSize,
        out string diagnostic)
    {
        diagnostic = null;
        if (material == null || font == null || !Finite(fontSize) || fontSize <= 0f)
            return FailRegistration("NATIVE_STATIC_TEXT_OUTLINE_CAPTURE_CANDIDATE_INPUT_INVALID", out diagnostic);
        try
        {
            ConfigureMaterial(material, font, fontSize);
            return true;
        }
        catch (Exception error)
        {
            return FailRegistration("NATIVE_STATIC_TEXT_OUTLINE_CAPTURE_CANDIDATE_CONFIGURE_FAILED:" + error.GetType().Name,
                out diagnostic);
        }
    }

    static bool FontOwnsAtlas(TMP_FontAsset font, Texture atlas)
    {
        return font != null && atlas != null && font.atlasTextures != null && font.atlasTextures.Any(row => row == atlas);
    }

    bool TryGetPersistentVariant(TMP_FontAsset font, Material parentFontMaterial, Texture atlas, out Material material)
    {
        material = null;
        if (persistentVariants == null || target == null || font == null) return false;
        var matches = persistentVariants.Where(row => row != null && row.font == font && row.material != null &&
            row.parentFontMaterial == parentFontMaterial && row.sourceFontMaterial == font.material && row.atlas == atlas &&
            row.fontSize == target.fontSize && row.outlineWidth == sourceOutlineWidth && row.outlineColor == sourceOutlineColor).ToArray();
        if (matches.Length != 1) return false;
        var candidate = matches[0].material;
        if (candidate.GetTexture("_MainTex") != atlas || !HasConfiguredStyle(candidate, font, target.fontSize)) return false;
        material = candidate;
        return true;
    }

    /// <summary>Read-only check that the exact capture-registered variant is selected for this TMP slot.</summary>
    public bool IsPersistentMaterialVariantSelected(TMP_FontAsset font, Material parentFontMaterial,
        Texture atlas, Material candidate)
    {
        return candidate != null && TryGetPersistentVariant(font, parentFontMaterial, atlas, out var selected) &&
            selected == candidate;
    }

    bool HasConfiguredStyle(Material material, TMP_FontAsset font, float labelFontSize)
    {
        if (material == null || font == null || font.material == null ||
            !material.HasProperty("_GradientScale") || !material.HasProperty("_OutlineWidth") ||
            !material.HasProperty("_OutlineColor") || !font.material.HasProperty("_GradientScale")) return false;
        var gradient = font.material.GetFloat("_GradientScale");
        var pointSize = font.faceInfo.pointSize;
        if (!Finite(gradient) || gradient <= 1f || !Finite(pointSize) || pointSize <= 0f || !Finite(labelFontSize) || labelFontSize <= 0f)
            return false;
        var width = sourceOutlineWidth * pointSize / labelFontSize / (gradient - 1f);
        var faceDilate = font.material.HasProperty("_FaceDilate") ? font.material.GetFloat("_FaceDilate") : 0f;
        return Finite(width) && Mathf.Approximately(material.GetFloat("_GradientScale"), gradient) &&
            Mathf.Approximately(material.GetFloat("_OutlineWidth"), width) && material.GetColor("_OutlineColor") == sourceOutlineColor &&
            (!material.HasProperty("_FaceDilate") || Mathf.Approximately(material.GetFloat("_FaceDilate"), faceDilate));
    }

    static bool FailRegistration(string message, out string diagnostic)
    {
        diagnostic = message;
        return false;
    }

    public void Configure(TMP_Text text, float width, Color color)
    {
        Configure(text, width, color, null);
    }

    public void Configure(TMP_Text text, float width, Color color, string sourceLabelId)
    {
        if (text == null) throw new ArgumentNullException(nameof(text));
        if (float.IsNaN(width) || float.IsInfinity(width) || width < 0f)
            throw new ArgumentOutOfRangeException(nameof(width));
        target = text;
        sourceOutlineWidth = width;
        sourceOutlineColor = color;
        diagnosticSourceLabelId = sourceLabelId;
        BindTarget();
        refreshPending = false;
        // Configure is an explicit importer/runtime call, outside Unity's
        // serialization validation callbacks, so its requested readback stays
        // synchronous. OnEnable/OnValidate never call this directly.
        RefreshNow();
    }

    void OnEnable()
    {
        // Do not force TMP mesh generation from a Unity lifecycle callback:
        // TMP may create TMP_SubMeshUI children during deserialization/validation.
        BindTarget();
        ScheduleSafeRefresh();
    }

    void OnDisable()
    {
        CancelSafeRefresh();
        UnbindTarget();
        ReleaseVariants();
    }

    void OnDestroy()
    {
        CancelSafeRefresh();
        UnbindTarget();
        ReleaseVariants();
    }

    void OnValidate()
    {
        // OnValidate can run inside SerializedObject.ApplyModifiedProperties.
        // Only mark work pending; mesh generation/component creation belongs in
        // LateUpdate after Unity has left the serialization consistency scope.
        if (isActiveAndEnabled && target != null) ScheduleSafeRefresh();
    }

    void ScheduleSafeRefresh()
    {
        if (isActiveAndEnabled && target != null) refreshPending = true;
    }

    void CancelSafeRefresh()
    {
        refreshPending = false;
    }

    void LateUpdate()
    {
        if (!refreshPending) return;
        refreshPending = false;
        if (!isActiveAndEnabled || target == null) return;
        BindTarget();
        RefreshNow();
    }

    void BindTarget()
    {
        if (subscribedTarget == target) return;
        UnbindTarget();
        if (target == null) return;
        subscribedTarget = target;
        subscribedTarget.OnPreRenderText += HandlePreRenderText;
    }

    void UnbindTarget()
    {
        if (subscribedTarget != null)
            subscribedTarget.OnPreRenderText -= HandlePreRenderText;
        subscribedTarget = null;
    }

    void HandlePreRenderText(TMP_TextInfo textInfo)
    {
        Apply(textInfo);
    }

    public Readback RefreshNow()
    {
        refreshPending = false;
        if (target == null)
        {
            lastReadback = Failure("NATIVE_STATIC_TEXT_OUTLINE_TARGET_MISSING");
            return lastReadback;
        }
        BindTarget();
        // TMP does not initialize inactive TextMeshProUGUI objects just because
        // ForceMeshUpdate(ignoreActiveState:true) was called: inactive objects
        // may not have run Awake and OnPreRenderCanvas returns without building
        // textInfo. Preserve their explicit inactive outline state without
        // pretending that glyph material values were rendered/read back.
        if (!target.enabled || !target.gameObject.activeInHierarchy)
        {
            lastReadback = NotVisible("not_visible_inactive",
                "Outline target is disabled or outside the active hierarchy; no glyph geometry was requested.");
            return lastReadback;
        }
        if (string.IsNullOrEmpty(target.text))
        {
            lastReadback = NotVisible("not_visible_empty_text",
                "Empty source text has no glyph geometry; serialized outline inputs were retained.");
            return lastReadback;
        }
        try
        {
            // Imported or cloned TMP labels can carry a serialized reference to
            // the source label's HideAndDontSave variant. That material is owned
            // by the old component and may already have been destroyed. TMP
            // resolves fallback materials while sizing arrays in ForceMeshUpdate,
            // before HandlePreRenderText/Apply can repair the assignment. Give
            // this component a live primary variant first.
            PreparePrimaryMaterialForMesh();
        }
        catch (Exception exception)
        {
            lastReadback = Failure("NATIVE_STATIC_TEXT_OUTLINE_PRIMARY_MATERIAL_PREPARE_FAILED: "
                + exception.GetType().Name);
            return lastReadback;
        }
        target.ForceMeshUpdate(true, true);
        // The callback normally runs during ForceMeshUpdate. Applying once more
        // guarantees a deterministic readback even when TMP skips unchanged text.
        Apply(target.textInfo);
        return lastReadback;
    }

    void PreparePrimaryMaterialForMesh()
    {
        if (target == null || target.font == null)
            throw new InvalidOperationException("NATIVE_STATIC_TEXT_OUTLINE_TEXT_UNAVAILABLE");
        var primaryAtlas = target.font.material == null ? null : target.font.material.GetTexture("_MainTex");
        var hasPersistentPrimary = TryGetPersistentVariant(target.font, null, primaryAtlas, out var primary);
        if (!hasPersistentPrimary) primary = GetVariant(target.font);
        bool requiresPaddingUpdate = hasPersistentPrimary ? false : ConfigureMaterial(primary, target.font, target.fontSize);
        if (target.fontSharedMaterial != primary)
        {
            target.fontSharedMaterial = primary;
            requiresPaddingUpdate = true;
        }

        if (requiresPaddingUpdate) target.UpdateMeshPadding();
    }

    void Apply(TMP_TextInfo textInfo)
    {
        if (applying) return;
        applying = true;
        try
        {
            if (target == null || target.font == null)
            {
                lastReadback = Failure("NATIVE_STATIC_TEXT_OUTLINE_TEXT_UNAVAILABLE");
                return;
            }
            if (string.IsNullOrEmpty(target.text))
            {
                lastReadback = NotVisible("not_visible_empty_text",
                    "Empty source text has no glyph geometry; serialized outline inputs were retained.");
                return;
            }
            if (!target.enabled || !target.gameObject.activeInHierarchy)
            {
                lastReadback = NotVisible("not_visible_inactive",
                    "Outline target is disabled or outside the active hierarchy; no glyph geometry was requested.");
                return;
            }
            if (textInfo == null || textInfo.characterCount <= 0)
            {
                lastReadback = Failure("NATIVE_STATIC_TEXT_OUTLINE_TEXT_INFO_MISSING");
                return;
            }
            float fontSize = target.fontSize;
            if (!Finite(fontSize) || fontSize <= 0f || !Finite(sourceOutlineWidth) || sourceOutlineWidth < 0f)
            {
                lastReadback = Failure("NATIVE_STATIC_TEXT_OUTLINE_METRICS_INVALID");
                return;
            }

            var assigned = new Dictionary<TMP_FontAsset, SortedSet<int>>();
            for (int i = 0; i < textInfo.characterCount; i++)
            {
                var character = textInfo.characterInfo[i];
                int unicode = character.textElement == null
                    ? char.ConvertToUtf32(character.character.ToString(), 0)
                    : checked((int)character.textElement.unicode);
                if (unicode == '\n' || unicode == '\r' || unicode == '\t') continue;
                var font = character.fontAsset;
                if (font == null)
                {
                    lastReadback = Failure("NATIVE_STATIC_TEXT_OUTLINE_GLYPH_FONT_MISSING_U+" + unicode.ToString("X4"));
                    return;
                }
                if (!assigned.TryGetValue(font, out var scalars))
                    assigned.Add(font, scalars = new SortedSet<int>());
                scalars.Add(unicode);
            }
            if (assigned.Count == 0)
            {
                lastReadback = Failure("NATIVE_STATIC_TEXT_OUTLINE_NO_RENDERED_GLYPHS");
                return;
            }

            // Build the primary material first. TMP's fallback material manager uses
            // this as the source style while taking atlas and gradient from each face.
            var primaryAtlas = target.font.material == null ? null : target.font.material.GetTexture("_MainTex");
            var hasPersistentPrimary = TryGetPersistentVariant(target.font, null, primaryAtlas, out var primary);
            if (!hasPersistentPrimary) primary = GetVariant(target.font);
            bool requiresPaddingUpdate = hasPersistentPrimary ? false : ConfigureMaterial(primary, target.font, fontSize);
            if (target.fontSharedMaterial != primary)
            {
                target.fontSharedMaterial = primary;
                requiresPaddingUpdate = true;
            }

            var rows = new List<FaceReadback>();
            foreach (var entry in assigned)
            {
                var font = entry.Key;
                if (font == null)
                {
                    lastReadback = Failure("NATIVE_STATIC_TEXT_OUTLINE_FONT_LOOKUP_FAILED");
                    return;
                }
                Material material;
                if (font == target.font)
                {
                    material = primary;
                }
                else
                {
                    var fallbackTemplate = TMP_MaterialManager.GetFallbackMaterial(primary, font.material);
                    if (fallbackTemplate == null)
                    {
                        lastReadback = Failure("NATIVE_STATIC_TEXT_OUTLINE_FALLBACK_MATERIAL_MISSING: " + font.name);
                        return;
                    }
                    var fallbackAtlas = fallbackTemplate.GetTexture("_MainTex");
                    var hasPersistentFallback = TryGetPersistentVariant(font, primary, fallbackAtlas, out material);
                    if (!hasPersistentFallback) material = GetVariant(font, fallbackTemplate);
                    if (!hasPersistentFallback) requiresPaddingUpdate |= ConfigureMaterial(material, font, fontSize);
                    var submeshes = target.GetComponentsInChildren<TMP_SubMeshUI>(true);
                    bool found = false;
                    foreach (var submesh in submeshes)
                    {
                        if (submesh == null || submesh.fontAsset != font) continue;
                        if (!submeshBaselines.ContainsKey(submesh))
                        {
                            var baselineSource = submesh.fallbackSourceMaterial;
                            var baselineFallback = submesh.fallbackMaterial;
                            // A cloned TMP submesh can deserialize references to
                            // the source component's owned (or already destroyed)
                            // materials. Never restore those references after this
                            // component releases its variants.
                            if (baselineSource == null || IsOwnedMaterial(baselineSource))
                            {
                                baselineSource = font.material;
                                baselineFallback = null;
                            }
                            submeshBaselines.Add(submesh, new SubmeshBaseline {
                                submesh = submesh,
                                sourceMaterial = baselineSource,
                                fallbackMaterial = baselineFallback,
                            });
                        }
                        if (submesh.fallbackSourceMaterial != primary || submesh.fallbackMaterial != material)
                        {
                            submesh.fallbackSourceMaterial = primary;
                            submesh.fallbackMaterial = material;
                            requiresPaddingUpdate = true;
                        }
                        if (submesh.fallbackMaterial != material)
                        {
                            lastReadback = Failure("NATIVE_STATIC_TEXT_OUTLINE_FALLBACK_MATERIAL_READBACK_MISMATCH: " + font.name);
                            return;
                        }
                        found = true;
                    }
                    if (!found)
                    {
                        lastReadback = Failure("NATIVE_STATIC_TEXT_OUTLINE_FALLBACK_SUBMESH_MISSING: " + font.name);
                        return;
                    }
                }
                rows.Add(ReadFace(font, material, entry.Value));
            }
            if (requiresPaddingUpdate) target.UpdateMeshPadding();
            lastReadback = new Readback {
                status = rows.TrueForAll(row => row.materialValuesVerified)
                    ? "material_values_applied_and_read_back" : "partial",
                sourceLabelId = diagnosticSourceLabelId,
                sourceOutlineWidth = sourceOutlineWidth,
                sourceOutlineColor = sourceOutlineColor,
                faces = rows.ToArray(),
                diagnostics = Array.Empty<string>(),
            };
        }
        catch (Exception exception)
        {
            lastReadback = Failure("NATIVE_STATIC_TEXT_OUTLINE_APPLY_FAILED: " + exception.GetType().Name);
        }
        finally
        {
            applying = false;
        }
    }

    Material GetVariant(TMP_FontAsset font, Material fallbackTemplate = null)
    {
        if (variants.TryGetValue(font, out var existing) && existing.font == font && existing.material != null)
            return existing.material;
        var source = fallbackTemplate != null ? fallbackTemplate : font.material;
        if (source == null) throw new InvalidOperationException("NATIVE_STATIC_TEXT_OUTLINE_FONT_MATERIAL_MISSING");
        var material = new Material(source) { name = source.name + " [native-static-outline]", hideFlags = HideFlags.HideAndDontSave };
        variants[font] = new MaterialVariant { font = font, material = material };
        return material;
    }

    bool ConfigureMaterial(Material material, TMP_FontAsset font, float labelFontSize)
    {
        if (font == null || font.material == null || material == null
            || !material.HasProperty("_GradientScale") || !material.HasProperty("_OutlineWidth")
            || !material.HasProperty("_OutlineColor"))
            throw new InvalidOperationException("NATIVE_STATIC_TEXT_OUTLINE_SHADER_PROPERTIES_MISSING");
        float gradient = font.material.GetFloat("_GradientScale");
        float pointSize = font.faceInfo.pointSize;
        if (!Finite(gradient) || gradient <= 1f || !Finite(pointSize) || pointSize <= 0f)
            throw new InvalidOperationException("NATIVE_STATIC_TEXT_OUTLINE_FONT_METRICS_INVALID");
        float width = sourceOutlineWidth * pointSize / labelFontSize / (gradient - 1f);
        float faceDilate = font.material.HasProperty("_FaceDilate") ? font.material.GetFloat("_FaceDilate") : 0f;
        bool changed = !Mathf.Approximately(material.GetFloat("_OutlineWidth"), width)
            || !Mathf.Approximately(material.GetFloat("_GradientScale"), gradient)
            || material.GetColor("_OutlineColor") != sourceOutlineColor
            || (material.HasProperty("_FaceDilate") && !Mathf.Approximately(material.GetFloat("_FaceDilate"), faceDilate));
        if (!Mathf.Approximately(material.GetFloat("_OutlineWidth"), width)) material.SetFloat("_OutlineWidth", width);
        if (material.GetColor("_OutlineColor") != sourceOutlineColor) material.SetColor("_OutlineColor", sourceOutlineColor);
        if (material.HasProperty("_FaceDilate") && !Mathf.Approximately(material.GetFloat("_FaceDilate"), faceDilate))
            material.SetFloat("_FaceDilate", faceDilate);
        // A fallback variant must keep its own atlas/range even after the manager
        // copies primary style properties onto it.
        if (!Mathf.Approximately(material.GetFloat("_GradientScale"), gradient)) material.SetFloat("_GradientScale", gradient);
        if (!Mathf.Approximately(material.GetFloat("_OutlineWidth"), width)
            || !Mathf.Approximately(material.GetFloat("_GradientScale"), gradient)
            || material.GetColor("_OutlineColor") != sourceOutlineColor
            || (material.HasProperty("_FaceDilate") && !Mathf.Approximately(material.GetFloat("_FaceDilate"), faceDilate)))
            throw new InvalidOperationException("NATIVE_STATIC_TEXT_OUTLINE_MATERIAL_READBACK_MISMATCH");
        return changed;
    }

    FaceReadback ReadFace(TMP_FontAsset font, Material material, SortedSet<int> assignedUnicode)
    {
        float gradient = font.material.GetFloat("_GradientScale");
        float pointSize = font.faceInfo.pointSize;
        float faceDilate = font.material.HasProperty("_FaceDilate") ? font.material.GetFloat("_FaceDilate") : 0f;
        float width = sourceOutlineWidth * pointSize / target.fontSize / (gradient - 1f);
        return new FaceReadback {
            fontAsset = font,
            fontName = font.name,
            materialName = material.name,
            assignedUnicode = new List<int>(assignedUnicode).ToArray(),
            pointSize = pointSize,
            gradientScale = gradient,
            faceDilate = faceDilate,
            sourceOutlineWidth = sourceOutlineWidth,
            normalizedOutlineWidth = width,
            outlineColor = sourceOutlineColor,
            materialValuesVerified = Mathf.Approximately(material.GetFloat("_GradientScale"), gradient)
                && Mathf.Approximately(material.GetFloat("_OutlineWidth"), width)
                && material.GetColor("_OutlineColor") == sourceOutlineColor
                && (!material.HasProperty("_FaceDilate")
                    || Mathf.Approximately(material.GetFloat("_FaceDilate"), faceDilate)),
        };
    }

    Readback Failure(string diagnostic)
    {
        return new Readback {
            status = "failed",
            sourceLabelId = diagnosticSourceLabelId,
            sourceOutlineWidth = sourceOutlineWidth,
            sourceOutlineColor = sourceOutlineColor,
            faces = Array.Empty<FaceReadback>(),
            diagnostics = new[] { diagnostic + ContextDiagnostic() },
        };
    }

    Readback NotVisible(string status, string reason)
    {
        return new Readback {
            status = status,
            sourceLabelId = diagnosticSourceLabelId,
            sourceOutlineWidth = sourceOutlineWidth,
            sourceOutlineColor = sourceOutlineColor,
            faces = Array.Empty<FaceReadback>(),
            diagnostics = new[] { reason + ContextDiagnostic() },
        };
    }

    string ContextDiagnostic()
    {
        if (target == null) return " [sourceLabel=" + (diagnosticSourceLabelId ?? "unknown") + "; target=null]";
        int length = target.text == null ? 0 : target.text.Length;
        int characterCount = target.textInfo == null ? -1 : target.textInfo.characterCount;
        return " [sourceLabel=" + (diagnosticSourceLabelId ?? "unknown")
            + "; textLength=" + length
            + "; textInfoCharacters=" + characterCount
            + "; enabled=" + target.enabled
            + "; activeSelf=" + target.gameObject.activeSelf
            + "; activeInHierarchy=" + target.gameObject.activeInHierarchy
            + "; richText=" + target.richText
            + "; maxVisibleCharacters=" + target.maxVisibleCharacters
            + "; colorAlpha=" + target.color.a + "]";
    }

    void ReleaseVariants()
    {
        foreach (var baseline in submeshBaselines.Values)
            if (baseline.submesh != null && IsOwnedMaterial(baseline.submesh.fallbackMaterial))
            {
                baseline.submesh.fallbackSourceMaterial = baseline.sourceMaterial;
                baseline.submesh.fallbackMaterial = baseline.fallbackMaterial;
            }
        submeshBaselines.Clear();
        if (target != null && target.font != null && IsOwnedMaterial(target.fontSharedMaterial))
            target.fontSharedMaterial = target.font.material;
        foreach (var row in variants.Values)
            if (row.material != null)
            {
                if (Application.isPlaying) Destroy(row.material);
                else DestroyImmediate(row.material);
            }
        variants.Clear();
    }

    bool IsOwnedMaterial(Material material)
    {
        if (material == null) return false;
        foreach (var row in variants.Values)
            if (row.material == material) return true;
        return false;
    }

    static bool Finite(float value) { return !float.IsNaN(value) && !float.IsInfinity(value); }
}
