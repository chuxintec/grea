using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEditorInternal;
using UnityEngine;
using Monkey.StaticMaskSort;
using Monkey.StaticSortQueueProxy;

public static partial class MonkeyImporter
{
    [Serializable] public class StaticMaskSourceDefault { public string field, sourceProperty, value; public string[] sourceIds; }
    [Serializable] public class StaticMaskSourceEngine { public string path, sha256, url; }
    [Serializable] public class StaticMaskContract
    {
        public int schemaVersion;
        public string contract, sourceManifestSha256, sourceProfile, sourceVersion;
        public StaticMaskSourceEngine sourceEngine;
        public StaticMaskSourceDefault[] sourceDefaults;
        public MaskSpec[] masks;
    }

    const string StaticMaskContractName="monkey-static-mask-continuation/1";
    const string StaticMaskSourceProfile="cocos-2.4.15-bundle";
    const string StaticMaskSourceVersion="2.4.15";
    const string StaticMaskSourceEnginePath="cocos2d/core/components/CCMask.js";
    const string StaticMaskSourceEngineSha256="33484e873f07be39fa6433c22819609bc52e51419992ffe8d230d68c453017a6";
    const string StaticMaskSourceEngineUrl="https://raw.githubusercontent.com/cocos/cocos-engine/v2.4.15/cocos2d/core/components/CCMask.js";

    static string[] StaticMaskSourceIds(Plan plan)
    {
        return (plan.components??Array.Empty<ComponentSpec>()).Where(c=>c!=null&&c.type=="cc.Mask")
            .Select(c=>c.sourceId).ToArray();
    }

    static bool IsLegacyStaticMaskContract(StaticMaskContract contract) =>
        contract!=null&&contract.schemaVersion==1&&String.IsNullOrEmpty(contract.contract)&&contract.masks!=null;

    // JsonUtility may materialize an empty nested object for a JSON null. The
    // explicit plan marker owns new contracts; only the recognized schema-1
    // legacy shape is inferred for old instructions that predate the marker.
    static bool HasStaticMasks(Plan plan) => plan!=null&&
        (plan.staticMasksPresent||IsLegacyStaticMaskContract(plan.staticMasks));

    static bool HasStaticMaskContractPayload(StaticMaskContract contract)
    {
        if(contract==null)return false;
        if(contract.schemaVersion!=0||!String.IsNullOrEmpty(contract.contract)||
            !String.IsNullOrEmpty(contract.sourceManifestSha256)||!String.IsNullOrEmpty(contract.sourceProfile)||
            !String.IsNullOrEmpty(contract.sourceVersion))return true;
        var engine=contract.sourceEngine;
        if(engine!=null&&(!String.IsNullOrEmpty(engine.path)||!String.IsNullOrEmpty(engine.sha256)||
            !String.IsNullOrEmpty(engine.url)))return true;
        return contract.sourceDefaults!=null&&contract.sourceDefaults.Length>0||
            contract.masks!=null&&contract.masks.Length>0;
    }

    static bool StaticMaskSourceActivity(Plan plan,string nodeId,out bool activeSelf)
    {
        var nodes=(plan.nodes??Array.Empty<NodeSpec>()).Where(n=>n!=null).ToDictionary(n=>n.sourceId,StringComparer.Ordinal);
        if(!nodes.TryGetValue(nodeId,out var own))throw new InvalidOperationException("STATIC_MASK_SOURCE_NODE_MISSING: "+nodeId);
        activeSelf=own.active;var cursor=nodeId;var seen=new HashSet<string>(StringComparer.Ordinal);
        while(!String.IsNullOrEmpty(cursor))
        {
            if(!seen.Add(cursor)||!nodes.TryGetValue(cursor,out var node))
                throw new InvalidOperationException("STATIC_MASK_SOURCE_NODE_HIERARCHY_INVALID: "+nodeId);
            if(!node.active)return false;
            cursor=node.parent;
        }
        return true;
    }

