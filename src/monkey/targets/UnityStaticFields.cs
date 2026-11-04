// Editor-side binder for generated disabled static-field carriers.
// NativeCreate uses no callbacks; all carrier components remain disabled.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using UnityEngine;

public static class UnityStaticFields
{
    [Serializable] public sealed class FieldSpec
    {
        public string name, sourceFieldName, fieldName, kind, storageType, elementKind, mode;
        public string sourceDeclaredType, referenceKind, dynamicType;
        public string sourceConstant, accessorBackingJson;
        public string sourceValueEncoding, sourceValueEncodingJson;
        public string recordTypeName, recordName;
        public double numberValue;
        public string stringValue, refValue, snapshotJson;
        public bool boolValue, nullExpected, referenceVerified, referencesVerified;
        public double[] numberValues;
        public string[] stringValues, refValues;
        public bool[] boolValues;
        public int colorR, colorG, colorB, colorA;
        public RecordValueSpec[] recordValues;
    }
    // Flat leaf spec: never points back to FieldSpec, RecordValueSpec or a
    // schema array. JsonUtility otherwise recursively walks FieldSpec -> rows
    // -> FieldSpec and exceeds its serialization depth limit.
    [Serializable] public sealed class RecordFieldValueSpec
    {
        public string name, sourceFieldName, fieldName, kind, storageType, referenceKind;
        public string sourceDeclaredType, dynamicType;
        public string sourceConstant;
        public string sourceValueEncoding, sourceValueEncodingJson;
        public double numberValue;
        public string stringValue, refValue;
        public bool boolValue, nullExpected, referenceVerified;
        public int colorR, colorG, colorB, colorA;
    }
    [Serializable] public sealed class RecordValueSpec { public int index; public RecordFieldValueSpec[] fields; }
    [Serializable] public sealed class Spec
    {
        public string sourceId, sourceTemplateId, node, sourceType, typeName, scriptGuid, behavior, nativeCreate;
        public bool enabled, declarationDefaultsVerified;
        public FieldSpec[] fields;
        public string[] gaps;
    }
    [Serializable] public sealed class Readback
    {
        public string sourceId, nativeSourceId, typeName, scriptGuid, nativeScriptGuid;
        public bool fieldsVerified, fieldsAssigned, nativeIdentityVerified, enabled, nativeComplete, dynamicBehaviorComplete;
        public bool recordSpecStructureVerified;
        public FieldSpec[] fields;
        public string[] gaps;
    }

    static void Gap(List<string> gaps, string text) { if (!gaps.Contains(text)) gaps.Add(text); }
    static string[] MergeGaps(Spec spec, List<string> operational)
    {
        var all = new List<string>();
        if (spec != null && spec.gaps != null) foreach (var gap in spec.gaps) Gap(all, gap);
        foreach (var gap in operational) Gap(all, gap);
        return all.ToArray();
    }
    static Type Resolve(Spec spec)
    {
        if (spec == null || String.IsNullOrEmpty(spec.typeName) || String.IsNullOrEmpty(spec.scriptGuid))
            throw new InvalidOperationException("STATIC_CARRIER_SPEC_INVALID");
        var path = UnityEditor.AssetDatabase.GUIDToAssetPath(spec.scriptGuid);
        if (String.IsNullOrEmpty(path) || !path.StartsWith("Assets/Game/Scripts/Presentation/Recovered/StaticFields/", StringComparison.Ordinal))
            throw new InvalidOperationException("STATIC_CARRIER_SCRIPT_IDENTITY: " + spec.typeName);
        var script = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEditor.MonoScript>(path);
        var type = script == null ? null : script.GetClass();
        if (type == null || type.FullName != spec.typeName || !typeof(MonoBehaviour).IsAssignableFrom(type))
            throw new InvalidOperationException("STATIC_CARRIER_SCRIPT_TYPE: " + spec.typeName);
        return type;
    }

