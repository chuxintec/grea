using System;
using System.Collections.Generic;
using System.Collections;
using System.Linq;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Monkey.StaticSortQueueProxy
{
    /// <summary>
    /// Supplements a Canvas raycast for baked sort-queue Graphics while returning
    /// the original source GameObject to the ordinary EventSystem pipeline.
    /// Register this component at runtime; it never simulates pointer events.
    /// </summary>
    [AddComponentMenu("")]
    [DisallowMultipleComponent]
    public sealed class NativeStaticSortQueueProxyRaycaster : GraphicRaycaster
    {
        sealed class CanvasRegistry
        {
            public NativeStaticSortQueueProxyRaycaster raycaster;
            public bool ownsRaycaster;
            public GraphicRaycaster settingsSource;
            public bool pendingDestroy;
            public bool cleanupScheduled;
            public int lifecycleVersion;
            public readonly Dictionary<NativeStaticSortQueueProxyPresenter,
                Dictionary<NativeStaticSortQueueProxyGraphic, Graphic>> presenters =
                new Dictionary<NativeStaticSortQueueProxyPresenter,
                    Dictionary<NativeStaticSortQueueProxyGraphic, Graphic>>();
        }

        static readonly Dictionary<Canvas, CanvasRegistry> Registries = new Dictionary<Canvas, CanvasRegistry>();
        bool raycastInProgress;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetRegistriesForPlaySession()
        {
            // With domain reload disabled, static references can outlive the
            // previous Play session. Drop registrations without destroying any
            // component whose ownership cannot be proven in the new session.
            Registries.Clear();
        }

        /// <summary>
        /// Register all presenter bindings, grouped by their native Canvas. A
        /// Canvas must already have exactly one enabled authored GraphicRaycaster;
        /// its blocking and reverse-graphic settings are copied when this runtime
        /// component is made. Call Unregister when the presenter is disabled or destroyed.
        /// </summary>
        public static bool Register(NativeStaticSortQueueProxyPresenter presenter,
            IEnumerable<ProxyGraphicBinding> bindings)
        {
            if (!Application.isPlaying || presenter == null || bindings == null)
                return false;

            var mappings = new Dictionary<Canvas, Dictionary<NativeStaticSortQueueProxyGraphic, Graphic>>();
            foreach (var binding in bindings)
            {
                if (binding == null) continue;
                foreach (var proxy in binding.proxyGraphics ?? Array.Empty<NativeStaticSortQueueProxyGraphic>())
                {
                    if (proxy == null || proxy.canvas == null) continue;
                    var source = proxy.sourceGraphic != null ? proxy.sourceGraphic : binding.sourceGraphic;
                    if (!IsSupportedSource(source)) continue;
                    var canvas = proxy.canvas;
                    if (!mappings.TryGetValue(canvas, out var mapped))
                        mappings.Add(canvas, mapped = new Dictionary<NativeStaticSortQueueProxyGraphic, Graphic>());
                    mapped[proxy] = source;
                }
            }

            // Resolve every existing input owner before mutating any Canvas.
            // Multiple active raycasters may have different policy, so selecting
            // one silently would change the user's configured input behavior.
            var settingsSources = new Dictionary<Canvas, GraphicRaycaster>();
            foreach (var canvas in mappings.Keys)
            {
                if (canvas == null) return false;
                var ownRaycaster = canvas.GetComponent<NativeStaticSortQueueProxyRaycaster>();
                if (Registries.TryGetValue(canvas, out var registered) && registered.raycaster == null)
                {
                    Registries.Remove(canvas);
                    registered = null;
                }
                if (ownRaycaster != null && !ownRaycaster.enabled && !IsOwnedRuntimeRaycaster(ownRaycaster))
                    return false;
                var activeSources = canvas.GetComponents<GraphicRaycaster>()
                    .Where(raycaster => raycaster != null && raycaster != ownRaycaster && raycaster.isActiveAndEnabled)
                    .ToArray();
                if (activeSources.Length != 1) return false;
                if (registered != null && registered.settingsSource != activeSources[0])
                    return false;
                settingsSources.Add(canvas, activeSources[0]);
            }

            // Remove stale Canvas mappings from a runtime refresh.
            foreach (var pair in Registries.ToArray())
            {
                if (!pair.Value.presenters.ContainsKey(presenter) || mappings.ContainsKey(pair.Key)) continue;
                pair.Value.presenters.Remove(presenter);
                DestroyUnusedRegistry(pair.Key, pair.Value);
            }

            foreach (var pair in mappings)
            {
                var canvas = pair.Key;
                if (!Registries.TryGetValue(canvas, out var registry))
                {
                    var existing = canvas.GetComponent<NativeStaticSortQueueProxyRaycaster>();
                    var owned = existing == null || IsOwnedRuntimeRaycaster(existing);
                    var raycaster = existing ?? canvas.gameObject.AddComponent<NativeStaticSortQueueProxyRaycaster>();
                    if (raycaster == null) return false;
                    if (owned)
                    {
                        raycaster.hideFlags |= HideFlags.DontSave;
                        if (!raycaster.enabled) raycaster.enabled = true;
                    }
                    raycaster.CopySettings(settingsSources[canvas]);
                    registry = new CanvasRegistry
                    {
                        raycaster = raycaster,
                        ownsRaycaster = owned,
                        settingsSource = settingsSources[canvas]
                    };
                    Registries.Add(canvas, registry);
                }
                registry.presenters[presenter] = pair.Value;
                registry.pendingDestroy = false;
                registry.cleanupScheduled = false;
                registry.lifecycleVersion++;
                if (registry.ownsRaycaster && registry.raycaster != null && !registry.raycaster.enabled)
                    registry.raycaster.enabled = true;
            }
            return true;
        }

        /// <summary>Remove a presenter's proxy mappings and destroy an unused runtime raycaster we created.</summary>
        public static void Unregister(NativeStaticSortQueueProxyPresenter presenter)
        {
            if (presenter == null) return;
            foreach (var pair in Registries.ToArray())
            {
                var registry = pair.Value;
                registry.presenters.Remove(presenter);
                DestroyUnusedRegistry(pair.Key, registry);
            }
        }

        static void DestroyUnusedRegistry(Canvas canvas, CanvasRegistry registry)
        {
            if (registry.presenters.Count != 0) return;
            registry.pendingDestroy = true;
            if (!registry.ownsRaycaster || registry.raycaster == null)
            {
                Registries.Remove(canvas);
                return;
            }

            if (!registry.cleanupScheduled)
            {
                registry.cleanupScheduled = registry.raycaster.gameObject.activeInHierarchy;
                if (registry.raycaster.gameObject.activeInHierarchy)
                {
                    var generation = ++registry.lifecycleVersion;
                    registry.raycaster.StartCoroutine(DestroyUnusedAfterFrame(canvas, registry, generation));
                }
            }
            registry.raycaster.enabled = false;
        }

        protected override void OnDisable()
        {
            base.OnDisable();
        }

        static IEnumerator DestroyUnusedAfterFrame(Canvas canvas, CanvasRegistry registry, int generation)
        {
            yield return null;
            if (canvas == null || !Registries.TryGetValue(canvas, out var current) || current != registry ||
                registry.lifecycleVersion != generation || !registry.pendingDestroy || registry.presenters.Count != 0)
                yield break;

            Registries.Remove(canvas);
            if (registry.ownsRaycaster && registry.raycaster != null)
                UnityEngine.Object.Destroy(registry.raycaster);
        }

        public override void Raycast(PointerEventData eventData, List<RaycastResult> resultAppendList)
        {
            if (!isActiveAndEnabled || eventData == null || resultAppendList == null || raycastInProgress ||
                !Registries.TryGetValue(GetComponent<Canvas>(), out var registry) || registry.raycaster != this ||
                registry.pendingDestroy || registry.presenters.Count == 0 || !TryRefreshSettingsSource(registry))
                return;

            raycastInProgress = true;
            try
            {
                var proxySources = new Dictionary<Graphic, Graphic>();
                var restoreRaycastTargets = new List<KeyValuePair<Graphic, bool>>();
                foreach (var source in registry.presenters.Values)
                foreach (var pair in source)
                {
                    var proxy = pair.Key;
                    var original = pair.Value;
                    if (proxy == null || !IsSupportedSource(original) || !proxy.isActiveAndEnabled ||
                        !proxy.gameObject.activeInHierarchy)
                        continue;

                    proxySources[proxy] = original;
                    if (!proxy.raycastTarget)
                    {
                        restoreRaycastTargets.Add(new KeyValuePair<Graphic, bool>(proxy, false));
                        proxy.raycastTarget = true;
                    }
                }

                List<RaycastResult> proxyHits;
                try
                {
                    proxyHits = new List<RaycastResult>();
                    base.Raycast(eventData, proxyHits);
                }
                finally
                {
                    foreach (var entry in restoreRaycastTargets)
                        if (entry.Key != null) entry.Key.raycastTarget = entry.Value;
                }

                var seenSources = new HashSet<GameObject>();
                foreach (var hit in proxyHits)
                {
                    if (hit.gameObject == null) continue;
                    var proxy = hit.gameObject.GetComponent<NativeStaticSortQueueProxyGraphic>();
                    if (proxy == null || !proxySources.TryGetValue(proxy, out var source) ||
                        !TryGetEligibleTarget(source, eventData.position, eventCamera, out var target) ||
                        !seenSources.Add(target))
                        continue;

                    // Preserve the proxy's geometry depth and Canvas sorting data,
                    // but let normal EventSystem dispatch target the source object.
                    var mappedHit = hit;
                    mappedHit.gameObject = target;
                    resultAppendList.Add(mappedHit);
                }
            }
            finally
            {
                raycastInProgress = false;
            }
        }

        void CopySettings(GraphicRaycaster source)
        {
            ignoreReversedGraphics = source.ignoreReversedGraphics;
            blockingObjects = source.blockingObjects;
            blockingMask = source.blockingMask;
        }

        bool TryRefreshSettingsSource(CanvasRegistry registry)
        {
            var canvas = GetComponent<Canvas>();
            if (canvas == null || registry.settingsSource == null || !registry.settingsSource.isActiveAndEnabled ||
                registry.settingsSource.GetComponent<Canvas>() != canvas)
                return false;

            var activeSources = canvas.GetComponents<GraphicRaycaster>()
                .Where(raycaster => raycaster != null && raycaster != this && raycaster.isActiveAndEnabled)
                .ToArray();
            if (activeSources.Length != 1 || activeSources[0] != registry.settingsSource)
                return false;

            CopySettings(registry.settingsSource);
            return true;
        }

        static bool IsOwnedRuntimeRaycaster(NativeStaticSortQueueProxyRaycaster raycaster)
        {
            return raycaster != null && (raycaster.hideFlags & HideFlags.DontSave) == HideFlags.DontSave;
        }

        static bool IsSupportedSource(Graphic source)
        {
            // Input-only blockers keep their ordinary raycaster route. Accept
            // only the display families actually mirrored by the runtime owner.
            return source is Image || source is RawImage || source is TMPro.TextMeshProUGUI ||
                source is NativeStaticSortInputSurface;
        }

        static bool TryGetEligibleTarget(Graphic source, Vector2 screenPosition, Camera camera,
            out GameObject target)
        {
            target = null;
            if (!IsSupportedSource(source) || !source.enabled || !source.gameObject.activeInHierarchy ||
                !source.raycastTarget || !RectTransformUtility.RectangleContainsScreenPoint(
                    source.rectTransform, screenPosition, camera) || !source.Raycast(screenPosition, camera))
                return false;

            var inputSurface = source as NativeStaticSortInputSurface;
            if (inputSurface != null)
            {
                if (inputSurface.owner == null || !inputSurface.owner.isActiveAndEnabled)
                    return false;
                target = inputSurface.owner.gameObject;
                return target != null;
            }

            target = source.gameObject;
            return target != null;
        }
    }
}
