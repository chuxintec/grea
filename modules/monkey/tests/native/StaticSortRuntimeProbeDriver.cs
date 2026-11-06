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
    [Serializable]
    public sealed class StaticSortRuntimeProbeReceipt
    {
        public string schema = "monkey.static-sort-runtime-probe.v1";
        public string status;
        public string unityVersion;
        public bool enteredPlayMode, outputWritten, isBatchMode;
        public bool imageFillAndRectRefreshed, imageSpriteAndColorRefreshed;
        public bool textLengthColorRefreshed, sourceDeactivateReactivateRefreshed;
        public bool canvasGroupAlphaProjected, maskBindingPresent;
        public bool maskClippingVerified, maskStencilMaterialVerified;
        public bool sourceButtonRaycastMapped, sourceButtonClickExecutedOnce;
        public bool blocksRaycastsRejected, disabledProxyRaycasterRejected;
        public bool instancesIsolated, bakedMeshAssetUnchanged;
        public bool sourceTreeUnmodified;
        public bool pixelReadbackVerified;
        public bool tmpFontAvailable, tmpFallbackOrMultipleMaterialsExercised;
        public bool addedTmpSlotRendered, presenterLifecycleRestored, canvasLifecycleRestored;
        public bool rendererTintProjected;
        public bool typedProgressBindingRefreshed;
        public int firstProxyVertexCount, secondProxyVertexCount, sourceVertexCount;
        public int buttonClickCount, eventSystemRaycastCount;
        public string bakedMeshSha256, bakedMeshSha256After;
        public string pixelReadback, maskPixelReadback;
        public string[] limitations = Array.Empty<string>();
        public string[] failures = Array.Empty<string>();
    }

    /// <summary>
    /// Neutral Unity-native runtime probe. Build a throwaway scene, enter PlayMode,
    /// mutate ordinary uGUI/TMP sources over several Editor frames, then write one
    /// machine-readable receipt to -monkeyProbeOutput. It does not simulate physical input.
    /// </summary>
    public sealed class StaticSortRuntimeProbeDriver : MonoBehaviour
    {
        public static Action<string, int> CompleteCallback;
        [Serializable] public sealed class State
        {
            public string output;
            public StaticSortRuntimeProbeReceipt receipt;
            public Image imageA, imageB, buttonImage;
            public Slider progress;
            public NativeHorizontalProgressFill progressFill;
            public TMP_Text textA;
            public GameObject sourceA, sourceB;
            public CanvasGroup groupA;
            public Mesh bakedMesh;
            public NativeStaticSortQueueProxyGraphic imageProxyA, imageProxyB, buttonProxy;
            public NativeStaticSortQueueProxyGraphic textProxy;
            public NativeStaticSortQueueProxyPresenter presenterA, presenterB;
            public GameObject raycasterCanvas;
            public Mask proxyMask;
            public GraphicRaycaster ordinaryRaycaster;
            public EventSystem eventSystem;
            public Button button;
            public StaticSortProbeClickCounter clickCounter;
            public Sprite spriteA, spriteB;
            public Texture2D texture;
            public int initialImageVertices, initialTextVertices;
        }

        static State state;
        public Mesh baselineMesh;
        public Sprite spriteB;

        public IEnumerator RunProbe(string output)
        {
            if (state == null) throw new InvalidOperationException("Probe scene state was not restored after entering PlayMode.");
            state.output = Path.GetFullPath(output);
            var errors = new List<string>();
            var routine = RunProbeSteps(errors);
            while (true)
            {
                bool moved;
                object current = null;
                try { moved = routine.MoveNext(); if (moved) current = routine.Current; }
                catch (Exception error) { errors.Add(error.ToString()); break; }
                if (!moved) break;
                yield return current;
            }
            CompleteReceipt(errors);
        }

        IEnumerator RunProbeSteps(List<string> errors)
        {
            var r = state.receipt;
            r.unityVersion = Application.unityVersion;
            r.isBatchMode = Application.isBatchMode;
            r.enteredPlayMode = Application.isPlaying;
            r.limitations = new[] {
                "The click evidence uses EventSystem.RaycastAll and ExecuteEvents; no physical pointer or device input is claimed.",
                "TMP fallback/multiple material slots are reported only when the installed test font and text exercise them."
            };

                yield return null;
                Canvas.ForceUpdateCanvases();
                yield return null;
                state.button.onClick.AddListener(state.clickCounter.Increment);
                // The consumer enables and wires the recovered native Button.
                // Its transition Graphic is a sibling, not an event ancestor.
                state.button.enabled = true;
                Canvas.ForceUpdateCanvases(); yield return null;
                var automaticRaycaster = FindProxyRaycaster(state.raycasterCanvas);
                if (automaticRaycaster == null) errors.Add("Presenter did not install/register its native proxy raycaster automatically.");
                r.tmpFontAvailable = state.textA != null && state.textA.font != null;
                r.bakedMeshSha256 = MeshDigest(state.bakedMesh);
                r.firstProxyVertexCount = ProxyVertexCount(state.imageProxyA);
                r.secondProxyVertexCount = ProxyVertexCount(state.imageProxyB);
                r.sourceVertexCount = MeshVertexCount(state.imageA);
                state.initialImageVertices = r.firstProxyVertexCount;
                state.initialTextVertices = ProxyVertexCount(state.textProxy);
                r.maskClippingVerified = CaptureMaskClipping(state, out var maskReadback);
                r.maskPixelReadback = maskReadback;
                var renderedMaterial = state.imageProxyA != null && state.imageProxyA.canvasRenderer != null
                    ? state.imageProxyA.canvasRenderer.GetMaterial(0) : null;
                r.maskStencilMaterialVerified = renderedMaterial != null && renderedMaterial.HasProperty("_StencilComp") &&
                    renderedMaterial.GetInt("_StencilComp") != (int)UnityEngine.Rendering.CompareFunction.Always;

                // Image.fillAmount and RectTransform dimensions must reach the live proxy.
                state.imageA.fillAmount = 0.31f;
                state.imageA.rectTransform.SetSizeWithCurrentAnchors(RectTransform.Axis.Horizontal, 73f);
                Canvas.ForceUpdateCanvases();
                yield return null;
                r.imageFillAndRectRefreshed = ProxyMatchesSource(state.imageA, state.imageProxyA) &&
                    state.imageProxyA != null && state.imageProxyA.proxyMesh == state.bakedMesh &&
                    ReadProxyCanvasMesh(state.imageProxyA) != null && ReadProxyCanvasMesh(state.imageProxyA).vertexCount > 0;
                var fillVertices = ReadProxyCanvasMesh(state.imageProxyA).vertices.Select(v =>
                    state.imageA.transform.worldToLocalMatrix.MultiplyPoint3x4(
                        state.imageProxyA.transform.localToWorldMatrix.MultiplyPoint3x4(v))).ToArray();
                r.imageFillAndRectRefreshed &= Mathf.Abs(fillVertices.Max(v => v.x) - fillVertices.Min(v => v.x) -
                    state.imageA.GetPixelAdjustedRect().width * state.imageA.fillAmount) < .001f;

                // Sprite/material and vertex colors are changed independently of the baked baseline.
                state.imageA.sprite = state.spriteB;
                state.imageA.color = new Color(0.17f, 0.72f, 0.33f, 0.83f);
                Canvas.ForceUpdateCanvases();
                yield return null;
                r.imageSpriteAndColorRefreshed = ProxyMatchesSource(state.imageA, state.imageProxyA) &&
                    state.imageProxyA.mainTexture == state.imageA.mainTexture;
                var tint = new Color(.75f, .5f, .25f, .6f);
                state.imageA.canvasRenderer.SetColor(tint);
                Canvas.ForceUpdateCanvases(); yield return null;
                r.rendererTintProjected = state.imageProxyA.canvasRenderer.GetColor() == tint;
                state.progress.value = .25f;
                Canvas.ForceUpdateCanvases(); yield return null;
                bool quarter = Mathf.Abs(state.progressFill.Fill.rect.width - 25) < .001f &&
                    ProxyMatchesSource(state.imageB, state.imageProxyB);
                state.progress.value = .8f;
                Canvas.ForceUpdateCanvases(); yield return null;
                r.typedProgressBindingRefreshed = quarter && state.progress.fillRect == null &&
                    state.progressFill.Progress == state.progress && state.progressFill.Fill == state.imageB.rectTransform &&
                    Mathf.Abs(state.progressFill.Fill.rect.width - 80) < .001f &&
                    ProxyMatchesSource(state.imageB, state.imageProxyB);

                // Length, visible vertex data and color are read back from the actual CanvasRenderers.
                if (state.textA != null)
                {
                    state.textA.text = "Runtime text grows W";
                    state.textA.color = new Color(0.86f, 0.21f, 0.49f, 1f);
                    Canvas.ForceUpdateCanvases();
                    yield return null;
                    var sourceTextMesh = ReadCanvasMesh(state.textA);
                    var proxyTextMesh = ReadProxyCanvasMesh(state.textProxy);
                    r.textLengthColorRefreshed = sourceTextMesh != null && proxyTextMesh != null &&
                        sourceTextMesh.vertexCount > state.initialTextVertices &&
                        MeshEquivalent(sourceTextMesh, state.textA.transform, proxyTextMesh, state.textProxy.transform);
                    r.tmpFallbackOrMultipleMaterialsExercised =
                        state.textA.textInfo != null && state.textA.textInfo.materialCount > 1;
                    var textProxies = state.textProxy.transform.parent.GetComponentsInChildren<NativeStaticSortQueueProxyGraphic>(true)
                        .Where(p => p.sourceGraphic == state.textA).OrderBy(p => p.transform.GetSiblingIndex()).ToArray();
                    r.addedTmpSlotRendered = r.tmpFallbackOrMultipleMaterialsExercised &&
                        textProxies.Length == state.textA.textInfo.materialCount &&
                        Enumerable.Range(0, textProxies.Length).All(i => MeshEquivalent(
                            state.textA.textInfo.meshInfo[i].mesh, state.textA.transform,
                            ReadProxyCanvasMesh(textProxies[i]), textProxies[i].transform));
                }
                else errors.Add("TMP font asset unavailable; text mutation was not exercised.");

                // The source node's own active state must drive its visible proxy, then recover.
                state.sourceA.SetActive(false);
                Canvas.ForceUpdateCanvases();
                yield return null;
                bool hidden = !ProxyVisible(state.imageProxyA);
                state.sourceA.SetActive(true);
                Canvas.ForceUpdateCanvases();
                yield return null;
                r.sourceDeactivateReactivateRefreshed = hidden && ProxyVisible(state.imageProxyA) &&
                    ProxyMatchesSource(state.imageA, state.imageProxyA);

                // CanvasGroup alpha is checked as effective CanvasRenderer alpha, not only authored fields.
                state.groupA.alpha = 0.42f;
                Canvas.ForceUpdateCanvases();
                yield return null;
                r.canvasGroupAlphaProjected = state.imageProxyA != null && state.imageProxyA.canvasRenderer != null &&
                    Mathf.Abs(state.imageProxyA.canvasRenderer.GetInheritedAlpha() - 0.42f) < 0.08f;

                r.maskBindingPresent = state.presenterA != null && state.presenterA.maskBindings != null &&
                    state.presenterA.maskBindings.Any(x => x != null && x.proxyMask == state.proxyMask);

                // A real EventSystem raycast must return the source button GameObject from the proxy hit.
                r.sourceButtonRaycastMapped = TryMappedButtonRaycast(state, out var raycastHit);
                r.eventSystemRaycastCount = LastStaticRaycastCount;
                if (raycastHit)
                {
                    var pointer = new PointerEventData(state.eventSystem) { position = ButtonScreenPoint(state.buttonImage) };
                    ExecuteEvents.Execute(state.button.gameObject, pointer, ExecuteEvents.pointerClickHandler);
                }
                r.sourceButtonClickExecutedOnce = state.clickCounter != null && state.clickCounter.clicks == 1;
                r.buttonClickCount = state.clickCounter == null ? 0 : state.clickCounter.clicks;

                state.groupA.blocksRaycasts = false;
                Canvas.ForceUpdateCanvases();
                yield return null;
                r.blocksRaycastsRejected = !TryMappedButtonRaycast(state, out _);
                state.groupA.blocksRaycasts = true;

                state.presenterA.enabled = false; state.presenterB.enabled = false;
                var noStaleProxy = !state.imageProxyA.enabled && !state.buttonProxy.enabled &&
                    !state.buttonImage.canvasRenderer.cull;
                state.presenterA.enabled = true; state.presenterB.enabled = true;
                Canvas.ForceUpdateCanvases(); yield return null;
                r.presenterLifecycleRestored = noStaleProxy && TryMappedButtonRaycast(state, out _) &&
                    ProxyMatchesSource(state.imageA, state.imageProxyA);
                state.raycasterCanvas.SetActive(false); state.raycasterCanvas.SetActive(true);
                Canvas.ForceUpdateCanvases(); yield return null;
                r.canvasLifecycleRestored = TryMappedButtonRaycast(state, out _) &&
                    ProxyMatchesSource(state.imageA, state.imageProxyA);

                var proxyRaycaster = FindProxyRaycaster(state.raycasterCanvas);
                if (proxyRaycaster != null) proxyRaycaster.enabled = false;
                r.disabledProxyRaycasterRejected = !TryMappedButtonRaycast(state, out _);

                // A second presenter uses its own mutable runtime mesh and cannot alter instance A.
                r.instancesIsolated = state.imageProxyA != null && state.imageProxyB != null &&
                    ReadProxyCanvasMesh(state.imageProxyA) != null && ReadProxyCanvasMesh(state.imageProxyB) != null &&
                    ReadProxyCanvasMesh(state.imageProxyA) != ReadProxyCanvasMesh(state.imageProxyB);
                r.bakedMeshSha256After = MeshDigest(state.bakedMesh);
                r.bakedMeshAssetUnchanged = r.bakedMeshSha256 == r.bakedMeshSha256After &&
                    state.imageProxyA != null && state.imageProxyA.proxyMesh == state.bakedMesh;
                r.sourceTreeUnmodified = state.presenterA != null && state.presenterA.sourceRoot == state.sourceA &&
                    state.sourceA.transform.Find("SourceMask/ProgressImage") == state.imageA.transform &&
                    state.sourceA.transform.Find("RuntimeText") == state.textA.transform && state.buttonImage.enabled;
                r.firstProxyVertexCount = ProxyVertexCount(state.imageProxyA);
                r.secondProxyVertexCount = ProxyVertexCount(state.imageProxyB);
                r.sourceVertexCount = MeshVertexCount(state.imageA);
                r.pixelReadback = CapturePixelReadback();
                r.pixelReadbackVerified = r.pixelReadback.StartsWith("readback=", StringComparison.Ordinal) &&
                    r.pixelReadback.Contains("visibleRgbPixels=") && !r.pixelReadback.EndsWith("visibleRgbPixels=0", StringComparison.Ordinal);
        }

        void CompleteReceipt(List<string> errors)
        {
            var r = state.receipt;
            var checks = new Dictionary<string, bool> {
                [nameof(r.enteredPlayMode)] = r.enteredPlayMode,
                [nameof(r.imageFillAndRectRefreshed)] = r.imageFillAndRectRefreshed,
                [nameof(r.imageSpriteAndColorRefreshed)] = r.imageSpriteAndColorRefreshed,
                [nameof(r.textLengthColorRefreshed)] = r.textLengthColorRefreshed,
                [nameof(r.addedTmpSlotRendered)] = r.addedTmpSlotRendered,
                [nameof(r.rendererTintProjected)] = r.rendererTintProjected,
                [nameof(r.typedProgressBindingRefreshed)] = r.typedProgressBindingRefreshed,
                [nameof(r.presenterLifecycleRestored)] = r.presenterLifecycleRestored,
                [nameof(r.canvasLifecycleRestored)] = r.canvasLifecycleRestored,
                [nameof(r.sourceDeactivateReactivateRefreshed)] = r.sourceDeactivateReactivateRefreshed,
                [nameof(r.canvasGroupAlphaProjected)] = r.canvasGroupAlphaProjected,
                [nameof(r.maskBindingPresent)] = r.maskBindingPresent,
                [nameof(r.maskClippingVerified)] = r.maskClippingVerified,
                [nameof(r.maskStencilMaterialVerified)] = r.maskStencilMaterialVerified,
                [nameof(r.sourceButtonRaycastMapped)] = r.sourceButtonRaycastMapped,
                [nameof(r.sourceButtonClickExecutedOnce)] = r.sourceButtonClickExecutedOnce,
                [nameof(r.blocksRaycastsRejected)] = r.blocksRaycastsRejected,
                [nameof(r.disabledProxyRaycasterRejected)] = r.disabledProxyRaycasterRejected,
                [nameof(r.instancesIsolated)] = r.instancesIsolated,
                [nameof(r.bakedMeshAssetUnchanged)] = r.bakedMeshAssetUnchanged,
                [nameof(r.sourceTreeUnmodified)] = r.sourceTreeUnmodified,
                [nameof(r.pixelReadbackVerified)] = r.pixelReadbackVerified
            };
            errors.AddRange(checks.Where(x => !x.Value).Select(x => "Failed runtime observation: " + x.Key));
            r.failures = errors.ToArray();
            r.status = errors.Count == 0 ? "passed" : "failed";
            r.outputWritten = true;
            CompleteCallback(JsonUtility.ToJson(r, true), errors.Count == 0 ? 0 : 1);
        }

        static bool TryMappedButtonRaycast(State s, out bool hit)
        {
            hit = false;
            if (s.eventSystem == null || s.buttonImage == null) return false;
            var pointer = new PointerEventData(s.eventSystem) { position = ButtonScreenPoint(s.buttonImage) };
            var results = new List<RaycastResult>();
            s.eventSystem.RaycastAll(pointer, results);
            LastStaticRaycastCount = results.Count;
            hit = results.Count > 0 && results[0].gameObject == s.button.gameObject &&
                results.Count(x => x.gameObject == s.button.gameObject) == 1;
            return hit;
        }
        static int LastStaticRaycastCount;
        static GraphicRaycaster FindProxyRaycaster(GameObject canvas) => canvas == null ? null :
            canvas.GetComponents<GraphicRaycaster>().FirstOrDefault(r => r != null && r.GetType() != typeof(GraphicRaycaster));

        static Vector2 ButtonScreenPoint(Graphic graphic) => RectTransformUtility.WorldToScreenPoint(
            graphic.canvas != null ? graphic.canvas.worldCamera : null, graphic.rectTransform.TransformPoint(graphic.rectTransform.rect.center));

        static bool ProxyMatchesSource(Graphic source, NativeStaticSortQueueProxyGraphic proxy)
        {
            var a = ReadCanvasMesh(source); var b = ReadProxyCanvasMesh(proxy);
            return a != null && b != null && MeshEquivalent(a, source.transform, b, proxy.transform);
        }
        static Mesh ReadCanvasMesh(Graphic graphic)
        {
            if (graphic == null || graphic.canvasRenderer == null) return null;
            return graphic.canvasRenderer.GetMesh();
        }
        static Mesh ReadProxyCanvasMesh(NativeStaticSortQueueProxyGraphic graphic)
        {
            if (graphic == null || graphic.canvasRenderer == null) return null;
            return graphic.canvasRenderer.GetMesh();
        }
        static int MeshVertexCount(Graphic graphic) { var m = ReadCanvasMesh(graphic); return m == null ? 0 : m.vertexCount; }
        static int ProxyVertexCount(NativeStaticSortQueueProxyGraphic graphic)
        {
            var m = ReadProxyCanvasMesh(graphic); return m == null ? 0 : m.vertexCount;
        }
        static bool ProxyVisible(NativeStaticSortQueueProxyGraphic graphic) => graphic != null &&
            graphic.gameObject.activeInHierarchy && graphic.enabled && graphic.canvasRenderer != null && !graphic.canvasRenderer.cull &&
            graphic.canvasRenderer.GetInheritedAlpha() > 0.001f;
        static bool MeshEquivalent(Mesh a, Transform aTransform, Mesh b, Transform bTransform)
        {
            if (a == null || b == null || a.vertexCount != b.vertexCount || a.subMeshCount != b.subMeshCount) return false;
            var av = a.vertices; var bv = b.vertices;
            var ac = a.colors32; var bc = b.colors32;
            for (var i = 0; i < av.Length; i++)
            {
                if ((aTransform.TransformPoint(av[i]) - bTransform.TransformPoint(bv[i])).sqrMagnitude > 0.0001f) return false;
                if (ac.Length == av.Length && bc.Length == bv.Length && ac[i].Equals(bc[i]) == false) return false;
            }
            for (var i = 0; i < a.subMeshCount; i++)
                if (!a.GetIndices(i).SequenceEqual(b.GetIndices(i))) return false;
            return true;
        }
        static string MeshDigest(Mesh mesh)
        {
            if (mesh == null) return "";
            var data = string.Join("|", mesh.vertices.Select(v => v.x.ToString("R") + "," + v.y.ToString("R") + "," + v.z.ToString("R"))) +
                "#" + string.Join("|", mesh.colors32.Select(c => c.r + "," + c.g + "," + c.b + "," + c.a)) +
                "#" + string.Join("|", mesh.triangles);
            using (var sha = System.Security.Cryptography.SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(System.Text.Encoding.UTF8.GetBytes(data))).Replace("-", "").ToLowerInvariant();
        }
        static string CapturePixelReadback()
        {
            var camera = Camera.main;
            if (camera == null) return "unavailable:no-main-camera";
            var texture = new Texture2D(128, 128, TextureFormat.RGBA32, false);
            var previous = RenderTexture.active;
            var target = new RenderTexture(128, 128, 16, RenderTextureFormat.ARGB32);
            camera.targetTexture = target;
            camera.Render();
            RenderTexture.active = target;
            texture.ReadPixels(new Rect(0, 0, 128, 128), 0, 0);
            texture.Apply();
            var pixels = texture.GetPixels32();
            var summary = "readback=" + pixels.Length + ";visibleRgbPixels=" + pixels.Count(p => p.r > 8 || p.g > 8 || p.b > 8);
            camera.targetTexture = null;
            RenderTexture.active = previous;
            Destroy(target); Destroy(texture);
            return summary;
        }
        static bool CaptureMaskClipping(State s, out string evidence)
        {
            var camera = Camera.main;
            if (camera == null || s.imageProxyA == null) { evidence = "mask-pixel-readback-unavailable"; return false; }
            const int size = 512;
            var previous = RenderTexture.active;
            var target = new RenderTexture(size, size, 16, RenderTextureFormat.ARGB32);
            var texture = new Texture2D(size, size, TextureFormat.RGBA32, false);
            camera.targetTexture = target; camera.Render(); RenderTexture.active = target;
            texture.ReadPixels(new Rect(0, 0, size, size), 0, 0); texture.Apply();
            var imageRect = s.imageProxyA.rectTransform;
            var inside = SampleWorld(texture, camera, imageRect.TransformPoint(Vector3.zero));
            // The source image is wider than the mask. This point remains inside the
            // image geometry but lies beyond the 60-pixel mask's right edge.
            var outside = SampleWorld(texture, camera, imageRect.TransformPoint(new Vector3(52, 0, 0)));
            evidence = "maskInside=" + inside + ";maskOutside=" + outside;
            camera.targetTexture = null; RenderTexture.active = previous; Destroy(target); Destroy(texture);
            return inside.a > 24 && outside.a < 8;
        }
        static Color32 SampleWorld(Texture2D texture, Camera camera, Vector3 world)
        {
            var viewport = camera.WorldToViewportPoint(world);
            var x = Mathf.Clamp(Mathf.RoundToInt(viewport.x * (texture.width - 1)), 0, texture.width - 1);
            var y = Mathf.Clamp(Mathf.RoundToInt(viewport.y * (texture.height - 1)), 0, texture.height - 1);
            return texture.GetPixel(x, y);
        }

        public static int CurrentRaycastCount => LastStaticRaycastCount;
    }
}
#endif
