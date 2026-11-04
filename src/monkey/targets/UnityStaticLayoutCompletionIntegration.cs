using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

// Editor serialization bridge for the source-backed Layout/Widget completion DTO.
// The carrier itself is runtime-safe; this partial owns plan parsing and saved-asset readback.
public static partial class MonkeyImporter
{
    [Serializable] public sealed class StaticLayoutCompletionContract
    {
        public string schema, status, sourceManifestSha256;
        public StaticLayoutNodeSpec[] nodes;
        public bool dynamicBusinessImplemented, initialPoseUsedAsConstraintProof;
    }
    [Serializable] public sealed class StaticLayoutNodeSpec
    {
        public string sourceNodeId, status;
        public string[] componentSourceOrder;
        public StaticLayoutSlotSpec[] layouts;
        public StaticWidgetSlotSpec[] widgets;
        public string[] diagnostics;
        public bool initialPoseMustRemainUnchangedDuringPrefabSave, runtimeInitializationMustBeReadBackSeparately;
    }
    [Serializable] public sealed class StaticLayoutSlotSpec
    {
        public string sourceComponentId, sourceNodeId, sourceType, status, nativeAlgorithm, sourceCodeEvidence;
        public int componentOrder, layoutType, resize, startAxis, horizontalDirection, verticalDirection;
        public bool sourceEnabled, sourceEnabledKnown, affectedByScale, cellSizeFromSource, dynamicAlgorithmEnabled;
        public float[] spacingXY, padding, cellSize, sourceLayoutCacheSize;
        public bool sourceLayoutCacheSizeKnown;
        public string[] sourceFieldPresence, unknownSourceFields, sourceFieldMismatches, normalizedPlanMismatch;
    }
    [Serializable] public sealed class StaticWidgetSlotSpec
    {
        public string sourceComponentId, sourceNodeId, sourceType, targetSourceNodeId, status, nativeAlgorithm, sourceCodeEvidence;
        public int componentOrder, alignFlags, alignMode;
        public bool sourceEnabled, sourceEnabledKnown, targetUsesParentWhenNull, constraintEnabled;
        public float[] margins, center, sourceNodeScale, sourceOriginalSize;
        public bool[] absolute, centerAbsolute;
        public bool sourceOriginalWidthKnown, sourceOriginalHeightKnown;
        public string[] sourceFieldPresence, unknownSourceFields, sourceFieldMismatches;
    }
    [Serializable] public sealed class StaticLayoutFieldValues
    {
        public int layoutType, resize, startAxis, horizontalDirection, verticalDirection;
        public bool affectedByScale, sourceLayoutCacheSizeKnown;
        public float[] spacingXY, padding, cellSize, sourceLayoutCacheSize;
    }
    [Serializable] public sealed class StaticWidgetFieldValues
    {
        public int alignFlags, alignMode;
        public bool targetUsesParentWhenNull;
        public float[] margins, center, sourceOriginalSize;
        public bool[] absolute, centerAbsolute;
        public string targetSourceNodeId;
    }
    [Serializable] public sealed class StaticLayoutComponentReadback
    {
        public string sourceComponentId, carrierGuid, targetGuid;
        public string[] sourceFieldPresence, unknownSourceFields;
        public long carrierLocalFileId, targetLocalFileId;
        public int componentOrder;
        public bool sourceEnabled, nativeComponentPresent, savedReferenceVerified;
        public StaticLayoutFieldValues fieldValues;
    }
    [Serializable] public sealed class StaticWidgetComponentReadback
    {
        public string sourceComponentId, carrierGuid, targetGuid;
        public string[] sourceFieldPresence, unknownSourceFields;
        public long carrierLocalFileId, targetLocalFileId;
        public int componentOrder;
        public bool sourceEnabled, nativeComponentPresent, savedReferenceVerified;
        public StaticWidgetFieldValues fieldValues;
    }
    [Serializable] public sealed class StaticLayoutNodeReadback
    {
        public string sourceNodeId;
        public StaticLayoutComponentReadback[] layouts;
        public StaticWidgetComponentReadback[] widgets;
    }
    [Serializable] public sealed class StaticLayoutProbeInput
    {
        public string sourceNodeId;
        public float[] position, size;
        public bool activateHierarchy;
    }
    [Serializable] public sealed class StaticLayoutProbeGeometry
    {
        public string sourceNodeId, parentSourceNodeId;
        public string[] childrenSourceNodeIds;
        public bool activeSelf, activeInHierarchy;
        public float[] position, size, anchor, scale;
    }
    [Serializable] public sealed class StaticLayoutProbeNodeResult
    {
        public string sourceNodeId;
        public float[] beforePosition, beforeSize, inputPosition, inputSize, afterPosition, afterSize;
        public StaticLayoutProbeGeometry before, input, after;
    }
    [Serializable] public sealed class StaticLayoutProbeResult
    {
        public string phase, status;
        public bool disposableCloneRequired, persistentPrefabMutated, baselineInitialized, baselineIsConstraintProof;
        public string[] appliedSourceComponentIds;
        public StaticLayoutProbeComponentParticipation[] layoutParticipation;
        public StaticLayoutProbeNodeResult[] nodes;
    }
    [Serializable] public sealed class StaticLayoutProbeComponentParticipation
    {
        public string sourceComponentId, ownerSourceNodeId;
        public int layoutType;
        public bool algorithmInvoked;
        public string[] effectiveChildSourceNodeIds;
    }

