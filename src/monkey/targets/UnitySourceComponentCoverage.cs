// Editor-only inventory of every planned source component, including gaps.
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static partial class MonkeyImporter
{
    [Serializable] public sealed class SourceComponentCoverage {
        public string sourceId,node,type,nativeType,componentUuid,status,representation,guid;
        public long localFileId;
        public string[] nativeBaseTypes;
        public bool sourceIdentityVerified,persistent,sourceEnabled,nativeEnabled,sourceVisible;
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
    static SourceComponentCoverage[] ReadSourceComponentCoverage(Plan plan,Dictionary<string,GameObject> nodes) {
        return plan.components.Where(x=>nodes.ContainsKey(x.node)).Select(source=>{
            var target=StaticReference(plan,nodes,source.sourceId);var component=target as Component;
            string guid=null;long local=0;bool persistent=target!=null&&AssetDatabase.TryGetGUIDAndLocalFileIdentifier(target,out guid,out local)&&!String.IsNullOrEmpty(guid)&&local!=0;
            var behavior=component as Behaviour;bool enabled=behavior==null||behavior.enabled;
            var chain=new List<string>();for(var current=target==null?null:target.GetType();current!=null;current=current.BaseType)chain.Add(current.FullName);
            bool retained=source.staticFieldBinding!=null&&!String.IsNullOrEmpty(source.staticFieldBinding.typeName)||
                source.type=="cc.Animation"&&(plan.staticAnimationBindingsEnabled||plan.staticCompletionEnabled)||
                source.type=="sp.Skeleton"&&!String.IsNullOrEmpty(plan.staticSpineContinuationJson);
            string status=target==null?(source.convertible?"missing":"unsupported"):retained?"retained":!enabled?"disabled":"native";
            return new SourceComponentCoverage{sourceId=source.sourceId,node=source.node,type=source.type,nativeType=target==null?null:target.GetType().FullName,
                componentUuid=persistent?guid+":"+local:null,nativeBaseTypes=chain.ToArray(),guid=guid,localFileId=local,persistent=persistent,sourceIdentityVerified=persistent,
                sourceEnabled=source.enabled,nativeEnabled=target!=null&&enabled,sourceVisible=SourceNodeVisible(plan,source),status=status,
                representation=retained?"disabled-source-data-carrier":target==null?"no-verified-native-counterpart":"native-component"};
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
