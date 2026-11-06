'use strict';
const assert = require('node:assert/strict');
const Module = require('node:module');
const load = Module._load;
const ownedRegistrations=[];
const ownedUndoStub={registerRoot(node){const descendants=[];const visit=current=>{for(const child of current.children||[]){descendants.push(child.name);visit(child);}};visit(node);ownedRegistrations.push({node,parent:node.parent||null,children:(node.children||[]).map(child=>child.name),descendants});return {registered:true};}};

class Vec2 { constructor(x = 0, y = 0) { if (typeof x === 'object') { this.x = x.x; this.y = x.y; } else { this.x = x; this.y = y; } } }
class Vec3 { constructor(x = 0, y = 0, z = 0) { if (typeof x === 'object') { this.x=x.x;this.y=x.y;this.z=x.z; } else { this.x=x;this.y=y;this.z=z; } } }
class Size { constructor(width=0,height=0) { this.width=width;this.height=height; } }
class UITransform {
    constructor() { this.contentSize = new Size(30, 40); this.anchorPoint = new Vec2(.5, .5); }
    setContentSize(value, height) { this.contentSize = typeof value === 'number' ? new Size(value,height) : new Size(value.width,value.height); }
    setAnchorPoint(value) { this.anchorPoint = new Vec2(value.x, value.y); }
}
class Component { constructor(node) { this.node=node;this.enabled=true; } }
class Canvas extends Component { constructor(node){super(node);this.alignCanvasWithScreen=true;} }
class Layout {
    constructor(node) { this.node=node;this.enabled=true;this.type=0;this.resizeMode=0;this.cellSize=new Size(40,40);this.paddingLeft=0;this.paddingBottom=0;this.paddingRight=0;this.paddingTop=0;this.spacingX=0;this.spacingY=0;this.startAxis=0;this.horizontalDirection=0;this.verticalDirection=1;this.affectedByScale=false;this.updateCount=0;node.ui.contentSize=new Size(999,999); }
    updateLayout(force) { assert.equal(force,true);this.updateCount++; }
}
class Widget {
    constructor(node) { this.node=node;this.enabled=true;this.target=null;this.alignMode=1;this.alignFlags=0;this.left=0;this.bottom=0;this.right=0;this.top=0;this.isAbsoluteLeft=true;this.isAbsoluteBottom=true;this.isAbsoluteRight=true;this.isAbsoluteTop=true;this.horizontalCenter=0;this.verticalCenter=0;this.isAbsoluteHorizontalCenter=true;this.isAbsoluteVerticalCenter=true;this.updateCount=0; }
    updateAlignment() { this.updateCount++; }
}
class LayoutSlot {}
class WidgetSlot {}
class Marker { constructor(node) { this.node=node;this.layouts=[];this.widget=null; } }
class Node {
    constructor(id) { this.id=id;this.name=id;this.position=new Vec3(1,2,3);this.scale=new Vec3(1,-1,1);this.ui=new UITransform();this.components=[this.ui];this.active=true;this._parent=null;this.children=[]; }
    get parent(){return this._parent;}
    set parent(value){if(this._parent){const index=this._parent.children.indexOf(this);if(index>=0)this._parent.children.splice(index,1);}this._parent=value||null;if(this._parent&&!this._parent.children.includes(this))this._parent.children.push(this);}
    getComponent(type) { return this.components.find(row => row instanceof type) || null; }
    getComponents(type) { return this.components.filter(row => row instanceof type); }
    addComponent(type) { const row=new type(this);this.components.push(row);return row; }
    get activeInHierarchy() { return this.active && !!this.parent && this.parent.activeInHierarchy; }
    setPosition(value) { this.position=new Vec3(value.x,value.y,value.z); }
    setScale(value) { this.scale=new Vec3(value.x,value.y,value.z); }
    setRotation(value) { this.rotation=value; }
}
class Scene extends Node {
    constructor(name){super(name);this.active=false;this.activated=false;this.loaded=false;}
    _load(){this.loaded=true;}
    _activate(value){this.activated=value!==false;this.active=this.activated;}
    get activeInHierarchy(){return this.activated;}
    destroy(){this._activate(false);for(const child of [...this.children])child.parent=null;}
}
const classNames = { MonkeyStaticLayoutCompletion: Marker, MonkeyStaticLayoutSlot: LayoutSlot, MonkeyStaticWidgetSlot: WidgetSlot };
const cc = { UITransform, Layout, Widget, Canvas, Scene, Node, Layers:{Enum:{UI_2D:1}}, Vec2, Vec3, Size,
    js: { getClassByName(name) { return classNames[name]; } } };
