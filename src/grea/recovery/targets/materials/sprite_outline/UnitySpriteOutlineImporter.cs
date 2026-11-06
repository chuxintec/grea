// Optional partial MonkeyImporter hooks. This file is copied only into a
// candidate with a source-profiled outline; ordinary plans keep the partial
// calls unimplemented and do not depend on the Spec/helper type.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;

public static partial class MonkeyImporter
{
    [Serializable]
    public sealed class SpriteOutlineReadback
    {
        public string sourcePrefabId, materialSourceId, materialGuid, shaderGuid;
        public bool propertiesVerified;
        public string[] boundSpriteComponentIds;
    }

    [Serializable]
    sealed class SpriteOutlineReadbackFile
    {
        public int schemaVersion = 1;
        public SpriteOutlineReadback[] prefabs;
    }

    sealed class SpriteOutlineReadContext
    {
        public Plan plan;
        public UnitySpriteOutlineMaterialBindings.Spec spec;
        public Dictionary<string, Sprite> frames;
        public Material material;
        public UnitySpriteOutlineMaterialBindings.Readback materialReadback;
    }

    // Matching signatures are declared in UnityImporter.cs using only shared
    // Unity/Monkey types. These implementations disappear from ordinary
    // candidates because this file is copied only for the outline profile.

    static UnitySpriteOutlineMaterialBindings.Spec ParseSpriteOutlineSpec(string json)
    {
        if (String.IsNullOrWhiteSpace(json)) return null;
        var spec = JsonUtility.FromJson<UnitySpriteOutlineMaterialBindings.Spec>(json);
        if (spec == null) throw new InvalidOperationException("SPRITE_OUTLINE_PLAN_JSON_INVALID");
        return spec;
    }

    static TextureSpec ExactOutlineTexture(Plan plan, string sourceFrameId)
    {
        if (plan == null || plan.textures == null)
            throw new InvalidOperationException("SPRITE_OUTLINE_PLAN_TEXTURES_MISSING");
        var matches = plan.textures.Where(texture => texture != null && texture.id == sourceFrameId).ToArray();
        if (matches.Length != 1)
            throw new InvalidOperationException("SPRITE_OUTLINE_PLAN_FRAME_IDENTITY_MISMATCH: " + sourceFrameId);
        var texture = matches[0];
        if (String.IsNullOrWhiteSpace(texture.path) || !texture.path.StartsWith("Assets/", StringComparison.Ordinal) ||
            texture.path.Contains("..") || texture.path.Contains("\\") || texture.path.Contains(":"))
            throw new InvalidOperationException("SPRITE_OUTLINE_PLAN_FRAME_PATH_UNSAFE: " + sourceFrameId);
        return texture;
    }

    static Dictionary<string, Sprite> LoadOutlineFrames(Plan plan,
        UnitySpriteOutlineMaterialBindings.Spec spec)
    {
        var frames = new Dictionary<string, Sprite>(StringComparer.Ordinal);
        foreach (var binding in spec.spriteBindings ?? Array.Empty<UnitySpriteOutlineMaterialBindings.SpriteBinding>())
        {
            if (binding == null || String.IsNullOrWhiteSpace(binding.spriteFrameSourceId))
                throw new InvalidOperationException("SPRITE_OUTLINE_PLAN_FRAME_BINDING_MISSING");
            var texture = ExactOutlineTexture(plan, binding.spriteFrameSourceId);
            var frame = AssetDatabase.LoadAssetAtPath<Sprite>(texture.path);
            if (frame == null)
                throw new InvalidOperationException("SPRITE_OUTLINE_PLAN_FRAME_ASSET_MISSING: " + texture.path);
            if (Mathf.Abs(frame.rect.width - spec.properties.outlineTextureSize[0]) > .01f ||
                Mathf.Abs(frame.rect.height - spec.properties.outlineTextureSize[1]) > .01f)
                throw new InvalidOperationException("SPRITE_OUTLINE_TEXTURE_SIZE_MISMATCH: " + binding.sourceId);
            if (frames.TryGetValue(binding.spriteFrameSourceId, out var existing) && existing != frame)
                throw new InvalidOperationException("SPRITE_OUTLINE_DUPLICATE_FRAME_IDENTITY_MISMATCH");
            frames[binding.spriteFrameSourceId] = frame;
        }
        return frames;
    }

