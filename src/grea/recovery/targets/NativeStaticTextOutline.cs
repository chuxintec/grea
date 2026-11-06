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
    [SerializeField] bool pairedRendering;
    [SerializeField] TMP_FontAsset strokeFont;
    [NonSerialized] NativeStaticTextOutline strokeDriver;
    [SerializeField, HideInInspector] bool isStrokePass;
    [SerializeField, HideInInspector] NativeStaticTextOutline faceDriver;
    public bool UsesPairedRendering => pairedRendering;
    public bool IsGeneratedStrokePass => isStrokePass;
    public TMP_Text StrokeTarget => strokeDriver == null ? null : strokeDriver.target;

    public void ConfigurePaired(TMP_Text face, float width, Color color, string sourceLabelId, TMP_FontAsset expandedStrokeFont = null)
    {
        if (!pairedRendering) { UnbindTarget(); ReleaseVariants(); }
        pairedRendering = true;
        strokeFont = expandedStrokeFont;
        Configure(face, width, color, sourceLabelId);
    }

    // Only a renderer owned by this exact live pair is derived presentation.
    // Names alone never exempt arbitrary source nodes from hierarchy checks.
    public static bool IsGeneratedStroke(Transform candidate)
    {
        var driver = candidate == null ? null : candidate.GetComponent<NativeStaticTextOutline>();
        return driver != null && driver.isStrokePass && driver.faceDriver != null &&
            driver.faceDriver.pairedRendering && driver.faceDriver.target != null &&
            candidate.parent == driver.faceDriver.target.transform.parent &&
            driver.target != null && driver.target.transform == candidate &&
            (candidate.gameObject.hideFlags & HideFlags.DontSave) == HideFlags.DontSave;
    }

    void RemoveStroke()
    {
        if (strokeDriver == null) return;
        var layer = strokeDriver.gameObject;
        strokeDriver = null;
        layer.SetActive(false);
        if (Application.isPlaying) Destroy(layer); else DestroyImmediate(layer);
    }

    bool syncingPair;
    Readback RefreshPair(bool refreshFace = true)
    {
        if (syncingPair) return lastReadback;
        syncingPair = true;
        try { return RefreshPairCore(refreshFace); }
        finally { syncingPair = false; }
    }

    Readback RefreshPairCore(bool refreshFace)
    {
        var face = target as TextMeshProUGUI;
        if (face == null) return Failure("NATIVE_TEXT_OUTLINE_FACE_MISSING");
        if (!isActiveAndEnabled || !face.isActiveAndEnabled || face.transform.parent == null)
        {
            RemoveStroke();
            return NotVisible("not_visible_inactive", "Outline target is inactive or unmounted.");
        }
        if (string.IsNullOrEmpty(face.text))
        {
            RemoveStroke();
            return NotVisible("not_visible_empty_text", "Empty source text has no stroke geometry.");
        }
        if (sourceOutlineWidth == 0 || sourceOutlineColor.a == 0)
        {
            RemoveStroke();
            return NotVisible("not_visible_zero_coverage", "Zero width or transparent source stroke.");
        }
        var parent = face.rectTransform.parent;
        if (strokeDriver == null)
            strokeDriver = Enumerable.Range(0, parent.childCount).Select(parent.GetChild)
                .Select(child => child.GetComponent<NativeStaticTextOutline>())
                .FirstOrDefault(driver => driver != null && driver.isStrokePass && driver.faceDriver == this);
        if (strokeDriver == null)
        {
            var layer = new GameObject("Native TMP Stroke", typeof(RectTransform));
            layer.hideFlags = HideFlags.DontSave;
            layer.SetActive(false);
            layer.transform.SetParent(parent, false);
            layer.AddComponent<UnityEngine.UI.LayoutElement>().ignoreLayout = true;
            var renderer = layer.AddComponent<TextMeshProUGUI>();
            renderer.raycastTarget = false;
            strokeDriver = layer.AddComponent<NativeStaticTextOutline>();
            strokeDriver.isStrokePass = true;
            strokeDriver.faceDriver = this;
            strokeDriver.target = renderer;
            layer.SetActive(true);
        }
        var stroke = (TextMeshProUGUI)strokeDriver.target;
        stroke.enabled = true;
        if (stroke.transform.parent != parent) stroke.transform.SetParent(parent, false);
        int faceIndex = face.transform.GetSiblingIndex();
        int current = stroke.transform.GetSiblingIndex();
        if (current != faceIndex - 1) stroke.transform.SetSiblingIndex(current < faceIndex ? faceIndex - 1 : faceIndex);
        stroke.gameObject.layer = face.gameObject.layer;
        // A sibling shares ancestor opacity, but needs the face node's own
        // CanvasGroup opacity and ignore-parent boundary explicitly mirrored.
        var opacity = stroke.GetComponent<CanvasGroup>();
        if (opacity == null) opacity = stroke.gameObject.AddComponent<CanvasGroup>();
        opacity.alpha = 1f; opacity.ignoreParentGroups = false;
        opacity.interactable = false; opacity.blocksRaycasts = false;
        foreach (var group in face.GetComponents<CanvasGroup>())
            if (group.enabled) { opacity.alpha *= group.alpha; opacity.ignoreParentGroups |= group.ignoreParentGroups; }
        var from = face.rectTransform; var to = stroke.rectTransform;
        to.anchorMin = from.anchorMin; to.anchorMax = from.anchorMax; to.pivot = from.pivot;
        to.sizeDelta = from.sizeDelta; to.anchoredPosition3D = from.anchoredPosition3D;
        to.localRotation = from.localRotation; to.localScale = from.localScale;
        // Force the original face first so auto sizing and fallback selection
        // are sampled at the same layout state, without changing its material.
        if (refreshFace) face.ForceMeshUpdate(true, true);
        stroke.font = strokeFont != null ? strokeFont : face.font; stroke.fontSize = face.fontSize;
        stroke.fontStyle = face.fontStyle; stroke.text = face.text;
        stroke.textPreprocessor = face.textPreprocessor;
        stroke.richText = face.richText; stroke.overrideColorTags = true;
        stroke.enableVertexGradient = false; stroke.color = new Color(sourceOutlineColor.r, sourceOutlineColor.g,
            sourceOutlineColor.b, sourceOutlineColor.a * face.color.a);
        stroke.alignment = face.alignment; stroke.margin = face.margin; stroke.overflowMode = face.overflowMode;
        stroke.textWrappingMode = face.textWrappingMode; stroke.maskable = face.maskable;
        stroke.enableAutoSizing = false; stroke.fontSizeMin = face.fontSizeMin; stroke.fontSizeMax = face.fontSizeMax;
        stroke.lineSpacing = face.lineSpacing; stroke.characterSpacing = face.characterSpacing;
        stroke.wordSpacing = face.wordSpacing; stroke.paragraphSpacing = face.paragraphSpacing;
        // Stroke opacity lives in vertex alpha once. The material outline
        // inherits that alpha in the stock shader.
        strokeDriver.sourceOutlineColor = new Color(sourceOutlineColor.r,sourceOutlineColor.g,sourceOutlineColor.b,1);
        strokeDriver.sourceOutlineWidth = sourceOutlineWidth; strokeDriver.diagnosticSourceLabelId = diagnosticSourceLabelId;
        var result = strokeDriver.RefreshNow();
        // The layer can be created during its owner's Canvas rebuild. TMP's
        // ForceMeshUpdate generates geometry but does not submit the primary
        // Canvas material in that case; explicitly complete its native rebuild.
        stroke.SetMaterialDirty();
        stroke.Rebuild(UnityEngine.UI.CanvasUpdate.PreRender);
        stroke.raycastTarget = false;
        foreach (var sub in stroke.GetComponentsInChildren<TMP_SubMeshUI>(true)) sub.raycastTarget = false;
        result.sourceOutlineColor = sourceOutlineColor;
        return result;
    }
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
        var width = OutlineWidth(font, material, sourceOutlineWidth, labelFontSize);
        var faceDilate = OutlineFaceDilate(font, material, width);
        return OutlineVariantMatches(material, width) && Finite(width) && Mathf.Approximately(material.GetFloat("_GradientScale"), gradient) &&
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
        if (pairedRendering && target != null && target.transform.parent != null)
            strokeDriver = Enumerable.Range(0, target.transform.parent.childCount).Select(target.transform.parent.GetChild)
                .Select(child => child.GetComponent<NativeStaticTextOutline>())
                .FirstOrDefault(driver => driver != null && driver.isStrokePass && driver.faceDriver == this);
        BindTarget();
        ScheduleSafeRefresh();
    }

    void OnDisable()
    {
        // Unity forbids destroying siblings during parent activation/teardown.
        // Hide immediately and retain the owned layer for a later safe refresh.
        if (strokeDriver != null && strokeDriver.target != null) strokeDriver.target.enabled = false;
        CancelSafeRefresh();
        UnbindTarget();
        ReleaseVariants();
    }

    void OnDestroy()
    {
        if (strokeDriver != null)
        {
            var layer = strokeDriver.gameObject;
            strokeDriver = null;
            if (Application.isPlaying) Destroy(layer);
#if UNITY_EDITOR
            else UnityEditor.EditorApplication.delayCall += () => { if (layer != null) DestroyImmediate(layer); };
#endif
        }
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
        if (pairedRendering && isActiveAndEnabled && target != null)
        {
            lastReadback = RefreshPair();
            return;
        }
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
        if (pairedRendering) { lastReadback = RefreshPair(false); return; }
        Apply(textInfo);
    }

    public Readback RefreshNow()
    {
        refreshPending = false;
        if (pairedRendering) return lastReadback = RefreshPair();
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

    static bool UsesGeneratedDistanceAtlas(TMP_FontAsset font, Material material)
    {
        return material.shader.name == "TextMeshPro/Mobile/Distance Field" &&
            font.atlasPopulationMode == AtlasPopulationMode.Static && font.atlasTexture != null &&
            font.atlasTexture.name.StartsWith("coretext-static-sdf-", StringComparison.Ordinal);
    }

    float OutlineWidth(TMP_FontAsset font, Material material, float sourceWidth, float labelSize)
    {
        float pointSize = font.faceInfo.pointSize, gradient = font.material.GetFloat("_GradientScale");
        float sourceOutlineWidth = sourceWidth, labelFontSize = labelSize;
        float width = sourceOutlineWidth * pointSize / labelFontSize / (gradient - 1f);
        if (!isStrokePass) return width;
        // CoreText stores the full signed range in an 8-bit atlas. TMP SDFAA
        // stores half that distance range for the same GradientScale. The two
        // native encodings therefore need different radius-to-threshold maps.
        return UsesGeneratedDistanceAtlas(font, material) ? width * (254f / 255f) : width * .5f;
    }

    float OutlineFaceDilate(TMP_FontAsset font, Material material, float width)
    {
        var baseDilate = font.material.HasProperty("_FaceDilate") ? font.material.GetFloat("_FaceDilate") : 0f;
        // Cocos strokes first, then fills the original glyph. TMP Mobile's
        // inner threshold adds half the outline. Dilating by the same width
        // cancels that offset and keeps the filled glyph's original edge.
        if (isStrokePass)
            return baseDilate * font.material.GetFloat("_ScaleRatioA") + width;
        return baseDilate;
    }

    // Mobile SDF draws its outline only in this shader variant. Full SDF
    // shaders without the keyword compute the outline unconditionally.
    static bool OutlineVariantMatches(Material material, float width)
    {
        var keyword = material.shader.keywordSpace.FindKeyword("OUTLINE_ON");
        return !keyword.isValid || material.IsKeywordEnabled(keyword) == (width > 0f);
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
        float width = OutlineWidth(font, material, sourceOutlineWidth, labelFontSize);
        float faceDilate = OutlineFaceDilate(font, material, width);
        bool changed = !Mathf.Approximately(material.GetFloat("_OutlineWidth"), width)
            || !Mathf.Approximately(material.GetFloat("_GradientScale"), gradient)
            || material.GetColor("_OutlineColor") != sourceOutlineColor
            || (material.HasProperty("_FaceDilate") && !Mathf.Approximately(material.GetFloat("_FaceDilate"), faceDilate));
        if (isStrokePass)
        {
            float ratio = font.material.GetFloat("_ScaleRatioA");
            material.EnableKeyword(ShaderUtilities.Keyword_Ratios);
            material.SetFloat("_WeightNormal", font.material.GetFloat("_WeightNormal") * ratio);
            material.SetFloat("_WeightBold", font.material.GetFloat("_WeightBold") * ratio);
            ShaderUtilities.UpdateShaderRatios(material);
        }
        if (!OutlineVariantMatches(material, width)) {
            material.SetKeyword(material.shader.keywordSpace.FindKeyword("OUTLINE_ON"), width > 0f);
            changed = true;
        }
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
        float width = OutlineWidth(font, material, sourceOutlineWidth, target.fontSize);
        float faceDilate = OutlineFaceDilate(font, material, width);
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
            materialValuesVerified = OutlineVariantMatches(material, width) && Mathf.Approximately(material.GetFloat("_GradientScale"), gradient)
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
