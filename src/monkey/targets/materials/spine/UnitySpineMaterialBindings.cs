using System;
using System.Reflection;
using UnityEngine;

namespace Monkey.Targets.SpineMaterials
{
    /// <summary>
    /// Applies an exact one-color Cocos Spine blend profile to already-created
    /// Unity Spine runtime materials. The importing owner supplies the
    /// SkeletonRenderer component and the page/slot mapping from source pins.
    /// </summary>
    public static class UnitySpineMaterialBindings
    {
        public const string SourceProfile = "cocos24-builtin-spine-material-v1";
        public const string ShaderName = "Monkey/SpineSourceProfile/Colored";
        public const string ShaderSourceSha256 = "0fe1ea3481787d0de2bd7545c8e77d769c681a7d30ca48d6ad56482bdeec549b";
        public const int BlendZero = 0;
        public const int BlendOne = 1;
        public const int BlendDstColor = 2;
        public const int BlendSrcAlpha = 5;
        public const int BlendOneMinusSrcColor = 6;
        public const int BlendOneMinusSrcAlpha = 10;

        public sealed class NativeShaderProof
        {
            public string sourceProfile;
            public string shaderName;
            public string shaderSourceSha256;
            public bool shaderImported;
            public bool nativeShaderReadback;
        }

        public sealed class Readback
        {
            public string componentSourceId;
            public string sourceAtlasPage;
            public string shaderName;
            public string shaderSourceSha256;
            public int normalSrcBlend;
            public int normalDstBlend;
            public int additiveSrcBlend;
            public int additiveDstBlend;
            public bool pmaVertexColors;
            public bool materialReferencesVerified;
            public bool pmaVertexColorsMemberApplicable;
        }

        /// <summary>Apply one source-pinned blend mode to an owned native profile Material.</summary>
        public static void ConfigureProfileMaterial(Material material, string blendMode, bool premultipliedAlpha)
        {
            if (material == null || material.shader == null || material.shader.name != ShaderName)
                throw new InvalidOperationException("Unity Spine source-profile Material/Shader identity is invalid.");
            var factors = BlendFactors(blendMode, premultipliedAlpha);
            SetBlend(material, factors[0], factors[1]);
        }

        public static bool ProfileMaterialMatches(Material material, string blendMode, bool premultipliedAlpha)
        {
            if (material == null || material.shader == null || material.shader.name != ShaderName) return false;
            var factors = BlendFactors(blendMode, premultipliedAlpha);
            return material.HasProperty("_SrcBlend") && material.HasProperty("_DstBlend") &&
                material.GetInt("_SrcBlend") == factors[0] && material.GetInt("_DstBlend") == factors[1];
        }

        public static int[] BlendFactors(string blendMode, bool premultipliedAlpha)
        {
            int source = premultipliedAlpha ? BlendOne : BlendSrcAlpha;
            if (blendMode == "normal") return new[] { source, BlendOneMinusSrcAlpha };
            if (blendMode == "additive") return new[] { source, BlendOne };
            if (blendMode == "multiply") return new[] { BlendDstColor, BlendOneMinusSrcAlpha };
            if (blendMode == "screen") return new[] { BlendOne, BlendOneMinusSrcColor };
            throw new InvalidOperationException("Unsupported source Spine blend mode: " + blendMode);
        }

