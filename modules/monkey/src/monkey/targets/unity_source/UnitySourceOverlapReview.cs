#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;

// Call Observe after the preview canvas has rebuilt its layout. This reports
// conflicting sibling labels for review; it never changes visibility itself.
public static class UnitySourceOverlapReview
{
    [Serializable] private class Finding
    {
        public string root, first, second, firstText, secondText;
        public float coverage;
    }
    [Serializable] private class Report
    {
        public int inspected;
        public List<Finding> findings = new List<Finding>();
    }
    private static Report report = new Report();
    public static void Begin() { report = new Report(); }
    private static string PathOf(Transform t, Transform root)
    {
        var indices=new Stack<int>();
        while (t!=root) { indices.Push(t.GetSiblingIndex()); t=t.parent; }
        return "0/"+string.Join("/",indices);
    }
    private static bool BoundsOf(Text text, Transform parent, out Rect bounds)
    {
        bounds=default;
        if (!text.isActiveAndEnabled || text.color.a<=0.02f || string.IsNullOrWhiteSpace(text.text)
            || text.text.Trim().Length<2 || text.canvasRenderer.cull || text.canvasRenderer.GetInheritedAlpha()<=0.02f)
            return false;
        var vertices=text.cachedTextGenerator.verts;
        Vector2 lo=Vector2.positiveInfinity,hi=Vector2.negativeInfinity;
        for (int j=0;j+3<vertices.Count;j+=4)
        {
            if ((vertices[j].position-vertices[j+2].position).sqrMagnitude<0.0001f) continue;
            for (int k=j;k<j+4;k++)
            {
                Vector2 pt=parent.InverseTransformPoint(text.transform.TransformPoint(vertices[k].position/text.pixelsPerUnit));
                lo=Vector2.Min(lo,pt);hi=Vector2.Max(hi,pt);
            }
        }
        if (hi.x-lo.x<4 || hi.y-lo.y<4) return false;
        bounds=Rect.MinMaxRect(lo.x,lo.y,hi.x,hi.y);
        return true;
    }
    public static void Observe(GameObject instance,string path)
    {
        report.inspected++;
        foreach (var group in instance.GetComponentsInChildren<Text>().GroupBy(t=>t.transform.parent))
        {
            if (!group.Key) continue;
            var labels=new List<KeyValuePair<Text,Rect>>();
            foreach (var t in group)
                if (BoundsOf(t,group.Key,out Rect rect)) labels.Add(new KeyValuePair<Text,Rect>(t,rect));
            for (int i=0;i<labels.Count;i++)
            for (int j=i+1;j<labels.Count;j++)
            {
                var a=labels[i];var b=labels[j];
                if (a.Key.text.Trim()==b.Key.text.Trim()) continue;
                float x=Mathf.Min(a.Value.xMax,b.Value.xMax)-Mathf.Max(a.Value.xMin,b.Value.xMin);
                float y=Mathf.Min(a.Value.yMax,b.Value.yMax)-Mathf.Max(a.Value.yMin,b.Value.yMin);
                if (x<=0 || y<=0) continue;
                float coverage=x*y/Mathf.Min(a.Value.width*a.Value.height,b.Value.width*b.Value.height);
                if (coverage<0.85f) continue;
                report.findings.Add(new Finding {root=path,first=PathOf(a.Key.transform,instance.transform),
                    second=PathOf(b.Key.transform,instance.transform),firstText=a.Key.text,
                    secondText=b.Key.text,coverage=coverage});
            }
        }
    }
    public static void Finish()
    {
        string project=Directory.GetParent(Application.dataPath).FullName;
        File.WriteAllText(Path.Combine(project,"text-overlap.json"),JsonUtility.ToJson(report,true));
    }
}
#endif
