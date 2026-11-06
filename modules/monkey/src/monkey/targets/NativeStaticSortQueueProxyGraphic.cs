using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace Monkey.StaticSortQueueProxy
{
    /// <summary>Draws a baked native CanvasRenderer mesh through uGUI MaskableGraphic stencil state.</summary>
    [AddComponentMenu("")]
    public sealed class NativeStaticSortQueueProxyGraphic : MaskableGraphic
    {
        public string sourceNodeId, sourceComponentId, sourceMeshSha256, meshContentSha256, expectedSourceGraphicType;
        public bool generatedSourceChild;
        public float sourceRendererAlpha, sourceInheritedAlpha;
        public bool sourceOpacityCaptured;
        public string sourceType;
        public int queueIndex, submeshIndex;
        public Graphic sourceGraphic;
        public Graphic sourceOwnerGraphic;
        public Mesh proxyMesh;
        public int[] sourceUvChannelVertexCounts;
        public int[] sourceUvChannelDimensions;
        public Texture proxyTexture;
        public Material proxyBaseMaterial;
        public Texture sourceBaseTexture;
        public string sourceMaterialFingerprint;
        public string transformCaptureDiagnosticJson;
        public string meshAssetGuid, sourceMaterialGuid, sourceTextureGuid;
        [System.NonSerialized] Mesh runtimeMesh;
        [System.NonSerialized] Texture runtimeTexture;
        [System.NonSerialized] Material runtimeMaterial;
        [System.NonSerialized] bool runtimePresentation;
        [System.NonSerialized] bool runtimeManaged;
        [System.NonSerialized] float runtimeInheritedAlpha;
        [System.NonSerialized] Color runtimeRendererColor;

        public override Texture mainTexture => runtimePresentation ? runtimeTexture ?? Texture2D.whiteTexture :
            proxyTexture == null ? Texture2D.whiteTexture : proxyTexture;
        public override Material material
        {
            get => runtimePresentation ? runtimeMaterial ?? base.material : proxyBaseMaterial != null ? proxyBaseMaterial : base.material;
            set { proxyBaseMaterial = value; base.material = value; }
        }

        // VertexHelper/UIVertex only carries TEXCOORD0..3. Use the persisted
        // native Mesh directly so source TEXCOORD4..7 survive Canvas rendering.
        // Graphic still owns materialForRendering, allowing MaskableGraphic's
        // ordinary uGUI stencil modifier to apply the ancestor Mask state.
        protected override void UpdateGeometry()
        {
            if (runtimePresentation || sourceOpacityCaptured)
            {
                var opacity = GetComponent<CanvasGroup>();
                if (opacity != null)
                {
                    opacity.ignoreParentGroups = true;
                    opacity.alpha = runtimePresentation ? runtimeInheritedAlpha : sourceInheritedAlpha;
                }
                if (runtimePresentation) canvasRenderer.SetColor(runtimeRendererColor);
                else canvasRenderer.SetAlpha(sourceRendererAlpha);
            }
            canvasRenderer.SetMesh(runtimePresentation ? runtimeMesh : proxyMesh);
        }

        // Runtime data never replaces the serialized fixed-state proof assets.
        internal bool AcceptRuntimeOwner()
        {
            // A consumer may have intentionally replaced a saved proxy with a
            // live project control. Preserve that explicit initial opt-out.
            if (!runtimeManaged && !enabled) return false;
            runtimeManaged = true;
            return true;
        }

        internal void ApplyRuntime(Mesh mesh, Texture texture, Material sourceMaterial,
            bool visible, Color rendererColor, float inheritedAlpha)
        {
            var materialChanged = !runtimePresentation || runtimeMaterial != sourceMaterial || runtimeTexture != texture;
            runtimePresentation = true; runtimeMesh = mesh; runtimeTexture = texture; runtimeMaterial = sourceMaterial;
            runtimeRendererColor = rendererColor; runtimeInheritedAlpha = inheritedAlpha;
            enabled = visible;
            if (!visible) return;
            if (materialChanged) RecalculateMasking();
            canvasRenderer.cull = false;
            UpdateGeometry();
            UpdateMaterial();
        }

        internal void ClearRuntime()
        {
            runtimePresentation = false; runtimeMesh = null; runtimeTexture = null; runtimeMaterial = null;
            SetAllDirty();
        }

        protected override void OnPopulateMesh(VertexHelper vh)
        {
            vh.Clear();
            if (proxyMesh == null) return;
            var positions = proxyMesh.vertices;
            var colors = proxyMesh.colors32;
            var uv0 = new List<Vector4>(); var uv1 = new List<Vector4>();
            var uv2 = new List<Vector4>(); var uv3 = new List<Vector4>();
            proxyMesh.GetUVs(0, uv0); proxyMesh.GetUVs(1, uv1);
            proxyMesh.GetUVs(2, uv2); proxyMesh.GetUVs(3, uv3);
            var normals = proxyMesh.normals; var tangents = proxyMesh.tangents;
            for (var i = 0; i < positions.Length; i++)
            {
                var vertex = UIVertex.simpleVert;
                vertex.position = positions[i];
                vertex.color = colors != null && colors.Length == positions.Length ? colors[i] : Color.white;
                if (uv0.Count == positions.Length) vertex.uv0 = uv0[i];
                if (uv1.Count == positions.Length) vertex.uv1 = uv1[i];
                if (uv2.Count == positions.Length) vertex.uv2 = uv2[i];
                if (uv3.Count == positions.Length) vertex.uv3 = uv3[i];
                if (normals != null && normals.Length == positions.Length) vertex.normal = normals[i];
                if (tangents != null && tangents.Length == positions.Length) vertex.tangent = tangents[i];
                vh.AddVert(vertex);
            }
            var triangles = proxyMesh.GetTriangles(0);
            for (var i = 0; i + 2 < triangles.Length; i += 3) vh.AddTriangle(triangles[i], triangles[i + 1], triangles[i + 2]);
        }
    }
}
