using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEngine;

// Editor-only adapter for source-exact static Spine records. It intentionally
// does not load the Spine runtime, decode pages, or create rendering objects.
public static partial class MonkeyImporter
{
    [Serializable] sealed class SpineEnvelope { public int schemaVersion; public string contract,sourceManifestSha256,sourceIrSha256,status; public SpineComponent[] components; public SpineData[] dataAssets; }
    [Serializable] sealed class SpineComponent
    {
        public string sourceComponentId,sourceTemplateComponentId,sourcePrefabId,sourceNodeId,sourceTemplateNodeId;
        public bool sourceComponentEnabled; public string sourceComponentEnabledStatus;
        public SpineDataReference sourceDataReference; public SpineField[] sourceFields;
        public string sourceFieldsJson,sourceFieldsSha256,sourceComponentEnvelopeJson,sourceComponentEnvelopeSha256;
        public string sourceNodeEnvelopeJson,sourceNodeEnvelopeSha256,sourceObjectReferencesJson,sourceObjectReferencesSha256;
        public SpineObjectReference[] sourceObjectReferences;
    }
    [Serializable] sealed class SpineDataReference { public string status,sourceDataAssetId,sourceUuid; public string[] fieldNames; }
    [Serializable] sealed class SpineField { public string name,status; public bool present,boolValue; public float numberValue; public string stringValue; }
    [Serializable] sealed class SpineObjectReference { public string fieldPath,sourceUuid,sourceAssetId,sourceAssetType,targetReferenceKind,resolutionStatus; }
    [Serializable] sealed class SpineData
    {
        public string sourceDataAssetId,sourceSpineVersion,sourceLogicalPath,sourceNativeSha256,sourceNativePath;
        public long sourceNativeBytes; public string sourceSkeletonTextAssetPath,sourceAtlasTextAssetPath,sourceAtlasSha256; public long sourceAtlasBytes;
        public SpinePage[] sourceAtlasPages; public string nativeStaticSpineDataAssetPath;
        public SpinePma sourcePma;
    }
    [Serializable] sealed class SpinePage { public string sourcePageName,sourceTextureSourceId,sourceTextureSha256,sourceTexturePath; public long sourceTextureBytes; }
    [Serializable] sealed class SpinePma { public string status; public bool[] knownValues; public bool valueKnown,boolValue; }
    [Serializable] sealed class SpineReadback
    {
        public int schemaVersion=1; public string contract="monkey-unity-static-spine-readback/1",sourceManifestSha256,sourceIrSha256,status="saved_static_references_verified";
        public SpineComponentReadback[] components;
    }
    [Serializable] sealed class SpineComponentReadback
    {
        public string sourceComponentId,sourceTemplateComponentId,sourceNodeId,sourceFieldsSha256,sourceComponentEnvelopeSha256;
        public bool savedComponent; public string persistedGuidStatus,persistedGuid; public long persistedLocalFileId;
        public string renderingStatus="not_rendered",dynamicBehaviorStatus="not_restored";
        public SpineReferenceReadback[] sourceObjectReferences;
        public string sourceDataAssetId,dataAssetGuidStatus,dataAssetGuid; public long dataAssetLocalFileId;
    }
    [Serializable] sealed class SpineReferenceReadback
    {
        public string fieldPath,sourceAssetId,sourceUuid,persistedGuid; public long persistedLocalFileId; public bool resolved;
    }

