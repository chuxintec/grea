using System;
using System.Collections.Generic;
using Grea.Foundation.Runtime;
using UnityEditor;
using UnityEngine;

namespace Grea.Editor
{
    public sealed class BindingFinding
    {
        public string ObjectPath { get; }
        public string Component { get; }
        public string Field { get; }
        public string Code { get; }
        public BindingFinding(string path, string component, string field, string code)
        { ObjectPath = path; Component = component; Field = field; Code = code; }
    }
    public static class BindingValidator
    {
        // Explicit root only. No scene search, auto-fix, SaveAssets or asset writes.
        public static IReadOnlyList<BindingFinding> Inspect(GameObject root)
        {
            if (!root) throw new ArgumentNullException(nameof(root));
            var result = new List<BindingFinding>();
            foreach (var transform in root.GetComponentsInChildren<Transform>(true))
            {
                var path = AnimationUtility.CalculateTransformPath(transform, root.transform);
                foreach (var component in transform.GetComponents<MonoBehaviour>())
                {
                    if (!component) { result.Add(new BindingFinding(path, "MonoBehaviour", "", "MISSING_SCRIPT")); continue; }
                    if (!(component is IBindingCheck check)) continue;
                    foreach (var field in check.MissingBindings())
                        result.Add(new BindingFinding(path, component.GetType().FullName, field, "MISSING_BINDING"));
                }
            }
            return result;
        }
    }
}
