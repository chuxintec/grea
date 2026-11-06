using System;
using System.Linq;
using UnityEditor;
using UnityEngine;

// Editor-only construction of explicitly generated, source-bound native scripts.
public static class MonkeyBehaviorBindings
{
    [Serializable] public sealed class Field {
        public string name, type;
        public float numberValue;
        public bool boolValue;
    }
    [Serializable] public sealed class Spec {
        public string typeName, scriptGuid;
        public Field[] fields;
        public bool runtimeComplete;
    }
    [Serializable] public sealed class Result {
        public string sourceId, typeName, assetGuid, scriptGuid;
        public long localFileId;
        public bool fieldsVerified, enabled;
        public Field[] fields;
        public string runtime = "not_run";
    }
    static Type Resolve(Spec spec) {
        var path = AssetDatabase.GUIDToAssetPath(spec.scriptGuid);
        if (string.IsNullOrEmpty(path) || !path.StartsWith("Assets/Game/Scripts/Presentation/Recovered/", StringComparison.Ordinal))
            throw new InvalidOperationException("BEHAVIOR_SCRIPT_IDENTITY: " + spec.typeName);
        var script = AssetDatabase.LoadAssetAtPath<MonoScript>(path);
        var type = script == null ? null : script.GetClass();
        if (type == null || type.FullName != spec.typeName || !typeof(MonoBehaviour).IsAssignableFrom(type))
            throw new InvalidOperationException("BEHAVIOR_SCRIPT_TYPE: " + spec.typeName);
        return type;
    }
    public static void Bind(Spec spec, GameObject node, bool enabled) {
        var type = Resolve(spec);
        if (node.GetComponents(type).Length != 0) throw new InvalidOperationException("BEHAVIOR_DUPLICATE_COMPONENT");
        var component = (MonoBehaviour)node.AddComponent(type);
        component.enabled = false;
        var serialized = new SerializedObject(component);
        foreach (var field in spec.fields ?? Array.Empty<Field>()) {
            var property = serialized.FindProperty(field.name);
            if (property == null) throw new InvalidOperationException("BEHAVIOR_FIELD_MISSING: " + field.name);
            if (field.type == "float" && property.propertyType == SerializedPropertyType.Float) property.floatValue = field.numberValue;
            else if (field.type == "bool" && property.propertyType == SerializedPropertyType.Boolean) property.boolValue = field.boolValue;
            else throw new InvalidOperationException("BEHAVIOR_FIELD_TYPE: " + field.name);
        }
        serialized.ApplyModifiedPropertiesWithoutUndo();
        component.enabled = enabled;
    }
    public static bool Read(Spec spec, GameObject node, bool enabled) {
        var components = node.GetComponents(Resolve(spec));
        if (components.Length != 1 || ((MonoBehaviour)components[0]).enabled != enabled) return false;
        var serialized = new SerializedObject(components[0]);
        foreach (var field in spec.fields ?? Array.Empty<Field>()) {
            var property = serialized.FindProperty(field.name);
            if (property == null) return false;
            if (field.type == "float") { if (property.propertyType != SerializedPropertyType.Float || property.floatValue != field.numberValue) return false; }
            else if (field.type == "bool") { if (property.propertyType != SerializedPropertyType.Boolean || property.boolValue != field.boolValue) return false; }
            else return false;
        }
        return true;
    }
    public static Result ReadPersistent(Spec spec, GameObject node, string sourceId, bool enabled) {
        if(!Read(spec,node,enabled))throw new InvalidOperationException("BEHAVIOR_NATIVE_FIELD_MISMATCH: "+sourceId);
        var component=(MonoBehaviour)node.GetComponent(Resolve(spec));
        if(!EditorUtility.IsPersistent(component)||!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(component,out string guid,out long id)||id==0)
            throw new InvalidOperationException("BEHAVIOR_PERSISTENT_ID_MISSING: "+sourceId);
        var script=MonoScript.FromMonoBehaviour(component);
        string actualScript=AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(script));
        if(actualScript!=spec.scriptGuid)throw new InvalidOperationException("BEHAVIOR_NATIVE_SCRIPT_MISMATCH: "+sourceId);
        return new Result {sourceId=sourceId,typeName=spec.typeName,assetGuid=guid,localFileId=id,
            scriptGuid=actualScript,fieldsVerified=true,enabled=component.enabled,fields=spec.fields};
    }
}