    public static MonoBehaviour Create(Spec spec, GameObject node)
    {
        var type = Resolve(spec);
        if (node == null) throw new InvalidOperationException("STATIC_CARRIER_NODE_MISSING: " + spec.sourceId);
        var component = (MonoBehaviour)node.AddComponent(type);
        var identity = type.GetField("__monkeySourceId", BindingFlags.Instance | BindingFlags.Public | BindingFlags.DeclaredOnly);
        if (identity == null || identity.FieldType != typeof(string)) throw new InvalidOperationException("STATIC_CARRIER_SOURCE_ID_FIELD_MISSING");
        identity.SetValue(component, spec.sourceId);
        component.enabled = false;
        return component;
    }

    public static Readback Assign(Spec spec, MonoBehaviour component, Func<string, UnityEngine.Object> resolveRef)
    {
        var gaps = new List<string>();
        bool recordSpecStructureVerified = true;
        if (spec == null || component == null) return Result(spec, component, false, gaps, Array.Empty<FieldSpec>());
        try
        {
            bool typeMatches = component.GetType() == Resolve(spec);
            if (!typeMatches) Gap(gaps, "carrier_type_mismatch");
            if (typeMatches)
            {
                var identity = component.GetType().GetField("__monkeySourceId", BindingFlags.Instance | BindingFlags.Public | BindingFlags.DeclaredOnly);
                if (identity == null || identity.FieldType != typeof(string)) Gap(gaps, "carrier_source_id_field_missing");
                else identity.SetValue(component, spec.sourceId);
            }
            foreach (var field in spec.fields ?? Array.Empty<FieldSpec>())
            {
                try
                {
                    if (field.elementKind == "record" && field.recordTypeName != null &&
                        !RecordRowsAreValid(field.recordValues))
                    { Gap(gaps, "record_array_spec_invalid:" + field.sourceFieldName); recordSpecStructureVerified = false; continue; }
                    var info = component.GetType().GetField(field.fieldName, BindingFlags.Instance | BindingFlags.Public | BindingFlags.DeclaredOnly);
                    if (info == null) { Gap(gaps, "carrier_field_missing:" + field.sourceFieldName); continue; }
                    object value = ScalarValue(field);
                    if (field.elementKind == "record" && field.recordTypeName != null)
                    {
                        value = AssignRecords(field, info.FieldType, resolveRef, gaps);
                        if (value == null) continue;
                    }
                    else if (field.storageType == "UnityEngine.Object")
                    {
                        if (field.nullExpected) value = null;
                        else
                        {
                            var resolved = ResolveOne(field.refValue, resolveRef, gaps, field.sourceFieldName);
                            if (resolved == null) continue;
                            value = resolved;
                        }
                    }
                    else if (field.storageType == "UnityEngine.Object[]")
                    {
                        var values = new UnityEngine.Object[(field.refValues ?? Array.Empty<string>()).Length];
                        bool valid = true;
                        for (int i = 0; i < values.Length; i++)
                        {
                            values[i] = ResolveOne(field.refValues[i], resolveRef, gaps, field.sourceFieldName + "[" + i + "]");
                            if (values[i] == null) valid = false;
                        }
                        if (!valid) continue;
                        value = values;
                    }
                    if ((value == null && !field.nullExpected) || (value != null && !info.FieldType.IsInstanceOfType(value)))
                    { Gap(gaps, "carrier_field_type_mismatch:" + field.sourceFieldName); continue; }
                    info.SetValue(component, value);
                }
                catch (Exception error) { Gap(gaps, "assign_failed:" + field.sourceFieldName + ":" + error.GetType().Name); }
            }
        }
        catch (Exception error) { Gap(gaps, "carrier_contract_failed:" + error.GetType().Name); }
        component.enabled = false;
        bool fieldsAssigned = gaps.Count == 0;
        var assignment = Result(spec, component, false, gaps, Clone(spec.fields));
        assignment.fieldsAssigned = fieldsAssigned;
        assignment.recordSpecStructureVerified = recordSpecStructureVerified;
        assignment.gaps = MergeGaps(spec, gaps);
        return assignment;
    }