Module._load = function (request, parent, isMain) { if (request === 'cc') return cc; if (request === './owned-import-undo.js' && /CreatorStaticLayoutCompletion\.js$/.test(parent.filename)) return ownedUndoStub; return load.call(this, request, parent, isMain); };

const helper = require('../src/monkey/targets/CreatorStaticLayoutCompletion.js');
const node = new Node('layout-owner');
const nodes = new Map([['node:0', node]]);
const plan = { nodes: [{ sourceNodeId: 'node:0', layouts: [
    { sourceComponentId: 'c:layout-second', componentOrder: 2, sourceEnabled: false,
        layoutType: 2, resize: 0, startAxis: 0, horizontalDirection: 0, verticalDirection: 1, spacingXY: [0, 7], padding: [0, 0, 0, 5], cellSize: [40, 40],
        affectedByScale: false, sourceFieldPresence: {}, unknownSourceFields: [], sourceLayoutCacheSizeKnown: false,
        fieldValues: {layoutType:2,resize:0,spacingXY:[0,7],padding:[0,0,0,5],cellSize:[40,40],startAxis:0,horizontalDirection:0,verticalDirection:1,affectedByScale:false,sourceLayoutCacheSizeKnown:false,sourceLayoutCacheSize:null} },
    { sourceComponentId: 'c:layout-first', componentOrder: 0, sourceEnabled: true,
        layoutType: 1, resize: 0, startAxis: 0, horizontalDirection: 0, verticalDirection: 1, spacingXY: [4, 0], padding: [-2.5, 0, 3, 0], cellSize: [40, 40],
        affectedByScale: true, sourceFieldPresence: {}, unknownSourceFields: [], sourceLayoutCacheSizeKnown: false,
        fieldValues: {layoutType:1,resize:0,spacingXY:[4,0],padding:[-2.5,0,3,0],cellSize:[40,40],startAxis:0,horizontalDirection:0,verticalDirection:1,affectedByScale:true,sourceLayoutCacheSizeKnown:false,sourceLayoutCacheSize:null} }
], widgets: [{ sourceComponentId: 'c:widget', componentOrder: 1, sourceEnabled: true,
    alignFlags: 4, alignMode: 1, margins: [0,-6,0,0], absolute: [true,true,true,true], center: [0,0],
    centerAbsolute: [true,true], targetSourceNodeId: null, targetUsesParentWhenNull: true, sourceOriginalSize: [0,25],
    sourceOriginalWidthKnown: false, sourceOriginalHeightKnown: true, sourceFieldPresence: {}, unknownSourceFields: [],
    fieldValues: {alignFlags:4,margins:[0,-6,0,0],absolute:[true,true,true,true],center:[0,0],centerAbsolute:[true,true],alignMode:1,targetUsesParentWhenNull:true,targetSourceNodeId:null,sourceOriginalSize:[0,25]} }
]}] };
const initialPosition = new Vec3(node.position.x,node.position.y,node.position.z), initialScale = new Vec3(node.scale.x,node.scale.y,node.scale.z);
const initialSize = new Size(node.ui.contentSize.width,node.ui.contentSize.height), initialAnchor = new Vec2(node.ui.anchorPoint.x,node.ui.anchorPoint.y);
helper.attach(plan, nodes);
assert.deepEqual(node.components.map(x => x.constructor), [UITransform, Layout, Widget, Layout, Marker]);
assert.deepEqual(node.position, initialPosition);
assert.deepEqual(node.scale, initialScale);
assert.deepEqual(node.ui.contentSize, initialSize, 'Creator 3.8 UITransform size restored after component insertion');
assert.deepEqual(node.ui.anchorPoint, initialAnchor);
const result = helper.read(plan, nodes);
assert.equal(result.status, 'read');
assert.deepEqual(result.staticLayoutFields[0].layouts.map(x => x.sourceComponentId), ['c:layout-first','c:layout-second']);
assert.equal(result.staticLayoutFields[0].widgets[0].fieldValues.margins[1], -6);
assert.equal(result.staticLayoutFields[0].layouts[0].sourceEnabled, true);
const probePlan={designSize:[640,960],nodes:[{sourceId:'node:0',parent:null,children:[]}],layoutCompletion:{nodes:[{sourceNodeId:'node:0',layouts:[plan.nodes[0].layouts[1],plan.nodes[0].layouts[0]],widgets:plan.nodes[0].widgets}]}};
const ownedStart=ownedRegistrations.length;
const probe=helper.probe(probePlan,nodes);
const probeOwnership=ownedRegistrations.slice(ownedStart);
assert.deepEqual(probeOwnership.slice(0,3).map(row=>row.node.name),['StaticLayoutProbeScene','StaticLayoutProbeCanvas','StaticLayoutProbeDesignRoot']);
assert.ok(probeOwnership.slice(0,3).every(row=>row.parent===null),'each generated root is registered immediately before parenting');
assert.equal(probeOwnership[3].node.name,'StaticLayoutProbeScene');
assert.ok(probeOwnership[3].children.includes('StaticLayoutProbeCanvas'),'scene is re-registered after activation to adopt its context');
assert.ok(probeOwnership[3].descendants.includes('layout-owner'),'scene is re-registered after activation to adopt the full clone tree');
assert.equal(probe.status,'probe_captured');
assert.equal(probe.baselineInitialized,true);
assert.equal(probe.baselineIsConstraintProof,false);
assert.equal(probe.sceneInitialized,true);
assert.deepEqual(probe.nodes[0].input.size,[initialSize.width+17,initialSize.height+11]);
assert.deepEqual(node.getComponents(Layout).map(x=>x.updateCount),[2,0]);
assert.equal(node.getComponent(Widget).updateCount,2);
const activate=Scene.prototype._activate;
Scene.prototype._activate=function(value){if(value===false){this.activated=false;this.active=false;}};
assert.throws(()=>helper.probe(probePlan,nodes),/STATIC_LAYOUT_PROBE_OWNER_NOT_ACTIVE_IN_HIERARCHY/);
Scene.prototype._activate=activate;

