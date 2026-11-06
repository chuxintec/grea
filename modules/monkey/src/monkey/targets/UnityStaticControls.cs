using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using TMPro;
using UnityEditor;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// DTO and native operations for the frozen cc.EditBox/cc.Graphics subset.
/// The owning importer supplies the exact component/material resolvers and
/// calls Read after saving and reopening its prefab candidate.
/// </summary>
public static partial class MonkeyImporter
{
    [Serializable] public sealed class StaticControlReferenceSpec
    {
        public string sourceField, field, sourceId, sourceType, nativeNodeSourceId;
    }

    [Serializable] public sealed class StaticControlMaterialSpec
    {
        public string sourceId, resolvedSourceId, sourceMaterialName;
        public string effectSourceId, effectName, sourceEffectUuid, nativeCreatorMaterialLookup;
        public int sourceTechniqueIndex;
        public string sourceTechniqueDefinesJson;
        public string unityProfile, sourceEffectDocumentSha256, sourceEffectNormalizedGlslSha256;
        public string unityShaderPath, unityShaderSha256, unityMaterialGuid, unityMaterialPath;
    }

    [Serializable] public sealed class StaticControlSpec
    {
        public int schemaVersion, maxLength, sourceObjectIndex;
        public string sourceId, node, sourceType, sourceManifestSha256;
        public string nativeCreatorType, inputBehavior, drawingBehavior, sourceDrawingCommands;
        public bool sourceEnabled, enabled;
        public StaticControlReferenceSpec[] references;
        public StaticControlMaterialSpec[] materials;
    }

    [Serializable] public sealed class StaticControlReferenceReadback
    {
        public string field, sourceId, componentType, assetGuid, globalObjectId;
        public long localFileId;
        public string entityId;
        public bool persistent, verified;
    }

    [Serializable] public sealed class StaticControlMaterialReadback
    {
        public string sourceId, resolvedSourceId, effectName, assetGuid, globalObjectId;
        public long localFileId;
        public string entityId;
        public bool persistent, verified;
    }

    [Serializable] public sealed class StaticControlReadback
    {
        public string sourceId, sourceType, nativeType, sourceDrawingCommands,carrierGuid; public long carrierLocalFileId;
        public string componentEntityId; public int maxLength;
        public bool enabled;
        public StaticControlReferenceReadback[] references;
        public StaticControlMaterialReadback[] materials;
    }

    public static Component CreateStaticControl(StaticControlSpec spec, GameObject node)
    {
        if (spec == null || node == null || spec.enabled || string.IsNullOrEmpty(spec.sourceId))
            throw new InvalidOperationException("STATIC_CONTROL_CREATE_SPEC_INVALID");
        Component component;
        if (spec.sourceType == "cc.EditBox")
        {
            if (node.GetComponent<NativeStaticEditBox>() != null)
                throw new InvalidOperationException("STATIC_EDITBOX_ALREADY_EXISTS: " + spec.sourceId);
            var carrier = node.AddComponent<NativeStaticEditBox>();
            carrier.sourceId = spec.sourceId;
            carrier.enabled = false;
            component = carrier;
        }
        else if (spec.sourceType == "cc.Graphics")
        {
            if (node.GetComponent<NativeStaticGraphics>() != null)
                throw new InvalidOperationException("STATIC_GRAPHICS_ALREADY_EXISTS: " + spec.sourceId);
            var carrier = node.AddComponent<NativeStaticGraphics>();
            carrier.sourceId = spec.sourceId;
            carrier.enabled = false;
            component = carrier;
        }
        else throw new InvalidOperationException("STATIC_CONTROL_SOURCE_TYPE_UNSUPPORTED: " + spec.sourceType);
        return component;
    }

