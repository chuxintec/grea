'use strict';
const cc=require('cc');
async function load(plan,loadAsset,native) {
    const animations=new Map(),evidence=new Map();
    for(const info of plan.animationAssets||[]) {
        const spec=(plan.animations||[]).find(x=>x.id===info.id);
        if(!spec||!spec.convertible)throw Error('STATIC_ANIMATION_PLAN_ASSET_IDENTITY_DIFFERS');
        const asset=await loadAsset(info.uuid,cc.AnimationClip);
        animations.set(info.id,{...info,asset,partial:!!spec.partial});
    }
    for(const info of plan.staticAnimationEvidence||[]) {
        const spec=plan.assets.find(x=>x.sourceId===info.sourceClipId+'@static-animation-evidence');
        if(!spec||spec.path!==info.path||spec.sha256!==info.sha256)throw Error('STATIC_ANIMATION_EVIDENCE_IDENTITY_DIFFERS');
        const asset=native.get(spec.sourceId)||await loadAsset(spec.uuid,cc.JsonAsset);
        evidence.set(info.sourceClipId,{...info,uuid:spec.uuid,asset});
    }
    for(const ref of plan.staticAnimationAssetReferences||[]) {
        const row=animations.get(ref.animationId);
        if(!row||row.path!==ref.path)throw Error('STATIC_ANIMATION_DIRECT_ASSET_MISSING');
        native.set(ref.sourceId,row.asset);
    }
    return {animations,evidence};
}
module.exports={load};
