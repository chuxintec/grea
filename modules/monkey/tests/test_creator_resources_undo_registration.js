'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const Module=require('node:module');
const path=require('node:path');
const original=Module._load;
const snapshots=[];
let nextId=0;
class Component { constructor(){this.uuid='component-'+(++nextId);} }
class UITransform extends Component {}
class Skeleton extends Component {}
class SkeletonData {}
class Node {
    constructor(name){this.name=name;this.uuid='node-'+(++nextId);this.children=[];this._components=[];this._parent=null;}
    set parent(value){if(this._parent){const i=this._parent.children.indexOf(this);if(i>=0)this._parent.children.splice(i,1);}this._parent=value;if(value)value.children.push(this);}
    get parent(){return this._parent;}
    addComponent(Ctor){const value=new Ctor();value.node=this;this._components.push(value);return value;}
}
const cc={Node,UITransform,sp:{Skeleton,SkeletonData},Layers:{Enum:{UI_2D:33554432}}};
Module._load=function(request,parent,isMain){
    if(request==='cc'&&/CreatorResources\.js$/.test(parent&&parent.filename||''))return cc;
    if(request==='./owned-import-undo.js'&&/CreatorResources\.js$/.test(parent&&parent.filename||''))return {registerRoot(root){
        const objects=[];const walk=n=>{objects.push(n,...n._components);for(const child of n.children)walk(child);};walk(root);
        snapshots.push({root,objects});return {registered:true};
    }};
    return original.call(this,request,parent,isMain);
};
const resources=require('../src/monkey/targets/CreatorResources.js');
Module._load=original;

test('resource probe root, node and native Skeleton component are included in owned Undo registrations',async()=>{
    snapshots.length=0;
    const canvas=new Node('Canvas');
    const plan={resourceProbes:{profile:'creator-spine-3.8-v1',spines:[{nodeName:'SpineProbe',skeletonUuid:'skeleton-uuid'}]}};
    await resources.attach(plan,canvas,async()=>new SkeletonData());
    const root=canvas.children.find(node=>node.name==='NativeResourceProbes');
    const probe=root.children[0],skeleton=probe._components.find(value=>value instanceof Skeleton);
    assert.ok(snapshots.some(row=>row.root===root));
    assert.ok(snapshots.some(row=>row.root===probe));
    assert.ok(snapshots.some(row=>row.root===probe&&row.objects.includes(skeleton)),
        're-register after addComponent captures the Skeleton UUID as owned');
    assert.ok(snapshots.some(row=>row.root===root&&row.objects.includes(skeleton)),
        'final root registration covers the complete probe subtree');
});

test('asset-load failure retains ownership of already constructed probe components',async()=>{
    snapshots.length=0;
    const canvas=new Node('Canvas');
    const plan={resourceProbes:{profile:'creator-spine-3.8-v1',spines:[{nodeName:'SpineProbe',skeletonUuid:'missing'}]}};
    await assert.rejects(resources.attach(plan,canvas,async()=>{throw Error('load failed');}),/load failed/);
    const probe=canvas.children[0].children[0];
    const skeleton=probe._components.find(value=>value instanceof Skeleton);
    assert.ok(snapshots.some(row=>row.root===probe&&row.objects.includes(skeleton)));
});