    static void VerifyPreparedFrameMap(Plan plan,
        UnitySpriteOutlineMaterialBindings.Spec spec,
        IDictionary<string, Sprite> suppliedFrames)
    {
        if (suppliedFrames == null) throw new InvalidOperationException("SPRITE_OUTLINE_IMPORT_CONTEXT_MISSING");
        foreach (var binding in spec.spriteBindings ?? Array.Empty<UnitySpriteOutlineMaterialBindings.SpriteBinding>())
        {
            var texture = ExactOutlineTexture(plan, binding.spriteFrameSourceId);
            if (!suppliedFrames.TryGetValue(binding.spriteFrameSourceId, out var frame) || frame == null ||
                !String.Equals(AssetDatabase.GetAssetPath(frame), texture.path, StringComparison.Ordinal))
                throw new InvalidOperationException("SPRITE_OUTLINE_PREPARE_FRAME_PATH_MISMATCH: " + binding.sourceId);
        }
    }

    static SpriteOutlineReadContext LoadReadOnlySpriteOutlineContext(Dictionary<string, GameObject> nodes, Plan suppliedPlan = null)
    {
        if (nodes == null) throw new InvalidOperationException("SPRITE_OUTLINE_CURRENT_NODE_MAP_MISSING");
        if (String.IsNullOrWhiteSpace(Paths.plan) || !File.Exists(Paths.plan))
            throw new InvalidOperationException("SPRITE_OUTLINE_IMPORT_PLAN_MISSING: " + Paths.plan);
        // Domain reload intentionally starts with no static outline state.
        // Rebuild the mapping from the exact saved import plan and its texture
        // source IDs/asset paths; this method never creates or rebinds assets.
        var plan = suppliedPlan ?? JsonUtility.FromJson<Plan>(File.ReadAllText(Paths.plan));
        if (plan == null || String.IsNullOrWhiteSpace(plan.spriteOutlineBindingJson)) return null;
        var spec = ParseSpriteOutlineSpec(plan.spriteOutlineBindingJson);
        var frames = LoadOutlineFrames(plan, spec);
        var material = AssetDatabase.LoadAssetAtPath<Material>(spec.unity.materialPath);
        if (material == null)
            throw new InvalidOperationException("SPRITE_OUTLINE_SAVED_MATERIAL_MISSING: " + spec.unity.materialPath);
        var materialReadback = UnitySpriteOutlineMaterialBindings.ReadbackNative(spec);
        return new SpriteOutlineReadContext { plan = plan, spec = spec, frames = frames,
            material = material, materialReadback = materialReadback };
    }

    static ComponentSpec ExactOutlineComponent(Plan plan, string sourceId)
    {
        var matches = (plan.components ?? Array.Empty<ComponentSpec>())
            .Where(component => component != null && component.sourceId == sourceId).ToArray();
        if (matches.Length != 1 || matches[0].type != "cc.Sprite" || !matches[0].convertible ||
            String.IsNullOrWhiteSpace(matches[0].node) || matches[0].spriteFrame == null)
            throw new InvalidOperationException("SPRITE_OUTLINE_PLAN_COMPONENT_MISMATCH: " + sourceId);
        return matches[0];
    }

