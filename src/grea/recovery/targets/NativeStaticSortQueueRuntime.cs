using System;
using System.Collections.Generic;
using System.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Monkey.StaticSortQueueProxy
{
    /// <summary>
    /// Play-mode presentation of native Image, RawImage and TMP properties in the
    /// persisted draw order. Saved meshes and source fields are never rewritten.
    /// Spine, new source objects and unordered non-draw carriers are not lowered here.
    /// </summary>
    internal sealed class NativeStaticSortQueueRuntime : IDisposable
    {
        sealed class Entry
        {
            public Graphic source;
            public NativeStaticSortQueueProxyGraphic proxy;
            public int textSlot;
            public bool created, enabledBefore;
            public Mesh mesh;
        }
        readonly NativeStaticSortQueueProxyPresenter presenter;
        readonly List<Entry> entries = new List<Entry>();
        readonly List<NativeStaticSortInputSurface> inputSources = new List<NativeStaticSortInputSurface>();
        readonly HashSet<Graphic> prepared = new HashSet<Graphic>();
        readonly List<Vector3> vertices = new List<Vector3>();
        readonly List<Vector3> normals = new List<Vector3>();
        readonly List<Vector4> tangents = new List<Vector4>();
        readonly List<Vector4> uv = new List<Vector4>();
        readonly List<Color32> colors = new List<Color32>();
        readonly Vector3[] corners = new Vector3[4];
        bool refreshing;

        public NativeStaticSortQueueRuntime(NativeStaticSortQueueProxyPresenter owner)
        {
            presenter = owner;
            foreach (var binding in owner.bindings ?? Array.Empty<ProxyGraphicBinding>())
            foreach (var proxy in binding?.proxyGraphics ?? Array.Empty<NativeStaticSortQueueProxyGraphic>())
            {
                if (proxy == null || !proxy.AcceptRuntimeOwner()) continue;
                var source = proxy.sourceGraphic != null ? proxy.sourceGraphic : binding.sourceGraphic;
                if (!Supported(source)) continue;
                var text = proxy.GetComponent<NativeStaticSortTextSource>();
                Add(source, proxy, text == null ? 0 : text.materialSlot, false);
            }
            // Ordered empty slots (for example initially empty text) may acquire
            // content later. Unordered retainedNonDraw records lack an accepted
            // draw position, so they are deliberately not guessed into the queue.
            foreach (var marker in owner.GetComponentsInChildren<NativeStaticSortQueueProxyMarker>(true))
            {
                if (marker.kind != "emptyRenderer" || !Supported(marker.sourceGraphic) ||
                    marker.GetComponentInParent<NativeStaticSortQueueProxyPresenter>() != owner) continue;
                var proxy = NewProxy(marker.transform, marker.sourceGraphic, marker.sourceNode, marker.sourceComponentId);
                proxy.queueIndex = marker.queueIndex;
                Add(marker.sourceGraphic, proxy, 0, true);
            }
            CreateRetainedButtonSurfaces();
        }

        static bool Supported(Graphic source) => source is Image || source is RawImage || source is TextMeshProUGUI ||
            source is NativeStaticSortInputSurface;

        void CreateRetainedButtonSurfaces()
        {
            if (presenter.sourceRoot == null) return;
            var lastInputByDisplay = new Dictionary<NativeStaticSortQueueProxyGraphic, Transform>();
            foreach (var retained in presenter.sourceRoot.GetComponentsInChildren<MonoBehaviour>(true)
                .OfType<Monkey.NativeUiContracts.INativeStaticButtonTarget>())
            {
                var button = (retained as Component)?.GetComponent<Button>();
                if (button == null || button.targetGraphic == null || button.GetComponent<Graphic>() != null ||
                    button.targetGraphic.transform.IsChildOf(button.transform)) continue;
                // A native Selectable's targetGraphic controls visual transitions;
                // a sibling Graphic is not an EventSystem ancestor of the Button.
                // The retained typed target supplies the exact conversion relation.
                if (retained.TransitionTarget != button.targetGraphic.gameObject) continue;
                var display = entries.FirstOrDefault(e => e.source == button.targetGraphic);
                if (display == null) continue;
                var go = new GameObject("__native_sort_input", typeof(RectTransform), typeof(CanvasRenderer),
                    typeof(LayoutElement), typeof(NativeStaticSortInputSurface));
                go.hideFlags = HideFlags.DontSave;
                go.transform.SetParent(button.transform, false);
                go.GetComponent<LayoutElement>().ignoreLayout = true;
                var rect = go.GetComponent<RectTransform>();
                rect.anchorMin = Vector2.zero; rect.anchorMax = Vector2.one;
                rect.offsetMin = rect.offsetMax = Vector2.zero;
                var surface = go.GetComponent<NativeStaticSortInputSurface>();
                surface.owner = button;
                inputSources.Add(surface);
                var proxy = NewProxy(display.proxy.transform.parent, surface,
                    "runtime-selectable:" + button.GetEntityId(), "runtime-selectable:" + button.GetEntityId());
                var prior = lastInputByDisplay.TryGetValue(display.proxy, out var tail) ? tail : display.proxy.transform;
                proxy.transform.SetSiblingIndex(prior.GetSiblingIndex() + 1);
                lastInputByDisplay[display.proxy] = proxy.transform;
                proxy.queueIndex = display.proxy.queueIndex;
                proxy.canvasRenderer.cullTransparentMesh = false;
                Add(surface, proxy, 0, true);
            }
        }
        static Mesh NewMesh()
        {
            var mesh = new Mesh { name = "Native sort runtime mesh", hideFlags = HideFlags.DontSave };
            mesh.MarkDynamic(); return mesh;
        }
        void Add(Graphic source, NativeStaticSortQueueProxyGraphic proxy, int slot, bool created)
        {
            entries.Add(new Entry { source = source, proxy = proxy, textSlot = slot,
                created = created, enabledBefore = proxy.enabled, mesh = NewMesh() });
        }
        static NativeStaticSortQueueProxyGraphic NewProxy(Transform parent, Graphic source, string node, string component)
        {
            var go = new GameObject("__runtime_sort_slot", typeof(RectTransform), typeof(CanvasRenderer),
                typeof(CanvasGroup), typeof(NativeStaticSortQueueProxyGraphic));
            go.hideFlags = HideFlags.DontSave;
            go.transform.SetParent(parent, false);
            var proxy = go.GetComponent<NativeStaticSortQueueProxyGraphic>();
            proxy.sourceGraphic = source; proxy.sourceOwnerGraphic = source;
            proxy.sourceNodeId = node; proxy.sourceComponentId = component;
            proxy.raycastTarget = false;
            return proxy;
        }

        public void Refresh()
        {
            if (refreshing || !Application.isPlaying) return;
            refreshing = true;
            try
            {
                prepared.Clear();
                foreach (var surface in inputSources)
                    if (surface != null)
                    {
                        surface.enabled = surface.owner != null && surface.owner.isActiveAndEnabled;
                        surface.raycastTarget = surface.enabled;
                    }
                // Restore native visibility solely while asking the source's own
                // implementation to rebuild; Graphic.Rebuild skips culled renderers.
                foreach (var entry in entries)
                {
                    var source = entry.source;
                    if (source == null || !source.isActiveAndEnabled || !prepared.Add(source)) continue;
                    var renderer = source.canvasRenderer;
                    var cull = renderer.cull;
                    try
                    {
                        renderer.cull = false;
                        if (source is TextMeshProUGUI text) text.ForceMeshUpdate();
                        else source.Rebuild(CanvasUpdate.PreRender);
                    }
                    finally { renderer.cull = cull; }
                }
                ExpandTextSlots();
                foreach (var entry in entries) Refresh(entry);
                foreach (var mask in presenter.maskBindings ?? Array.Empty<ProxyMaskBinding>())
                {
                    if (mask?.sourceMask == null || mask.proxyMask == null) continue;
                    mask.proxyMask.gameObject.SetActive(mask.sourceMask.gameObject.activeInHierarchy);
                    if (mask.sourceMask is Behaviour behavior) mask.proxyMask.enabled = behavior.enabled;
                }
                var inputBindings = entries.Where(e => e.source != null && e.proxy != null).Select(e =>
                    new ProxyGraphicBinding { sourceGraphic = e.source, sourceCanvasRenderer = e.source.canvasRenderer,
                        proxyGraphics = new[] { e.proxy } }).ToArray();
                NativeStaticSortQueueProxyRaycaster.Register(presenter, inputBindings);
            }
            finally { refreshing = false; }
        }

        void ExpandTextSlots()
        {
            foreach (var source in prepared.OfType<TextMeshProUGUI>())
            {
                var existing = entries.Where(e => e.source == source).ToArray();
                if (existing.Length == 0) continue;
                var first = existing.OrderBy(e => e.textSlot).First();
                for (var slot = 0; slot < source.textInfo.materialCount; slot++)
                {
                    if (existing.Any(e => e.textSlot == slot)) continue;
                    var proxy = NewProxy(first.proxy.transform.parent, source,
                        first.proxy.sourceNodeId, first.proxy.sourceComponentId);
                    proxy.transform.SetSiblingIndex(first.proxy.transform.GetSiblingIndex() + slot);
                    proxy.queueIndex = first.proxy.queueIndex;
                    Add(source, proxy, slot, true);
                }
            }
        }

        void Refresh(Entry entry)
        {
            var source = entry.source; var proxy = entry.proxy;
            if (proxy == null) return;
            var visible = source != null && source.isActiveAndEnabled;
            Mesh mesh = null; Material material = null; Texture texture = null;
            if (visible && source is TextMeshProUGUI text)
            {
                visible = entry.textSlot < text.textInfo.materialCount;
                if (visible)
                {
                    var info = text.textInfo.meshInfo[entry.textSlot];
                    mesh = info.mesh; material = info.material;
                    texture = material == null ? source.mainTexture : material.mainTexture;
                }
            }
            else if (visible)
            {
                mesh = source.canvasRenderer.GetMesh(); material = source.material; texture = source.mainTexture;
            }
            if (visible)
            {
                // A conservative hit rect encloses the projected source rectangle;
                // the raycaster subsequently checks the exact original rect/filter.
                UpdateHitRect(source.rectTransform, proxy.rectTransform);
                CopyMesh(mesh, source.transform, proxy.transform, entry.mesh);
            }
            proxy.ApplyRuntime(entry.mesh, texture, material, visible,
                source == null ? Color.clear : source.canvasRenderer.GetColor(),
                source == null ? 0 : source.canvasRenderer.GetInheritedAlpha());
        }

        void UpdateHitRect(RectTransform source, RectTransform target)
        {
            source.GetWorldCorners(corners);
            var parent = target.parent as RectTransform;
            if (parent == null) return;
            var min = new Vector3(float.PositiveInfinity, float.PositiveInfinity, float.PositiveInfinity);
            var max = new Vector3(float.NegativeInfinity, float.NegativeInfinity, float.NegativeInfinity);
            for (var i = 0; i < 4; i++)
            {
                var point = parent.worldToLocalMatrix.MultiplyPoint3x4(corners[i]);
                min = Vector3.Min(min, point); max = Vector3.Max(max, point);
            }
            target.anchorMin = target.anchorMax = parent.pivot;
            target.pivot = new Vector2(.5f, .5f);
            target.localRotation = Quaternion.identity; target.localScale = Vector3.one;
            target.sizeDelta = new Vector2(max.x - min.x, max.y - min.y);
            target.localPosition = (min + max) * .5f;
        }

        void CopyMesh(Mesh source, Transform sourceTransform, Transform targetTransform, Mesh target)
        {
            target.Clear();
            if (source == null || source.vertexCount == 0) return;
            target.indexFormat = source.indexFormat;
            var matrix = targetTransform.worldToLocalMatrix * sourceTransform.localToWorldMatrix;
            source.GetVertices(vertices);
            for (var i = 0; i < vertices.Count; i++) vertices[i] = matrix.MultiplyPoint3x4(vertices[i]);
            target.SetVertices(vertices);
            source.GetColors(colors); if (colors.Count != 0) target.SetColors(colors);
            source.GetNormals(normals);
            var normalMatrix = matrix.inverse.transpose;
            for (var i = 0; i < normals.Count; i++) normals[i] = normalMatrix.MultiplyVector(normals[i]).normalized;
            if (normals.Count != 0) target.SetNormals(normals);
            source.GetTangents(tangents);
            for (var i = 0; i < tangents.Count; i++)
            {
                var old = tangents[i]; var direction = matrix.MultiplyVector(new Vector3(old.x, old.y, old.z)).normalized;
                tangents[i] = new Vector4(direction.x, direction.y, direction.z, old.w);
            }
            if (tangents.Count != 0) target.SetTangents(tangents);
            for (var channel = 0; channel < 8; channel++)
            {
                source.GetUVs(channel, uv);
                if (uv.Count != 0) target.SetUVs(channel, uv);
            }
            target.subMeshCount = source.subMeshCount;
            for (var slot = 0; slot < source.subMeshCount; slot++)
                target.SetIndices(source.GetIndices(slot), source.GetTopology(slot), slot, false);
            target.RecalculateBounds();
        }

        public void Dispose()
        {
            NativeStaticSortQueueProxyRaycaster.Unregister(presenter);
            foreach (var entry in entries)
            {
                if (entry.proxy != null)
                {
                    // Disabling presentation restores the original source draw;
                    // leaving a baked proxy enabled would draw the same UI twice.
                    entry.proxy.ClearRuntime(); entry.proxy.enabled = false;
                    if (entry.created) UnityEngine.Object.Destroy(entry.proxy.gameObject);
                }
                if (entry.mesh != null) UnityEngine.Object.Destroy(entry.mesh);
            }
            entries.Clear();
            foreach (var surface in inputSources)
                if (surface != null)
                {
                    surface.enabled = false; surface.raycastTarget = false;
                    UnityEngine.Object.Destroy(surface.gameObject);
                }
            inputSources.Clear();
        }
    }
}
