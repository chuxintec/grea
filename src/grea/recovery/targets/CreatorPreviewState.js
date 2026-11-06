'use strict';
// Import-time state application/readback on isolated Creator scene clones.
// No source script, network, input, animation or business callback is interpreted.
const cc = require('cc');
const KINDS = new Set(['node.active', 'node.scale', 'label.text', 'sprite.asset', 'node.opacity', 'label.fontSize', 'label.lineHeight', 'progress.value']);
const HASH = /^[0-9a-f]{64}$/;

function validate(spec) {
    if (!spec || spec.schemaVersion !== 1 || typeof spec.stateId !== 'string' || !spec.stateId ||
        typeof spec.sourcePrefabId !== 'string' || !spec.sourcePrefabId || !HASH.test(spec.stateSha256 || '') ||
        !HASH.test(spec.sourceManifestSha256 || '') || !spec.sourceVersion || !spec.referenceVersion)
        throw Error('PREVIEW_STATE_SPEC_INVALID');
    if (!Array.isArray(spec.evidence) || !spec.evidence.length || spec.evidence.some(e => !e || !e.id || !e.path || !HASH.test(e.sha256 || '')))
        throw Error('PREVIEW_STATE_EVIDENCE_INVALID');
    const evidenceIds = spec.evidence.map(e => e.id);
    if (new Set(evidenceIds).size !== evidenceIds.length) throw Error('PREVIEW_STATE_EVIDENCE_DUPLICATE');
    if (!Array.isArray(spec.operations) || !spec.operations.length) throw Error('PREVIEW_STATE_OPERATIONS_INVALID');
    const seen = new Set();
    for (const op of spec.operations) {
        if (!op || !KINDS.has(op.kind) || typeof op.sourceId !== 'string' ||
            !op.sourceId.startsWith(spec.sourcePrefabId + '#') || !evidenceIds.includes(op.evidenceId))
            throw Error('PREVIEW_STATE_OPERATION_INVALID');
        const key = op.kind + '\n' + op.sourceId;
        if (seen.has(key)) throw Error('PREVIEW_STATE_OPERATION_DUPLICATE');
        seen.add(key);
    }
}
function resolve(sourceId, resolver) {
    if (typeof resolver !== 'function') throw Error('PREVIEW_STATE_RESOLVER_MISSING: ' + sourceId);
    let value;
    try { value = resolver(sourceId); }
    catch (error) { throw Error('PREVIEW_STATE_RESOLVE_FAILED: ' + sourceId + ': ' + (error && error.message || error)); }
    if (!value || value.isValid === false) throw Error('PREVIEW_STATE_SOURCE_MISSING: ' + sourceId);
    return value;
}
function sameSprite(a,b){return a===b||!!(a&&b&&a instanceof cc.SpriteFrame&&b instanceof cc.SpriteFrame&&a._uuid&&a._uuid===b._uuid);}
function previewNode(value, sourceId) {
    const node = value instanceof cc.Node ? value : null;
    let root=node;while(root&&root.parent)root=root.parent;
    if (!node || !node.isValid || !(root instanceof cc.Scene)) throw Error('PREVIEW_STATE_REQUIRES_SCENE_CLONE: ' + sourceId);
    return node;
}
function ensureUserBehaviorsDisabled(root) {
    const pending = [root];
    while (pending.length) {
        const node = pending.pop();
        for (const component of node.getComponents(cc.Component)) {
            const className = cc.js.getClassName(component.constructor) || '';
            if (!className.startsWith('cc.') && !className.startsWith('sp.') && component.enabled && !(className==='MonkeySpineUITransformPreserver' && require('./spine-ui-transform.js').isPreserver(component,cc)))
                throw Error('PREVIEW_STATE_ENABLED_USER_BEHAVIOR: ' + className);
        }
        pending.push(...node.children);
    }
}
function near(a, b) { return Math.abs(a - b) <= 1e-5; }
function vector(value, sourceId) {
    if (!Array.isArray(value) || value.length !== 3 || value.some(n => typeof n !== 'number' || !Number.isFinite(n)))
        throw Error('PREVIEW_STATE_VECTOR_INVALID: ' + sourceId);
    return value;
}
function labelFor(value, sourceId) {
    if (value instanceof cc.Label || cc.RichText && value instanceof cc.RichText) return value;
    if (value instanceof cc.Node) {
        const label = value.getComponent(cc.Label) || (cc.RichText&&value.getComponent(cc.RichText));
        if (label) return label;
    }
    throw Error('PREVIEW_STATE_LABEL_MISSING: ' + sourceId);
}
function spriteFor(value, sourceId) {
    if (value instanceof cc.Sprite) return value;
    if (value instanceof cc.Node) {
        const sprite = value.getComponent(cc.Sprite);
        if (sprite) return sprite;
    }
    throw Error('PREVIEW_STATE_SPRITE_COMPONENT_MISSING: ' + sourceId);
}
function spriteFrame(assetId, resolver, optional) {
    if (assetId == null || assetId === '') {
        if (optional) return null;
        throw Error('PREVIEW_STATE_SPRITE_ASSET_ID_MISSING');
    }
    const value = resolve(assetId, resolver);
    if (!(value instanceof cc.SpriteFrame)) throw Error('PREVIEW_STATE_SPRITE_ASSET_TYPE: ' + assetId);
    return value;
}
function sameVector(actual, expected) {
    return actual && near(actual.x, expected[0]) && near(actual.y, expected[1]) && near(actual.z, expected[2]);
}

