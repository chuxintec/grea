'use strict';
const cc=require('cc');
function type(spec) {
    if(!/^MonkeyRecovered[A-Za-z0-9_]+$/.test(spec.typeName||''))throw Error('Invalid recovered behavior type');
    const ctor=cc.js.getClassByName(spec.typeName);
    if(typeof ctor!=='function'||!(ctor.prototype instanceof cc.Component))throw Error('Behavior class not loaded: '+spec.typeName);
    if(!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(spec.scriptGuid||''))throw Error('Invalid behavior UUID');
    const raw=spec.scriptGuid.replace(/-/g,''), alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
    let expected=raw.slice(0,5);
    for(let i=5;i<32;i+=3){const n=parseInt(raw.slice(i,i+3),16);expected+=alphabet[n>>6]+alphabet[n&63];}
    if(cc.js.getClassId(ctor,false)!==expected)throw Error('Behavior script UUID differs');
    return ctor;
}
function value(field) {
    if(field.type==='float'&&Number.isFinite(field.numberValue))return field.numberValue;
    if(field.type==='bool'&&typeof field.boolValue==='boolean')return field.boolValue;
    throw Error('Unsupported behavior field');
}
function bind(node,spec,enabled) {
    const ctor=type(spec);
    if(node.getComponents(ctor).length)throw Error('Duplicate recovered behavior');
    const component=node.addComponent(ctor);component.enabled=false;
    for(const field of spec.fields||[]) {
        if(!/^[A-Za-z_][A-Za-z0-9_]*$/.test(field.name)||!(field.name in component))throw Error('Behavior field missing');
        const v=value(field);
        if(typeof component[field.name]!==typeof v)throw Error('Behavior field type differs');
        component[field.name]=v;
    }
    component.enabled=enabled;return component;
}
function read(node,spec,enabled) {
    const components=node.getComponents(type(spec));
    if(components.length!==1||components[0].enabled!==enabled)throw Error('Saved behavior identity differs');
    for(const field of spec.fields||[])if(components[0][field.name]!==value(field))throw Error('Saved behavior field differs');
    return components[0];
}
function readPersistent(node,spec,enabled,sourceId,assetUuid) {
    const component=read(node,spec,enabled);
    // Called on loaded Prefab.data, not a newly instantiated node tree. The
    // serialized component _id is the local identity for standalone prefabs;
    // __prefab.fileId is only present for native linked instances.
    const fileId=component.uuid;
    if(typeof fileId!=='string'||!fileId||typeof assetUuid!=='string'||!assetUuid)
        throw Error('Saved behavior persistent identity missing: '+sourceId);
    return {sourceId,typeName:spec.typeName,assetGuid:assetUuid,localFileId:fileId,
        scriptGuid:spec.scriptGuid,fieldsVerified:true,enabled:component.enabled,
        fields:(spec.fields||[]).map(field=>({name:field.name,type:field.type,
            ...(field.type==='float'?{numberValue:component[field.name]}:{boolValue:component[field.name]})})),runtime:'not_run'};
}
module.exports={type,bind,read,readPersistent};
