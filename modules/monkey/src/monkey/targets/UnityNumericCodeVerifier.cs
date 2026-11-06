// Editor-only verification of newly generated numeric methods and exact TMP bindings.
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Reflection;
using System.Globalization;
using UnityEngine;
using UnityEditor;
using TMPro;
namespace Monkey.CodeRecovery {
public static class NumericCodeVerifier {
    [Serializable] public class Presentation { public string fontPath; public string text; public float fontSize; public float lineHeight; public float spacing; public int horizontalAlign; public int verticalAlign; public int sourceOverflow; public bool bold; public bool wrap; public bool enabled; public int[] color; }
    [Serializable] public class Binding { public string sourceNode; public string sourceComponent; public int[] childIndices; public Presentation presentation; }
    [Serializable] public class Spec { public string prefabPath; public string className; public string scriptGuid; public string setter; public string getter; public string deadlineUtc; public int budgetSeconds; public Binding[] bindings; }
    [Serializable] public class Row { public string sourceNode; public string sourceComponent; public string nodeName; public string componentFileId; public string labelFileId; public string scriptGuid; public string text; public bool bound; public bool uninitialized; }
    [Serializable] public class Result { public string status="failed"; public string unityVersion; public string prefabGuid; public int nodeCount; public int missingScripts; public bool numberBoundaries; public bool instancesIndependent; public bool geometryPreserved; public bool saved; public bool reopened; public Row[] bindings; public string phase; public string error; }
    static string Identity(UnityEngine.Object asset) { string guid;long id;if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(asset,out guid,out id))throw new Exception("Missing native identity");return guid+"/"+id.ToString(CultureInfo.InvariantCulture); }
    static Transform Node(Transform root,int[] indices) { var node=root;foreach(int index in indices){if(index<0||index>=node.childCount)throw new Exception("Binding hierarchy differs");node=node.GetChild(index);}return node; }
    static string Geometry(GameObject root) {
        return string.Join("|",root.GetComponentsInChildren<Transform>(true).Select(t=>{
            var rect=t as RectTransform;
            var floats=new List<float>{t.localPosition.x,t.localPosition.y,t.localPosition.z,t.localScale.x,t.localScale.y,t.localScale.z,t.localRotation.x,t.localRotation.y,t.localRotation.z,t.localRotation.w};
            if(rect!=null)floats.AddRange(new[]{rect.sizeDelta.x,rect.sizeDelta.y,rect.pivot.x,rect.pivot.y,rect.anchorMin.x,rect.anchorMin.y,rect.anchorMax.x,rect.anchorMax.y,rect.anchoredPosition.x,rect.anchoredPosition.y});
            return t.name+":"+t.gameObject.activeSelf+":"+string.Join(",",floats.Select(v=>v.ToString("R",CultureInfo.InvariantCulture)));
        }));
    }
    static void VerifyGlyphs(TMP_Text original,string text) {
        var canvas=new GameObject("MonkeyNumericGlyphProbe",typeof(RectTransform),typeof(Canvas));
        UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(canvas,original.gameObject.scene);
        try {
            canvas.GetComponent<Canvas>().renderMode=RenderMode.WorldSpace;
            var clone=UnityEngine.Object.Instantiate(original.gameObject,canvas.transform,false);var measured=clone.GetComponent<TMP_Text>();
            foreach(var behaviour in clone.GetComponentsInChildren<Behaviour>(true))if(behaviour!=measured)behaviour.enabled=false;
            var rect=(RectTransform)clone.transform;var saved=(RectTransform)original.transform;rect.anchorMin=rect.anchorMax=new Vector2(.5f,.5f);rect.pivot=saved.pivot;rect.sizeDelta=saved.rect.size;rect.anchoredPosition3D=Vector3.zero;
            clone.SetActive(true);measured.enabled=true;measured.ForceMeshUpdate(true,true);
            if(measured.textInfo.characterCount!=text.Length||text.Any(ch=>!char.IsWhiteSpace(ch)&&!measured.font.HasCharacter(ch)))throw new Exception("Projected Label glyph missing");
        } finally {UnityEngine.Object.DestroyImmediate(canvas);}
    }
    public static void Run() {
        var result=new Result{unityVersion=Application.unityVersion};int exit=1;GameObject contents=null;
        try {
            var spec=JsonUtility.FromJson<Spec>(File.ReadAllText(File.Exists("Analysis/Plans/numeric-code-spec.json")||!File.Exists("Analysis/numeric-code-spec.json")?"Analysis/Plans/numeric-code-spec.json":"Analysis/numeric-code-spec.json"));
            var start=DateTime.UtcNow;var deadline=DateTime.Parse(spec.deadlineUtc,null,DateTimeStyles.AdjustToUniversal);
            Action checkpoint=()=>{if(spec.budgetSeconds<1||spec.budgetSeconds>1200||DateTime.UtcNow>=deadline||(DateTime.UtcNow-start).TotalSeconds>spec.budgetSeconds)throw new TimeoutException("Numeric code deadline");};checkpoint();
            if(!spec.prefabPath.StartsWith("Assets/",StringComparison.Ordinal)||spec.prefabPath.Contains("..")||!spec.prefabPath.EndsWith(".prefab",StringComparison.Ordinal)||spec.bindings.Length==0)throw new Exception("Unsafe binding spec");
            result.phase="component-class";
            var script=AssetDatabase.LoadAssetAtPath<MonoScript>(AssetDatabase.GUIDToAssetPath(spec.scriptGuid));var type=script==null?null:script.GetClass();
            if(type==null||type.FullName!=spec.className||!typeof(MonoBehaviour).IsAssignableFrom(type))throw new Exception("Generated component not registered");
            var setter=type.GetMethod(spec.setter,BindingFlags.Instance|BindingFlags.Public|BindingFlags.DeclaredOnly);var getter=type.GetMethod(spec.getter,BindingFlags.Instance|BindingFlags.Public|BindingFlags.DeclaredOnly);
            if(setter==null||setter.ReturnType!=typeof(void)||setter.GetParameters().Length!=1||setter.GetParameters()[0].ParameterType!=typeof(double)||getter==null||getter.ReturnType!=typeof(double?)||getter.GetParameters().Length!=0)throw new Exception("Generated numeric method signature differs");
            result.phase="load-prefab";contents=PrefabUtility.LoadPrefabContents(spec.prefabPath);var before=Geometry(contents);result.prefabGuid=AssetDatabase.AssetPathToGUID(spec.prefabPath);result.nodeCount=contents.GetComponentsInChildren<Transform>(true).Length;
            var components=new List<Component>();var labels=new List<TMP_Text>();var text=new List<string>();var fonts=new List<string>();var paths=new HashSet<string>();
            foreach(var binding in spec.bindings) {
                checkpoint();if(!paths.Add(string.Join("/",binding.childIndices)))throw new Exception("Repeated node binding");
                result.phase="binding/"+binding.sourceComponent;var node=Node(contents.transform,binding.childIndices);var label=node.GetComponent<TMP_Text>();
                if(node.GetComponents(type).Length!=0)throw new Exception("Generated component already exists");
                if(label==null) {
                    var data=binding.presentation;
                    if(data==null||data.sourceOverflow!=2||data.wrap||!data.fontPath.StartsWith("Assets/",StringComparison.Ordinal)||data.fontPath.Contains(".."))throw new Exception("Missing supported source Label projection");
                    if(node.GetComponent<UnityEngine.UI.Graphic>()!=null)throw new Exception("Conflicting graphic");
                    var font=AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(data.fontPath);if(font==null)throw new Exception("Original font asset unavailable");
                    if(TMP_Settings.instance==null)throw new Exception("Required original TMP Settings resource missing");
                    label=node.gameObject.AddComponent<TextMeshProUGUI>();label.font=font;label.text=data.text;label.fontSize=data.fontSize;
                    label.fontStyle=data.bold?FontStyles.Bold:FontStyles.Normal;
                    label.characterSpacing=data.fontSize>0?data.spacing*100f/data.fontSize:0;
                    label.lineSpacing=data.fontSize>0?(data.lineHeight-font.faceInfo.lineHeight*data.fontSize/font.faceInfo.pointSize)*100f/data.fontSize:0;
                    label.enableAutoSizing=false;label.richText=false;label.raycastTarget=false;label.enabled=data.enabled;label.textWrappingMode=TextWrappingModes.NoWrap;
                    if(data.color==null||data.color.Length!=4)throw new Exception("Source color missing");label.color=new Color32((byte)data.color[0],(byte)data.color[1],(byte)data.color[2],(byte)data.color[3]);
                    label.horizontalAlignment=new[]{HorizontalAlignmentOptions.Left,HorizontalAlignmentOptions.Center,HorizontalAlignmentOptions.Right}[data.horizontalAlign];
                    label.verticalAlignment=new[]{VerticalAlignmentOptions.Top,VerticalAlignmentOptions.Middle,VerticalAlignmentOptions.Bottom}[data.verticalAlign];
                    result.phase="glyphs/"+binding.sourceComponent;VerifyGlyphs(label,data.text);
                }
                result.phase="numeric-component/"+binding.sourceComponent;var component=node.gameObject.AddComponent(type);var serialized=new SerializedObject(component);var property=serialized.FindProperty("targetLabel");
                if(property==null||property.propertyType!=SerializedPropertyType.ObjectReference)throw new Exception("TMP binding field missing");property.objectReferenceValue=label;serialized.ApplyModifiedPropertiesWithoutUndo();
                if(getter.Invoke(component,null)!=null)throw new Exception("Uninitialized state became zero");
                components.Add(component);labels.Add(label);text.Add(label.text);fonts.Add(Identity(label.font));
            }
            var values=new[]{0d,BitConverter.Int64BitsToDouble(long.MinValue),1d,double.MaxValue,double.NaN,double.PositiveInfinity,double.NegativeInfinity};
            for(int i=0;i<components.Count;i++) {
                foreach(var value in values) {
                    checkpoint();setter.Invoke(components[i],new object[]{value});var actual=(double)getter.Invoke(components[i],null);
                    if(BitConverter.DoubleToInt64Bits(actual)!=BitConverter.DoubleToInt64Bits(value)&&!(double.IsNaN(actual)&&double.IsNaN(value)))throw new Exception("Numeric state differs");
                    if(Enumerable.Range(i+1,components.Count-i-1).Any(j=>getter.Invoke(components[j],null)!=null))throw new Exception("Instances share state");
                }
                if(labels[i].text!=text[i]||Identity(labels[i].font)!=fonts[i])throw new Exception("State setter changed presentation");
            }
            result.numberBoundaries=true;result.instancesIndependent=true;
            checkpoint();bool saved;var asset=PrefabUtility.SaveAsPrefabAsset(contents,spec.prefabPath,out saved);if(!saved||asset==null)throw new Exception("Save failed");result.saved=true;
            PrefabUtility.UnloadPrefabContents(contents);contents=null;AssetDatabase.ImportAsset(spec.prefabPath,ImportAssetOptions.ForceSynchronousImport|ImportAssetOptions.ForceUpdate);contents=PrefabUtility.LoadPrefabContents(spec.prefabPath);checkpoint();
            if(AssetDatabase.AssetPathToGUID(spec.prefabPath)!=result.prefabGuid)throw new Exception("Prefab GUID changed");
            var persisted=AssetDatabase.LoadAssetAtPath<GameObject>(spec.prefabPath);var rows=new List<Row>();
            for(int i=0;i<spec.bindings.Length;i++) {
                var binding=spec.bindings[i];var node=Node(contents.transform,binding.childIndices);var all=node.GetComponents(type);if(all.Length!=1)throw new Exception("Reopened component differs");
                var serialized=new SerializedObject(all[0]);var label=node.GetComponent<TMP_Text>();bool bound=serialized.FindProperty("targetLabel").objectReferenceValue==label;
                if(!bound||label.text!=text[i]||Identity(label.font)!=fonts[i]||getter.Invoke(all[0],null)!=null)throw new Exception("Reopened binding/state differs");
                var native=Node(persisted.transform,binding.childIndices);var nativeComponent=native.GetComponent(type);var nativeLabel=native.GetComponent<TMP_Text>();
                rows.Add(new Row{sourceNode=binding.sourceNode,sourceComponent=binding.sourceComponent,nodeName=node.name,componentFileId=Identity(nativeComponent).Split('/')[1],labelFileId=Identity(nativeLabel).Split('/')[1],scriptGuid=spec.scriptGuid,text=label.text,bound=bound,uninitialized=true});
            }
            result.bindings=rows.ToArray();result.geometryPreserved=before==Geometry(contents);if(!result.geometryPreserved)throw new Exception("Original hierarchy or geometry changed");
            result.missingScripts=contents.GetComponentsInChildren<Transform>(true).Sum(t=>GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject));if(result.missingScripts!=0)throw new Exception("Missing scripts");
            result.reopened=true;result.status="numeric_subset_binding_verified";exit=0;
        } catch(Exception error) {result.error=error.ToString();}
        finally {if(contents!=null)PrefabUtility.UnloadPrefabContents(contents);Directory.CreateDirectory("Analysis/Readback");File.WriteAllText("Analysis/Readback/numeric-code-readback.json",JsonUtility.ToJson(result,true));}
        EditorApplication.Exit(exit);
    }
}
}