    public static Readback Read(Spec spec, MonoBehaviour component, Func<string, UnityEngine.Object> resolveRef)
    {
        var gaps = new List<string>();
        var nativeGaps = new List<string>();
        var fields = new List<FieldSpec>();
        bool verified = spec != null && component != null;
        bool recordSpecStructureVerified = true;
        try
        {
            if (spec == null || component == null || component.GetType() != Resolve(spec))
            { Gap(gaps, "carrier_type_mismatch"); verified = false; }
            else
            {
                foreach (var expected in spec.fields ?? Array.Empty<FieldSpec>())
                {
                    if (expected.elementKind == "record" && expected.recordTypeName != null &&
                        !RecordRowsAreValid(expected.recordValues))
                    { Gap(gaps, "record_array_spec_invalid:" + expected.sourceFieldName); verified = false; recordSpecStructureVerified = false; }
                    var actual = Clone(expected);
                    var info = component.GetType().GetField(expected.fieldName, BindingFlags.Instance | BindingFlags.Public | BindingFlags.DeclaredOnly);
                    if (info == null) { Gap(gaps, "carrier_field_missing:" + expected.sourceFieldName); verified = false; fields.Add(actual); continue; }
                    var value = info.GetValue(component);
                    if (expected.elementKind == "record" && expected.recordTypeName != null)
                    {
                        actual.recordValues = ReadRecords(expected, value, resolveRef, gaps, ref verified);
                        if (actual.recordValues == null) { Gap(gaps, "record_array_readback_mismatch:" + expected.sourceFieldName); verified = false; }
                    }
                    else if (expected.storageType == "UnityEngine.Object")
                    {
                        if (expected.nullExpected)
                        {
                            actual.referenceVerified = (value as UnityEngine.Object) == null;
                        }
                        else
                        {
                            var resolved = ResolveOne(expected.refValue, resolveRef, gaps, expected.sourceFieldName);
                            actual.refValue = expected.refValue;
                            actual.referenceVerified = resolved != null && ReferenceEquals(value, resolved);
                        }
                        if (!actual.referenceVerified) { Gap(gaps, "reference_readback_mismatch:" + expected.sourceFieldName); verified = false; }
                    }
                    else if (expected.storageType == "UnityEngine.Object[]")
                    {
                        var values = value as UnityEngine.Object[];
                        actual.refValues = expected.refValues ?? Array.Empty<string>();
                        bool arrayVerified = values != null && values.Length == actual.refValues.Length;
                        if (!arrayVerified) { Gap(gaps, "reference_array_readback_mismatch:" + expected.sourceFieldName); verified = false; }
                        else for (int i = 0; i < values.Length; i++)
                        {
                            var resolved = ResolveOne(actual.refValues[i], resolveRef, gaps, expected.sourceFieldName + "[" + i + "]");
                            if (resolved == null || !ReferenceEquals(values[i], resolved)) { arrayVerified = false; Gap(gaps, "reference_array_readback_mismatch:" + expected.sourceFieldName); verified = false; }
                        }
                        actual.referencesVerified = arrayVerified;
                    }
                    else
                    {
                        CopyActual(actual, value);
                        if (!ValueEquals(expected, value))
                        { Gap(gaps, "field_readback_mismatch:" + expected.sourceFieldName); verified = false; }
                    }
                    fields.Add(actual);
                }
            }
        }
        catch (Exception error) { Gap(gaps, "read_failed:" + error.GetType().Name); verified = false; }
        string nativeSourceId = NativeSourceId(component), nativeScriptGuid = NativeScriptGuid(component);
        bool nativeIdentityVerified = spec != null && nativeSourceId == spec.sourceId && nativeScriptGuid == spec.scriptGuid;
        if (nativeSourceId != (spec == null ? null : spec.sourceId)) Gap(nativeGaps, "native_source_id_mismatch");
        if (nativeScriptGuid != (spec == null ? null : spec.scriptGuid)) Gap(nativeGaps, "native_script_guid_mismatch");
        bool enabled = component != null && component.enabled;
        if (enabled) { Gap(nativeGaps, "behavior_enabled"); component.enabled = false; }
        var allGaps = MergeGaps(spec, gaps.Concat(nativeGaps).ToList());
        bool fieldsVerified = verified && gaps.Count == 0;
        return new Readback { sourceId = spec == null ? null : spec.sourceId, typeName = spec == null ? null : spec.typeName,
            nativeSourceId = nativeSourceId, scriptGuid = spec == null ? null : spec.scriptGuid, nativeScriptGuid = nativeScriptGuid,
            nativeIdentityVerified = nativeIdentityVerified, fieldsVerified = fieldsVerified,
            enabled = false, fields = fields.ToArray(), gaps = allGaps,
            nativeComplete = fieldsVerified && nativeIdentityVerified && !enabled && recordSpecStructureVerified && spec != null && spec.declarationDefaultsVerified && (spec.gaps == null || spec.gaps.Length == 0),
            recordSpecStructureVerified = recordSpecStructureVerified,
            dynamicBehaviorComplete = false };
    }

