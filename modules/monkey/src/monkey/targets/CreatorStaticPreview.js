'use strict';
const clones=require('./preview-clones.js'),projections=require('./static-sprite-frames.js');
const sourceChildren=require('./static-richtext.js').sourceChildren;
const cc=require('cc'),states=require('./preview-state.js'),fields=require('./static-field-integration.js'),dynamic=require('./dynamic-ui.js');
function mapNodes(plan,spec,root,cloned=false){
 const source=new Map(plan.nodes.map(n=>[n.sourceId,n])),nodes=new Map();
 const projectionParents=new Map((cloned&&plan.previewState.spriteProjection&&plan.previewState.spriteProjection.entries||[]).map(e=>[e.parentSourceId,e]));
 const parents=new Map((cloned&&plan.previewState.cloneBatches||[]).map(b=>[b.template.parentSourceId,b]));
 function walk(id,node){
  const n=source.get(id);if(!n||!node)throw Error('STATIC_PREVIEW_HIERARCHY');
  const children=sourceChildren(node),batch=parents.get(id);nodes.set(id,node);
  if(batch){
   if(children.length!==batch.template.expectedChildCount)throw Error('STATIC_PREVIEW_CLONE_BOUNDARY');
   if(batch.template.placementMode==='append-external'){
    if(JSON.stringify(n.children)!==JSON.stringify(batch.template.initialChildSourceIds))throw Error('STATIC_PREVIEW_CLONE_PREFIX');
    n.children.forEach((child,i)=>walk(child,children[i]));
   }else{if(n.children.length!==1)throw Error('STATIC_PREVIEW_CLONE_BOUNDARY');walk(n.children[0],children[0]);}
  }
  else if(projectionParents.has(id)){const e=projectionParents.get(id);if(n.children.length!==0||e.expectedParentChildSourceIds.length!==0||children.length!==1)throw Error('STATIC_PREVIEW_PROJECTION_BOUNDARY');}
  else {if(n.children.length!==children.length)throw Error('STATIC_PREVIEW_HIERARCHY: '+id+' '+JSON.stringify({expected:n.children.length,actual:children.map(x=>x.name)}));n.children.forEach((child,i)=>walk(child,children[i]));}
 }
 walk(spec.root,root);return nodes;
}
function detachPreviewPrefabLinks(root){
 // Only the disposable static-state clone is unpacked. Source Prefabs keep
 // their independently verified native template/instance relationships.
 // A derived scene must persist its authored rows instead of re-expanding
 // the original template on Scene._load and discarding static overrides.
 function walk(node){node._prefab=null;for(const component of node.components)if(component.__prefab)component.__prefab=null;for(const child of node.children)walk(child);}
 walk(root);
}
function settlePreview(root,nodes,plan){
 const all=new Map(nodes),seen=new Set(nodes.values());let sequence=0;
 function walk(node){if(!seen.has(node)&&node.getComponent(cc.UITransform)){all.set('$preview-clone/'+sequence++,node);seen.add(node);}for(const child of sourceChildren(node))walk(child);}
 walk(root);const parent=root.parent;
 try{return dynamic.settleRoot(root,all,plan);}finally{root.parent=parent;}
}
async function assets(plan,load){const result=new Map();for(const a of plan.assets)result.set(a.sourceId,await load(a.kind==='sprite'?a.spriteFrameUuid:a.uuid,a.kind==='sprite'?cc.SpriteFrame:a.kind==='json'?cc.JsonAsset:a.kind==='audio'?cc.AudioClip:cc.Font));
 if(plan.spriteOutlineBinding)result.set(plan.spriteOutlineBinding.materialSourceId,await load(plan.spriteOutlineBinding.creator.materialUuid,cc.Material));
 for(const a of (plan.spineBinding&&plan.spineBinding.assets)||[])result.set(a.sourceId,await load(a.creator.nativeUuid,cc.sp.SkeletonData));
 if(plan.materialBinding)result.set(plan.materialBinding.materialSourceId,await load(plan.materialBinding.creator.materialUuid,cc.Material));
 return result;}
