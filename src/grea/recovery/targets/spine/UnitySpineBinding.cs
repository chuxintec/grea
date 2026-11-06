using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace Monkey.Targets.Spine
{
    /// <summary>
    /// Applies one frozen source Spine spec to an already-created Spine Unity
    /// component. The owning importer supplies the exact SkeletonDataAsset
    /// resolved from sourceAssetId; this helper never chooses a fallback.
    /// </summary>
    public static class UnitySpineBinding
    {
        public sealed class ApplyResult
        {
            public string sourceComponentId;
            public bool staticDataBound;
            public bool unresolvedDynamicAssignment;
            public string[] appliedMembers;
            public bool sourceCallbacksExecuted;
        }

        public static ApplyResult Apply(
            Component component,
            string sourceComponentId,
            UnityEngine.Object exactSkeletonDataAsset,
            bool sourceHasStaticDataReference,
            IDictionary<string, object> explicitTargetFields)
        {
            if (component == null) throw new ArgumentNullException(nameof(component));
            if (string.IsNullOrEmpty(sourceComponentId)) throw new ArgumentException("Source component ID is required.", nameof(sourceComponentId));
            if (sourceHasStaticDataReference && exactSkeletonDataAsset == null)
                throw new InvalidOperationException("The exact SkeletonDataAsset is missing for " + sourceComponentId);

            if (sourceHasStaticDataReference)
                SetFirstMember(component, new[] { "SkeletonDataAsset", "skeletonDataAsset" }, exactSkeletonDataAsset);

            var applied = new List<string>();
            if (explicitTargetFields != null)
            {
                foreach (var pair in explicitTargetFields)
                {
                    if (pair.Key != "initialSkinName" && pair.Key != "startingAnimation" &&
                        pair.Key != "startingLoop" && pair.Key != "AnimationName" && pair.Key != "loop" && pair.Key != "timeScale" &&
                        pair.Key != "pmaVertexColors")
                        throw new InvalidOperationException("Unsupported or unresolved Unity Spine field: " + pair.Key);
                    SetMember(component, pair.Key, pair.Value);
                    applied.Add(pair.Key);
                }
            }

            return new ApplyResult
            {
                sourceComponentId = sourceComponentId,
                staticDataBound = sourceHasStaticDataReference,
                unresolvedDynamicAssignment = !sourceHasStaticDataReference,
                appliedMembers = applied.ToArray(),
                sourceCallbacksExecuted = false,
            };
        }

        private static void SetMember(object target, string name, object value)
        {
            for (var type = target.GetType(); type != null; type = type.BaseType)
            {
                var property = type.GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                if (property != null && property.CanWrite)
                {
                    property.SetValue(target, Coerce(value, property.PropertyType), null);
                    return;
                }
                var field = type.GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                if (field != null)
                {
                    field.SetValue(target, Coerce(value, field.FieldType));
                    return;
                }
            }
            throw new MissingMemberException(target.GetType().FullName, name);
        }

        private static void SetFirstMember(object target, string[] names, object value)
        {
            foreach (var name in names)
            {
                if (HasWritableMember(target.GetType(), name))
                {
                    SetMember(target, name, value);
                    return;
                }
            }
            throw new MissingMemberException(target.GetType().FullName, string.Join("|", names));
        }

        private static bool HasWritableMember(Type type, string name)
        {
            for (; type != null; type = type.BaseType)
            {
                var property = type.GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                if (property != null && property.CanWrite) return true;
                if (type.GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly) != null) return true;
            }
            return false;
        }

        private static object Coerce(object value, Type targetType)
        {
            if (value == null) return null;
            var nullable = Nullable.GetUnderlyingType(targetType);
            var effectiveType = nullable ?? targetType;
            if (effectiveType.IsInstanceOfType(value)) return value;
            if (effectiveType.IsEnum)
            {
                if (value is string text) return Enum.Parse(effectiveType, text, false);
                return Enum.ToObject(effectiveType, value);
            }
            return Convert.ChangeType(value, effectiveType);
        }
    }
}
