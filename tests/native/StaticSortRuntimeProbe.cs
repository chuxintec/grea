#if UNITY_EDITOR
using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Monkey.StaticSortQueueProxy;
using TMPro;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace Monkey.Tests
{
    [InitializeOnLoad]
    public static class StaticSortRuntimeProbe
    {
        const string StageKey = "Monkey.StaticSortRuntimeProbe.Stage";
        const string OutputKey = "Monkey.StaticSortRuntimeProbe.Output";
        const string ExitKey = "Monkey.StaticSortRuntimeProbe.Exit";
        static bool queued;

        static StaticSortRuntimeProbe()
        {
            EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;
            EditorApplication.playModeStateChanged += OnPlayModeStateChanged;
            EditorApplication.update -= Resume;
            EditorApplication.update += Resume;
        }

        static void Resume()
        {
            var stage = SessionState.GetString(StageKey, "");
            if ((stage == "enter" || stage == "running") && EditorApplication.isPlaying && !queued)
            {
                queued = true;
                SessionState.SetString(StageKey, "observing");
                try { StartDriver(); }
                catch (Exception error) { WriteFailure(error.ToString()); SessionState.SetInt(ExitKey, 3);
                    SessionState.SetString(StageKey, "exit"); EditorApplication.isPlaying = false; }
            }
            if (stage == "exit" && !EditorApplication.isPlayingOrWillChangePlaymode) ExitBatch();
            if (stage == "observing" && EditorApplication.timeSinceStartup - SessionState.GetFloat(StageKey + ".time", 0) > 60)
                Finish("{\"status\":\"failed\",\"failures\":[\"native observation timeout\"]}", 4);
        }

        public static void Run()
        {
            try
            {
                if (EditorApplication.isPlayingOrWillChangePlaymode) throw new InvalidOperationException("Editor must be idle before the isolated probe starts.");
                var output = Argument("-monkeyProbeOutput");
                if (string.IsNullOrWhiteSpace(output)) throw new ArgumentException("Pass -monkeyProbeOutput <json-path>.");
                SessionState.SetString(OutputKey, Path.GetFullPath(output));
                Debug.Log("MONKEY_RUNTIME_PROBE: build isolated scene");
                SessionState.SetString(StageKey, "enter");
                SessionState.SetInt(ExitKey, 1);
                BuildScene();
                EditorApplication.isPlaying = true;
            }
            catch (Exception error)
            {
                WriteFailure(error.ToString());
                if (Application.isBatchMode) EditorApplication.Exit(2); else throw;
            }
        }

        static void BuildScene()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var cameraObject = new GameObject("ProbeCamera", typeof(Camera));
            cameraObject.tag = "MainCamera";
            var camera = cameraObject.GetComponent<Camera>();
            camera.orthographic = true; camera.orthographicSize = 5; camera.transform.position = new Vector3(0, 0, -10);
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(0, 0, 0, 0);
            var canvasObject = new GameObject("ProbeCanvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            var canvas = canvasObject.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceCamera; canvas.worldCamera = camera; canvas.pixelPerfect = true;
            canvasObject.GetComponent<CanvasScaler>().uiScaleMode = CanvasScaler.ScaleMode.ConstantPixelSize;
            var esObject = new GameObject("EventSystem", typeof(EventSystem));
            var eventSystem = esObject.GetComponent<EventSystem>();

            var imageRoot = new GameObject("SourceA", typeof(RectTransform), typeof(CanvasGroup));
            imageRoot.transform.SetParent(canvasObject.transform, false);
            var sourceA = imageRoot;
            var group = imageRoot.GetComponent<CanvasGroup>();
            var image = AddImage(sourceA.transform, "ProgressImage", new Vector2(-170, 70), new Vector2(140, 70));
            image.fillMethod = Image.FillMethod.Horizontal; image.fillAmount = 1f;
            var spriteA = MakeSprite(Color.white);
            var spriteB = MakeSprite(Color.cyan);
            image.sprite = spriteA; image.type = Image.Type.Filled;
            var fallback = TMP_Settings.defaultFontAsset;
            var tmpFont = UnityEngine.Object.Instantiate(fallback);
            tmpFont.name = "Probe primary bounded font";
            tmpFont.material = new Material(fallback.material);
            tmpFont.characterTable.RemoveAll(c => c.unicode == 'W');
            if (!fallback.characterTable.Any(c => c.unicode == 'W'))
                throw new InvalidOperationException("Probe fallback must retain W in its independent font asset.");
            tmpFont.fallbackFontAssetTable = new List<TMP_FontAsset> { fallback };
            tmpFont.ReadFontAssetDefinition();
            var textObject = new GameObject("RuntimeText", typeof(RectTransform), typeof(TextMeshProUGUI));
            textObject.transform.SetParent(sourceA.transform, false);
            var textRect = textObject.GetComponent<RectTransform>(); textRect.anchoredPosition = new Vector2(0, -45); textRect.sizeDelta = new Vector2(280, 36);
            var text = textObject.GetComponent<TextMeshProUGUI>(); text.font = tmpFont; text.text = "seed"; text.fontSize = 20;

            // Two independently cloned source/proxy pairs catch accidental shared runtime-mesh mutation.
            var sourceBRoot = new GameObject("SourceB", typeof(RectTransform)); sourceBRoot.transform.SetParent(canvasObject.transform, false);
            var imageB = AddImage(sourceBRoot.transform, "ProgressImage", new Vector2(170, 70), new Vector2(100, 55));
            imageB.sprite = spriteA; imageB.type = Image.Type.Simple;
            imageB.rectTransform.pivot = new Vector2(0, .5f);
            var progress = sourceBRoot.AddComponent<Slider>(); progress.value = .77f;
            sourceBRoot.AddComponent<NativeHorizontalProgressFill>().Configure(progress, imageB.rectTransform, 100);

            var sourceButton = AddImage(canvasObject.transform, "SourceButtonGraphic", new Vector2(0, -160), new Vector2(140, 64));
            sourceButton.transform.SetParent(sourceA.transform, false);
            var hitArea = new GameObject("SourceButton", typeof(RectTransform), typeof(Button), typeof(NativeStaticButtonTarget));
            hitArea.transform.SetParent(sourceA.transform, false);
            var hitRect = hitArea.GetComponent<RectTransform>(); hitRect.anchoredPosition = new Vector2(0, -160);
            hitRect.sizeDelta = new Vector2(180, 84);
            var button = hitArea.GetComponent<Button>(); button.targetGraphic = sourceButton; button.enabled = false;
            var retainedTarget = hitArea.GetComponent<NativeStaticButtonTarget>();
            retainedTarget.Target = sourceButton.gameObject; retainedTarget.SourceEnabled = true; retainedTarget.enabled = false;
            Canvas.ForceUpdateCanvases();
            if (text != null) text.ForceMeshUpdate(true, true);

            var proxyRootA = new GameObject("ProxyA", typeof(RectTransform)); proxyRootA.transform.SetParent(canvasObject.transform, false);
            var proxyRootB = new GameObject("ProxyB", typeof(RectTransform)); proxyRootB.transform.SetParent(canvasObject.transform, false);
            var proxyImageA = AddProxy(image, proxyRootA.transform, "ProgressImageProxy", spriteA.texture);
            var proxyText = AddProxy(text, proxyRootA.transform, "RuntimeTextProxy", tmpFont != null && tmpFont.atlasTexture != null ? tmpFont.atlasTexture : null);
            var proxyImageB = AddProxy(imageB, proxyRootB.transform, "ProgressImageProxy", spriteA.texture);
            var proxyButton = AddProxy(sourceButton, proxyRootA.transform, "SourceButtonProxy", spriteA.texture);

            var presenterHostA = new GameObject("PresenterA"); presenterHostA.transform.SetParent(canvasObject.transform, false);
            var presenterA = presenterHostA.AddComponent<NativeStaticSortQueueProxyPresenter>();
            presenterA.sourceRoot = sourceA; presenterA.proxyRoot = proxyRootA;
            presenterA.bindings = new[] { Bind(image, proxyImageA), Bind(text, proxyText), Bind(sourceButton, proxyButton) };
            presenterA.sourceTreeStayedUnmodified = true;
            presenterA.InitializePresentation();
            var presenterHostB = new GameObject("PresenterB"); presenterHostB.transform.SetParent(canvasObject.transform, false);
            var presenterB = presenterHostB.AddComponent<NativeStaticSortQueueProxyPresenter>();
            presenterB.sourceRoot = sourceBRoot; presenterB.proxyRoot = proxyRootB;
            presenterB.bindings = new[] { Bind(imageB, proxyImageB) };
            presenterB.sourceTreeStayedUnmodified = true;
            presenterB.InitializePresentation();

            // A real proxy-side MaskableGraphic mask pair exercises the normal uGUI stencil binding.
            var sourceMaskRoot = new GameObject("SourceMask", typeof(RectTransform)); sourceMaskRoot.transform.SetParent(sourceA.transform, false);
            ConfigureMaskRect(sourceMaskRoot.GetComponent<RectTransform>(), new Vector2(-170, 70));
            var sourceMaskImage = sourceMaskRoot.AddComponent<Image>(); sourceMaskImage.sprite = spriteA; sourceMaskImage.color = Color.white;
            var sourceMask = sourceMaskRoot.AddComponent<Mask>(); sourceMask.showMaskGraphic = false;
            image.transform.SetParent(sourceMaskRoot.transform, false);
            image.rectTransform.anchoredPosition = Vector2.zero;
            var proxyMaskRoot = new GameObject("ProxyMask", typeof(RectTransform)); proxyMaskRoot.transform.SetParent(proxyRootA.transform, false);
            ConfigureMaskRect(proxyMaskRoot.GetComponent<RectTransform>(), new Vector2(-170, 70));
            var proxyMaskImage = proxyMaskRoot.AddComponent<Image>(); proxyMaskImage.sprite = spriteA; proxyMaskImage.color = Color.white;
            var proxyMask = proxyMaskRoot.AddComponent<Mask>(); proxyMask.showMaskGraphic = false;
            proxyImageA.transform.SetParent(proxyMaskRoot.transform, false);
            proxyImageA.rectTransform.anchoredPosition = Vector2.zero;
            presenterA.maskBindings = new[] { new ProxyMaskBinding { sourceId = "probe-mask", sourceNode = "probe-mask", sourceMask = sourceMask, proxyMask = proxyMask } };

            var state = new StaticSortRuntimeProbeDriver.State {
                output = Argument("-monkeyProbeOutput"), receipt = new StaticSortRuntimeProbeReceipt(),
                imageA = image, imageB = imageB, textA = text, sourceA = sourceA, sourceB = sourceBRoot,
                progress = progress, progressFill = sourceBRoot.GetComponent<NativeHorizontalProgressFill>(),
                groupA = group, imageProxyA = proxyImageA, imageProxyB = proxyImageB, textProxy = proxyText,
                buttonImage = sourceButton, button = button, clickCounter = hitArea.AddComponent<StaticSortProbeClickCounter>(), buttonProxy = proxyButton,
                presenterA = presenterA, presenterB = presenterB, raycasterCanvas = canvasObject,
                proxyMask = proxyMask, ordinaryRaycaster = canvasObject.GetComponent<GraphicRaycaster>(),
                eventSystem = eventSystem, spriteA = spriteA, spriteB = spriteB
            };
            typeof(StaticSortRuntimeProbeDriver).GetField("state", System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic).SetValue(null, state);
            // AddProxy already cloned native mesh data. Keep exactly that saved
            // proof object; the runtime presenter must draw a different live mesh.
            var baselineMesh = proxyImageA.proxyMesh;

            // The observer must survive deactivating the tested Canvas.
            var driver = new GameObject("ProbeDriver").AddComponent<StaticSortRuntimeProbeDriver>();
            driver.spriteB = spriteB;
            driver.baselineMesh = baselineMesh;
            state.bakedMesh = baselineMesh;
        }

        public static void Finish(string json, int code)
        {
            try { var path = SessionState.GetString(OutputKey, ""); if (!string.IsNullOrWhiteSpace(path)) { Directory.CreateDirectory(Path.GetDirectoryName(path)); File.WriteAllText(path, json); } }
            catch (Exception error) { Debug.LogException(error); code = 2; }
            SessionState.SetInt(ExitKey, code); SessionState.SetString(StageKey, "exit");
            EditorApplication.isPlaying = false;
            if (Application.isBatchMode && !EditorApplication.isPlayingOrWillChangePlaymode) EditorApplication.delayCall += ExitBatch;
        }
        static void OnPlayModeStateChanged(PlayModeStateChange state)
        {
            Debug.Log("MONKEY_RUNTIME_PROBE: " + state);
            var stage = SessionState.GetString(StageKey, "");
            if (state == PlayModeStateChange.EnteredPlayMode && stage == "enter") SessionState.SetString(StageKey, "running");
        }
        static void QueueStart() { if (queued) return; queued = true; EditorApplication.delayCall += StartDriver; }
        static void StartDriver()
        {
            Debug.Log("MONKEY_RUNTIME_PROBE: start native observations");
            SessionState.SetFloat(StageKey + ".time", (float)EditorApplication.timeSinceStartup);
            queued = false;
            var driver = UnityEngine.Object.FindAnyObjectByType<StaticSortRuntimeProbeDriver>();
            if (driver == null) { Finish("{\"status\":\"failed\",\"failures\":[\"driver missing after PlayMode transition\"]}", 3); return; }
            var output = SessionState.GetString(OutputKey, "");
            // Recover the setup state from named native objects after Unity's PlayMode domain reload.
            var state = RecoverState(output);
            typeof(StaticSortRuntimeProbeDriver).GetField("state", System.Reflection.BindingFlags.Static | System.Reflection.BindingFlags.NonPublic).SetValue(null, state);
            StaticSortRuntimeProbeDriver.CompleteCallback = Finish;
            driver.StartCoroutine(driver.RunProbe(output));
        }
        static StaticSortRuntimeProbeDriver.State RecoverState(string output)
        {
            // Scene objects survive Enter PlayMode; find by explicit neutral probe names.
            var canvas = GameObject.Find("ProbeCanvas"); var sourceA = GameObject.Find("SourceA"); var sourceB = GameObject.Find("SourceB");
            var image = sourceA.transform.Find("SourceMask/ProgressImage").GetComponent<Image>();
            var text = sourceA.GetComponentInChildren<TMP_Text>(true);
            var imageB = sourceB.GetComponentInChildren<Image>(true);
            var buttonImage = GameObject.Find("SourceButtonGraphic").GetComponent<Image>();
            var button = GameObject.Find("SourceButton").GetComponent<Button>();
            var proxyRootA = GameObject.Find("ProxyA"); var proxyRootB = GameObject.Find("ProxyB");
            var proxyImageA = proxyRootA.GetComponentsInChildren<NativeStaticSortQueueProxyGraphic>(true).First(x => x.sourceGraphic == image);
            var proxyText = proxyRootA.GetComponentsInChildren<NativeStaticSortQueueProxyGraphic>(true).First(x => x.sourceGraphic == text);
            var proxyButton = proxyRootA.GetComponentsInChildren<NativeStaticSortQueueProxyGraphic>(true).First(x => x.sourceGraphic == buttonImage);
            var proxyImageB = proxyRootB.GetComponentInChildren<NativeStaticSortQueueProxyGraphic>(true);
            var presenterA = GameObject.Find("PresenterA").GetComponent<NativeStaticSortQueueProxyPresenter>();
            var presenterB = GameObject.Find("PresenterB").GetComponent<NativeStaticSortQueueProxyPresenter>();
            var eventSystem = UnityEngine.Object.FindAnyObjectByType<EventSystem>();
            var driver = UnityEngine.Object.FindAnyObjectByType<StaticSortRuntimeProbeDriver>();
            return new StaticSortRuntimeProbeDriver.State {
                output = output, receipt = new StaticSortRuntimeProbeReceipt(), imageA = image, imageB = imageB,
                textA = text, sourceA = sourceA, sourceB = sourceB, groupA = sourceA.GetComponent<CanvasGroup>(),
                progress = sourceB.GetComponent<Slider>(), progressFill = sourceB.GetComponent<NativeHorizontalProgressFill>(),
                bakedMesh = driver.baselineMesh,
                imageProxyA = proxyImageA, imageProxyB = proxyImageB, textProxy = proxyText, buttonImage = buttonImage,
                button = button, buttonProxy = proxyButton, presenterA = presenterA, presenterB = presenterB,
                raycasterCanvas = canvas, proxyMask = GameObject.Find("ProxyMask").GetComponent<Mask>(),
                ordinaryRaycaster = canvas.GetComponent<GraphicRaycaster>(), eventSystem = eventSystem,
                clickCounter = button.GetComponent<StaticSortProbeClickCounter>(), spriteA = image.sprite,
                spriteB = driver.spriteB
            };
        }
        static void ExitBatch() { if (Application.isBatchMode) EditorApplication.Exit(SessionState.GetInt(ExitKey, 1)); }
        static string Argument(string name)
        {
            var args = Environment.GetCommandLineArgs();
            for (var i = 0; i + 1 < args.Length; i++) if (args[i] == name) return args[i + 1];
            return null;
        }
        static void WriteFailure(string message)
        {
            var path = Argument("-monkeyProbeOutput");
            if (!string.IsNullOrWhiteSpace(path)) { Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))); File.WriteAllText(Path.GetFullPath(path), "{\"status\":\"error\",\"message\":" + JsonUtility.ToJson(new ErrorMessage { message = message }).Replace("{\"message\":", "").TrimEnd('}') + "}"); }
        }
        [Serializable] sealed class ErrorMessage { public string message; }
        static Image AddImage(Transform parent, string name, Vector2 position, Vector2 size)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image)); go.transform.SetParent(parent, false);
            var rect = go.GetComponent<RectTransform>(); rect.anchorMin = rect.anchorMax = new Vector2(0.5f, 0.5f); rect.pivot = new Vector2(0.5f, 0.5f); rect.anchoredPosition = position; rect.sizeDelta = size;
            return go.GetComponent<Image>();
        }
        static void ConfigureMaskRect(RectTransform rect, Vector2 position)
        {
            rect.anchorMin = rect.anchorMax = new Vector2(.5f, .5f);
            rect.pivot = new Vector2(.5f, .5f);
            rect.anchoredPosition = position;
            rect.sizeDelta = new Vector2(60, 60);
        }
        static NativeStaticSortQueueProxyGraphic AddProxy(Graphic source, Transform parent, string name, Texture texture)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(CanvasRenderer), typeof(CanvasGroup),
                typeof(NativeStaticSortQueueProxyGraphic)); go.transform.SetParent(parent, false);
            var rect = go.GetComponent<RectTransform>(); rect.anchorMin = source.rectTransform.anchorMin; rect.anchorMax = source.rectTransform.anchorMax;
            rect.pivot = source.rectTransform.pivot; rect.sizeDelta = source.rectTransform.sizeDelta; rect.anchoredPosition = source.rectTransform.anchoredPosition;
            rect.localRotation = source.rectTransform.localRotation; rect.localScale = source.rectTransform.localScale;
            var proxy = go.GetComponent<NativeStaticSortQueueProxyGraphic>(); proxy.sourceGraphic = source; proxy.sourceOwnerGraphic = source;
            proxy.proxyTexture = texture; proxy.raycastTarget = false; proxy.maskable = true;
            proxy.proxyBaseMaterial = source.material;
            proxy.sourceOpacityCaptured = true;
            proxy.sourceRendererAlpha = source.canvasRenderer.GetAlpha();
            proxy.sourceInheritedAlpha = source.canvasRenderer.GetInheritedAlpha();
            var mesh = source.canvasRenderer.GetMesh(); proxy.proxyMesh = mesh == null ? new Mesh() : UnityEngine.Object.Instantiate(mesh);
            return proxy;
        }
        static ProxyGraphicBinding Bind(Graphic source, NativeStaticSortQueueProxyGraphic proxy) =>
            new ProxyGraphicBinding { sourceGraphic = source, sourceCanvasRenderer = source.canvasRenderer, proxyGraphics = new[] { proxy }, sourceGraphicEnabled = source.enabled, sourceCanvasCullBefore = source.canvasRenderer.cull };
        static Sprite MakeSprite(Color color)
        {
            var tex = new Texture2D(2, 2, TextureFormat.RGBA32, false); tex.SetPixels(Enumerable.Repeat(color, 4).ToArray()); tex.Apply();
            return Sprite.Create(tex, new Rect(0, 0, 2, 2), new Vector2(.5f, .5f), 100f);
        }
    }
}
#endif
