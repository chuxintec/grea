'use strict';
const assert = require('assert');
const Module = require('module');
const load = Module._load;
const ownedRegistrations=[];
const ownedUndoStub={registerRoot(node){const descendants=[];const visit=current=>{for(const child of current.children||[]){descendants.push(child.name);visit(child);}};visit(node);ownedRegistrations.push({node,parent:node.parent||null,children:(node.children||[]).map(child=>child.name),descendants});return {registered:true};}};

class BitmapFont { constructor(dict){this.fntConfig={fontDefDictionary:dict};this._uuid='font-uuid';} }
class Label {
    constructor(node,font,string,enabled=true){this.node=node;this.font=font;this.string=string;this.enabled=enabled;this.renderData={vertexCount:0,indexCount:0,vertDirty:false};this._assembler={updateRenderData:label=>{
        let visible=0;for(let i=0;i<label.string.length;i++){const code=label.string.charCodeAt(i);const glyph=label.font.fntConfig.fontDefDictionary[String(code)];if(glyph&&glyph.rect.width>0&&glyph.rect.height>0)visible++;}
        label.renderData.vertexCount=visible*4;label.renderData.indexCount=visible*6;label.renderData.vertDirty=false;
    }};}
}
class Marker {}
class UITransform {}
class Node {
    constructor(name){this.name=name;this.parent=null;this.children=[];this.active=false;this.components=[];}
    set parent(value){if(this._parent===value)return;if(this._parent)this._parent.children=this._parent.children.filter(x=>x!==this);this._parent=value;if(value&&!value.children.includes(this))value.children.push(this);}
    get parent(){return this._parent||null;}
    get activeInHierarchy(){return this.active&&(!this.parent||this.parent.activeInHierarchy);}
    addComponent(Type){const value=new Type();value.node=this;this.components.push(value);return value;}
    getComponents(Type){return this.components.filter(x=>x instanceof Type);}
    getComponent(Type){return this.getComponents(Type)[0]||null;}
}
class Scene extends Node {
    constructor(name){super(name);}
    _load(){}
    _activate(value){const walk=node=>{for(const child of node.children){child._sceneActive=value;walk(child);}};this._sceneActive=value;walk(this);}
    destroy(){this.parent=null;}
}
class CtxNode extends Node { constructor(name){super(name);} addComponent(Type){return super.addComponent(Type);} }
const classNames={MonkeyStaticBitmapMissingGlyphs:Marker};
const cc={BitmapFont,Label,UITransform,Scene,Node:CtxNode,
    js:{getClassByName(name){return classNames[name];}}};
Module._load=function(request,parent,isMain){if(request==='cc')return cc;if(request==='./owned-import-undo.js'&&/CreatorStaticBitmapMissingGlyphs\.js$/.test(parent.filename))return ownedUndoStub;return load.call(this,request,parent,isMain);};
const helper=require('../src/monkey/targets/CreatorStaticBitmapMissingGlyphs.js');
const empty={schema:'monkey-prefab-bitmap-missing-glyphs/1',status:'not_applicable',
    policy:'cocos24-bitmap-missing-glyph-skip-v1',sourceCodeEvidence:'cocos2d/core/renderer/utils/label/bmfont.js:235',
    missingGlyphsAreVisibleTextRecovered:false,components:[]};
const classlessCc={js:{getClassByName(){throw new Error('marker class must not be queried for an empty contract');}}};
assert.equal(helper.attach(empty,new Map(),new Map(),classlessCc).status,'not_applicable');
assert.deepEqual(helper.read(empty,new Map(),new Map(),new Map(),classlessCc),[]);