    static float StaticLayoutAt(float[] values, int index, float fallback = 0f)
    {
        return values != null && values.Length > index ? values[index] : fallback;
    }
    static bool StaticLayoutAt(bool[] values, int index, bool fallback = false)
    {
        return values != null && values.Length > index ? values[index] : fallback;
    }
    static Vector2 StaticLayoutVec2(float[] values)
    {
        if (values == null || values.Length != 2) throw new InvalidOperationException("STATIC_LAYOUT_VECTOR2_INVALID");
        return new Vector2(values[0], values[1]);
    }
    static Vector4 StaticLayoutVec4(float[] values)
    {
        if (values == null || values.Length != 4) throw new InvalidOperationException("STATIC_LAYOUT_VECTOR4_INVALID");
        return new Vector4(values[0], values[1], values[2], values[3]);
    }
    static string[] StaticLayoutPresence(IEnumerable<string> values) => (values ?? Enumerable.Empty<string>()).ToArray();
    static bool StaticLayoutSameFloat(float a, float b) => Math.Abs(a - b) <= 0.0001f;
    static bool StaticLayoutSameFloats(float[] expected, float[] actual)
    {
        if (expected == null || actual == null) return expected == actual;
        return expected.Length == actual.Length && expected.Select((value,index) => StaticLayoutSameFloat(value,actual[index])).All(x => x);
    }
    static bool StaticLayoutSameStrings(string[] expected, string[] actual) =>
        (expected ?? Array.Empty<string>()).SequenceEqual(actual ?? Array.Empty<string>(), StringComparer.Ordinal);

