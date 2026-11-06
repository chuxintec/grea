using System;
using System.Collections.Generic;
using System.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

// Scene-local clone/layout helper. Importers call Apply once on an isolated
// source prefab clone, then call Read after save/reopen. It never enables or
// invokes source business behaviours. Native mode delegates positions to the
// source Layout; manual mode assigns only pinned source-formula positions.
public static class UnityPreviewClones
{
    [Serializable] public sealed class TemplateNode
    {
        public string sourceId, name, parentSourceId;
        public string[] childrenSourceIds, componentSourceIds;
    }
    [Serializable] public sealed class SourceByteRange { public int start, end; }
    [Serializable] public sealed class SourceManualLayout
    {
        public string formulaId, sourceEvidenceId, sourceCodePath, sourceCodeSha256, sourceSpanSha256;
        public int count;
        public int totalThresholdCount;
        public float templateWidth, gap, progressBarTotalLength, sourceTemplateY, passItemHeight, spacingY;
        public SourceByteRange sourceBytes;
    }
    [Serializable] public sealed class AppendGridLayoutRule
    {
        public string formulaId;
        public int sourceLayoutType, sourceResizeMode, sourceStartAxis, sourceHorizontalDirection, sourceVerticalDirection, sourceConstraint, sourceConstraintCount;
        public int columns, rows, count;
        public float[] cellSize, spacing, padding, sourceParentSize, expectedParentSize;
        public string[] inactiveOwnerChildSourceIds;
    }
    [Serializable] public sealed class TemplateSpec
    {
        public string rootSourceId, templatePrefabId, parentSourceId, sourceRootParentSourceId,
            replacePlaceholderSourceId, layoutComponentSourceId, layoutMode, placementMode;
        public float[] firstSourcePosition, firstSourceSize;
        public int initialSiblingIndex, appendStartSiblingIndex, expectedChildCount;
        public bool positionsAreTargetReadbackOnly;
        public string retainedTemplateDisposition;
        public string[] initialChildSourceIds;
        public TemplateNode[] sourceTree;
        public SourceManualLayout sourceManualLayout;
        public AppendGridLayoutRule appendLayoutRule;
    }
    [Serializable] public sealed class ColorOperation
    {
        public string kind, sourceId, targetKind, targetNodeSourceId, targetComponentSourceId;
        public int[] expectedValue, value;
    }
    [Serializable] public sealed class InstanceSpec
    {
        public string instanceId, mode, sourceNodeId, parentSourceId;
        public int siblingIndex, layoutIndex;
        public bool hasLayoutIndex;
        public string positionEvidenceId;
        public float[] position;
        public UnityPreviewState.OperationState previewState;
        public ColorOperation[] extraOperations;
    }
    [Serializable] public sealed class EvidenceFile { public string path, sha256; public int bytes; }
    [Serializable] public sealed class CloneBatch
    {
        public string schema, cloneSpecSha256, sourcePlanSha256, sourceManifestSha256, sourcePrefabId, templatePrefabId;
        public TemplateSpec template;
        public EvidenceFile[] evidenceFiles;
        public InstanceSpec[] instances;
        public bool layoutReadbackRequired, sourceBehaviorExecuted;
    }
    [Serializable] public sealed class ColorReadback
    {
        public string kind, sourceId;
        public int[] expectedValue, value, actualValue;
        public bool verified;
    }
    [Serializable] public sealed class LayoutItemReadback
    {
        public string instanceId;
        public int siblingIndex;
        public bool parentMatches;
        public float[] size, position;
    }
    [Serializable] public sealed class LayoutReadback
    {
        public string status;
        public bool verified;
        public float[] firstSourcePosition, expectedSourcePosition, parentSize, expectedParentSize;
        public LayoutItemReadback[] items;
    }
    [Serializable] public sealed class InstanceReadback
    {
        public string instanceId;
        public UnityPreviewState.Readback state;
        public ColorReadback[] colors;
        public bool verified;
    }
    [Serializable] public sealed class Readback
    {
        public string schema, sourcePrefabId, cloneSpecSha256, sourcePlanSha256;
        public int cloneCount;
        public bool applied, verified, businessBehaviorComplete;
        public LayoutReadback layout;
        public InstanceReadback[] instances;
        public string[] gaps;
    }

    public delegate UnityEngine.Object CloneResolver(IDictionary<string, GameObject> sourceNodes, string sourceId);
    public delegate GameObject TemplateProvider(string templatePrefabId, string rootSourceId);
    static readonly HashSet<string> LayoutHelpers = new HashSet<string>(StringComparer.Ordinal) {
        "NativeRectConstraints", "NativeTextLineBox", "IntrinsicGridLayoutGroup", "NativeLinearLayoutGroup",
        "NativeHorizontalProgressFill", "NativeInputBlocker", "NativeInputBlockerSurface", "NativeStaticTextOutline", "Monkey.Targets.Spine.UnitySpineGraphicMaterialPresentation"
    };

