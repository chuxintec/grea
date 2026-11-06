'use strict';
// Creator 3.8 Editor project scripts are evaluated by the Editor Packer's
// prerequisite-import reload before scene extension methods run. Resolve the
// registered native API class and verify its real script UUID; no source-module
// path guessing or source-graphics interpretation is involved.
const cc = require('cc');
const ownedUndo = require('./owned-import-undo.js');
const API_CLASS_NAME = 'MonkeyStaticSortQueueProxyApi';
const API_MODULE_UUID = 'f82a1331-6407-5dbc-9833-b421ddbbfc68';
let registeredApi = null;

function fail(message) { throw new Error('CREATOR_STATIC_SORT_QUEUE: ' + message); }
function failWithReadback(message, readback, plan, phase, rootScope) {
    let evidence=null;
    if(plan&&plan.nativeProjectRoot) {
        const fs=require('fs'),path=require('path'),crypto=require('crypto');
        const root=fs.realpathSync(plan.nativeProjectRoot);
        const frozen=JSON.parse(fs.readFileSync(path.join(root,'extensions/monkey-import/import-plan.json'),'utf8'));
        if(frozen.projectUuid!==plan.projectUuid||frozen.sourceManifestSha256!==plan.sourceManifestSha256)
            fail('diagnostic project identity differs');
        const folder=path.join(root,'Analysis/Readback/StaticSort');fs.mkdirSync(folder,{recursive:true});
        const key=crypto.createHash('sha256').update(rootScope).digest('hex').slice(0,24);
        for(let sequence=0;sequence<10000;sequence++) {
            const target=path.join(folder,key+'-'+phase+'-'+sequence+'.json');
            try {
                fs.writeFileSync(target,JSON.stringify({scope:'native-static-sort-diagnostic-only',status:'failed',phase,
                    rootScope,projectUuid:plan.projectUuid,sourceManifestSha256:plan.sourceManifestSha256,readback},null,2)+'\n',{flag:'wx'});
                evidence=path.relative(root,target);break;
            }catch(error){if(error.code!=='EEXIST')throw error;}
        }
        if(!evidence)fail('diagnostic receipt sequence exhausted');
    }
    const error = new Error('CREATOR_STATIC_SORT_QUEUE: ' + message + ':' + JSON.stringify({...readbackFailureSummary(readback),evidence}));
    error.creatorStaticSortReadback = readback;
    throw error;
}
function parentCanvas(node) {
    for(let current=node;current;current=current.parent) {
        const canvas=current.getComponent(cc.Canvas);
        if(canvas)return canvas;
    }
    return null;
}
function isPinnedApiClass(ctor) {
    const uuidUtils = globalThis.EditorExtends && EditorExtends.UuidUtils;
    if (!uuidUtils || typeof uuidUtils.decompressUuid !== 'function') return false;
    const registeredScriptUuid = ctor && ctor.prototype && ctor.prototype.__scriptUuid;
    return ctor.moduleUuid === API_MODULE_UUID && registeredScriptUuid === uuidUtils.decompressUuid(API_MODULE_UUID);
}
function api() {
    const ctor = registeredApi || (cc.js && cc.js.getClassByName && cc.js.getClassByName(API_CLASS_NAME));
    if (!ctor || !isPinnedApiClass(ctor) || typeof ctor.create !== 'function' ||
        typeof ctor.attachSourceIdentities !== 'function' ||
        typeof ctor.readPersistent !== 'function' || typeof ctor.readInitialized !== 'function' ||
        typeof ctor.isGeneratedProxyRoot !== 'function') fail('registered TypeScript API class missing or UUID differs');
    return ctor;
}
function registerApiClass(ctor) {
    if (!ctor || !isPinnedApiClass(ctor) || (cc.js && cc.js.getClassByName(API_CLASS_NAME) !== ctor))
        fail('loaded API class does not match the pinned module UUID/class registration');
    registeredApi = ctor;
    return { uuid: API_MODULE_UUID, className: API_CLASS_NAME, registered: true };
}
function validatePlan(plan) {
    if (!plan || typeof plan !== 'object') fail('plan missing');
    if (plan.staticSortQueue === undefined && !plan.staticCompletion) return { applicable: false, status: 'not_applicable' };
    if (!Array.isArray(plan.sourcePrefabs)) fail('sourcePrefabs list missing');
    if (!Array.isArray(plan.staticSortQueue)) fail('staticCompletion requires a staticSortQueue array');
    const expected = new Map(plan.sourcePrefabs.map(prefab => [prefab.root, prefab]));
    const rows = plan.staticSortQueue;
    if (rows.length !== expected.size) fail('staticSortQueue/sourcePrefabs count differs');
    const seen = new Set();
    for (const row of rows) {
        if (!row || typeof row.rootScope !== 'string' || seen.has(row.rootScope)) fail('missing or duplicate rootScope');
        const prefab = expected.get(row.rootScope);
        if (!prefab || prefab.sourceId !== row.sourcePrefabId || prefab.path !== row.prefabPath)
            fail('root/sourcePrefabId/path identity differs: ' + row.rootScope);
        if (row.sourceManifestSha256 !== plan.sourceManifestSha256 || !Array.isArray(row.sourceDrawEvents) ||
            !Array.isArray(row.renderers) || !Array.isArray(row.nonDrawRenderers) || !Array.isArray(row.masks) ||
            !row.sourceChildOrder || !row.sourceNodeActive)
            fail('incomplete or differently bound static proxy contract: ' + row.rootScope);
        seen.add(row.rootScope);
    }
    for (const root of expected.keys()) if (!seen.has(root)) fail('source Prefab root has no sort proxy contract: ' + root);
    return { applicable: true, status: 'required', rows };
}
function spec(plan, rootScope) {
    const validation = validatePlan(plan);
    if (!validation.applicable) return null;
    const row = plan.staticSortQueue.find(item => item.rootScope === rootScope);
    if (!row) fail('Prefab root was not in the complete plan contract: ' + rootScope);
    const nonDrawRenderers=row.nonDrawRenderers.map(item=>{
        if(item.sourceType!=='cc.Sprite'||item.sourceSpriteFrameUuid===null) {
            if(item.sourceSpriteFrameAssetId!=null||item.nativeSpriteImageUuidExpected!=null)
                fail('null/non-Sprite source contains an unexpected native frame mapping: '+item.sourceId);
            return {...item,nativeSpriteFrameUuidExpected:null};
        }
        const matches=(plan.assets||[]).filter(asset=>asset.sourceId===item.sourceSpriteFrameAssetId);
        if(matches.length!==1||matches[0].kind!=='sprite'||matches[0].uuid!==item.nativeSpriteImageUuidExpected||
            typeof matches[0].spriteFrameUuid!=='string'||!matches[0].spriteFrameUuid)
            fail('source SpriteFrame cannot resolve through the imported ImageAsset metadata: '+item.sourceId);
        return {...item,nativeSpriteFrameUuidExpected:matches[0].spriteFrameUuid};
    });
    const sourceNodeLayers = {};
    if (Array.isArray(row.sourceNodeIds)) {
        const nodesById = new Map((plan.nodes || []).map(node => [node.sourceId, node]));
        for (const nodeId of row.sourceNodeIds) {
            const sourceNode = nodesById.get(nodeId);
            if (!sourceNode)fail('source node target layer owner absent from plan: '+nodeId);
            // Match CreatorScene's construction rule, including its explicit target UI layer default.
            const layer=sourceNode.sourceLayer??cc.Layers.Enum.UI_2D;
            if (!Number.isInteger(layer))fail('source node target layer is invalid: '+nodeId);
            sourceNodeLayers[nodeId] = layer;
        }
    }
    return {...row,nonDrawRenderers,sourceNodeLayers};
}
function attachSourceIdentities(plan, nodes) {
    const validation = validatePlan(plan);
    if (!validation.applicable) return { applicable: false, status: 'not_applicable' };
    if (!nodes || typeof nodes.get !== 'function') fail('source identity attachment requires the complete native source node map');
    for (const row of validation.rows) for (const nodeId of row.sourceNodeIds || [])
        if (!nodes.get(nodeId)) fail('source identity attachment node missing: ' + nodeId);
    const result = api().attachSourceIdentities(validation.rows, nodes);
    if (!result || result.verified !== true || !Array.isArray(result.sourceSortOrderFields) || !Array.isArray(result.sourceSortRoots))
        fail('typed source identity attachment/readback failed');
    return { applicable: true, status: 'verified', ...result };
}
function resolveSprite(specRow, nodes, uuid, requireInitializedBacking = false) {
    const Identity = cc.js && cc.js.getClassByName && cc.js.getClassByName('MonkeyStaticMaskIdentity');
    if (!Identity) fail('source Mask identity class is not registered');
    const frames = new Set();
    for (const mask of specRow.masks) {
        if (mask.maskType !== 2 || mask.spriteFrameUuid !== uuid) continue;
        const node = nodes.get(mask.node), sprite = node && node.getComponent(cc.Sprite);
        const nativeMask = node && node.getComponent(cc.Mask);
        const identities = node && node.getComponents(Identity);
        if (!sprite || !nativeMask || !identities || identities.length !== 1) continue;
        const identity = identities[0], frame = identity.sourceSpriteFrame;
        // Source UUIDs belong to the old Creator project and need not equal the
        // imported native UUID. Bind by the persisted typed identity reference,
        // then prove the native Sprite and Mask resolve to that same object.
        if (identity.sourceSpriteFrameUuid === uuid && frame && sprite.spriteFrame === frame &&
            (!requireInitializedBacking || (nativeMask.subComp === sprite && nativeMask.spriteFrame === frame))) frames.add(frame);
    }
    if (frames.size !== 1) fail('exact source SpriteFrame reference is absent/ambiguous: ' + uuid);
    return [...frames][0];
}
function rootPresenter(sourceRoot, rootScope) {
    const Api = api();
    const candidates = sourceRoot.children.filter(child => Api.isGeneratedProxyRoot(child));
    if (candidates.length !== 1) fail('source root must have exactly one owner-verified generated proxy root: ' + rootScope);
    const proxyRoot = candidates[0];
    const Presenter = cc.js.getClassByName('MonkeyStaticSortQueueProxyPresenter');
    if (!Presenter) fail('Presenter class script is not registered');
    const presenter = proxyRoot.getComponent(Presenter);
    if (!presenter || presenter.sourceRoot !== sourceRoot || presenter.proxyRoot !== proxyRoot || presenter.sourceRootId !== rootScope)
        fail('proxy root Presenter refs differ: ' + rootScope);
    return { proxyRoot, presenter };
}
function createForPrefab(plan, rootScope, nodes) {
    const row = spec(plan, rootScope);
    if (!row) return { applicable: false, status: 'not_applicable', createReadback: { applicable: false, status: 'not_applicable' } };
    const sourceRoot = nodes.get(rootScope);
    const canvas = sourceRoot && parentCanvas(sourceRoot);
    if (!sourceRoot || !sourceRoot.parent || !sourceRoot.activeInHierarchy || !canvas ||
        !canvas.enabledInHierarchy || !canvas.node.activeInHierarchy)
        fail('create requires the source Prefab in an active native Canvas context');
    for (const nodeId of row.sourceNodeIds) if (!nodes.has(nodeId)) fail('source node missing before proxy creation: ' + nodeId);
    const result = api().create(row, nodes, uuid => resolveSprite(row, nodes, uuid, true));
    const refs = rootPresenter(sourceRoot, rootScope);
    // The generated subtree can record UUIDs during construction, before this
    // bridge returns to the Prefab serializer. Register its exact root while
    // it remains attached to the source tree so the import-owned Undo scope can
    // suppress later records and safely clean constructor residue on destroy.
    ownedUndo.registerRoot(refs.proxyRoot);
    if (!result || !result.verified || result.presentationMode !== 'initialized')
        failWithReadback('create did not verify the active native proxy tree: ' + rootScope, result, plan, 'construction', rootScope);
    return { spec: row, sourceRoot, proxyRoot: refs.proxyRoot, presenter: refs.presenter, createReadback: result };
}
function readPersistent(plan, rootScope, nodes, sourceRoot) {
    const row = spec(plan, rootScope);
    if (!row) return { applicable: false, status: 'not_applicable' };
    const refs = rootPresenter(sourceRoot, rootScope);
    const result = api().readPersistent(row, nodes, refs.proxyRoot, refs.presenter,
        uuid => resolveSprite(row, nodes, uuid));
    if (!result || !result.verified || result.presentationMode !== 'persistent' || !result.sourceLayersPreserved)
        failWithReadback('serialized source fields/proxy asset readback failed: ' + rootScope, result, plan, 'persistent', rootScope);
    return result;
}
function readInitialized(plan, rootScope, nodes, sourceRoot) {
    const row = spec(plan, rootScope);
    if (!row) return { applicable: false, status: 'not_applicable' };
    const canvas = sourceRoot && parentCanvas(sourceRoot);
    if (!sourceRoot || !sourceRoot.activeInHierarchy || !canvas || !canvas.enabledInHierarchy || !canvas.node.activeInHierarchy)
        fail('initialized read requires an active native Canvas context: ' + rootScope);
    const refs = rootPresenter(sourceRoot, rootScope);
    const result = api().readInitialized(row, nodes, refs.proxyRoot, refs.presenter,
        uuid => resolveSprite(row, nodes, uuid, true));
    if (!result || !result.verified || result.presentationMode !== 'initialized' || !result.sourceSuppressed)
        failWithReadback('initialized Editor presentation readback failed: ' + rootScope, result, plan, 'initialized', rootScope);
    return result;
}
function readbackFailureSummary(result) {
    if (!result || typeof result !== 'object') return { falseChecks: ['readback-missing'], badSourceIds: [] };
    const falseChecks = Array.isArray(result.failedChecks) ? result.failedChecks.slice(0, 32) :
        Object.keys(result).filter(key => result[key] === false).slice(0, 32);
    const idFields = ['sourceId', 'sourceComponentId', 'expectedSourceId'];
    const listFields = ['sourceNonDrawRenderers', 'sourceNonDrawSourceMappings', 'sourceSortOrderFields',
        'sourceSortRoots', 'graphics', 'masks'];
    const badSourceIds = [];
    for (const field of listFields) {
        const rows = result[field];
        if (!Array.isArray(rows)) continue;
        for (const row of rows) {
            if (!row || row.verified !== false) continue;
            const id = idFields.map(key => row[key]).find(value => typeof value === 'string' && value);
            if (id && !badSourceIds.includes(id)) badSourceIds.push(id);
            if (badSourceIds.length >= 40) break;
        }
        if (badSourceIds.length >= 40) break;
    }
    if (Array.isArray(result.failedSourceIds)) for (const id of result.failedSourceIds) {
        if (typeof id === 'string' && id && !badSourceIds.includes(id)) badSourceIds.push(id);
        if (badSourceIds.length >= 40) break;
    }
    return { falseChecks, badSourceIds: badSourceIds.slice(0, 40) };
}
function sourceSuppressionEvidence(root, node, originalLayer) {
    if (!root || !node) return false;
    const Api = api(), Presenter = cc.js.getClassByName('MonkeyStaticSortQueueProxyPresenter');
    if (!Presenter) fail('Presenter class script is not registered');
    let found = false;
    function visit(parent) {
        for (const child of parent.children || []) {
            if (Api.isGeneratedProxyRoot(child)) {
                const presenter = child.getComponent(Presenter);
                if (presenter && presenter.sourceRoot && presenter.sourceRoot.isValid) {
                    const index = presenter.sourceNodes.indexOf(node);
                    if (index >= 0 && presenter.originalLayers[index] === originalLayer &&
                        node.layer === presenter.hiddenLayer) found = true;
                }
            }
            visit(child);
        }
    }
    visit(root);
    return found;
}
function prepareForSerialization(presenter) {
    if (!presenter) return { applicable: false, status: 'not_applicable' };
    if (!presenter || typeof presenter.prepareForSerialization !== 'function') fail('Presenter serialization hook missing');
    presenter.prepareForSerialization();
}
function restoreAfterSerialization(presenter) {
    if (!presenter) return { applicable: false, status: 'not_applicable' };
    if (!presenter || typeof presenter.restoreAfterSerialization !== 'function') fail('Presenter restore hook missing');
    presenter.restoreAfterSerialization();
}
module.exports = { parentCanvas, API_CLASS_NAME, API_MODULE_UUID, registerApiClass, validatePlan, spec, attachSourceIdentities, createForPrefab,
    readPersistent, readInitialized, sourceSuppressionEvidence, prepareForSerialization, restoreAfterSerialization };
