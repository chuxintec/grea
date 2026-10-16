using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Grea.Editor
{
    // Read the current frame without forcing layout, replaying animation or altering selection.
    public static class PresentationSampler
    {
        [Serializable] public sealed class Node
        {
            public string id, component, shader, text, blend = "unknown";
            public bool active, culled, raycast_target, raycast_top;
            public float effective_alpha, track_time;
            public int mesh_vertices, mask_count, text_length, particle_count;
            public bool track_observed, particles_observed, text_observed;
            public Vector3[] world_corners;
        }
        [Serializable] public sealed class Frame
        {
            public int frame;
            public string phase;
            public Node[] nodes;
        }
        [Serializable] public sealed class Capture
        {
            public int schema_version = 1;
            public string candidate_sha256, run_instance;
            public Frame[] frames;
        }
        static string Identity(Transform transform)
        {
            var parts = new List<string>();
            for (var current=transform; current; current=current.parent)
                parts.Add(current.name+"["+current.GetSiblingIndex()+"]");
            parts.Reverse(); return string.Join("/",parts);
        }
        public static Frame Sample(GameObject root, string phase, Vector2? pointer = null)
        {
            if (!root) throw new ArgumentNullException(nameof(root));
            if (!Application.isPlaying) throw new InvalidOperationException("Live Play Mode is required");
            var hits = new List<RaycastResult>();
            if (pointer.HasValue && EventSystem.current)
                EventSystem.current.RaycastAll(new PointerEventData(EventSystem.current) { position=pointer.Value },hits);
            var result = new List<Node>();
            foreach (var graphic in root.GetComponentsInChildren<Graphic>(true))
            {
                var node = new Node {id=Identity(graphic.transform)+"/"+graphic.GetType().Name,
                    component=graphic.GetType().FullName, active=graphic.isActiveAndEnabled,
                    culled=graphic.canvasRenderer.cull, raycast_target=graphic.raycastTarget,
                    raycast_top=hits.Count>0 && hits[0].gameObject==graphic.gameObject,
                    effective_alpha=graphic.color.a*graphic.canvasRenderer.GetInheritedAlpha(),
                    mask_count=graphic.GetComponentsInParent<Mask>(true).Count(x=>x.enabled)+graphic.GetComponentsInParent<RectMask2D>(true).Count(x=>x.enabled),
                    shader=graphic.material ? graphic.material.shader.name : "", world_corners=new Vector3[4]};
                graphic.rectTransform.GetWorldCorners(node.world_corners);
                var mesh=graphic.canvasRenderer.GetMesh();
                node.mesh_vertices=mesh ? mesh.vertexCount : 0;
                if (graphic is Text legacy) { node.text=legacy.text; node.text_observed=true; }
                else if (graphic.GetType().Namespace=="TMPro")
                {
                    // Optional TMP inspection; no runtime reference or source-engine adapter.
                    node.text=graphic.GetType().GetProperty("text")?.GetValue(graphic) as string;
                    node.text_observed=node.text!=null;
                }
                node.text_length=node.text?.Length??0;
                // Shader semantics are deliberately unknown until an explicit adapter establishes them.
                result.Add(node);
            }
            foreach (var animator in root.GetComponentsInChildren<Animator>(true))
            {
                var observable=animator.isActiveAndEnabled && animator.runtimeAnimatorController && animator.layerCount>0;
                result.Add(new Node { id=Identity(animator.transform)+"/Animator", component="UnityEngine.Animator",
                    active=animator.isActiveAndEnabled, track_observed=observable,
                    track_time=observable ? animator.GetCurrentAnimatorStateInfo(0).normalizedTime : 0 });
            }
            foreach (var particles in root.GetComponentsInChildren<ParticleSystem>(true))
                result.Add(new Node {id=Identity(particles.transform)+"/ParticleSystem",component="UnityEngine.ParticleSystem",
                    active=particles.gameObject.activeInHierarchy,particles_observed=true,particle_count=particles.particleCount});
            return new Frame {frame=Time.frameCount,phase=phase,nodes=result.ToArray()};
        }
    }
}