    public static void AssignStaticControl(StaticControlSpec spec, Component component,
        Func<string, Component> resolveComponent, Func<StaticControlMaterialSpec, Material> resolveMaterial)
    {
        if (spec == null || component == null || ((Behaviour)component).enabled || component.gameObject == null)
            throw new InvalidOperationException("STATIC_CONTROL_ASSIGN_TARGET_INVALID");
        if (spec.sourceType == "cc.EditBox")
        {
            var carrier = component as NativeStaticEditBox;
            if (carrier == null || spec.maxLength < 0 || spec.references == null || spec.references.Length != 3)
                throw new InvalidOperationException("STATIC_EDITBOX_ASSIGN_SPEC_INVALID: " + spec.sourceId);
            var fields = spec.references.ToDictionary(x => x.field, x => x);
            var background = ResolveEditBoxReference(fields, "background", "cc.Sprite", resolveComponent) as Image;
            var placeholder = ResolveEditBoxReference(fields, "placeholderLabel", "cc.Label", resolveComponent) as TMP_Text;
            var text = ResolveEditBoxReference(fields, "textLabel", "cc.Label", resolveComponent) as TMP_Text;
            if (background == null || placeholder == null || text == null)
                throw new InvalidOperationException("STATIC_EDITBOX_TARGET_COMPONENT_TYPE_MISMATCH: " + spec.sourceId);
            carrier.background = background;
            carrier.placeholderLabel = placeholder;
            carrier.textLabel = text;
            carrier.maxLength = spec.maxLength;
            if (carrier.enabled || carrier.background != background || carrier.placeholderLabel != placeholder ||
                carrier.textLabel != text || carrier.maxLength != spec.maxLength)
                throw new InvalidOperationException("STATIC_EDITBOX_ASSIGNMENT_READBACK_FAILED: " + spec.sourceId);
            return;
        }

        var graphics = component as NativeStaticGraphics;
        if (graphics == null || spec.sourceDrawingCommands != "not-serialized-empty-in-fixed-state" ||
            spec.materials == null || spec.materials.Length == 0 || resolveMaterial == null)
            throw new InvalidOperationException("STATIC_GRAPHICS_ASSIGN_SPEC_INVALID: " + spec.sourceId);
        graphics.sourceMaterials = new Material[spec.materials.Length];
        graphics.sourceMaterialIds = new string[spec.materials.Length];
        graphics.sourceEffectIds = new string[spec.materials.Length];
        graphics.sourceEffectNames = new string[spec.materials.Length];
        for (int i = 0; i < spec.materials.Length; i++)
        {
            var materialSpec = spec.materials[i];
            var material = resolveMaterial(materialSpec);
            if (material == null)
                throw new InvalidOperationException("STATIC_GRAPHICS_SOURCE_MATERIAL_UNRESOLVED: " + materialSpec.sourceId);
            graphics.sourceMaterials[i] = material;
            graphics.sourceMaterialIds[i] = materialSpec.sourceId;
            graphics.sourceEffectIds[i] = materialSpec.effectSourceId;
            graphics.sourceEffectNames[i] = materialSpec.effectName;
        }
        graphics.sourceDrawingCommands = spec.sourceDrawingCommands;
        if (graphics.enabled || graphics.sourceMaterials.Length != spec.materials.Length ||
            graphics.sourceMaterials.Any(x => x == null))
            throw new InvalidOperationException("STATIC_GRAPHICS_ASSIGNMENT_READBACK_FAILED: " + spec.sourceId);
    }

    static Component ResolveEditBoxReference(Dictionary<string, StaticControlReferenceSpec> fields,
        string field, string expectedSourceType, Func<string, Component> resolveComponent)
    {
        if (!fields.TryGetValue(field, out var spec) || spec.sourceType != expectedSourceType || resolveComponent == null)
            throw new InvalidOperationException("STATIC_EDITBOX_REFERENCE_SPEC_INVALID: " + field);
        var component = resolveComponent(spec.sourceId);
        if (component == null) throw new InvalidOperationException("STATIC_EDITBOX_REFERENCE_UNRESOLVED: " + spec.sourceId);
        return component;
    }

