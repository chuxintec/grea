using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEngine;

public static class UnityStaticRetainedAssets
{
    [Serializable] public class HashSpec { public string bundle, path, sha256; public int bytes; }
    [Serializable] public class UnityTargetSpec
    {
        public string path, guid, type, shader, pixelOrientation;
        public string materialDocumentPath, effectDocumentPath;
    }
    [Serializable] public class Entry
    {
        public string sourceId, sourceType, retentionKind, contentSha256, rgbaSha256;
        public string sourceMaterialUuid, sourceMaterialDocumentSha256, sourceEffectId;
        public string sourceMaterialName, sourceEffectDocumentSha256, sourceEffectName, shader;
        public string sourceDocumentSha256, effectDocumentSha256;
        public int[] dimensions;
        public bool nonRendering, renderingRecovered;
        public HashSpec sourceNative;
        public UnityTargetSpec unity;
    }
    [Serializable] public class Contract
    {
        public string schema, sourceManifestSha256;
        public Entry[] assets;
    }
    [Serializable] public class Result
    {
        public string sourceId, retentionKind, nativeType, guid, sourceSha256, pixelSha256, shader;
        public long localFileId;
        public int width, height;
        public bool persistent, nonRendering, verified;
    }

    static string Sha(byte[] bytes)
    {
        using (var hash = SHA256.Create())
            return BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
    }

    static string CanonicalPath(string path)
    {
        if (String.IsNullOrEmpty(path) || !path.StartsWith("Assets/", StringComparison.Ordinal) ||
            path.Contains("..") || path.Contains("\\")) throw new InvalidOperationException("RETAINED_ASSET_PATH_INVALID: " + path);
        return path;
    }

    static Entry Exact(Contract contract, string sourceId)
    {
        if (contract == null || contract.schema != "monkey-prefab-static-retained-assets/1")
            throw new InvalidOperationException("RETAINED_ASSET_CONTRACT_INVALID");
        var rows = (contract.assets ?? Array.Empty<Entry>()).Where(x => x.sourceId == sourceId).ToArray();
        if (rows.Length != 1) throw new InvalidOperationException("RETAINED_ASSET_SOURCE_ID_NOT_UNIQUE: " + sourceId);
        return rows[0];
    }

    static UnityEngine.Object Load(Entry entry)
    {
        var path = CanonicalPath(entry.unity.path);
        UnityEngine.Object value;
        switch (entry.retentionKind)
        {
            case "buffer-asset": value = AssetDatabase.LoadAssetAtPath<TextAsset>(path); break;
            case "texture-asset": value = AssetDatabase.LoadAssetAtPath<Texture2D>(path); break;
            case "retained-source-material": value = AssetDatabase.LoadAssetAtPath<NativeRetainedMaterial>(path); break;
            case "builtin-default-material": value = AssetDatabase.LoadAssetAtPath<Material>(path); break;
            default: throw new InvalidOperationException("RETAINED_ASSET_KIND_UNSUPPORTED: " + entry.retentionKind);
        }
        if (value == null) throw new InvalidOperationException("RETAINED_ASSET_NATIVE_IMPORT_MISSING: " + entry.sourceId);
        if (AssetDatabase.AssetPathToGUID(path) != entry.unity.guid)
            throw new InvalidOperationException("RETAINED_ASSET_GUID_DIFFERS: " + entry.sourceId);
        return value;
    }

    static void PrepareTexture(Entry entry)
    {
        var path = CanonicalPath(entry.unity.path);
        var importer = AssetImporter.GetAtPath(path) as TextureImporter;
        if (importer == null) throw new InvalidOperationException("RETAINED_TEXTURE_IMPORTER_MISSING: " + entry.sourceId);
        importer.textureType = TextureImporterType.Default;
        importer.textureShape = TextureImporterShape.Texture2D;
        importer.mipmapEnabled = false;
        importer.isReadable = true;
        importer.alphaIsTransparency = false;
        importer.textureCompression = TextureImporterCompression.Uncompressed;
        importer.npotScale = TextureImporterNPOTScale.None;
        importer.SaveAndReimport();
    }