const NUMERIC=new Set(['node.opacity','label.fontSize','label.lineHeight','progress.value']);
function numberValue(op,value){
 if(op.kind==='node.opacity'){const n=previewNode(value,op.sourceId),c=n.getComponent(cc.UIOpacity);return c?c.opacity:255;}
 if(op.kind==='progress.value'){if(!(value instanceof cc.ProgressBar))throw Error('PREVIEW_PROGRESS_MISSING');return value.progress;}
 return labelFor(value,op.sourceId)[op.kind.split('.')[1]];
}
function setNumber(op,value){
 if(op.kind==='node.opacity'){const n=previewNode(value,op.sourceId);(n.getComponent(cc.UIOpacity)||n.addComponent(cc.UIOpacity)).opacity=op.numberValue;}
 else if(op.kind==='progress.value')value.progress=op.numberValue;
 else labelFor(value,op.sourceId)[op.kind.split('.')[1]]=op.numberValue;
}
function Apply(spec, resolver) {
    validate(spec);
    const pending = [];
    for (const op of spec.operations) {
        if (op.kind === 'node.active') {
            if (typeof op.expectedBoolValue !== 'boolean' || typeof op.boolValue !== 'boolean') throw Error('PREVIEW_STATE_BOOL_INVALID: ' + op.sourceId);
            const node = previewNode(resolve(op.sourceId, resolver), op.sourceId);
            const current = node.active;
            if (current !== op.expectedBoolValue && current !== op.boolValue) throw Error('PREVIEW_STATE_REENTRY_MISMATCH: ' + op.sourceId);
            if (current !== op.boolValue) ensureUserBehaviorsDisabled(node);
            pending.push(() => { if (node.active === op.expectedBoolValue) node.active = op.boolValue; });
        } else if (op.kind === 'node.scale') {
            const before = vector(op.expectedVectorValue, op.sourceId), after = vector(op.vectorValue, op.sourceId);
            const node = previewNode(resolve(op.sourceId, resolver), op.sourceId);
            if (!sameVector(node.scale, before) && !sameVector(node.scale, after)) throw Error('PREVIEW_STATE_REENTRY_MISMATCH: ' + op.sourceId);
            pending.push(() => { if (sameVector(node.scale, before)) node.setScale(new cc.Vec3(...after)); });
        } else if (NUMERIC.has(op.kind)) {
            const value=resolve(op.sourceId,resolver),current=numberValue(op,value);
            if(!near(current,op.expectedNumberValue)&&!near(current,op.numberValue))throw Error('PREVIEW_STATE_REENTRY_MISMATCH: '+op.sourceId);
            pending.push(()=>setNumber(op,value));
        } else if (op.kind === 'label.text') {
            if (typeof op.expectedStringValue !== 'string' || typeof op.stringValue !== 'string') throw Error('PREVIEW_STATE_STRING_INVALID: ' + op.sourceId);
            const label = labelFor(resolve(op.sourceId, resolver), op.sourceId);
            previewNode(label.node, op.sourceId);
            if (label.string !== op.expectedStringValue && label.string !== op.stringValue) throw Error('PREVIEW_STATE_REENTRY_MISMATCH: ' + op.sourceId);
            pending.push(() => { if (label.string === op.expectedStringValue) label.string = op.stringValue; });
        } else if (op.kind === 'sprite.asset') {
            const sprite = spriteFor(resolve(op.sourceId, resolver), op.sourceId);
            previewNode(sprite.node, op.sourceId);
            const before = spriteFrame(op.expectedAssetId, resolver, true), after = spriteFrame(op.assetId, resolver, true);
            if (!sameSprite(sprite.spriteFrame,before) && !sameSprite(sprite.spriteFrame,after)) throw Error('PREVIEW_STATE_REENTRY_MISMATCH: ' + op.sourceId);
            pending.push(() => { if (sameSprite(sprite.spriteFrame,before)) sprite.spriteFrame = after; sprite.enabled = op.sourceEnabled; });
        }
    }
    for (const apply of pending) apply();
    const result = Read(spec, resolver);
    result.applied = true;
    return result;
}

