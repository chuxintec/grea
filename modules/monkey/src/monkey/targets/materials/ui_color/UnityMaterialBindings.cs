using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;

// Editor-only native material creation, binding and persisted readback.
public static class MonkeyUnityMaterialBindings
{
    const string Profile = "cocos24-ui-color-sprite-v1";
    const string ProgramHash = "b4e5e249e052cb9370d4e4995b6d5f2f223e8e9cba447d28d2a2d2d0bf4f9b9d";
    const float Epsilon = 0.0001f;

    [Serializable] public sealed class Binding
    {
        public string sourceId;
    }

    [Serializable] public sealed class Spec
    {
        public string profile, programCanonicalSha256, materialSourceId, shaderPath, shaderGuid;
        public string materialPath, materialGuid;
        public string module;
        public float brightness, saturation, constrast, gray;
        public Color silhouette;
        public Binding[] spriteBindings;
    }

    [Serializable] public sealed class Readback
    {
        public string sourceId, materialGuid, shaderGuid;
        public long localFileId;
        public bool persistent, propertiesVerified;
        public bool shaderCompiled;
        public float brightness, saturation, constrast, gray;
        public Color silhouette;
        public string status = "native-editor-readback";
    }

    public sealed class CreatedMaterial
    {
        public Material asset;
        public Readback readback;
    }

    static void Validate(Spec spec)
    {
        if (spec == null || spec.profile != Profile || spec.programCanonicalSha256 != ProgramHash)
            throw new InvalidOperationException("MATERIAL_PROFILE_UNSUPPORTED");
        if (String.IsNullOrEmpty(spec.module) || !Regex.IsMatch(spec.module, @"^[A-Za-z][A-Za-z0-9_-]{0,63}$"))
            throw new InvalidOperationException("MATERIAL_MODULE_PATH_INVALID");
        if (spec.shaderPath != "Assets/Game/Content/Shaders/" + spec.module + "/Shader2DUIColor.shader" ||
            spec.materialPath != "Assets/Game/Content/Materials/" + spec.module + "/Shader2DUIColor.mat")
            throw new InvalidOperationException("MATERIAL_ASSET_PATH_UNSUPPORTED");
        if (String.IsNullOrEmpty(spec.materialSourceId) ||
            !Regex.IsMatch(spec.shaderGuid ?? "", @"^[0-9a-f]{32}$") ||
            !Regex.IsMatch(spec.materialGuid ?? "", @"^[0-9a-f]{32}$"))
            throw new InvalidOperationException("MATERIAL_SOURCE_IDENTITY_MISSING");
        if (new[] { spec.brightness, spec.saturation, spec.constrast, spec.gray,
                    spec.silhouette.r, spec.silhouette.g, spec.silhouette.b, spec.silhouette.a }.Any(v => Single.IsNaN(v) || Single.IsInfinity(v)))
            throw new InvalidOperationException("MATERIAL_PROPERTY_NONFINITE");
    }

    static void SetSourceProperties(Material material, Spec spec)
    {
        foreach (var property in new[] { "_Brightness", "_Saturation", "_Constrast", "_Gray", "_Silhouette" })
            if (!material.HasProperty(property)) throw new InvalidOperationException("MATERIAL_SHADER_PROPERTY_MISSING: " + property);
        material.SetFloat("_Brightness", spec.brightness);
        material.SetFloat("_Saturation", spec.saturation);
        material.SetFloat("_Constrast", spec.constrast);
        material.SetFloat("_Gray", spec.gray);
        material.SetColor("_Silhouette", spec.silhouette);
    }

    static bool Near(float a, float b) => Mathf.Abs(a - b) <= Epsilon;

    static string ReadMetaGuid(string metaPath)
    {
        if (!File.Exists(metaPath)) return null;
        var match = Regex.Match(File.ReadAllText(metaPath), @"(?m)^guid:\s*([0-9a-fA-F]{32})\s*$");
        return match.Success ? match.Groups[1].Value.ToLowerInvariant() : null;
    }

    static bool IsNativeMaterialMeta(string metaPath)
    {
        if (!File.Exists(metaPath)) return false;
        var text = File.ReadAllText(metaPath);
        return text.Contains("NativeFormatImporter:") && text.Contains("mainObjectFileID: 2100000");
    }