    static void Require(bool condition, string code) { if (!condition) throw new InvalidOperationException(code); }
    static bool SameColor(Color actual, int[] expected)
    {
        return expected != null && expected.Length == 4 &&
            Mathf.Abs(actual.r - expected[0] / 255f) <= 1e-5f &&
            Mathf.Abs(actual.g - expected[1] / 255f) <= 1e-5f &&
            Mathf.Abs(actual.b - expected[2] / 255f) <= 1e-5f &&
            Mathf.Abs(actual.a - expected[3] / 255f) <= 1e-5f;
    }
    static int[] Bytes(Color color)
    {
        return new[] {Mathf.RoundToInt(color.r*255), Mathf.RoundToInt(color.g*255),
            Mathf.RoundToInt(color.b*255), Mathf.RoundToInt(color.a*255)};
    }
    static void Validate(CloneBatch batch, IDictionary<string, GameObject> sourceNodes, bool readingSavedBatch = false)
    {
        Require(batch != null && batch.schema == "monkey-prefab-preview-clone-batch/1" &&
            !String.IsNullOrEmpty(batch.sourcePrefabId) && !String.IsNullOrEmpty(batch.sourceManifestSha256) &&
            !String.IsNullOrEmpty(batch.cloneSpecSha256) && !String.IsNullOrEmpty(batch.sourcePlanSha256), "PREVIEW_CLONE_BATCH_INVALID");
        Require(sourceNodes != null && batch.template != null &&
            (batch.template.layoutMode == "native-layout" || batch.template.layoutMode == "source-manual") &&
            batch.template.positionsAreTargetReadbackOnly && batch.template.sourceTree != null && batch.template.sourceTree.Length > 0,
            "PREVIEW_CLONE_LAYOUT_CONTRACT_REQUIRED");
        var templatePrefabId = String.IsNullOrEmpty(batch.templatePrefabId) ? batch.sourcePrefabId : batch.templatePrefabId;
        var external = templatePrefabId != batch.sourcePrefabId;
        bool manual = batch.template.layoutMode == "source-manual";
        var placement = String.IsNullOrEmpty(batch.template.placementMode) ? (external ? "replace-placeholder" : "reuse-source-child") : batch.template.placementMode;
        bool append = placement == "append-external";
        Require(placement=="reuse-source-child"||placement=="replace-placeholder"||append,"PREVIEW_CLONE_PLACEMENT_MODE_INVALID");
        Require(!manual || !external || append, "PREVIEW_CLONE_EXTERNAL_SOURCE_MANUAL_UNSUPPORTED");
        var initialChildId = external ? batch.template.replacePlaceholderSourceId : batch.template.rootSourceId;
        var initialChildren=batch.template.initialChildSourceIds;
        Require(initialChildren!=null&&initialChildren.All(x=>!String.IsNullOrEmpty(x)),"PREVIEW_CLONE_INITIAL_CHILDREN_INVALID");
        if(append)Require(external&&String.IsNullOrEmpty(batch.template.replacePlaceholderSourceId)&&
            String.IsNullOrEmpty(batch.template.sourceRootParentSourceId)&&batch.template.appendStartSiblingIndex==initialChildren.Length,
            "PREVIEW_CLONE_APPEND_CONTRACT_INVALID");
        else Require(initialChildren.Length==1&&initialChildren[0]==initialChildId,"PREVIEW_CLONE_PARENT_INITIAL_CHILDREN_MISMATCH");
        Require(batch.template.rootSourceId.StartsWith(templatePrefabId+"#", StringComparison.Ordinal) &&
            batch.template.parentSourceId.StartsWith(batch.sourcePrefabId+"#", StringComparison.Ordinal), "PREVIEW_CLONE_TEMPLATE_OUTSIDE_PREFAB");
        Require(sourceNodes.TryGetValue(batch.template.parentSourceId, out var parent) && parent != null &&
            (append ? initialChildren.All(sourceNodes.ContainsKey) : (external ? sourceNodes.ContainsKey(initialChildId) : sourceNodes.ContainsKey(batch.template.rootSourceId))), "PREVIEW_CLONE_SOURCE_NODE_MISSING");
        bool externalContract=external
            ? (append || (!String.IsNullOrEmpty(initialChildId) && initialChildId.StartsWith(batch.sourcePrefabId+"#", StringComparison.Ordinal) &&
                batch.template.sourceRootParentSourceId != batch.template.parentSourceId))
            : ((String.IsNullOrEmpty(batch.template.sourceRootParentSourceId) || batch.template.sourceRootParentSourceId == batch.template.parentSourceId) &&
                String.IsNullOrEmpty(batch.template.replacePlaceholderSourceId));
        Require(externalContract,"PREVIEW_CLONE_EXTERNAL_TEMPLATE_CONTRACT_INVALID");
        var byId = new Dictionary<string, TemplateNode>(StringComparer.Ordinal);
        foreach (var row in batch.template.sourceTree) {
            Require(row != null && !String.IsNullOrEmpty(row.sourceId) && row.childrenSourceIds != null &&
                row.componentSourceIds != null && !byId.ContainsKey(row.sourceId), "PREVIEW_CLONE_SOURCE_TREE_INVALID");
            byId.Add(row.sourceId,row);
        }
        Require(byId.ContainsKey(batch.template.rootSourceId), "PREVIEW_CLONE_SOURCE_TREE_ROOT_MISSING");
        var seen = new HashSet<string>(StringComparer.Ordinal);var pending = new Stack<string>();pending.Push(batch.template.rootSourceId);
        while (pending.Count > 0) {
            var id=pending.Pop();Require(seen.Add(id), "PREVIEW_CLONE_SOURCE_TREE_CYCLE");
            Require(byId.TryGetValue(id,out var row), "PREVIEW_CLONE_SOURCE_TREE_CHILD_MISSING");
            foreach(var child in row.childrenSourceIds)pending.Push(child);
        }
        Require(seen.Count == byId.Count, "PREVIEW_CLONE_SOURCE_TREE_EXTRA_NODE");
        Require(batch.template.initialChildSourceIds != null && batch.template.initialChildSourceIds.Distinct(StringComparer.Ordinal).Count()==batch.template.initialChildSourceIds.Length &&
            batch.template.initialChildSourceIds.All(id=>sourceNodes.ContainsKey(id)), "PREVIEW_CLONE_PARENT_INITIAL_CHILDREN_MISMATCH");
        if(!readingSavedBatch)Require(parent.transform.childCount==batch.template.initialChildSourceIds.Length&&
            batch.template.initialChildSourceIds.Select((id,index)=>sourceNodes[id].transform==parent.transform.GetChild(index)).All(x=>x),
            "PREVIEW_CLONE_PARENT_INITIAL_CHILDREN_MISMATCH");
        else Require(batch.template.initialChildSourceIds.Select((id,index)=>sourceNodes[id].transform==parent.transform.GetChild(index)).All(x=>x),
            "PREVIEW_CLONE_SAVED_SOURCE_CHILD_PREFIX_MISMATCH");
        Require(batch.instances != null && batch.instances.Length > 0 && batch.instances.Length <= 10000, "PREVIEW_CLONE_INSTANCE_COUNT_INVALID");
        Require(batch.template.expectedChildCount == (append ? batch.template.initialChildSourceIds.Length+batch.instances.Length : batch.instances.Length + (manual ? 1 : 0)),
            "PREVIEW_CLONE_EXPECTED_CHILD_COUNT_INVALID");
        if(readingSavedBatch) {
            Require(parent.transform.childCount == batch.template.expectedChildCount, "PREVIEW_CLONE_SAVED_CHILD_COUNT_MISMATCH");
            if(!external) {
                var sourceRoot=sourceNodes[batch.template.rootSourceId];
                Require(sourceRoot.transform.parent==parent.transform&&parent.transform.GetChild(0).gameObject==sourceRoot,
                    "PREVIEW_CLONE_SAVED_SOURCE_ROOT_MISMATCH");
                if(manual)Require(!sourceRoot.activeSelf&&batch.template.retainedTemplateDisposition=="inactive",
                    "PREVIEW_CLONE_SOURCE_MANUAL_TEMPLATE_STATE_MISMATCH");
            }
        } else {
            Require(parent.transform.childCount == batch.template.initialChildSourceIds.Length &&
                (external || sourceNodes[batch.template.rootSourceId].transform.parent == parent.transform),
                "PREVIEW_CLONE_PARENT_INITIAL_CHILDREN_MISMATCH");
        }
        if(manual) {
            var proof=batch.template.sourceManualLayout;
            Require(proof!=null&&batch.template.firstSourcePosition!=null&&batch.template.firstSourcePosition.Length==3&&
                proof.count==batch.instances.Length&&proof.sourceBytes!=null&&proof.sourceBytes.start>=0&&
                proof.sourceBytes.end>proof.sourceBytes.start&&proof.formulaId!=null&&
                (proof.formulaId=="centered-horizontal-linear/1"||proof.formulaId=="progress-threshold-centers/1"||proof.formulaId=="pass-task-linear-y/1")&&
                proof.sourceEvidenceId!=null&&proof.sourceCodePath!=null&&proof.sourceCodeSha256!=null&&proof.sourceCodeSha256.Length==64&&
                proof.sourceSpanSha256!=null&&proof.sourceSpanSha256.Length==64&&
                (proof.formulaId=="pass-task-linear-y/1"||proof.sourceTemplateY==batch.template.firstSourcePosition[1]),
                "PREVIEW_CLONE_SOURCE_MANUAL_EVIDENCE_INVALID");
            Require(batch.evidenceFiles!=null&&batch.evidenceFiles.Any(x=>x.path==proof.sourceCodePath&&x.sha256==proof.sourceCodeSha256),
                "PREVIEW_CLONE_SOURCE_MANUAL_CODE_NOT_PINNED");
            if(proof.formulaId=="centered-horizontal-linear/1")
                Require(proof.templateWidth>proof.gap&&proof.gap>=0,"PREVIEW_CLONE_SOURCE_MANUAL_FORMULA_INVALID");
            else if(proof.formulaId=="progress-threshold-centers/1")Require(proof.progressBarTotalLength>0&&proof.totalThresholdCount>proof.count,
                "PREVIEW_CLONE_SOURCE_MANUAL_FORMULA_INVALID");
            else Require(proof.passItemHeight>0&&proof.spacingY>=0&&Mathf.Abs(proof.sourceTemplateY+proof.passItemHeight/2)<=1e-4f,
                "PREVIEW_CLONE_SOURCE_MANUAL_FORMULA_INVALID");
            if(append)Require(batch.template.expectedChildCount==batch.template.initialChildSourceIds.Length+batch.instances.Length&&
                batch.template.retainedTemplateDisposition=="preserve-owner-children",
                "PREVIEW_CLONE_APPEND_MANUAL_CHILD_CONTRACT_INVALID");
            else Require(batch.template.expectedChildCount==batch.instances.Length+1&&batch.template.retainedTemplateDisposition=="inactive",
                "PREVIEW_CLONE_SOURCE_MANUAL_CHILD_CONTRACT_INVALID");
        }
        else Require(batch.template.layoutMode=="native-layout"&&batch.template.retainedTemplateDisposition==(append?"preserve-owner-children":"reused-as-row-zero"),
            "PREVIEW_CLONE_NATIVE_LAYOUT_CONTRACT_INVALID");
        if(append&&!manual) {
            var rule=batch.template.appendLayoutRule;
            Require(rule!=null&&rule.formulaId=="cocos-grid-auto-columns-top-left/1"&&rule.count==batch.instances.Length&&
                rule.cellSize!=null&&rule.cellSize.Length==2&&rule.cellSize.All(x=>x>0)&&rule.spacing!=null&&rule.spacing.Length==2&&rule.spacing.All(x=>x>=0)&&
                rule.padding!=null&&rule.padding.Length==4&&rule.padding.All(x=>x>=0)&&rule.sourceParentSize!=null&&rule.sourceParentSize.Length==2&&
                rule.sourceParentSize.All(x=>x>0)&&rule.expectedParentSize!=null&&rule.expectedParentSize.Length==2&&rule.expectedParentSize.All(x=>x>0)&&
                rule.inactiveOwnerChildSourceIds!=null&&rule.inactiveOwnerChildSourceIds.SequenceEqual(batch.template.initialChildSourceIds),
                "PREVIEW_CLONE_APPEND_LAYOUT_RULE_INVALID");
            int derivedColumns=Mathf.Max(1,Mathf.FloorToInt((rule.sourceParentSize[0]-rule.padding[0]-rule.padding[2]+rule.spacing[0]+1e-6f)/
                (rule.cellSize[0]+rule.spacing[0])));
            int derivedRows=(rule.count+derivedColumns-1)/derivedColumns;
            float derivedHeight=derivedRows*rule.cellSize[1]+Mathf.Max(0,derivedRows-1)*rule.spacing[1]+rule.padding[1]+rule.padding[3];
            Require(rule.sourceLayoutType==3&&rule.sourceResizeMode==1&&rule.sourceStartAxis==0&&rule.sourceHorizontalDirection==0&&
                rule.sourceVerticalDirection==1&&rule.sourceConstraint==0&&rule.sourceConstraintCount>=0&&rule.columns==derivedColumns&&rule.rows==derivedRows&&
                Mathf.Abs(rule.expectedParentSize[0]-rule.sourceParentSize[0])<=1e-3f&&Mathf.Abs(rule.expectedParentSize[1]-derivedHeight)<=1e-3f,
                "PREVIEW_CLONE_APPEND_LAYOUT_RULE_SOURCE_FORMULA_MISMATCH");
            Require(batch.template.initialChildSourceIds.All(id=>!sourceNodes[id].activeInHierarchy),
                "PREVIEW_CLONE_APPEND_LAYOUT_ACTIVE_OWNER_CHILD_UNSUPPORTED");
            Require(parent.activeInHierarchy,"PREVIEW_CLONE_APPEND_LAYOUT_PARENT_INACTIVE");
        }
        var ids = new HashSet<string>(StringComparer.Ordinal);
        var componentIds = new HashSet<string>(batch.template.sourceTree.SelectMany(x=>x.componentSourceIds),StringComparer.Ordinal);
        for(int i=0;i<batch.instances.Length;i++) {
            var row=batch.instances[i];
            int expectedSibling=append?batch.template.appendStartSiblingIndex+i:(manual?i+1:i);
            string expectedMode=append?"append-clone":(manual?"clone-template":(i==0?"reuse-template":"clone-template"));
            Require(row!=null&&!String.IsNullOrEmpty(row.instanceId)&&ids.Add(row.instanceId)&&row.siblingIndex==expectedSibling&&
                row.sourceNodeId==batch.template.rootSourceId&&row.parentSourceId==batch.template.parentSourceId&&
                row.mode==expectedMode&&row.previewState!=null&&
                row.previewState.sourcePrefabId==templatePrefabId&&row.previewState.sourceManifestSha256==batch.sourceManifestSha256&&
                row.previewState.operations!=null&&row.previewState.operations.Length>0,"PREVIEW_CLONE_INSTANCE_INVALID");
            if(manual) {
                var proof=batch.template.sourceManualLayout;var p=row.position;
                Require(p!=null&&p.Length==3&&row.positionEvidenceId==proof.sourceEvidenceId,"PREVIEW_CLONE_SOURCE_MANUAL_POSITION_MISSING");
                float x;
                if(proof.formulaId=="centered-horizontal-linear/1") {
                    float step=proof.templateWidth-proof.gap;x=-(proof.count*step)/2f+step/2f+i*step;
                } else if(proof.formulaId=="progress-threshold-centers/1") {
                    float step=proof.progressBarTotalLength/proof.totalThresholdCount;
                    x=-proof.progressBarTotalLength/2f+(i+1)*step;
                } else {
                    int layoutIndex=row.hasLayoutIndex?row.layoutIndex:i;
                    float y=-proof.passItemHeight/2f-layoutIndex*(proof.passItemHeight+proof.spacingY);
                    Require(Mathf.Abs(p[0])<=1e-4f&&Mathf.Abs(p[1]-y)<=1e-4f&&Mathf.Abs(p[2])<=1e-4f,
                        "PREVIEW_CLONE_SOURCE_MANUAL_POSITION_INVALID");
                    x=Single.NaN;
                }
                if(!Single.IsNaN(x))Require(Mathf.Abs(p[0]-x)<=1e-4f&&Mathf.Abs(p[1]-proof.sourceTemplateY)<=1e-4f&&Mathf.Abs(p[2])<=1e-4f,
                    "PREVIEW_CLONE_SOURCE_MANUAL_POSITION_INVALID");
            }
            foreach(var op in row.extraOperations??Array.Empty<ColorOperation>()) {
                bool nodeComponentBound=op!=null&&byId.ContainsKey(op.targetNodeSourceId??"")&&
                    byId[op.targetNodeSourceId].componentSourceIds.Contains(op.targetComponentSourceId??"");
                bool colorTarget=op!=null&&((op.targetKind=="node"&&op.sourceId==op.targetNodeSourceId&&
                    nodeComponentBound&&componentIds.Contains(op.targetComponentSourceId??""))||
                    (op.targetKind=="component"&&op.sourceId==op.targetComponentSourceId&&componentIds.Contains(op.sourceId??"")&&
                    (String.IsNullOrEmpty(op.targetNodeSourceId)||byId.ContainsKey(op.targetNodeSourceId))));
                Require(colorTarget&&op.kind=="sprite.color"&&
                    op.expectedValue!=null&&op.expectedValue.Length==4&&op.value!=null&&op.value.Length==4&&
                    op.expectedValue.Concat(op.value).All(x=>x>=0&&x<=255),"PREVIEW_CLONE_EXTRA_OPERATION_INVALID");
            }
        }
    }
    static void StaticOnly(GameObject root)
    {
        foreach(var behaviour in root.GetComponentsInChildren<MonoBehaviour>(true)) {
            var name=behaviour.GetType().FullName??"";var assembly=behaviour.GetType().Assembly.GetName().Name??"";
            bool engine=assembly.StartsWith("UnityEngine",StringComparison.Ordinal)||assembly.StartsWith("Unity.",StringComparison.Ordinal)||
                assembly.StartsWith("UnityEditor",StringComparison.Ordinal)||assembly.StartsWith("Unity.TextMeshPro",StringComparison.Ordinal)||assembly.StartsWith("TMPro",StringComparison.Ordinal);
            Require(!behaviour.enabled||engine||LayoutHelpers.Contains(name)||UnityPreviewState.IsFrozenNativeRenderer(behaviour),
                "PREVIEW_CLONE_ENABLED_SOURCE_BEHAVIOR: "+name);
        }
    }
    static Dictionary<string,GameObject> MapTree(TemplateSpec template, GameObject root)
    {
        var spec=template.sourceTree.ToDictionary(x=>x.sourceId,StringComparer.Ordinal);
        var map=new Dictionary<string,GameObject>(StringComparer.Ordinal);var pending=new Stack<Tuple<string,GameObject>>();pending.Push(Tuple.Create(template.rootSourceId,root));
        while(pending.Count>0) {
            var entry=pending.Pop();var id=entry.Item1;var go=entry.Item2;
            Require(go!=null&&!map.ContainsKey(id),"PREVIEW_CLONE_TREE_READBACK_INVALID: "+id);
            if(!spec.TryGetValue(id,out var row))throw new InvalidOperationException("PREVIEW_CLONE_TREE_READBACK_INVALID: "+id);
            map.Add(id,go);
            var sourceChildren=SourceChildren(go.transform);
            Require(go.name==row.name&&sourceChildren.Length==row.childrenSourceIds.Length,"PREVIEW_CLONE_HIERARCHY_MISMATCH: "+id);
            for(int i=row.childrenSourceIds.Length-1;i>=0;i--)pending.Push(Tuple.Create(row.childrenSourceIds[i],sourceChildren[i].gameObject));
        }
        return map;
    }
    // Match UnityImporter's strict rule: only hidden, native TMP fallback
    // submeshes are generated. Arbitrary extra transforms remain mismatches.
    static bool IsGeneratedTextSubmesh(Transform child)
    {
        if(child==null||child.parent==null||child.childCount!=0)return false;
        var sub=child.GetComponent<TMP_SubMeshUI>();
        var owner=child.parent.GetComponent<TextMeshProUGUI>();
        var layout=child.GetComponent<LayoutElement>();
        if(sub==null||owner==null||sub.textComponent!=owner||sub.fontAsset==null||layout==null||!layout.ignoreLayout||
            (child.gameObject.hideFlags&HideFlags.DontSave)!=HideFlags.DontSave)return false;
        return child.GetComponents<Component>().All(c=>c is RectTransform||c is CanvasRenderer||c is TMP_SubMeshUI||c is LayoutElement);
    }
    static Transform[] SourceChildren(Transform parent)
    {
        return Enumerable.Range(0,parent.childCount).Select(parent.GetChild).Where(child=>!MonkeyImporter.IsGeneratedNativePresentationChild(child)).ToArray();
    }
    static ColorReadback ApplyColor(ColorOperation op,CloneResolver resolve,IDictionary<string,GameObject> map)
    {
        var graphic=resolve(map,String.IsNullOrEmpty(op.targetComponentSourceId)?op.sourceId:op.targetComponentSourceId) as Graphic;
        Require(graphic!=null,"PREVIEW_CLONE_COLOR_TARGET: "+op.sourceId);
        if(!SameColor(graphic.color,op.expectedValue)&&!SameColor(graphic.color,op.value))throw new InvalidOperationException("PREVIEW_CLONE_REENTRY_MISMATCH: "+op.sourceId);
        if(SameColor(graphic.color,op.expectedValue))graphic.color=new Color(op.value[0]/255f,op.value[1]/255f,op.value[2]/255f,op.value[3]/255f);
        var actual=Bytes(graphic.color);return new ColorReadback{kind=op.kind,sourceId=op.sourceId,expectedValue=op.expectedValue,value=op.value,actualValue=actual,verified=actual.SequenceEqual(op.value)};
    }
    static ColorReadback ReadColor(ColorOperation op,CloneResolver resolve,IDictionary<string,GameObject> map)
    {
        var graphic=resolve(map,String.IsNullOrEmpty(op.targetComponentSourceId)?op.sourceId:op.targetComponentSourceId) as Graphic;Require(graphic!=null,"PREVIEW_CLONE_COLOR_TARGET: "+op.sourceId);
        var actual=Bytes(graphic.color);return new ColorReadback{kind=op.kind,sourceId=op.sourceId,expectedValue=op.expectedValue,value=op.value,actualValue=actual,verified=actual.SequenceEqual(op.value)};
    }
    static LayoutReadback Layout(CloneBatch batch,Transform parent,GameObject[] roots)
    {
        var rows=roots.Select((root,index)=>{var rect=root.transform as RectTransform;return new LayoutItemReadback{instanceId=batch.instances[index].instanceId,
            siblingIndex=root.transform.GetSiblingIndex(),parentMatches=root.transform.parent==parent,
            size=rect==null?Array.Empty<float>():new[]{rect.rect.width,rect.rect.height},
            position=new[]{root.transform.localPosition.x,root.transform.localPosition.y,root.transform.localPosition.z}};}).ToArray();
        if(batch.template.layoutMode=="source-manual") {
            bool positions=rows.Select((row,i)=>Enumerable.Range(0,3).All(j=>Mathf.Abs(row.position[j]-batch.instances[i].position[j])<=1e-4f)).All(x=>x);
            int start=batch.template.placementMode=="append-external"?batch.template.appendStartSiblingIndex:1;
            bool manualOrder=rows.Select((row,i)=>row.siblingIndex==start+i&&row.parentMatches).All(x=>x);
            return new LayoutReadback{status=positions&&manualOrder?"source_manual_position_pass":"source_manual_position_partial",verified=positions&&manualOrder,
                firstSourcePosition=rows[0].position,expectedSourcePosition=batch.instances[0].position,items=rows};
        }
        if(batch.template.placementMode=="append-external") {
            var rule=batch.template.appendLayoutRule;var rect=parent as RectTransform;
            var parentSize=rect==null?Array.Empty<float>():new[]{rect.rect.width,rect.rect.height};
            bool size=parentSize.Length==2&&Mathf.Abs(parentSize[0]-rule.expectedParentSize[0])<=1e-3f&&Mathf.Abs(parentSize[1]-rule.expectedParentSize[1])<=1e-3f;
            float parentWidth=parentSize.Length==2?parentSize[0]:0,parentHeight=parentSize.Length==2?parentSize[1]:0;
            bool appendOrder=rows.Select((row,i)=>row.siblingIndex==batch.template.appendStartSiblingIndex+i&&row.parentMatches).All(x=>x);
            bool positions=rows.Select((row,i)=>{
                int col=i%rule.columns,r=i/rule.columns;float x=-parentWidth/2f+rule.padding[0]+rule.cellSize[0]/2f+col*(rule.cellSize[0]+rule.spacing[0]);
                float y=parentHeight/2f-rule.padding[3]-rule.cellSize[1]/2f-r*(rule.cellSize[1]+rule.spacing[1]);
                return Mathf.Abs(row.position[0]-x)<=1e-4f&&Mathf.Abs(row.position[1]-y)<=1e-4f&&Mathf.Abs(row.position[2])<=1e-4f&&
                    row.size.Length==2&&Mathf.Abs(row.size[0]-rule.cellSize[0])<=1e-3f&&Mathf.Abs(row.size[1]-rule.cellSize[1])<=1e-3f;
            }).All(x=>x);
            bool verified=size&&appendOrder&&positions;
            return new LayoutReadback{status=verified?"append_grid_source_rule_pass":"append_grid_source_rule_partial",verified=verified,
                firstSourcePosition=rows[0].position,expectedSourcePosition=new[]{-parentWidth/2f+rule.padding[0]+rule.cellSize[0]/2f,
                    parentHeight/2f-rule.padding[3]-rule.cellSize[1]/2f,0},parentSize=parentSize,expectedParentSize=rule.expectedParentSize,items=rows};
        }
        var expected=batch.template.firstSourcePosition;var first=rows[0].position;
        bool firstMatch=expected!=null&&expected.Length==3&&Enumerable.Range(0,3).All(i=>Mathf.Abs(first[i]-expected[i])<=1e-4f);
        bool order=rows.Select((row,i)=>row.siblingIndex==i&&row.parentMatches).All(x=>x);
        return new LayoutReadback{status=firstMatch&&order?"native_layout_readback_pass":"native_layout_readback_partial",verified=firstMatch&&order,
            firstSourcePosition=first,expectedSourcePosition=expected,items=rows};
    }

