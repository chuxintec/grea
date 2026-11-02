// Native Unity creation and cold-read validation for embedded Sprite assets.
// Source assemblies are never loaded or executed; all inputs are static, hashed evidence.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace MonkeyUnitySource
{
    public static class UnityPrefabEmbeddedAssets
    {
        const string RequiredUnityVersion = "6000.6.2f1";
        const int MaxSprites = 64;
        const long MaxPixels = 16 * 1024 * 1024;
        const int MaxVerticesPerSprite = 10_000;
        const int MaxIndexBytesPerSprite = 60_000;
        const int MaxVertexBytesPerSprite = 1_000_000;
        const int MaxPlanBytes = 128 * 1024 * 1024;
        const int MaxOutputBytes = 16 * 1024 * 1024;
        const int NormalizedSpriteSettingsRaw = 64;
        const double GeometryTolerance = 0.000001d;

        [Serializable]
        public sealed class Plan
        {
            public int schemaVersion;
            public string targetUnityVersion;
            public string outputAbsolute;
            public bool reopenOnly;
            public bool allowSharedTextures;
            public AssetSpec[] assets;
        }

        [Serializable]
        public sealed class AssetSpec
        {
            public string sourceId;
            public string textureSourceId;
            public bool preserveExistingSprite;
            public string expectedSpriteGuid;
            public string expectedSpriteLocalId;
            public string sourceBeforeAssetSha256;
            public string sourceBeforeMetaSha256;
            public int expectedNativeSpriteSettingsRaw;
            public int sourcePackedSettingsRaw;
            public string texturePath;
            public string spritePath;
            public string rgbaPath;
            public string rgbaSha256;
            public string spriteName;
            public string textureName;
            public int width;
            public int height;
            public int sourceColorSpace;
            public int filterMode;
            public int aniso;
            public int wrapU;
            public int wrapV;
            public int wrapW;
            public float mipBias;
            public float pixelsToUnits;
            public int extrude;
            public RectDto rect;
            public Vector2Dto pivot;
            public Vector4Dto border;
            public Vector2Dto offset;
            public RectDto textureRect;
            public Vector2Dto textureRectOffset;
            public Vector2Dto atlasRectOffset;
            public Vector4Dto uvTransform;
            public string vertexBytesBase64;
            public int[] indexBytes;
            public ChannelDto[] channels;
            public SubmeshDto[] subMeshes;
            public Vector2Dto[] meshVertices;
            public int[] triangleIndices;
            public Vector2Dto[] meshUv;
            public PhysicsShapeDto[] physicsShapes;
        }

        [Serializable] public sealed class RectDto { public float x, y, width, height; }
        [Serializable] public sealed class Vector2Dto { public float x, y; }
        [Serializable] public sealed class PhysicsShapeDto { public Vector2Dto[] vertices; }
        [Serializable] public sealed class Vector3Dto { public float x, y, z; }
        [Serializable] public sealed class Vector4Dto { public float x, y, z, w; }
        [Serializable] public sealed class ChannelDto { public int stream, offset, format, dimension; }
        [Serializable] public sealed class BoundsDto { public Vector3Dto m_Center, m_Extent; }
        [Serializable] public sealed class SubmeshDto
        {
            public int firstByte, indexCount, topology, baseVertex, firstVertex, vertexCount;
            public BoundsDto localAABB;
        }

        [Serializable]
        public sealed class ExecutionResult
        {
            public int schemaVersion = 1;
            public string status = "failed";
            public string error = String.Empty;
            public string targetVersion;
            public string planSha256;
            public bool reopenOnly;
            public AssetResult[] assets = new AssetResult[0];
            public string sourceCodeExecution = "not_invoked";
            public string staticProfile;
        }

        [Serializable]
        public sealed class AssetResult
        {
            public string sourceId, textureSourceId;
            public string spritePath, spriteGuid, spriteLocalId, spriteType, spriteName;
            public string spriteIdentityDisposition, beforeSpriteGuid, beforeSpriteLocalId;
            public string sourceBeforeAssetSha256, sourceBeforeMetaSha256;
            public string texturePath, textureGuid, textureLocalId, textureType, textureName;
            public string pixelSha256, vertexBytesSha256, sourceVertexBytesSha256, atlasVertexBytesSha256, indexBytesSha256;
            public int originalPackedSettingsRaw, targetRenderCacheSettingsRaw;
            public bool verified;
            public int width, height, sourceColorSpace, nativeTextureFormat, mipmapCount;
            public int sourceRenderSettingsRaw, targetAtlasCacheSettingsRaw;
            public bool textureIsReadable, textureIsDataSRGB, packed;
            public int filterMode, anisoLevel, wrapModeU, wrapModeV, wrapModeW;
            public float mipBias, pixelsToUnits;
            public int spriteSettingsRaw, atlasSettingsRaw;
            public float spriteDownscaleMultiplier, atlasDownscaleMultiplier;
            public Rect rect, atlasRegion, textureRect;
            public Vector2 pivotPixels, pivotNormalized, textureRectOffset, atlasRectOffset, offset;
            public Vector4 border, uvTransform;
            public Vector2[] vertices = new Vector2[0];
            public Vector2[] uv = new Vector2[0];
            public int[] triangles = new int[0];
            public string[] normalization = new string[0];
        }

        sealed class PreparedAsset
        {
            public AssetSpec spec;
            public string rgbaAbsolute, spriteAssetPath, textureAssetPath;
            public byte[] rgba, vertexBytes, indexBytes;
            public bool hasSerializedIsPolygon;
            public string beforeSpriteGuid, beforeSpriteLocalId;
            public int beforeRenderSettingsRaw, beforeAtlasSettingsRaw;
            public float beforeRenderDownscale, beforeAtlasDownscale;
            public AssetResult result;
        }

        sealed class PreparedTexture
        {
            public string sourceId, assetPath, rgbaPath, rgbaSha256, textureName;
            public int width, height, sourceColorSpace, filterMode, aniso, wrapU, wrapV, wrapW;
            public float mipBias;
            public byte[] rgba;
            public Texture2D texture;
        }

        sealed class PathContext
        {
            public string projectRoot;
            public string planAbsolute;
            public string resultAbsolute;
            public string resultAssetPath;
        }

        public static void Run()
        {
            var result = new ExecutionResult { targetVersion = Application.unityVersion };
            int exitCode = 1;
            PathContext paths = null;
            try
            {
                if (!String.Equals(Application.unityVersion, RequiredUnityVersion, StringComparison.Ordinal))
                    throw new InvalidOperationException("Unity Editor identity differs: expected=" + RequiredUnityVersion + ", actual=" + Application.unityVersion);
                paths = ResolvePlanAndOutputPaths();
                byte[] planBytes = ReadBounded(paths.planAbsolute, MaxPlanBytes);
                result.planSha256 = Sha256(planBytes);
                string expectedSha = RequiredEnvironment("MONKEY_UNITY_EMBEDDED_PLAN_SHA256");
                if (!IsSha256(expectedSha) || !String.Equals(result.planSha256, expectedSha, StringComparison.Ordinal))
                    throw new InvalidOperationException("Plan SHA256 differs from MONKEY_UNITY_EMBEDDED_PLAN_SHA256");

                string json = new UTF8Encoding(false, true).GetString(planBytes);
                Plan plan = JsonUtility.FromJson<Plan>(json);
                if (plan == null) throw new InvalidOperationException("Embedded asset plan JSON is null or malformed");
                result.reopenOnly = plan.reopenOnly;
                if (plan.schemaVersion != 1) throw new InvalidOperationException("schemaVersion 1 required");
                if (!String.Equals(plan.targetUnityVersion, RequiredUnityVersion, StringComparison.Ordinal))
                    throw new InvalidOperationException("Plan targetUnityVersion differs from the required Editor");
                ValidateOutputPath(plan.outputAbsolute, paths);
                bool hasPreservedSprite = plan.assets != null && plan.assets.Any(item => item != null && item.preserveExistingSprite);
                result.staticProfile = hasPreservedSprite
                    ? "Texture2D: decoded CPU-readable RGBA32/no-mipmap derived texture; preserved Sprite identity with source-verified full unrotated atlas-region geometry; only m_RD.texture and m_AtlasRD.texture rebound"
                    : "Texture2D: decoded RGBA32, CPU-readable, no mipmaps; new embedded Sprite asset; source compression/atlas metadata not claimed";

                List<PreparedAsset> assets = PreflightAssets(paths.projectRoot, plan, plan.reopenOnly);
                result.assets = assets.Select(NewAssetResult).ToArray();
                for (int i = 0; i < assets.Count; i++) assets[i].result = result.assets[i];

                if (!plan.reopenOnly)
                {
                    EnsureAssetDirectories(paths.projectRoot, assets);
                    CreateTextureAssets(assets);
                    CreateSpriteAssets(assets);
                    AssetDatabase.SaveAssets();
                    AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
                    UnloadCreatedObjects(assets);
                }

                VerifyAllAssets(paths.projectRoot, assets);
                if (result.assets.Length == 0 || result.assets.Any(asset => asset == null || !asset.verified) || !String.IsNullOrEmpty(result.error))
                    throw new InvalidOperationException("Execution cannot complete until every AssetResult is verified and error-free");
                result.status = "completed";
                exitCode = 0;
            }
            catch (Exception error)
            {
                result.status = "failed";
                result.error = error.ToString();
                Debug.LogError("Embedded native asset execution failed: " + error);
                exitCode = 1;
            }
            finally
            {
                if (paths != null && !String.IsNullOrEmpty(paths.resultAbsolute))
                {
                    try
                    {
                        WriteResult(paths.resultAbsolute, result);
                    }
                    catch (Exception outputError)
                    {
                        Debug.LogError("Could not write embedded native asset result: " + outputError);
                        result.status = "failed";
                        result.error = outputError.ToString();
                        exitCode = 1;
                    }
                }
                EditorApplication.Exit(exitCode);
            }
        }

        static PathContext ResolvePlanAndOutputPaths()
        {
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            EnsureNoSymlink(projectRoot, projectRoot, "Unity project root");
            string planEnv = RequiredEnvironment("MONKEY_UNITY_EMBEDDED_PLAN");
            if (!Path.IsPathRooted(planEnv)) throw new InvalidOperationException("MONKEY_UNITY_EMBEDDED_PLAN must be absolute");
            string planAbsolute = Path.GetFullPath(planEnv);
            RequireInside(projectRoot, planAbsolute, "Plan input");
            ValidateAnalysisJsonPath(projectRoot, planAbsolute, "Plan input");
            EnsureNoSymlink(projectRoot, planAbsolute, "Plan input");
            if (!File.Exists(planAbsolute)) throw new InvalidOperationException("Embedded asset plan file is absent");

            // Plan JSON is hash checked before use. This bounded parse only locates the explicit result path.
            byte[] bytes = ReadBounded(planAbsolute, MaxPlanBytes);
            Plan plan;
            try { plan = JsonUtility.FromJson<Plan>(new UTF8Encoding(false, true).GetString(bytes)); }
            catch (Exception error) { throw new InvalidOperationException("Embedded asset plan JSON cannot be decoded", error); }
            if (plan == null || String.IsNullOrWhiteSpace(plan.outputAbsolute))
                throw new InvalidOperationException("Plan outputAbsolute result path is missing");
            if (!Path.IsPathRooted(plan.outputAbsolute)) throw new InvalidOperationException("outputAbsolute must be an absolute result JSON path");
            string resultAbsolute = Path.GetFullPath(plan.outputAbsolute);
            RequireInside(projectRoot, resultAbsolute, "Result output");
            ValidateAnalysisJsonPath(projectRoot, resultAbsolute, "Result output");
            EnsureNoSymlink(projectRoot, resultAbsolute, "Result output");
            if (String.Equals(planAbsolute, resultAbsolute, StringComparison.Ordinal))
                throw new InvalidOperationException("Plan input and result output must be different files");
            return new PathContext { projectRoot = projectRoot, planAbsolute = planAbsolute,
                resultAbsolute = resultAbsolute, resultAssetPath = ToAssetPath(projectRoot, resultAbsolute) };
        }

        static void ValidateOutputPath(string planOutput, PathContext paths)
        {
            if (!Path.IsPathRooted(planOutput) || !String.Equals(Path.GetFullPath(planOutput), paths.resultAbsolute, StringComparison.Ordinal))
                throw new InvalidOperationException("outputAbsolute changed between bounded path validation and plan execution");
        }

        static List<PreparedAsset> PreflightAssets(string projectRoot, Plan plan, bool reopenOnly)
        {
            if (plan.assets == null || plan.assets.Length == 0 || plan.assets.Length > MaxSprites)
                throw new InvalidOperationException("assets count must be in 1..64");
            var result = new List<PreparedAsset>(plan.assets.Length);
            var sourceIds = new HashSet<string>(StringComparer.Ordinal);
            var spritePaths = new HashSet<string>(StringComparer.Ordinal);
            var texturePathsBySource = new Dictionary<string, string>(StringComparer.Ordinal);
            var textureSourcesByPath = new Dictionary<string, string>(StringComparer.Ordinal);
            var texturesBySource = new Dictionary<string, PreparedTexture>(StringComparer.Ordinal);
            var newTexturePathsChecked = new HashSet<string>(StringComparer.Ordinal);
            long totalPixels = 0;
            foreach (AssetSpec spec in plan.assets)
            {
                ValidateSpecPresence(spec);
                if (!sourceIds.Add(spec.sourceId)) throw new InvalidOperationException("Duplicate asset sourceId: " + spec.sourceId);
                string spriteAssetPath = ValidateAssetOutputPath(projectRoot, spec.spritePath, "spritePath");
                string textureAssetPath = ValidateAssetOutputPath(projectRoot, spec.texturePath, "texturePath");
                if (String.Equals(spriteAssetPath, textureAssetPath, StringComparison.Ordinal))
                    throw new InvalidOperationException("Sprite and Texture asset paths must differ: " + spec.sourceId);
                if (textureSourcesByPath.ContainsKey(spriteAssetPath))
                    throw new InvalidOperationException("Sprite path collides with another planned Texture path: " + spriteAssetPath);
                if (spritePaths.Contains(textureAssetPath))
                    throw new InvalidOperationException("Texture path collides with another planned Sprite path: " + textureAssetPath);
                if (!spritePaths.Add(spriteAssetPath)) throw new InvalidOperationException("Duplicate spritePath: " + spriteAssetPath);
                string existingTextureSource;
                if (textureSourcesByPath.TryGetValue(textureAssetPath, out existingTextureSource) && existingTextureSource != spec.textureSourceId)
                    throw new InvalidOperationException("Distinct textureSourceId values share one target texture path");
                textureSourcesByPath[textureAssetPath] = spec.textureSourceId;
                string oldTexturePath;
                if (texturePathsBySource.TryGetValue(spec.textureSourceId, out oldTexturePath) && oldTexturePath != textureAssetPath)
                    throw new InvalidOperationException("One textureSourceId maps to multiple texturePath values: " + spec.textureSourceId);
                texturePathsBySource[spec.textureSourceId] = textureAssetPath;

                if (spec.width <= 0 || spec.height <= 0) throw new InvalidOperationException("Texture dimensions must be positive: " + spec.sourceId);
                long pixels = checked((long)spec.width * spec.height);
                string rgbaAbsolute = ValidateAnalysisInputPath(projectRoot, spec.rgbaPath, "rgbaPath");
                byte[] rgba = ReadBounded(rgbaAbsolute, checked((int)(pixels * 4L)));
                if (rgba.LongLength != pixels * 4L) throw new InvalidOperationException("RGBA byte count differs from width*height*4: " + spec.sourceId);
                string rgbaSha = Sha256(rgba);
                if (!IsSha256(spec.rgbaSha256) || !String.Equals(rgbaSha, spec.rgbaSha256, StringComparison.Ordinal))
                    throw new InvalidOperationException("RGBA SHA256 differs for " + spec.textureSourceId);

                var texture = new PreparedTexture {
                    sourceId = spec.textureSourceId, assetPath = textureAssetPath, rgbaPath = rgbaAbsolute,
                    rgbaSha256 = rgbaSha, textureName = spec.textureName, width = spec.width, height = spec.height,
                    sourceColorSpace = spec.sourceColorSpace, filterMode = spec.filterMode, aniso = spec.aniso,
                    wrapU = spec.wrapU, wrapV = spec.wrapV, wrapW = spec.wrapW, mipBias = spec.mipBias, rgba = rgba
                };
                PreparedTexture priorTexture;
                bool firstTextureUse = !texturesBySource.TryGetValue(spec.textureSourceId, out priorTexture);
                if (!firstTextureUse)
                {
                    if (!plan.allowSharedTextures)
                        throw new InvalidOperationException("Repeated textureSourceId requires Plan.allowSharedTextures=true: " + spec.textureSourceId);
                    VerifySameTextureSpec(priorTexture, spec, textureAssetPath, rgbaAbsolute, rgbaSha, rgba);
                    rgba = priorTexture.rgba;
                }
                else
                {
                    totalPixels = checked(totalPixels + pixels);
                    if (totalPixels > MaxPixels) throw new InvalidOperationException("Aggregate texture pixels exceed 16,000,000");
                    texturesBySource.Add(spec.textureSourceId, texture);
                }
                if (!reopenOnly)
                {
                    if (spec.preserveExistingSprite) VerifyPreservedSpriteProvenance(projectRoot, spec, spriteAssetPath, reopenOnly);
                    else EnsureNewAssetPath(projectRoot, spec.spritePath, spriteAssetPath);
                    if (firstTextureUse && newTexturePathsChecked.Add(textureAssetPath))
                        EnsureNewAssetPath(projectRoot, spec.texturePath, textureAssetPath);
                }
                else if (spec.preserveExistingSprite)
                {
                    VerifyPreservedSpriteProvenance(projectRoot, spec, spriteAssetPath, reopenOnly);
                }
                else
                {
                    if (String.IsNullOrEmpty(AssetDatabase.AssetPathToGUID(spriteAssetPath)))
                        throw new InvalidOperationException("Read-only reopen Sprite is absent: " + spriteAssetPath);
                }
                byte[] vertexBytes, indexBytes;
                ValidateAndDecodeMesh(spec, out vertexBytes, out indexBytes);
                ValidateAtlasRegionProfile(spec);
                var prepared = new PreparedAsset { spec = spec, rgbaAbsolute = rgbaAbsolute,
                    spriteAssetPath = spriteAssetPath, textureAssetPath = textureAssetPath,
                    rgba = rgba, vertexBytes = vertexBytes, indexBytes = indexBytes };
                if (spec.preserveExistingSprite)
                {
                    if (reopenOnly) VerifyPreservedSpriteProvenance(projectRoot, spec, spriteAssetPath, true);
                    Sprite preserved = AssetDatabase.LoadAssetAtPath<Sprite>(spriteAssetPath);
                    if (preserved == null) throw new InvalidOperationException("Preserved Sprite asset is absent/not a Sprite: " + spriteAssetPath);
                    ReadNativeIdentity(preserved, spriteAssetPath, out prepared.beforeSpriteGuid, out prepared.beforeSpriteLocalId, out _);
                    VerifyPreservedSpriteIdentity(spec, prepared.beforeSpriteGuid, prepared.beforeSpriteLocalId);
                    VerifyPreservedSpriteGeometryBeforeBind(preserved, prepared);
                }
                else if (reopenOnly && AssetDatabase.LoadAssetAtPath<Sprite>(spriteAssetPath) == null)
                {
                    throw new InvalidOperationException("Read-only reopen Sprite is absent/not a Sprite: " + spriteAssetPath);
                }
                result.Add(prepared);
            }
            if (!String.IsNullOrEmpty(plan.outputAbsolute))
            {
                string resultAbsolute = Path.GetFullPath(plan.outputAbsolute);
                foreach (PreparedAsset asset in result)
                    if (String.Equals(resultAbsolute, Path.GetFullPath(Path.Combine(projectRoot, asset.spriteAssetPath.Replace('/', Path.DirectorySeparatorChar))), StringComparison.Ordinal) ||
                        String.Equals(resultAbsolute, Path.GetFullPath(Path.Combine(projectRoot, asset.textureAssetPath.Replace('/', Path.DirectorySeparatorChar))), StringComparison.Ordinal))
                        throw new InvalidOperationException("Result output cannot overwrite a candidate asset");
            }
            return result;
        }

        static bool IsGuid32(string value)
        {
            if (String.IsNullOrEmpty(value) || value.Length != 32) return false;
            for (int i = 0; i < value.Length; i++)
                if (!((value[i] >= '0' && value[i] <= '9') || (value[i] >= 'a' && value[i] <= 'f'))) return false;
            return true;
        }

        static string HashFile(string path)
        {
            using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
            using (SHA256 sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", String.Empty).ToLowerInvariant();
        }

        static void VerifySameTextureSpec(PreparedTexture previous, AssetSpec current, string assetPath,
                                          string rgbaPath, string rgbaSha, byte[] rgba)
        {
            if (!String.Equals(previous.assetPath, assetPath, StringComparison.Ordinal) ||
                !String.Equals(previous.rgbaPath, rgbaPath, StringComparison.Ordinal) ||
                !String.Equals(previous.rgbaSha256, rgbaSha, StringComparison.Ordinal) ||
                !String.Equals(previous.textureName, current.textureName, StringComparison.Ordinal) ||
                previous.width != current.width || previous.height != current.height ||
                previous.sourceColorSpace != current.sourceColorSpace || previous.filterMode != current.filterMode ||
                previous.aniso != current.aniso || previous.wrapU != current.wrapU || previous.wrapV != current.wrapV ||
                previous.wrapW != current.wrapW || !previous.mipBias.Equals(current.mipBias) ||
                !BytesEqual(previous.rgba, rgba))
                throw new InvalidOperationException("Shared textureSourceId has inconsistent texture path, bytes, identity, or sampler fields: " + current.textureSourceId);
        }

        static void VerifyPreservedSpriteProvenance(string projectRoot, AssetSpec spec, string assetPath, bool reopenOnly)
        {
            string absolute = Path.GetFullPath(Path.Combine(projectRoot, assetPath.Replace('/', Path.DirectorySeparatorChar)));
            string meta = absolute + ".meta";
            EnsureNoSymlink(projectRoot, absolute, "Preserved Sprite asset");
            EnsureNoSymlink(projectRoot, meta, "Preserved Sprite meta");
            if (!File.Exists(absolute) || !File.Exists(meta))
                throw new InvalidOperationException("Preserved Sprite asset and meta must both exist: " + assetPath);
            if (!reopenOnly && !String.Equals(HashFile(absolute), spec.sourceBeforeAssetSha256, StringComparison.Ordinal))
                throw new InvalidOperationException("Pre-copied Sprite asset SHA256 differs from sourceBeforeAssetSha256: " + spec.sourceId);
            if (!String.Equals(HashFile(meta), spec.sourceBeforeMetaSha256, StringComparison.Ordinal))
                throw new InvalidOperationException("Preserved Sprite meta SHA256 differs from sourceBeforeMetaSha256: " + spec.sourceId);
            string guid = AssetDatabase.AssetPathToGUID(assetPath);
            if (!String.Equals(guid, spec.expectedSpriteGuid, StringComparison.Ordinal))
                throw new InvalidOperationException("Preserved Sprite GUID differs from pinned expectedSpriteGuid: " + spec.sourceId);
            Sprite sprite = AssetDatabase.LoadAssetAtPath<Sprite>(assetPath);
            if (sprite == null) throw new InvalidOperationException("Preserved Sprite path does not load as UnityEngine.Sprite: " + assetPath);
            string actualGuid, actualLocalId, actualType;
            ReadNativeIdentity(sprite, assetPath, out actualGuid, out actualLocalId, out actualType);
            VerifyPreservedSpriteIdentity(spec, actualGuid, actualLocalId);
            if (!String.Equals(actualType, "UnityEngine.Sprite", StringComparison.Ordinal))
                throw new InvalidOperationException("Preserved asset type is not UnityEngine.Sprite: " + spec.sourceId);
        }

        static void VerifyPreservedSpriteIdentity(AssetSpec spec, string guid, string localId)
        {
            if (!String.Equals(guid, spec.expectedSpriteGuid, StringComparison.Ordinal) ||
                !String.Equals(localId, spec.expectedSpriteLocalId, StringComparison.Ordinal))
                throw new InvalidOperationException("Preserved Sprite GUID/localID differs from pinned identity: " + spec.sourceId);
        }

        static void VerifyPreservedSpriteGeometryBeforeBind(Sprite sprite, PreparedAsset asset)
        {
            AssetSpec spec = asset.spec;
            Rect sourceRect = ToRect(spec.rect);
            if (!String.Equals(sprite.name, spec.spriteName, StringComparison.Ordinal) ||
                !Close(sprite.rect, sourceRect, GeometryTolerance) ||
                !Close(sprite.pixelsPerUnit, spec.pixelsToUnits, GeometryTolerance) ||
                !Close(sprite.pivot, new Vector2(spec.pivot.x * spec.rect.width, spec.pivot.y * spec.rect.height), GeometryTolerance) ||
                !Close(sprite.border, ToVector4(spec.border), GeometryTolerance) ||
                !Close(sprite.textureRectOffset, Vector2.zero, GeometryTolerance))
                throw new InvalidOperationException("Preserved Sprite public source geometry/name differs before texture repair: " + spec.sourceId);
            Vector2[] vertices = sprite.vertices;
            Vector2[] uv = sprite.uv;
            int[] triangles = sprite.triangles.Select(value => (int)value).ToArray();
            if (vertices.Length != spec.meshVertices.Length || uv.Length != spec.meshUv.Length || !triangles.SequenceEqual(spec.triangleIndices))
                throw new InvalidOperationException("Preserved Sprite public mesh counts differ before texture repair: " + spec.sourceId);
            for (int i = 0; i < vertices.Length; i++)
                if (!vertices[i].Equals(ToVector2(spec.meshVertices[i])))
                    throw new InvalidOperationException("Preserved Sprite source vertex differs before texture repair at " + i + ": " + spec.sourceId);
            for (int i = 0; i < uv.Length; i++)
                // A missing source texture makes Unity's public UV getter
                // return the empty cache. Source serialized mesh/transform is
                // still checked below; repaired/save/cold UVs are mandatory.
                if (sprite.texture == null ? uv[i] != Vector2.zero : !Close(uv[i], ToVector2(spec.meshUv[i]), GeometryTolerance))
                    throw new InvalidOperationException("Preserved Sprite source UV differs before texture repair at " + i + ": actual=" + uv[i].ToString("R") +
                        " expected=" + ToVector2(spec.meshUv[i]).ToString("R") + " texture=" +
                        (sprite.texture == null ? "null" : sprite.texture.name + " " + sprite.texture.width + "x" + sprite.texture.height) + ": " + spec.sourceId);

            var so = new SerializedObject(sprite);
            so.UpdateIfRequiredOrScript();
            if (!Close(FindRequired(so, "m_Rect").rectValue, sourceRect, GeometryTolerance) ||
                !Close(FindRequired(so, "m_Pivot").vector2Value, ToVector2(spec.pivot), GeometryTolerance) ||
                !Close(FindRequired(so, "m_Offset").vector2Value, Vector2.zero, GeometryTolerance) ||
                !Close(FindRequired(so, "m_Border").vector4Value, ToVector4(spec.border), GeometryTolerance) ||
                !Close(FindRequired(so, "m_PixelsToUnits").floatValue, spec.pixelsToUnits, GeometryTolerance) ||
                !Close(FindRequired(so, "m_RD.textureRect").rectValue, ToRect(spec.rect), GeometryTolerance) ||
                !Close(FindRequired(so, "m_RD.textureRectOffset").vector2Value, Vector2.zero, GeometryTolerance) ||
                !Close(FindRequired(so, "m_RD.atlasRectOffset").vector2Value, ToVector2(spec.atlasRectOffset), GeometryTolerance) ||
                !Close(FindRequired(so, "m_RD.uvTransform").vector4Value, ToVector4(spec.uvTransform), GeometryTolerance))
                throw new InvalidOperationException("Preserved Sprite serialized geometry differs before texture repair: " + spec.sourceId);
            asset.beforeRenderSettingsRaw = FindRequired(so, "m_RD.settingsRaw").intValue;
            asset.beforeAtlasSettingsRaw = FindRequired(so, "m_AtlasRD.settingsRaw").intValue;
            int expectedBeforeSettings = sprite.texture == null ? spec.expectedNativeSpriteSettingsRaw : spec.sourcePackedSettingsRaw;
            if (asset.beforeRenderSettingsRaw != expectedBeforeSettings)
                throw new InvalidOperationException("Preserved Sprite native m_RD.settingsRaw=" + asset.beforeRenderSettingsRaw +
                    " m_AtlasRD.settingsRaw=" + asset.beforeAtlasSettingsRaw + " expected=" + expectedBeforeSettings + ": " + spec.sourceId);
            asset.beforeRenderDownscale = FindRequired(so, "m_RD.downscaleMultiplier").floatValue;
            asset.beforeAtlasDownscale = FindRequired(so, "m_AtlasRD.downscaleMultiplier").floatValue;
            if (!Finite(asset.beforeRenderDownscale) || !Finite(asset.beforeAtlasDownscale))
                throw new InvalidOperationException("Preserved Sprite downscale multiplier is non-finite: " + spec.sourceId);
            VerifyRenderData(so, "m_RD", null, asset, false);
            VerifyRenderData(so, "m_AtlasRD", null, asset, false);
            VerifyPreservedPhysicsShapes(sprite, spec);
        }

        static void VerifyPreservedPhysicsShapes(Sprite sprite, AssetSpec spec)
        {
            if (spec.physicsShapes == null || spec.physicsShapes.Length > 64 || sprite.GetPhysicsShapeCount() != spec.physicsShapes.Length)
                throw new InvalidOperationException("Preserved source physics shape count differs: " + spec.sourceId);
            int total = 0;
            for (int i = 0; i < spec.physicsShapes.Length; i++)
            {
                var expected = spec.physicsShapes[i];
                if (expected == null || expected.vertices == null || (total += expected.vertices.Length) > 10000)
                    throw new InvalidOperationException("Preserved source physics shape budget/layout differs: " + spec.sourceId);
                var actual = new List<Vector2>();
                sprite.GetPhysicsShape(i, actual);
                if (actual.Count != expected.vertices.Length)
                    throw new InvalidOperationException("Preserved source physics vertex count differs: " + spec.sourceId);
                for (int j = 0; j < actual.Count; j++)
                    if (expected.vertices[j] == null || !Finite(expected.vertices[j].x) || !Finite(expected.vertices[j].y) ||
                        !actual[j].Equals(ToVector2(expected.vertices[j])))
                        throw new InvalidOperationException("Preserved source physics vertex differs: " + spec.sourceId + "[" + i + "][" + j + "]");
            }
        }

        static void ValidateSpecPresence(AssetSpec spec)
        {
            if (spec == null || String.IsNullOrWhiteSpace(spec.sourceId) || String.IsNullOrWhiteSpace(spec.textureSourceId) ||
                String.IsNullOrWhiteSpace(spec.spriteName) || String.IsNullOrWhiteSpace(spec.textureName) ||
                String.IsNullOrWhiteSpace(spec.texturePath) || String.IsNullOrWhiteSpace(spec.spritePath) || String.IsNullOrWhiteSpace(spec.rgbaPath))
                throw new InvalidOperationException("AssetSpec identity/path/name is incomplete");
            if (spec.sourceColorSpace != 0 && spec.sourceColorSpace != 1)
                throw new InvalidOperationException("sourceColorSpace must be 0 (linear) or 1 (sRGB): " + spec.sourceId);
            if (!Enum.IsDefined(typeof(FilterMode), spec.filterMode)) throw new InvalidOperationException("Unsupported filterMode: " + spec.sourceId);
            if (!Enum.IsDefined(typeof(TextureWrapMode), spec.wrapU) || !Enum.IsDefined(typeof(TextureWrapMode), spec.wrapV) ||
                !Enum.IsDefined(typeof(TextureWrapMode), spec.wrapW))
                throw new InvalidOperationException("Unsupported texture wrap mode: " + spec.sourceId);
            if (spec.aniso < 0 || spec.aniso > 16) throw new InvalidOperationException("aniso must be within 0..16: " + spec.sourceId);
            if (!Finite(spec.mipBias) || Math.Abs(spec.mipBias) > 100f) throw new InvalidOperationException("mipBias is invalid: " + spec.sourceId);
            if (!Finite(spec.pixelsToUnits) || spec.pixelsToUnits <= 0f) throw new InvalidOperationException("pixelsToUnits must be finite and positive: " + spec.sourceId);
            if (spec.extrude < 0 || spec.extrude > 65535) throw new InvalidOperationException("extrude must be within 0..65535: " + spec.sourceId);
            RequireRect(spec.rect, "rect", spec.sourceId); RequireRect(spec.textureRect, "textureRect", spec.sourceId);
            RequireVector(spec.pivot, "pivot", spec.sourceId); RequireVector(spec.offset, "offset", spec.sourceId);
            RequireVector(spec.textureRectOffset, "textureRectOffset", spec.sourceId); RequireVector(spec.atlasRectOffset, "atlasRectOffset", spec.sourceId);
            RequireVector(spec.border, "border", spec.sourceId); RequireVector(spec.uvTransform, "uvTransform", spec.sourceId);
            if (spec.pivot.x < 0f || spec.pivot.x > 1f || spec.pivot.y < 0f || spec.pivot.y > 1f)
                throw new InvalidOperationException("Pivot must be normalized into 0..1: " + spec.sourceId);
            if (spec.border.x < 0f || spec.border.y < 0f || spec.border.z < 0f || spec.border.w < 0f)
                throw new InvalidOperationException("Sprite border cannot be negative: " + spec.sourceId);
            if (spec.rect.width <= 0f || spec.rect.height <= 0f || spec.textureRect.width <= 0f || spec.textureRect.height <= 0f)
                throw new InvalidOperationException("Sprite rect and textureRect must have positive size: " + spec.sourceId);
            if (spec.rect.x < 0f || spec.rect.y < 0f || spec.rect.x + spec.rect.width > spec.width || spec.rect.y + spec.rect.height > spec.height ||
                spec.textureRect.x < 0f || spec.textureRect.y < 0f ||
                spec.textureRect.x + spec.textureRect.width > spec.width || spec.textureRect.y + spec.textureRect.height > spec.height)
                throw new InvalidOperationException("Sprite rect/textureRect escapes the source texture bounds: " + spec.sourceId);
            if (spec.border.x + spec.border.z > spec.rect.width || spec.border.y + spec.border.w > spec.rect.height)
                throw new InvalidOperationException("Sprite border exceeds the source rect: " + spec.sourceId);
            if (spec.preserveExistingSprite)
            {
                if (!IsGuid32(spec.expectedSpriteGuid) || String.IsNullOrWhiteSpace(spec.expectedSpriteLocalId) ||
                    !IsSha256(spec.sourceBeforeAssetSha256) || !IsSha256(spec.sourceBeforeMetaSha256))
                    throw new InvalidOperationException("Preserved Sprite requires pinned expected identity and pre-copy asset/meta SHA256 values: " + spec.sourceId);
                long localId;
                if (!Int64.TryParse(spec.expectedSpriteLocalId, NumberStyles.Integer, CultureInfo.InvariantCulture, out localId))
                    throw new InvalidOperationException("expectedSpriteLocalId is not an invariant integer: " + spec.sourceId);
            }
            else if (!String.IsNullOrEmpty(spec.expectedSpriteGuid) || !String.IsNullOrEmpty(spec.expectedSpriteLocalId) ||
                     !String.IsNullOrEmpty(spec.sourceBeforeAssetSha256) || !String.IsNullOrEmpty(spec.sourceBeforeMetaSha256))
            {
                throw new InvalidOperationException("New Sprite creation cannot carry preserved-existing Sprite identity fields: " + spec.sourceId);
            }
            if (spec.meshVertices == null || spec.meshUv == null || spec.triangleIndices == null || spec.indexBytes == null ||
                spec.channels == null || spec.subMeshes == null)
                throw new InvalidOperationException("Sprite native mesh DTO arrays must be present (empty arrays are allowed): " + spec.sourceId);
            if (spec.meshVertices.Length != spec.meshUv.Length) throw new InvalidOperationException("meshVertices and meshUv lengths differ: " + spec.sourceId);
            if (spec.meshVertices.Length > MaxVerticesPerSprite) throw new InvalidOperationException("Sprite vertex count exceeds 10,000: " + spec.sourceId);
            if (spec.indexBytes.Length > MaxIndexBytesPerSprite) throw new InvalidOperationException("Sprite index bytes exceed 60,000: " + spec.sourceId);
            if ((spec.indexBytes.Length & 1) != 0) throw new InvalidOperationException("Sprite index buffer must be 16-bit aligned: " + spec.sourceId);
            if (spec.triangleIndices.Length % 3 != 0) throw new InvalidOperationException("Sprite triangleIndices count must be divisible by 3: " + spec.sourceId);
        }

        static void ValidateAtlasRegionProfile(AssetSpec spec)
        {
            if (spec.preserveExistingSprite && (spec.sourcePackedSettingsRaw != 67 || spec.expectedNativeSpriteSettingsRaw != 3139))
                throw new InvalidOperationException("Only source packed flags 67 and observed Unity 6000.6 native cache flags 3139 are verified: " + spec.sourceId);
            if (!spec.preserveExistingSprite) return;
            if (!Close(spec.rect.x, spec.textureRect.x, GeometryTolerance) ||
                !Close(spec.rect.y, spec.textureRect.y, GeometryTolerance) ||
                !Close(spec.rect.width, spec.textureRect.width, GeometryTolerance) ||
                !Close(spec.rect.height, spec.textureRect.height, GeometryTolerance))
                throw new InvalidOperationException("Atlas-region profile requires rect and RD.textureRect to be the same full unrotated region: " + spec.sourceId);
            if (!Close(spec.textureRect.width, spec.rect.width, GeometryTolerance) ||
                !Close(spec.textureRect.height, spec.rect.height, GeometryTolerance))
                throw new InvalidOperationException("Atlas-region profile does not support trimmed Sprite dimensions: " + spec.sourceId);
            if (!Close(spec.textureRectOffset.x, 0f, GeometryTolerance) || !Close(spec.textureRectOffset.y, 0f, GeometryTolerance) ||
                !Close(spec.offset.x, 0f, GeometryTolerance) || !Close(spec.offset.y, 0f, GeometryTolerance))
                throw new InvalidOperationException("Atlas-region profile requires zero trim/offset: " + spec.sourceId);
            if (spec.uvTransform.x <= 0f || spec.uvTransform.z <= 0f)
                throw new InvalidOperationException("Atlas-region profile requires unrotated positive-axis UV scale: " + spec.sourceId);
            for (int i = 0; i < spec.meshVertices.Length; i++)
            {
                double u = (spec.meshVertices[i].x * spec.uvTransform.x + spec.uvTransform.y) / spec.width;
                double v = (spec.meshVertices[i].y * spec.uvTransform.z + spec.uvTransform.w) / spec.height;
                if (!Close(spec.meshUv[i].x, (float)u, GeometryTolerance) || !Close(spec.meshUv[i].y, (float)v, GeometryTolerance))
                    throw new InvalidOperationException("Atlas-region profile UVs are not the exact unrotated RD transform of source vertices: " + spec.sourceId + "[" + i + "]");
            }
        }

        static void ValidateAndDecodeMesh(AssetSpec spec, out byte[] vertexBytes, out byte[] indexBytes)
        {
            try { vertexBytes = Convert.FromBase64String(spec.vertexBytesBase64 ?? String.Empty); }
            catch (FormatException error) { throw new InvalidOperationException("vertexBytesBase64 is malformed: " + spec.sourceId, error); }
            if (vertexBytes.Length > MaxVertexBytesPerSprite) throw new InvalidOperationException("Source vertex byte buffer exceeds 1,000,000 bytes: " + spec.sourceId);
            if ((vertexBytes.Length & 3) != 0) throw new InvalidOperationException("Source mesh data is not 32-bit aligned: " + spec.sourceId);
            if (vertexBytes.Length == 0 && spec.meshVertices.Length != 0)
                throw new InvalidOperationException("Non-empty mesh has an empty source vertex byte buffer: " + spec.sourceId);
            indexBytes = new byte[spec.indexBytes.Length];
            for (int i = 0; i < spec.indexBytes.Length; i++)
            {
                if (spec.indexBytes[i] < 0 || spec.indexBytes[i] > 255)
                    throw new InvalidOperationException("indexBytes contains a value outside 0..255: " + spec.sourceId);
                indexBytes[i] = (byte)spec.indexBytes[i];
            }
            foreach (Vector2Dto vertex in spec.meshVertices)
                if (vertex == null || !Finite(vertex.x) || !Finite(vertex.y)) throw new InvalidOperationException("Mesh vertex is null/non-finite: " + spec.sourceId);
            foreach (Vector2Dto uv in spec.meshUv)
                if (uv == null || !Finite(uv.x) || !Finite(uv.y)) throw new InvalidOperationException("Mesh UV is null/non-finite: " + spec.sourceId);
            foreach (int triangle in spec.triangleIndices)
                if (triangle < 0 || triangle >= spec.meshVertices.Length) throw new InvalidOperationException("Triangle index is outside source mesh: " + spec.sourceId);
            ValidateChannelsAndSourceVertexBytes(spec, vertexBytes);
            ValidateSubmeshesAndSourceIndices(spec, indexBytes);
        }

        static void ValidateChannelsAndSourceVertexBytes(AssetSpec spec, byte[] bytes)
        {
            if (spec.channels.Length > 14) throw new InvalidOperationException("Vertex channel count exceeds Unity Sprite channel schema: " + spec.sourceId);
            var strides = new int[4];
            var occupied = new List<Tuple<int, int, int>>();
            for (int i = 0; i < spec.channels.Length; i++)
            {
                ChannelDto channel = spec.channels[i];
                if (channel == null || channel.stream < 0 || channel.stream > 3 || channel.offset < 0 || channel.offset > 256 ||
                    channel.dimension < 0 || channel.dimension > 4 || channel.format < 0 || channel.format > 10)
                    throw new InvalidOperationException("Vertex channel DTO is outside bounded Unity format range: " + spec.sourceId + "[" + i + "]");
                if (channel.dimension == 0) continue;
                int formatSize = VertexFormatSize(channel.format);
                int end = checked(channel.offset + channel.dimension * formatSize);
                if (end > 256) throw new InvalidOperationException("Vertex channel exceeds bounded stream stride: " + spec.sourceId);
                foreach (Tuple<int, int, int> prior in occupied)
                    if (prior.Item1 == channel.stream && channel.offset < prior.Item3 && end > prior.Item2)
                        throw new InvalidOperationException("Overlapping populated vertex channels: " + spec.sourceId);
                occupied.Add(Tuple.Create(channel.stream, channel.offset, end));
                strides[channel.stream] = Math.Max(strides[channel.stream], end);
            }
            if (spec.meshVertices.Length == 0)
            {
                if (bytes.Length != 0) throw new InvalidOperationException("Empty source mesh has non-empty vertex bytes: " + spec.sourceId);
                return;
            }
            if (spec.channels.Length == 0 || spec.channels[0] == null || spec.channels[0].dimension < 2 ||
                spec.channels[0].format != 0 || spec.channels[0].stream < 0 || spec.channels[0].stream > 3)
                throw new InvalidOperationException("Sprite position channel must be Float32 with at least two dimensions: " + spec.sourceId);
            int maxStream = occupied.Max(row => row.Item1);
            int[] streamOffsets = new int[maxStream + 1];
            int cursor = 0;
            for (int stream = 0; stream <= maxStream; stream++)
            {
                if (strides[stream] <= 0) throw new InvalidOperationException("Vertex streams must be contiguous and populated: " + spec.sourceId);
                if (stream > 0) cursor = Align(cursor, 16);
                streamOffsets[stream] = cursor;
                cursor = checked(cursor + spec.meshVertices.Length * strides[stream]);
            }
            if (cursor != bytes.Length)
                throw new InvalidOperationException("Vertex byte count differs from bounded channel layout: " + spec.sourceId + "; expected=" + cursor + "; actual=" + bytes.Length);
            ChannelDto position = spec.channels[0];
            int positionStride = strides[position.stream];
            for (int i = 0; i < spec.meshVertices.Length; i++)
            {
                int start = checked(streamOffsets[position.stream] + i * positionStride + position.offset);
                float x = ReadFloat32(bytes, start);
                float y = ReadFloat32(bytes, start + 4);
                if (!Close(x, spec.meshVertices[i].x, GeometryTolerance) || !Close(y, spec.meshVertices[i].y, GeometryTolerance))
                    throw new InvalidOperationException("Source 32-bit vertex bytes differ from meshVertices at index " + i + ": " + spec.sourceId);
            }
        }

        static void ValidateSubmeshesAndSourceIndices(AssetSpec spec, byte[] bytes)
        {
            if (spec.meshVertices.Length == 0)
            {
                if (spec.subMeshes.Length != 0 || spec.triangleIndices.Length != 0 || bytes.Length != 0)
                    throw new InvalidOperationException("Empty Sprite mesh contains submesh/index data: " + spec.sourceId);
                return;
            }
            if (spec.subMeshes.Length == 0) throw new InvalidOperationException("Non-empty Sprite mesh has no submesh: " + spec.sourceId);
            var decoded = new List<int>();
            foreach (SubmeshDto submesh in spec.subMeshes)
            {
                if (submesh == null || submesh.localAABB == null || submesh.localAABB.m_Center == null || submesh.localAABB.m_Extent == null)
                    throw new InvalidOperationException("Submesh fields are incomplete: " + spec.sourceId);
                if (submesh.firstByte < 0 || (submesh.firstByte & 1) != 0 || submesh.indexCount < 0 || (submesh.indexCount % 3) != 0 || submesh.baseVertex < 0 ||
                    submesh.firstVertex < 0 || submesh.vertexCount < 0 || submesh.firstVertex + submesh.vertexCount > spec.meshVertices.Length)
                    throw new InvalidOperationException("Submesh integer fields are invalid: " + spec.sourceId);
                if (submesh.topology != 0) throw new InvalidOperationException("Only triangle Sprite submeshes are supported: " + spec.sourceId);
                if ((long)submesh.firstByte + (long)submesh.indexCount * 2L > bytes.Length)
                    throw new InvalidOperationException("Submesh index range exceeds source index buffer: " + spec.sourceId);
                RequireVector(submesh.localAABB.m_Center, "localAABB.m_Center", spec.sourceId);
                RequireVector(submesh.localAABB.m_Extent, "localAABB.m_Extent", spec.sourceId);
                if (submesh.localAABB.m_Extent.x < 0f || submesh.localAABB.m_Extent.y < 0f || submesh.localAABB.m_Extent.z < 0f)
                    throw new InvalidOperationException("Submesh AABB extent cannot be negative: " + spec.sourceId);
                for (int i = 0; i < submesh.indexCount; i++)
                {
                    int offset = submesh.firstByte + i * 2;
                    int rawIndex = bytes[offset] | (bytes[offset + 1] << 8);
                    int index = checked(rawIndex + submesh.baseVertex);
                    if (index < 0 || index >= spec.meshVertices.Length)
                        throw new InvalidOperationException("Source index buffer points outside meshVertices: " + spec.sourceId);
                    decoded.Add(index);
                }
            }
            if (!decoded.SequenceEqual(spec.triangleIndices))
                throw new InvalidOperationException("Source index bytes/submesh ranges differ from triangleIndices: " + spec.sourceId);
        }

        static int VertexFormatSize(int format)
        {
            switch (format)
            {
                case 0: return 4; // Float32
                case 1: return 2; // Float16
                case 2: case 3: case 6: case 7: return 1;
                case 4: case 5: case 8: case 9: return 2;
                case 10: case 11: return 4;
                default: throw new InvalidOperationException("Unknown vertex attribute format: " + format);
            }
        }

        static void EnsureAssetDirectories(string projectRoot, List<PreparedAsset> assets)
        {
            var directories = new HashSet<string>(StringComparer.Ordinal);
            foreach (PreparedAsset asset in assets)
            {
                directories.Add(AssetDirectory(asset.spriteAssetPath));
                directories.Add(AssetDirectory(asset.textureAssetPath));
            }
            foreach (string directory in directories.OrderBy(x => x.Length).ThenBy(x => x, StringComparer.Ordinal))
            {
                string current = "Assets";
                string[] parts = directory.Split('/');
                for (int i = 1; i < parts.Length; i++)
                {
                    string next = current + "/" + parts[i];
                    if (!AssetDatabase.IsValidFolder(next))
                    {
                        string absolute = Path.GetFullPath(Path.Combine(projectRoot, next.Replace('/', Path.DirectorySeparatorChar)));
                        RequireInside(projectRoot, absolute, "Asset output directory");
                        EnsureNoSymlink(projectRoot, absolute, "Asset output directory");
                        if (File.Exists(absolute)) throw new InvalidOperationException("Asset output directory is occupied by a file: " + next);
                        Directory.CreateDirectory(absolute);
                        AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
                        if (!AssetDatabase.IsValidFolder(next)) throw new InvalidOperationException("Unity could not register output folder: " + next);
                    }
                    current = next;
                }
            }
        }

        static void CreateTextureAssets(List<PreparedAsset> assets)
        {
            var bySourceId = new Dictionary<string, PreparedTexture>(StringComparer.Ordinal);
            foreach (PreparedAsset asset in assets)
            {
                string key = asset.spec.textureSourceId;
                if (bySourceId.ContainsKey(key)) continue;
                var prepared = new PreparedTexture {
                    sourceId = key, assetPath = asset.textureAssetPath, rgba = asset.rgba,
                    rgbaPath = asset.rgbaAbsolute, rgbaSha256 = asset.spec.rgbaSha256,
                    textureName = asset.spec.textureName, width = asset.spec.width, height = asset.spec.height,
                    sourceColorSpace = asset.spec.sourceColorSpace, filterMode = asset.spec.filterMode,
                    aniso = asset.spec.aniso, wrapU = asset.spec.wrapU, wrapV = asset.spec.wrapV,
                    wrapW = asset.spec.wrapW, mipBias = asset.spec.mipBias
                };
                bool linear = prepared.sourceColorSpace == 0;
                var texture = new Texture2D(prepared.width, prepared.height, TextureFormat.RGBA32, false, linear);
                texture.name = prepared.textureName;
                texture.LoadRawTextureData(prepared.rgba);
                texture.filterMode = (FilterMode)prepared.filterMode;
                texture.anisoLevel = prepared.aniso;
                texture.wrapModeU = (TextureWrapMode)prepared.wrapU;
                texture.wrapModeV = (TextureWrapMode)prepared.wrapV;
                texture.wrapModeW = (TextureWrapMode)prepared.wrapW;
                texture.mipMapBias = prepared.mipBias;
                texture.Apply(false, false);
                AssetDatabase.CreateAsset(texture, prepared.assetPath);
                texture.name = prepared.textureName;
                EditorUtility.SetDirty(texture);
                prepared.texture = texture;
                bySourceId.Add(key, prepared);
            }
            foreach (PreparedAsset asset in assets)
            {
                PreparedTexture texture = bySourceId[asset.spec.textureSourceId];
                asset.result.texturePath = texture.assetPath;
                asset.result.textureName = texture.textureName;
                asset.result.textureType = "UnityEngine.Texture2D";
            }
        }

        static void CreateSpriteAssets(List<PreparedAsset> assets)
        {
            var textureBySource = new Dictionary<string, Texture2D>(StringComparer.Ordinal);
            foreach (PreparedAsset asset in assets)
            {
                if (!textureBySource.ContainsKey(asset.spec.textureSourceId))
                    textureBySource.Add(asset.spec.textureSourceId,
                        AssetDatabase.LoadAssetAtPath<Texture2D>(asset.textureAssetPath));
            }
            foreach (PreparedAsset asset in assets)
            {
                AssetSpec spec = asset.spec;
                Texture2D texture = textureBySource[spec.textureSourceId];
                if (texture == null) throw new InvalidOperationException("Created Texture2D asset could not be loaded: " + spec.textureSourceId);
                if (spec.preserveExistingSprite)
                {
                    Sprite preserved = AssetDatabase.LoadAssetAtPath<Sprite>(asset.spriteAssetPath);
                    if (preserved == null) throw new InvalidOperationException("Preserved Sprite disappeared before texture repair: " + spec.sourceId);
                    string guid, localId, type;
                    ReadNativeIdentity(preserved, asset.spriteAssetPath, out guid, out localId, out type);
                    VerifyPreservedSpriteIdentity(spec, guid, localId);
                    if (!String.Equals(type, "UnityEngine.Sprite", StringComparison.Ordinal))
                        throw new InvalidOperationException("Preserved Sprite runtime type changed before binding: " + spec.sourceId);
                    var serialized = new SerializedObject(preserved);
                    serialized.UpdateIfRequiredOrScript();
                    SetRequiredReference(serialized, "m_RD.texture", texture);
                    SetRequiredReference(serialized, "m_AtlasRD.texture", texture);
                    if (!serialized.ApplyModifiedPropertiesWithoutUndo()) serialized.UpdateIfRequiredOrScript();
                    EditorUtility.SetDirty(preserved);
                    asset.result.spritePath = asset.spriteAssetPath;
                    asset.result.spriteName = preserved.name;
                    asset.result.spriteType = "UnityEngine.Sprite";
                    asset.result.spriteIdentityDisposition = "preserved-existing-provider";
                    continue;
                }
                var sprite = Sprite.Create(texture, ToRect(spec.rect), ToVector2(spec.pivot), spec.pixelsToUnits,
                    (uint)spec.extrude, SpriteMeshType.Tight, ToVector4(spec.border), false);
                if (sprite == null) throw new InvalidOperationException("Sprite.Create returned null: " + spec.sourceId);
                sprite.name = spec.spriteName;
                AssetDatabase.CreateAsset(sprite, asset.spriteAssetPath);
                sprite.name = spec.spriteName;
                WriteSpriteSourceData(sprite, texture, asset);
                EditorUtility.SetDirty(sprite);
                asset.result.spritePath = asset.spriteAssetPath;
                asset.result.spriteName = spec.spriteName;
                asset.result.spriteType = "UnityEngine.Sprite";
                asset.result.spriteIdentityDisposition = "new-native-derived";
            }
        }

        static void WriteSpriteSourceData(Sprite sprite, Texture2D texture, PreparedAsset asset)
        {
            AssetSpec spec = asset.spec;
            var serialized = new SerializedObject(sprite);
            serialized.UpdateIfRequiredOrScript();
            SetRequiredRect(serialized, "m_Rect", ToRect(spec.rect));
            SetRequiredVector2(serialized, "m_Pivot", ToVector2(spec.pivot));
            SetRequiredVector4(serialized, "m_Border", ToVector4(spec.border));
            SetRequiredFloat(serialized, "m_PixelsToUnits", spec.pixelsToUnits);
            SetRequiredInt(serialized, "m_Extrude", spec.extrude);
            SetRequiredVector2(serialized, "m_Offset", ToVector2(spec.offset));
            asset.hasSerializedIsPolygon = SetOptionalFalse(serialized, "m_IsPolygon");
            SetEmptyArrayIfPresent(serialized, "m_Bones");
            SetEmptyArrayIfPresent(serialized, "m_PhysicsShape");
            SetEmptyArrayIfPresent(serialized, "m_ScriptableObjects");
            SetEmptyArrayIfPresent(serialized, "m_AtlasTags");
            SetNullReferenceIfPresent(serialized, "m_SpriteAtlas");

            WriteRenderData(serialized, "m_RD", texture, spec, asset.vertexBytes, asset.indexBytes);
            WriteRenderData(serialized, "m_AtlasRD", texture, spec, asset.vertexBytes, asset.indexBytes);
            if (!serialized.ApplyModifiedPropertiesWithoutUndo()) serialized.UpdateIfRequiredOrScript();
            // Construction can carry transient native cache flags. Acceptance
            // checks the actual saved/reloaded object and the independent cold
            // object below, without masking or relaxing the source fields.
        }

        static void WriteRenderData(SerializedObject serialized, string prefix, Texture2D texture,
                                    AssetSpec spec, byte[] vertexBytes, byte[] indexBytes)
        {
            SetRequiredReference(serialized, prefix + ".texture", texture);
            SetRequiredReference(serialized, prefix + ".alphaTexture", null);
            SetRequiredRect(serialized, prefix + ".textureRect", ToRect(spec.textureRect));
            SetRequiredVector2(serialized, prefix + ".textureRectOffset", ToVector2(spec.textureRectOffset));
            SetRequiredVector2(serialized, prefix + ".atlasRectOffset", ToVector2(spec.atlasRectOffset));
            SetRequiredVector4(serialized, prefix + ".uvTransform", ToVector4(spec.uvTransform));
            if (prefix == "m_RD") SetRequiredInt(serialized, prefix + ".settingsRaw", NormalizedSpriteSettingsRaw);
            SetRequiredFloat(serialized, prefix + ".downscaleMultiplier", 1f);

            SerializedProperty secondary = FindRequired(serialized, prefix + ".secondaryTextures");
            SetEmptyArray(secondary, prefix + ".secondaryTextures");
            FindRequired(serialized, prefix + ".m_VertexData");
            SetRequiredInt(serialized, prefix + ".m_VertexData.m_VertexCount", spec.meshVertices.Length);
            WriteChannels(FindRequired(serialized, prefix + ".m_VertexData.m_Channels"), spec.channels, prefix);
            WriteByteArray(FindRequired(serialized, prefix + ".m_VertexData.m_DataSize"), vertexBytes, prefix + ".m_VertexData.m_DataSize");
            WriteByteArray(FindRequired(serialized, prefix + ".m_IndexBuffer"), indexBytes, prefix + ".m_IndexBuffer");
            WriteSubmeshes(FindRequired(serialized, prefix + ".m_SubMeshes"), spec.subMeshes, prefix);
            SetEmptyArray(FindRequired(serialized, prefix + ".m_Bindpose"), prefix + ".m_Bindpose");
            WriteEmptyBlendShapes(serialized, prefix + ".m_BlendShapes");
        }

        static void WriteChannels(SerializedProperty array, ChannelDto[] channels, string prefix)
        {
            SetArraySize(array, channels.Length, prefix + ".m_VertexData.m_Channels");
            for (int i = 0; i < channels.Length; i++)
            {
                SerializedProperty item = array.GetArrayElementAtIndex(i);
                SetRelativeInt(item, "stream", channels[i].stream, prefix + ".m_Channels[" + i + "].stream");
                SetRelativeInt(item, "offset", channels[i].offset, prefix + ".m_Channels[" + i + "].offset");
                SetRelativeInt(item, "format", channels[i].format, prefix + ".m_Channels[" + i + "].format");
                SetRelativeInt(item, "dimension", channels[i].dimension, prefix + ".m_Channels[" + i + "].dimension");
            }
        }

        static void WriteByteArray(SerializedProperty array, byte[] bytes, string path)
        {
            SetArraySize(array, bytes.Length, path);
            for (int i = 0; i < bytes.Length; i++)
            {
                SerializedProperty item = array.GetArrayElementAtIndex(i);
                RequirePropertyType(item, SerializedPropertyType.Integer, path + "[" + i + "]");
                item.intValue = bytes[i];
            }
        }

        static void WriteSubmeshes(SerializedProperty array, SubmeshDto[] submeshes, string prefix)
        {
            SetArraySize(array, submeshes.Length, prefix + ".m_SubMeshes");
            for (int i = 0; i < submeshes.Length; i++)
            {
                SubmeshDto source = submeshes[i];
                SerializedProperty item = array.GetArrayElementAtIndex(i);
                string path = prefix + ".m_SubMeshes[" + i + "]";
                SetRelativeInt(item, "firstByte", source.firstByte, path + ".firstByte");
                SetRelativeInt(item, "indexCount", source.indexCount, path + ".indexCount");
                SetRelativeInt(item, "topology", source.topology, path + ".topology");
                SetRelativeInt(item, "baseVertex", source.baseVertex, path + ".baseVertex");
                SetRelativeInt(item, "firstVertex", source.firstVertex, path + ".firstVertex");
                SetRelativeInt(item, "vertexCount", source.vertexCount, path + ".vertexCount");
                SetRelativeVector3(item, "localAABB.m_Center", ToVector3(source.localAABB.m_Center), path + ".localAABB.m_Center");
                SetRelativeVector3(item, "localAABB.m_Extent", ToVector3(source.localAABB.m_Extent), path + ".localAABB.m_Extent");
            }
        }

        static void WriteEmptyBlendShapes(SerializedObject serialized, string path)
        {
            SerializedProperty blendShapes = FindRequired(serialized, path);
            foreach (string field in new[] { "vertices", "shapes", "channels", "fullWeights" })
                SetEmptyArray(FindRelativeRequired(blendShapes, field, path + "." + field), path + "." + field);
        }

        static void UnloadCreatedObjects(List<PreparedAsset> assets)
        {
            foreach (PreparedAsset asset in assets)
            {
                Sprite sprite = AssetDatabase.LoadAssetAtPath<Sprite>(asset.spriteAssetPath);
                if (sprite != null) Resources.UnloadAsset(sprite);
            }
            foreach (string path in assets.Select(x => x.textureAssetPath).Distinct(StringComparer.Ordinal))
            {
                Texture2D texture = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
                if (texture != null) Resources.UnloadAsset(texture);
            }
        }

        static void VerifyAllAssets(string projectRoot, List<PreparedAsset> assets)
        {
            foreach (PreparedAsset asset in assets)
            {
                Texture2D texture = AssetDatabase.LoadAssetAtPath<Texture2D>(asset.textureAssetPath);
                Sprite sprite = AssetDatabase.LoadAssetAtPath<Sprite>(asset.spriteAssetPath);
                if (texture == null) throw new InvalidOperationException("Texture2D asset could not be loaded: " + asset.spec.textureSourceId);
                if (sprite == null) throw new InvalidOperationException("Sprite asset could not be loaded: " + asset.spec.sourceId);
                VerifyTexture(asset, texture);
                VerifySprite(asset, texture, sprite);
                ReadNativeIdentity(sprite, asset.spriteAssetPath, out asset.result.spriteGuid, out asset.result.spriteLocalId, out asset.result.spriteType);
                ReadNativeIdentity(texture, asset.textureAssetPath, out asset.result.textureGuid, out asset.result.textureLocalId, out asset.result.textureType);
                if (asset.spec.preserveExistingSprite)
                {
                    VerifyPreservedSpriteIdentity(asset.spec, asset.result.spriteGuid, asset.result.spriteLocalId);
                    string meta = Path.GetFullPath(Path.Combine(projectRoot, asset.spriteAssetPath.Replace('/', Path.DirectorySeparatorChar))) + ".meta";
                    if (!File.Exists(meta) || !String.Equals(HashFile(meta), asset.spec.sourceBeforeMetaSha256, StringComparison.Ordinal))
                        throw new InvalidOperationException("Preserved Sprite .meta changed during repair/reopen: " + asset.spec.sourceId);
                }
                asset.result.verified = true;
            }
        }

        static void VerifyTexture(PreparedAsset asset, Texture2D texture)
        {
            AssetSpec spec = asset.spec;
            if (AssetDatabase.GetAssetPath(texture) != asset.textureAssetPath)
                throw new InvalidOperationException("Texture asset path differs: " + spec.textureSourceId);
            if (texture.width != spec.width || texture.height != spec.height)
                throw new InvalidOperationException("Texture dimensions differ: " + spec.textureSourceId);
            if (texture.format != TextureFormat.RGBA32)
                throw new InvalidOperationException("Normalized Texture2D format is not RGBA32: " + spec.textureSourceId);
            if (texture.mipmapCount != 1) throw new InvalidOperationException("Normalized Texture2D must have exactly one mip level: " + spec.textureSourceId);
            if (!texture.isReadable) throw new InvalidOperationException("Normalized Texture2D is not CPU-readable: " + spec.textureSourceId);
            if (texture.isDataSRGB != (spec.sourceColorSpace == 1))
                throw new InvalidOperationException("Texture color-space bit differs from sourceColorSpace normalization: " + spec.textureSourceId);
            if (texture.filterMode != (FilterMode)spec.filterMode || texture.anisoLevel != spec.aniso ||
                texture.wrapModeU != (TextureWrapMode)spec.wrapU || texture.wrapModeV != (TextureWrapMode)spec.wrapV ||
                texture.wrapModeW != (TextureWrapMode)spec.wrapW || !Close(texture.mipMapBias, spec.mipBias, GeometryTolerance))
                throw new InvalidOperationException("Texture sampler settings differ: " + spec.textureSourceId);
            string pixelsHash = Sha256(ReadRgbaPixels(texture));
            if (!String.Equals(pixelsHash, spec.rgbaSha256, StringComparison.Ordinal))
                throw new InvalidOperationException("Reloaded texture RGBA pixel SHA256 differs: " + spec.textureSourceId);
            asset.result.width = texture.width;
            asset.result.height = texture.height;
            asset.result.sourceColorSpace = spec.sourceColorSpace;
            asset.result.nativeTextureFormat = (int)texture.format;
            asset.result.mipmapCount = texture.mipmapCount;
            asset.result.textureIsReadable = texture.isReadable;
            asset.result.textureIsDataSRGB = texture.isDataSRGB;
            asset.result.filterMode = (int)texture.filterMode;
            asset.result.anisoLevel = texture.anisoLevel;
            asset.result.wrapModeU = (int)texture.wrapModeU;
            asset.result.wrapModeV = (int)texture.wrapModeV;
            asset.result.wrapModeW = (int)texture.wrapModeW;
            asset.result.mipBias = texture.mipMapBias;
            asset.result.pixelSha256 = pixelsHash;
            asset.result.textureName = texture.name;
            if (!String.Equals(texture.name, spec.textureName, StringComparison.Ordinal))
                throw new InvalidOperationException("Texture name differs after CreateAsset/save/reload: " + spec.textureSourceId);
        }

        static void VerifySprite(PreparedAsset asset, Texture2D texture, Sprite sprite)
        {
            AssetSpec spec = asset.spec;
            if (AssetDatabase.GetAssetPath(sprite) != asset.spriteAssetPath)
                throw new InvalidOperationException("Sprite asset path differs: " + spec.sourceId);
            if (!String.Equals(sprite.name, spec.spriteName, StringComparison.Ordinal))
                throw new InvalidOperationException("Sprite name differs after CreateAsset/save/reload: " + spec.sourceId);
            if (sprite.texture != texture || !String.Equals(AssetDatabase.GetAssetPath(sprite.texture), asset.textureAssetPath, StringComparison.Ordinal))
                throw new InvalidOperationException("Sprite.texture does not resolve to the planned texture asset: " + spec.sourceId);
            if (!spec.preserveExistingSprite && sprite.packed)
                throw new InvalidOperationException("Candidate Sprite unexpectedly packed into an atlas: " + spec.sourceId);
            if (!Close(sprite.pixelsPerUnit, spec.pixelsToUnits, GeometryTolerance))
                throw new InvalidOperationException("Sprite pixelsPerUnit differs: " + spec.sourceId);
            Rect expectedRect = ToRect(spec.rect);
            if (!Close(sprite.rect, expectedRect, GeometryTolerance)) throw new InvalidOperationException("Sprite rect differs: " + spec.sourceId);
            Vector2 expectedPivotPixels = new Vector2(spec.pivot.x * spec.rect.width, spec.pivot.y * spec.rect.height);
            if (!Close(sprite.pivot, expectedPivotPixels, GeometryTolerance))
                throw new InvalidOperationException("Sprite public pixel pivot differs: " + spec.sourceId);
            if (!Close(sprite.border, ToVector4(spec.border), GeometryTolerance))
                throw new InvalidOperationException("Sprite border differs: " + spec.sourceId);
            Rect nativeTextureRect;
            try { nativeTextureRect = sprite.textureRect; }
            catch (Exception error) { throw new InvalidOperationException("Sprite.textureRect is unavailable for un-atlased asset " + spec.sourceId, error); }
            if (!Close(nativeTextureRect, ToRect(spec.textureRect), GeometryTolerance))
                throw new InvalidOperationException("Sprite public textureRect differs: " + spec.sourceId);
            if (!Close(sprite.textureRectOffset, ToVector2(spec.textureRectOffset), GeometryTolerance))
                throw new InvalidOperationException("Sprite public textureRectOffset differs: " + spec.sourceId);

            Vector2[] vertices = sprite.vertices;
            Vector2[] uv = sprite.uv;
            ushort[] rawTriangles = sprite.triangles;
            if (vertices.Length != spec.meshVertices.Length || uv.Length != spec.meshUv.Length || rawTriangles.Length != spec.triangleIndices.Length)
                throw new InvalidOperationException("Public Sprite mesh array lengths differ: " + spec.sourceId);
            for (int i = 0; i < vertices.Length; i++)
                if (!vertices[i].Equals(ToVector2(spec.meshVertices[i])))
                    throw new InvalidOperationException("Public Sprite vertex differs at index " + i + ": " + spec.sourceId);
            for (int i = 0; i < uv.Length; i++)
                if (!Close(uv[i], ToVector2(spec.meshUv[i]), GeometryTolerance))
                    throw new InvalidOperationException("Public Sprite UV differs at index " + i + ": " + spec.sourceId);
            var triangles = rawTriangles.Select(value => (int)value).ToArray();
            if (!triangles.SequenceEqual(spec.triangleIndices))
                throw new InvalidOperationException("Public Sprite triangleIndices differ: " + spec.sourceId);

            var so = new SerializedObject(sprite);
            so.UpdateIfRequiredOrScript();
            if (!Close(FindRequired(so, "m_Rect").rectValue, expectedRect, GeometryTolerance))
                throw new InvalidOperationException("Serialized m_Rect differs: " + spec.sourceId);
            if (!Close(FindRequired(so, "m_Pivot").vector2Value, ToVector2(spec.pivot), GeometryTolerance))
                throw new InvalidOperationException("Serialized normalized m_Pivot differs: " + spec.sourceId);
            if (!Close(FindRequired(so, "m_Offset").vector2Value, ToVector2(spec.offset), GeometryTolerance))
                throw new InvalidOperationException("Serialized m_Offset differs: " + spec.sourceId);
            if (!Close(FindRequired(so, "m_Border").vector4Value, ToVector4(spec.border), GeometryTolerance))
                throw new InvalidOperationException("Serialized m_Border differs: " + spec.sourceId);
            if (!Close(FindRequired(so, "m_PixelsToUnits").floatValue, spec.pixelsToUnits, GeometryTolerance))
                throw new InvalidOperationException("Serialized m_PixelsToUnits differs: " + spec.sourceId);
            if (FindRequired(so, "m_Extrude").intValue != spec.extrude)
                throw new InvalidOperationException("Serialized m_Extrude differs: " + spec.sourceId);
            SerializedProperty polygon = so.FindProperty("m_IsPolygon");
            asset.hasSerializedIsPolygon = polygon != null;
            if (polygon != null)
            {
                RequirePropertyType(polygon, SerializedPropertyType.Boolean, "m_IsPolygon");
                if (polygon.boolValue) throw new InvalidOperationException("Target Sprite m_IsPolygon must be false for the normalized tight-mesh profile: " + spec.sourceId);
            }
            VerifyEmptyArrayIfPresent(so, "m_Bones");
            if (spec.preserveExistingSprite) VerifyPreservedPhysicsShapes(sprite, spec);
            else VerifyEmptyArrayIfPresent(so, "m_PhysicsShape");
            VerifyEmptyArrayIfPresent(so, "m_ScriptableObjects");
            VerifyNullReferenceIfPresent(so, "m_SpriteAtlas");
            VerifyRenderData(so, "m_RD", texture, asset);
            VerifyRenderData(so, "m_AtlasRD", texture, asset);

            asset.result.spriteName = sprite.name;
            asset.result.packed = sprite.packed;
            asset.result.rect = sprite.rect;
            asset.result.textureRect = nativeTextureRect;
            asset.result.pivotPixels = sprite.pivot;
            asset.result.pivotNormalized = ToVector2(spec.pivot);
            asset.result.textureRectOffset = sprite.textureRectOffset;
            asset.result.atlasRectOffset = ToVector2(spec.atlasRectOffset);
            asset.result.atlasRegion = ToRect(spec.rect);
            asset.result.offset = ToVector2(spec.offset);
            asset.result.border = sprite.border;
            asset.result.pixelsToUnits = sprite.pixelsPerUnit;
            asset.result.uvTransform = ToVector4(spec.uvTransform);
            asset.result.vertices = vertices;
            asset.result.uv = uv;
            asset.result.triangles = triangles;
            asset.result.sourceVertexBytesSha256 = Sha256(asset.vertexBytes);
            asset.result.vertexBytesSha256 = Sha256(ReadByteArray(FindRequired(so, "m_RD.m_VertexData.m_DataSize")));
            asset.result.atlasVertexBytesSha256 = Sha256(ReadByteArray(FindRequired(so, "m_AtlasRD.m_VertexData.m_DataSize")));
            asset.result.sourceRenderSettingsRaw = FindRequired(so, "m_RD.settingsRaw").intValue;
            asset.result.originalPackedSettingsRaw = spec.preserveExistingSprite ? spec.sourcePackedSettingsRaw : 64;
            asset.result.targetRenderCacheSettingsRaw = asset.result.sourceRenderSettingsRaw;
            asset.result.targetAtlasCacheSettingsRaw = FindRequired(so, "m_AtlasRD.settingsRaw").intValue;
            asset.result.spriteSettingsRaw = asset.result.sourceRenderSettingsRaw;
            asset.result.atlasSettingsRaw = asset.result.targetAtlasCacheSettingsRaw;
            asset.result.spriteDownscaleMultiplier = FindRequired(so, "m_RD.downscaleMultiplier").floatValue;
            asset.result.atlasDownscaleMultiplier = FindRequired(so, "m_AtlasRD.downscaleMultiplier").floatValue;
            asset.result.indexBytesSha256 = Sha256(asset.indexBytes);
            asset.result.normalization = spec.preserveExistingSprite
                ? new[] {
                    "Texture bytes are a decoded, CPU-readable derived RGBA32/no-mipmap asset; a source unreadable flag is normalized for exact pixel verification, and source compressed storage is not preserved.",
                    "Existing provider Sprite .asset and .meta identity are preserved; only m_RD.texture and m_AtlasRD.texture references are rebound.",
                    "Atlas-region representation is limited to a full, unrotated rectangle with zero trim offsets; source public packed state is not claimed equivalent.",
                    "Original packed settingsRaw 67 is retained separately from observed missing-texture cache flags 3139; repaired m_RD must return to 67 and m_AtlasRD target cache is checked independently. Legacy sourceRenderSettingsRaw reports native m_RD.",
                    "Source position/index bytes and vertex padding remain exact; only an empty source UV cache may materialize source-derived UV values."
                }
                : new[] {
                    "Texture bytes normalized to native Texture2D RGBA32, CPU-readable, no mipmaps; original compressed source storage/import flags are not preserved.",
                    "The empty source UV cache may materialize source-derived UVs; source position/index bytes and padding remain exact.",
                    "m_AtlasRD is target-only cache metadata: its native flags are recorded, not asserted source-equivalent. Source m_RD.settingsRaw remains exactly 64.",
                    "Source-origin readable=false is normalized to a CPU-readable derived RGBA32 asset so exact pixel verification can run.",
                    "Sprite and Texture asset GUID/localID values are newly generated by Unity; original source object identities are retained separately by sourceId.",
                    "Sprite settingsRaw is normalized to 64; downscaleMultiplier is 1; " +
                        (asset.hasSerializedIsPolygon ? "m_IsPolygon is normalized false." : "target Sprite serializer has no m_IsPolygon property."),
                    "Empty source bones, bindpose, blend-shapes, physics shapes, alpha texture and secondary textures remain empty.",
                    "Unity-generated RenderDataKey and asset metadata are target-native; original SpriteAtlas packing identity is not claimed."
                };
        }

        static void VerifySpriteSerializedData(Sprite sprite, Texture2D texture, PreparedAsset asset, string phase)
        {
            var so = new SerializedObject(sprite);
            so.UpdateIfRequiredOrScript();
            VerifyRenderData(so, "m_RD", texture, asset);
            VerifyRenderData(so, "m_AtlasRD", texture, asset);
            if (!Close(FindRequired(so, "m_Rect").rectValue, ToRect(asset.spec.rect), GeometryTolerance) ||
                !Close(FindRequired(so, "m_Pivot").vector2Value, ToVector2(asset.spec.pivot), GeometryTolerance))
                throw new InvalidOperationException("Sprite source geometry differs " + phase + ": " + asset.spec.sourceId);
        }

        static void VerifyRenderData(SerializedObject so, string prefix, Texture2D texture, PreparedAsset asset,
                                     bool verifyTextureReference = true)
        {
            AssetSpec spec = asset.spec;
            if (verifyTextureReference && FindRequired(so, prefix + ".texture").objectReferenceValue != texture)
                throw new InvalidOperationException(prefix + ".texture differs: " + spec.sourceId);
            if (FindRequired(so, prefix + ".alphaTexture").objectReferenceValue != null)
                throw new InvalidOperationException(prefix + ".alphaTexture must be null: " + spec.sourceId);
            if (!Close(FindRequired(so, prefix + ".textureRect").rectValue, ToRect(spec.textureRect), GeometryTolerance) ||
                !Close(FindRequired(so, prefix + ".textureRectOffset").vector2Value, ToVector2(spec.textureRectOffset), GeometryTolerance) ||
                !Close(FindRequired(so, prefix + ".atlasRectOffset").vector2Value, ToVector2(spec.atlasRectOffset), GeometryTolerance) ||
                !Close(FindRequired(so, prefix + ".uvTransform").vector4Value, ToVector4(spec.uvTransform), GeometryTolerance))
                throw new InvalidOperationException(prefix + " crop/offset/UV transform differs: " + spec.sourceId);
            int settingsRaw = FindRequired(so, prefix + ".settingsRaw").intValue;
            if (spec.preserveExistingSprite)
            {
                int expectedSettings = prefix == "m_RD" ? (verifyTextureReference ? spec.sourcePackedSettingsRaw : asset.beforeRenderSettingsRaw) : asset.beforeAtlasSettingsRaw;
                if (settingsRaw != expectedSettings)
                    throw new InvalidOperationException(prefix + ".settingsRaw=" + settingsRaw + " expected=" + expectedSettings +
                        " phaseTextureVerified=" + verifyTextureReference + ": " + spec.sourceId);
                float expectedDownscale = prefix == "m_RD" ? asset.beforeRenderDownscale : asset.beforeAtlasDownscale;
                if (!Close(FindRequired(so, prefix + ".downscaleMultiplier").floatValue, expectedDownscale, GeometryTolerance))
                    throw new InvalidOperationException(prefix + ".downscaleMultiplier changed from the preserved native value: " + spec.sourceId);
            }
            else
            {
                if (prefix == "m_RD" && settingsRaw != NormalizedSpriteSettingsRaw)
                    throw new InvalidOperationException(prefix + ".settingsRaw differs from normalized value 64; actual=" + settingsRaw + ": " + spec.sourceId);
                if (!Close(FindRequired(so, prefix + ".downscaleMultiplier").floatValue, 1f, GeometryTolerance))
                    throw new InvalidOperationException(prefix + ".downscaleMultiplier differs from normalized 1: " + spec.sourceId);
            }
            VerifyEmptyArray(FindRequired(so, prefix + ".secondaryTextures"), prefix + ".secondaryTextures");
            VerifyChannels(FindRequired(so, prefix + ".m_VertexData.m_Channels"), spec.channels, prefix);
            if (FindRequired(so, prefix + ".m_VertexData.m_VertexCount").intValue != spec.meshVertices.Length)
                throw new InvalidOperationException(prefix + " vertex count differs: " + spec.sourceId);
            VerifyVertexBuffer(FindRequired(so, prefix + ".m_VertexData.m_DataSize"), asset, prefix);
            VerifyByteArray(FindRequired(so, prefix + ".m_IndexBuffer"), asset.indexBytes, prefix + ".m_IndexBuffer");
            VerifySubmeshes(FindRequired(so, prefix + ".m_SubMeshes"), spec.subMeshes, prefix);
            VerifyEmptyArray(FindRequired(so, prefix + ".m_Bindpose"), prefix + ".m_Bindpose");
            VerifyEmptyBlendShapes(so, prefix + ".m_BlendShapes");
        }

        static void VerifyChannels(SerializedProperty array, ChannelDto[] expected, string prefix)
        {
            RequireArray(array, prefix + ".m_VertexData.m_Channels");
            if (array.arraySize != expected.Length) throw new InvalidOperationException(prefix + " channel count differs");
            for (int i = 0; i < expected.Length; i++)
            {
                SerializedProperty item = array.GetArrayElementAtIndex(i);
                if (RelativeInt(item, "stream", prefix) != expected[i].stream || RelativeInt(item, "offset", prefix) != expected[i].offset ||
                    RelativeInt(item, "format", prefix) != expected[i].format || RelativeInt(item, "dimension", prefix) != expected[i].dimension)
                    throw new InvalidOperationException(prefix + " channel tuple differs at index " + i);
            }
        }

        static byte[] ReadByteArray(SerializedProperty array)
        {
            RequireArray(array, array.propertyPath);
            var bytes = new byte[array.arraySize];
            for (int i = 0; i < bytes.Length; i++)
            {
                var item = array.GetArrayElementAtIndex(i);
                RequirePropertyType(item, SerializedPropertyType.Integer, array.propertyPath);
                if (item.intValue < 0 || item.intValue > 255) throw new InvalidOperationException("Native byte is out of range");
                bytes[i] = (byte)item.intValue;
            }
            return bytes;
        }

        static void VerifyVertexBuffer(SerializedProperty array, PreparedAsset asset, string prefix)
        {
            var actual = ReadByteArray(array);
            var source = asset.vertexBytes;
            int uvStart = (asset.spec.meshVertices.Length * 12 + 15) / 16 * 16;
            if (!BitConverter.IsLittleEndian || actual.Length != source.Length || actual.Length != uvStart + asset.spec.meshUv.Length * 8)
                throw new InvalidOperationException(prefix + " unsupported vertex buffer layout");
            // Source positions and alignment padding are exact. The source has
            // an empty UV cache; Unity may populate only that cache on access.
            for (int i = 0; i < uvStart; i++)
                if (actual[i] != source[i]) throw new InvalidOperationException(prefix + " source position/padding byte differs at " + i);
            bool emptyCache = true;
            for (int i = uvStart; i < actual.Length; i++) emptyCache &= actual[i] == 0;
            if (!emptyCache)
                for (int i = 0; i < asset.spec.meshUv.Length; i++)
                    if (!Close(BitConverter.ToSingle(actual, uvStart + i * 8), asset.spec.meshUv[i].x, GeometryTolerance) ||
                        !Close(BitConverter.ToSingle(actual, uvStart + i * 8 + 4), asset.spec.meshUv[i].y, GeometryTolerance))
                        throw new InvalidOperationException(prefix + " populated UV cache differs from exact source-derived UV at " + i);
        }

        static void VerifyByteArray(SerializedProperty array, byte[] expected, string path)
        {
            RequireArray(array, path);
            if (array.arraySize != expected.Length) throw new InvalidOperationException(path + " byte length differs");
            for (int i = 0; i < expected.Length; i++)
            {
                SerializedProperty item = array.GetArrayElementAtIndex(i);
                RequirePropertyType(item, SerializedPropertyType.Integer, path + "[" + i + "]");
                if (item.intValue != expected[i]) throw new InvalidOperationException(path + " differs at byte " + i);
            }
        }

        static void VerifySubmeshes(SerializedProperty array, SubmeshDto[] expected, string prefix)
        {
            RequireArray(array, prefix + ".m_SubMeshes");
            if (array.arraySize != expected.Length) throw new InvalidOperationException(prefix + " submesh count differs");
            for (int i = 0; i < expected.Length; i++)
            {
                SerializedProperty item = array.GetArrayElementAtIndex(i);
                SubmeshDto source = expected[i];
                string path = prefix + ".m_SubMeshes[" + i + "]";
                string[] names = { "firstByte", "indexCount", "topology", "baseVertex", "firstVertex", "vertexCount" };
                int[] values = { source.firstByte, source.indexCount, source.topology, source.baseVertex, source.firstVertex, source.vertexCount };
                for (int f = 0; f < names.Length; f++)
                    if (RelativeInt(item, names[f], path) != values[f]) throw new InvalidOperationException(path + "." + names[f] + " differs");
                if (!Close(RelativeVector3(item, "localAABB.m_Center", path), ToVector3(source.localAABB.m_Center), GeometryTolerance) ||
                    !Close(RelativeVector3(item, "localAABB.m_Extent", path), ToVector3(source.localAABB.m_Extent), GeometryTolerance))
                    throw new InvalidOperationException(path + ".localAABB differs");
            }
        }

        static void VerifyEmptyBlendShapes(SerializedObject serialized, string path)
        {
            SerializedProperty blendShapes = FindRequired(serialized, path);
            foreach (string field in new[] { "vertices", "shapes", "channels", "fullWeights" })
                VerifyEmptyArray(FindRelativeRequired(blendShapes, field, path + "." + field), path + "." + field);
        }

        static void VerifyEmptyArrayIfPresent(SerializedObject serialized, string path)
        {
            SerializedProperty property = serialized.FindProperty(path);
            if (property != null) VerifyEmptyArray(property, path);
        }

        static void VerifyNullReferenceIfPresent(SerializedObject serialized, string path)
        {
            SerializedProperty property = serialized.FindProperty(path);
            if (property != null && property.propertyType == SerializedPropertyType.ObjectReference && property.objectReferenceValue != null)
                throw new InvalidOperationException(path + " must be null on the un-atlased candidate Sprite");
        }

        static bool SetOptionalFalse(SerializedObject serialized, string path)
        {
            SerializedProperty property = serialized.FindProperty(path);
            if (property == null) return false;
            RequirePropertyType(property, SerializedPropertyType.Boolean, path);
            property.boolValue = false;
            return true;
        }

        static void SetEmptyArrayIfPresent(SerializedObject serialized, string path)
        {
            SerializedProperty property = serialized.FindProperty(path);
            if (property != null) SetEmptyArray(property, path);
        }

        static void SetNullReferenceIfPresent(SerializedObject serialized, string path)
        {
            SerializedProperty property = serialized.FindProperty(path);
            if (property == null) return;
            RequirePropertyType(property, SerializedPropertyType.ObjectReference, path);
            property.objectReferenceValue = null;
        }

        static void SetRequiredReference(SerializedObject serialized, string path, UnityEngine.Object value)
        {
            SerializedProperty property = FindRequired(serialized, path);
            RequirePropertyType(property, SerializedPropertyType.ObjectReference, path);
            property.objectReferenceValue = value;
        }

        static void SetRequiredRect(SerializedObject serialized, string path, Rect value)
        {
            SerializedProperty property = FindRequired(serialized, path);
            RequirePropertyType(property, SerializedPropertyType.Rect, path);
            property.rectValue = value;
        }

        static void SetRequiredVector2(SerializedObject serialized, string path, Vector2 value)
        {
            SerializedProperty property = FindRequired(serialized, path);
            RequirePropertyType(property, SerializedPropertyType.Vector2, path);
            property.vector2Value = value;
        }

        static void SetRequiredVector4(SerializedObject serialized, string path, Vector4 value)
        {
            SerializedProperty property = FindRequired(serialized, path);
            RequirePropertyType(property, SerializedPropertyType.Vector4, path);
            property.vector4Value = value;
        }

        static void SetRequiredFloat(SerializedObject serialized, string path, float value)
        {
            SerializedProperty property = FindRequired(serialized, path);
            RequirePropertyType(property, SerializedPropertyType.Float, path);
            property.floatValue = value;
        }

        static void SetRequiredInt(SerializedObject serialized, string path, long value)
        {
            SerializedProperty property = FindRequired(serialized, path);
            if (property.propertyType != SerializedPropertyType.Integer && property.propertyType != SerializedPropertyType.Enum)
                throw new InvalidOperationException(path + " is not Integer/Enum, actual=" + property.propertyType);
            property.longValue = value;
        }

        static void SetRelativeInt(SerializedProperty parent, string name, int value, string path)
        {
            SerializedProperty property = FindRelativeRequired(parent, name, path);
            if (property.propertyType != SerializedPropertyType.Integer && property.propertyType != SerializedPropertyType.Enum)
                throw new InvalidOperationException(path + " is not Integer/Enum, actual=" + property.propertyType);
            property.intValue = value;
        }

        static void SetRelativeVector3(SerializedProperty parent, string name, Vector3 value, string path)
        {
            SerializedProperty property = FindRelativeRequired(parent, name, path);
            RequirePropertyType(property, SerializedPropertyType.Vector3, path);
            property.vector3Value = value;
        }

        static int RelativeInt(SerializedProperty parent, string name, string label)
        {
            SerializedProperty property = FindRelativeRequired(parent, name, label + "." + name);
            if (property.propertyType != SerializedPropertyType.Integer && property.propertyType != SerializedPropertyType.Enum)
                throw new InvalidOperationException(label + "." + name + " is not Integer/Enum");
            return property.intValue;
        }

        static Vector3 RelativeVector3(SerializedProperty parent, string name, string label)
        {
            SerializedProperty property = FindRelativeRequired(parent, name, label + "." + name);
            RequirePropertyType(property, SerializedPropertyType.Vector3, label + "." + name);
            return property.vector3Value;
        }

        static void SetEmptyArray(SerializedProperty property, string path)
        {
            RequireArray(property, path);
            property.arraySize = 0;
        }

        static void VerifyEmptyArray(SerializedProperty property, string path)
        {
            RequireArray(property, path);
            if (property.arraySize != 0) throw new InvalidOperationException(path + " must be empty in the static source profile");
        }

        static void SetArraySize(SerializedProperty property, int size, string path)
        {
            RequireArray(property, path);
            property.arraySize = size;
            if (property.arraySize != size) throw new InvalidOperationException("Unity did not allocate requested array size at " + path);
        }

        static void RequireArray(SerializedProperty property, string path)
        {
            if (property == null || !property.isArray || property.propertyType == SerializedPropertyType.String)
                throw new InvalidOperationException("Serialized array is absent/unsupported: " + path);
        }

        static SerializedProperty FindRequired(SerializedObject serialized, string path)
        {
            SerializedProperty property = serialized == null ? null : serialized.FindProperty(path);
            if (property == null) throw new InvalidOperationException("SerializedProperty is absent: " + path);
            return property;
        }

        static SerializedProperty FindRelativeRequired(SerializedProperty parent, string path, string label)
        {
            SerializedProperty property = parent == null ? null : parent.FindPropertyRelative(path);
            if (property == null) throw new InvalidOperationException("SerializedProperty is absent: " + label);
            return property;
        }

        static void RequirePropertyType(SerializedProperty property, SerializedPropertyType expected, string path)
        {
            if (property == null || property.propertyType != expected)
                throw new InvalidOperationException("SerializedProperty type differs at " + path + ": expected=" + expected + ", actual=" +
                    (property == null ? "missing" : property.propertyType.ToString()));
        }

        static void EnsureNewAssetPath(string projectRoot, string assetPath, string label)
        {
            if (File.Exists(Path.GetFullPath(Path.Combine(projectRoot, assetPath.Replace('/', Path.DirectorySeparatorChar)))) ||
                File.Exists(Path.GetFullPath(Path.Combine(projectRoot, assetPath.Replace('/', Path.DirectorySeparatorChar))) + ".meta"))
                throw new InvalidOperationException("Creation target or meta already exists; refusing overwrite: " + assetPath);
            if (!String.IsNullOrEmpty(AssetDatabase.AssetPathToGUID(assetPath)))
                throw new InvalidOperationException("AssetDatabase already has a GUID for new target " + label + ": " + assetPath);
        }

        static string ValidateAssetOutputPath(string projectRoot, string relative, string label)
        {
            ValidateRelativePath(relative, "Assets/", ".asset", label);
            string full = Path.GetFullPath(Path.Combine(projectRoot, relative.Replace('/', Path.DirectorySeparatorChar)));
            RequireInside(projectRoot, full, label);
            EnsureNoSymlink(projectRoot, full, label);
            return relative;
        }

        static string ValidateAnalysisInputPath(string projectRoot, string relative, string label)
        {
            ValidateRelativePath(relative, "Analysis/", ".rgba", label);
            string full = Path.GetFullPath(Path.Combine(projectRoot, relative.Replace('/', Path.DirectorySeparatorChar)));
            RequireInside(projectRoot, full, label);
            EnsureNoSymlink(projectRoot, full, label);
            if (!File.Exists(full)) throw new InvalidOperationException(label + " does not exist: " + relative);
            return full;
        }

        static void ValidateAnalysisJsonPath(string projectRoot, string full, string label)
        {
            RequireInside(projectRoot, full, label);
            string relative = ToRelative(projectRoot, full);
            if (!relative.StartsWith("Analysis/", StringComparison.Ordinal) ||
                !String.Equals(Path.GetExtension(relative), ".json", StringComparison.Ordinal))
                throw new InvalidOperationException(label + " must be an Analysis/*.json file inside the current project");
        }

        static void ValidateRelativePath(string path, string rootPrefix, string extension, string label)
        {
            if (String.IsNullOrWhiteSpace(path) || Path.IsPathRooted(path) || path.IndexOf('\\') >= 0 || path.IndexOf(':') >= 0 ||
                !path.StartsWith(rootPrefix, StringComparison.Ordinal) || !String.Equals(Path.GetExtension(path), extension, StringComparison.Ordinal))
                throw new InvalidOperationException(label + " must be a safe " + rootPrefix + "*" + extension + " path");
            string[] parts = path.Split('/');
            if (parts.Any(part => String.IsNullOrWhiteSpace(part) || part == "." || part == ".."))
                throw new InvalidOperationException(label + " contains an unsafe path segment");
        }

        static void EnsureNoSymlink(string root, string fullPath, string label)
        {
            string normalizedRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            string normalizedPath = Path.GetFullPath(fullPath);
            CheckNotReparse(normalizedRoot, label);
            if (String.Equals(normalizedRoot, normalizedPath, StringComparison.Ordinal)) return;
            if (!String.Equals(normalizedRoot, normalizedPath, StringComparison.Ordinal))
                RequireInside(normalizedRoot, normalizedPath, label);
            string relative = ToRelative(normalizedRoot, normalizedPath);
            string current = normalizedRoot;
            CheckNotReparse(current, label);
            foreach (string part in relative.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar))
            {
                if (String.IsNullOrEmpty(part)) continue;
                current = Path.Combine(current, part);
                if (File.Exists(current) || Directory.Exists(current)) CheckNotReparse(current, label);
            }
        }

        static void CheckNotReparse(string path, string label)
        {
            try
            {
                if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
                    throw new InvalidOperationException(label + " traverses a symbolic link/reparse point: " + path);
            }
            catch (FileNotFoundException) { }
            catch (DirectoryNotFoundException) { }
        }

        static void RequireInside(string root, string full, string label)
        {
            string normalizedRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            string normalizedFull = Path.GetFullPath(full);
            if (!normalizedFull.StartsWith(normalizedRoot, StringComparison.Ordinal))
                throw new InvalidOperationException(label + " escapes the current Unity project");
        }

        static string ToRelative(string root, string full)
        {
            string rootWithSep = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            string normalized = Path.GetFullPath(full);
            if (!normalized.StartsWith(rootWithSep, StringComparison.Ordinal)) throw new InvalidOperationException("Path escapes project root");
            return normalized.Substring(rootWithSep.Length).Replace(Path.DirectorySeparatorChar, '/');
        }

        static string ToAssetPath(string root, string full)
        {
            return ToRelative(root, full);
        }

        static string AssetDirectory(string assetPath)
        {
            int slash = assetPath.LastIndexOf('/');
            return slash < 0 ? "Assets" : assetPath.Substring(0, slash);
        }

        static void ReadNativeIdentity(UnityEngine.Object value, string expectedAssetPath,
                                       out string guid, out string localId, out string type)
        {
            long nativeLocalId;
            if (value == null || !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value, out guid, out nativeLocalId) || String.IsNullOrEmpty(guid))
                throw new InvalidOperationException("New Unity native asset identity is unavailable: " + expectedAssetPath);
            localId = nativeLocalId.ToString(CultureInfo.InvariantCulture);
            type = value.GetType().FullName;
            if (!String.Equals(AssetDatabase.GetAssetPath(value), expectedAssetPath, StringComparison.Ordinal))
                throw new InvalidOperationException("Native object asset path differs from its planned path: " + expectedAssetPath);
        }

        static AssetResult NewAssetResult(PreparedAsset asset)
        {
            AssetSpec spec = asset.spec;
            return new AssetResult { sourceId = spec.sourceId, textureSourceId = spec.textureSourceId,
                spritePath = spec.spritePath, texturePath = spec.texturePath,
                spriteName = spec.spriteName, textureName = spec.textureName,
                spriteIdentityDisposition = spec.preserveExistingSprite ? "preserved-existing-provider" : "new-native-derived",
                beforeSpriteGuid = asset.beforeSpriteGuid, beforeSpriteLocalId = asset.beforeSpriteLocalId,
                sourceBeforeAssetSha256 = spec.sourceBeforeAssetSha256, sourceBeforeMetaSha256 = spec.sourceBeforeMetaSha256 };
        }

        static void WriteResult(string outputAbsolute, ExecutionResult result)
        {
            string json = JsonUtility.ToJson(result, true) + "\n";
            byte[] bytes = new UTF8Encoding(false).GetBytes(json);
            if (bytes.Length > MaxOutputBytes) throw new InvalidOperationException("Embedded asset result exceeds 16 MiB");
            string directory = Path.GetDirectoryName(outputAbsolute);
            if (String.IsNullOrEmpty(directory)) throw new InvalidOperationException("Result output parent directory is absent");
            Directory.CreateDirectory(directory);
            File.WriteAllBytes(outputAbsolute, bytes);
        }

        static byte[] ReadBounded(string path, int maxBytes)
        {
            var info = new FileInfo(path);
            if (!info.Exists || info.Length < 1 || info.Length > maxBytes)
                throw new InvalidOperationException("Input file is missing, empty, or above its byte limit: " + path);
            return File.ReadAllBytes(path);
        }

        static byte[] ReadRgbaPixels(Texture2D texture)
        {
            Color32[] colors = texture.GetPixels32(0);
            var bytes = new byte[checked(colors.Length * 4)];
            for (int i = 0; i < colors.Length; i++)
            {
                bytes[i * 4] = colors[i].r;
                bytes[i * 4 + 1] = colors[i].g;
                bytes[i * 4 + 2] = colors[i].b;
                bytes[i * 4 + 3] = colors[i].a;
            }
            return bytes;
        }

        static string Sha256(byte[] bytes)
        {
            using (SHA256 sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", String.Empty).ToLowerInvariant();
        }

        static bool IsSha256(string value)
        {
            if (String.IsNullOrEmpty(value) || value.Length != 64) return false;
            for (int i = 0; i < value.Length; i++)
                if (!((value[i] >= '0' && value[i] <= '9') || (value[i] >= 'a' && value[i] <= 'f'))) return false;
            return true;
        }

        static string RequiredEnvironment(string name)
        {
            string value = Environment.GetEnvironmentVariable(name);
            if (String.IsNullOrWhiteSpace(value)) throw new InvalidOperationException("Required environment variable is missing: " + name);
            return value;
        }

        static int Align(int value, int alignment)
        {
            return checked((value + alignment - 1) / alignment * alignment);
        }

        static float ReadFloat32(byte[] bytes, int offset)
        {
            if (!BitConverter.IsLittleEndian) throw new InvalidOperationException("Source Sprite mesh bytes require little-endian decoding");
            if (offset < 0 || offset + 4 > bytes.Length) throw new InvalidOperationException("Source mesh float read exceeds vertex buffer");
            float value = BitConverter.ToSingle(bytes, offset);
            if (!Finite(value)) throw new InvalidOperationException("Source mesh position contains a non-finite Float32");
            return value;
        }

        static bool BytesEqual(byte[] left, byte[] right)
        {
            if (left == null || right == null || left.Length != right.Length) return false;
            for (int i = 0; i < left.Length; i++) if (left[i] != right[i]) return false;
            return true;
        }

        static void RequireRect(RectDto value, string name, string sourceId)
        {
            if (value == null || !Finite(value.x) || !Finite(value.y) || !Finite(value.width) || !Finite(value.height))
                throw new InvalidOperationException(name + " is null or contains non-finite values: " + sourceId);
        }

        static void RequireVector(Vector2Dto value, string name, string sourceId)
        {
            if (value == null || !Finite(value.x) || !Finite(value.y))
                throw new InvalidOperationException(name + " is null or contains non-finite values: " + sourceId);
        }

        static void RequireVector(Vector3Dto value, string name, string sourceId)
        {
            if (value == null || !Finite(value.x) || !Finite(value.y) || !Finite(value.z))
                throw new InvalidOperationException(name + " is null or contains non-finite values: " + sourceId);
        }

        static void RequireVector(Vector4Dto value, string name, string sourceId)
        {
            if (value == null || !Finite(value.x) || !Finite(value.y) || !Finite(value.z) || !Finite(value.w))
                throw new InvalidOperationException(name + " is null or contains non-finite values: " + sourceId);
        }

        static Rect ToRect(RectDto value) { return new Rect(value.x, value.y, value.width, value.height); }
        static Vector2 ToVector2(Vector2Dto value) { return new Vector2(value.x, value.y); }
        static Vector3 ToVector3(Vector3Dto value) { return new Vector3(value.x, value.y, value.z); }
        static Vector4 ToVector4(Vector4Dto value) { return new Vector4(value.x, value.y, value.z, value.w); }
        static bool Finite(float value) { return !Single.IsNaN(value) && !Single.IsInfinity(value); }

        static bool Close(float a, float b, double tolerance) { return !Single.IsNaN(a) && !Single.IsInfinity(a) && Math.Abs((double)a - b) <= tolerance; }
        static bool Close(Vector2 a, Vector2 b, double tolerance) { return Close(a.x, b.x, tolerance) && Close(a.y, b.y, tolerance); }
        static bool Close(Vector3 a, Vector3 b, double tolerance) { return Close(a.x, b.x, tolerance) && Close(a.y, b.y, tolerance) && Close(a.z, b.z, tolerance); }
        static bool Close(Vector4 a, Vector4 b, double tolerance) { return Close(a.x, b.x, tolerance) && Close(a.y, b.y, tolerance) && Close(a.z, b.z, tolerance) && Close(a.w, b.w, tolerance); }
        static bool Close(Rect a, Rect b, double tolerance) { return Close(a.x, b.x, tolerance) && Close(a.y, b.y, tolerance) && Close(a.width, b.width, tolerance) && Close(a.height, b.height, tolerance); }
    }
}
