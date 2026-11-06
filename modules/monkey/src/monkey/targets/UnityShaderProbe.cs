using System;
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

public static class MonkeyShaderProbe
{
    private const int BudgetSeconds = 1200;
    private const string ShaderName = "Monkey/RecoveredSprite";
    private const string ShaderAssetPath = "__MONKEY_SHADER_ASSET_PATH__";
    private const string MaterialPath = "__MONKEY_MATERIAL_ASSET_PATH__";

    [MenuItem("Monkey/Run Shader Pixel Probe")]
    public static void RunFromEditorMenu() => Run();

    public static void Run()
    {
        var started = DateTime.UtcNow;
        var reportPath = Path.GetFullPath(Path.Combine(Application.dataPath, "../shader-probe-result.json"));
        try
        {
            if (SystemInfo.graphicsDeviceType == GraphicsDeviceType.Null)
                throw new InvalidOperationException("No graphics device; pixel probe cannot be treated as passed.");

            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var shader = Shader.Find(ShaderName);
            if (shader == null) throw new InvalidOperationException("Candidate shader did not import: " + ShaderName);
            var messages = ShaderUtil.GetShaderMessages(shader);
            foreach (var message in messages)
                if (string.Equals(message.severity.ToString(), "Error", StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("Shader compile error: " + message.message);

            var shaderGuid = AssetDatabase.AssetPathToGUID(ShaderAssetPath);
            var materialGuid = AssetDatabase.AssetPathToGUID(MaterialPath);
            if (string.IsNullOrEmpty(shaderGuid) || string.IsNullOrEmpty(materialGuid))
                throw new InvalidOperationException("Shader or material asset did not import with a stable GUID.");
            if (shaderGuid != ReadMetaGuid(ShaderAssetPath) || materialGuid != ReadMetaGuid(MaterialPath))
                throw new InvalidOperationException("Imported asset GUID differs from its supplied deterministic .meta.");
            var importedMaterial = AssetDatabase.LoadAssetAtPath<Material>(MaterialPath);
            if (importedMaterial == null || importedMaterial.shader != shader)
                throw new InvalidOperationException("Generated material did not resolve the generated shader GUID.");
            AssetDatabase.SaveAssets();
            AssetDatabase.ImportAsset(MaterialPath, ImportAssetOptions.ForceUpdate | ImportAssetOptions.ForceSynchronousImport);
            var reopenedMaterial = AssetDatabase.LoadAssetAtPath<Material>(MaterialPath);
            if (reopenedMaterial == null || reopenedMaterial.shader != shader || AssetDatabase.AssetPathToGUID(MaterialPath) != materialGuid)
                throw new InvalidOperationException("Generated material lost its shader reference after save/reimport.");

            var source = new Color(0.8f, 0.4f, 0.2f, 0.5f);
            var vertex = new Color(0.5f, 1f, 0.5f, 0.5f);
            var clear = new Color(0.1f, 0.2f, 0.3f, 0.4f);
            var expectedSource = new Color(source.r * vertex.r, source.g * vertex.g, source.b * vertex.b, source.a * vertex.a);
            var expected = new Color(
                expectedSource.r * expectedSource.a + clear.r * (1f - expectedSource.a),
                expectedSource.g * expectedSource.a + clear.g * (1f - expectedSource.a),
                expectedSource.b * expectedSource.a + clear.b * (1f - expectedSource.a),
                expectedSource.a * expectedSource.a + clear.a * (1f - expectedSource.a));

            var texture = new Texture2D(1, 1, TextureFormat.RGBA32, false, true) { filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp };
            texture.SetPixel(0, 0, source);
            texture.Apply(false, false);
            var material = new Material(reopenedMaterial) { mainTexture = texture };
            var mesh = new Mesh { vertices = new[] { new Vector3(-1, -1, 0), new Vector3(1, -1, 0), new Vector3(1, 1, 0), new Vector3(-1, 1, 0) },
                uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(1, 1), new Vector2(0, 1) },
                colors = new[] { vertex, vertex, vertex, vertex }, triangles = new[] { 0, 1, 2, 0, 2, 3 } };
            var gameObject = new GameObject("shader-probe-camera");
            var camera = gameObject.AddComponent<Camera>();
            camera.orthographic = true;
            camera.orthographicSize = 1f;
            camera.transform.position = new Vector3(0, 0, -2);
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = clear;
            camera.cullingMask = 1 << 30;
            gameObject.layer = 30;
            var quad = new GameObject("shader-probe-quad") { layer = 30 };
            quad.AddComponent<MeshFilter>().sharedMesh = mesh;
            quad.AddComponent<MeshRenderer>().sharedMaterial = material;
            var target = new RenderTexture(32, 32, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
            target.antiAliasing = 1;
            target.Create();
            camera.targetTexture = target;
            camera.Render();
            var previous = RenderTexture.active;
            RenderTexture.active = target;
            var readback = new Texture2D(1, 1, TextureFormat.RGBA32, false, true);
            readback.ReadPixels(new Rect(16, 16, 1, 1), 0, 0, false);
            readback.Apply(false, false);
            var actual = readback.GetPixel(0, 0);
            RenderTexture.active = previous;
            const float tolerance = 0.018f;
            var maxError = Mathf.Max(Mathf.Abs(actual.r - expected.r), Mathf.Abs(actual.g - expected.g), Mathf.Abs(actual.b - expected.b), Mathf.Abs(actual.a - expected.a));
            if (maxError > tolerance) throw new InvalidOperationException("Pixel differs from source subset oracle; maxError=" + maxError.ToString("R"));
            if ((DateTime.UtcNow - started).TotalSeconds > BudgetSeconds) throw new TimeoutException("Probe exceeded its 1200-second method budget.");

            var report = "{\"status\":\"passed\",\"shader\":\"" + ShaderName + "\",\"graphicsDevice\":\"" + SystemInfo.graphicsDeviceType +
                "\",\"expected\":[" + expected.r.ToString("R") + "," + expected.g.ToString("R") + "," + expected.b.ToString("R") + "," + expected.a.ToString("R") +
                "],\"actual\":[" + actual.r.ToString("R") + "," + actual.g.ToString("R") + "," + actual.b.ToString("R") + "," + actual.a.ToString("R") +
                "],\"maxError\":" + maxError.ToString("R") + ",\"tolerance\":" + tolerance.ToString("R") +
                ",\"shaderGuid\":\"" + shaderGuid + "\",\"materialGuid\":\"" + materialGuid + "\"}";
            File.WriteAllText(reportPath, report);
            UnityEngine.Object.DestroyImmediate(readback);
            UnityEngine.Object.DestroyImmediate(target);
            UnityEngine.Object.DestroyImmediate(mesh);
            UnityEngine.Object.DestroyImmediate(material);
            UnityEngine.Object.DestroyImmediate(texture);
            UnityEngine.Object.DestroyImmediate(quad);
            UnityEngine.Object.DestroyImmediate(gameObject);
            EditorApplication.Exit(0);
        }
        catch (Exception exception)
        {
            File.WriteAllText(reportPath, "{\"status\":\"failed\",\"error\":\"" + exception.Message.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"}");
            Debug.LogException(exception);
            EditorApplication.Exit(1);
        }
    }

    private static string ReadMetaGuid(string assetPath)
    {
        var metaPath = Path.GetFullPath(Path.Combine(Application.dataPath, "..", assetPath + ".meta"));
        foreach (var line in File.ReadAllLines(metaPath))
            if (line.StartsWith("guid:", StringComparison.Ordinal)) return line.Substring("guid:".Length).Trim();
        throw new InvalidOperationException("Missing GUID in supplied metadata for " + assetPath);
    }
}
