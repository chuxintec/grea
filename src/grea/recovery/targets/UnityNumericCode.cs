// Editor-only binding of compiler-generated numeric Label subsets; no original code is executed.
using System;
using System.Linq;
using System.Reflection;
using System.Globalization;
using UnityEngine;
using UnityEditor;
using TMPro;
public static class MonkeyNumericCode {
    [Serializable] public class Result { public string sourceId,sourceScriptIdentity,scriptGuid,componentFileId,labelFileId,fileIdOwner; public bool bound,uninitialized,numberBoundaries,instancesIndependent,textUnchanged; }
    static Type TypeFor(MonkeyImporter.ComponentSpec spec) {
        if(!System.Text.RegularExpressions.Regex.IsMatch(spec.codeClassName??"","^[A-Za-z_][A-Za-z0-9_]*$"))throw new Exception("Invalid generated class name");
        var space=string.IsNullOrEmpty(spec.codeNamespace)?"Monkey.Recovered":spec.codeNamespace;
        if(!System.Text.RegularExpressions.Regex.IsMatch(space,"^[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)*$"))throw new Exception("Invalid generated namespace");
        var matches=AppDomain.CurrentDomain.GetAssemblies().Select(assembly=>assembly.GetType(space+"."+spec.codeClassName,false)).Where(type=>type!=null).ToArray();
        if(matches.Length!=1||!typeof(MonoBehaviour).IsAssignableFrom(matches[0]))throw new Exception("Generated numeric class not registered");return matches[0];
    }
    static MethodInfo[] Methods(Type type,MonkeyImporter.ComponentSpec spec) {
        if(spec.numericMethods==null)throw new Exception("Numeric method contract missing");
        var setter=type.GetMethod(spec.numericMethods.setter,BindingFlags.Instance|BindingFlags.Public|BindingFlags.DeclaredOnly);var getter=type.GetMethod(spec.numericMethods.getter,BindingFlags.Instance|BindingFlags.Public|BindingFlags.DeclaredOnly);
        if(setter==null||setter.ReturnType!=typeof(void)||setter.GetParameters().Length!=1||setter.GetParameters()[0].ParameterType!=typeof(double)||getter==null||getter.ReturnType!=typeof(double?)||getter.GetParameters().Length!=0)throw new Exception("Generated numeric method signature differs");return new[]{setter,getter};
    }
    static string ScriptGuid(MonoBehaviour component) { var script=MonoScript.FromMonoBehaviour(component);if(script==null)throw new Exception("Generated MonoScript unavailable");return AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(script)); }
    static string FileId(UnityEngine.Object value,out string owner) {
        var original=value;var corresponding=PrefabUtility.GetCorrespondingObjectFromSource(value);if(corresponding!=null)value=corresponding;
        string guid;long id;if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value,out guid,out id))throw new Exception("Saved numeric binding identity unavailable");owner=corresponding!=null?"saved-prefab-source":"persistent-asset";return id.ToString(CultureInfo.InvariantCulture);
    }
    public static void Bind(MonkeyImporter.ComponentSpec spec,TMP_Text label) {
        var type=TypeFor(spec);Methods(type,spec);if(label.GetComponents(type).Length!=0)throw new Exception("Generated numeric component already exists");
        var component=(MonoBehaviour)label.gameObject.AddComponent(type);
        if(string.IsNullOrEmpty(spec.codeScriptGuid)||ScriptGuid(component)!=spec.codeScriptGuid)throw new Exception("Generated script GUID differs from code contract");
        var serialized=new SerializedObject(component);var target=serialized.FindProperty("targetLabel");if(target==null||target.propertyType!=SerializedPropertyType.ObjectReference)throw new Exception("Generated TMP reference field missing");target.objectReferenceValue=label;serialized.ApplyModifiedPropertiesWithoutUndo();
    }
    public static Result[] Exercise(MonkeyImporter.ComponentSpec[] specs,System.Collections.Generic.Dictionary<string,GameObject> nodes) {
        var selected=specs.Where(c=>c.convertible&&!string.IsNullOrEmpty(c.codeClassName)).ToArray();var components=selected.Select(c=>(MonoBehaviour)nodes[c.node].GetComponent(TypeFor(c))).ToArray();var methods=selected.Select((c,i)=>Methods(components[i].GetType(),c)).ToArray();
        if(components.Select((component,i)=>methods[i][1].Invoke(component,null)).Any(value=>value!=null))throw new Exception("Generated uninitialized numeric state changed");
        var result=new Result[selected.Length];
        for(int i=0;i<selected.Length;i++) {
            var label=components[i].GetComponent<TMP_Text>();var text=label.text;var font=label.font;
            foreach(var value in new[]{0d,BitConverter.Int64BitsToDouble(long.MinValue),1d,double.MaxValue,double.NaN,double.PositiveInfinity,double.NegativeInfinity}) {
                methods[i][0].Invoke(components[i],new object[]{value});var actual=(double)methods[i][1].Invoke(components[i],null);
                if(BitConverter.DoubleToInt64Bits(value)!=BitConverter.DoubleToInt64Bits(actual)&&!(double.IsNaN(value)&&double.IsNaN(actual)))throw new Exception("Numeric value differs");
                if(Enumerable.Range(i+1,selected.Length-i-1).Any(j=>methods[j][1].Invoke(components[j],null)!=null))throw new Exception("Generated instances share state");
                if(label.text!=text||label.font!=font)throw new Exception("Generated setter changed presentation");
            }
            result[i]=new Result{sourceId=selected[i].sourceId,sourceScriptIdentity=selected[i].sourceScriptIdentity,scriptGuid=ScriptGuid(components[i]),bound=true,numberBoundaries=true,instancesIndependent=true,textUnchanged=true};
        }
        return result;
    }
    public static Result Read(MonkeyImporter.ComponentSpec spec,GameObject node) {
        var type=TypeFor(spec);var components=node.GetComponents(type);if(components.Length!=1)throw new Exception("Saved numeric component count differs");var component=(MonoBehaviour)components[0];var label=node.GetComponent<TMP_Text>();var serialized=new SerializedObject(component);
        if(label==null||serialized.FindProperty("targetLabel").objectReferenceValue!=label||ScriptGuid(component)!=spec.codeScriptGuid||Methods(type,spec)[1].Invoke(component,null)!=null)throw new Exception("Saved numeric binding/state differs");
        string owner,unused;return new Result{sourceId=spec.sourceId,sourceScriptIdentity=spec.sourceScriptIdentity,scriptGuid=spec.codeScriptGuid,componentFileId=FileId(component,out owner),labelFileId=FileId(label,out unused),fileIdOwner=owner,bound=true,uninitialized=true};
    }
}
