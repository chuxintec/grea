'use strict';
const assert=require('assert'),fs=require('fs'),vm=require('vm');
class Component{};class SpriteFrame{constructor(id){this._uuid=id;this.rect={width:8,height:6};}}
class UITransform extends Component{constructor(w,h){super();this.width=w;this.height=h;this.anchorX=.5;this.anchorY=.5;}}
class Sprite extends Component{};Sprite.SizeMode={TRIMMED:1};
class Node{constructor(name){this.name=name;this.children=[];this.active=true;this.layer=1;this.isValid=true;this.position={x:0,y:0,z:0};this.scale={x:1,y:1,z:1};this.components=[];}getComponent(t){return this.components.find(c=>c instanceof t)||null;}getComponents(){return this.components;}getSiblingIndex(){return this.parent.children.indexOf(this);}}
class Scene extends Node{};
const cc={Component,SpriteFrame,UITransform,Sprite,Node,Scene,js:{getClassName:()=> 'cc.Sprite'}};
const moduleObject={exports:{}};vm.runInNewContext(fs.readFileSync('src/monkey/targets/CreatorStaticSpriteFrames.js','utf8'),{require:n=>{assert.equal(n,'cc');return cc;},module:moduleObject,Map,Array,Number,Math,Error,String});
const scene=new Scene('scene'),parent=new Node('parent'),root=new Node('__monkey_static_sprite__neutral'),child=new Node('icon');
scene.children=[parent];parent.parent=scene;parent.children=[root];root.parent=parent;root.children=[child];child.parent=root;
root.components=[new UITransform(10,10)];child.components=[new UITransform(8,6)];
const sprite=new Sprite();sprite.spriteFrame=new SpriteFrame('stable-frame-id');sprite.sizeMode=1;sprite.enabled=true;sprite.color={r:255,g:255,b:255,a:255};child.components.push(sprite);
const entry={projectionId:'neutral',parentSourceId:'source:panel#1',expectedParentChildSourceIds:[],root:{active:true,size:[10,10],localPosition:[0,0,0],localScale:[1,1,1]},spriteChild:{name:'icon',spriteFrameSourceId:'source:frame',originalSize:[8,6],enabled:true,anchor:[.5,.5],localPosition:[0,0,0],color:[255,255,255,255]}};
const plan={schema:'monkey-prefab-static-sprite-projection-plan/1',entries:[entry]},nodes=new Map([[entry.parentSourceId,parent]]);
assert.equal(moduleObject.exports.Read(plan,nodes,()=>new SpriteFrame('stable-frame-id')).verified,true);
const wrong=moduleObject.exports.Read(plan,nodes,()=>new SpriteFrame('wrong-frame-id'));assert.equal(wrong.verified,false);assert.match(wrong.projections[0].error,/STATIC_SPRITE_READBACK_MISMATCH/);
child.getComponent(UITransform).width=9;assert.equal(moduleObject.exports.Read(plan,nodes,()=>new SpriteFrame('stable-frame-id')).verified,false);
console.log('Static sprite reload identity and geometry checks passed');