        /// <summary>
        /// Configure separate native materials for normal/additive source slots.
        /// Attach them through the pinned Spine 3.8 BlendModeMaterials mapping,
        /// keyed by the source Atlas page. This method never picks a fallback.
        /// </summary>
        public static Readback Configure(Component skeletonRenderer,
            Material normalMaterial, Material additiveMaterial, bool premultipliedAlpha,
            bool hasAdditiveSlots, bool materialReferencesVerified,
            string componentSourceId, string sourceAtlasPage, NativeShaderProof proof)
        {
            if (string.IsNullOrEmpty(componentSourceId))
                throw new ArgumentException("Source component identity is required.", nameof(componentSourceId));
            if (string.IsNullOrEmpty(sourceAtlasPage))
                throw new ArgumentException("Source Atlas page identity is required.", nameof(sourceAtlasPage));
            if (skeletonRenderer == null || normalMaterial == null)
                throw new InvalidOperationException("A native SkeletonRenderer and normal material are required.");
            if (hasAdditiveSlots && additiveMaterial == null)
                throw new InvalidOperationException("Source additive slots require a separate additive material.");
            if (!materialReferencesVerified)
                throw new InvalidOperationException("Source Atlas page/slot material references must be read back before accepting this binding.");
            if (proof == null || proof.sourceProfile != SourceProfile || proof.shaderName != ShaderName ||
                proof.shaderSourceSha256 != ShaderSourceSha256 || !proof.shaderImported || !proof.nativeShaderReadback)
                throw new InvalidOperationException("Pinned Unity source-profile shader import/readback proof is required.");
            if (normalMaterial.shader == null || normalMaterial.shader.name != ShaderName ||
                (additiveMaterial != null && (additiveMaterial.shader == null || additiveMaterial.shader.name != ShaderName)))
                throw new InvalidOperationException("Unity Spine materials do not use the pinned source-profile shader.");

            bool pmaMemberApplicable = skeletonRenderer.GetType().FullName != "Spine.Unity.SkeletonGraphic";
            int src = premultipliedAlpha ? BlendOne : BlendSrcAlpha;
            SetBlend(normalMaterial, src, BlendOneMinusSrcAlpha);
            if (additiveMaterial != null) SetBlend(additiveMaterial, src, BlendOne);
            if (pmaMemberApplicable) SetBooleanMember(skeletonRenderer, "pmaVertexColors", premultipliedAlpha);

            var readback = new Readback
            {
                componentSourceId = componentSourceId,
                sourceAtlasPage = sourceAtlasPage,
                shaderName = normalMaterial.shader.name,
                shaderSourceSha256 = proof.shaderSourceSha256,
                normalSrcBlend = normalMaterial.GetInt("_SrcBlend"),
                normalDstBlend = normalMaterial.GetInt("_DstBlend"),
                additiveSrcBlend = additiveMaterial != null ? additiveMaterial.GetInt("_SrcBlend") : BlendZero,
                additiveDstBlend = additiveMaterial != null ? additiveMaterial.GetInt("_DstBlend") : BlendZero,
                pmaVertexColors = pmaMemberApplicable ? ReadBooleanMember(skeletonRenderer, "pmaVertexColors") : false,
                pmaVertexColorsMemberApplicable = pmaMemberApplicable,
                materialReferencesVerified = materialReferencesVerified,
            };
            if (readback.normalSrcBlend != src || readback.normalDstBlend != BlendOneMinusSrcAlpha ||
                (hasAdditiveSlots && (readback.additiveSrcBlend != src || readback.additiveDstBlend != BlendOne)) ||
                readback.pmaVertexColors != premultipliedAlpha)
                throw new InvalidOperationException("Native Unity Spine blend/PMA readback differs from the source contract.");
            return readback;
        }

        private static void SetBlend(Material material, int source, int destination)
        {
            material.SetInt("_SrcBlend", source);
            material.SetInt("_DstBlend", destination);
            material.SetOverrideTag("RenderType", "Transparent");
            material.renderQueue = (int)UnityEngine.Rendering.RenderQueue.Transparent;
        }

        private static void SetBooleanMember(Component target, string name, bool value)
        {
            var type = target.GetType();
            var field = type.GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (field != null && field.FieldType == typeof(bool)) { field.SetValue(target, value); return; }
            var property = type.GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (property != null && property.CanWrite && property.PropertyType == typeof(bool)) { property.SetValue(target, value); return; }
            throw new MissingMemberException(type.FullName, name);
        }

        private static bool ReadBooleanMember(Component target, string name)
        {
            var type = target.GetType();
            var field = type.GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (field != null && field.FieldType == typeof(bool)) return (bool)field.GetValue(target);
            var property = type.GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            if (property != null && property.CanRead && property.PropertyType == typeof(bool)) return (bool)property.GetValue(target);
            throw new MissingMemberException(type.FullName, name);
        }
    }
}