function Read(spec, resolver) {
    validate(spec);
    const rows = [];
    for (const op of spec.operations) {
        const row = { kind: op.kind, sourceId: op.sourceId, evidenceId: op.evidenceId, verified: false };
        if (op.kind === 'node.active') {
            row.actualBoolValue = previewNode(resolve(op.sourceId, resolver), op.sourceId).active;
            row.verified = row.actualBoolValue === op.boolValue;
        } else if (op.kind === 'node.scale') {
            const scale = previewNode(resolve(op.sourceId, resolver), op.sourceId).scale;
            row.actualVectorValue = [scale.x, scale.y, scale.z];
            row.verified = sameVector(scale, vector(op.vectorValue, op.sourceId));
        } else if (NUMERIC.has(op.kind)) {
            row.actualNumberValue=numberValue(op,resolve(op.sourceId,resolver));row.verified=near(row.actualNumberValue,op.numberValue);
        } else if (op.kind === 'label.text') {
            const label = labelFor(resolve(op.sourceId, resolver), op.sourceId);
            previewNode(label.node, op.sourceId);
            row.actualStringValue = label.string;
            row.verified = row.actualStringValue === op.stringValue;
        } else if (op.kind === 'sprite.asset') {
            const sprite = spriteFor(resolve(op.sourceId, resolver), op.sourceId);
            previewNode(sprite.node, op.sourceId);
            const expected = spriteFrame(op.assetId, resolver, true);
            const before = spriteFrame(op.expectedAssetId, resolver, true);
            row.actualAssetPresent = !!sprite.spriteFrame; row.actualAssetUuid=sprite.spriteFrame&&sprite.spriteFrame._uuid; row.actualEnabled=sprite.enabled;
            if (sameSprite(sprite.spriteFrame,expected)) { row.actualAssetId = op.assetId; row.actualAssetIdentityKnown = true; }
            else if (sameSprite(sprite.spriteFrame,before)) { row.actualAssetId = op.expectedAssetId; row.actualAssetIdentityKnown = true; }
            else if (!sprite.spriteFrame) row.actualAssetIdentityKnown = true;
            row.verified = sameSprite(sprite.spriteFrame,expected) && sprite.enabled === op.sourceEnabled;
        }
        rows.push(row);
    }
    const verified = rows.every(row => row.verified);
    return { stateId: spec.stateId, sourcePrefabId: spec.sourcePrefabId,
        sourceManifestSha256: spec.sourceManifestSha256, sourceVersion: spec.sourceVersion,
        referenceVersion: spec.referenceVersion, stateSha256: spec.stateSha256,
        applied: false, verified, businessBehaviorComplete: false, operations: rows,
        gaps: verified ? [] : ['preview_state_readback_mismatch'] };
}

module.exports = { Apply, Read };