    public static Readback Apply(CloneBatch batch, IDictionary<string,GameObject> sourceNodes,
        CloneResolver resolve, Action<GameObject> settleLayout, TemplateProvider templateProvider = null)
    {
        Validate(batch,sourceNodes,false);bool manual=batch.template.layoutMode=="source-manual";
        Require(resolve!=null&&(manual||settleLayout!=null),"PREVIEW_CLONE_CALLBACK_REQUIRED");
        var external=!String.IsNullOrEmpty(batch.templatePrefabId)&&batch.templatePrefabId!=batch.sourcePrefabId;
        bool append=batch.template.placementMode=="append-external";
        var parent=sourceNodes[batch.template.parentSourceId];
        var placeholder=external&&!append?sourceNodes[batch.template.replacePlaceholderSourceId]:null;
        var template=external?(templateProvider==null?null:templateProvider(batch.templatePrefabId,batch.template.rootSourceId)):
            sourceNodes[batch.template.rootSourceId];
        Require(template!=null&&(!external||template.transform.parent==null),external?"PREVIEW_CLONE_EXTERNAL_TEMPLATE_PROVIDER_REQUIRED":"PREVIEW_CLONE_SOURCE_NODE_MISSING");
        var parentLayout=parent.GetComponent<UnityEngine.UI.LayoutGroup>();
        if(!manual)Require(parentLayout!=null&&parentLayout.enabled,
            "PREVIEW_CLONE_NATIVE_LAYOUT_MISSING");
        if(append&&manual&&batch.template.layoutComponentSourceId!=null)
            Require(parentLayout!=null,"PREVIEW_CLONE_SOURCE_MANUAL_LAYOUT_MISSING");
        var initialPosition=template.transform.localPosition;
        Require(batch.template.firstSourcePosition!=null&&batch.template.firstSourcePosition.Length==3&&
            Enumerable.Range(0,3).All(i=>Mathf.Abs(initialPosition[i]-batch.template.firstSourcePosition[i])<=1e-4f),"PREVIEW_CLONE_TEMPLATE_POSITION_MISMATCH: "+batch.sourcePrefabId+" actual="+initialPosition+" source="+String.Join(",",batch.template.firstSourcePosition??Array.Empty<float>()));
        StaticOnly(template);bool oldActive=template.activeSelf;bool oldPlaceholderActive=placeholder!=null&&placeholder.activeSelf;
        bool oldLayoutEnabled=parentLayout!=null&&parentLayout.enabled;
        var roots=(manual||append)?new List<GameObject>():new List<GameObject>{template};var added=new List<GameObject>();
        try {
            // Native mode reuses the source child for row 0. Manual mode leaves
            // that template hidden and clones each row. Every copy starts inactive.
            template.SetActive(false);
            if(append&&manual&&parentLayout!=null)parentLayout.enabled=false;
            if(external&&!append){placeholder.SetActive(false);placeholder.transform.SetParent(null,false);template.transform.SetParent(parent.transform,false);}
            if(manual) {
                foreach(var row in batch.instances) {
                    var clone=UnityEngine.Object.Instantiate(template,parent.transform,false);clone.name=template.name;clone.SetActive(false);StaticOnly(clone);
                    clone.transform.localPosition=new Vector3(row.position[0],row.position[1],row.position[2]);
                    clone.transform.SetSiblingIndex(row.siblingIndex);added.Add(clone);roots.Add(clone);
                }
            } else if(append) for(int i=0;i<batch.instances.Length;i++) {
                var row=batch.instances[i];var clone=UnityEngine.Object.Instantiate(template,parent.transform,false);
                clone.name=template.name;clone.SetActive(false);StaticOnly(clone);clone.transform.SetSiblingIndex(row.siblingIndex);
                added.Add(clone);roots.Add(clone);
            } else for(int i=1;i<batch.instances.Length;i++) {
                var clone=UnityEngine.Object.Instantiate(template,parent.transform,false);clone.name=template.name;clone.SetActive(false);StaticOnly(clone);added.Add(clone);roots.Add(clone);
            }
            for(int i=0;i<roots.Count;i++) {
                var root=roots[i];var row=batch.instances[i];root.transform.SetSiblingIndex(row.siblingIndex);
                var map=MapTree(batch.template,root);Func<string,UnityEngine.Object> resolver=id=>resolve(map,id);
                var applied=UnityPreviewState.Apply(row.previewState,resolver);
                if(!applied.verified)throw new InvalidOperationException("PREVIEW_CLONE_STATE_APPLY_FAILED: "+row.instanceId);
                var colors=(row.extraOperations??Array.Empty<ColorOperation>()).Select(op=>ApplyColor(op,resolve,map)).ToArray();
                if(colors.Any(x=>!x.verified))throw new InvalidOperationException("PREVIEW_CLONE_COLOR_READBACK_FAILED: "+row.instanceId);
            }
            foreach(var root in roots)root.SetActive(true);
            if(!manual)settleLayout(parent);var layout=Layout(batch,parent.transform,roots.ToArray());
            var readbacks=roots.Select((root,i)=>{var row=batch.instances[i];var map=MapTree(batch.template,root);Func<string,UnityEngine.Object> resolver=id=>resolve(map,id);
                var state=UnityPreviewState.Read(row.previewState,resolver);var colors=(row.extraOperations??Array.Empty<ColorOperation>()).Select(op=>ReadColor(op,resolve,map)).ToArray();
                return new InstanceReadback{instanceId=row.instanceId,state=state,colors=colors,verified=state.verified&&colors.All(x=>x.verified)};}).ToArray();
            return new Readback{schema="monkey-prefab-preview-clone-readback/1",sourcePrefabId=batch.sourcePrefabId,
                cloneSpecSha256=batch.cloneSpecSha256,sourcePlanSha256=batch.sourcePlanSha256,cloneCount=roots.Count,applied=true,
                verified=readbacks.All(x=>x.verified)&&layout.verified,businessBehaviorComplete=false,layout=layout,instances=readbacks,
                gaps=layout.verified?Array.Empty<string>():new[]{"native_layout_readback_mismatch"}};
        } catch {
            foreach(var clone in added)if(clone!=null)UnityEngine.Object.DestroyImmediate(clone);
            if(template!=null){template.SetActive(oldActive);if(external&&!append&&template.transform.parent==parent.transform)template.transform.SetParent(null,false);
                else if(!external&&template.transform.parent!=parent.transform)template.transform.SetParent(parent.transform,false);}
            if(placeholder!=null){placeholder.transform.SetParent(parent.transform,false);placeholder.SetActive(oldPlaceholderActive);}
            if(parentLayout!=null)parentLayout.enabled=oldLayoutEnabled;
            if(!manual)settleLayout(parent);throw;
        }
    }