function encode(asset){const raw=EditorExtends.serialize(asset);return typeof raw==='string'?raw:JSON.stringify(raw);}
async function create(uuid,plan,load){
 const state=plan.previewState,spec=plan.sourcePrefabs.find(x=>x.sourceId===state.sourcePrefabId);
 if(!spec)throw Error('STATIC_PREVIEW_SOURCE_MISSING');
 const source=await load(uuid,cc.Prefab),native=await assets(plan,load),scene=new cc.Scene('StaticPreview');
 try {
  const canvasNode=new cc.Node('StaticPreviewCanvas');canvasNode.layer=cc.Layers.Enum.UI_2D;canvasNode.parent=scene;canvasNode.setPosition(plan.designSize[0]/2,plan.designSize[1]/2,0);canvasNode.addComponent(cc.UITransform).setContentSize(...plan.designSize);const canvas=canvasNode.addComponent(cc.Canvas);canvas.alignCanvasWithScreen=false;
  const cameraNode=new cc.Node('StaticPreviewCamera');cameraNode.parent=scene;cameraNode.setPosition(0,0,1000);const camera=cameraNode.addComponent(cc.Camera);camera.projection=cc.Camera.ProjectionType.ORTHO;camera.orthoHeight=plan.designSize[1]/2;camera.near=1;camera.far=2000;camera.visibility=cc.Layers.Enum.UI_2D;canvas.cameraComponent=camera;
  const design=new cc.Node('DesignRoot');design.layer=cc.Layers.Enum.UI_2D;design.parent=canvasNode;design.addComponent(cc.UITransform).setContentSize(...plan.designSize);design.getComponent(cc.UITransform).setAnchorPoint(0,0);design.setPosition(-plan.designSize[0]/2,-plan.designSize[1]/2,0);
  const root=cc.instantiate(source);detachPreviewPrefabLinks(root);root.parent=design;const nodes=mapNodes(plan,spec,root),resolve=fields.resolver(plan,nodes,native);
  settlePreview(root,nodes,plan);
  const cloneResults=[];
  for(const batch of state.cloneBatches||[]){
   let template=null;
   if(batch.templatePrefabId!==batch.sourcePrefabId){
    const templateSpec=(plan.savedPrefabs||[]).find(x=>x.sourceId===batch.templatePrefabId);
    if(!templateSpec)throw Error('STATIC_PREVIEW_TEMPLATE_MISSING');
    template=cc.instantiate(await load(templateSpec.uuid,cc.Prefab));detachPreviewPrefabLinks(template);
   }
   const result=clones.Apply(batch,nodes,local=>fields.resolver(plan,local,native),()=>settlePreview(root,nodes,plan),()=>template);
   if(!result.verified)throw Error('STATIC_PREVIEW_CLONE_APPLY_FAILED');cloneResults.push(result);
  }
  const projectionResults=state.spriteProjection?projections.Apply(state.spriteProjection,nodes,id=>native.get(id)):null;
  const finalNodes=mapNodes(plan,spec,root,true),finalResolve=fields.resolver(plan,finalNodes,native);
  fields.createAssign(plan,finalNodes,native);
  states.Apply(state,finalResolve);settlePreview(root,finalNodes,plan);root.parent=design;const readback=states.Read(state,finalResolve);if(!readback.verified)throw Error('STATIC_PREVIEW_STATE_FAILED');
  const transform=root.getComponent(cc.UITransform),center=transform.convertToWorldSpaceAR(new cc.Vec3((.5-transform.anchorX)*transform.width,(.5-transform.anchorY)*transform.height,0));
  cameraNode.setWorldPosition(center.x,center.y,1000);
  root.parent=null;const prefab=new cc.Prefab();prefab.name='StaticPreview';prefab.data=root;const prefabSerialized=encode(prefab);root.parent=design;
  const sceneAsset=new cc.SceneAsset();sceneAsset.scene=scene;
  return {prefabSerialized,sceneSerialized:encode(sceneAsset),state:readback,derivedPrefabLinksDetached:true,clones:cloneResults,spriteProjections:projectionResults};
 }finally{dynamic.release(scene);scene.destroy();}
}
async function read(uuid,plan,load){
 const asset=await load(uuid,cc.SceneAsset),scene=asset.scene,native=await assets(plan,load);
 if(!scene)throw Error('STATIC_PREVIEW_SCENE_ASSET_MISSING');
 scene._load();
 try {const spec=plan.sourcePrefabs.find(x=>x.sourceId===plan.previewState.sourcePrefabId);const root=scene.getChildByName('StaticPreviewCanvas').getChildByName('DesignRoot').children[0];const nodes=mapNodes(plan,spec,root,true);
 const parent=root.parent;settlePreview(root,nodes,plan);root.parent=parent;return {spriteProjections:plan.previewState.spriteProjection?projections.Read(plan.previewState.spriteProjection,nodes,id=>native.get(id)):null,clones:(plan.previewState.cloneBatches||[]).map(b=>clones.Read(b,nodes,local=>fields.resolver(plan,local,native),()=>settlePreview(root,nodes,plan))),state:states.Read(plan.previewState,fields.resolver(plan,nodes,native)),fields:fields.read(plan,nodes,native,uuid),nodeCount:nodes.size,savedReloaded:true,sceneUuid:uuid};
 }finally{dynamic.release(scene);}
}
module.exports={create,read};