// Source-mapped children remain the only Layout denominator. A generated proxy
// without UITransform is not an input; an unmapped active UI child is rejected.
const sourceOwner=new Node('source-owner'),sourceChild=new Node('source-child');sourceChild.parent=sourceOwner;
const sourceMap=new Map([['owner',sourceOwner],['child',sourceChild]]);
const sourceLayoutPlan={designSize:[640,960],sourceNodes:[
    {sourceId:'owner',parent:null,children:['child']},{sourceId:'child',parent:'owner',children:[]}],
    layoutCompletion:{nodes:[{sourceNodeId:'owner',layouts:[plan.nodes[0].layouts[1]],widgets:[]}]}};
helper.attach(sourceLayoutPlan.layoutCompletion,sourceMap);
const proxyWithoutUi=new Node('generated-sort-proxy');proxyWithoutUi.components=[];proxyWithoutUi.ui=null;proxyWithoutUi.parent=sourceOwner;
const sourceProbe=helper.probe(sourceLayoutPlan,sourceMap);
assert.deepEqual(sourceProbe.nodes.find(row=>row.sourceNodeId==='owner').before.childrenSourceNodeIds,['child']);
assert.deepEqual(sourceProbe.layoutParticipation[0].effectiveChildSourceNodeIds,['child']);
assert.equal(sourceProbe.status,'probe_captured');
const unknownUiChild=new Node('unmapped-ui-child');unknownUiChild.parent=sourceOwner;
assert.throws(()=>helper.probe(sourceLayoutPlan,sourceMap),/STATIC_LAYOUT_PROBE_UNMAPPED_UI_LAYOUT_CHILD/);
unknownUiChild.parent=null;
proxyWithoutUi.parent=null;

node.getComponent(Marker).sourceNodeId = 'wrong-node';
assert.throws(() => helper.read(plan, nodes), /STATIC_LAYOUT_MARKER_MISSING_OR_WRONG_NODE/);
node.getComponent(Marker).sourceNodeId = 'node:0';
node.getComponent(Widget).alignFlags = 8;
assert.throws(() => helper.read(plan, nodes), /STATIC_LAYOUT_FIELD_MISMATCH/);