    static Image CurrentOutlineImage(SpriteOutlineReadContext context,
        Dictionary<string, GameObject> nodes, UnitySpriteOutlineMaterialBindings.SpriteBinding binding)
    {
        var component = ExactOutlineComponent(context.plan, binding.sourceId);
        if (!String.Equals(component.spriteFrame, binding.spriteFrameSourceId, StringComparison.Ordinal))
            throw new InvalidOperationException("SPRITE_OUTLINE_PLAN_COMPONENT_FRAME_IDENTITY_MISMATCH: " + binding.sourceId);
        if (!nodes.TryGetValue(component.node, out var node) || node == null)
            throw new InvalidOperationException("SPRITE_OUTLINE_CURRENT_SOURCE_NODE_MISSING: " + component.node);
        var image = node.GetComponent<Image>();
        if (image == null || !context.frames.TryGetValue(binding.spriteFrameSourceId, out var frame) ||
            frame == null || image.sprite != frame)
            throw new InvalidOperationException("SPRITE_OUTLINE_CURRENT_FRAME_MISMATCH: " + binding.sourceId);
        return image;
    }

    static void VerifyCurrentOutlineBindings(SpriteOutlineReadContext context,
        Dictionary<string, GameObject> nodes, IEnumerable<UnitySpriteOutlineMaterialBindings.SpriteBinding> rows)
    {
        foreach (var binding in rows)
        {
            var image = CurrentOutlineImage(context, nodes, binding);
            var frame = context.frames[binding.spriteFrameSourceId];
            if (!UnitySpriteOutlineMaterialBindings.ReadBound(context.spec, context.material,
                    binding.sourceId, image, _ => frame))
                throw new InvalidOperationException("SPRITE_OUTLINE_CURRENT_BINDING_MISMATCH: " + binding.sourceId);
        }
    }

    // Optional prepare hook. Only this path may create the native Material and
    // bind it to the newly constructed Sprite Image components.
    static partial void PrepareOptionalSpriteOutline(string json, Plan plan,
        Dictionary<string, GameObject> nodes, Dictionary<string, Sprite> spriteFrames)
    {
        if (String.IsNullOrWhiteSpace(json)) return;
        if (plan == null || nodes == null) throw new InvalidOperationException("SPRITE_OUTLINE_IMPORT_CONTEXT_MISSING");
        var spec = ParseSpriteOutlineSpec(json);
        VerifyPreparedFrameMap(plan, spec, spriteFrames);
        PrepareSpriteOutline(spec, plan.components, nodes, spriteFrames);
    }

    // Optional read-only native reference resolver. It reloads the plan and
    // saved Material after domain reload, and validates only this import's
    // source-node map; it never creates a Material or changes a component.
    static partial void ResolveOptionalSpriteOutline(Plan plan, string id,
        Dictionary<string, GameObject> nodes, ref UnityEngine.Object value)
    {
        if (String.IsNullOrWhiteSpace(id) || plan == null) return;
        var spec = ParseSpriteOutlineSpec(plan.spriteOutlineBindingJson);
        if (spec == null || id != spec.materialSourceId) return;
        var context = LoadReadOnlySpriteOutlineContext(nodes, plan);
        if (context == null || id != context.spec.materialSourceId) return;
        VerifyCurrentOutlineBindings(context, nodes, context.spec.spriteBindings);
        value = context.material;
    }

    // Optional read-only saved-Prefab verification. Current nodes are supplied
    // by the caller's reopened Prefab; no global scene search or static node
    // cache participates in mapping source IDs to native Images.
    static partial void ReadSavedOptionalSpriteOutline(Dictionary<string, GameObject> nodes, string prefabId)
    {
        ReadSavedSpriteOutline(nodes, prefabId);
    }