    public static Readback Read(CloneBatch batch, IDictionary<string,GameObject> sourceNodes,
        CloneResolver resolve, Action<GameObject> settleLayout)
    {
        bool manual=batch.template.layoutMode=="source-manual";
        bool append=batch.template.placementMode=="append-external";
        Validate(batch,sourceNodes,true);
        Require(resolve!=null&&(manual||settleLayout!=null),"PREVIEW_CLONE_CALLBACK_REQUIRED");
        var parent=sourceNodes[batch.template.parentSourceId];
        Require(parent.transform.childCount==batch.template.expectedChildCount,"PREVIEW_CLONE_SAVED_CHILD_COUNT_MISMATCH");
        GameObject[] roots;
        if(append) {
            Require(batch.template.initialChildSourceIds.Select((id,index)=>sourceNodes[id].transform==parent.transform.GetChild(index)).All(x=>x),
                "PREVIEW_CLONE_SAVED_SOURCE_CHILD_PREFIX_MISMATCH");
            roots=Enumerable.Range(batch.template.appendStartSiblingIndex,batch.instances.Length).Select(i=>parent.transform.GetChild(i).gameObject).ToArray();
            if(manual&&batch.template.layoutComponentSourceId!=null) {
                var sourceLayout=parent.GetComponent<UnityEngine.UI.LayoutGroup>();
                Require(sourceLayout!=null&&!sourceLayout.enabled,"PREVIEW_CLONE_SOURCE_MANUAL_LAYOUT_MUST_BE_DISABLED");
            }
        } else if(manual) {
            var template=sourceNodes[batch.template.rootSourceId];
            Require(parent.transform.GetChild(0).gameObject==template&&!template.activeSelf,"PREVIEW_CLONE_SOURCE_MANUAL_TEMPLATE_STATE_MISMATCH");
            roots=Enumerable.Range(1,parent.transform.childCount-1).Select(i=>parent.transform.GetChild(i).gameObject).ToArray();
        } else roots=Enumerable.Range(0,parent.transform.childCount).Select(i=>parent.transform.GetChild(i).gameObject).ToArray();
        if(!manual)settleLayout(parent);var layout=Layout(batch,parent.transform,roots);
        var readbacks=roots.Select((root,i)=>{var row=batch.instances[i];var map=MapTree(batch.template,root);Func<string,UnityEngine.Object> resolver=id=>resolve(map,id);
            var state=UnityPreviewState.Read(row.previewState,resolver);var colors=(row.extraOperations??Array.Empty<ColorOperation>()).Select(op=>ReadColor(op,resolve,map)).ToArray();
            return new InstanceReadback{instanceId=row.instanceId,state=state,colors=colors,verified=state.verified&&colors.All(x=>x.verified)};}).ToArray();
        return new Readback{schema="monkey-prefab-preview-clone-readback/1",sourcePrefabId=batch.sourcePrefabId,
            cloneSpecSha256=batch.cloneSpecSha256,sourcePlanSha256=batch.sourcePlanSha256,cloneCount=roots.Length,applied=false,
            verified=readbacks.All(x=>x.verified)&&layout.verified,businessBehaviorComplete=false,layout=layout,instances=readbacks,
            gaps=layout.verified?Array.Empty<string>():new[]{"native_layout_readback_mismatch"}};
    }
}
