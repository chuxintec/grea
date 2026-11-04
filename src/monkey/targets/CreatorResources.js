'use strict';
// Resource-only nodes live outside the source hierarchy. No recovered program is attached.
const cc=require('cc');
const ownedUndo=require('./owned-import-undo.js');
async function attach(plan,canvas,loadAsset) {
    if(!plan.resourceProbes)return;
    if(plan.resourceProbes.profile!=='creator-spine-3.8-v1')throw Error('Unsupported resource probe profile');
    const root=new cc.Node('NativeResourceProbes');ownedUndo.registerRoot(root);root.parent=canvas;
    for(const spec of plan.resourceProbes.spines) {
        const node=new cc.Node(spec.nodeName);ownedUndo.registerRoot(node);node.parent=root;node.layer=cc.Layers.Enum.UI_2D;
        node.addComponent(cc.UITransform);
        const skeleton=node.addComponent(cc.sp.Skeleton);
        // Re-register the exact node after component construction so the Undo
        // scope also includes the newly-created native Skeleton component UUID.
        ownedUndo.registerRoot(node);
        skeleton.skeletonData=await loadAsset(spec.skeletonUuid,cc.sp.SkeletonData);
    }
    // Include children added since the root was first constructed.
    ownedUndo.registerRoot(root);
}
function pose(skeleton,bones) {
    return bones.map(data=>{
        const b=skeleton.findBone(data.name);if(!b)throw Error('Native Spine bone missing');
        const values=[b.worldX,b.worldY,b.a,b.b,b.c,b.d];
        if(!values.every(Number.isFinite))throw Error('Native Spine bone pose is nonfinite');
        return values;
    });
}
function applyPose(skeleton,bones) {
    // The detached scene has no render-loop update. Apply the native animation
    // state to the actual component's native skeleton before reading transforms.
    const bone=skeleton.findBone(bones[0].name),state=skeleton.getState();
    const model=bone&&bone.skeleton;
    if(!state||!model)throw Error('Native Spine model/state unavailable');
    state.apply(model);model.updateWorldTransform();
    return pose(skeleton,bones);
}
async function read(plan,scene) {
    if(!plan.resourceProbes)return null;
    const root=scene.getChildByName('Canvas').getChildByName('NativeResourceProbes');if(!root)throw Error('Saved resource probe root missing');
    const rows=[];
    for(const spec of plan.resourceProbes.spines) {
        const nodes=root.children.filter(n=>n.name===spec.nodeName);if(nodes.length!==1)throw Error('Saved Spine probe identity ambiguous');
        const skeleton=nodes[0].getComponent(cc.sp.Skeleton),data=skeleton&&skeleton.skeletonData;
        if(!(data instanceof cc.sp.SkeletonData)||data._uuid!==spec.skeletonUuid)throw Error('Saved Spine asset reference differs');
        if(data.textureNames.length!==spec.pages.length||data.textures.length!==spec.pages.length)throw Error('Native Spine page count differs');
        const textures=spec.pages.map((p,i)=>{
            if(data.textureNames[i]!==p.name||data.textures[i]._uuid!==p.textureUuid)throw Error('Native Spine texture name/UUID differs');
            return {name:p.name,imageUuid:p.imageUuid,textureUuid:p.textureUuid,nativeUuid:data.textures[i]._uuid};
        });
        const runtime=data.getRuntimeData();if(!runtime||!runtime.bones.length||runtime.bones.length>4096)throw Error('Native Spine runtime data unavailable');
        const nameCatalog=require('./spine-bindings.js').readCreatorSpineDataCatalog(spec.sourceId,data,{nativeUuid:spec.skeletonUuid});
        if(nameCatalog.status!=='verified')throw Error('Native Spine animation/skin name catalog unavailable');
        const animation=runtime.animations.find(a=>Number.isFinite(a.duration)&&a.duration>0);
        if(!animation)throw Error('No finite sourced animation for native playback probe');
        // Inactive Scene deserialization does not run component lifecycle. Initialize
        // the existing saved native reference through its public setter, then sample it.
        skeleton.skeletonData=null;skeleton.skeletonData=data;
        const entry=skeleton.setAnimation(0,animation.name,true);if(!entry)throw Error('Native Spine animation did not start');
        skeleton.updateAnimation(0);const before=entry.trackTime,first=applyPose(skeleton,runtime.bones);
        let after=before,last=first;const samples=[];
        const times=[...new Set([Math.min(.125,animation.duration/4),Math.min(.5,animation.duration/2),Math.min(1,animation.duration*.75)])].sort((a,b)=>a-b);
        for(const time of times) {
            skeleton.updateAnimation(time-(after-before));
            after=entry.trackTime;last=applyPose(skeleton,runtime.bones);
            samples.push({trackTime:after,poseChanged:JSON.stringify(first)!==JSON.stringify(last)});
            if(samples[samples.length-1].poseChanged)break;
        }
        if(!(Number.isFinite(before)&&Number.isFinite(after)&&after>before))throw Error('Native Spine animation state did not advance');
        const poseChanged=JSON.stringify(first)!==JSON.stringify(last);
        rows.push({sourceId:spec.sourceId,skeletonUuid:data._uuid,sourceSkeletonSha256:spec.sourceSkeletonSha256,
            animationNames:nameCatalog.animationNames,skinNames:nameCatalog.skinNames,
            version:spec.version,savedReferenceVerified:true,textures,bones:runtime.bones.length,slots:runtime.slots.length,
            animation:animation.name,duration:animation.duration,trackTimeBefore:before,trackTimeAfter:after,
            nativeStateAdvanced:true,poseChanged,sampledBones:first.length,samples,
            diagnostics:poseChanged?[]:[{code:'NO_OBSERVED_BONE_MOTION',sourceId:spec.sourceId,
                message:'Native time advanced; bone pose did not change at these sample times. Slot/attachment/colour channels and static animation remain unverified.'}]});
    }
    return {profile:plan.resourceProbes.profile,spines:rows};
}
module.exports={attach,read};
