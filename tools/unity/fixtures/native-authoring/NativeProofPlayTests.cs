using System.Collections;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using Own.Proof;

public sealed class NativeProofPlayTests
{
    [UnityTest] public IEnumerator NativeAssetsWorkWithoutConverter()
    {
        var template=Resources.Load<GameObject>("NativeProof");Assert.IsNotNull(template);
        var root=Object.Instantiate(template);var receiver=root.GetComponent<NativeProofReceiver>();
        Assert.IsTrue(receiver.ConfigurationValid());yield return null;
        var animator=root.GetComponent<Animator>();animator.cullingMode=AnimatorCullingMode.AlwaysAnimate;
        animator.Play("Move",0,0);animator.Update(0);animator.Update(0.5f);
        Assert.That(root.transform.Find("Widget").localPosition.x,Is.EqualTo(4).Within(0.03f),"Manual curve edit takes effect directly in Play");
        Assert.That(root.transform.Find("Widget").localScale,Is.EqualTo(new Vector3(2,3,1)));
        Assert.That(receiver.pulses,Is.GreaterThanOrEqualTo(1),"Native AnimationEvent delivered");
        animator.Play("Return",0,0.5f);animator.Update(0);Assert.That(root.transform.Find("Widget").localPosition.x,Is.EqualTo(2).Within(0.03f),"Explicit interruption to second target clip");
        animator.Play("Move",0,0.99f);animator.Update(0);animator.Update(0.03f);
        Assert.That(root.transform.Find("Widget").localPosition.x,Is.LessThan(0.3f),"Loop seam");
        Object.Destroy(root);yield return null;
    }
}