    static void CreateRetainedMaterial(Entry entry)
    {
        var target = entry.unity;
        var path = CanonicalPath(target.path);
        var materialDocument = AssetDatabase.LoadAssetAtPath<TextAsset>(CanonicalPath(target.materialDocumentPath));
        var effectDocument = AssetDatabase.LoadAssetAtPath<TextAsset>(CanonicalPath(target.effectDocumentPath));
        if (materialDocument == null || effectDocument == null)
            throw new InvalidOperationException("RETAINED_MATERIAL_SOURCE_DOCUMENT_MISSING: " + entry.sourceId);
        var current = AssetDatabase.LoadAssetAtPath<NativeRetainedMaterial>(path);
        if (current == null)
        {
            var created = ScriptableObject.CreateInstance<NativeRetainedMaterial>();
            created.name = Path.GetFileNameWithoutExtension(path);
            current = created;

        }
        current.sourceMaterialId = entry.sourceId;
        current.sourceMaterialName = entry.sourceMaterialName;
        current.sourceMaterialDocumentSha256 = entry.sourceMaterialDocumentSha256;
        current.sourceEffectId = entry.sourceEffectId;
        current.sourceEffectName = entry.sourceEffectName;
        current.sourceEffectDocumentSha256 = entry.sourceEffectDocumentSha256;
        current.sourceMaterialDocument = materialDocument;
        current.sourceEffectDocument = effectDocument;
        current.retentionOnly = entry.nonRendering;
        current.renderingRecovered = entry.renderingRecovered;
        if(!EditorUtility.IsPersistent(current)) {
            File.WriteAllText(path+".meta","fileFormatVersion: 2\nguid: "+entry.unity.guid+"\nNativeFormatImporter:\n  externalObjects: {}\n  mainObjectFileID: 11400000\n");
            UnityEditorInternal.InternalEditorUtility.SaveToSerializedFileAndForget(new UnityEngine.Object[]{current},path,true);
            UnityEngine.Object.DestroyImmediate(current);AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceSynchronousImport);
        } else EditorUtility.SetDirty(current);
    }

    static void CreateBuiltinMaterial(Entry entry)
    {
        var path = CanonicalPath(entry.unity.path);
        var shader = Shader.Find(entry.unity.shader);
        if (shader == null || shader.name != "UI/Default")
            throw new InvalidOperationException("RETAINED_BUILTIN_UI_SHADER_MISSING: " + entry.sourceId);
        var material = AssetDatabase.LoadAssetAtPath<Material>(path);
        if (material == null)
        {
            material = new Material(shader) { name = Path.GetFileNameWithoutExtension(path) };
            File.WriteAllText(path+".meta","fileFormatVersion: 2\nguid: "+entry.unity.guid+"\nNativeFormatImporter:\n  externalObjects: {}\n  mainObjectFileID: 2100000\n");
            UnityEditorInternal.InternalEditorUtility.SaveToSerializedFileAndForget(new UnityEngine.Object[]{material},path,true);
            UnityEngine.Object.DestroyImmediate(material);AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceSynchronousImport);
            material=AssetDatabase.LoadAssetAtPath<Material>(path);
        }
        if (material.shader != shader || material.shader.name != "UI/Default")
            throw new InvalidOperationException("RETAINED_BUILTIN_MATERIAL_SHADER_DIFFERS: " + entry.sourceId);
    }

    public static void Create(Contract contract)
    {
        if (contract == null || contract.schema != "monkey-prefab-static-retained-assets/1")
            throw new InvalidOperationException("RETAINED_ASSET_CONTRACT_INVALID");
        foreach (var entry in contract.assets ?? Array.Empty<Entry>())
        {
            if (entry == null || String.IsNullOrEmpty(entry.sourceId) || entry.unity == null)
                throw new InvalidOperationException("RETAINED_ASSET_ENTRY_INVALID");
            CanonicalPath(entry.unity.path);
            if (entry.retentionKind == "texture-asset") PrepareTexture(entry);
            else if (entry.retentionKind == "retained-source-material") CreateRetainedMaterial(entry);
            else if (entry.retentionKind == "builtin-default-material") CreateBuiltinMaterial(entry);
            else if (entry.retentionKind != "buffer-asset")
                throw new InvalidOperationException("RETAINED_ASSET_KIND_UNSUPPORTED: " + entry.retentionKind);
        }
        AssetDatabase.SaveAssets();
    }

    public static UnityEngine.Object Resolve(Contract contract, string sourceId)
    {
        var entry = Exact(contract, sourceId);
        var value = Load(entry);
        if (entry.retentionKind == "builtin-default-material" &&
            (!(value is Material) || ((Material)value).shader == null || ((Material)value).shader.name != "UI/Default"))
            throw new InvalidOperationException("RETAINED_BUILTIN_MATERIAL_NOT_NATIVE_DEFAULT: " + sourceId);
        if (entry.retentionKind == "retained-source-material" &&
            (!(value is NativeRetainedMaterial) || !((NativeRetainedMaterial)value).retentionOnly || ((NativeRetainedMaterial)value).renderingRecovered))
            throw new InvalidOperationException("RETAINED_MATERIAL_MUST_NOT_RENDER: " + sourceId);
        return value;
    }

    static byte[] TexturePixelsTopDown(Texture2D texture)
    {
        var pixels = texture.GetPixels32();
        var bytes = new byte[pixels.Length * 4];
        var offset = 0;
        for (var y = texture.height - 1; y >= 0; y--)
        for (var x = 0; x < texture.width; x++)
        {
            var pixel = pixels[y * texture.width + x];
            bytes[offset++] = pixel.r; bytes[offset++] = pixel.g; bytes[offset++] = pixel.b; bytes[offset++] = pixel.a;
        }
        return bytes;
    }

    static Result ReadOne(Entry entry)
    {
        var asset = Load(entry);
        if (!EditorUtility.IsPersistent(asset) || !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(asset, out var guid, out long localId) || localId == 0)
            throw new InvalidOperationException("RETAINED_ASSET_PERSISTENT_IDENTITY_MISSING: " + entry.sourceId);
        var result = new Result { sourceId = entry.sourceId, retentionKind = entry.retentionKind,
            nativeType = asset.GetType().FullName, guid = guid, localFileId = localId,
            persistent = true, nonRendering = entry.nonRendering, verified = true };
        if (entry.retentionKind == "buffer-asset")
        {
            var raw = ((TextAsset)asset).bytes;
            result.sourceSha256 = Sha(raw);
            if (result.sourceSha256 != entry.contentSha256) throw new InvalidOperationException("RETAINED_BUFFER_BYTES_DIFFER: " + entry.sourceId);
        }
        else if (entry.retentionKind == "texture-asset")
        {
            var texture = (Texture2D)asset;
            var pixels = TexturePixelsTopDown(texture);
            result.width = texture.width; result.height = texture.height; result.pixelSha256 = Sha(pixels);
            if (texture.width != entry.dimensions[0] || texture.height != entry.dimensions[1] || result.pixelSha256 != entry.rgbaSha256)
                throw new InvalidOperationException("RETAINED_TEXTURE_PIXELS_DIFFER: " + entry.sourceId);
        }
        else if (entry.retentionKind == "retained-source-material")
        {
            var retained = (NativeRetainedMaterial)asset;
            if (retained.sourceMaterialId != entry.sourceId || retained.sourceEffectId != entry.sourceEffectId ||
                retained.sourceMaterialDocument == null || retained.sourceEffectDocument == null ||
                Sha(retained.sourceMaterialDocument.bytes) != entry.sourceMaterialDocumentSha256 ||
                Sha(retained.sourceEffectDocument.bytes) != entry.sourceEffectDocumentSha256 ||
                retained.sourceMaterialName != entry.sourceMaterialName ||
                !retained.retentionOnly || retained.renderingRecovered)
                throw new InvalidOperationException("RETAINED_MATERIAL_SOURCE_DOCUMENTS_DIFFER: " + entry.sourceId);
            result.sourceSha256 = retained.sourceMaterialDocumentSha256;
        }
        else if (entry.retentionKind == "builtin-default-material")
        {
            var material = (Material)asset;
            if (material.shader == null || material.shader.name != "UI/Default")
                throw new InvalidOperationException("RETAINED_BUILTIN_MATERIAL_SHADER_DIFFERS: " + entry.sourceId);
            var materialDoc = AssetDatabase.LoadAssetAtPath<TextAsset>(CanonicalPath(entry.unity.materialDocumentPath));
            var effectDoc = AssetDatabase.LoadAssetAtPath<TextAsset>(CanonicalPath(entry.unity.effectDocumentPath));
            if (materialDoc == null || effectDoc == null || Sha(materialDoc.bytes) != entry.sourceDocumentSha256 ||
                Sha(effectDoc.bytes) != entry.effectDocumentSha256)
                throw new InvalidOperationException("RETAINED_BUILTIN_SOURCE_EVIDENCE_DIFFERS: " + entry.sourceId);
            result.sourceSha256 = entry.sourceDocumentSha256;
            result.shader = material.shader.name;
        }
        return result;
    }

    public static Result[] Read(Contract contract)
    {
        if (contract == null || contract.schema != "monkey-prefab-static-retained-assets/1")
            throw new InvalidOperationException("RETAINED_ASSET_CONTRACT_INVALID");
        return (contract.assets ?? Array.Empty<Entry>()).Select(ReadOne).ToArray();
    }
}

// Thin integration surface; the owner adds this field to its serialized Plan
// DTO and calls these methods after importing the payload copies.
public static partial class MonkeyImporter
{
    static void CreateStaticRetainedAssets(Plan plan)
    {
        UnityStaticRetainedAssets.Create(plan.staticRetainedAssets);
    }

    static UnityEngine.Object ResolveStaticRetainedAsset(Plan plan, string sourceId)
    {
        return UnityStaticRetainedAssets.Resolve(plan.staticRetainedAssets, sourceId);
    }

    static UnityStaticRetainedAssets.Result[] ReadStaticRetainedAssets(Plan plan)
    {
        return UnityStaticRetainedAssets.Read(plan.staticRetainedAssets);
    }
}
