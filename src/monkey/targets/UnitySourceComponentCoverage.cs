// Editor-only inventory of every planned source component, including gaps.
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static partial class MonkeyImporter
{
    [Serializable] public sealed class SourceComponentCoverage {
        public string sourceId,node,type,nativeType,componentUuid,status,representation,guid,disabledReason,nativeSlotId;
        public long localFileId;
        public string[] nativeBaseTypes;
        public bool sourceIdentityVerified,persistent,sourceEnabled,nativeEnabled,sourceVisible,nativeStaticFieldsVerified;
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
    static bool SourceNodeVisible(Plan plan,ComponentSpec component) {
        var nodes=plan.nodes.ToDictionary(x=>x.sourceId);var id=component.node;var seen=new HashSet<string>();
        if(!component.enabled)return false;
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
            string disabledReason=enabled?null:!source.enabled?"source-disabled":emptySprite?"source-empty-sprite":source.type=="cc.Button"&&source.staticButtonBinding!=null&&source.staticButtonBinding.renderReady?"static-button-business-safety":"unproven-native-disabled";
            return new SourceComponentCoverage{sourceId=source.sourceId,node=source.node,type=source.type,nativeType=target==null?null:target.GetType().FullName,
                nativeSlotId=completedLayout?source.sourceId:null,
                componentUuid=persistent?guid+":"+local:null,nativeBaseTypes=chain.ToArray(),guid=guid,localFileId=local,persistent=persistent,sourceIdentityVerified=persistent,
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