    static object ScalarValue(FieldSpec field)
    {
        switch (field.storageType)
        {
            case "bool": return field.boolValue;
            case "double": return field.numberValue;
            case "string": return field.mode == "snapshot-json" ? field.snapshotJson : field.stringValue;
            case "Color": return ToColor32(field.colorR, field.colorG, field.colorB, field.colorA);
            case "bool[]": return field.boolValues ?? Array.Empty<bool>();
            case "double[]": return field.numberValues ?? Array.Empty<double>();
            case "string[]": return field.stringValues ?? Array.Empty<string>();
            default: return null;
        }
    }
    static Array AssignRecords(FieldSpec expected, Type arrayType, Func<string, UnityEngine.Object> resolver, List<string> gaps)
    {
        if (!arrayType.IsArray || arrayType.GetElementType() == null ||
            arrayType.GetElementType().Name != expected.recordTypeName)
        { Gap(gaps, "record_array_type_mismatch:" + expected.sourceFieldName); return null; }
        var rows = expected.recordValues ?? Array.Empty<RecordValueSpec>();
        if (!RecordRowsAreValid(rows))
        { Gap(gaps, "record_array_spec_invalid:" + expected.sourceFieldName); return null; }
        var result = Array.CreateInstance(arrayType.GetElementType(), rows.Length);
        for (int i = 0; i < rows.Length; i++)
        {
            var instance = Activator.CreateInstance(arrayType.GetElementType());
            foreach (var field in rows[i].fields ?? Array.Empty<RecordFieldValueSpec>())
            {
                var info = instance.GetType().GetField(field.fieldName, BindingFlags.Instance | BindingFlags.Public | BindingFlags.DeclaredOnly);
                if (info == null) { Gap(gaps, "record_field_missing:" + field.sourceFieldName); continue; }
                object value;
                if (field.storageType == "UnityEngine.Object")
                {
                    value = field.nullExpected ? null : ResolveOne(field.refValue, resolver, gaps,
                        expected.sourceFieldName + "[" + i + "]." + field.sourceFieldName);
                    if (!field.nullExpected && value == null) continue;
                }
                else value = RecordScalarValue(field);
                if ((value == null && !field.nullExpected) || (value != null && !info.FieldType.IsInstanceOfType(value)))
                { Gap(gaps, "record_field_type_mismatch:" + field.sourceFieldName); continue; }
                info.SetValue(instance, value);
            }
            result.SetValue(instance, i);
        }
        return result;
    }
    static RecordValueSpec[] ReadRecords(FieldSpec expected, object value, Func<string, UnityEngine.Object> resolver,
        List<string> gaps, ref bool verified)
    {
        var rows = value as Array;
        var sourceRows = expected.recordValues ?? Array.Empty<RecordValueSpec>();
        if (!RecordRowsAreValid(sourceRows)) { verified = false; return null; }
        if (rows == null || rows.Length != sourceRows.Length) { verified = false; return null; }
        var actualRows = new RecordValueSpec[rows.Length];
        for (int i = 0; i < rows.Length; i++)
        {
            var sourceFields = sourceRows[i].fields ?? Array.Empty<RecordFieldValueSpec>();
            var actualFields = new RecordFieldValueSpec[sourceFields.Length];
            var instance = rows.GetValue(i);
            if (instance == null) { Gap(gaps, "record_instance_missing:" + expected.sourceFieldName + "[" + i + "]"); verified = false; continue; }
            for (int j = 0; j < sourceFields.Length; j++)
            {
                var source = sourceFields[j]; var actual = Clone(source);
                var info = instance.GetType().GetField(source.fieldName, BindingFlags.Instance | BindingFlags.Public | BindingFlags.DeclaredOnly);
                if (info == null) { Gap(gaps, "record_field_missing:" + source.sourceFieldName); verified = false; actualFields[j] = actual; continue; }
                var fieldValue = info.GetValue(instance);
                if (source.storageType == "UnityEngine.Object")
                {
                    if (source.nullExpected) actual.referenceVerified = (fieldValue as UnityEngine.Object) == null;
                    else
                    {
                        var resolved = ResolveOne(source.refValue, resolver, gaps, expected.sourceFieldName + "[" + i + "]." + source.sourceFieldName);
                        actual.refValue = source.refValue;
                        actual.referenceVerified = resolved != null && ReferenceEquals(fieldValue, resolved);
                    }
                    if (!actual.referenceVerified) { Gap(gaps, "record_reference_readback_mismatch:" + source.sourceFieldName); verified = false; }
                }
                else
                {
                    CopyActual(actual, fieldValue);
                    if (!ValueEquals(source, fieldValue)) { Gap(gaps, "record_field_readback_mismatch:" + source.sourceFieldName); verified = false; }
                }
                actualFields[j] = actual;
            }
            actualRows[i] = new RecordValueSpec { index = i, fields = actualFields };
        }
        return actualRows;
    }
    static object RecordScalarValue(RecordFieldValueSpec field)
    {
        switch (field.storageType)
        {
            case "bool": return field.boolValue;
            case "double": return field.numberValue;
            case "string": return field.stringValue;
            case "Color": return ToColor32(field.colorR, field.colorG, field.colorB, field.colorA);
            default: return null;
        }
    }
    static Color32 ToColor32(int r, int g, int b, int a)
    {
        if (r < 0 || r > 255 || g < 0 || g > 255 || b < 0 || b > 255 || a < 0 || a > 255)
            throw new InvalidOperationException("STATIC_COLOR_CHANNEL_OUT_OF_RANGE");
        return new Color32((byte)r, (byte)g, (byte)b, (byte)a);
    }
    static void CopyActual(RecordFieldValueSpec field, object value)
    {
        if (field.storageType == "bool" && value is bool) field.boolValue = (bool)value;
        else if (field.storageType == "double" && value is double) field.numberValue = (double)value;
        else if (field.storageType == "string" && value is string) field.stringValue = (string)value;
        else if (field.storageType == "Color" && value is Color32) CopyColor(field, (Color32)value);
    }
    static UnityEngine.Object ResolveOne(string sourceId, Func<string, UnityEngine.Object> resolver, List<string> gaps, string field)
    {
        if (String.IsNullOrEmpty(sourceId) || resolver == null) { Gap(gaps, "reference_resolver_missing:" + field); return null; }
        try { var value = resolver(sourceId); if (value == null) Gap(gaps, "reference_unresolved:" + field + ":" + sourceId); return value; }
        catch (Exception error) { Gap(gaps, "reference_resolver_failed:" + field + ":" + error.GetType().Name); return null; }
    }
    static bool ValueEquals(FieldSpec expected, object actual)
    {
        if (expected.storageType == "bool") return actual is bool && (bool)actual == expected.boolValue;
        if (expected.storageType == "double") return actual is double && (double)actual == expected.numberValue;
        if (expected.storageType == "string") return actual is string && (string)actual == (expected.mode == "snapshot-json" ? expected.snapshotJson : expected.stringValue);
        if (expected.storageType == "Color") return ColorEquals(actual, expected.colorR, expected.colorG, expected.colorB, expected.colorA);
        if (expected.storageType == "bool[]") return (actual as bool[] ?? Array.Empty<bool>()).SequenceEqual(expected.boolValues ?? Array.Empty<bool>());
        if (expected.storageType == "double[]") return (actual as double[] ?? Array.Empty<double>()).SequenceEqual(expected.numberValues ?? Array.Empty<double>());
        if (expected.storageType == "string[]") return (actual as string[] ?? Array.Empty<string>()).SequenceEqual(expected.stringValues ?? Array.Empty<string>());
        return false;
    }
    static bool ValueEquals(RecordFieldValueSpec expected, object actual)
    {
        if (expected.storageType == "bool") return actual is bool && (bool)actual == expected.boolValue;
        if (expected.storageType == "double") return actual is double && (double)actual == expected.numberValue;
        if (expected.storageType == "string") return actual is string && (string)actual == expected.stringValue;
        if (expected.storageType == "Color") return ColorEquals(actual, expected.colorR, expected.colorG, expected.colorB, expected.colorA);
        return false;
    }
    static void CopyActual(FieldSpec field, object value)
    {
        if (field.storageType == "bool" && value is bool) field.boolValue = (bool)value;
        else if (field.storageType == "double" && value is double) field.numberValue = (double)value;
        else if (field.storageType == "string" && value is string) field.stringValue = (string)value;
        else if (field.storageType == "Color" && value is Color32) CopyColor(field, (Color32)value);
        else if (field.storageType == "bool[]") field.boolValues = value as bool[] ?? Array.Empty<bool>();
        else if (field.storageType == "double[]") field.numberValues = value as double[] ?? Array.Empty<double>();
        else if (field.storageType == "string[]") field.stringValues = value as string[] ?? Array.Empty<string>();
    }
    static FieldSpec Clone(FieldSpec field)
    {
        if (field == null) return null;
        return new FieldSpec {
            name = field.name, sourceFieldName = field.sourceFieldName, fieldName = field.fieldName,
            kind = field.kind, storageType = field.storageType, elementKind = field.elementKind,
            mode = field.mode, sourceDeclaredType = field.sourceDeclaredType,
            referenceKind = field.referenceKind, dynamicType = field.dynamicType,
            sourceConstant = field.sourceConstant, accessorBackingJson = field.accessorBackingJson,
            sourceValueEncoding = field.sourceValueEncoding, sourceValueEncodingJson = field.sourceValueEncodingJson,
            recordTypeName = field.recordTypeName, recordName = field.recordName,
            numberValue = field.numberValue, stringValue = field.stringValue, refValue = field.refValue,
            snapshotJson = field.snapshotJson, boolValue = field.boolValue, nullExpected = field.nullExpected,
            referenceVerified = field.referenceVerified, referencesVerified = field.referencesVerified,
            numberValues = field.numberValues == null ? null : (double[])field.numberValues.Clone(),
            stringValues = field.stringValues == null ? null : (string[])field.stringValues.Clone(),
            refValues = field.refValues == null ? null : (string[])field.refValues.Clone(),
            boolValues = field.boolValues == null ? null : (bool[])field.boolValues.Clone(),
            colorR = field.colorR, colorG = field.colorG, colorB = field.colorB, colorA = field.colorA,
            recordValues = Clone(field.recordValues)
        };
    }
    static RecordFieldValueSpec Clone(RecordFieldValueSpec field)
    {
        if (field == null) return null;
        return new RecordFieldValueSpec {
            name = field.name, sourceFieldName = field.sourceFieldName, fieldName = field.fieldName,
            kind = field.kind, storageType = field.storageType, referenceKind = field.referenceKind,
            sourceDeclaredType = field.sourceDeclaredType, dynamicType = field.dynamicType,
            sourceConstant = field.sourceConstant, sourceValueEncoding = field.sourceValueEncoding,
            sourceValueEncodingJson = field.sourceValueEncodingJson, numberValue = field.numberValue,
            stringValue = field.stringValue, refValue = field.refValue, boolValue = field.boolValue,
            nullExpected = field.nullExpected, referenceVerified = field.referenceVerified,
            colorR = field.colorR, colorG = field.colorG, colorB = field.colorB, colorA = field.colorA
        };
    }
    static RecordValueSpec[] Clone(RecordValueSpec[] rows)
    {
        if (rows == null) return null;
        return rows.Select(row => row == null ? null : new RecordValueSpec {
            index = row.index,
            fields = row.fields == null ? null : row.fields.Select(Clone).ToArray()
        }).ToArray();
    }
    static FieldSpec[] Clone(FieldSpec[] fields) { return (fields ?? Array.Empty<FieldSpec>()).Select(Clone).ToArray(); }
    static bool ColorEquals(object value, int r, int g, int b, int a)
    { return value is Color32 color && color.r == r && color.g == g && color.b == b && color.a == a; }
    static void CopyColor(FieldSpec field, Color32 color)
    { field.colorR = color.r; field.colorG = color.g; field.colorB = color.b; field.colorA = color.a; }
    static void CopyColor(RecordFieldValueSpec field, Color32 color)
    { field.colorR = color.r; field.colorG = color.g; field.colorB = color.b; field.colorA = color.a; }
    // JsonUtility cannot reliably round-trip this nested plan shape. The plan
    // has already been parsed by Unity; validate its typed rows directly, then
    // prove the actual assigned values in ReadRecords after native persistence.
    static bool RecordRowsAreValid(RecordValueSpec[] rows)
    {
        rows = rows ?? Array.Empty<RecordValueSpec>();
        for (var i = 0; i < rows.Length; i++)
        {
            var row = rows[i];
            if (row == null || row.index != i || row.fields == null) return false;
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (var field in row.fields)
            {
                if (field == null || String.IsNullOrEmpty(field.sourceFieldName) ||
                    String.IsNullOrEmpty(field.fieldName) || !names.Add(field.fieldName)) return false;
                switch (field.storageType)
                {
                    case "bool":
                    case "string":
                    case "Color":
                        break;
                    case "double":
                        if (Double.IsNaN(field.numberValue) || Double.IsInfinity(field.numberValue)) return false;
                        break;
                    case "UnityEngine.Object":
                        if (field.nullExpected ? !String.IsNullOrEmpty(field.refValue) : String.IsNullOrEmpty(field.refValue)) return false;
                        break;
                    default:
                        return false;
                }
            }
        }
        return true;
    }
    static string NativeSourceId(MonoBehaviour component)
    {
        if (component == null) return null;
        try
        {
            var field = component.GetType().GetField("__monkeySourceId", BindingFlags.Instance | BindingFlags.Public | BindingFlags.DeclaredOnly);
            return field == null || field.FieldType != typeof(string) ? null : field.GetValue(component) as string;
        }
        catch { return null; }
    }
    static string NativeScriptGuid(MonoBehaviour component)
    {
        if (component == null) return null;
        try
        {
            var script = UnityEditor.MonoScript.FromMonoBehaviour(component);
            if (script == null) return null;
            var path = UnityEditor.AssetDatabase.GetAssetPath(script);
            return String.IsNullOrEmpty(path) ? null : UnityEditor.AssetDatabase.AssetPathToGUID(path);
        }
        catch { return null; }
    }
    static Readback Result(Spec spec, MonoBehaviour component, bool verified, List<string> gaps, FieldSpec[] fields)
    {
        bool enabled = component != null && component.enabled;
        if (enabled) { component.enabled = false; Gap(gaps, "behavior_enabled"); verified = false; }
        var nativeSourceId = NativeSourceId(component);
        var nativeScriptGuid = NativeScriptGuid(component);
        bool identityVerified = spec != null && nativeSourceId == spec.sourceId && nativeScriptGuid == spec.scriptGuid;
        if (!identityVerified) Gap(gaps, "native_identity_unverified");
        return new Readback { sourceId = spec == null ? null : spec.sourceId, typeName = spec == null ? null : spec.typeName,
            nativeSourceId = nativeSourceId, scriptGuid = spec == null ? null : spec.scriptGuid, nativeScriptGuid = nativeScriptGuid,
            nativeIdentityVerified = identityVerified, fieldsVerified = verified && gaps.Count == 0,
            enabled = false, fields = fields, gaps = MergeGaps(spec, gaps), nativeComplete = false };
    }
}