    static void EnsurePlannedMaterialMeta(Spec spec)
    {
        var folder = Path.GetDirectoryName(spec.materialPath);
        if (String.IsNullOrEmpty(folder)) throw new InvalidOperationException("MATERIAL_NATIVE_FOLDER_INVALID");
        Directory.CreateDirectory(folder);
        var metaPath = spec.materialPath + ".meta";
        var current = ReadMetaGuid(metaPath);
        if (File.Exists(metaPath) && current == null)
            throw new InvalidOperationException("MATERIAL_META_GUID_INVALID: " + metaPath);
        if (File.Exists(metaPath) && !IsNativeMaterialMeta(metaPath))
            throw new InvalidOperationException("MATERIAL_META_IMPORTER_INVALID: " + metaPath);
        if (current != null && !String.Equals(current, spec.materialGuid, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("MATERIAL_META_GUID_CONFLICT: " + metaPath);
        if (File.Exists(spec.materialPath) || AssetDatabase.LoadAssetAtPath<Material>(spec.materialPath) != null)
            throw new InvalidOperationException("MATERIAL_NATIVE_ASSET_COLLISION: " + spec.materialPath);
        var known = AssetDatabase.AssetPathToGUID(spec.materialPath);
        if (!String.IsNullOrEmpty(known) && !String.Equals(known, spec.materialGuid, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("MATERIAL_NATIVE_GUID_CONFLICT: " + spec.materialPath);
        var guidOwner = AssetDatabase.GUIDToAssetPath(spec.materialGuid);
        if (!String.IsNullOrEmpty(guidOwner) && guidOwner != spec.materialPath)
            throw new InvalidOperationException("MATERIAL_NATIVE_GUID_ALREADY_OWNED: " + guidOwner);
        if (current == null)
        {
            var metadata = "fileFormatVersion: 2\nguid: " + spec.materialGuid + "\nNativeFormatImporter:\n" +
                "  externalObjects: {}\n  mainObjectFileID: 2100000\n  userData: \n" +
                "  assetBundleName: \n  assetBundleVariant: \n";
            File.WriteAllText(metaPath, metadata, new UTF8Encoding(false));
        }
        if (!String.Equals(ReadMetaGuid(metaPath), spec.materialGuid, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("MATERIAL_META_GUID_READBACK_MISMATCH: " + metaPath);
    }

    static bool VerifyProperties(Material material, Spec spec)
    {
        return material != null && material.shader != null && !ShaderUtil.ShaderHasError(material.shader) &&
            Near(material.GetFloat("_Brightness"), spec.brightness) &&
            Near(material.GetFloat("_Saturation"), spec.saturation) &&
            Near(material.GetFloat("_Constrast"), spec.constrast) &&
            Near(material.GetFloat("_Gray"), spec.gray) &&
            Near(material.GetColor("_Silhouette").r, spec.silhouette.r) &&
            Near(material.GetColor("_Silhouette").g, spec.silhouette.g) &&
            Near(material.GetColor("_Silhouette").b, spec.silhouette.b) &&
            Near(material.GetColor("_Silhouette").a, spec.silhouette.a);
    }

    public static CreatedMaterial CreateSaveReadback(Spec spec)
    {
        Validate(spec);
        AssetDatabase.ImportAsset(spec.shaderPath, ImportAssetOptions.ForceSynchronousImport);
        var shader = AssetDatabase.LoadAssetAtPath<Shader>(spec.shaderPath);
        if (shader == null || AssetDatabase.GetAssetPath(shader) != spec.shaderPath ||
            AssetDatabase.AssetPathToGUID(spec.shaderPath) != spec.shaderGuid ||
            AssetDatabase.GUIDToAssetPath(spec.shaderGuid) != spec.shaderPath ||
            shader.name != "Monkey/Recovered/Shader2DUIColor")
            throw new InvalidOperationException("MATERIAL_SHADER_NATIVE_IDENTITY_MISMATCH");
        if (ShaderUtil.ShaderHasError(shader))
            throw new InvalidOperationException("MATERIAL_SHADER_COMPILE_ERROR: " + spec.shaderPath);
        EnsurePlannedMaterialMeta(spec);

        var material = new Material(shader) { name = "Shader2DUIColor" };
        SetSourceProperties(material, spec);
        AssetDatabase.CreateAsset(material, spec.materialPath);
        EditorUtility.SetDirty(material);
        AssetDatabase.SaveAssetIfDirty(material);
        // CreateAsset may assign a fresh GUID even when an orphan generated
        // meta existed. No renderer references this new asset yet. Bind only
        // this just-created asset's metadata, then ask AssetDatabase to reload.
        string createdGuid=AssetDatabase.AssetPathToGUID(spec.materialPath);
        if(createdGuid!=spec.materialGuid) {
            string occupied=AssetDatabase.GUIDToAssetPath(spec.materialGuid);
            if(!String.IsNullOrEmpty(occupied)&&occupied!=spec.materialPath)
                throw new InvalidOperationException("MATERIAL_GUID_ALREADY_OWNED");
            string metaPath=spec.materialPath+".meta",meta=File.ReadAllText(metaPath);
            var expression=new Regex("(?m)^guid: "+Regex.Escape(createdGuid)+"\\r?$");
            if(!Regex.IsMatch(createdGuid,"^[a-f0-9]{32}$")||expression.Matches(meta).Count!=1)
                throw new InvalidOperationException("MATERIAL_CREATED_META_IDENTITY_INVALID");
            File.WriteAllText(metaPath,expression.Replace(meta,"guid: "+spec.materialGuid),new UTF8Encoding(false));
        }
        AssetDatabase.ImportAsset(spec.materialPath, ImportAssetOptions.ForceSynchronousImport|ImportAssetOptions.ForceUpdate);
        var saved = AssetDatabase.LoadAssetAtPath<Material>(spec.materialPath);
        if (saved == null || !EditorUtility.IsPersistent(saved) ||
            AssetDatabase.AssetPathToGUID(spec.materialPath) != spec.materialGuid ||
            AssetDatabase.GUIDToAssetPath(spec.materialGuid) != spec.materialPath ||
            AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(saved.shader)) != spec.shaderGuid ||
            !VerifyProperties(saved, spec) ||
            !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(saved, out string materialGuid, out long localId) ||
            materialGuid != spec.materialGuid || localId == 0)
            throw new InvalidOperationException("MATERIAL_NATIVE_SAVE_READBACK_MISMATCH");

        return new CreatedMaterial { asset = saved, readback = new Readback {
            sourceId = spec.materialSourceId, materialGuid = materialGuid,
            shaderGuid = spec.shaderGuid, localFileId = localId, persistent = true,
            propertiesVerified = true, shaderCompiled = !ShaderUtil.ShaderHasError(saved.shader), brightness = saved.GetFloat("_Brightness"),
            saturation = saved.GetFloat("_Saturation"), constrast = saved.GetFloat("_Constrast"),
            gray = saved.GetFloat("_Gray"), silhouette = saved.GetColor("_Silhouette") }};
    }

    static HashSet<string> ExpectedBindings(Spec spec)
    {
        var ids = (spec.spriteBindings ?? Array.Empty<Binding>()).Select(row => row == null ? null : row.sourceId).ToArray();
        if (ids.Any(String.IsNullOrEmpty) || ids.Distinct().Count() != ids.Length)
            throw new InvalidOperationException("MATERIAL_SOURCE_COMPONENT_IDS_INVALID");
        return new HashSet<string>(ids, StringComparer.Ordinal);
    }

    public static void Bind(Spec spec, Material savedMaterial, IDictionary<string, Component> componentsBySourceId)
    {
        Validate(spec);
        if (!VerifyProperties(savedMaterial, spec) || AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(savedMaterial)) != spec.materialGuid)
            throw new InvalidOperationException("MATERIAL_NATIVE_ASSET_NOT_VERIFIED");
        var expected = ExpectedBindings(spec);
        if (componentsBySourceId == null || componentsBySourceId.Count != expected.Count ||
            !expected.SetEquals(componentsBySourceId.Keys))
            throw new InvalidOperationException("MATERIAL_SOURCE_COMPONENT_MAP_MISMATCH");
        foreach (var sourceId in expected)
        {
            var component = componentsBySourceId[sourceId];
            var image = component as Image;
            if (image != null) image.material = savedMaterial;
            else
            {
                var renderer = component as SpriteRenderer;
                if (renderer == null) throw new InvalidOperationException("MATERIAL_COMPONENT_TYPE_UNSUPPORTED: " + sourceId);
                renderer.sharedMaterial = savedMaterial;
            }
            if (!ReadBound(spec, savedMaterial, component))
                throw new InvalidOperationException("MATERIAL_COMPONENT_BINDING_READBACK_MISMATCH: " + sourceId);
        }
    }

    public static bool ReadBound(Spec spec, Material savedMaterial, Component component)
    {
        Validate(spec);
        if (!VerifyProperties(savedMaterial, spec)) return false;
        var image = component as Image;
        if (image != null) return image.material == savedMaterial;
        var renderer = component as SpriteRenderer;
        return renderer != null && renderer.sharedMaterial == savedMaterial;
    }
}