    // Public prepare body retained for callers that already construct a Spec.
    // It is the only implementation that creates and binds the native asset.
    public static void PrepareSpriteOutline(
        UnitySpriteOutlineMaterialBindings.Spec spec,
        ComponentSpec[] planComponents,
        IDictionary<string, GameObject> sourceNodes,
        IDictionary<string, Sprite> spriteFramesBySourceId)
    {
        if (spec == null) return;
        if (planComponents == null || sourceNodes == null || spriteFramesBySourceId == null)
            throw new InvalidOperationException("SPRITE_OUTLINE_IMPORT_CONTEXT_MISSING");
        var components = new Dictionary<string, Component>(StringComparer.Ordinal);
        foreach (var binding in spec.spriteBindings ?? Array.Empty<UnitySpriteOutlineMaterialBindings.SpriteBinding>())
        {
            var row = planComponents.SingleOrDefault(component => component != null && component.sourceId == binding.sourceId);
            if (row == null || row.type != "cc.Sprite" || !row.convertible || String.IsNullOrEmpty(row.node) ||
                !String.Equals(row.spriteFrame, binding.spriteFrameSourceId, StringComparison.Ordinal))
                throw new InvalidOperationException("SPRITE_OUTLINE_PLAN_COMPONENT_MISMATCH: " + binding.sourceId);
            if (!sourceNodes.TryGetValue(row.node, out var node) || node == null)
                throw new InvalidOperationException("SPRITE_OUTLINE_SOURCE_NODE_MISSING: " + row.node);
            var image = node.GetComponent<Image>();
            if (image == null) throw new InvalidOperationException("SPRITE_OUTLINE_NATIVE_IMAGE_MISSING: " + binding.sourceId);
            if (!spriteFramesBySourceId.TryGetValue(binding.spriteFrameSourceId, out var frame) || frame == null || image.sprite != frame)
                throw new InvalidOperationException("SPRITE_OUTLINE_SOURCE_FRAME_MISMATCH: " + binding.sourceId);
            if (Mathf.Abs(frame.rect.width - spec.properties.outlineTextureSize[0]) > .01f ||
                Mathf.Abs(frame.rect.height - spec.properties.outlineTextureSize[1]) > .01f)
                throw new InvalidOperationException("SPRITE_OUTLINE_TEXTURE_SIZE_MISMATCH: " + binding.sourceId);
            components.Add(binding.sourceId, image);
        }
        UnitySpriteOutlineMaterialBindings.CreateNative(spec);
        var material = AssetDatabase.LoadAssetAtPath<Material>(spec.unity.materialPath);
        if (material == null)
            throw new InvalidOperationException("SPRITE_OUTLINE_NATIVE_MATERIAL_MISSING: " + spec.unity.materialPath);
        UnitySpriteOutlineMaterialBindings.Bind(spec, material, components,
            frameSourceId => spriteFramesBySourceId.TryGetValue(frameSourceId, out var frame) ? frame : null);
    }

    // Public read-only reference method retained for optional integrations.
    public static void ResolveSpriteOutlineReference(string id, Dictionary<string, GameObject> nodes,
        ref UnityEngine.Object value)
    {
        var plan = JsonUtility.FromJson<Plan>(File.ReadAllText(Paths.plan));
        ResolveOptionalSpriteOutline(plan, id, nodes, ref value);
    }

    public static void ReadSavedSpriteOutline(Dictionary<string, GameObject> nodes, string prefabId)
    {
        var context = LoadReadOnlySpriteOutlineContext(nodes);
        if (context == null) return;
        var rows = context.spec.spriteBindings.Where(binding => binding.sourceId.StartsWith(prefabId + "#", StringComparison.Ordinal)).ToArray();
        if (rows.Length == 0) return;
        VerifyCurrentOutlineBindings(context, nodes, rows);

        var path = "Analysis/Readback/sprite-outline-materials.json";
        var previous = File.Exists(path) ? JsonUtility.FromJson<SpriteOutlineReadbackFile>(File.ReadAllText(path)) : null;
        var results = (previous != null && previous.prefabs != null ? previous.prefabs : Array.Empty<SpriteOutlineReadback>())
            .Where(result => result != null && result.sourcePrefabId != prefabId).ToList();
        results.Add(new SpriteOutlineReadback { sourcePrefabId = prefabId,
            materialSourceId = context.spec.materialSourceId,
            materialGuid = context.materialReadback.materialGuid,
            shaderGuid = context.materialReadback.shaderGuid,
            propertiesVerified = context.materialReadback.propertiesVerified,
            boundSpriteComponentIds = rows.Select(row => row.sourceId).ToArray() });
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, JsonUtility.ToJson(new SpriteOutlineReadbackFile { prefabs = results.ToArray() }, true));
    }
}