const font=new BitmapFont({'10':{rect:{width:0,height:0}},'65':{rect:{width:8,height:9}}});
const sourceId='asset:neutral#177/components/0',nodeId='asset:neutral#177',fontId='font:neutral';
const contract={schema:'monkey-prefab-bitmap-missing-glyphs/1',status:'source_missing_glyphs_retained_and_skipped',
    policy:'cocos24-bitmap-missing-glyph-skip-v1',sourceCodeEvidence:'cocos2d/core/renderer/utils/label/bmfont.js:235',
    missingGlyphsAreVisibleTextRecovered:false,components:[{sourceComponentId:sourceId,sourceNodeId:nodeId,sourceText:'跳过',sourceFontId:fontId,
        sourceEnabled:true,sourceGlyphUnicode:[10,65],missingGlyphUnicode:[36339,36807],displayText:'',policy:'cocos24-bitmap-missing-glyph-skip-v1',
        sourceCodeEvidence:'cocos2d/core/renderer/utils/label/bmfont.js:235',missingGlyphsAreVisibleTextRecovered:false}]};
const savedNode=new Node('txt');savedNode.active=false;const savedLabel=savedNode.addComponent(Label);savedLabel.font=font;savedLabel.string='跳过';
const persistent=new Map([[nodeId,savedNode]]),fonts=new Map([[fontId,font]]);
assert.deepEqual(helper.attach(contract,persistent,fonts,cc),{status:'attached',sourceTextMutated:false,nativeFontSubstituted:false});
assert.equal(savedLabel.string,'跳过');assert.equal(savedLabel.font,font);
assert.throws(()=>helper.read(contract,persistent,persistent,fonts,cc),/REQUIRES_DISPOSABLE_CLONE/);

const loadedNode=new Node('txt-clone');loadedNode.active=false;const loadedLabel=loadedNode.addComponent(Label);loadedLabel.font=font;loadedLabel.string='跳过';
const marker=loadedNode.addComponent(Marker);Object.assign(marker,savedNode.getComponent(Marker));marker.node=loadedNode;marker.targetLabel=loadedLabel;
const ownedStart=ownedRegistrations.length;
const rows=helper.read(contract,persistent,new Map([[nodeId,loadedNode]]),fonts,cc);
const probeOwnership=ownedRegistrations.slice(ownedStart);
assert.deepEqual(probeOwnership.slice(0,2).map(row=>row.node.name),['BitmapMissingGlyphProbeScene','BitmapMissingGlyphProbeRoot']);
assert.ok(probeOwnership.slice(0,2).every(row=>row.parent===null),'new probe scene and context are registered immediately before parenting');
assert.equal(probeOwnership[2].node.name,'BitmapMissingGlyphProbeScene');
assert.ok(probeOwnership[2].children.includes('BitmapMissingGlyphProbeRoot'),'scene is re-registered after activation to adopt its context');
assert.ok(probeOwnership[2].descendants.includes('txt-clone'),'scene is re-registered after activation to adopt the full clone tree');
assert.equal(rows.length,1);assert.equal(rows[0].sourceText,'跳过');assert.equal(rows[0].targetText,'跳过');
assert.equal(rows[0].displayText,'');assert.equal(rows[0].vertexCount,0);assert.equal(rows[0].indexCount,0);
assert.equal(rows[0].bitmapRenderDataInitialized,true);assert.equal(rows[0].missingGlyphsAreVisibleTextRecovered,false);
assert.equal(loadedLabel.string,'跳过');assert.equal(loadedLabel.font,font);
assert.deepEqual(helper.displayFor('A\rB\nC\t',[65,66,67]).missingGlyphUnicode,[9]);
assert.equal(helper.displayFor('A\rB\nC\t',[65,66,67]).displayText,'AB\nC');
assert.deepEqual(helper.displayFor('😀',[]).missingGlyphUnicode,[0xD83D,0xDE00]);

marker.missingGlyphUnicode=[36339];
assert.throws(()=>helper.read(contract,persistent,new Map([[nodeId,loadedNode]]),fonts,cc),/TYPED_FIELDS_OR_REFERENCE_DIFFERS/);
marker.missingGlyphUnicode=[36339,36807];
loadedLabel._assembler.updateRenderData=()=>{loadedLabel.renderData.vertexCount=4;loadedLabel.renderData.indexCount=6;};
assert.throws(()=>helper.read(contract,persistent,new Map([[nodeId,loadedNode]]),fonts,cc),/VERTEX_COUNT_DIFFERS|EMPTY_SOURCE_TEXT_RENDERED_VERTICES/);
