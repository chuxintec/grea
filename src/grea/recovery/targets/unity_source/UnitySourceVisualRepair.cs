#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

// Applies a source-identity plan to an independent export. Verify is intended
// for a separate Editor process so its reads cannot use transient objects.
public static class UnitySourceVisualRepair
{
    [Serializable] private class Binding
    {
        public string root, path, node, component, field, kind, asset, token, sourceName;
        public int index;
    }
    [Serializable] private class Plan { public Binding[] edits, slots; public string[] roots; public string outlineFallback; public Layout[] layouts; public State[] states; }
    [Serializable] private class State
    {
        public string root, path, node, reason;
        public bool active;
    }
    [Serializable] private class Layout { public string root, path, node, mode, reason; }
    private static bool LayoutChange(GameObject root,Layout op,bool verify)
    {
        if (string.IsNullOrEmpty(op.reason)) throw new InvalidDataException("Missing layout rationale");
        GameObject node=Child(root,op.path,op.node).gameObject;
        if (op.mode=="includeInLayout")
        {
            var element=node.GetComponent<UnityEngine.UI.LayoutElement>();
            if (!element || !node.transform.parent.GetComponent<UnityEngine.UI.LayoutGroup>())
                throw new InvalidDataException("Expected an excluded layout child: "+op.path);
            if (!element.ignoreLayout) return false;
            if (verify) throw new InvalidDataException("Layout child excluded: "+op.path);
            element.ignoreLayout=false;
        }
        else if (op.mode=="fitPreferredHeight")
        {
            if (!node.GetComponent<UnityEngine.UI.LayoutGroup>()) throw new InvalidDataException("Missing layout group: "+op.path);
            var fitter=node.GetComponent<UnityEngine.UI.ContentSizeFitter>();
            if (fitter && fitter.verticalFit==UnityEngine.UI.ContentSizeFitter.FitMode.PreferredSize) return false;
            if (verify) throw new InvalidDataException("Missing preferred height: "+op.path);
            if (!fitter) fitter=node.AddComponent<UnityEngine.UI.ContentSizeFitter>();
            fitter.verticalFit=UnityEngine.UI.ContentSizeFitter.FitMode.PreferredSize;
        }
        else throw new InvalidDataException("Unknown layout repair: "+op.mode);
        return true;
    }
    [Serializable] private class States { public State[] states; }
    private static readonly string Project = Directory.GetParent(Application.dataPath).FullName;
    private static Object Resolve(Binding b)
    {
        Object target;
        switch (b.kind)
        {
            case "builtinFont": target = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); break;
            case "builtinSprite": target = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/Knob.psd"); break;
            case "mesh":
                target=AssetDatabase.LoadAssetAtPath<Mesh>(b.asset);
                if (target && target.name!=b.token) throw new InvalidDataException("Mesh identity mismatch: "+b.asset);
                break;
            case "texture": target = AssetDatabase.LoadAssetAtPath<Texture2D>(b.asset); break;
            case "sprite": target = AssetDatabase.LoadAssetAtPath<Sprite>(b.asset); break;
            default: throw new InvalidDataException(b.kind);
        }
        if (!target) throw new InvalidDataException("Missing source image: "+b.asset);
        if (b.kind=="texture" && target.name!=b.sourceName) throw new InvalidDataException("Atlas texture name mismatch: "+b.asset);
        if (b.kind.StartsWith("builtin",StringComparison.Ordinal))
        {
            AssetDatabase.TryGetGUIDAndLocalFileIdentifier(target,out string guid,out long id);
            string expected = b.kind=="builtinFont"?"0000000000000000e000000000000000":"0000000000000000f000000000000000";
            if (guid!=expected || id.ToString()!=b.token) throw new InvalidDataException("Builtin mismatch: "+b.token);
        }
        return target;
    }
    private static Transform Child(GameObject root,string path,string name)
    {
        var indexes = path.Split('/');
        if (indexes[0]!="0") throw new InvalidDataException(path);
        Transform node=root.transform;
        foreach (string index in indexes.Skip(1)) node=node.GetChild(int.Parse(index));
        if (node.name!=name) throw new InvalidDataException("Hierarchy mismatch: "+path+" "+node.name+" / "+name);
        return node;
    }
    private static bool Bind(SerializedObject owner, SerializedProperty property, Binding b,bool verify)
    {
        if (property==null || property.propertyType!=SerializedPropertyType.ObjectReference)
            throw new InvalidDataException(b.root+" "+b.path+" "+b.field);
        Object expected=Resolve(b);
        if (property.objectReferenceValue==expected) return false;
        if (verify) throw new InvalidDataException("Reference readback failed: "+b.root+" "+b.field);
        property.objectReferenceValue=expected;
        owner.ApplyModifiedPropertiesWithoutUndo();
        return true;
    }
    public static void Apply() { Run(false); }
    public static void Verify() { Run(true); }
    private static void Run(bool verify)
    {
        Plan plan=JsonUtility.FromJson<Plan>(File.ReadAllText(Path.Combine(Project,"visual-repair.json")));
        string stateFile=Path.Combine(Project,"visual-states.json");
        State[] states=plan.states ?? (File.Exists(stateFile)?JsonUtility.FromJson<States>(File.ReadAllText(stateFile)).states:Array.Empty<State>());
        var edits=plan.edits.ToLookup(x=>x.root);
        var visibility=states.ToLookup(x=>x.root);
        var layouts=(plan.layouts??Array.Empty<Layout>()).ToLookup(x=>x.root);
        int checkedCount=0, changed=0;
        Material fallback=null;
        if (!string.IsNullOrEmpty(plan.outlineFallback))
        {
            fallback=AssetDatabase.LoadAssetAtPath<Material>(plan.outlineFallback);
            if (!fallback || !fallback.shader || fallback.shader.name!="Monkey/UnitySource/TextOutline")
                throw new InvalidDataException("Incompatible static outline fallback: "+plan.outlineFallback);
        }
        var paths=edits.Select(g=>g.Key).Union(visibility.Select(g=>g.Key)).Union(layouts.Select(g=>g.Key));
        if (fallback) paths=paths.Union(plan.roots);
        int outlineCount=0, outlineChanges=0;
        foreach (string path in paths)
        {
            GameObject root=PrefabUtility.LoadPrefabContents(path);
            try
            {
                bool dirty=false;
                foreach (Binding b in edits[path])
                {
                    var component=Child(root,b.path,b.node).GetComponents<Component>()[b.index];
                    if (!component || component.GetType().Name!=b.component) throw new InvalidDataException("Component mismatch: "+path+" "+b.path);
                    var owner=new SerializedObject(component);
                    if (Bind(owner,owner.FindProperty(b.field),b,verify)) {dirty=true; changed++;}
                    checkedCount++;
                }
                foreach (State state in visibility[path])
                {
                    var obj=Child(root,state.path,state.node).gameObject;
                    if (string.IsNullOrEmpty(state.reason)) throw new InvalidDataException("Missing state rationale");
                    if (obj.activeSelf!=state.active)
                    {
                        if (verify) throw new InvalidDataException("State readback failed: "+path+" "+state.node);
                        obj.SetActive(state.active); dirty=true; changed++;
                    }
                    checkedCount++;
                }
                foreach (var op in layouts[path])
                {
                    if (LayoutChange(root,op,verify)) {dirty=true;changed++;}
                    checkedCount++;
                }
                if (fallback)
                {
                    foreach (var effect in root.GetComponentsInChildren<UnityEngine.UI.BaseMeshEffect>(true))
                    {
                        if (!effect || !effect.enabled || effect.GetType().FullName!="DodGame.DodTextOutline") continue;
                        var width=new SerializedObject(effect).FindProperty("m_OutlineWidth");
                        var text=effect.GetComponent<UnityEngine.UI.Text>();
                        if (width==null || width.floatValue<=0 || !text) continue;
                        var owner=new SerializedObject(text);
                        var prop=owner.FindProperty("m_Material");
                        if (prop.objectReferenceValue!=null && prop.objectReferenceValue!=fallback) continue;
                        outlineCount++;
                        if (prop.objectReferenceValue==fallback) continue;
                        if (verify) throw new InvalidDataException("Missing outline material: "+path);
                        prop.objectReferenceValue=fallback;
                        owner.ApplyModifiedPropertiesWithoutUndo();
                        dirty=true; changed++; outlineChanges++;
                    }
                }
                if (dirty)
                {
                    PrefabUtility.SaveAsPrefabAsset(root,path,out bool saved);
                    if (!saved) throw new IOException(path);
                }
            }
            finally {PrefabUtility.UnloadPrefabContents(root);}
        }
        foreach (var group in plan.slots.GroupBy(b=>b.root))
        {
            var material=AssetDatabase.LoadAssetAtPath<Material>(group.Key);
            if (!material) throw new InvalidDataException(group.Key);
            var owner=new SerializedObject(material);
            var env=owner.FindProperty("m_SavedProperties.m_TexEnvs");
            foreach (var b in group)
            {
                SerializedProperty slot=null;
                for (int i=0;i<env.arraySize;i++)
                {
                    var pair=env.GetArrayElementAtIndex(i);
                    if (pair.FindPropertyRelative("first").stringValue==b.field)
                    {
                        if (slot!=null) throw new InvalidDataException("Duplicate material slot: "+group.Key+" "+b.field);
                        slot=pair.FindPropertyRelative("second.m_Texture");
                    }
                }
                if (Bind(owner,slot,b,verify)) changed++;
                checkedCount++;
            }
        }
        if (!verify) AssetDatabase.SaveAssets();
        File.WriteAllText(Path.Combine(Project,verify?"outlines-cold.txt":"outlines-applied.txt"),outlineCount+"\t"+outlineChanges);
        File.WriteAllText(Path.Combine(Project,verify?"visual-cold.txt":"visual-applied.txt"),checkedCount+"\t"+changed);
    }
}
#endif