    public static StaticControlReadback ReadStaticControl(StaticControlSpec spec, Component component,
        Func<string, Component> resolveComponent, Func<StaticControlMaterialSpec, Material> resolveMaterial)
    {
        if (spec == null || component == null)
            throw new InvalidOperationException("STATIC_CONTROL_READBACK_TARGET_MISSING");
        var row = new StaticControlReadback {
            sourceId = spec.sourceId, sourceType = spec.sourceType, enabled = ((Behaviour)component).enabled,
            componentEntityId = component.GetEntityId().ToString(),
            nativeType = component.GetType().FullName,
            references = Array.Empty<StaticControlReferenceReadback>(),
            materials = Array.Empty<StaticControlMaterialReadback>()
        };
        string componentGuid; long componentFileId;
        if (AssetDatabase.TryGetGUIDAndLocalFileIdentifier(component, out componentGuid, out componentFileId))
        {
            row.carrierGuid=componentGuid;row.carrierLocalFileId=componentFileId;
        }
        if (spec.sourceType == "cc.EditBox")
        {
            var carrier = component as NativeStaticEditBox;
            if (carrier == null || carrier.sourceId != spec.sourceId)
                throw new InvalidOperationException("STATIC_EDITBOX_CARRIER_IDENTITY_MISMATCH: " + spec.sourceId);
            row.maxLength = carrier.maxLength;
            row.references = spec.references.Select(reference => {
                var target = resolveComponent == null ? null : resolveComponent(reference.sourceId);
                Component actual = reference.field == "background" ? carrier.background :
                    reference.field == "placeholderLabel" ? carrier.placeholderLabel :
                    reference.field == "textLabel" ? carrier.textLabel : null;
                var match = actual != null && ReferenceEquals(actual, target);
                var identity = PersistentIdentity(actual);
                return new StaticControlReferenceReadback {
                    field = reference.field, sourceId = reference.sourceId,
                    componentType = actual == null ? null : actual.GetType().FullName,
                    assetGuid = identity.guid, localFileId = identity.localFileId,
                    globalObjectId = identity.globalId, entityId = actual == null ? null : actual.GetEntityId().ToString(),
                    persistent = identity.persistent, verified = match
                };
            }).ToArray();
        }
        else
        {
            var carrier = component as NativeStaticGraphics;
            if (carrier == null || carrier.sourceId != spec.sourceId ||
                carrier.sourceDrawingCommands != spec.sourceDrawingCommands)
                throw new InvalidOperationException("STATIC_GRAPHICS_CARRIER_IDENTITY_MISMATCH: " + spec.sourceId);
            row.sourceDrawingCommands = carrier.sourceDrawingCommands;
            row.materials = spec.materials.Select((materialSpec, index) => {
                var actual = carrier.sourceMaterials != null && index < carrier.sourceMaterials.Length
                    ? carrier.sourceMaterials[index] : null;
                var expected = resolveMaterial == null ? null : resolveMaterial(materialSpec);
                var identity = PersistentIdentity(actual);
                return new StaticControlMaterialReadback {
                    sourceId = materialSpec.sourceId, resolvedSourceId = materialSpec.resolvedSourceId,
                    effectName = materialSpec.effectName, assetGuid = identity.guid,
                    localFileId = identity.localFileId, globalObjectId = identity.globalId,
                    entityId = actual == null ? null : actual.GetEntityId().ToString(), persistent = identity.persistent,
                    verified = actual != null && ReferenceEquals(actual, expected) &&
                        carrier.sourceMaterialIds != null && index < carrier.sourceMaterialIds.Length &&
                        carrier.sourceMaterialIds[index] == materialSpec.sourceId &&
                        carrier.sourceEffectIds != null && index < carrier.sourceEffectIds.Length &&
                        carrier.sourceEffectIds[index] == materialSpec.effectSourceId &&
                        carrier.sourceEffectNames != null && index < carrier.sourceEffectNames.Length &&
                        carrier.sourceEffectNames[index] == materialSpec.effectName
                };
            }).ToArray();
        }
        return row;
    }

    /// <summary>Create disabled controls and their exact profile-bound Material assets.</summary>
    public static StaticControlReadback[] CreateStaticControls(StaticControlSpec[] specs,
        IDictionary<string, GameObject> nodes)
    {
        var componentResolver = ComponentResolver(specs, nodes);
        var materialResolver = MaterialResolver(specs, true);
        var results = new List<StaticControlReadback>();
        foreach (var spec in specs ?? Array.Empty<StaticControlSpec>())
        {
            if (spec == null || !nodes.TryGetValue(spec.node, out var node) || node == null)
                throw new InvalidOperationException("STATIC_CONTROL_NODE_MISSING: " + (spec == null ? "<null>" : spec.sourceId));
            var component = CreateStaticControl(spec, node);
            AssignStaticControl(spec, component, componentResolver, materialResolver);
            results.Add(ReadStaticControl(spec, component, componentResolver, materialResolver));
        }
        return results.ToArray();
    }

