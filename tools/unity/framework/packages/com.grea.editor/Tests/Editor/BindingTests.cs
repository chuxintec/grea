using Grea.Editor;
using Grea.UI.UGUI;
using NUnit.Framework;
using UnityEngine;

namespace Grea.Tests
{
    public sealed class BindingTests
    {
        [Test] public void ReportsExactObjectComponentFieldWithoutChangingHierarchy()
        {
            var go = new GameObject("synthetic");
            try
            {
                go.AddComponent<CommandButton>(); int before = go.GetComponents<Component>().Length;
                var findings = BindingValidator.Inspect(go);
                Assert.AreEqual(1, findings.Count); Assert.AreEqual("button", findings[0].Field);
                Assert.AreEqual("Grea.UI.UGUI.CommandButton", findings[0].Component);
                Assert.AreEqual(before, go.GetComponents<Component>().Length);
            }
            finally { Object.DestroyImmediate(go); }
        }
        [Test] public void NoBindingComponentsIsValid()
        {
            var go = new GameObject("synthetic");
            try { Assert.AreEqual(0, BindingValidator.Inspect(go).Count); }
            finally { Object.DestroyImmediate(go); }
        }
    }
}