    static void ValidateStaticMaskContract(Plan plan)
    {
        if(plan==null)throw new InvalidOperationException("STATIC_MASK_CONTRACT_PLAN_MISSING");
        var source=StaticMaskSourceIds(plan);var contract=plan.staticMasks;
        if(source.Any(String.IsNullOrEmpty)||source.Distinct(StringComparer.Ordinal).Count()!=source.Length)
            throw new InvalidOperationException("STATIC_MASK_SOURCE_COMPONENT_IDENTITY_INVALID");
        var legacy=IsLegacyStaticMaskContract(contract);
        if(!plan.staticMasksPresent&&!legacy)
        {
            if(source.Length>0)
                throw new InvalidOperationException("STATIC_MASK_CONTRACT_REQUIRED: sourceMaskCount="+source.Length);
            if(HasStaticMaskContractPayload(contract))
                throw new InvalidOperationException("STATIC_MASK_CONTRACT_PRESENCE_MARKER_MISMATCH");
            return;
        }
        if(contract==null)throw new InvalidOperationException("STATIC_MASK_CONTRACT_DECLARED_BUT_NULL");
        if(contract.masks==null)throw new InvalidOperationException("STATIC_MASK_CONTRACT_ROWS_MISSING");
        if(String.IsNullOrEmpty(plan.sourceManifestSha256)||contract.sourceManifestSha256!=plan.sourceManifestSha256)
            throw new InvalidOperationException("STATIC_MASK_SOURCE_MANIFEST_PIN_MISMATCH");
        if(contract.masks.Length!=source.Length||contract.masks.Any(row=>row==null||String.IsNullOrEmpty(row.sourceId))||
            contract.masks.Select(row=>row.sourceId).Distinct(StringComparer.Ordinal).Count()!=contract.masks.Length||
            !new HashSet<string>(contract.masks.Select(row=>row.sourceId),StringComparer.Ordinal).SetEquals(source))
            throw new InvalidOperationException("STATIC_MASK_COMPONENT_IDENTITY_DENOMINATOR_MISMATCH");
        if(legacy) {
            if(contract.schemaVersion!=1||!String.IsNullOrEmpty(contract.contract))
                throw new InvalidOperationException("STATIC_MASK_LEGACY_CONTRACT_INVALID");
            if(contract.masks.Any(row=>!String.IsNullOrEmpty(row.sourceMaterialResolution)))
                throw new InvalidOperationException("STATIC_MASK_LEGACY_DEFAULT_MATERIAL_UNPROVEN");
            return;
        }
        if(contract.schemaVersion!=1||contract.contract!=StaticMaskContractName||
            contract.sourceProfile!=StaticMaskSourceProfile||contract.sourceVersion!=StaticMaskSourceVersion||
            contract.sourceEngine==null||contract.sourceEngine.path!=StaticMaskSourceEnginePath||
            contract.sourceEngine.sha256!=StaticMaskSourceEngineSha256||contract.sourceEngine.url!=StaticMaskSourceEngineUrl)
            throw new InvalidOperationException("STATIC_MASK_SOURCE_DEFAULTS_PIN_MISMATCH");
        var expected=plan.components.Where(c=>c!=null&&c.type=="cc.Mask").ToDictionary(c=>c.sourceId,StringComparer.Ordinal);
        var actual=contract.masks;
        if(actual.Length!=expected.Count||actual.Any(m=>m==null||String.IsNullOrEmpty(m.sourceId))||
            actual.Select(m=>m.sourceId).Distinct(StringComparer.Ordinal).Count()!=actual.Length||
            !new HashSet<string>(actual.Select(m=>m.sourceId),StringComparer.Ordinal).SetEquals(expected.Keys))
            throw new InvalidOperationException("STATIC_MASK_COMPONENT_IDENTITY_DENOMINATOR_MISMATCH");
        var defaultsByField=new Dictionary<string,HashSet<string>>(StringComparer.Ordinal)
        {
            {"maskType",new HashSet<string>(StringComparer.Ordinal)},
            {"inverted",new HashSet<string>(StringComparer.Ordinal)},
            {"alphaThreshold",new HashSet<string>(StringComparer.Ordinal)}
        };
        var queueEvents=new Dictionary<string,List<ProxyMaskSpec>>(StringComparer.Ordinal);
        foreach(var queue in plan.staticSortQueue??Array.Empty<ProxyQueueSpec>())
        foreach(var eventRow in queue==null?Array.Empty<ProxyMaskSpec>():queue.masks??Array.Empty<ProxyMaskSpec>())
        {
            if(eventRow==null||String.IsNullOrEmpty(eventRow.sourceId))
                throw new InvalidOperationException("STATIC_MASK_QUEUE_EVENT_INVALID");
            if(!queueEvents.TryGetValue(eventRow.sourceId,out var list))queueEvents[eventRow.sourceId]=list=new List<ProxyMaskSpec>();
            list.Add(eventRow);
        }
        foreach(var mask in actual)
        {
            var component=expected[mask.sourceId];
            if(!String.IsNullOrEmpty(mask.sourceMaterialResolution)&&
                (mask.sourceMaterialResolution!="engine-default-builtin"||mask.sourceMaterialResolverPath!=StaticMaskSourceEnginePath||
                mask.sourceMaterialResolverSha256!=StaticMaskSourceEngineSha256||String.IsNullOrEmpty(mask.sourceMaterialId)||String.IsNullOrEmpty(mask.sourceEffectId)))
                throw new InvalidOperationException("STATIC_MASK_DEFAULT_MATERIAL_PROOF_INVALID: "+mask.sourceId);
            var effectiveActive=StaticMaskSourceActivity(plan,mask.node,out var sourceActiveSelf);
            if(mask.sourceOriginId==null||mask.node!=component.node||mask.nativeId!=component.nativeId||
                mask.enabled!=component.enabled||mask.maskType!=component.maskType||mask.inverted!=component.inverted||
                String.IsNullOrEmpty(mask.sourceFieldsJson)||String.IsNullOrEmpty(mask.sourceQueueDisposition)||
                mask.sourceActiveSelf!=sourceActiveSelf||mask.sourceActive!=effectiveActive||
                mask.maskType<0||mask.maskType>2||Single.IsNaN(mask.alphaThreshold)||Single.IsInfinity(mask.alphaThreshold)||
                mask.alphaThreshold<0||mask.alphaThreshold>1)
                throw new InvalidOperationException("STATIC_MASK_COMPONENT_FIELDS_MISMATCH: "+mask.sourceId);
            var queueRows=queueEvents.TryGetValue(mask.sourceId,out var rowsForId)?rowsForId:new List<ProxyMaskSpec>();
            var shouldHaveEvent=mask.sourceQueueDisposition=="active-mask-barrier-event";
            if(queueRows.Count!=(shouldHaveEvent?1:0)||
                queueRows.Any(row=>row.node!=mask.node||row.nativeId!=mask.nativeId||row.maskType!=mask.maskType||
                    row.enabled!=mask.enabled||row.inverted!=mask.inverted||Math.Abs(row.alphaThreshold-mask.alphaThreshold)>.000001f)||
                shouldHaveEvent&&(!mask.sourceActive||!mask.enabled)||
                mask.sourceQueueDisposition=="outside-active-render-flow-inactive-ancestor"&&mask.sourceActive||
                mask.sourceQueueDisposition=="outside-active-render-flow-disabled-mask"&&(!mask.sourceActive||mask.enabled))
                throw new InvalidOperationException("STATIC_MASK_QUEUE_EVENT_DENOMINATOR_MISMATCH: "+mask.sourceId);
            var defaultFields=mask.sourceDefaultFields??Array.Empty<string>();
            if(defaultFields.Distinct(StringComparer.Ordinal).Count()!=defaultFields.Length)
                throw new InvalidOperationException("STATIC_MASK_SOURCE_DEFAULT_FIELD_DUPLICATE: "+mask.sourceId);
            foreach(var field in defaultFields)
            {
                if(!defaultsByField.ContainsKey(field))throw new InvalidOperationException("STATIC_MASK_SOURCE_DEFAULT_FIELD_UNKNOWN: "+mask.sourceId+":"+field);
                defaultsByField[field].Add(mask.sourceId);
            }
            if(mask.sourceQueueDisposition!="active-mask-barrier-event"&&
                mask.sourceQueueDisposition!="outside-active-render-flow-inactive-ancestor"&&
                mask.sourceQueueDisposition!="outside-active-render-flow-disabled-mask"&&
                mask.sourceQueueDisposition!="outside-static-sort-queue-scope")
                throw new InvalidOperationException("STATIC_MASK_QUEUE_DISPOSITION_INVALID: "+mask.sourceId);
        }
        var observedDefaults=new Dictionary<string,HashSet<string>>(StringComparer.Ordinal);
        foreach(var row in contract.sourceDefaults??Array.Empty<StaticMaskSourceDefault>())
        {
            if(row==null||!defaultsByField.ContainsKey(row.field)||observedDefaults.ContainsKey(row.field)||row.sourceIds==null||
                row.sourceIds.Any(String.IsNullOrEmpty)||row.sourceIds.Distinct(StringComparer.Ordinal).Count()!=row.sourceIds.Length)
                throw new InvalidOperationException("STATIC_MASK_SOURCE_DEFAULT_EVIDENCE_INVALID");
            var expectedProperty=row.field=="maskType"?"_type":row.field;
            var expectedValue=row.field=="maskType"?"0":row.field=="inverted"?"false":"0.1";
            if(row.sourceProperty!=expectedProperty||row.value!=expectedValue)
                throw new InvalidOperationException("STATIC_MASK_SOURCE_DEFAULT_VALUE_MISMATCH: "+row.field);
            observedDefaults[row.field]=new HashSet<string>(row.sourceIds,StringComparer.Ordinal);
        }
        foreach(var field in defaultsByField.Keys)
        {
            var expectedIds=defaultsByField[field];
            if(expectedIds.Count==0)
            {
                if(observedDefaults.ContainsKey(field))throw new InvalidOperationException("STATIC_MASK_SOURCE_DEFAULT_SCOPE_EXTRA: "+field);
            }
            else if(!observedDefaults.TryGetValue(field,out var actualIds)||!actualIds.SetEquals(expectedIds))
                throw new InvalidOperationException("STATIC_MASK_SOURCE_DEFAULT_SCOPE_MISMATCH: "+field);
        }
    }