    /// <summary>Read controls from the saved/reopened persistent prefab node map.</summary>
    public static StaticControlReadback[] ReadStaticControls(StaticControlSpec[] specs,
        IDictionary<string, GameObject> persistentMap)
    {
        var componentResolver = ComponentResolver(specs, persistentMap);
        var materialResolver = MaterialResolver(specs, false);
        var results = new List<StaticControlReadback>();
        foreach (var spec in specs ?? Array.Empty<StaticControlSpec>())
        {
            if (spec == null || !persistentMap.TryGetValue(spec.node, out var node) || node == null)
                throw new InvalidOperationException("STATIC_CONTROL_PERSISTENT_NODE_MISSING: " + (spec == null ? "<null>" : spec.sourceId));
            Component component;
            if (spec.sourceType == "cc.EditBox")
            {
                var found = node.GetComponents<NativeStaticEditBox>().Where(x => x.sourceId == spec.sourceId).ToArray();
                if (found.Length != 1) throw new InvalidOperationException("STATIC_EDITBOX_PERSISTENT_IDENTITY_MISMATCH: " + spec.sourceId);
                component = found[0];
            }
            else
            {
                var found = node.GetComponents<NativeStaticGraphics>().Where(x => x.sourceId == spec.sourceId).ToArray();
                if (found.Length != 1) throw new InvalidOperationException("STATIC_GRAPHICS_PERSISTENT_IDENTITY_MISMATCH: " + spec.sourceId);
                component = found[0];
            }
            results.Add(ReadStaticControl(spec, component, componentResolver, materialResolver));
        }
        var readbacks = results.ToArray();
        var gaps = VerifyStaticControlReadbacks(specs, readbacks, true);
        if (gaps.Length != 0)
            throw new InvalidOperationException("STATIC_CONTROL_SAVED_READBACK_FAILED: " + string.Join("; ", gaps));
        return readbacks;
    }

    public static string[] VerifyStaticControlReadbacks(StaticControlSpec[] specs,
        StaticControlReadback[] readbacks, bool requirePersistent)
    {
        var expected = (specs ?? Array.Empty<StaticControlSpec>()).Where(x => x != null)
            .ToDictionary(x => x.sourceId, x => x);
        var actualRows = readbacks ?? Array.Empty<StaticControlReadback>();
        var actual = actualRows.Where(x => x != null).GroupBy(x => x.sourceId).ToDictionary(x => x.Key, x => x.ToArray());
        var gaps = new List<string>();
        if (actualRows.Length != expected.Count || actual.Any(x => x.Value.Length != 1) ||
            !expected.Keys.ToHashSet().SetEquals(actual.Keys))
            gaps.Add("static control source identities/count differ");
        foreach (var pair in expected)
        {
            if (!actual.TryGetValue(pair.Key, out var rows) || rows.Length != 1) continue;
            var spec = pair.Value; var row = rows[0];
            var expectedType = spec.sourceType == "cc.EditBox" ? typeof(NativeStaticEditBox).FullName : typeof(NativeStaticGraphics).FullName;
            if (row.sourceType != spec.sourceType || row.nativeType == null || !row.nativeType.StartsWith(expectedType, StringComparison.Ordinal) || row.enabled)
                gaps.Add("native type/disabled state differs: " + pair.Key);
            if (spec.sourceType == "cc.EditBox")
            {
                if (row.maxLength != spec.maxLength || row.references == null || row.references.Length != spec.references.Length)
                    gaps.Add("EditBox maxLength/reference count differs: " + pair.Key);
                else foreach (var reference in spec.references)
                {
                    var found = row.references.Where(x => x != null && x.field == reference.field).ToArray();
                    if (found.Length != 1 || found[0].sourceId != reference.sourceId || !found[0].verified ||
                        (requirePersistent && (!found[0].persistent || string.IsNullOrEmpty(found[0].assetGuid) || found[0].localFileId == 0)))
                        gaps.Add("EditBox reference identity differs: " + pair.Key + "/" + reference.field);
                }
            }
            else
            {
                if (row.sourceDrawingCommands != spec.sourceDrawingCommands || row.sourceDrawingCommands != "not-serialized-empty-in-fixed-state")
                    gaps.Add("Graphics static drawing state differs: " + pair.Key);
                if (row.materials == null || row.materials.Length != spec.materials.Length)
                    gaps.Add("Graphics material count differs: " + pair.Key);
                else for (int i = 0; i < spec.materials.Length; i++)
                {
                    var material = row.materials[i]; var wanted = spec.materials[i];
                    if (material == null || material.sourceId != wanted.sourceId || material.effectName != wanted.effectName ||
                        !material.verified || (requirePersistent && (!material.persistent || string.IsNullOrEmpty(material.assetGuid) || material.localFileId == 0)))
                        gaps.Add("Graphics material identity differs: " + pair.Key + "/" + i);
                }
            }
        }
        return gaps.ToArray();
    }

