using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using Grea.Foundation.Runtime;
using Grea.UI.UGUI;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using Object = UnityEngine.Object;

namespace Grea.Editor
{
    // Only invoked by the grea-owned staged project. Existing assets are never overwritten.
    public static class ProjectGenerator
    {
        public const string Version = "0.1.1";
        public const string BasePath = "Assets/GreaGenerated";
        [Serializable] public sealed class Request
        {
            public string generatorVersion, identity, bootstrapScene, entryScene, bootstrapType, playerSaveNamespace, qaSaveNamespace;
        }
        [Serializable] public sealed class AssetRecord
        {
            public string path, sha256, metaSha256, guid;
            public string[] fileIds;
        }
        [Serializable] public sealed class Journal
        {
            public string generatorVersion, identity, pending;
            public bool complete;
            public int errorCount;
            public List<AssetRecord> assets = new List<AssetRecord>();
        }
        public static string Hash(string path)
        { using (var sha = SHA256.Create()) using (var f = File.OpenRead(path)) return BitConverter.ToString(sha.ComputeHash(f)).Replace("-", "").ToLowerInvariant(); }
        static void AtomicJson(string path, object value)
        {
            var tmp = path + ".tmp";
            if (File.Exists(tmp)) throw new InvalidOperationException("RECOVERY_REQUIRED: interrupted journal write");
            File.WriteAllText(tmp, JsonUtility.ToJson(value, true));
            if (File.Exists(path)) File.Replace(tmp, path, null); else File.Move(tmp, path);
        }
        static void SafeAssetPath(string path, string extension)
        {
            if (string.IsNullOrEmpty(path) || !path.StartsWith("Assets/", StringComparison.Ordinal) || !path.EndsWith(extension, StringComparison.Ordinal) ||
                path.Contains("..") || path.Contains("\\") || path.Contains(":")) throw new InvalidOperationException("INVALID_ASSET_PATH");
        }
        static void Folder(string path)
        {
            var parent = Path.GetDirectoryName(path).Replace('\\', '/');
            if (AssetDatabase.IsValidFolder(parent)) return;
            Folder(parent);
            AssetDatabase.CreateFolder(Path.GetDirectoryName(parent).Replace('\\', '/'), Path.GetFileName(parent));
        }
        public static void Generate(Request request, string journalPath, Action<string> checkpoint = null)
        {
            if (Application.unityVersion != "6000.6.2f1" || request.generatorVersion != Version)
                throw new InvalidOperationException("UNSUPPORTED_VERSION");
            SafeAssetPath(request.bootstrapScene, ".unity"); SafeAssetPath(request.entryScene, ".unity");
            if (request.bootstrapScene == request.entryScene) throw new InvalidOperationException("SCENE_CONFLICT");
            var types = TypeCache.GetTypesDerivedFrom<MonoBehaviour>().Where(t => t.FullName == request.bootstrapType).ToArray();
            if (types.Length != 1) throw new InvalidOperationException("BOOTSTRAP_TYPE_CONFLICT");
            var journal = File.Exists(journalPath) ? JsonUtility.FromJson<Journal>(File.ReadAllText(journalPath)) :
                new Journal { generatorVersion = Version, identity = request.identity };
            if (journal.generatorVersion != Version || journal.identity != request.identity) throw new InvalidOperationException("STALE_GENERATOR");
            if (journal.errorCount != 0) throw new InvalidOperationException("RECOVERY_REQUIRED: previous Editor errors require a new reviewed attempt");
            if (!string.IsNullOrEmpty(journal.pending)) throw new InvalidOperationException("RECOVERY_REQUIRED: pending asset " + journal.pending);
            foreach (var item in journal.assets)
                if (!File.Exists(item.path) || Hash(item.path) != item.sha256 || !File.Exists(item.path + ".meta") || Hash(item.path + ".meta") != item.metaSha256)
                    throw new InvalidOperationException("OWNERSHIP_CONFLICT: " + item.path);
            void Observe(string message, string trace, LogType type)
            { if (type == LogType.Error || type == LogType.Exception || type == LogType.Assert) journal.errorCount++; }
            journal.complete = false;
            Application.logMessageReceived += Observe;
            try
            {
            void Create(string path, Action action)
            {
                if (journal.assets.Any(x => x.path == path)) return;
                if (File.Exists(path) || File.Exists(path + ".meta")) throw new InvalidOperationException("OWNERSHIP_CONFLICT: " + path);
                Folder(path);
                journal.pending = path; AtomicJson(journalPath, journal); checkpoint?.Invoke("before:" + path);
                action(); AssetDatabase.SaveAssets(); AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
                var ids = new SortedSet<string>();
                var root = AssetDatabase.LoadMainAssetAtPath(path);
                var objects = path.EndsWith(".unity", StringComparison.Ordinal) ? Array.Empty<Object>().AsEnumerable() :
                    root is GameObject go ? go.GetComponentsInChildren<Transform>(true).SelectMany(t => t.GetComponents<Component>().Cast<Object>().Append(t.gameObject)) : AssetDatabase.LoadAllAssetsAtPath(path).AsEnumerable();
                foreach (var obj in objects)
                    if (obj && AssetDatabase.TryGetGUIDAndLocalFileIdentifier(obj, out string _, out long id)) ids.Add(id.ToString());
                if (path.EndsWith(".unity", StringComparison.Ordinal))
                    foreach (var obj in SceneManager.GetActiveScene().GetRootGameObjects().SelectMany(g => g.GetComponentsInChildren<Transform>(true)).SelectMany(t => t.GetComponents<Component>().Cast<Object>().Append(t.gameObject)))
                        if (obj) ids.Add(GlobalObjectId.GetGlobalObjectIdSlow(obj).targetObjectId.ToString());
                journal.assets.Add(new AssetRecord { path = path, sha256 = Hash(path), metaSha256 = Hash(path + ".meta"), guid = AssetDatabase.AssetPathToGUID(path), fileIds = ids.ToArray() });
                journal.pending = null; AtomicJson(journalPath, journal); checkpoint?.Invoke("after:" + path);
            }
            Create(BasePath + "/ButtonShell.prefab", () => SavePrefab(MakeButton("ButtonShell"), BasePath + "/ButtonShell.prefab"));
            Create(BasePath + "/ModalShell.prefab", () => SavePrefab(MakeModal(), BasePath + "/ModalShell.prefab"));
            Create(BasePath + "/UIHost.prefab", () => SavePrefab(MakeHost(), BasePath + "/UIHost.prefab"));
            Create(BasePath + "/BootstrapConfig.asset", () => {
                var config = ScriptableObject.CreateInstance<BootstrapConfig>(); config.entryScene = request.entryScene;
                config.playerSaveNamespace = request.playerSaveNamespace; config.qaSaveNamespace = request.qaSaveNamespace;
                AssetDatabase.CreateAsset(config, BasePath + "/BootstrapConfig.asset");
            });
            Create(BasePath + "/Renderer.asset", () => AssetDatabase.CreateAsset(ScriptableObject.CreateInstance<UniversalRendererData>(), BasePath + "/Renderer.asset"));
            Create(BasePath + "/Pipeline.asset", () => AssetDatabase.CreateAsset(UniversalRenderPipelineAsset.Create(AssetDatabase.LoadAssetAtPath<UniversalRendererData>(BasePath + "/Renderer.asset")), BasePath + "/Pipeline.asset"));
            Create(request.bootstrapScene, () => {
                var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                var bootstrap = new GameObject("Bootstrap").AddComponent(types[0]);
                if (!bootstrap) throw new InvalidOperationException("BOOTSTRAP_TYPE_NOT_ATTACHABLE");
                var so = new SerializedObject(bootstrap); var field = so.FindProperty("config");
                if (field == null) throw new InvalidOperationException("BINDING_FAILED: config");
                field.objectReferenceValue = AssetDatabase.LoadAssetAtPath<BootstrapConfig>(BasePath + "/BootstrapConfig.asset"); so.ApplyModifiedPropertiesWithoutUndo();
                if (!EditorSceneManager.SaveScene(scene, request.bootstrapScene)) throw new InvalidOperationException("SCENE_SAVE_FAILED");
            });
            Create(request.entryScene, () => {
                var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(BasePath + "/UIHost.prefab"), scene);
                var camera = new GameObject("Camera").AddComponent<Camera>(); camera.gameObject.tag = "MainCamera";
                camera.transform.position = new Vector3(0, 0, -10); camera.orthographic = true;
                camera.gameObject.AddComponent<UniversalAdditionalCameraData>();
                if (!EditorSceneManager.SaveScene(scene, request.entryScene)) throw new InvalidOperationException("SCENE_SAVE_FAILED");
            });
            // Settings are finalized only in the private staging project; no existing project is opened.
            GraphicsSettings.defaultRenderPipeline = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(BasePath + "/Pipeline.asset");
            QualitySettings.renderPipeline = null;
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(request.bootstrapScene, true), new EditorBuildSettingsScene(request.entryScene, true) };
            Validate(request);
            if (journal.errorCount != 0) throw new InvalidOperationException("EDITOR_ERRORS: inspect preserved log");
            journal.complete = true;
            }
            finally
            {
                Application.logMessageReceived -= Observe;
                AtomicJson(journalPath, journal);
            }
        }
        static GameObject Rect(string name, Transform parent = null)
        { var go = new GameObject(name, typeof(RectTransform)); if (parent) go.transform.SetParent(parent, false); return go; }
        static void Stretch(GameObject go)
        { var r = (RectTransform)go.transform; r.anchorMin = Vector2.zero; r.anchorMax = Vector2.one; r.offsetMin = r.offsetMax = Vector2.zero; }
        static GameObject MakeButton(string name)
        {
            var go = Rect(name); ((RectTransform)go.transform).sizeDelta = new Vector2(220, 64);
            var image = go.AddComponent<Image>(); image.color = new Color(.15f, .45f, .7f);
            var button = go.AddComponent<Button>(); button.targetGraphic = image;
            go.AddComponent<CommandButton>().Configure(button);
            return go;
        }
        static GameObject MakeModal()
        {
            var root = Rect("ModalShell"); Stretch(root);
            var content = Rect("Content", root.transform); Stretch(content);
            var blocker = Rect("Blocker", content.transform); Stretch(blocker); blocker.AddComponent<Image>().color = new Color(0, 0, 0, .7f);
            var close = MakeButton("Close"); close.transform.SetParent(content.transform, false);
            root.AddComponent<ModalPanel>().Configure(content, blocker, close.GetComponent<Button>(), close.GetComponent<Button>(), null);
            content.SetActive(false); return root;
        }
        static GameObject MakeHost()
        {
            var root = Rect("UIHost"); var canvas = root.AddComponent<Canvas>(); canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            root.AddComponent<CanvasScaler>().uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            root.AddComponent<GraphicRaycaster>();
            var host = root.AddComponent<UIHost>(); host.canvas = canvas;
            host.pageLayer = (RectTransform)Rect("Pages", root.transform).transform; Stretch(host.pageLayer.gameObject);
            host.modalLayer = (RectTransform)Rect("Modals", root.transform).transform; Stretch(host.modalLayer.gameObject);
            host.toastLayer = (RectTransform)Rect("Toasts", root.transform).transform; Stretch(host.toastLayer.gameObject);
            var events = new GameObject("EventSystem", typeof(EventSystem), typeof(StandaloneInputModule)); events.transform.SetParent(root.transform, false); host.events = events.GetComponent<EventSystem>();
            var button = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(BasePath + "/ButtonShell.prefab")); button.transform.SetParent(host.pageLayer, false); host.openButton = button.GetComponent<CommandButton>();
            var modal = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(BasePath + "/ModalShell.prefab")); modal.transform.SetParent(host.modalLayer, false); host.modal = modal.GetComponent<ModalPanel>();
            var close = modal.GetComponentInChildren<Button>(true); var content = modal.transform.Find("Content").gameObject;
            host.modal.Configure(content, content.transform.Find("Blocker").gameObject, close, close, host.events);
            PrefabUtility.RecordPrefabInstancePropertyModifications(host.modal);
            return root;
        }
        static void SavePrefab(GameObject go, string path)
        { try { if (!PrefabUtility.SaveAsPrefabAsset(go, path)) throw new InvalidOperationException("PREFAB_SAVE_FAILED"); } finally { Object.DestroyImmediate(go); } }
        public static void Validate(Request request)
        {
            var host = AssetDatabase.LoadAssetAtPath<GameObject>(BasePath + "/UIHost.prefab");
            if (!host || BindingValidator.Inspect(host).Count != 0 || host.GetComponentsInChildren<EventSystem>(true).Length != 1)
                throw new InvalidOperationException("BINDING_FAILED: UIHost");
            var button = AssetDatabase.LoadAssetAtPath<GameObject>(BasePath + "/ButtonShell.prefab");
            if (!button || BindingValidator.Inspect(button).Count != 0) throw new InvalidOperationException("BINDING_FAILED: ButtonShell");
            var modal = AssetDatabase.LoadAssetAtPath<GameObject>(BasePath + "/ModalShell.prefab");
            if (!modal || BindingValidator.Inspect(modal).Any(x => x.Field != "events")) throw new InvalidOperationException("BINDING_FAILED: ModalShell");
            var scene = EditorSceneManager.OpenScene(request.bootstrapScene, OpenSceneMode.Single);
            var components = scene.GetRootGameObjects().SelectMany(x => x.GetComponentsInChildren<MonoBehaviour>(true)).Where(x => x && x.GetType().FullName == request.bootstrapType).ToArray();
            if (components.Length != 1 || !new SerializedObject(components[0]).FindProperty("config").objectReferenceValue) throw new InvalidOperationException("BINDING_FAILED: Bootstrap");
            scene = EditorSceneManager.OpenScene(request.entryScene, OpenSceneMode.Single);
            if (scene.GetRootGameObjects().SelectMany(x => x.GetComponentsInChildren<EventSystem>(true)).Count() != 1) throw new InvalidOperationException("BINDING_FAILED: EventSystem");
            foreach (var go in scene.GetRootGameObjects()) if (BindingValidator.Inspect(go).Count != 0) throw new InvalidOperationException("BINDING_FAILED: Entry");
        }
        public static void Run()
        {
            int code = 1;
            try
            {
                var project = Path.GetDirectoryName(Application.dataPath);
                var request = JsonUtility.FromJson<Request>(File.ReadAllText(Path.Combine(project, "Tools/Generated/request.json")));
                Generate(request, Path.Combine(project, "Tools/Generated/editor-journal.json"));
                code = 0;
            }
            catch (Exception error) { Debug.LogException(error); }
            finally { EditorApplication.Exit(code); }
        }
    }
}
