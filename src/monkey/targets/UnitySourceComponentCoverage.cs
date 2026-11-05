// Editor-only inventory of every planned source component, including gaps.
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static partial class MonkeyImporter
{
    // Actual component inventory on mapped saved nodes. Source IDs are joined
    // only after the independent logical component observations are available.
    [Serializable] public sealed class PhysicalComponentObservation {
        public string nativeType,componentUuid,guid,role,identityOrigin,auxiliaryKind,auxiliaryOwnerComponentUuid;
        public long localFileId;
        public bool persistent,enabledKnown,enabled;
        public string[] nativeBaseTypes,sourceComponentIds,identityPath;
    }
    static string PhysicalComponentUuid(UnityEngine.Object target,out string guid,out long local) {
        guid=null;local=0;
        return target!=null&&AssetDatabase.TryGetGUIDAndLocalFileIdentifier(target,out guid,out local)&&
            !String.IsNullOrEmpty(guid)&&local!=0?guid+":"+local:null;
    }
    static UnityEngine.Object SavedPhysicalComponentIdentity(Component component,SourceComponentCoverage[] sources,
        out string[] observedPath) {
        var expected=new HashSet<string>((sources??Array.Empty<SourceComponentCoverage>()).Where(row=>row!=null&&
            !String.IsNullOrEmpty(row.componentUuid)).Select(row=>row.componentUuid),StringComparer.Ordinal);
        var path=new List<string>();var seen=new HashSet<UnityEngine.Object>();UnityEngine.Object fallback=component;
        UnityEngine.Object current=component;
        for(int depth=0;current!=null&&depth<32&&seen.Add(current);depth++) {
            var uuid=PhysicalComponentUuid(current,out string ignoredGuid,out long ignoredLocal);
            if(!String.IsNullOrEmpty(uuid)) {
                path.Add(uuid);
                if(EditorUtility.IsPersistent(current)) {
                    if(!EditorUtility.IsPersistent(fallback))fallback=current;
                    if(expected.Contains(uuid)){observedPath=path.ToArray();return current;}
                }
            }
            current=PrefabUtility.GetCorrespondingObjectFromSource(current);
        }
        observedPath=path.ToArray();return fallback;
    }
    static PhysicalComponentObservation[] ReadPhysicalNodeComponents(GameObject node,SourceComponentCoverage[] sources) {
        return node.GetComponents<Component>().Select(component=>{
            if(component==null)return new PhysicalComponentObservation{nativeType="<missing-script>",role="unmapped",
                nativeBaseTypes=Array.Empty<string>(),sourceComponentIds=Array.Empty<string>(),identityPath=Array.Empty<string>()};
            var target=SavedPhysicalComponentIdentity(component,sources,out var path);
            var uuid=PhysicalComponentUuid(target,out string guid,out long local);
            var chain=new List<string>();for(var type=component.GetType();type!=null;type=type.BaseType)chain.Add(type.FullName);
            var behavior=component as Behaviour;
            var row=new PhysicalComponentObservation{nativeType=component.GetType().FullName,componentUuid=uuid,
                guid=guid,localFileId=local,persistent=target!=null&&EditorUtility.IsPersistent(target)&&!String.IsNullOrEmpty(uuid),
                enabledKnown=behavior!=null,enabled=behavior==null||behavior.enabled,nativeBaseTypes=chain.ToArray(),
                sourceComponentIds=Array.Empty<string>(),role="unmapped",identityPath=path,
                identityOrigin=target==component?"direct-observation":"corresponding-prefab-source"};
            // This is an observed engine reference, not an exemption by class
            // name. The consumer still verifies the owner Mask/source contract.
            var graphic=component as UnityEngine.UI.Graphic;
            if(graphic!=null) {
                var masks=node.GetComponents<UnityEngine.UI.Mask>().Where(mask=>mask!=null&&mask.graphic==graphic).ToArray();
                if(masks.Length==1) {
                    var owner=SavedPhysicalComponentIdentity(masks[0],sources,out var ownerPath);
                    row.auxiliaryKind="mask-stencil-graphic";
                    row.auxiliaryOwnerComponentUuid=PhysicalComponentUuid(owner,out string ownerGuid,out long ownerLocal);
                }
            }
            return row;
        }).ToArray();
    }
    static void BindPhysicalNodeComponents(NodeResult[] nodes,SourceComponentCoverage[] components) {
        foreach(var node in nodes??Array.Empty<NodeResult>()) {
            foreach(var physical in node.physicalComponents??Array.Empty<PhysicalComponentObservation>()) {
                physical.sourceComponentIds=(components??Array.Empty<SourceComponentCoverage>()).Where(source=>source!=null&&
                    source.node==node.sourceId&&!String.IsNullOrEmpty(physical.componentUuid)&&source.componentUuid==physical.componentUuid)
                    .Select(source=>source.sourceId).Distinct(StringComparer.Ordinal).OrderBy(id=>id,StringComparer.Ordinal).ToArray();
                physical.role=physical.sourceComponentIds.Length>0?"source-components":
                    physical.auxiliaryKind=="mask-stencil-graphic"&&!String.IsNullOrEmpty(physical.auxiliaryOwnerComponentUuid)?"engine-auxiliary":"unmapped";
            }
        }
    }
    [Serializable] public sealed class SavedScrollStaticObservation {
        public int schemaVersion=1;
        public string contract="monkey-unity-saved-scroll-static/1",phase="persistent-saved-prefab";
        public string sourceId,node,guid,contentNode,viewportNode,contentGuid,viewportGuid;
        public long localFileId,contentLocalFileId,viewportLocalFileId;
        public bool horizontal,vertical,contentPersistent,viewportPersistent;
    }
    static SavedScrollStaticObservation ReadSavedScrollStaticFields(Plan plan,ComponentSpec source,
        UnityEngine.UI.ScrollRect scroll,Dictionary<string,GameObject> nodes) {
        if(source.type!="cc.ScrollView"||scroll==null)return null;
        PhysicalComponentUuid(scroll,out string guid,out long local);
        var content=scroll.content;var viewport=scroll.viewport;
        var contentUuid=PhysicalComponentUuid(content,out string contentGuid,out long contentLocal);
        var viewportUuid=PhysicalComponentUuid(viewport,out string viewportGuid,out long viewportLocal);
        var contentIds=nodes.Where(pair=>pair.Value!=null&&pair.Value.transform==content).Select(pair=>pair.Key).ToArray();
        var viewportIds=nodes.Where(pair=>pair.Value!=null&&pair.Value.transform==viewport).Select(pair=>pair.Key).ToArray();
        return new SavedScrollStaticObservation{sourceId=source.sourceId,node=source.node,guid=guid,localFileId=local,
            phase=EditorUtility.IsPersistent(scroll)?"persistent-saved-prefab":"unverified-transient-object",
            horizontal=scroll.horizontal,vertical=scroll.vertical,
            contentNode=contentIds.Length==1?contentIds[0]:null,viewportNode=viewportIds.Length==1?viewportIds[0]:null,
            contentGuid=contentGuid,contentLocalFileId=contentLocal,viewportGuid=viewportGuid,viewportLocalFileId=viewportLocal,
            contentPersistent=content!=null&&EditorUtility.IsPersistent(content)&&!String.IsNullOrEmpty(contentUuid),
            viewportPersistent=viewport!=null&&EditorUtility.IsPersistent(viewport)&&!String.IsNullOrEmpty(viewportUuid)};
    }
    [Serializable] public sealed class SourceComponentCoverage {
        public string sourceId,node,type,nativeType,componentUuid,status,representation,guid,disabledReason,nativeSlotId;
        public long localFileId;
        public string[] nativeBaseTypes;
        public bool sourceIdentityVerified,persistent,sourceEnabled,nativeEnabled,sourceVisible,nativeStaticFieldsVerified;
        public SavedScrollStaticObservation staticScrollFields;
    }
    [Serializable] public sealed class SourceComponentPresentation {
        public string sourceId,reason;public bool sourceVisible,verified,rendered;
    }
    [Serializable] public sealed class SourcePresentationCoverage {
        public string status;public SourceComponentPresentation[] components;
    }
    static readonly HashSet<string> SourceVisualComponentTypes=new HashSet<string>{
        "cc.Sprite","cc.Label","cc.RichText","cc.LabelOutline","sp.Skeleton","cc.Graphics","cc.ParticleSystem","cc.MotionStreak","cc.TiledMap"};
    static readonly HashSet<string> SourceNonVisualComponentTypes=new HashSet<string>{
        "cc.Widget","cc.Layout","cc.Button","cc.Toggle","cc.ToggleContainer","cc.ScrollView","cc.Mask",
        "cc.LabelOutline","cc.LabelShadow","cc.SortRoot","cc.SortOrder","cc.Animation","cc.BlockInputEvents",
        "cc.ProgressBar","cc.EditBox","cc.Canvas"};
    static bool SourceOutlineOwnerLabelDisabled(Plan plan,ComponentSpec component) {
        if(component.type!="cc.LabelOutline")return false;
        var labels=plan.components.Where(source=>source.type=="cc.Label"&&source.node==component.node).ToArray();
        return labels.Length==1&&!labels[0].enabled;
    }
    static bool SourceNodeVisible(Plan plan,ComponentSpec component) {
        var nodes=plan.nodes.ToDictionary(x=>x.sourceId);var id=component.node;var seen=new HashSet<string>();
        if(!component.enabled)return false;
        if(SourceOutlineOwnerLabelDisabled(plan,component))return false;
        while(!String.IsNullOrEmpty(id)) {
            if(!seen.Add(id)||!nodes.TryGetValue(id,out var node))throw new InvalidOperationException("SOURCE_VISIBILITY_NODE_INVALID: "+id);
            if(!node.active||node.opacity<=0)return false;
            id=node.parent;
        }
        return true;
    }
    static SourceComponentCoverage[] ReadSourceComponentCoverage(Plan plan,Dictionary<string,GameObject> nodes,ISet<string> referenceFailures) {
        var completedLayoutSources=new HashSet<string>(ReadStaticLayoutCompletion(plan,nodes)
            .SelectMany(node=>(node.layouts??Array.Empty<StaticLayoutComponentReadback>()).Select(slot=>slot.sourceComponentId)
                .Concat((node.widgets??Array.Empty<StaticWidgetComponentReadback>()).Select(slot=>slot.sourceComponentId))),StringComparer.Ordinal);
        return plan.components.Where(x=>nodes.ContainsKey(x.node)).Select(source=>{
            var target=StaticReference(plan,nodes,source.sourceId);var component=target as Component;
            string guid=null;long local=0;bool persistent=target!=null&&AssetDatabase.TryGetGUIDAndLocalFileIdentifier(target,out guid,out local)&&!String.IsNullOrEmpty(guid)&&local!=0;
            var behavior=component as Behaviour;bool enabled=behavior==null||behavior.enabled;
            bool completedLayout=completedLayoutSources.Contains(source.sourceId)&&target is NativeStaticLayoutCompletion;
            if(completedLayout)enabled=enabled&&source.enabled;
            var chain=new List<string>();for(var current=target==null?null:target.GetType();current!=null;current=current.BaseType)chain.Add(current.FullName);
            bool retained=source.staticFieldBinding!=null&&!String.IsNullOrEmpty(source.staticFieldBinding.typeName)||
                source.type=="cc.ProgressBar"&&source.staticProgressBinding!=null&&!source.convertible||
                source.type=="cc.Animation"&&(plan.staticAnimationBindingsEnabled||plan.staticCompletionEnabled)||
                source.type=="sp.Skeleton"&&!String.IsNullOrEmpty(plan.staticSpineContinuationJson);
            string status=target==null?(source.convertible?"missing":"unsupported"):retained?"retained":!enabled?"disabled":"native";
            bool emptySprite=source.type=="cc.Sprite"&&String.IsNullOrEmpty(source.spriteFrame)&&target is UnityEngine.UI.Image image&&image.sprite==null;
            string disabledReason=enabled?null:!source.enabled?"source-disabled":SourceOutlineOwnerLabelDisabled(plan,source)?"owning-label-disabled":emptySprite?"source-empty-sprite":source.type=="cc.Button"&&source.staticButtonBinding!=null&&source.staticButtonBinding.renderReady?"static-button-business-safety":"unproven-native-disabled";
            return new SourceComponentCoverage{sourceId=source.sourceId,node=source.node,type=source.type,nativeType=target==null?null:target.GetType().FullName,
                nativeSlotId=completedLayout?source.sourceId:null,
                componentUuid=persistent?guid+":"+local:null,nativeBaseTypes=chain.ToArray(),guid=guid,localFileId=local,persistent=persistent,sourceIdentityVerified=persistent,
                staticScrollFields=ReadSavedScrollStaticFields(plan,source,target as UnityEngine.UI.ScrollRect,nodes),
                sourceEnabled=source.enabled,nativeEnabled=target!=null&&enabled,sourceVisible=SourceNodeVisible(plan,source)&&!emptySprite,status=status,
                disabledReason=disabledReason,nativeStaticFieldsVerified=persistent&&(source.convertible||completedLayout)&&referenceFailures!=null&&!referenceFailures.Contains(source.sourceId),
                representation=retained?"disabled-source-data-carrier":target==null?"no-verified-native-counterpart":completedLayout?"native-component-slot":"native-component"};
        }).ToArray();
    }
    static SourcePresentationCoverage ReadSourcePresentationCoverage(Plan plan,SourceComponentCoverage[] rows) {
        var components=rows.Select(row=>{
            bool visual=SourceVisualComponentTypes.Contains(row.type),known=visual||SourceNonVisualComponentTypes.Contains(row.type);
            bool visible=visual&&row.sourceVisible;
            // A retained visual source is never reported as rendered. Unknown
            // custom behavior remains unproven rather than inferred nonvisual.
            bool rendered=visual&&row.status=="native"&&row.nativeEnabled&&row.persistent;
            bool verified=known&&row.sourceIdentityVerified&&row.status!="unsupported"&&row.status!="missing"&&(!visible||rendered);
            return new SourceComponentPresentation{sourceId=row.sourceId,sourceVisible=visible,rendered=rendered,verified=verified,
                reason=!known?"source-static-role-unproven":visible&&!rendered?"visible-source-not-rendered":"native-presence-only;field-and-visual-checks-separate"};
        }).ToArray();
        return new SourcePresentationCoverage{status=components.All(x=>x.verified)?"pass":"partial",components=components};
    }
}
