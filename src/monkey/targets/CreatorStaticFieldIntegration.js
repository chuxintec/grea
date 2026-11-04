'use strict';
const cc=require('cc');
const fields=require('./static-fields.js');
function specs(plan,nodes){return plan.components.filter(c=>c.staticFieldBinding&&nodes.has(c.node));}
function component(c,node){
    const ctor=cc.js.getClassByName(c.staticFieldBinding.typeName);
    if(!ctor)return null;
    const candidates=node.getComponents(ctor),exact=candidates.filter(x=>x.__monkeySourceId===c.sourceId);
    if(exact.length>1)throw Error('STATIC_CARRIER_IDENTITY_AMBIGUOUS');
    if(exact.length)return exact[0];
    const inherited=c.staticFieldBinding.sourceTemplateId?candidates.filter(x=>x.__monkeySourceId===c.staticFieldBinding.sourceTemplateId):[];
    if(inherited.length>1)throw Error('STATIC_CARRIER_TEMPLATE_IDENTITY_AMBIGUOUS');
    return inherited[0]||null;
}
function sourceOwners(plan,nodeSourceId) {
    return (plan.sourcePrefabs||[]).filter(spec=>Array.isArray(spec.nodes)&&spec.nodes.includes(nodeSourceId));
}
function sourceIdentityProof(plan,nodes,logicalSourceId,actual,expected) {
    const candidates=(plan.components||[]).filter(c=>c.sourceId===logicalSourceId);
    if(candidates.length!==1)return null;
    const logical=candidates[0],binding=logical.staticFieldBinding;
    const templateSourceId=binding&&binding.sourceTemplateId;
    if(typeof templateSourceId!=='string'||!templateSourceId)return null;
    const targetNode=nodes.get(logical.node);
    if(!targetNode||component(logical,targetNode)!==expected)return null;
    if(actual.__monkeySourceId!==templateSourceId||expected.__monkeySourceId!==templateSourceId)return null;

    const templateComponents=(plan.components||[]).filter(c=>c.sourceId===templateSourceId);
    if(templateComponents.length!==1)return null;
    const logicalOwners=sourceOwners(plan,logical.node),templateOwners=sourceOwners(plan,templateComponents[0].node);
    if(logicalOwners.length!==1||templateOwners.length!==1)return null;
    const matches=[];
    for(const relation of plan.syncPrefabBindings||[]) {
        if(relation.owner!==logicalOwners[0].sourceId||relation.template!==templateOwners[0].sourceId)continue;
        for(const origin of relation.componentOrigins||[]) {
            if(origin.instanceSourceId===logicalSourceId&&origin.templateSourceId===templateSourceId)
                matches.push({ownerPrefabSourceId:relation.owner,templatePrefabSourceId:relation.template});
        }
    }
    const unique=new Map(matches.map(match=>[match.ownerPrefabSourceId+'\n'+match.templatePrefabSourceId,match]));
    if(unique.size!==1)return null;
    const relationship=[...unique.values()][0];
    return {verified:true,logicalSourceId,templateSourceId,...relationship,
        proof:'syncPrefabBindings.componentOrigins'};
}
function resolver(plan,nodes,assets){
    const resolve=id=>{
        if(nodes.has(id))return nodes.get(id);
        const c=plan.components.find(x=>x.sourceId===id);
        if(c&&nodes.has(c.node)){
            const node=nodes.get(c.node);
            if(c.staticFieldBinding)return component(c,node);
            if(c.staticControlBinding)return node.getComponent(c.type==='cc.Graphics'?cc.Graphics:cc.EditBox);
            if(c.type==='cc.Animation'&&plan.staticAnimationEvidence)return node.getComponent(cc.Animation);
            if(c.staticProgressBinding)return node.getComponent(cc.ProgressBar);
            if(!c.convertible)return null;
            if(c.behaviorBinding){const ctor=cc.js.getClassByName(c.behaviorBinding.typeName);return ctor?node.getComponent(ctor):null;}
            const type=c.spineBinding?cc.sp.Skeleton:cc[c.type==='cc.LabelOutline'?'Label':c.type.slice(3)];
            return type?node.getComponent(type):null;
        }
        return assets&&assets.get(id)||null;
    };
    resolve.sourceIdentityProof=(sourceId,actual,expected)=>sourceIdentityProof(plan,nodes,sourceId,actual,expected);
    return resolve;
}
function createAssign(plan,nodes,assets){
    for(const c of specs(plan,nodes))if(!component(c,nodes.get(c.node)))fields.Create(c.staticFieldBinding,nodes.get(c.node));
    return specs(plan,nodes).map(c=>fields.Assign(c.staticFieldBinding,component(c,nodes.get(c.node)),resolver(plan,nodes,assets)));
}
function read(plan,nodes,assets,assetUuid){
    return specs(plan,nodes).map(c=>{
        const value=component(c,nodes.get(c.node));
        return {binding:fields.Read(c.staticFieldBinding,value,resolver(plan,nodes,assets)),assetUuid,componentUuid:value&&value.uuid};
    });
}
module.exports={createAssign,read,resolver};