    // Call after the ordinary hierarchy/components have been created and before saving
    // the prefab. This method only serializes configuration; it never invokes ApplyNow.
    static void CreateStaticLayoutCompletion(Plan plan, Dictionary<string, GameObject> nodes)
    {
        var contract = plan.layoutCompletion;
        if (contract == null || String.IsNullOrEmpty(contract.schema)) return;
        if (contract.schema != "monkey-prefab-static-layout-completion/1" || contract.nodes == null)
            throw new InvalidOperationException("STATIC_LAYOUT_CONTRACT_INVALID");
        foreach (var spec in contract.nodes)
        {
            if (spec == null || String.IsNullOrEmpty(spec.sourceNodeId) || !nodes.TryGetValue(spec.sourceNodeId, out var node) || node == null)
                continue; // Candidate prefabs can contain a strict source-node subset.
            if (spec.initialPoseMustRemainUnchangedDuringPrefabSave != true || spec.runtimeInitializationMustBeReadBackSeparately != true)
                throw new InvalidOperationException("STATIC_LAYOUT_POSE_PHASE_CONTRACT_INVALID: " + spec.sourceNodeId);
            var layouts = (spec.layouts ?? Array.Empty<StaticLayoutSlotSpec>()).OrderBy(x => x.componentOrder).Select(x =>
            {
                if (x.sourceType != "cc.Layout" || x.sourceNodeId != spec.sourceNodeId || String.IsNullOrEmpty(x.sourceComponentId))
                    throw new InvalidOperationException("STATIC_LAYOUT_SLOT_IDENTITY_INVALID: " + spec.sourceNodeId);
                return new NativeStaticLayoutCompletion.LayoutSlot
                {
                    sourceComponentId=x.sourceComponentId, componentOrder=x.componentOrder, sourceEnabled=x.sourceEnabled,
                    layoutType=x.layoutType, resize=x.resize, startAxis=x.startAxis,
                    horizontalDirection=x.horizontalDirection, verticalDirection=x.verticalDirection,
                    affectedByScale=x.affectedByScale, padding=StaticLayoutVec4(x.padding), spacingXY=StaticLayoutVec2(x.spacingXY),
                    cellSize=StaticLayoutVec2(x.cellSize), sourceLayoutCacheSize=x.sourceLayoutCacheSizeKnown ? StaticLayoutVec2(x.sourceLayoutCacheSize) : Vector2.zero,
                    hasSourceLayoutCacheSize=x.sourceLayoutCacheSizeKnown,
                    sourceFieldPresence=StaticLayoutPresence(x.sourceFieldPresence), unknownSourceFields=StaticLayoutPresence(x.unknownSourceFields),
                };
            }).ToArray();
            var widgets = spec.widgets ?? Array.Empty<StaticWidgetSlotSpec>();
            if (widgets.Length > 1) throw new InvalidOperationException("STATIC_LAYOUT_MULTIPLE_WIDGETS_ON_NODE: " + spec.sourceNodeId);
            NativeStaticLayoutCompletion.WidgetSlot widget = null;
            if (widgets.Length == 1)
            {
                var x = widgets[0];
                if (x.sourceType != "cc.Widget" || x.sourceNodeId != spec.sourceNodeId || String.IsNullOrEmpty(x.sourceComponentId))
                    throw new InvalidOperationException("STATIC_WIDGET_SLOT_IDENTITY_INVALID: " + spec.sourceNodeId);
                RectTransform target = null;
                if (!String.IsNullOrEmpty(x.targetSourceNodeId))
                {
                    if (!nodes.TryGetValue(x.targetSourceNodeId, out var targetNode) || targetNode == null)
                        throw new InvalidOperationException("STATIC_WIDGET_TARGET_NODE_MISSING: " + x.targetSourceNodeId);
                    target = targetNode.GetComponent<RectTransform>();
                    if (target == null) throw new InvalidOperationException("STATIC_WIDGET_TARGET_RECT_MISSING: " + x.targetSourceNodeId);
                }
                widget = new NativeStaticLayoutCompletion.WidgetSlot
                {
                    sourceComponentId=x.sourceComponentId, componentOrder=x.componentOrder, sourceEnabled=x.sourceEnabled,
                    alignFlags=x.alignFlags, alignMode=x.alignMode, margins=StaticLayoutVec4(x.margins),
                    absoluteMargins=new Vector4(StaticLayoutAt(x.absolute,0,true)?1:0,StaticLayoutAt(x.absolute,1,true)?1:0,
                        StaticLayoutAt(x.absolute,2,true)?1:0,StaticLayoutAt(x.absolute,3,true)?1:0),
                    center=StaticLayoutVec2(x.center), centerAbsolute=new Vector2(StaticLayoutAt(x.centerAbsolute,0,true)?1:0,StaticLayoutAt(x.centerAbsolute,1,true)?1:0),
                    target=target, targetSourceNodeId=String.IsNullOrEmpty(x.targetSourceNodeId)?String.Empty:x.targetSourceNodeId,
                    targetUsesParentWhenNull=x.targetUsesParentWhenNull,
                    sourceOriginalSize=new Vector2(StaticLayoutAt(x.sourceOriginalSize,0),StaticLayoutAt(x.sourceOriginalSize,1)),
                    hasSourceOriginalWidth=x.sourceOriginalWidthKnown, hasSourceOriginalHeight=x.sourceOriginalHeightKnown,
                    sourceFieldPresence=StaticLayoutPresence(x.sourceFieldPresence), unknownSourceFields=StaticLayoutPresence(x.unknownSourceFields),
                };
            }
            var carrier = node.GetComponent<NativeStaticLayoutCompletion>();
            if (carrier == null) carrier = node.AddComponent<NativeStaticLayoutCompletion>();
            carrier.Configure(spec.sourceNodeId, layouts, widget);
        }
    }