    static SpineEnvelope spineStaticEnvelope;
    static Plan spineStaticPlan;
    static readonly List<SpineComponentReadback> spineStaticReadback = new List<SpineComponentReadback>();
    static string SpineSha(string value) { using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(value??""))).Replace("-","").ToLowerInvariant(); }
    static string SpineBytesSha(byte[] value) { using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(value??Array.Empty<byte>())).Replace("-","").ToLowerInvariant(); }
    static SpineComponent SpineFind(string id) {
        if(spineStaticEnvelope==null)throw new InvalidOperationException("STATIC_SPINE_PLAN_MISSING");
        var rows=(spineStaticEnvelope.components??Array.Empty<SpineComponent>()).Where(x=>x.sourceComponentId==id||x.sourceTemplateComponentId==id).ToArray();
        if(rows.Length==0)return null;
        // Template and each sync instance can share a marker; source template
        // selection is deterministic and the requested row remains the identity.
        return rows.FirstOrDefault(x=>x.sourceComponentId==id)??rows.First();
    }
    static SpineComponent SpineFindExact(string id) {
        return spineStaticEnvelope==null?null:(spineStaticEnvelope.components??Array.Empty<SpineComponent>()).SingleOrDefault(x=>x.sourceComponentId==id);
    }
    static NativeStaticSpineReference SpineCarrier(SpineComponent row, Dictionary<string,GameObject> nodes) {
        if(row==null||nodes==null||!nodes.TryGetValue(row.sourceNodeId,out var node)||node==null)return null;
        var all=node.GetComponents<NativeStaticSpineReference>();
        return all.SingleOrDefault(x=>x!=null&&x.sourceComponentId==row.sourceTemplateComponentId);
    }
    static partial void PrepareStaticSpine(Plan plan, Dictionary<string,GameObject> nodes)
    {
        if(String.IsNullOrEmpty(plan.staticSpineContinuationJson))return;
        spineStaticPlan=plan;
        spineStaticEnvelope=JsonUtility.FromJson<SpineEnvelope>(plan.staticSpineContinuationJson);
        if(spineStaticEnvelope==null||spineStaticEnvelope.contract!="monkey-prefab-static-spine-continuation/1")throw new InvalidOperationException("STATIC_SPINE_PLAN_CONTRACT_INVALID");
        spineStaticReadback.Clear();
        foreach(var data in spineStaticEnvelope.dataAssets??Array.Empty<SpineData>()) {
            var skeleton=AssetDatabase.LoadAssetAtPath<TextAsset>(data.sourceSkeletonTextAssetPath);
            var atlas=AssetDatabase.LoadAssetAtPath<TextAsset>(data.sourceAtlasTextAssetPath);
            if(skeleton==null||atlas==null)throw new InvalidOperationException("STATIC_SPINE_SOURCE_TEXT_ASSET_MISSING: "+data.sourceDataAssetId);
            var path=data.nativeStaticSpineDataAssetPath;
            var asset=AssetDatabase.LoadAssetAtPath<NativeStaticSpineData>(path);
            if(asset==null) {
                asset=ScriptableObject.CreateInstance<NativeStaticSpineData>(); asset.name=Path.GetFileNameWithoutExtension(path);
                var directory=Path.GetDirectoryName(path); if(!Directory.Exists(directory))Directory.CreateDirectory(directory);
                AssetDatabase.CreateAsset(asset,path);
            }
            asset.sourceDataAssetId=data.sourceDataAssetId; asset.sourceLogicalPath=data.sourceLogicalPath; asset.sourceSpineVersion=data.sourceSpineVersion;
            asset.sourceNativeSha256=data.sourceNativeSha256; asset.sourceNativeBytes=data.sourceNativeBytes; asset.sourceSkeletonBytes=skeleton;
            asset.sourceAtlasSha256=data.sourceAtlasSha256; asset.sourceAtlasBytes=data.sourceAtlasBytes; asset.sourceAtlasText=atlas;
            var pages=data.sourceAtlasPages??Array.Empty<SpinePage>();
            asset.sourcePageIds=pages.Select(x=>x.sourceTextureSourceId).ToArray(); asset.sourcePageNames=pages.Select(x=>x.sourcePageName).ToArray();
            asset.sourcePageSha256=pages.Select(x=>x.sourceTextureSha256).ToArray(); asset.sourcePageBytes=pages.Select(x=>x.sourceTextureBytes).ToArray();
            asset.sourceAstcPageBytes=pages.Select(x=>AssetDatabase.LoadAssetAtPath<TextAsset>(x.sourceTexturePath)).ToArray();
            if(asset.sourceAstcPageBytes.Any(x=>x==null))throw new InvalidOperationException("STATIC_SPINE_OPAQUE_PAGE_TEXT_ASSET_MISSING: "+data.sourceDataAssetId);
            asset.sourcePremultipliedAlphaStatus=data.sourcePma==null?"unknown":data.sourcePma.status;
            asset.hasSourcePremultipliedAlpha=data.sourcePma!=null&&data.sourcePma.valueKnown;
            if(asset.hasSourcePremultipliedAlpha)asset.sourcePremultipliedAlpha=data.sourcePma.boolValue;
            asset.skeletonParsed=false; asset.atlasDecoded=false; asset.pagesDecoded=false; asset.nonRendering=true;
            EditorUtility.SetDirty(asset);
        }
        foreach(var row in spineStaticEnvelope.components??Array.Empty<SpineComponent>()) {
            if(row.sourceComponentId!=row.sourceTemplateComponentId)continue;
            if(!nodes.TryGetValue(row.sourceNodeId,out var node)||node==null)throw new InvalidOperationException("STATIC_SPINE_SOURCE_NODE_MISSING: "+row.sourceNodeId);
            var carriers=node.GetComponents<NativeStaticSpineReference>();
            var carrier=carriers.SingleOrDefault(x=>x!=null&&x.sourceComponentId==row.sourceTemplateComponentId);
            if(carrier==null)carrier=node.AddComponent<NativeStaticSpineReference>();
            carrier.sourceComponentId=row.sourceComponentId; carrier.sourceTemplateComponentId=row.sourceTemplateComponentId;
            carrier.sourcePrefabId=row.sourcePrefabId; carrier.sourceNodeId=row.sourceNodeId; carrier.sourceTemplateNodeId=row.sourceTemplateNodeId;
            carrier.sourceComponentEnabledKnown=row.sourceComponentEnabledStatus=="plan-source-value"; carrier.sourceComponentEnabled=row.sourceComponentEnabled;
            var data=(spineStaticEnvelope.dataAssets??Array.Empty<SpineData>()).SingleOrDefault(x=>x.sourceDataAssetId==row.sourceDataReference.sourceDataAssetId);
            carrier.sourceData=data==null?null:AssetDatabase.LoadAssetAtPath<NativeStaticSpineData>(data.nativeStaticSpineDataAssetPath);
            SpineAssignFields(carrier,row.sourceFields??Array.Empty<SpineField>());
            carrier.sourceFieldsJson=row.sourceFieldsJson; carrier.sourceFieldsSha256=row.sourceFieldsSha256;
            carrier.sourceComponentEnvelopeJson=row.sourceComponentEnvelopeJson; carrier.sourceComponentEnvelopeSha256=row.sourceComponentEnvelopeSha256;
            carrier.sourceNodeEnvelopeJson=row.sourceNodeEnvelopeJson; carrier.sourceNodeEnvelopeSha256=row.sourceNodeEnvelopeSha256;
            carrier.sourceObjectReferencesJson=row.sourceObjectReferencesJson; carrier.sourceObjectReferencesSha256=row.sourceObjectReferencesSha256;
            var refs=row.sourceObjectReferences??Array.Empty<SpineObjectReference>();
            carrier.sourceObjectReferencePaths=refs.Select(x=>x.fieldPath).ToArray(); carrier.sourceObjectReferenceIds=refs.Select(x=>x.sourceAssetId).ToArray();
            carrier.sourceObjectReferenceUuids=refs.Select(x=>x.sourceUuid).ToArray();
            carrier.sourceObjectReferences=refs.Select(x=>SpineResolveObject(plan,x)).ToArray();
            if(carrier.sourceObjectReferences.Where((x,i)=>refs[i].sourceAssetId!=null).Any(x=>x==null))throw new InvalidOperationException("STATIC_SPINE_SOURCE_OBJECT_REFERENCE_UNRESOLVED: "+row.sourceComponentId);
            carrier.sourceMaterials=refs.Where(x=>x.targetReferenceKind=="retained-source-material").Select(x=>{
                var value=UnityStaticRetainedAssets.Resolve(plan.staticRetainedAssets,x.sourceAssetId) as NativeRetainedMaterial;
                if(value==null||!value.retentionOnly||value.renderingRecovered)throw new InvalidOperationException("STATIC_SPINE_RETAINED_MATERIAL_INVALID: "+x.sourceAssetId);
                return value;
            }).ToArray();
            carrier.nonRendering=true; carrier.dynamicBehaviorRestored=false; carrier.enabled=false;
            EditorUtility.SetDirty(carrier);
        }
    }
    static void SpineAssignFields(NativeStaticSpineReference carrier, SpineField[] fields) {
        foreach(var f in fields) {
            switch(f.name) {
                case "defaultSkin": if(f.present){carrier.hasDefaultSkin=true;carrier.defaultSkin=f.stringValue;} break;
                case "_skinName": if(f.present){carrier.hasSkinName=true;carrier.skinName=f.stringValue;} break;
                case "defaultAnimation":if(f.present){carrier.hasDefaultAnimation=true;carrier.defaultAnimation=f.stringValue;}break;
                case "_animationName":if(f.present){carrier.hasAnimationName=true;carrier.animationName=f.stringValue;}break;
                case "loop":if(f.present){carrier.hasLoop=true;carrier.loop=f.boolValue;}break;
                case "_playTimes":if(f.present){carrier.hasPlayTimes=true;carrier.playTimes=f.numberValue;}break;
                case "timeScale":if(f.present){carrier.hasTimeScale=true;carrier.timeScale=f.numberValue;}break;
                case "premultipliedAlpha":if(f.present){carrier.hasPremultipliedAlpha=true;carrier.premultipliedAlpha=f.boolValue;}break;
                case "useTint":if(f.present){carrier.hasUseTint=true;carrier.useTint=f.boolValue;}break;
                case "debugSlots":if(f.present){carrier.hasDebugSlots=true;carrier.debugSlots=f.boolValue;}break;
                case "debugBones":if(f.present){carrier.hasDebugBones=true;carrier.debugBones=f.boolValue;}break;
                case "debugMesh":if(f.present){carrier.hasDebugMesh=true;carrier.debugMesh=f.boolValue;}break;
                case "_preCacheMode":if(f.present){carrier.hasPreCacheMode=true;carrier.preCacheMode=(int)f.numberValue;}break;
                case "enableBatch":if(f.present){carrier.hasEnableBatch=true;carrier.enableBatch=f.boolValue;}break;
            }
        }
    }
    static UnityEngine.Object SpineResolveObject(Plan plan, SpineObjectReference reference) {
        if(reference==null||String.IsNullOrEmpty(reference.sourceAssetId))return null;
        if(reference.targetReferenceKind=="source-spine-data") {
            var data=(spineStaticEnvelope.dataAssets??Array.Empty<SpineData>()).SingleOrDefault(x=>x.sourceDataAssetId==reference.sourceAssetId);
            return data==null?null:AssetDatabase.LoadAssetAtPath<NativeStaticSpineData>(data.nativeStaticSpineDataAssetPath);
        }
        if(reference.targetReferenceKind=="retained-source-material")return UnityStaticRetainedAssets.Resolve((plan??spineStaticPlan).staticRetainedAssets,reference.sourceAssetId);
        return null;
    }
    static partial void ResolveStaticSpineReference(string id, Dictionary<string,GameObject> nodes, ref UnityEngine.Object value)
    {
        if(spineStaticEnvelope==null||String.IsNullOrEmpty(id))return;
        var row=SpineFindExact(id);
        if(row!=null) { value=SpineCarrier(row,nodes); return; }
        var data=(spineStaticEnvelope.dataAssets??Array.Empty<SpineData>()).SingleOrDefault(x=>x.sourceDataAssetId==id);
        if(data!=null) { value=AssetDatabase.LoadAssetAtPath<NativeStaticSpineData>(data.nativeStaticSpineDataAssetPath); return; }
        foreach(var component in spineStaticEnvelope.components??Array.Empty<SpineComponent>()) {
            var reference=(component.sourceObjectReferences??Array.Empty<SpineObjectReference>()).FirstOrDefault(x=>x.sourceAssetId==id);
            if(reference!=null) { value=SpineResolveObject(null,reference); return; }
        }
    }
    static partial void ReadSavedStaticSpine(Dictionary<string,GameObject> nodes,string prefabId)
    {
        if(spineStaticEnvelope==null)return;
        foreach(var row in (spineStaticEnvelope.components??Array.Empty<SpineComponent>()).Where(x=>x.sourcePrefabId==prefabId)) {
            var carrier=SpineCarrier(row,nodes); if(carrier==null)throw new InvalidOperationException("STATIC_SPINE_SAVED_CARRIER_MISSING: "+row.sourceComponentId);
            var persistent=PrefabUtility.GetCorrespondingObjectFromSource(carrier) as NativeStaticSpineReference;
            string guidValue=null; long localId=0;
            if(persistent!=null)AssetDatabase.TryGetGUIDAndLocalFileIdentifier(persistent,out guidValue,out localId);
            var typedFieldsMatch=SpineTypedFieldsMatch(carrier,row.sourceFields??Array.Empty<SpineField>())&&
                carrier.sourceComponentEnabledKnown==(row.sourceComponentEnabledStatus=="plan-source-value")&&
                (!carrier.sourceComponentEnabledKnown||carrier.sourceComponentEnabled==row.sourceComponentEnabled)&&
                carrier.sourceFieldsJson==row.sourceFieldsJson&&carrier.sourceFieldsSha256==row.sourceFieldsSha256&&
                carrier.sourceComponentEnvelopeJson==row.sourceComponentEnvelopeJson&&carrier.sourceComponentEnvelopeSha256==row.sourceComponentEnvelopeSha256&&
                carrier.sourceNodeEnvelopeJson==row.sourceNodeEnvelopeJson&&carrier.sourceNodeEnvelopeSha256==row.sourceNodeEnvelopeSha256&&
                SpineCarrierReferencesMatch(carrier,row);
            var result=new SpineComponentReadback { sourceComponentId=row.sourceComponentId,sourceTemplateComponentId=row.sourceTemplateComponentId,
                sourceNodeId=row.sourceNodeId,sourceFieldsSha256=SpineSha(carrier.sourceFieldsJson),sourceComponentEnvelopeSha256=SpineSha(carrier.sourceComponentEnvelopeJson),
                savedComponent=typedFieldsMatch,
                persistedGuidStatus=(!String.IsNullOrEmpty(guidValue)&&localId!=0)?"verified":"missing",persistedGuid=guidValue,persistedLocalFileId=localId,
                sourceDataAssetId=row.sourceDataReference.sourceDataAssetId };
            if(carrier.sourceData!=null)AssetDatabase.TryGetGUIDAndLocalFileIdentifier(carrier.sourceData,out result.dataAssetGuid,out result.dataAssetLocalFileId);
            var expectedData=(spineStaticEnvelope.dataAssets??Array.Empty<SpineData>()).SingleOrDefault(x=>x.sourceDataAssetId==row.sourceDataReference.sourceDataAssetId);
            var expectedDataObject=expectedData==null?null:AssetDatabase.LoadAssetAtPath<NativeStaticSpineData>(expectedData.nativeStaticSpineDataAssetPath);
            var dataBytesMatch=carrier.sourceData!=null&&carrier.sourceData==expectedDataObject&&expectedData!=null&&carrier.sourceData.sourceDataAssetId==expectedData.sourceDataAssetId&&
                carrier.sourceData.sourceLogicalPath==expectedData.sourceLogicalPath&&carrier.sourceData.sourceSpineVersion==expectedData.sourceSpineVersion&&
                carrier.sourceData.sourceNativeSha256==expectedData.sourceNativeSha256&&carrier.sourceData.sourceNativeBytes==expectedData.sourceNativeBytes&&
                carrier.sourceData.sourceAtlasSha256==expectedData.sourceAtlasSha256&&carrier.sourceData.sourceAtlasBytes==expectedData.sourceAtlasBytes&&
                carrier.sourceData.sourceSkeletonBytes!=null&&SpineBytesSha(carrier.sourceData.sourceSkeletonBytes.bytes)==expectedData.sourceNativeSha256&&
                carrier.sourceData.sourceAtlasText!=null&&SpineBytesSha(carrier.sourceData.sourceAtlasText.bytes)==expectedData.sourceAtlasSha256&&
                carrier.sourceData.sourceSkeletonBytes==AssetDatabase.LoadAssetAtPath<TextAsset>(expectedData.sourceSkeletonTextAssetPath)&&
                carrier.sourceData.sourceAtlasText==AssetDatabase.LoadAssetAtPath<TextAsset>(expectedData.sourceAtlasTextAssetPath)&&
                (carrier.sourceData.sourceAstcPageBytes??Array.Empty<TextAsset>()).Length==(expectedData.sourceAtlasPages??Array.Empty<SpinePage>()).Length;
            if(dataBytesMatch)for(int i=0;i<carrier.sourceData.sourceAstcPageBytes.Length;i++) {
                var expectedPage=expectedData.sourceAtlasPages[i];
                dataBytesMatch&=carrier.sourceData.sourceAstcPageBytes[i]==AssetDatabase.LoadAssetAtPath<TextAsset>(expectedPage.sourceTexturePath)&&
                    SpineBytesSha(carrier.sourceData.sourceAstcPageBytes[i].bytes)==expectedPage.sourceTextureSha256&&
                    carrier.sourceData.sourcePageIds[i]==expectedPage.sourceTextureSourceId&&carrier.sourceData.sourcePageNames[i]==expectedPage.sourcePageName&&
                    carrier.sourceData.sourcePageSha256[i]==expectedPage.sourceTextureSha256&&carrier.sourceData.sourcePageBytes[i]==expectedPage.sourceTextureBytes;
            }
            var pma=expectedData==null?null:expectedData.sourcePma;
            dataBytesMatch&=pma!=null&&carrier.sourceData.hasSourcePremultipliedAlpha==pma.valueKnown&&
                (!pma.valueKnown||carrier.sourceData.sourcePremultipliedAlpha==pma.boolValue)&&carrier.sourceData.sourcePremultipliedAlphaStatus==pma.status&&
                carrier.sourceData.nonRendering&&!carrier.sourceData.skeletonParsed&&!carrier.sourceData.atlasDecoded&&!carrier.sourceData.pagesDecoded;
            result.dataAssetGuidStatus=carrier.sourceData!=null&&!String.IsNullOrEmpty(result.dataAssetGuid)&&result.dataAssetLocalFileId!=0&&dataBytesMatch?"verified":"missing";
            var refs=row.sourceObjectReferences??Array.Empty<SpineObjectReference>();
            result.sourceObjectReferences=refs.Select((refRow,i)=>{
                var target=carrier.sourceObjectReferences!=null&&i<carrier.sourceObjectReferences.Length?carrier.sourceObjectReferences[i]:null;string targetGuid=null;long targetId=0;
                bool persisted=target!=null&&AssetDatabase.TryGetGUIDAndLocalFileIdentifier(target,out targetGuid,out targetId)&&!String.IsNullOrEmpty(targetGuid)&&targetId!=0;
                return new SpineReferenceReadback{fieldPath=refRow.fieldPath,sourceAssetId=refRow.sourceAssetId,sourceUuid=refRow.sourceUuid,persistedGuid=targetGuid,persistedLocalFileId=targetId,resolved=target!=null&&persisted};
            }).ToArray();
            spineStaticReadback.Add(result);
        }
        WriteStaticSpineReadback();
    }
    static bool SpineTypedFieldsMatch(NativeStaticSpineReference c,SpineField[] fields) {
        foreach(var f in fields) {
            bool present=false,boolean=false;float number=0;string text=null;
            switch(f.name) {
                case "defaultSkin":present=c.hasDefaultSkin;text=c.defaultSkin;break;
                case "_skinName":present=c.hasSkinName;text=c.skinName;break;
                case "defaultAnimation":present=c.hasDefaultAnimation;text=c.defaultAnimation;break;
                case "_animationName":present=c.hasAnimationName;text=c.animationName;break;
                case "loop":present=c.hasLoop;boolean=c.loop;break;
                case "_playTimes":present=c.hasPlayTimes;number=c.playTimes;break;
                case "timeScale":present=c.hasTimeScale;number=c.timeScale;break;
                case "premultipliedAlpha":present=c.hasPremultipliedAlpha;boolean=c.premultipliedAlpha;break;
                case "useTint":present=c.hasUseTint;boolean=c.useTint;break;
                case "debugSlots":present=c.hasDebugSlots;boolean=c.debugSlots;break;
                case "debugBones":present=c.hasDebugBones;boolean=c.debugBones;break;
                case "debugMesh":present=c.hasDebugMesh;boolean=c.debugMesh;break;
                case "_preCacheMode":present=c.hasPreCacheMode;number=c.preCacheMode;break;
                case "enableBatch":present=c.hasEnableBatch;boolean=c.enableBatch;break;
                default:continue;
            }
            if(present!=f.present)return false;
            if(!present)continue;
            if(f.name=="defaultSkin"||f.name=="_skinName"||f.name=="defaultAnimation"||f.name=="_animationName") {
                if((text??"")!=(f.stringValue??""))return false;
            } else if(f.name=="loop"||f.name=="premultipliedAlpha"||f.name=="useTint"||f.name=="debugSlots"||f.name=="debugBones"||f.name=="debugMesh"||f.name=="enableBatch") {
                if(boolean!=f.boolValue)return false;
            } else if(Math.Abs(number-f.numberValue)>.00001f)return false;
        }
        return c.nonRendering&&!c.dynamicBehaviorRestored&&!c.enabled;
    }
    static bool SpineCarrierReferencesMatch(NativeStaticSpineReference c,SpineComponent row) {
        var refs=row.sourceObjectReferences??Array.Empty<SpineObjectReference>();
        if(c.sourceObjectReferencesJson!=row.sourceObjectReferencesJson||c.sourceObjectReferencesSha256!=row.sourceObjectReferencesSha256||
            c.sourceObjectReferences==null||c.sourceObjectReferences.Length!=refs.Length||
            !SpineStringArrayEqual(c.sourceObjectReferencePaths,refs.Select(x=>x.fieldPath).ToArray())||
            !SpineStringArrayEqual(c.sourceObjectReferenceIds,refs.Select(x=>x.sourceAssetId).ToArray())||
            !SpineStringArrayEqual(c.sourceObjectReferenceUuids,refs.Select(x=>x.sourceUuid).ToArray()))return false;
        for(int i=0;i<refs.Length;i++)if(c.sourceObjectReferences[i]!=SpineResolveObject(spineStaticPlan,refs[i]))return false;
        var materials=refs.Where(x=>x.targetReferenceKind=="retained-source-material").ToArray();
        if(c.sourceMaterials==null||c.sourceMaterials.Length!=materials.Length)return false;
        for(int i=0;i<materials.Length;i++) {
            var expected=SpineResolveObject(spineStaticPlan,materials[i]) as NativeRetainedMaterial;
            if(expected==null||c.sourceMaterials[i]!=expected||!expected.retentionOnly||expected.renderingRecovered)return false;
        }
        return true;
    }
    static bool SpineStringArrayEqual(string[] a,string[] b) {
        return a!=null&&b!=null&&a.SequenceEqual(b,StringComparer.Ordinal);
    }
    static void WriteStaticSpineReadback() {
        var report=new SpineReadback {sourceManifestSha256=spineStaticEnvelope.sourceManifestSha256,sourceIrSha256=spineStaticEnvelope.sourceIrSha256,
            components=spineStaticReadback.ToArray()};
        report.status=report.components.All(x=>x.savedComponent&&x.persistedGuidStatus=="verified"&&x.dataAssetGuidStatus=="verified"&&x.sourceObjectReferences.All(y=>y.resolved))?
            "saved_static_references_verified":"saved_static_references_incomplete";
        var path=Path.Combine("Analysis","Readback","spine-static-continuation.json");
        Directory.CreateDirectory(Path.GetDirectoryName(path)); File.WriteAllText(path,JsonUtility.ToJson(report,true),new UTF8Encoding(false));
    }
}
