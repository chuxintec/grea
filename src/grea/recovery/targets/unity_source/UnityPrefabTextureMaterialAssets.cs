#if UNITY_EDITOR
using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace MonkeyUnitySource
{
    [Serializable] sealed class TextureMaterialPlan { public int schemaVersion; public string contract; public AssetSpec[] assets; public bool reopenOnly; public string outputAbsolute; }
    [Serializable] sealed class AssetSpec
    {
        public string sourceMaterialId, sourceMaterialRawSha256, sourceMaterialDataSha256; public NativeSourceProperties nativeSourceMaterialProperties;
        public string sourceTextureId; public TextureSpec texture; public ProviderMaterial providerMaterial; public ShaderClosure candidateShaderClosure;
    }
    [Serializable] sealed class NativeSourceProperties { public string m_Name; public NativeSavedProperties m_SavedProperties; }
    [Serializable] sealed class NativeSavedProperties { public NativeColorPair[] m_Colors; public NativeFloatPair[] m_Floats; public NativeIntPair[] m_Ints; public NativeTexEnvPair[] m_TexEnvs; }
    [Serializable] sealed class NativeColorPair { public string name; public Color value; }
    [Serializable] sealed class NativeFloatPair { public string name; public float value; }
    [Serializable] sealed class NativeIntPair { public string name; public int value; }
    [Serializable] sealed class NativeTexEnvPair { public string name; public Vector2 scale, offset; }
    [Serializable] sealed class TextureSpec
    {
        public string rgbaAbsolutePath, rgbaRawSha256, sourceTextureRawSha256, sourceTextureDataSha256, textureName; public int width, height, colorSpace, mipCount; public SourceIdentity sourceTextureIdentity;
        public Sampling sampling;
    }
    [Serializable] sealed class SourceIdentity { public string containerSha256, serializedFile, serializedFileSha256, pathId; }
    [Serializable] sealed class Sampling { public int m_FilterMode, m_Aniso, m_WrapU, m_WrapV, m_WrapW; public float m_MipBias; }
    [Serializable] sealed class ShaderClosure { public string assetPath, metaPath, guid, absoluteAssetPath, absoluteMetaPath, assetSha256, metaSha256; public long localId; }
    [Serializable] sealed class ProviderMaterial
    {
        public string assetPath, guid, absoluteAssetPath, absoluteMetaPath, assetSha256, metaSha256, shaderGuid; public long localId;
    }
    [Serializable] sealed class AssetReadback
    {
        public string materialPath, texturePath;
        public string sourceMaterialId, sourceTextureId, textureGuid, materialGuid, materialShaderGuid, rgbaSha256, textureName, textureType, materialName, materialType, shaderGuid, shaderPath, shaderType;
        public long materialLocalId, textureLocalId, shaderLocalId; public int width, height, filterMode, anisoLevel, wrapModeU, wrapModeV, wrapModeW, mipCount, sourceColorSpace; public bool textureReadable, textureIsDataSRGB; public string textureFormat;
        public bool verified, materialPersistent, texturePersistent, sourcePropertyArraysPreserved, shaderReferencePreserved;
    }
    [Serializable] sealed class TextureMaterialReadback { public string status, error; public AssetReadback[] assets; }

    public static class UnityPrefabTextureMaterialAssets
    {
        [Serializable] sealed class ColorBox { public Color value; }
        static bool NativeIdentity(UnityEngine.Object asset, out string guid, out long localId)
        {
            guid = ""; localId = 0;
            return asset != null && AssetDatabase.Contains(asset) && AssetDatabase.TryGetGUIDAndLocalFileIdentifier(asset, out guid, out localId);
        }
        static bool VerifyAssetIdentity(UnityEngine.Object asset, string path, string expectedGuid, long expectedLocalId, Type expectedType)
        {
            string guid; long localId;
            return NativeIdentity(asset, out guid, out localId) && guid == expectedGuid && localId == expectedLocalId &&
                asset.GetType() == expectedType && AssetDatabase.GetAssetPath(asset) == path;
        }
        static string Hash(byte[] bytes) { using (var h = SHA256.Create()) return BitConverter.ToString(h.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant(); }
        static byte[] ReadBounded(string path, int max = 64 * 1024 * 1024)
        {
            var b = File.ReadAllBytes(path); if (b.Length > max) throw new InvalidDataException("Input exceeds byte limit: " + path); return b;
        }
        static void Require(bool ok, string message) { if (!ok) throw new InvalidDataException(message); }
        static Texture2D CreateTexture(TextureSpec spec, string assetPath)
        {
            var rgba = ReadBounded(spec.rgbaAbsolutePath, 128 * 1024 * 1024);
            Require(Hash(rgba) == spec.rgbaRawSha256 && rgba.Length == spec.width * spec.height * 4, "Pinned RGBA pixels differ");
            var texture = new Texture2D(spec.width, spec.height, TextureFormat.RGBA32, false, spec.colorSpace == 0);
            texture.name = spec.textureName; texture.LoadRawTextureData(rgba); texture.Apply(false, false);
            texture.filterMode = (FilterMode)spec.sampling.m_FilterMode;
            texture.anisoLevel = spec.sampling.m_Aniso; texture.mipMapBias = spec.sampling.m_MipBias;
            texture.wrapModeU = (TextureWrapMode)spec.sampling.m_WrapU; texture.wrapModeV = (TextureWrapMode)spec.sampling.m_WrapV;
            texture.wrapModeW = (TextureWrapMode)spec.sampling.m_WrapW;
            AssetDatabase.CreateAsset(texture, assetPath); texture.name = spec.textureName; EditorUtility.SetDirty(texture); return texture;
        }
        static SerializedProperty MainTex(SerializedObject so)
        {
            var envs = so.FindProperty("m_SavedProperties.m_TexEnvs");
            Require(envs != null && envs.isArray, "Material saved texture environment array unavailable");
            SerializedProperty found = null;
            for (int i = 0; i < envs.arraySize; i++)
            {
                var row = envs.GetArrayElementAtIndex(i); var key = row.FindPropertyRelative("first");
                if (key != null && key.stringValue == "_MainTex")
                {
                    Require(found == null, "Duplicate serialized _MainTex entries");
                    found = row.FindPropertyRelative("second.m_Texture");
                }
            }
            Require(found != null && found.propertyType == SerializedPropertyType.ObjectReference, "Serialized _MainTex texture slot missing");
            return found;
        }
        static void VerifySourceSavedProperties(SerializedObject so, NativeSourceProperties source)
        {
            Require(source != null && source.m_SavedProperties != null, "Pinned source Material saved properties absent");
            VerifyPairs(so.FindProperty("m_SavedProperties.m_Floats"), source.m_SavedProperties.m_Floats, "float");
            VerifyPairs(so.FindProperty("m_SavedProperties.m_Ints"), source.m_SavedProperties.m_Ints, "int");
            VerifyColorPairs(so.FindProperty("m_SavedProperties.m_Colors"), source.m_SavedProperties.m_Colors);
            var envs = so.FindProperty("m_SavedProperties.m_TexEnvs"); var expected = source.m_SavedProperties.m_TexEnvs ?? new NativeTexEnvPair[0];
            Require(envs != null && envs.isArray && envs.arraySize == expected.Length, "Candidate Material texture environment count differs from source");
            for (int i = 0; i < expected.Length; i++)
            {
                var row = envs.GetArrayElementAtIndex(i); var key = row.FindPropertyRelative("first"); var value = row.FindPropertyRelative("second");
                Require(key != null && key.stringValue == expected[i].name, "Candidate Material texture environment key/order differs from source");
                var scale = value.FindPropertyRelative("m_Scale").vector2Value; var offset = value.FindPropertyRelative("m_Offset").vector2Value;
                Require(scale == expected[i].scale && offset == expected[i].offset, "Candidate Material texture transform differs from source");
            }
        }
        static void VerifyPairs<T>(SerializedProperty rows, T[] expected, string kind) where T : class
        {
            expected = expected ?? new T[0]; Require(rows != null && rows.isArray && rows.arraySize == expected.Length, "Candidate Material " + kind + " array count differs from source");
            for (int i = 0; i < expected.Length; i++)
            {
                var row = rows.GetArrayElementAtIndex(i); var key = row.FindPropertyRelative("first"); var value = row.FindPropertyRelative("second");
                Require(key != null, "Candidate Material " + kind + " key unavailable");
                if (kind == "float") { var e = expected[i] as NativeFloatPair; Require(key.stringValue == e.name && Mathf.Abs(value.floatValue-e.value) <= 1e-6f, "Candidate Material float differs from source"); }
                else { var e = expected[i] as NativeIntPair; Require(key.stringValue == e.name && value.intValue == e.value, "Candidate Material int differs from source"); }
            }
        }
        static void VerifyColorPairs(SerializedProperty rows, NativeColorPair[] expected)
        {
            expected = expected ?? new NativeColorPair[0]; Require(rows != null && rows.isArray && rows.arraySize == expected.Length, "Candidate Material color array count differs from source");
            for (int i = 0; i < expected.Length; i++)
            {
                var row = rows.GetArrayElementAtIndex(i); var key = row.FindPropertyRelative("first"); var value = row.FindPropertyRelative("second");
                var c = value.colorValue; var e = expected[i].value;
                Require(key.stringValue == expected[i].name && c == e, "Candidate Material color differs from source");
            }
        }
        static string SerializedSnapshot(SerializedObject so)
        {
            var ignore = MainTex(so).propertyPath;
            var copy = so.GetIterator(); var sb = new StringBuilder();
            while (copy.Next(true))
            { if (copy.propertyPath == ignore || copy.propertyPath.StartsWith(ignore + ".", StringComparison.Ordinal)) continue;
                sb.Append(copy.propertyPath).Append('|').Append(copy.propertyType).Append('|').Append(PropertyValue(copy)).Append('\n');
            }
            return sb.ToString();
        }
        static string PropertyValue(SerializedProperty p)
        {
            switch (p.propertyType)
            {
                case SerializedPropertyType.Integer: return p.intValue.ToString(System.Globalization.CultureInfo.InvariantCulture);
                case SerializedPropertyType.Boolean: return p.boolValue ? "1" : "0";
                case SerializedPropertyType.Float: return p.floatValue.ToString("R", System.Globalization.CultureInfo.InvariantCulture);
                case SerializedPropertyType.String: return p.stringValue;
                case SerializedPropertyType.Color: return JsonUtility.ToJson(new ColorBox { value = p.colorValue });
                case SerializedPropertyType.Vector2: return JsonUtility.ToJson(new Vector2Box { value = p.vector2Value });
                case SerializedPropertyType.Vector3: return JsonUtility.ToJson(new Vector3Box { value = p.vector3Value });
                case SerializedPropertyType.Vector4: return JsonUtility.ToJson(new Vector4Box { value = p.vector4Value });
                case SerializedPropertyType.Quaternion: return JsonUtility.ToJson(new QuaternionBox { value = p.quaternionValue });
                case SerializedPropertyType.Rect: return JsonUtility.ToJson(new RectBox { value = p.rectValue });
                case SerializedPropertyType.Bounds: return JsonUtility.ToJson(new BoundsBox { value = p.boundsValue });
                case SerializedPropertyType.Vector2Int: return JsonUtility.ToJson(new Vector2IntBox { value = p.vector2IntValue });
                case SerializedPropertyType.Vector3Int: return JsonUtility.ToJson(new Vector3IntBox { value = p.vector3IntValue });
                case SerializedPropertyType.RectInt: return JsonUtility.ToJson(new RectIntBox { value = p.rectIntValue });
                case SerializedPropertyType.BoundsInt: return JsonUtility.ToJson(new BoundsIntBox { value = p.boundsIntValue });
                case SerializedPropertyType.LayerMask: return p.intValue.ToString(System.Globalization.CultureInfo.InvariantCulture);
                case SerializedPropertyType.RenderingLayerMask: return p.uintValue.ToString(System.Globalization.CultureInfo.InvariantCulture);
                case SerializedPropertyType.AnimationCurve: return CurveValue(p.animationCurveValue);
                case SerializedPropertyType.Gradient: return GradientValue(p.gradientValue);
                case SerializedPropertyType.ObjectReference: return ObjectIdentity(p.objectReferenceValue);
                case SerializedPropertyType.Enum: return p.enumValueIndex.ToString(System.Globalization.CultureInfo.InvariantCulture);
                case SerializedPropertyType.ArraySize: return p.intValue.ToString(System.Globalization.CultureInfo.InvariantCulture);
                case SerializedPropertyType.ManagedReference: return p.managedReferenceFullTypename + ":" + (p.managedReferenceValue == null ? "null" : p.managedReferenceValue.GetType().FullName);
                default: return p.isArray ? p.arraySize.ToString(System.Globalization.CultureInfo.InvariantCulture) : p.ToString();
            }
        }
        [Serializable] sealed class Vector2Box { public Vector2 value; }
        [Serializable] sealed class Vector3Box { public Vector3 value; }
        [Serializable] sealed class Vector4Box { public Vector4 value; }
        [Serializable] sealed class QuaternionBox { public Quaternion value; }
        [Serializable] sealed class RectBox { public Rect value; }
        [Serializable] sealed class BoundsBox { public Bounds value; }
        [Serializable] sealed class Vector2IntBox { public Vector2Int value; }
        [Serializable] sealed class Vector3IntBox { public Vector3Int value; }
        [Serializable] sealed class RectIntBox { public RectInt value; }
        [Serializable] sealed class BoundsIntBox { public BoundsInt value; }
        static string CurveValue(AnimationCurve curve)
        {
            if (curve == null) return "null";
            var sb = new StringBuilder().Append(curve.preWrapMode).Append('|').Append(curve.postWrapMode);
            foreach (var k in curve.keys) sb.Append('|').Append(k.time.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',').Append(k.value.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',').Append(k.inTangent.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',').Append(k.outTangent.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',').Append(k.inWeight.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',').Append(k.outWeight.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',').Append(k.weightedMode);
            return sb.ToString();
        }
        static string GradientValue(Gradient gradient)
        {
            if (gradient == null) return "null";
            var sb = new StringBuilder().Append(gradient.mode);
            foreach (var k in gradient.colorKeys) sb.Append('|').Append(k.color.r.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',').Append(k.color.g.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',').Append(k.color.b.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',').Append(k.time.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
            foreach (var k in gradient.alphaKeys) sb.Append('|').Append(k.alpha.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',').Append(k.time.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
            return sb.ToString();
        }
        static string ObjectIdentity(UnityEngine.Object asset)
        {
            if (asset == null) return "null";
            string guid; long localId;
            if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(asset, out guid, out localId)) return "unresolved:" + asset.GetEntityId();
            return guid + ":" + localId.ToString(System.Globalization.CultureInfo.InvariantCulture);
        }
        static string GuidOf(UnityEngine.Object asset)
        {
            if (asset == null) return String.Empty;
            return AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(asset));
        }
        static bool VerifySampler(Texture2D t, TextureSpec s)
        {
            return t.width == s.width && t.height == s.height && t.name == s.textureName && t.format == TextureFormat.RGBA32 && t.isReadable &&
                t.isDataSRGB == (s.colorSpace != 0) && t.mipmapCount == 1 && (int)t.filterMode == s.sampling.m_FilterMode && t.anisoLevel == s.sampling.m_Aniso &&
                (int)t.wrapModeU == s.sampling.m_WrapU && (int)t.wrapModeV == s.sampling.m_WrapV &&
                (int)t.wrapModeW == s.sampling.m_WrapW && Mathf.Abs(t.mipMapBias - s.sampling.m_MipBias) < 1e-6f;
        }
        static string TexturePixelsSha(Texture2D t)
        {
            var pixels = t.GetPixels32(); var bytes = new byte[pixels.Length * 4];
            for (int i = 0; i < pixels.Length; i++) { int j = i * 4; bytes[j] = pixels[i].r; bytes[j + 1] = pixels[i].g; bytes[j + 2] = pixels[i].b; bytes[j + 3] = pixels[i].a; }
            return Hash(bytes);
        }
        static string ProjectRoot { get { return Directory.GetParent(Application.dataPath).FullName; } }
        static string Under(string root, string path)
        {
            var r = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            var p = Path.GetFullPath(path);
            Require(p.StartsWith(r, StringComparison.Ordinal), "Path escapes owned project scope: " + path); return p;
        }
        static string AssetsPath(string rel)
        {
            Require(!String.IsNullOrEmpty(rel) && rel.StartsWith("Assets/", StringComparison.Ordinal), "Expected project-owned Assets path");
            return Under(Application.dataPath, Path.Combine(ProjectRoot, rel.Replace('/', Path.DirectorySeparatorChar)));
        }
        static void ValidatePlanScope(TextureMaterialPlan plan, string planPath, string outputPath)
        {
            Require(Application.unityVersion == "6000.6.2f1", "Unexpected native Editor version: " + Application.unityVersion);
            var analysis = Path.Combine(ProjectRoot, "Analysis");
            Under(analysis, planPath); Under(analysis, outputPath);
            Require(plan.assets != null && plan.assets.Length > 0 && plan.assets.Length <= 64, "Plan asset-count limit is 1..64");
            var unique = new Dictionary<string, TextureSpec>(StringComparer.Ordinal); long totalPixels = 0;
            foreach (var a in plan.assets)
            {
                Require(a.texture != null && !String.IsNullOrEmpty(a.sourceTextureId) && a.texture.sourceTextureIdentity != null &&
                        !String.IsNullOrEmpty(a.texture.sourceTextureIdentity.containerSha256) && !String.IsNullOrEmpty(a.texture.sourceTextureIdentity.serializedFile) &&
                        !String.IsNullOrEmpty(a.texture.sourceTextureIdentity.serializedFileSha256) && !String.IsNullOrEmpty(a.texture.sourceTextureIdentity.pathId), "Missing exact source texture tuple");
                Require(a.providerMaterial != null && a.candidateShaderClosure != null, "Missing exact Material/Shader identity tuples");
                AssetsPath(a.providerMaterial.assetPath); AssetsPath(a.candidateShaderClosure.assetPath);
                var rgbaPath = Under(analysis, a.texture.rgbaAbsolutePath);
                Require(a.texture.width > 0 && a.texture.height > 0 && a.texture.sampling != null, "Invalid Texture2D dimensions/sampling tuple");
                var expectedBytes = checked((long)a.texture.width * a.texture.height * 4L);
                var rgba = ReadBounded(rgbaPath, 128 * 1024 * 1024);
                Require(rgba.LongLength == expectedBytes && Hash(rgba) == a.texture.rgbaRawSha256, "Pinned RGBA input bytes/hash differ");
                var serialized = JsonUtility.ToJson(a.texture);
                TextureSpec prior;
                if (unique.TryGetValue(a.sourceTextureId, out prior))
                    Require(JsonUtility.ToJson(prior) == serialized, "Shared Texture2D source identity has conflicting native tuple");
                else { unique.Add(a.sourceTextureId, a.texture); totalPixels += (long)a.texture.width * a.texture.height; }
            }
            Require(unique.Count <= 64 && totalPixels <= 16L * 1024 * 1024, "Plan texture or total pixel budget exceeded");
        }
        static void RunFirst(TextureMaterialPlan plan, TextureMaterialReadback result)
        {
            var copiedShaders = new HashSet<string>(StringComparer.Ordinal); var createdTextures = new Dictionary<string, Texture2D>(StringComparer.Ordinal); var textureTuples = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (var spec in plan.assets)
            {
                var provider = spec.providerMaterial; var shaderClosure = spec.candidateShaderClosure;
                var originalAsset = ReadBounded(provider.absoluteAssetPath, 16 * 1024 * 1024);
                var originalMeta = ReadBounded(provider.absoluteMetaPath, 1024 * 1024);
                Require(Hash(originalAsset) == provider.assetSha256 && Hash(originalMeta) == provider.metaSha256, "Provider Material changed after planning");
                var shaderAsset = ReadBounded(shaderClosure.absoluteAssetPath, 16 * 1024 * 1024); var shaderMeta = ReadBounded(shaderClosure.absoluteMetaPath, 1024 * 1024);
                Require(Hash(shaderAsset) == shaderClosure.assetSha256 && Hash(shaderMeta) == shaderClosure.metaSha256, "Candidate Shader closure changed after planning");
                var shaderTarget = Path.Combine(Application.dataPath, shaderClosure.assetPath.Substring("Assets/".Length)); var shaderTargetMeta = shaderTarget + ".meta";
                if (copiedShaders.Add(shaderClosure.guid))
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(shaderTarget)); Require(!File.Exists(shaderTarget) && !File.Exists(shaderTargetMeta), "Shader closure path already exists");
                    File.Copy(shaderClosure.absoluteAssetPath, shaderTarget); File.Copy(shaderClosure.absoluteMetaPath, shaderTargetMeta);
                }
                Require(Hash(ReadBounded(shaderTarget, 16 * 1024 * 1024)) == shaderClosure.assetSha256 && Hash(ReadBounded(shaderTargetMeta, 1024 * 1024)) == shaderClosure.metaSha256, "Owned Shader target bytes differ from exact closure");
                Directory.CreateDirectory(Path.GetDirectoryName(Path.Combine(Application.dataPath, provider.assetPath.Substring("Assets/".Length))));
                var targetAsset = Path.Combine(Application.dataPath, provider.assetPath.Substring("Assets/".Length));
                var targetMeta = targetAsset + ".meta";
                Require(!File.Exists(targetAsset) && !File.Exists(targetMeta), "Isolated Material path already exists");
                File.Copy(provider.absoluteAssetPath, targetAsset); File.Copy(provider.absoluteMetaPath, targetMeta);
                AssetDatabase.ImportAsset(shaderClosure.assetPath, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
                var targetShader = AssetDatabase.LoadAssetAtPath<Shader>(shaderClosure.assetPath); Require(VerifyAssetIdentity(targetShader, shaderClosure.assetPath, shaderClosure.guid, shaderClosure.localId, typeof(Shader)), "Exact candidate Shader GUID/localID/type closure failed native load");
                var texturePath = "Assets/TextureMaterialGenerated/" + SafeName(spec.sourceTextureId) + ".asset"; AssetsPath(texturePath);
                Directory.CreateDirectory(Path.Combine(Application.dataPath, "TextureMaterialGenerated"));
                Texture2D texture;
                var tupleHash = Hash(Encoding.UTF8.GetBytes(JsonUtility.ToJson(spec.texture)));
                if (createdTextures.TryGetValue(spec.sourceTextureId, out texture))
                    Require(textureTuples[spec.sourceTextureId] == tupleHash, "Shared texture source ID has conflicting native tuple");
                else
                {
                    Require(!File.Exists(Path.Combine(ProjectRoot, texturePath.Replace('/', Path.DirectorySeparatorChar))) &&
                            !File.Exists(Path.Combine(ProjectRoot, (texturePath + ".meta").Replace('/', Path.DirectorySeparatorChar))), "Generated Texture2D target path already exists");
                    texture = CreateTexture(spec.texture, texturePath); createdTextures.Add(spec.sourceTextureId, texture); textureTuples.Add(spec.sourceTextureId, tupleHash);
                }
                AssetDatabase.ImportAsset(provider.assetPath, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
                AssetDatabase.ImportAsset(texturePath, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
                var material = AssetDatabase.LoadAssetAtPath<Material>(provider.assetPath);
                Require(material != null && VerifyAssetIdentity(material, provider.assetPath, provider.guid, provider.localId, typeof(Material)) && material.name == spec.nativeSourceMaterialProperties.m_Name, "Copied Material native identity/type/name mismatch");
                var shaderBefore = material.shader;
                var so = new SerializedObject(material); so.Update(); VerifySourceSavedProperties(so, spec.nativeSourceMaterialProperties); var beforeProperties = SerializedSnapshot(so); var slot = MainTex(so); slot.objectReferenceValue = texture;
                Require(so.ApplyModifiedPropertiesWithoutUndo(), "SerializedObject did not apply selected _MainTex binding");
                EditorUtility.SetDirty(material); AssetDatabase.SaveAssets(); AssetDatabase.Refresh();
                material = AssetDatabase.LoadAssetAtPath<Material>(provider.assetPath);
                texture = AssetDatabase.LoadAssetAtPath<Texture2D>(texturePath);
                Require(material != null && texture != null && AssetDatabase.Contains(material) && AssetDatabase.Contains(texture), "Saved native assets did not reload");
                Require(material.name == spec.nativeSourceMaterialProperties.m_Name && AssetDatabase.GetMainAssetTypeAtPath(provider.assetPath) == typeof(Material), "Native Material type/name differs from source");
                string textureGuid; long textureLocalId; Require(NativeIdentity(texture, out textureGuid, out textureLocalId) && !String.IsNullOrEmpty(textureGuid) && VerifyAssetIdentity(texture, texturePath, textureGuid, textureLocalId, typeof(Texture2D)), "Native Texture2D identity/type failed");
                so = new SerializedObject(material); so.Update(); var reloadedSlot = MainTex(so);
                Require(reloadedSlot.objectReferenceValue == texture, "Reloaded Material _MainTex does not reference selected Texture2D");
                Require(VerifySampler(texture, spec.texture) && TexturePixelsSha(texture) == spec.texture.rgbaRawSha256, "Saved Texture2D pixels or sampling differ");
                var reread = ReadBounded(targetAsset, 16 * 1024 * 1024);
                string actualGuid; long actualLocalId; Require(NativeIdentity(material, out actualGuid, out actualLocalId) && actualGuid == provider.guid && actualLocalId == provider.localId, "Saved Material GUID/localID changed");
                var shaderYamlSame = ExtractShaderGuid(originalAsset) == ExtractShaderGuid(reread) && ExtractShaderGuid(reread) == provider.shaderGuid && material.shader == targetShader && GuidOf(material.shader) == shaderClosure.guid;
                so = new SerializedObject(material); so.Update(); var afterProperties = SerializedSnapshot(so); var propertiesSame = beforeProperties == afterProperties;
                if (!propertiesSame) { File.WriteAllText(Path.Combine(ProjectRoot, "Analysis/material-before.txt"), beforeProperties); File.WriteAllText(Path.Combine(ProjectRoot, "Analysis/material-after.txt"), afterProperties); }
                Require(propertiesSame, "Material saved properties changed beyond selected _MainTex reference");
                var row = new AssetReadback { materialPath = provider.assetPath, texturePath = texturePath, sourceMaterialId = spec.sourceMaterialId, sourceTextureId = spec.sourceTextureId,
                    textureGuid = textureGuid, textureLocalId = textureLocalId, textureType = AssetDatabase.GetMainAssetTypeAtPath(texturePath).FullName, textureName = texture.name,
                    materialGuid = AssetDatabase.AssetPathToGUID(provider.assetPath), materialType = AssetDatabase.GetMainAssetTypeAtPath(provider.assetPath).FullName, materialName = material.name,
                    shaderGuid = shaderClosure.guid, shaderLocalId = shaderClosure.localId, shaderPath = shaderClosure.assetPath, shaderType = AssetDatabase.GetMainAssetTypeAtPath(shaderClosure.assetPath).FullName,
                    materialLocalId = actualLocalId, materialShaderGuid = GuidOf(material.shader), width = texture.width, height = texture.height,
                    filterMode = (int)texture.filterMode, anisoLevel = texture.anisoLevel, wrapModeU = (int)texture.wrapModeU,
                    wrapModeV = (int)texture.wrapModeV, wrapModeW = (int)texture.wrapModeW, mipCount = texture.mipmapCount, sourceColorSpace = spec.texture.colorSpace, textureReadable = texture.isReadable, textureIsDataSRGB = texture.isDataSRGB, textureFormat = texture.format.ToString(), rgbaSha256 = TexturePixelsSha(texture), verified = true, materialPersistent = AssetDatabase.Contains(material),
                    texturePersistent = AssetDatabase.Contains(texture), sourcePropertyArraysPreserved = propertiesSame,
                    shaderReferencePreserved = shaderYamlSame && material.shader == shaderBefore };
                Require(row.materialGuid == provider.guid && row.shaderReferencePreserved, "Material GUID or serialized shader reference changed");
                result.assets = result.assets.Concat(new[] { row }).ToArray();
            }
            AssetDatabase.SaveAssets();
        }
        static void RunCold(TextureMaterialPlan plan, TextureMaterialReadback result)
        {
            foreach (var spec in plan.assets)
            {
                var provider = spec.providerMaterial; var shaderClosure = spec.candidateShaderClosure; var texturePath = "Assets/TextureMaterialGenerated/" + SafeName(spec.sourceTextureId) + ".asset"; AssetsPath(texturePath);
                var shaderAssetBytes = ReadBounded(shaderClosure.absoluteAssetPath, 16 * 1024 * 1024); var shaderMetaBytes = ReadBounded(shaderClosure.absoluteMetaPath, 1024 * 1024);
                Require(Hash(shaderAssetBytes) == shaderClosure.assetSha256 && Hash(shaderMetaBytes) == shaderClosure.metaSha256, "Cold candidate Shader closure bytes changed");
                var shader = AssetDatabase.LoadAssetAtPath<Shader>(shaderClosure.assetPath); Require(VerifyAssetIdentity(shader, shaderClosure.assetPath, shaderClosure.guid, shaderClosure.localId, typeof(Shader)), "Cold Shader closure identity/type mismatch");
                var material = AssetDatabase.LoadAssetAtPath<Material>(provider.assetPath);
                var texture = AssetDatabase.LoadAssetAtPath<Texture2D>(texturePath);
                Require(material != null && texture != null && AssetDatabase.Contains(material) && AssetDatabase.Contains(texture), "Cold process could not load persistent native assets");
                Require(material.name == spec.nativeSourceMaterialProperties.m_Name && VerifyAssetIdentity(material, provider.assetPath, provider.guid, provider.localId, typeof(Material)), "Cold Material identity/type/name mismatch");
                string textureGuid; long textureLocalId; Require(NativeIdentity(texture, out textureGuid, out textureLocalId) && !String.IsNullOrEmpty(textureGuid) && AssetDatabase.GetMainAssetTypeAtPath(texturePath) == typeof(Texture2D), "Cold Texture2D identity/type mismatch");
                var so = new SerializedObject(material); so.Update(); Require(MainTex(so).objectReferenceValue == texture, "Cold process _MainTex binding mismatch"); VerifySourceSavedProperties(so, spec.nativeSourceMaterialProperties);
                string actualGuid; long actualLocalId; Require(NativeIdentity(material, out actualGuid, out actualLocalId) && actualGuid == provider.guid && actualLocalId == provider.localId, "Cold Material GUID/localID mismatch");
                Require(VerifySampler(texture, spec.texture) && TexturePixelsSha(texture) == spec.texture.rgbaRawSha256, "Cold process pixel/sampler mismatch");
                var shaderYaml = ExtractShaderGuid(ReadBounded(Path.Combine(Application.dataPath, provider.assetPath.Substring("Assets/".Length)), 16 * 1024 * 1024));
                var shaderPreserved = shaderYaml == provider.shaderGuid && material.shader == shader && GuidOf(material.shader) == shaderClosure.guid;
                Require(shaderPreserved, "Cold shader pointer/GUID changed");
                result.assets = result.assets.Concat(new[] { new AssetReadback { materialPath = provider.assetPath, texturePath = texturePath, sourceMaterialId = spec.sourceMaterialId, sourceTextureId = spec.sourceTextureId,
                    textureGuid = textureGuid, textureLocalId = textureLocalId, textureType = AssetDatabase.GetMainAssetTypeAtPath(texturePath).FullName, textureName = texture.name,
                    materialGuid = AssetDatabase.AssetPathToGUID(provider.assetPath), materialType = AssetDatabase.GetMainAssetTypeAtPath(provider.assetPath).FullName, materialName = material.name,
                    shaderGuid = shaderClosure.guid, shaderLocalId = shaderClosure.localId, shaderPath = shaderClosure.assetPath, shaderType = AssetDatabase.GetMainAssetTypeAtPath(shaderClosure.assetPath).FullName, materialLocalId = actualLocalId,
                    materialShaderGuid = GuidOf(material.shader), width = texture.width, height = texture.height, filterMode = (int)texture.filterMode,
                    anisoLevel = texture.anisoLevel, wrapModeU = (int)texture.wrapModeU, wrapModeV = (int)texture.wrapModeV, wrapModeW = (int)texture.wrapModeW,
                    mipCount = texture.mipmapCount, sourceColorSpace = spec.texture.colorSpace, textureReadable = texture.isReadable, textureIsDataSRGB = texture.isDataSRGB, textureFormat = texture.format.ToString(), rgbaSha256 = TexturePixelsSha(texture), verified = true, materialPersistent = true, texturePersistent = true,
                    sourcePropertyArraysPreserved = true, shaderReferencePreserved = shaderPreserved } }).ToArray();
            }
        }
        static string ExtractShaderGuid(byte[] yaml)
        {
            var text = Encoding.UTF8.GetString(yaml); var marker = "m_Shader:"; int i = text.IndexOf(marker, StringComparison.Ordinal);
            if (i < 0) return ""; var tail = text.Substring(i); var m = System.Text.RegularExpressions.Regex.Match(tail, @"guid:\s*([0-9a-f]{32})");
            return m.Success ? m.Groups[1].Value : "";
        }
        static string SafeName(string sourceId) { return Hash(Encoding.UTF8.GetBytes(sourceId)).Substring(0, 24); }
        public static void Run()
        {
            var result = new TextureMaterialReadback { status = "failed", assets = new AssetReadback[0] };
            try
            {
                var path = Environment.GetEnvironmentVariable("MONKEY_UNITY_TEXTURE_MATERIAL_PLAN");
                var expected = Environment.GetEnvironmentVariable("MONKEY_UNITY_TEXTURE_MATERIAL_PLAN_SHA256");
                Require(!String.IsNullOrEmpty(path) && !String.IsNullOrEmpty(expected), "Texture/material plan environment is required");
                var raw = ReadBounded(path); Require(Hash(raw) == expected, "Texture/material plan hash mismatch");
                var plan = JsonUtility.FromJson<TextureMaterialPlan>(Encoding.UTF8.GetString(raw));
                Require(plan != null && plan.schemaVersion == 1 && plan.contract == "monkey-unity-prefab-texture-material-plan/1" && plan.assets != null && plan.assets.Length > 0,
                    "Unsupported texture/material plan");
                var outputPath = Environment.GetEnvironmentVariable("MONKEY_UNITY_TEXTURE_MATERIAL_READBACK");
                Require(!String.IsNullOrEmpty(outputPath), "Texture/material readback path is required");
                ValidatePlanScope(plan, path, outputPath);
                if (plan.reopenOnly) RunCold(plan, result); else RunFirst(plan, result);
                result.status = "completed";
            }
            catch (Exception ex) { result.error = ex.ToString(); }
            var finalOutput = Environment.GetEnvironmentVariable("MONKEY_UNITY_TEXTURE_MATERIAL_READBACK");
            if (!String.IsNullOrEmpty(finalOutput))
            {
                var analysis = Path.Combine(ProjectRoot, "Analysis");
                var resolvedOutput = Path.GetFullPath(finalOutput);
                if (resolvedOutput.StartsWith(Path.GetFullPath(analysis).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar, StringComparison.Ordinal))
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(resolvedOutput));
                    File.WriteAllText(resolvedOutput, JsonUtility.ToJson(result, true), new UTF8Encoding(false));
                }
            }
            if (result.status != "completed") throw new InvalidOperationException("Texture/material native verification failed: " + result.error);
        }
    }
}
#endif