    // Read only persisted prefab objects. Missing source nodes are intentionally skipped
    // so each source-prefab result is checked against its own node subset.
    static StaticLayoutNodeReadback[] ReadStaticLayoutCompletion(Plan plan, Dictionary<string, GameObject> persistentNodes)
    {
        var contract = plan.layoutCompletion;
        if (contract == null) return Array.Empty<StaticLayoutNodeReadback>();
        return (contract.nodes ?? Array.Empty<StaticLayoutNodeSpec>()).Where(s => s != null && persistentNodes.ContainsKey(s.sourceNodeId))
            .OrderBy(s => s.sourceNodeId, StringComparer.Ordinal).Select(spec =>
            {
                var owner = persistentNodes[spec.sourceNodeId];
                var carrier = owner.GetComponent<NativeStaticLayoutCompletion>();
                if (carrier == null || carrier.sourceNodeId != spec.sourceNodeId || !EditorUtility.IsPersistent(carrier))
                    throw new InvalidOperationException("STATIC_LAYOUT_CARRIER_NOT_PERSISTENT: " + spec.sourceNodeId);
                string carrierGuid; long carrierId;
                if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(carrier, out carrierGuid, out carrierId) || carrierId == 0)
                    throw new InvalidOperationException("STATIC_LAYOUT_CARRIER_IDENTITY_MISSING: " + spec.sourceNodeId);
                var saved = carrier.Readback();
                var savedById = saved.ToDictionary(x => x.sourceComponentId, StringComparer.Ordinal);
                var layoutRows = (spec.layouts ?? Array.Empty<StaticLayoutSlotSpec>()).OrderBy(x => x.componentOrder)
                    .Select(x => ReadStaticLayoutSlot(x, savedById, carrierGuid, carrierId)).ToArray();
                var widgetRows = (spec.widgets ?? Array.Empty<StaticWidgetSlotSpec>()).OrderBy(x => x.componentOrder)
                    .Select(x => ReadStaticWidgetSlot(x, savedById, carrierGuid, carrierId, owner, persistentNodes)).ToArray();
                var order = layoutRows.Select(x => new { x.componentOrder, row=x.sourceComponentId })
                    .Concat(widgetRows.Select(x => new { x.componentOrder, row=x.sourceComponentId }))
                    .OrderBy(x => x.componentOrder).Select(x => x.row).ToArray();
                if (!order.SequenceEqual(spec.componentSourceOrder ?? Array.Empty<string>()))
                    throw new InvalidOperationException("STATIC_LAYOUT_SOURCE_COMPONENT_ORDER_DIFFERS: " + spec.sourceNodeId);
                return new StaticLayoutNodeReadback { sourceNodeId=spec.sourceNodeId, layouts=layoutRows, widgets=widgetRows };
            }).ToArray();
    }

    // Run only on a caller-owned disposable prefab instance. Inputs are applied after
    // the before snapshot; ApplyNow then executes the real native carrier algorithms.
    // The caller destroys the clone after it has compared this result with Python's oracle.
    static StaticLayoutProbeResult ProbeStaticLayoutCompletion(Plan plan,StaticLayoutCompletionContract contract,
        Dictionary<string, GameObject> disposableNodes, StaticLayoutProbeInput[] inputs)
    {
        if (contract == null || disposableNodes == null) throw new InvalidOperationException("STATIC_LAYOUT_PROBE_CONTRACT_OR_NODES_MISSING");
        var inputById = (inputs ?? Array.Empty<StaticLayoutProbeInput>()).ToDictionary(x => x.sourceNodeId, StringComparer.Ordinal);
        var nodeSpecs=(plan.nodes??Array.Empty<NodeSpec>()).ToDictionary(x=>x.sourceId,StringComparer.Ordinal);
        var reverse=disposableNodes.ToDictionary(x=>x.Value,x=>x.Key);
        if(inputById.Keys.Any(id=>!disposableNodes.ContainsKey(id)))throw new InvalidOperationException("STATIC_LAYOUT_PROBE_INPUT_NODE_OUTSIDE_SCOPE");
        foreach(var spec in contract.nodes??Array.Empty<StaticLayoutNodeSpec>())
        {
            if(!disposableNodes.TryGetValue(spec.sourceNodeId,out var owner)||owner==null)
                throw new InvalidOperationException("STATIC_LAYOUT_PROBE_SOURCE_NODE_MISSING: "+spec.sourceNodeId);
            for(var ancestor=owner.transform;ancestor!=null;ancestor=ancestor.parent)ancestor.gameObject.SetActive(true);
        }
        var probeRoot=disposableNodes.Values.FirstOrDefault(x=>x!=null);
        if(probeRoot!=null)SettleNativeLayout(probeRoot.transform.root.gameObject);
        var baselineCarriers=disposableNodes.Values.Where(x=>x!=null).Select(x=>x.GetComponent<NativeStaticLayoutCompletion>())
            .Where(x=>x!=null).OrderBy(x=>StaticLayoutTransformDepth(x.transform)).ToArray();
        foreach(var carrier in baselineCarriers)carrier.ApplyNow();
        var rows = new List<StaticLayoutProbeNodeResult>();
        foreach (var pair in disposableNodes.OrderBy(x => StaticLayoutTransformDepth(x.Value.transform)).ThenBy(x=>x.Key,StringComparer.Ordinal))
        {
            if (pair.Value == null) throw new InvalidOperationException("STATIC_LAYOUT_PROBE_NODE_NULL: " + pair.Key);
            if (EditorUtility.IsPersistent(pair.Value) || PrefabUtility.IsPartOfPrefabAsset(pair.Value))
                throw new InvalidOperationException("STATIC_LAYOUT_PROBE_REQUIRES_DISPOSABLE_INSTANCE: " + pair.Key);
            var rect = pair.Value.GetComponent<RectTransform>();
            if (rect == null) continue;
            var before=StaticLayoutCaptureGeometry(pair.Key,rect,nodeSpecs,reverse);
            if((contract.nodes??Array.Empty<StaticLayoutNodeSpec>()).Any(x=>x.sourceNodeId==pair.Key)&&!before.activeInHierarchy)
                throw new InvalidOperationException("STATIC_LAYOUT_PROBE_OWNER_NOT_ACTIVE_IN_HIERARCHY: "+pair.Key);
            rows.Add(new StaticLayoutProbeNodeResult { sourceNodeId=pair.Key,before=before,beforePosition=before.position,beforeSize=before.size });
        }
        foreach(var input in inputById.Values)
        {
            var rect=disposableNodes[input.sourceNodeId].GetComponent<RectTransform>();
            if(rect==null)throw new InvalidOperationException("STATIC_LAYOUT_PROBE_INPUT_RECT_MISSING: "+input.sourceNodeId);
            var before=rows.Single(x=>x.sourceNodeId==input.sourceNodeId).before;
            var position=input.position??before.position;
            var isContractOwner=(contract.nodes??Array.Empty<StaticLayoutNodeSpec>()).Any(x=>x.sourceNodeId==input.sourceNodeId);
            var size=input.size??(isContractOwner?new[]{before.size[0]+17f,before.size[1]+11f}:before.size);
            if (position.Length != 3 || size.Length != 2) throw new InvalidOperationException("STATIC_LAYOUT_PROBE_INPUT_GEOMETRY_INVALID: " + input.sourceNodeId);
            if(input.activateHierarchy)
                for(var ancestor=rect.transform;ancestor!=null;ancestor=ancestor.parent)ancestor.gameObject.SetActive(true);
            rect.localPosition=new Vector3(position[0],position[1],position[2]);
            rect.SetSizeWithCurrentAnchors(RectTransform.Axis.Horizontal,size[0]);
            rect.SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical,size[1]);
        }
        foreach(var row in rows){var rect=disposableNodes[row.sourceNodeId].GetComponent<RectTransform>();row.input=StaticLayoutCaptureGeometry(row.sourceNodeId,rect,nodeSpecs,reverse);row.inputPosition=row.input.position;row.inputSize=row.input.size;}
        foreach (var spec in contract.nodes ?? Array.Empty<StaticLayoutNodeSpec>())
            if (!disposableNodes.ContainsKey(spec.sourceNodeId)) throw new InvalidOperationException("STATIC_LAYOUT_PROBE_SOURCE_NODE_MISSING: " + spec.sourceNodeId);
        var carriers = disposableNodes.OrderBy(x=>StaticLayoutTransformDepth(x.Value.transform)).ThenBy(x=>x.Key,StringComparer.Ordinal)
            .Select(x=>x.Value).Where(x => x != null).Select(x => x.GetComponent<NativeStaticLayoutCompletion>())
            .Where(x => x != null).Distinct().ToArray();
        foreach (var pair in disposableNodes)
        {
            var carrier=pair.Value==null?null:pair.Value.GetComponent<NativeStaticLayoutCompletion>();
            if(carrier!=null&&carrier.sourceNodeId!=pair.Key)
                throw new InvalidOperationException("STATIC_LAYOUT_PROBE_CARRIER_NODE_ID_DIFFERS: "+pair.Key);
        }
        var participation=new List<StaticLayoutProbeComponentParticipation>();
        foreach(var pair in disposableNodes.OrderBy(x=>StaticLayoutTransformDepth(x.Value.transform)).ThenBy(x=>x.Key,StringComparer.Ordinal))
        {
            var carrier=pair.Value==null?null:pair.Value.GetComponent<NativeStaticLayoutCompletion>();
            if(carrier==null)continue;
            foreach(var slot in carrier.layouts.Where(x=>x!=null&&x.sourceEnabled))
            {
                var supported=slot.layoutType==0&&slot.resize==0||
                    (slot.layoutType==1||slot.layoutType==2)&&slot.resize>=0&&slot.resize<=2;
                var children=Enumerable.Range(0,pair.Value.transform.childCount).Select(pair.Value.transform.GetChild)
                    .OfType<RectTransform>().Where(x=>x.gameObject.activeInHierarchy&&!NativeStaticLayoutCompletion.IsIgnoredLayoutChild(x)&&reverse.ContainsKey(x.gameObject))
                    .Select(x=>reverse[x.gameObject]).ToArray();
                participation.Add(new StaticLayoutProbeComponentParticipation{sourceComponentId=slot.sourceComponentId,
                    ownerSourceNodeId=pair.Key,layoutType=slot.layoutType,algorithmInvoked=supported&&pair.Value.activeInHierarchy,
                    effectiveChildSourceNodeIds=children});
            }
        }
        foreach (var carrier in carriers) carrier.ApplyNow();
        var byId = rows.ToDictionary(x => x.sourceNodeId, StringComparer.Ordinal);
        foreach (var pair in disposableNodes)
        {
            if (!byId.TryGetValue(pair.Key,out var row)) continue;
            var rect=pair.Value.GetComponent<RectTransform>();
            row.after=StaticLayoutCaptureGeometry(pair.Key,rect,nodeSpecs,reverse);
            row.afterPosition=row.after.position;row.afterSize=row.after.size;
        }
        return new StaticLayoutProbeResult { phase="initialized-disposable-clone", status="probe_captured",
            disposableCloneRequired=true, persistentPrefabMutated=false,baselineInitialized=true,baselineIsConstraintProof=false,
            appliedSourceComponentIds=carriers.SelectMany(x => x.layouts.Where(s=>s.sourceEnabled).Select(s => s.sourceComponentId)
                .Concat(x.widget==null||!x.widget.sourceEnabled?Enumerable.Empty<string>():new[]{x.widget.sourceComponentId})).Distinct().OrderBy(x=>x,StringComparer.Ordinal).ToArray(),
            layoutParticipation=participation.ToArray(),
            nodes=rows.ToArray() };
    }

    static float[] StaticLayoutVec2Values(Vector2 value) => new[]{value.x,value.y};
    static float[] StaticLayoutVec3Values(Vector3 value) => new[]{value.x,value.y,value.z};
    static int StaticLayoutTransformDepth(Transform value){int depth=0;for(var p=value;p!=null;p=p.parent)depth++;return depth;}
    static GameObject StaticLayoutCreateInactiveProbeContext(GameObject contents,Plan plan)
    {
        var context=new GameObject("StaticLayoutProbeCanvas",typeof(RectTransform),typeof(Canvas));
        UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(context,contents.scene);
        var canvas=context.GetComponent<Canvas>();canvas.renderMode=RenderMode.WorldSpace;
        var rect=(RectTransform)context.transform;rect.pivot=Vector2.zero;
        rect.sizeDelta=new Vector2(plan.designSize[0],plan.designSize[1]);
        context.SetActive(false);
        contents.transform.SetParent(rect,false);
        return context;
    }
    static StaticLayoutProbeGeometry StaticLayoutCaptureGeometry(string sourceId,RectTransform rect,
        Dictionary<string,NodeSpec> specs,Dictionary<GameObject,string> reverse)
    {
        specs.TryGetValue(sourceId,out var spec);
        var parent=rect.parent!=null&&reverse.TryGetValue(rect.parent.gameObject,out var parentId)?parentId:spec!=null?spec.parent:null;
        var children=Enumerable.Range(0,rect.childCount).Select(i=>rect.GetChild(i).gameObject)
            .Where(reverse.ContainsKey).Select(child=>reverse[child]).ToArray();
        return new StaticLayoutProbeGeometry {sourceNodeId=sourceId,parentSourceNodeId=parent,
            childrenSourceNodeIds=children,activeSelf=rect.gameObject.activeSelf,activeInHierarchy=rect.gameObject.activeInHierarchy,
            position=StaticLayoutVec3Values(rect.localPosition),size=StaticLayoutVec2Values(rect.rect.size),
            anchor=new[]{rect.pivot.x,rect.pivot.y},scale=StaticLayoutVec3Values(rect.localScale)};
    }

    // The main importer calls this while prefab contents are loaded, after ordinary
    // saved-readback. All geometry changes happen on an owned clone that is destroyed here.
    static StaticLayoutProbeResult RunStaticLayoutPrefabProbe(Plan plan,SourcePrefabSpec prefab,GameObject loadedContents)
    {
        var contract=plan.layoutCompletion;
        if(contract==null||String.IsNullOrEmpty(contract.schema))return new StaticLayoutProbeResult{phase="initialized-disposable-clone",status="not_applicable",disposableCloneRequired=true,persistentPrefabMutated=false};
        if(prefab==null||loadedContents==null)throw new InvalidOperationException("STATIC_LAYOUT_PREFAB_PROBE_INPUT_MISSING");
        var selected=new HashSet<string>(prefab.nodes??Array.Empty<string>(),StringComparer.Ordinal);
        var scopedNodes=(contract.nodes??Array.Empty<StaticLayoutNodeSpec>()).Where(x=>x!=null&&selected.Contains(x.sourceNodeId)).ToArray();
        if(scopedNodes.Length==0)return new StaticLayoutProbeResult{phase="initialized-disposable-clone",status="not_applicable",disposableCloneRequired=true,persistentPrefabMutated=false};
        var scopedContract=new StaticLayoutCompletionContract{schema=contract.schema,status=contract.status,
            sourceManifestSha256=contract.sourceManifestSha256,nodes=scopedNodes,
            dynamicBusinessImplemented=contract.dynamicBusinessImplemented,initialPoseUsedAsConstraintProof=false};
        GameObject clone=null,context=null,host=null;
        try
        {
            host=new GameObject("StaticLayoutInactiveProbeHost");
            UnityEngine.SceneManagement.SceneManager.MoveGameObjectToScene(host,loadedContents.scene);host.SetActive(false);
            clone=UnityEngine.Object.Instantiate(loadedContents,host.transform,false);clone.name="StaticLayoutDisposableProbe";
            context=StaticLayoutCreateInactiveProbeContext(clone,plan);
            UnityEngine.Object.DestroyImmediate(host);host=null;
            var byId=(plan.nodes??Array.Empty<NodeSpec>()).ToDictionary(x=>x.sourceId,StringComparer.Ordinal);
            var mapped=SavedNodeMap(plan.nodes,clone,prefab,byId).ToDictionary(x=>x.Key,x=>x.Value.gameObject,StringComparer.Ordinal);
            var inputs=scopedNodes.SelectMany(x=>(x.layouts??Array.Empty<StaticLayoutSlotSpec>()).Select(_=>x.sourceNodeId)
                .Concat((x.widgets??Array.Empty<StaticWidgetSlotSpec>()).Select(_=>x.sourceNodeId))).Distinct(StringComparer.Ordinal)
                .Where(mapped.ContainsKey).Select(id=>{
                    var rect=mapped[id].GetComponent<RectTransform>();
                    return new StaticLayoutProbeInput{sourceNodeId=id,position=null,size=null,activateHierarchy=true};
                }).ToArray();
            return ProbeStaticLayoutCompletion(plan,scopedContract,mapped,inputs);
        }
        finally
        {
            if(context!=null)UnityEngine.Object.DestroyImmediate(context);
            else if(clone!=null)UnityEngine.Object.DestroyImmediate(clone);
            if(host!=null)UnityEngine.Object.DestroyImmediate(host);
        }
    }

    static StaticLayoutComponentReadback ReadStaticLayoutSlot(StaticLayoutSlotSpec spec,
        Dictionary<string, NativeStaticLayoutCompletion.SlotReadback> saved, string guid, long localId)
    {
        if (!saved.TryGetValue(spec.sourceComponentId, out var slot) || slot.componentOrder != spec.componentOrder ||
            slot.sourceEnabled != spec.sourceEnabled || !slot.nativeComponentPresent || !slot.savedReferenceVerified)
            throw new InvalidOperationException("STATIC_LAYOUT_SAVED_SLOT_IDENTITY_OR_STATE_DIFFERS: " + spec.sourceComponentId);
        var value = slot.layoutValue;
        if (value == null) throw new InvalidOperationException("STATIC_LAYOUT_TYPED_SLOT_VALUE_MISSING: " + spec.sourceComponentId);
        if (value.layoutType != spec.layoutType || value.resize != spec.resize || value.startAxis != spec.startAxis ||
            value.horizontalDirection != spec.horizontalDirection || value.verticalDirection != spec.verticalDirection ||
            value.affectedByScale != spec.affectedByScale || !StaticLayoutSameFloats(spec.padding,new[]{value.padding.x,value.padding.y,value.padding.z,value.padding.w}) ||
            !StaticLayoutSameFloats(spec.spacingXY,new[]{value.spacingXY.x,value.spacingXY.y}) ||
            !StaticLayoutSameFloats(spec.cellSize,new[]{value.cellSize.x,value.cellSize.y}) ||
            value.hasSourceLayoutCacheSize != spec.sourceLayoutCacheSizeKnown ||
            value.hasSourceLayoutCacheSize && !StaticLayoutSameFloats(spec.sourceLayoutCacheSize,new[]{value.sourceLayoutCacheSize.x,value.sourceLayoutCacheSize.y}) ||
            !StaticLayoutSameStrings(spec.sourceFieldPresence,value.sourceFieldPresence) || !StaticLayoutSameStrings(spec.unknownSourceFields,value.unknownSourceFields))
            throw new InvalidOperationException("STATIC_LAYOUT_SAVED_TYPED_FIELDS_DIFFER: " + spec.sourceComponentId);
        return new StaticLayoutComponentReadback
        {
            sourceComponentId=slot.sourceComponentId, componentOrder=slot.componentOrder,
            sourceEnabled=slot.sourceEnabled, nativeComponentPresent=true, savedReferenceVerified=true,
            sourceFieldPresence=value.sourceFieldPresence, unknownSourceFields=value.unknownSourceFields,
            carrierGuid=guid, carrierLocalFileId=localId,
            fieldValues=new StaticLayoutFieldValues { layoutType=value.layoutType, resize=value.resize,
                spacingXY=new[]{value.spacingXY.x,value.spacingXY.y}, padding=new[]{value.padding.x,value.padding.y,value.padding.z,value.padding.w},
                cellSize=new[]{value.cellSize.x,value.cellSize.y}, startAxis=value.startAxis,
                horizontalDirection=value.horizontalDirection, verticalDirection=value.verticalDirection,
                affectedByScale=value.affectedByScale,
                sourceLayoutCacheSizeKnown=value.hasSourceLayoutCacheSize,
                sourceLayoutCacheSize=value.hasSourceLayoutCacheSize?new[]{value.sourceLayoutCacheSize.x,value.sourceLayoutCacheSize.y}:null }
        };
    }

    static StaticWidgetComponentReadback ReadStaticWidgetSlot(StaticWidgetSlotSpec spec,
        Dictionary<string, NativeStaticLayoutCompletion.SlotReadback> saved, string guid, long localId,
        GameObject owner, Dictionary<string, GameObject> persistentNodes)
    {
        if (!saved.TryGetValue(spec.sourceComponentId, out var slot) || slot.componentOrder != spec.componentOrder ||
            slot.sourceEnabled != spec.sourceEnabled || !slot.nativeComponentPresent || !slot.savedReferenceVerified)
            throw new InvalidOperationException("STATIC_WIDGET_SAVED_SLOT_IDENTITY_OR_STATE_DIFFERS: " + spec.sourceComponentId);
        var value = slot.widgetValue;
        if (value == null) throw new InvalidOperationException("STATIC_WIDGET_TYPED_SLOT_VALUE_MISSING: " + spec.sourceComponentId);
        RectTransform expectedTarget=null;
        if (!String.IsNullOrEmpty(spec.targetSourceNodeId))
        {
            if (!persistentNodes.TryGetValue(spec.targetSourceNodeId,out var targetNode) || targetNode == null)
                throw new InvalidOperationException("STATIC_WIDGET_READ_TARGET_MISSING: " + spec.targetSourceNodeId);
            expectedTarget=targetNode.GetComponent<RectTransform>();
        }
        else if(spec.targetUsesParentWhenNull && owner.transform.parent as RectTransform == null)
            throw new InvalidOperationException("STATIC_WIDGET_PARENT_FALLBACK_UNAVAILABLE: " + spec.sourceComponentId);
        bool targetSourceIdMatches=spec.targetUsesParentWhenNull
            ? String.IsNullOrEmpty(spec.targetSourceNodeId)&&String.IsNullOrEmpty(value.targetSourceNodeId)
            : String.Equals(value.targetSourceNodeId,spec.targetSourceNodeId,StringComparison.Ordinal);
        if (value.sourceComponentId != spec.sourceComponentId || value.componentOrder != spec.componentOrder ||
            value.sourceEnabled != spec.sourceEnabled || value.alignFlags != spec.alignFlags || value.alignMode != spec.alignMode ||
            value.targetUsesParentWhenNull != spec.targetUsesParentWhenNull ||
            !StaticLayoutSameFloats(spec.margins,new[]{value.margins.x,value.margins.y,value.margins.z,value.margins.w}) ||
            !StaticLayoutSameFloats(spec.center,new[]{value.center.x,value.center.y}) ||
            !StaticLayoutSameFloats(spec.absolute.Select(x=>x?1f:0f).ToArray(),new[]{value.absoluteMargins.x,value.absoluteMargins.y,value.absoluteMargins.z,value.absoluteMargins.w}) ||
            !StaticLayoutSameFloats(spec.centerAbsolute.Select(x=>x?1f:0f).ToArray(),new[]{value.centerAbsolute.x,value.centerAbsolute.y}) ||
            value.hasSourceOriginalWidth != spec.sourceOriginalWidthKnown || value.hasSourceOriginalHeight != spec.sourceOriginalHeightKnown ||
            !StaticLayoutSameFloats(new[]{StaticLayoutAt(spec.sourceOriginalSize,0),StaticLayoutAt(spec.sourceOriginalSize,1)},new[]{value.sourceOriginalSize.x,value.sourceOriginalSize.y}) ||
            value.target != expectedTarget || !targetSourceIdMatches ||
            !StaticLayoutSameStrings(spec.sourceFieldPresence,value.sourceFieldPresence) || !StaticLayoutSameStrings(spec.unknownSourceFields,value.unknownSourceFields))
            throw new InvalidOperationException("STATIC_WIDGET_SAVED_TYPED_FIELDS_OR_TARGET_DIFFER: " + spec.sourceComponentId);
        string targetGuid=null; long targetId=0;
        if (value.target != null && (!EditorUtility.IsPersistent(value.target) ||
            !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value.target, out targetGuid, out targetId) || targetId == 0))
            throw new InvalidOperationException("STATIC_WIDGET_TARGET_REFERENCE_IDENTITY_MISSING: " + spec.sourceComponentId);
        return new StaticWidgetComponentReadback
        {
            sourceComponentId=slot.sourceComponentId, componentOrder=slot.componentOrder,
            sourceEnabled=slot.sourceEnabled, nativeComponentPresent=true, savedReferenceVerified=true,
            sourceFieldPresence=value.sourceFieldPresence, unknownSourceFields=value.unknownSourceFields,
            carrierGuid=guid, carrierLocalFileId=localId, targetGuid=targetGuid, targetLocalFileId=targetId,
            fieldValues=new StaticWidgetFieldValues { alignFlags=value.alignFlags, alignMode=value.alignMode,
                margins=new[]{value.margins.x,value.margins.y,value.margins.z,value.margins.w},
                absolute=new[]{value.absoluteMargins.x!=0,value.absoluteMargins.y!=0,value.absoluteMargins.z!=0,value.absoluteMargins.w!=0},
                center=new[]{value.center.x,value.center.y}, centerAbsolute=new[]{value.centerAbsolute.x!=0,value.centerAbsolute.y!=0},
                targetUsesParentWhenNull=spec.targetUsesParentWhenNull,
                targetSourceNodeId=spec.targetUsesParentWhenNull?null:spec.targetSourceNodeId,
                sourceOriginalSize=new[]{value.hasSourceOriginalWidth?value.sourceOriginalSize.x:0f,
                    value.hasSourceOriginalHeight?value.sourceOriginalSize.y:0f} }
        };
    }
}