    static Func<string, Component> ComponentResolver(StaticControlSpec[] specs, IDictionary<string, GameObject> nodes)
    {
        var refs = new Dictionary<string, StaticControlReferenceSpec>();
        foreach (var reference in (specs ?? Array.Empty<StaticControlSpec>()).Where(x => x != null)
            .SelectMany(x => x.references ?? Array.Empty<StaticControlReferenceSpec>()))
        {
            if (string.IsNullOrEmpty(reference.sourceId) || string.IsNullOrEmpty(reference.nativeNodeSourceId))
                throw new InvalidOperationException("STATIC_CONTROL_REFERENCE_IDENTITY_INCOMPLETE");
            if (refs.TryGetValue(reference.sourceId, out var previous) &&
                (previous.nativeNodeSourceId != reference.nativeNodeSourceId || previous.sourceType != reference.sourceType))
                throw new InvalidOperationException("STATIC_CONTROL_REFERENCE_IDENTITY_AMBIGUOUS: " + reference.sourceId);
            refs[reference.sourceId] = reference;
        }
        return sourceId => {
            if (!refs.TryGetValue(sourceId, out var reference) || !nodes.TryGetValue(reference.nativeNodeSourceId, out var node) || node == null)
                return null;
            if (reference.sourceType == "cc.Sprite")
            {
                var found = node.GetComponents<Image>();
                return found.Length == 1 ? found[0] : null;
            }
            if (reference.sourceType == "cc.Label")
            {
                var found = node.GetComponents<TMP_Text>();
                return found.Length == 1 ? found[0] : null;
            }
            return null;
        };
    }

