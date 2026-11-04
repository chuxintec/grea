using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;

/// <summary>Optional strict static t0 material hooks for the Unity Editor importer.</summary>
public static partial class MonkeyImporter
{
    static UnityStaticTimeMaterialBindings.Spec ParseStaticTimeMaterialSpec(string json)
    {
        var spec = UnityStaticTimeMaterialBindings.Parse(json);
        if (spec == null) return null;
        if (String.IsNullOrWhiteSpace(spec.sourceManifestSha256) || spec.materials.Length == 0)
            throw new InvalidOperationException("STATIC_TIME_MATERIAL_SOURCE_PIN_MISSING");
        return spec;
    }

    static TextureSpec ExactStaticTimeTexture(Plan plan, string frameSourceId)
    {
        var rows = (plan.textures ?? Array.Empty<TextureSpec>()).Where(row => row != null && row.id == frameSourceId).ToArray();
        if (rows.Length != 1 || String.IsNullOrWhiteSpace(rows[0].path) || !rows[0].path.StartsWith("Assets/", StringComparison.Ordinal) ||
            rows[0].path.Contains("..") || rows[0].path.Contains("\\") || rows[0].path.Contains(":"))
            throw new InvalidOperationException("STATIC_TIME_FRAME_PLAN_IDENTITY_MISMATCH: " + frameSourceId);
        return rows[0];
    }

    static Dictionary<string, Sprite> LoadStaticTimeFrames(Plan plan, UnityStaticTimeMaterialBindings.Spec spec)
    {
        var frames = new Dictionary<string, Sprite>(StringComparer.Ordinal);
        foreach (var binding in spec.materials.SelectMany(row => row.spriteBindings ?? Array.Empty<UnityStaticTimeMaterialBindings.SpriteBinding>()))
        {
            var texture = ExactStaticTimeTexture(plan, binding.spriteFrameSourceId);
            var frame = AssetDatabase.LoadAssetAtPath<Sprite>(texture.path);
            if (frame == null) throw new InvalidOperationException("STATIC_TIME_FRAME_ASSET_MISSING: " + texture.path);
            if (frames.TryGetValue(binding.spriteFrameSourceId, out var prior) && prior != frame)
                throw new InvalidOperationException("STATIC_TIME_FRAME_ASSET_AMBIGUOUS: " + binding.spriteFrameSourceId);
            frames[binding.spriteFrameSourceId] = frame;
        }
        return frames;
    }

