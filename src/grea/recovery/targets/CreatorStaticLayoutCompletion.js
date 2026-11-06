'use strict';
// Attach real Creator 2.4 cc.Layout / cc.Widget components. The typed marker only
// records source identity/order and owns references; it is not a JSON carrier.
const cc = require('cc');
const ownedUndo = require('./owned-import-undo.js');

function markerClass() {
    const type = cc.js && cc.js.getClassByName && cc.js.getClassByName('MonkeyStaticLayoutCompletion');
    if (!type) throw new Error('STATIC_LAYOUT_TYPED_MARKER_CLASS_MISSING');
    return type;
}
function requireMap(map, id, code) {
    const node = map instanceof Map ? map.get(id) : map && map[id];
    if (!node) throw new Error(`${code}:${id}`);
    return node;
}
function mapHas(map, id) { return map instanceof Map ? map.has(id) : !!(map && Object.prototype.hasOwnProperty.call(map, id)); }
function mapEntries(map) { return map instanceof Map ? [...map.entries()] : Object.entries(map || {}); }
function mappedSourceChildIds(node, reverse) { return (node.children || []).filter(child => reverse.has(child)).map(child => reverse.get(child)); }
function capturePose(nodes) {
    const rows = [];
    const entries = nodes instanceof Map ? [...nodes.entries()] : Object.entries(nodes || {});
    for (const [id, node] of entries) {
        const ui = node && node.getComponent && node.getComponent(cc.UITransform);
        if (!node || !ui || !node.position || !node.scale) continue;
        rows.push({ id, node, ui, position: new cc.Vec3(node.position.x, node.position.y, node.position.z),
            scale: new cc.Vec3(node.scale.x, node.scale.y, node.scale.z),
            size: new cc.Size(ui.contentSize.width, ui.contentSize.height),
            anchor: new cc.Vec2(ui.anchorPoint.x, ui.anchorPoint.y) });
    }
    return rows;
}
function restorePose(snapshot) {
    for (const row of snapshot || []) {
        row.node.setPosition(row.position);
        row.node.setScale(row.scale);
        row.ui.setContentSize(row.size);
        row.ui.setAnchorPoint(row.anchor);
    }
}
function assignLayout(comp, spec) {
    comp.enabled = false;
    comp.type = spec.layoutType;
    comp.resizeMode = spec.resize;
    comp.cellSize = new cc.Size(spec.cellSize[0], spec.cellSize[1]);
    [comp.paddingLeft, comp.paddingBottom, comp.paddingRight, comp.paddingTop] = spec.padding;
    [comp.spacingX, comp.spacingY] = spec.spacingXY;
    comp.startAxis = spec.startAxis;
    comp.horizontalDirection = spec.horizontalDirection;
    comp.verticalDirection = spec.verticalDirection;
    comp.affectedByScale = spec.affectedByScale;
    // Preserve source cache dimensions as typed native fields where available;
    // this is provenance only and never used as proof of the constraint result.
    comp.enabled = spec.sourceEnabled;
}
function assignWidget(comp, spec, nodes) {
    comp.enabled = false;
    comp.target = spec.targetSourceNodeId ? requireMap(nodes, spec.targetSourceNodeId, 'STATIC_LAYOUT_WIDGET_TARGET_MISSING') : null;
    comp.alignMode = spec.alignMode;
    comp.alignFlags = spec.alignFlags;
    [comp.left, comp.bottom, comp.right, comp.top] = spec.margins;
    [comp.isAbsoluteLeft, comp.isAbsoluteBottom, comp.isAbsoluteRight, comp.isAbsoluteTop] = spec.absolute;
    [comp.horizontalCenter, comp.verticalCenter] = spec.center;
    [comp.isAbsoluteHorizontalCenter, comp.isAbsoluteVerticalCenter] = spec.centerAbsolute;
    comp.enabled = spec.sourceEnabled;
}
function copyLayoutSlot(dst, spec, comp) {
    Object.assign(dst, {
        sourceComponentId: spec.sourceComponentId, componentOrder: spec.componentOrder,
        sourceEnabled: spec.sourceEnabled, layoutType: spec.layoutType, resize: spec.resize,
        startAxis: spec.startAxis || 0, horizontalDirection: spec.horizontalDirection || 0,
        verticalDirection: spec.verticalDirection == null ? 1 : spec.verticalDirection,
        affectedByScale: spec.affectedByScale, paddingLeft: spec.padding[0], paddingBottom: spec.padding[1],
        paddingRight: spec.padding[2], paddingTop: spec.padding[3], spacingX: spec.spacingXY[0],
        spacingY: spec.spacingXY[1], cellWidth: spec.cellSize[0], cellHeight: spec.cellSize[1],
        hasSourceLayoutCacheSize: spec.sourceLayoutCacheSizeKnown === true,
        sourceLayoutCacheWidth: spec.sourceLayoutCacheSize ? spec.sourceLayoutCacheSize[0] : 0,
        sourceLayoutCacheHeight: spec.sourceLayoutCacheSize ? spec.sourceLayoutCacheSize[1] : 0,
        nativeLayout: comp, sourceFieldPresence: spec.sourceFieldPresence || [],
        unknownSourceFields: spec.unknownSourceFields || []
    });
}
function copyWidgetSlot(dst, spec, comp) {
    Object.assign(dst, {
        sourceComponentId: spec.sourceComponentId, componentOrder: spec.componentOrder,
        sourceEnabled: spec.sourceEnabled, alignFlags: spec.alignFlags, alignMode: spec.alignMode,
        left: spec.margins[0], bottom: spec.margins[1], right: spec.margins[2], top: spec.margins[3],
        isAbsLeft: spec.absolute[0], isAbsBottom: spec.absolute[1], isAbsRight: spec.absolute[2], isAbsTop: spec.absolute[3],
        horizontalCenter: spec.center[0], verticalCenter: spec.center[1],
        isAbsHorizontalCenter: spec.centerAbsolute[0], isAbsVerticalCenter: spec.centerAbsolute[1],
        originalWidth: spec.sourceOriginalSize[0] || 0, originalHeight: spec.sourceOriginalSize[1] || 0,
        hasOriginalWidth: spec.sourceOriginalWidthKnown, hasOriginalHeight: spec.sourceOriginalHeightKnown,
        targetUsesParentWhenNull: spec.targetUsesParentWhenNull === true,
        targetSourceNodeId: spec.targetSourceNodeId || '',
        nativeWidget: comp, sourceFieldPresence: spec.sourceFieldPresence || [],
        unknownSourceFields: spec.unknownSourceFields || []
    });
}
function sameValue(a, b) {
    if (a === b) return true;
    if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((v, i) => sameValue(v, b[i]));
    if (a && b && typeof a === 'object' && typeof b === 'object') {
        const ak = Object.keys(a).sort(), bk = Object.keys(b).sort();
        return sameValue(ak, bk) && ak.every(key => sameValue(a[key], b[key]));
    }
    return false;
}
function attach(plan, nodes) {
    const snapshots = capturePose(nodes);
    const reverse=new Map();
    for(const [sourceId,node] of mapEntries(nodes))reverse.set(node,sourceId);
    try {
        for (const nodeSpec of plan.nodes || []) {
            if (!mapHas(nodes, nodeSpec.sourceNodeId)) continue;
            const node = requireMap(nodes, nodeSpec.sourceNodeId, 'STATIC_LAYOUT_NODE_MISSING');
            const layouts = [];
            let widget = null;
            const ordered = [...(nodeSpec.layouts || []).map(slot => ({ kind: 'layout', slot })),
                ...(nodeSpec.widgets || []).map(slot => ({ kind: 'widget', slot }))]
                .sort((a, b) => a.slot.componentOrder - b.slot.componentOrder);
            for (const row of ordered) {
                if (row.kind === 'layout') {
                    const comp = node.addComponent(cc.Layout);
                    assignLayout(comp, row.slot);
                    layouts.push({ slot: row.slot, comp });
                } else {
                    if (widget) throw new Error(`STATIC_LAYOUT_WIDGET_MULTIPLE_ON_NODE:${nodeSpec.sourceNodeId}`);
                    const comp = node.addComponent(cc.Widget);
                    assignWidget(comp, row.slot, nodes);
                    widget = { slot: row.slot, comp };
                }
            }
            const marker = node.addComponent(markerClass());
            marker.sourceNodeId = nodeSpec.sourceNodeId;
            marker.sourceChildNodeIds = mappedSourceChildIds(node,reverse);
            marker.layouts = layouts.sort((a, b) => a.slot.componentOrder - b.slot.componentOrder).map(({ slot, comp }) => {
                const instance = new (cc.js.getClassByName('MonkeyStaticLayoutSlot'))();
                copyLayoutSlot(instance, slot, comp); return instance;
            });
            if (widget) {
                const instance = new (cc.js.getClassByName('MonkeyStaticWidgetSlot'))();
                copyWidgetSlot(instance, widget.slot, widget.comp); marker.widget = instance;
            }
        }
    } finally {
        // Layout/Widget may recalculate immediately in editor contexts. The authored
        // prefab pose is retained; initialization is verified separately on a clone.
        restorePose(snapshots);
    }
    return { status: 'attached', nodes: (plan.nodes || []).filter(row => mapHas(nodes,row.sourceNodeId)).length, initialPoseRestored: true };
}
function read(plan, nodes) {
    const result = [];
    const reverse=new Map();for(const [sourceId,node] of mapEntries(nodes))reverse.set(node,sourceId);
    for (const nodeSpec of plan.nodes || []) {
        if (!mapHas(nodes, nodeSpec.sourceNodeId)) continue;
        const node = requireMap(nodes, nodeSpec.sourceNodeId, 'STATIC_LAYOUT_READ_NODE_MISSING');
        const Marker = markerClass();
        const marker = node.getComponent(Marker);
        if (!marker || marker.sourceNodeId !== nodeSpec.sourceNodeId) throw new Error(`STATIC_LAYOUT_MARKER_MISSING_OR_WRONG_NODE:${nodeSpec.sourceNodeId}`);
        const mappedChildren=mappedSourceChildIds(node,reverse);
        if(!sameValue(marker.sourceChildNodeIds||[],mappedChildren))
            throw new Error(`STATIC_LAYOUT_SOURCE_CHILD_IDENTITY_DIFFERS:${nodeSpec.sourceNodeId}`);
        const layouts = marker.layouts || [];
        const widgets = marker.widget ? [marker.widget] : [];
        const readSlots = (kind, expected, actual) => {
            expected = [...expected].sort((a, b) => a.componentOrder - b.componentOrder);
            if (expected.length !== actual.length) throw new Error(`STATIC_LAYOUT_${kind.toUpperCase()}_COUNT_MISMATCH:${nodeSpec.sourceNodeId}`);
            return expected.map((slot, i) => {
                const row = actual[i];
                if (!row || row.sourceComponentId !== slot.sourceComponentId || row.componentOrder !== slot.componentOrder)
                    throw new Error(`STATIC_LAYOUT_${kind.toUpperCase()}_IDENTITY_ORDER_MISMATCH:${slot.sourceComponentId}`);
                const comp = kind === 'layouts' ? row.nativeLayout : row.nativeWidget;
                if (!comp) throw new Error(`STATIC_LAYOUT_NATIVE_REFERENCE_MISSING:${slot.sourceComponentId}`);
                const actualComponents = node.getComponents(kind === 'layouts' ? cc.Layout : cc.Widget) || [];
                if (!actualComponents.includes(comp)) throw new Error(`STATIC_LAYOUT_NATIVE_COMPONENT_NOT_ATTACHED:${slot.sourceComponentId}`);
                if (kind === 'widgets') {
                    const expectedTarget = slot.targetSourceNodeId ? requireMap(nodes, slot.targetSourceNodeId, 'STATIC_LAYOUT_WIDGET_TARGET_MISSING') : null;
                    if (comp.target !== expectedTarget) throw new Error(`STATIC_LAYOUT_WIDGET_TARGET_REFERENCE_MISMATCH:${slot.sourceComponentId}`);
                }
                const fieldValues = kind === 'layouts' ? layoutFieldValues(comp, row) : widgetFieldValues(comp, row);
                if (comp.enabled !== row.sourceEnabled)
                    throw new Error(`STATIC_LAYOUT_ENABLED_MISMATCH:${slot.sourceComponentId}`);
                if (!sameValue(fieldValues, slot.fieldValues))
                    throw new Error(`STATIC_LAYOUT_FIELD_MISMATCH:${slot.sourceComponentId}:${JSON.stringify({expected:slot.fieldValues,actual:fieldValues})}`);
                if (!sameValue(row.sourceFieldPresence || [], slot.sourceFieldPresence || []) ||
                    !sameValue(row.unknownSourceFields || [], slot.unknownSourceFields || []))
                    throw new Error(`STATIC_LAYOUT_SOURCE_FIELD_PRESENCE_MISMATCH:${slot.sourceComponentId}`);
                return { sourceComponentId: row.sourceComponentId, componentOrder: row.componentOrder,
                    sourceEnabled: comp.enabled, nativeComponentPresent: true, savedReferenceVerified: true,
                    sourceFieldPresence: row.sourceFieldPresence || [], unknownSourceFields: row.unknownSourceFields || [], fieldValues };
            });
        };
        result.push({ sourceNodeId: nodeSpec.sourceNodeId,
            layouts: readSlots('layouts', nodeSpec.layouts || [], layouts),
            widgets: readSlots('widgets', nodeSpec.widgets || [], widgets) });
    }
    return { staticLayoutFields: result, status: 'read' };
}
function probe(plan, nodes) {
    if (!(nodes instanceof Map)) throw new Error('STATIC_LAYOUT_PROBE_NODE_MAP_REQUIRED');
    const sourceById = new Map((plan.sourceNodes || plan.nodes || []).map(row => [row.sourceId, row]));
    const reverse = new Map();
    for (const [sourceId, node] of nodes) {
        if (reverse.has(node)) throw new Error(`STATIC_LAYOUT_PROBE_NODE_MAPPING_AMBIGUOUS:${sourceId}`);
        reverse.set(node, sourceId);
    }
    const geometry = node => {
        const sourceId = reverse.get(node), source = sourceById.get(sourceId);
        if (!source || !sourceId) throw new Error(`STATIC_LAYOUT_PROBE_SOURCE_NODE_MISSING:${sourceId || node.name}`);
        const ui = node.getComponent(cc.UITransform);
        if (!ui) throw new Error(`STATIC_LAYOUT_PROBE_UI_TRANSFORM_MISSING:${sourceId}`);
        return {
            sourceNodeId: sourceId, parentSourceNodeId: source.parent || null,
            childrenSourceNodeIds: (source.children || []).filter(id => nodes.has(id)),
            activeSelf: node.active === true, activeInHierarchy: node.activeInHierarchy === true,
            position: [node.position.x,node.position.y,node.position.z],
            size: [ui.contentSize.width,ui.contentSize.height],
            anchor: [ui.anchorPoint.x,ui.anchorPoint.y],
            scale: [node.scale.x,node.scale.y,node.scale.z],
        };
    };
    const scene = new cc.Scene('StaticLayoutProbeScene');
    ownedUndo.registerRoot(scene);
    let initialized = false;
    const roots = [...nodes].filter(([id]) => {
        const source=sourceById.get(id);return !source || !source.parent || !nodes.has(source.parent);
    }).map(([,node])=>node);
    try {
        const canvasNode=new cc.Node('StaticLayoutProbeCanvas');
        ownedUndo.registerRoot(canvasNode);
        canvasNode.layer=cc.Layers.Enum.UI_2D;canvasNode.parent=scene;
        canvasNode.addComponent(cc.UITransform).setContentSize(...plan.designSize);
        const canvas=canvasNode.addComponent(cc.Canvas);canvas.alignCanvasWithScreen=false;
        const design=new cc.Node('StaticLayoutProbeDesignRoot');ownedUndo.registerRoot(design);design.layer=cc.Layers.Enum.UI_2D;design.parent=canvasNode;
        design.addComponent(cc.UITransform).setContentSize(...plan.designSize);
        design.getComponent(cc.UITransform).setAnchorPoint(0,0);
        design.setPosition(-plan.designSize[0]/2,-plan.designSize[1]/2,0);
        for(const root of roots)root.parent=design;
        const specs=plan.layoutCompletion&&plan.layoutCompletion.nodes||[];
        const owners=specs.filter(spec=>nodes.has(spec.sourceNodeId));
        const layoutOwners=owners.filter(spec=>(spec.layouts||[]).some(slot=>slot.sourceEnabled===true));
        for(const spec of layoutOwners){
            const node=nodes.get(spec.sourceNodeId),source=sourceById.get(spec.sourceNodeId),marker=node.getComponent(markerClass());
            if(!marker||marker.sourceNodeId!==spec.sourceNodeId)throw new Error(`STATIC_LAYOUT_PROBE_MARKER_MISSING:${spec.sourceNodeId}`);
            const expected=(source.children||[]).filter(id=>nodes.has(id));
            if(!sameValue(marker.sourceChildNodeIds||[],expected)||!sameValue(mappedSourceChildIds(node,reverse),expected))
                throw new Error(`STATIC_LAYOUT_PROBE_SOURCE_CHILD_MAP_DIFFERS:${spec.sourceNodeId}`);
            for(const child of node.children||[]){
                if(reverse.has(child)||!child.active||!child.getComponent(cc.UITransform))continue;
                throw new Error(`STATIC_LAYOUT_PROBE_UNMAPPED_UI_LAYOUT_CHILD:${spec.sourceNodeId}:${child.uuid||child.name}`);
            }
        }
        for(const spec of owners){
            const node=nodes.get(spec.sourceNodeId);
            for(let current=node;current&&reverse.has(current);current=current.parent)current.active=true;
        }
        scene._load();scene._activate(true);initialized=true;
        // Re-register after attachment/activation so the owned scope adopts the
        // complete disposable tree, including imported clone descendants.
        ownedUndo.registerRoot(scene);
        for(const spec of owners){
            const node=nodes.get(spec.sourceNodeId);
            if(node.activeInHierarchy!==true)throw new Error(`STATIC_LAYOUT_PROBE_OWNER_NOT_ACTIVE_IN_HIERARCHY:${spec.sourceNodeId}`);
        }
        // Establish a settled native baseline after scene activation. Existing
        // layout components may adjust related nodes during initialization; the
        // baseline records that state but is never used as proof of correctness.
        const baselineNodes=[...nodes].sort((a,b)=>nodeDepth(a[1])-nodeDepth(b[1])||a[0].localeCompare(b[0]));
        for(const [,node] of baselineNodes){
            const layout=node.getComponent(cc.Layout);
            if(layout&&layout.enabled&&typeof layout.updateLayout==='function')layout.updateLayout(true);
            const widget=node.getComponent(cc.Widget);
            if(widget&&widget.enabled&&typeof widget.updateAlignment==='function')widget.updateAlignment();
        }
        for(const spec of owners){
            const node=nodes.get(spec.sourceNodeId);
            if(node.activeInHierarchy!==true)throw new Error(`STATIC_LAYOUT_PROBE_OWNER_NOT_ACTIVE_IN_HIERARCHY:${spec.sourceNodeId}`);
        }
        // Lifecycle and baseline initialization have completed. The input pose is captured and
        // changed synchronously; no frame/timer runs between it and native calls.
        const before=new Map([...nodes].map(([id,node])=>[id,geometry(node)]));
        for(const spec of owners){
            const node=nodes.get(spec.sourceNodeId),ui=node.getComponent(cc.UITransform),authored=before.get(spec.sourceNodeId);
            ui.setContentSize(authored.size[0]+17,authored.size[1]+11);
        }
        const input=new Map([...nodes].map(([id,node])=>[id,geometry(node)]));
        const orderedNodes=[...owners].sort((a,b)=>nodeDepth(nodes.get(a.sourceNodeId))-nodeDepth(nodes.get(b.sourceNodeId))||a.sourceNodeId.localeCompare(b.sourceNodeId));
        const appliedSourceComponentIds=[],layoutParticipation=[];
        for(const nodeSpec of orderedNodes){
            const node=nodes.get(nodeSpec.sourceNodeId),marker=node.getComponent(markerClass());
            if(!marker||marker.sourceNodeId!==nodeSpec.sourceNodeId)throw new Error(`STATIC_LAYOUT_PROBE_MARKER_MISSING:${nodeSpec.sourceNodeId}`);
            const work=[...(marker.layouts||[]).map(slot=>({kind:'layout',slot})),...(marker.widget?[{kind:'widget',slot:marker.widget}]:[])]
                .sort((a,b)=>a.slot.componentOrder-b.slot.componentOrder);
            for(const row of work){
                if(!row.slot.sourceEnabled)continue;
                if(row.kind==='layout'){
                    const component=row.slot.nativeLayout;
                    if(!component||component.node!==node||typeof component.updateLayout!=='function')throw new Error(`STATIC_LAYOUT_PROBE_NATIVE_LAYOUT_INVALID:${row.slot.sourceComponentId}`);
                    const effectiveChildSourceNodeIds=(marker.sourceChildNodeIds||[]).filter(childId=>{
                        const child=nodes.get(childId);return !!child&&child.activeInHierarchy&&child.getComponent(cc.UITransform);
                    });
                    component.updateLayout(true);
                    layoutParticipation.push({sourceComponentId:row.slot.sourceComponentId,ownerSourceNodeId:nodeSpec.sourceNodeId,
                        layoutType:row.slot.layoutType,algorithmInvoked:[0,1,2].includes(row.slot.layoutType)&&[0,1,2].includes(row.slot.resize),
                        effectiveChildSourceNodeIds});
                }else{
                    const component=row.slot.nativeWidget;
                    if(!component||component.node!==node||typeof component.updateAlignment!=='function')throw new Error(`STATIC_LAYOUT_PROBE_NATIVE_WIDGET_INVALID:${row.slot.sourceComponentId}`);
                    component.updateAlignment();
                }
                appliedSourceComponentIds.push(row.slot.sourceComponentId);
            }
        }
        const actual=[...nodes].map(([sourceNodeId,node])=>({sourceNodeId,before:before.get(sourceNodeId),input:input.get(sourceNodeId),after:geometry(node)}));
        for(const sourceNodeId of owners.map(row=>row.sourceNodeId)){
            const row=actual.find(value=>value.sourceNodeId===sourceNodeId);
            if(row.input.activeInHierarchy!==true||row.input.size[0]!==row.before.size[0]+17||row.input.size[1]!==row.before.size[1]+11)
                throw new Error(`STATIC_LAYOUT_PROBE_INPUT_NOT_ACTIVE_OR_SIZE_DELTA_INVALID:${sourceNodeId}`);
        }
        return {phase:'initialized-disposable-clone',status:'probe_captured',sceneInitialized:true,
            baselineInitialized:true,baselineIsConstraintProof:false,
            disposableCloneRequired:true,persistentPrefabMutated:false,
            appliedSourceComponentIds:[...new Set(appliedSourceComponentIds)].sort(),layoutParticipation,nodes:actual};
    } finally {
        if(initialized)scene._activate(false);
        for(const root of roots)if(root.parent)root.parent=null;
        scene.destroy();
    }
}
function nodeDepth(node){let depth=0;for(let current=node;current;current=current.parent)depth++;return depth;}
function layoutFieldValues(comp, slot) {
    return { layoutType: comp.type, resize: comp.resizeMode, spacingXY: [comp.spacingX, comp.spacingY],
        padding: [comp.paddingLeft, comp.paddingBottom, comp.paddingRight, comp.paddingTop],
        cellSize: [comp.cellSize.width, comp.cellSize.height], startAxis: comp.startAxis,
        horizontalDirection: comp.horizontalDirection, verticalDirection: comp.verticalDirection,
        affectedByScale: comp.affectedByScale, sourceLayoutCacheSizeKnown: slot.hasSourceLayoutCacheSize === true,
        sourceLayoutCacheSize: slot.hasSourceLayoutCacheSize ?
            [slot.sourceLayoutCacheWidth, slot.sourceLayoutCacheHeight] : null };
}
function widgetFieldValues(comp, slot) {
    const targetSourceNodeId = slot.targetSourceNodeId || null;
    return { alignFlags: comp.alignFlags, margins: [comp.left, comp.bottom, comp.right, comp.top],
        absolute: [comp.isAbsoluteLeft, comp.isAbsoluteBottom, comp.isAbsoluteRight, comp.isAbsoluteTop],
        center: [comp.horizontalCenter, comp.verticalCenter],
        centerAbsolute: [comp.isAbsoluteHorizontalCenter, comp.isAbsoluteVerticalCenter],
        alignMode: comp.alignMode, targetUsesParentWhenNull: slot.targetUsesParentWhenNull === true, targetSourceNodeId,
        sourceOriginalSize: [slot.hasOriginalWidth ? slot.originalWidth : 0, slot.hasOriginalHeight ? slot.originalHeight : 0] };
}
module.exports = { attach, read, probe, capturePose, restorePose };