    static Func<StaticControlMaterialSpec, Material> MaterialResolver(StaticControlSpec[] specs, bool allowCreate)
    {
        var groups = (specs ?? Array.Empty<StaticControlSpec>()).Where(x => x != null)
            .SelectMany(x => x.materials ?? Array.Empty<StaticControlMaterialSpec>()).GroupBy(x => x.sourceId).ToArray();
        foreach (var group in groups)
            if (group.Any(x => x.unityProfile != group.First().unityProfile ||
                x.sourceEffectNormalizedGlslSha256 != group.First().sourceEffectNormalizedGlslSha256 ||
                x.unityShaderPath != group.First().unityShaderPath || x.unityShaderSha256 != group.First().unityShaderSha256 ||
                x.unityMaterialGuid != group.First().unityMaterialGuid || x.unityMaterialPath != group.First().unityMaterialPath))
                throw new InvalidOperationException("STATIC_GRAPHICS_SOURCE_MATERIAL_CONTRACT_CONFLICT: " + group.Key);
        var rows = groups.ToDictionary(x => x.Key, x => x.First());
        var cache = new Dictionary<string, Material>();
        return requested => {
            if (requested == null || !rows.TryGetValue(requested.sourceId, out var bound) ||
                bound.unityProfile != "cocos24-builtin-2d-graphics-glsl1-vertex-color-distance-v1" ||
                bound.sourceEffectNormalizedGlslSha256 != "a4db92cdb68f3fb8366c189daa5f9a2e318c28f6674e80ed01f97868633a9b76" ||
                bound.sourceTechniqueIndex != 0 || bound.sourceTechniqueDefinesJson != "{}" ||
                bound.unityShaderPath != "Assets/Game/Content/Materials/StaticControls/NativeStaticGraphics.shader" ||
                string.IsNullOrEmpty(bound.unityMaterialGuid) ||
                bound.unityMaterialPath != "Assets/Game/Content/Materials/StaticControls/NativeStaticGraphics_" +
                    bound.sourceEffectNormalizedGlslSha256.Substring(0, 16) + ".mat")
                throw new InvalidOperationException("STATIC_GRAPHICS_UNITY_EFFECT_PROFILE_UNVERIFIED");
            if (cache.TryGetValue(requested.sourceId, out var cached)) return cached;
            var shader = AssetDatabase.LoadAssetAtPath<Shader>(bound.unityShaderPath);
            if (shader == null || shader.name != "Monkey/StaticControls/CocosBuiltin2DGraphics" ||
                !File.Exists(bound.unityShaderPath) || HashBytes(File.ReadAllBytes(bound.unityShaderPath)) != bound.unityShaderSha256)
                throw new InvalidOperationException("STATIC_GRAPHICS_UNITY_SHADER_IDENTITY_MISMATCH: " + bound.unityShaderPath);
            var folder = Path.GetDirectoryName(bound.unityMaterialPath)?.Replace('\\', '/');
            if (string.IsNullOrEmpty(folder) || !(folder=="Assets/Game/Content/Materials/StaticControls"||folder.StartsWith("Assets/Game/Content/Materials/StaticControls/", StringComparison.Ordinal)) ||
                bound.unityMaterialPath.Contains(".."))
                throw new InvalidOperationException("STATIC_GRAPHICS_UNITY_MATERIAL_PATH_UNSAFE");
            Directory.CreateDirectory(folder);
            var material = AssetDatabase.LoadAssetAtPath<Material>(bound.unityMaterialPath);
            if (material == null)
            {
                if (!allowCreate) throw new InvalidOperationException("STATIC_GRAPHICS_UNITY_MATERIAL_MISSING: " + bound.unityMaterialPath);
                var existingGuidPath = AssetDatabase.GUIDToAssetPath(bound.unityMaterialGuid);
                if (!string.IsNullOrEmpty(existingGuidPath) || File.Exists(bound.unityMaterialPath) ||
                    File.Exists(bound.unityMaterialPath + ".meta"))
                    throw new InvalidOperationException("STATIC_GRAPHICS_UNITY_MATERIAL_IDENTITY_COLLISION: " + bound.unityMaterialPath);
                material = new Material(shader) { name = Path.GetFileNameWithoutExtension(bound.unityMaterialPath) };
                material.SetFloat("_AlphaThreshold", 0.5f);
                File.WriteAllText(bound.unityMaterialPath+".meta","fileFormatVersion: 2\nguid: "+bound.unityMaterialGuid+"\nNativeFormatImporter:\n  externalObjects: {}\n  mainObjectFileID: 2100000\n");
                UnityEditorInternal.InternalEditorUtility.SaveToSerializedFileAndForget(new UnityEngine.Object[]{material},bound.unityMaterialPath,true);
                UnityEngine.Object.DestroyImmediate(material);AssetDatabase.ImportAsset(bound.unityMaterialPath,ImportAssetOptions.ForceSynchronousImport);
                material=AssetDatabase.LoadAssetAtPath<Material>(bound.unityMaterialPath);
            }
            if (material.shader != shader || !EditorUtility.IsPersistent(material) ||
                !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(material, out var guid, out long localId) ||
                guid != bound.unityMaterialGuid || localId == 0)
                throw new InvalidOperationException("STATIC_GRAPHICS_UNITY_MATERIAL_IDENTITY_MISMATCH: " + bound.unityMaterialPath);
            cache[requested.sourceId] = material;
            return material;
        };
    }

    static string HashBytes(byte[] bytes)
    {
        using (var sha = System.Security.Cryptography.SHA256.Create())
            return BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
    }

    static (bool persistent, string guid, long localFileId, string globalId) PersistentIdentity(UnityEngine.Object value)
    {
        if (value == null) return (false, null, 0, null);
        var persistent = EditorUtility.IsPersistent(value);
        var hasAssetId = AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value, out var guid, out long fileId);
        var global = GlobalObjectId.GetGlobalObjectIdSlow(value).ToString();
        return (persistent && hasAssetId, hasAssetId ? guid : null, hasAssetId ? fileId : 0, global);
    }
}
