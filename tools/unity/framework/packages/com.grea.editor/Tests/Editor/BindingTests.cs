using Grea.Editor;
using Grea.UI.UGUI;
using NUnit.Framework;
using UnityEngine;
using System;
using System.Reflection;
using Object = UnityEngine.Object;

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
        [Test] public void SafeAreaUsesExplicitLayoutRootAndRejectsInvalidDimensions()
        {
            var go = new GameObject("host", typeof(RectTransform)); go.SetActive(false);
            try
            {
                var host = go.AddComponent<UIHost>();
                var safe = new GameObject("safe", typeof(RectTransform)).GetComponent<RectTransform>();
                safe.SetParent(go.transform, false);
                var field = typeof(UIHost).GetField("safeAreaRoot");
                Assert.IsNotNull(field, "UIHost needs an explicit safe-area layout entry");
                field.SetValue(host, safe);
                var method = typeof(UIHost).GetMethod("ApplySafeArea", new[] { typeof(Rect), typeof(Vector2) }); Assert.IsNotNull(method);
                method.Invoke(host, new object[] { new Rect(0, 40, 400, 720), new Vector2(400, 800) });
                Assert.That(Vector2.Distance(safe.anchorMin, new Vector2(0, .05f)), Is.LessThan(.0001f));
                Assert.That(Vector2.Distance(safe.anchorMax, new Vector2(1, .95f)), Is.LessThan(.0001f));
                var prior = safe.anchorMin;
                var error = Assert.Throws<TargetInvocationException>(() => method.Invoke(host,
                    new object[] { new Rect(0, 0, 400, 800), Vector2.zero }));
                Assert.IsInstanceOf<ArgumentOutOfRangeException>(error.InnerException);
                Assert.AreEqual(prior, safe.anchorMin);
            }
            finally { Object.DestroyImmediate(go); }
        }
        [Test] public void SafeAreaIntersectsNonzeroViewportAndScalesWithoutChangingUnits()
        {
            var go = new GameObject("host", typeof(RectTransform)); go.SetActive(false);
            try
            {
                var host = go.AddComponent<UIHost>(); host.safeAreaRoot = go.GetComponent<RectTransform>();
                host.ApplySafeArea(new Rect(50,240,500,720), new Rect(100,200,400,800));
                Assert.That(host.safeAreaRoot.anchorMin.y, Is.EqualTo(.05f).Within(.0001f));
                Assert.That(host.safeAreaRoot.anchorMax.y, Is.EqualTo(.95f).Within(.0001f));
                Assert.AreEqual(0,host.safeAreaRoot.anchorMin.x); Assert.AreEqual(1,host.safeAreaRoot.anchorMax.x);
                host.ApplySafeArea(new Rect(100,480,1000,1440), new Rect(200,400,800,1600));
                Assert.That(host.safeAreaRoot.anchorMin.y, Is.EqualTo(.05f).Within(.0001f));
                var before = host.safeAreaRoot.anchorMax;
                Assert.Throws<ArgumentOutOfRangeException>(()=>host.ApplySafeArea(new Rect(0,0,10,10),new Rect(100,100,100,100)));
                Assert.Throws<ArgumentOutOfRangeException>(()=>host.ApplySafeArea(new Rect(float.NaN,0,10,10),new Vector2(100,100)));
                Assert.Throws<ArgumentOutOfRangeException>(()=>host.ApplySafeArea(new Rect(0,0,-1,10),new Vector2(100,100)));
                Assert.AreEqual(before, host.safeAreaRoot.anchorMax);
            }
            finally { Object.DestroyImmediate(go); }
        }
    }
}