    static string StaticTimeSha(byte[] bytes)
    {
        using (var sha = System.Security.Cryptography.SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
    }

    static string StaticTimeProjectPath(string assetPath)
    {
        if (String.IsNullOrWhiteSpace(assetPath) || !assetPath.StartsWith("Assets/", StringComparison.Ordinal) ||
            assetPath.Contains("..") || assetPath.Contains("\\") || assetPath.Contains(":"))
            throw new InvalidOperationException("STATIC_TIME_SHADER_PATH_INVALID");
        var root = Directory.GetParent(Application.dataPath);
        if (root == null) throw new InvalidOperationException("STATIC_TIME_PROJECT_ROOT_UNAVAILABLE");
        return Path.GetFullPath(Path.Combine(root.FullName, assetPath.Replace('/', Path.DirectorySeparatorChar)));
    }

    static void VerifyStaticTimeShaderPayload(UnityStaticTimeMaterialBindings.Spec spec)
    {
        if (spec.targetShader == null || spec.targetShader.unity == null ||
            !File.Exists(StaticTimeProjectPath(spec.targetShader.unity.path)) ||
            StaticTimeSha(File.ReadAllBytes(StaticTimeProjectPath(spec.targetShader.unity.path))) != spec.targetShaderSha256)
            throw new InvalidOperationException("STATIC_TIME_SHADER_PAYLOAD_HASH_MISMATCH");
        var shader = AssetDatabase.LoadAssetAtPath<Shader>(spec.targetShader.unity.path);
        if (shader == null || AssetDatabase.AssetPathToGUID(spec.targetShader.unity.path) != spec.targetShader.unity.guid)
            throw new InvalidOperationException("STATIC_TIME_SHADER_NATIVE_IDENTITY_MISMATCH");
    }

    static Dictionary<string, Material> PrepareStaticTimeMaterials(UnityStaticTimeMaterialBindings.Spec spec)
    {
        VerifyStaticTimeShaderPayload(spec);
        var saved = new Dictionary<string, Material>(StringComparer.Ordinal);
        foreach (var row in spec.materials)
        {
            var material = UnityStaticTimeMaterialBindings.Prepare(spec, row);
            if (saved.ContainsKey(row.sourceMaterialId))
                throw new InvalidOperationException("STATIC_TIME_SOURCE_MATERIAL_DUPLICATE: " + row.sourceMaterialId);
            saved.Add(row.sourceMaterialId, material);
        }
        return saved;
    }

    static ComponentSpec ExactStaticTimeComponent(Plan plan, UnityStaticTimeMaterialBindings.MaterialSpec material,
        UnityStaticTimeMaterialBindings.SpriteBinding binding)
    {
        var rows = (plan.components ?? Array.Empty<ComponentSpec>()).Where(row => row != null && row.sourceId == binding.sourceId).ToArray();
        if (rows.Length != 1 || rows[0].type != "cc.Sprite" || !rows[0].convertible || rows[0].node == null ||
            rows[0].spriteFrame != binding.spriteFrameSourceId ||
            rows[0].nativeStaticTimeMaterialSourceId != material.sourceMaterialId ||
            rows[0].nativeStaticTimeSourceComponentId != binding.sourceComponentId)
            throw new InvalidOperationException("STATIC_TIME_PLAN_COMPONENT_BINDING_MISMATCH: " + binding.sourceId);
        return rows[0];
    }

    static partial void PrepareOptionalStaticTimeMaterials(string json, Plan plan,
        Dictionary<string, GameObject> nodes, Dictionary<string, Sprite> spriteFrames)
    {
        if (String.IsNullOrWhiteSpace(json)) return;
        if (plan == null || nodes == null || spriteFrames == null)
            throw new InvalidOperationException("STATIC_TIME_IMPORT_CONTEXT_MISSING");
        var spec = ParseStaticTimeMaterialSpec(json);
        if (spec.target != "unity" || plan.sourceManifestSha256 != spec.sourceManifestSha256)
            throw new InvalidOperationException("STATIC_TIME_PLAN_SOURCE_PIN_MISMATCH");
        var frames = LoadStaticTimeFrames(plan, spec);
        foreach (var frame in frames)
        {
            if (!spriteFrames.TryGetValue(frame.Key, out var supplied) || supplied == null || supplied != frame.Value)
                throw new InvalidOperationException("STATIC_TIME_PREPARE_FRAME_MAP_MISMATCH: " + frame.Key);
        }
        var materials = PrepareStaticTimeMaterials(spec);
        foreach (var row in spec.materials)
        {
            var images = new Dictionary<string, Image>(StringComparer.Ordinal);
            foreach (var binding in row.spriteBindings ?? Array.Empty<UnityStaticTimeMaterialBindings.SpriteBinding>())
            {
                var component = ExactStaticTimeComponent(plan, row, binding);
                if (!nodes.TryGetValue(component.node, out var node) || node == null)
                    throw new InvalidOperationException("STATIC_TIME_SOURCE_NODE_MISSING: " + component.node);
                var image = node.GetComponent<Image>();
                if (image == null) throw new InvalidOperationException("STATIC_TIME_NATIVE_IMAGE_MISSING: " + binding.sourceId);
                images.Add(binding.sourceId, image);
            }
            UnityStaticTimeMaterialBindings.Apply(spec, row, images, frames);
        }
    }

    static partial void ResolveOptionalStaticTimeMaterial(Plan plan,string id, ref UnityEngine.Object value)
    {
        if (String.IsNullOrWhiteSpace(id)) return;
        if (plan == null || String.IsNullOrWhiteSpace(plan.staticTimeMaterialsJson)) return;
        var spec = ParseStaticTimeMaterialSpec(plan.staticTimeMaterialsJson);
        var row = spec.materials.SingleOrDefault(item => item.sourceMaterialId == id);
        if (row == null) return;
        VerifyStaticTimeShaderPayload(spec);
        var material = AssetDatabase.LoadAssetAtPath<Material>(row.unity.materialPath);
        UnityStaticTimeMaterialBindings.VerifyMaterialAsset(spec, row, material);
        value = material;
    }

    static partial void ReadSavedOptionalStaticTimeMaterials(Dictionary<string, GameObject> nodes, string prefabId)
    {
        if (nodes == null || String.IsNullOrWhiteSpace(prefabId) || String.IsNullOrWhiteSpace(Paths.plan) || !File.Exists(Paths.plan)) return;
        var plan = JsonUtility.FromJson<Plan>(File.ReadAllText(Paths.plan));
        if (plan == null || String.IsNullOrWhiteSpace(plan.staticTimeMaterialsJson)) return;
        var spec = ParseStaticTimeMaterialSpec(plan.staticTimeMaterialsJson);
        VerifyStaticTimeShaderPayload(spec);
        var frames = LoadStaticTimeFrames(plan, spec);
        var savedRows = new List<UnityStaticTimeMaterialBindings.MaterialReadback>();
        foreach (var row in spec.materials)
        {
            var subset = (row.spriteBindings ?? Array.Empty<UnityStaticTimeMaterialBindings.SpriteBinding>())
                .Where(binding => binding.ownerPrefabId == prefabId).ToArray();
            if (subset.Length == 0) continue;
            var material = AssetDatabase.LoadAssetAtPath<Material>(row.unity.materialPath);
            var local = new UnityStaticTimeMaterialBindings.MaterialSpec
            {
                profile = row.profile, sourceMaterialId = row.sourceMaterialId,
                sourceMaterialDocumentSha256 = row.sourceMaterialDocumentSha256,
                effectDocumentSha256 = row.effectDocumentSha256, targetShaderSha256 = row.targetShaderSha256,
                staticTimeSeconds = row.staticTimeSeconds, targetProperties = row.targetProperties, unity = row.unity,
                spriteBindings = subset
            };
            var images = new Dictionary<string, Image>(StringComparer.Ordinal);
            foreach (var binding in subset)
            {
                var component = ExactStaticTimeComponent(plan, row, binding);
                if (!nodes.TryGetValue(component.node, out var node) || node == null)
                    throw new InvalidOperationException("STATIC_TIME_SAVED_SOURCE_NODE_MISSING: " + component.node);
                var image = node.GetComponent<Image>();
                if (image == null) throw new InvalidOperationException("STATIC_TIME_SAVED_IMAGE_MISSING: " + binding.sourceId);
                images.Add(binding.sourceId, image);
            }
            savedRows.Add(UnityStaticTimeMaterialBindings.Read(spec, local, material, images, frames));
        }
        if (savedRows.Count == 0) return;
        UnityStaticTimeMaterialBindings.WriteReadback("Analysis/Readback/static-time-materials.json", spec, prefabId, savedRows.ToArray());
    }
}