    static Sprite ResolveStaticMaskSprite(string uuid,Plan plan,Dictionary<string,Sprite> sprites)
    {
        if(String.IsNullOrEmpty(uuid))return null;
        var ids=plan.textures.Where(t=>t.id.EndsWith(":"+uuid,StringComparison.Ordinal)).Select(t=>t.id).Distinct().ToArray();
        if(ids.Length!=1||!sprites.TryGetValue(ids[0],out var sprite))throw new InvalidOperationException("STATIC_MASK_FRAME_IDENTITY_AMBIGUOUS: "+uuid);
        return sprite;
    }
    static Material CreateStaticMaskMaterial(MaskSpec spec)
    {
        if(String.IsNullOrEmpty(spec.unityMaskMaterialPath)||!spec.unityMaskMaterialPath.StartsWith("Assets/Game/Content/Materials/StaticMasks/")||spec.unityMaskMaterialPath.Contains(".."))
            throw new InvalidOperationException("STATIC_MASK_MATERIAL_PATH_INVALID");
        var existing=AssetDatabase.LoadAssetAtPath<Material>(spec.unityMaskMaterialPath);
        if(existing!=null)return existing;
        var shader=AssetDatabase.LoadAssetAtPath<Shader>(spec.unityMaskShaderPath);
        if(shader==null)throw new InvalidOperationException("STATIC_MASK_SHADER_MISSING");
        Directory.CreateDirectory(Path.GetDirectoryName(spec.unityMaskMaterialPath));
        var material=new Material(shader);material.SetFloat("_AlphaThreshold",spec.alphaThreshold);
        File.WriteAllText(spec.unityMaskMaterialPath+".meta","fileFormatVersion: 2\nguid: "+spec.unityMaskMaterialGuid+"\n");
        InternalEditorUtility.SaveToSerializedFileAndForget(new UnityEngine.Object[]{material},spec.unityMaskMaterialPath,true);
        UnityEngine.Object.DestroyImmediate(material);
        AssetDatabase.ImportAsset(spec.unityMaskMaterialPath,ImportAssetOptions.ForceSynchronousImport);
        return AssetDatabase.LoadAssetAtPath<Material>(spec.unityMaskMaterialPath);
    }
    static void CreateStaticMasks(Plan plan,Dictionary<string,GameObject> nodes,Dictionary<string,Sprite> sprites)
    {
        ValidateStaticMaskContract(plan);
        if(!HasStaticMasks(plan))return;
        ApplyStaticMasks(plan,plan.staticMasks.masks,nodes,sprites);
    }
    static partial void RefreshOptionalStaticMasksForPrefab(Plan plan,SourcePrefabSpec prefab,Dictionary<string,GameObject> nodes,Dictionary<string,Sprite> sprites)
    {
        CreateStaticMasksForPrefab(plan,prefab,nodes,sprites);
    }
    static void CreateStaticMasksForPrefab(Plan plan,SourcePrefabSpec prefab,Dictionary<string,GameObject> nodes,Dictionary<string,Sprite> sprites)
    {
        ValidateStaticMaskContract(plan);
        if(!HasStaticMasks(plan))return;
        if(prefab==null)throw new InvalidOperationException("STATIC_MASK_PREFAB_SCOPE_INVALID");
        var scope=new HashSet<string>(prefab.nodes??Array.Empty<string>(),StringComparer.Ordinal);
        if(!String.IsNullOrEmpty(prefab.root))scope.Add(prefab.root);
        var rows=plan.staticMasks.masks.Where(m=>m!=null&&scope.Contains(m.node)).ToArray();
        ApplyStaticMasks(plan,rows,nodes,sprites);
    }
    static void ApplyStaticMasks(Plan plan,MaskSpec[] specs,Dictionary<string,GameObject> nodes,Dictionary<string,Sprite> sprites)
    {
        foreach(var spec in specs??Array.Empty<MaskSpec>())
        {
            if(spec==null||!nodes.TryGetValue(spec.node,out var go)||go==null)
                throw new InvalidOperationException("STATIC_MASK_NODE_MISSING: "+(spec==null?"<null>":spec.sourceId));
            var mask=go.GetComponent<UnityEngine.UI.Mask>();
            var identity=go.GetComponent<NativeStaticMaskIdentity>();
            if(mask!=null)
            {
                if(identity==null||identity.nativeId!=spec.nativeId)
                    throw new InvalidOperationException("STATIC_MASK_EXISTING_IDENTITY_MISMATCH: "+spec.sourceId);
                if(identity.sourceId!=spec.sourceId)
                {
                    if(identity.sourceId!=spec.sourceOriginId)
                        throw new InvalidOperationException("STATIC_MASK_CLONE_ORIGIN_MISMATCH: "+spec.sourceId);
                    identity.sourceId=spec.sourceId;
                    identity.sourceFieldsJson=spec.sourceFieldsJson;identity.sourceMaskType=spec.maskType;
                    identity.sourceInverted=spec.inverted;identity.sourceAlphaThreshold=spec.alphaThreshold;
                    identity.spriteFrameUuid=spec.spriteFrameUuid;identity.sourceMaterialId=spec.sourceMaterialId;
                    identity.resolvedSourceMaterialId=spec.resolvedSourceMaterialId;identity.sourceEffectId=spec.sourceEffectId;
                    identity.sourceEffectName=spec.sourceEffectName;identity.sourceEffectDocumentSha256=spec.sourceEffectDocumentSha256;
                    identity.sourceMaterialResolution=spec.sourceMaterialResolution;identity.sourceMaterialResolverPath=spec.sourceMaterialResolverPath;identity.sourceMaterialResolverSha256=spec.sourceMaterialResolverSha256;
                }
                if(!UnityStaticMaskSort.ReadStaticMask(spec,go,id=>ResolveStaticMaskSprite(id,plan,sprites)).verified)
                    throw new InvalidOperationException("STATIC_MASK_IDEMPOTENT_READBACK_FAILED: "+spec.sourceId);
                continue;
            }
            var rectMask=go.GetComponent<UnityEngine.UI.RectMask2D>();
            if(rectMask!=null)UnityEngine.Object.DestroyImmediate(rectMask);
            var rows=UnityStaticMaskSort.CreateStaticMasks(new[]{spec},nodes,
                id=>ResolveStaticMaskSprite(id,plan,sprites),CreateStaticMaskMaterial);
            if(rows.Length!=1||!rows[0].verified)
                throw new InvalidOperationException("STATIC_MASK_CREATE_READBACK_FAILED: "+spec.sourceId);
        }
    }
    static MaskReadback[] ReadStaticMasks(Plan plan,Dictionary<string,GameObject> loaded,Dictionary<string,GameObject> persistent,Dictionary<string,Sprite> sprites)
    {
        ValidateStaticMaskContract(plan);
        if(!HasStaticMasks(plan))return Array.Empty<MaskReadback>();
        return plan.staticMasks.masks.Where(s=>loaded.ContainsKey(s.node)).Select(spec=>{
            if(!persistent.TryGetValue(spec.node,out var savedNode)||savedNode==null)
                throw new InvalidOperationException("STATIC_MASK_PERSISTENT_NODE_MISSING: "+spec.sourceId);
            var saved=savedNode.GetComponent<NativeStaticMaskIdentity>();
            if(saved==null||!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(saved,out string guid,out long id)||String.IsNullOrEmpty(guid)||id==0)
                throw new InvalidOperationException("STATIC_MASK_PERSISTENT_IDENTITY_MISSING: "+spec.sourceId);
            var row=UnityStaticMaskSort.ReadStaticMask(spec,loaded[spec.node],sid=>ResolveStaticMaskSprite(sid,plan,sprites));
            if(!row.verified)throw new InvalidOperationException("STATIC_MASK_NATIVE_READBACK_FAILED: "+spec.sourceId);
            row.persistentIdentityGuid=guid;row.persistentIdentityLocalFileId=id;row.persistentIdentityVerified=true;
            if(plan.staticMasks.contract==StaticMaskContractName) {
                row.clipProbe=ProbeStaticMaskClipping(plan,spec,loaded[spec.node]);
                row.clipProbeVerified=row.clipProbe!=null&&row.clipProbe.verified;
            }
            return row;
        }).ToArray();
    }
}
