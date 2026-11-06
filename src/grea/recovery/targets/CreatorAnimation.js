'use strict';
// Editor-only native curve authoring. Not shipped under assets or loaded by a Player.
const cc=require('cc');
function create(spec,nodes) {
    const clip=new cc.AnimationClip(spec.name);clip.duration=spec.duration;clip.sample=spec.sample;
    clip.wrapMode=spec.wrap==='loop'?cc.AnimationClip.WrapMode.Loop:cc.AnimationClip.WrapMode.Normal;clip.events=[];
    const groups=new Map();
    for(const channel of spec.tracks) {
        const property=channel.property.split('.')[0],key=channel.path+'|'+property;
        if(!groups.has(key))groups.set(key,{path:channel.path,property,channels:[]});groups.get(key).channels.push(channel);
        if(!spec.assetOnly&&property==='opacity'&&!nodes.get(channel.node).getComponent(cc.UIOpacity))nodes.get(channel.node).addComponent(cc.UIOpacity);
    }
    for(const group of groups.values()) {
        const track=group.property==='opacity'?new cc.animation.RealTrack():new cc.animation.VectorTrack();
        track.path=new cc.animation.TrackPath().toHierarchy(group.path);
        if(group.property==='opacity')track.path.toComponent(cc.UIOpacity).toProperty('opacity');
        else {track.componentsCount=3;track.path.toProperty(group.property);}
        for(const channel of group.channels) {
            const index=group.property==='opacity'?0:'xyz'.indexOf(channel.property.split('.')[1]);
            const curve=[...track.channels()][index].curve;
            curve.preExtrapolation=curve.postExtrapolation=cc.ExtrapolationMode.CLAMP;
            curve.assignSorted(channel.keys.map(k=>[k.time,{value:k.value,interpolationMode:k.interpolation==='step'?cc.RealInterpolationMode.CONSTANT:cc.RealInterpolationMode.LINEAR}]));
        }
        clip.addTrack(track);
    }
    return clip;
}
function read(clip,spec) {
    const channels=[];
    // Same deterministic native group order as authoring; no source callbacks are evaluated.
    const groups=new Map();
    for(const c of spec.tracks) {const key=c.path+'|'+c.property.split('.')[0];if(!groups.has(key))groups.set(key,[]);groups.get(key).push(c);}
    if(clip.tracksCount!==groups.size)throw Error('Native animation track count mismatch');
    let index=0;
    for(const group of groups.values()) {
        const track=clip.getTrack(index++);
        for(const c of group) {
            const axis=c.property==='opacity'?0:'xyz'.indexOf(c.property.split('.')[1]);const curve=[...track.channels()][axis].curve;
            const p=track.path;const opacity=p.length===3&&p.isComponentAt(1)&&p.parseComponentAt(1)==='cc.UIOpacity';
            if(!p.isHierarchyAt(0)||!(opacity?p.isPropertyAt(2):p.length===2&&p.isPropertyAt(1)))throw Error('Unexpected native animation binding');
            channels.push({path:p.parseHierarchyAt(0),property:opacity?p.parsePropertyAt(2):p.parsePropertyAt(1)+'.'+'xyz'[axis],nativeType:opacity?'UIOpacity':'Node',times:[...curve.times()],
                values:[...curve.values()].map(v=>v.value),interpolations:[...curve.values()].map(v=>v.interpolationMode===cc.RealInterpolationMode.CONSTANT?'step':v.interpolationMode===cc.RealInterpolationMode.LINEAR?'linear':'unsupported'),
                probeTimes:c.probes.map(p=>p.time),probeValues:c.probes.map(p=>curve.evaluate(p.time))});
        }
    }
    return {id:spec.id,path:spec.path,uuid:clip._uuid,curveCount:[...clip.tracks].reduce((n,t)=>n+[...t.channels()].filter(c=>[...c.curve.times()].length>0).length,0),duration:clip.duration,wrap:clip.wrapMode===cc.AnimationClip.WrapMode.Loop?'loop':'normal',eventCount:clip.events.length,tracks:channels};
}
module.exports={create,read};
