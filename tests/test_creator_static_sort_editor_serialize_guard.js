'use strict';

const assert = require('node:assert/strict');
const {install, uninstall, collectScopes, inspectScopes, probeRuntimeApi, installRuntimeCallProbe, PREFIX} = require('../src/monkey/targets/CreatorStaticSortSerialization.js');

class Node {
    constructor(uuid, layer = 1 << 28) {
        this.uuid = uuid; this._layer = layer; this.children = []; this.parent = null;
        this.components = new Map(); this.isValid = true;
    }
    get layer() { return this._layer; }
    set layer(value) {
        this.layerSetCount = (this.layerSetCount || 0) + 1;
        this._layer = value;
    }
    getComponent(type) { return this.components.get(type) || null; }
    addChild(child) { child.parent = this; this.children.push(child); return child; }
    addComponent(type, value) { value.node = this; this.components.set(type, value); return value; }
}
class Prefab { constructor(data) { this.data = data; } }
class Presenter {}
class Marker {}
const cc = {Node, Prefab, js: {getClassByName(name) {
    return name === 'MonkeyStaticSortQueueProxyPresenter' ? Presenter :
        name === 'MonkeyStaticSortQueueProxyMarker' ? Marker : null;
}}};

function makeScope(sourceRootId = 'root:1', parentRoot = null) {
    const authored = [1 << 25, 1 << 26];
    const root = new Node(sourceRootId, 1 << 28);
    if (parentRoot) parentRoot.addChild(root);
    const child = root.addChild(new Node(sourceRootId + ':child', 1 << 28));
    const proxyRoot = root.addChild(new Node(sourceRootId + ':generated', 1 << 29));
    const marker = proxyRoot.addComponent(Marker, Object.assign(new Marker(), {
        kind: 'root', sourceNode: sourceRootId, sourceRootOwner: root,
    }));
    const presenter = proxyRoot.addComponent(Presenter, Object.assign(new Presenter(), {
        sourceRootId, sourcePrefabId: 'prefab:' + sourceRootId, prefabPath: 'assets/' + sourceRootId + '.prefab',
        sourceRoot: root, proxyRoot, sourceNodes: [root, child], originalLayers: authored,
        hiddenLayer: 1 << 28,
    }));
    return {root, child, proxyRoot, marker, presenter, authored};
}

const logs = [];
const originalInfo = console.info;
console.info = value => logs.push(String(value));
try {
    let classLookupsBeforeRegistration = 0;
    const unregisteredCc = {Node, Prefab, js: {getClassByName() { classLookupsBeforeRegistration++; return null; }}};
    assert.deepEqual(inspectScopes(unregisteredCc, {kind: 'Material'}), {scopes: [], reason: 'non-node-input'});
    assert.equal(classLookupsBeforeRegistration, 0,
        'non-Node assets are classified before any static component registry lookup');
    const notYetRegisteredNode = new Node('before-class-registration', 123);
    assert.deepEqual(inspectScopes(unregisteredCc, notYetRegisteredNode), {scopes: [], reason: 'typed-classes-not-registered'});
    const earlyExtends = {serialize(input) { return input; }};
    const earlyApi = install(unregisteredCc, earlyExtends);
    assert.deepEqual(earlyExtends.serialize({kind: 'Material'}), {kind: 'Material'},
        'Material serialization passes through before Presenter/Marker classes register');
    assert.equal(earlyExtends.serialize(notYetRegisteredNode), notYetRegisteredNode,
        'ordinary Node serialization passes through while typed component classes are not registered');
    earlyApi.uninstall();

    const scope = makeScope();
    let calls = 0;
    const editorExtends = {serialize(input, options) {
        calls++;
        assert.equal(this, editorExtends, 'the EditorExtends receiver is preserved');
        assert.deepEqual(options, {keepNodeUuid: true}, 'the original options are passed unchanged');
        assert.deepEqual(scope.presenter.sourceNodes.map(node => node.layer), scope.authored,
            'only the exact owned source scope is restored while Parser enumerates its fields');
        return {layers: scope.presenter.sourceNodes.map(node => node.layer)};
    }};
    editorExtends.serialize.asAsset = uuid => ({uuid});
    const api = install(cc, editorExtends);
    assert.equal(typeof editorExtends.serialize, 'function');
    assert.equal(editorExtends.serialize.asAsset('a').uuid, 'a', 'the EditorExtends serializer namespace remains available');
    const result = editorExtends.serialize(new Prefab(scope.root), {keepNodeUuid: true});
    assert.deepEqual(result.layers, scope.authored);
    assert.equal(calls, 1);
    assert.deepEqual(scope.presenter.sourceNodes.map(node => node.layer), [1 << 28, 1 << 28],
        'finally restores the exact prior hidden layer state');
    assert.ok(logs.some(line => line.startsWith(PREFIX) && line.includes('"restoredNodeCount":2')),
        'the actual wrapper records matched identities and restoration count');
    api.uninstall();
    assert.equal(editorExtends.serialize.asAsset('b').uuid, 'b');

    const unowned = makeScope('unowned:1');
    const passthroughExtends = {serialize(input) {
        assert.equal(unowned.root.layer, 1 << 28, 'unowned payloads are not mutated');
        return input;
    }};
    install(cc, passthroughExtends);
    const plainNode = new Node('plain', 123);
    assert.equal(passthroughExtends.serialize(plainNode), plainNode,
        'a Node payload without typed Presenter/Marker ownership is passed through');
    assert.equal(unowned.root.layer, 1 << 28);
    uninstall();

    const quotaExtends = {serialize(input) { return input; }};
    const quotaApi = install(cc, quotaExtends);
    const noChange = makeScope('no-change:1');
    noChange.presenter.sourceNodes.forEach((node, index) => { node._layer = noChange.authored[index]; });
    quotaExtends.serialize(noChange.root);
    assert.equal(quotaApi.diagnostics().diagnosticCount, 0,
        'a matched native serialization with no hidden-to-authored change does not consume the diagnostic quota');
    const unrelatedRoot = new Node('unrelated-root', 123);
    for (let index = 0; index < 130; index++) quotaExtends.serialize(unrelatedRoot);
    assert.equal(quotaApi.diagnostics().diagnosticCount, 128,
        'unowned node diagnostics have a bounded quota while matched no-change native rows do not consume it');
    const afterQuota = makeScope('ordinary-save-after-quota:1');
    quotaExtends.serialize(afterQuota.root);
    assert.equal(quotaApi.diagnostics().priorityDiagnosticCount, 1,
        'a changed owned source layer still produces a priority ordinary-save receipt after native logs hit the cap');
    assert.ok(logs.some(line => line.startsWith(PREFIX) && line.includes('ordinary-save-after-quota:1') && line.includes('"changedLayerCount":2')),
        'the owned hidden-to-authored save evidence is not dropped by the generic diagnostic limit');
    uninstall();

    const outer = makeScope('outer:1');
    const inner = makeScope('inner:1', outer.root);
    outer.presenter.sourceNodes.push(inner.root, inner.child);
    outer.presenter.originalLayers.push(1 << 27, 1 << 24);
    inner.root._layer = 1 << 28; inner.child._layer = 1 << 28;
    assert.deepEqual(collectScopes(cc, outer.root).map(row => row.presenter), [outer.presenter],
        'rootmost scope alone owns serialization of its nested prefab closure');

    const malformed = makeScope('malformed:1');
    malformed.marker.sourceRootOwner = new Node('foreign-root');
    let malformedOriginalCalls = 0;
    const invalidExtends = {serialize() { malformedOriginalCalls++; }};
    install(cc, invalidExtends);
    assert.throws(() => invalidExtends.serialize(malformed.root), /MARKER_OWNER_INVALID/,
        'a foreign marker owner cannot become an unowned pass');
    assert.equal(malformedOriginalCalls, 0, 'invalid ownership fails before serializing hidden source layers');
    uninstall();

    const throwing = makeScope('throwing:1');
    const throwingExtends = {serialize() { throw new Error('native serialize failed'); }};
    install(cc, throwingExtends);
    assert.throws(() => throwingExtends.serialize(throwing.root), /native serialize failed/);
    assert.deepEqual(throwing.presenter.sourceNodes.map(node => node.layer), [1 << 28, 1 << 28],
        'serializer exceptions still restore the exact previous live layers');
    uninstall();

    class PrefabSceneProxy { save() { return true; } serialize() { return '{}'; } }
    class PrefabSceneFacade { saveScene() { return true; } }
    class GeneralSceneFacade { saveScene() { return true; } }
    class Parser { parse(input) { return input; } }
    const moduleRegistry = {
        'cce:/builtin/scene/prefab-scene-proxy': {id: 'cce:/builtin/scene/prefab-scene-proxy', n: {default: PrefabSceneProxy}},
        'cce:/builtin/scene/prefab-scene-facade': {id: 'cce:/builtin/scene/prefab-scene-facade', n: {default: PrefabSceneFacade}},
        'cce:/builtin/scene/general-scene-facade': {id: 'cce:/builtin/scene/general-scene-facade', n: {GeneralSceneFacade}},
        'cce:/builtin/engine/serialize-parser': {id: 'cce:/builtin/engine/serialize-parser', n: {Parser}},
    };
    const registrySymbol = Symbol('system-registry');
    const System = {[registrySymbol]: moduleRegistry, get(id) { return moduleRegistry[id] && moduleRegistry[id].n; }};
    const Editor = {Message: {request() {}}, Package: {getPackages: () => [{name: 'scene', path: '/builtin/scene', main: 'dist/browser/index'}]}};
    const compiledExtends = {serialize() {}, serializeCompiled() { return 'compiled'; }};
    const probeScene = new Node('prefab-scene', 123); probeScene.name = 'PrefabScene';
    probeScene.addChild(new Node('goose-root', 123)).name = 'GooseDetails';
    const probeCc = {Node, Prefab, director: {getScene: () => probeScene}, js: {getClassByName: () => null}};
    const fakeRequire = () => {};
    fakeRequire.cache = {
        '/app/builtin/scene/dist/script/3d/manager/scene/proxy/prefab-scene-proxy.js': {
            id: 'prefab-scene-proxy', loaded: true, exports: {PrefabSceneProxy},
        },
        '/project/assets/Game/scene-business.js': {id: 'scene-business', loaded: true, exports: {unrelated: true}},
    };
    const probeRealm = {System, Editor, cce: {SceneFacadeManager: {active: true}}};
    const runtime = probeRuntimeApi(probeCc, compiledExtends, probeRealm, fakeRequire);
    assert.doesNotThrow(() => JSON.stringify(runtime), 'runtime diagnostics are IPC-safe JSON data');
    assert.ok(runtime.facadeExports.some(row => row.className === 'PrefabSceneProxy' &&
        row.methods.some(method => method.name === 'save')),
    'runtime probe exposes actual registered Facade/Proxy class methods and module IDs');
    assert.equal(runtime.currentScene.name, 'PrefabScene');
    assert.equal(runtime.currentScene.childCount, 1);
    assert.equal(runtime.currentScene.directChildNames[0], 'GooseDetails');
    assert.ok(runtime.cce.descriptors.some(row => row.key === 'SceneFacadeManager'),
        'probe reports bounded cce top-level facade/manager descriptors without recursively scanning it');
    assert.equal(runtime.cachedBuiltinSceneModules.matchedModuleCount, 1,
        'require.cache inspection only returns already-loaded builtin/scene facade/proxy/serialize modules');
    assert.equal(runtime.cachedBuiltinSceneModules.modules[0].filename,
        '/app/builtin/scene/dist/script/3d/manager/scene/proxy/prefab-scene-proxy.js');
    const cachedProxy = runtime.cachedBuiltinSceneModules.modules[0].exportFunctions[0];
    assert.ok(cachedProxy.prototypeFunctions.some(row => row.name === 'serialize' && row.function.source.includes('serialize')),
        'cached scene module probe reports bounded actual source for the PrefabSceneProxy.serialize method');
    const compiledSave = compiledExtends.serializeCompiled;
    const proxySave = PrefabSceneProxy.prototype.save;
    const facadeSave = PrefabSceneFacade.prototype.saveScene;
    const parse = Parser.prototype.parse;

    const proxyScope = makeScope('actual-proxy-serializer:1');
    class PrefabInstance {}
    const sourceNestedNode = proxyScope.child;
    sourceNestedNode._prefab = {fileId: 'nested-star-file-id'};
    sourceNestedNode.templateLayer = 1 << 25;
    const staleLayerOverride = {targetInfo: {localID: ['nested-star-file-id']}, propertyPath: ['_layer'], value: 1 << 28};
    const unrelatedLayerOverride = {targetInfo: {localID: ['unrelated-file-id']}, propertyPath: ['_layer'], value: 1 << 24};
    const unrelatedFieldOverride = {targetInfo: {localID: ['nested-star-file-id']}, propertyPath: ['_name'], value: 'user-name'};
    const originalOverrides = [staleLayerOverride, unrelatedLayerOverride, unrelatedFieldOverride];
    const nestedInstance = Object.assign(new PrefabInstance(), {propertyOverrides: originalOverrides});
    proxyScope.root._prefab = {instance: nestedInstance};
    for (let index = 0; index < proxyScope.presenter.sourceNodes.length; index++) {
        const node = proxyScope.presenter.sourceNodes[index];
        node.authoredLayer = proxyScope.authored[index];
        node.prefabLayerOverrides = [{path: ['_layer'], value: 1 << 28}];
    }
    class OwnedPrefabSceneProxy {
        constructor(root) { this.root = root; }
        getRootNode() { return this.root; }
        serialize() {
            assert.deepEqual(proxyScope.presenter.sourceNodes.map(node => node.layer), proxyScope.authored,
                'the observed PrefabSceneProxy serializer sees authored source layers');
            assert.equal(nestedInstance.propertyOverrides[0].value, proxyScope.authored[1],
                'the exact nested PrefabInstance layer override is temporarily restored to its captured authored value');
            assert.equal(nestedInstance.propertyOverrides[1], unrelatedLayerOverride,
                'an unrelated override row keeps its exact object identity');
            assert.equal(nestedInstance.propertyOverrides[2], unrelatedFieldOverride,
                'other fields on the same nested source node remain untouched');
            return JSON.parse(JSON.stringify(proxyScope.presenter.sourceNodes.map(node => ({
                layer: node.layer, overrides: node.prefabLayerOverrides,
            })).concat([{overrides: nestedInstance.propertyOverrides}])));
        }
    }
    Object.defineProperty(OwnedPrefabSceneProxy, 'name', {value: 'PrefabSceneProxy'});
    const lateRequire = () => {};
    const prefabUtils = {getPrefabForSerialize(root) { return {prefab: new Prefab(root)}; }};
    lateRequire.cache = {'/app/builtin/scene/dist/script/3d/utils/prefab-utils.ccc': {
        id: 'prefab-utils', loaded: true, exports: {prefabUtils},
    }};
    const facadeExtends = {serialize(input) { return input; }};
    const installed = install(cc, facadeExtends, probeRealm, lateRequire);
    const nativeProxySerialize = OwnedPrefabSceneProxy.prototype.serialize;
    lateRequire.cache['/app/builtin/scene/dist/script/3d/manager/scene/proxy/prefab-scene-proxy.ccc'] = {
        id: 'prefab-scene-proxy', loaded: true, exports: {default: OwnedPrefabSceneProxy},
    };
    assert.equal(installed.refresh().cachedPrefabProxySerializeMethodsPatched, 1,
        'the exact built-in PrefabSceneProxy class is instrumented when its module registers after helper startup');
    const installedProbe = probeRuntimeApi(cc, facadeExtends, probeRealm, lateRequire);
    assert.ok(installedProbe.activeOwnedSerializationHooks.some(row =>
        row.label.endsWith('PrefabSceneProxy.serialize') && row.originalFunction.source.includes('serialize()')),
    'runtime diagnostics preserve the exact original SDK serializer source behind the installed wrapper');
    const writtenLayers = new OwnedPrefabSceneProxy(proxyScope.root).serialize();
    assert.deepEqual(writtenLayers.slice(0, 2), proxyScope.presenter.sourceNodes.map((node, index) => ({
        layer: proxyScope.authored[index], overrides: [{path: ['_layer'], value: 1 << 28}],
    })), 'serialized source Nodes retain their exact authored layer fields');
    assert.equal(writtenLayers[2].overrides[0].value, proxyScope.authored[1],
        'the serialized result captures the non-default authored layer override before finally restores live metadata');
    assert.notEqual(proxyScope.authored[1], sourceNestedNode.templateLayer,
        'the fixture proves a deliberate authored layer differing from its nested template default');
    assert.equal(nestedInstance.propertyOverrides, originalOverrides,
        'finally restores the exact original nested PrefabInstance override array reference');
    assert.equal(nestedInstance.propertyOverrides[0], staleLayerOverride);
    assert.equal(nestedInstance.propertyOverrides[0].value, 1 << 28,
        'finally leaves the live hidden override object exactly as it was before serialization');
    assert.deepEqual(proxyScope.presenter.sourceNodes.map(node => node.layer), [1 << 28, 1 << 28],
        'the built-in synchronous serialize hook restores the precise live layer snapshot in finally');
    const proxyReceipt = JSON.parse(logs.filter(line => line.startsWith(PREFIX) && line.includes('actual-proxy-serializer:1')).at(-1).slice(PREFIX.length + 1));
    const nestedEvidence = proxyReceipt.nestedLayerEvidence;
    assert.deepEqual(nestedEvidence.map(row => row.phase), [
        'before-authored-restore', 'before-native-serialize', 'after-native-serialize', 'after-live-layer-restore',
    ]);
    assert.deepEqual(nestedEvidence.map(row => row.rows[0].candidates[0].matching[0].value),
        [1 << 28, proxyScope.authored[1], proxyScope.authored[1], 1 << 28],
    'bounded scope diagnostics report the temporary authored override at the native serializer boundary');
    assert.ok(nestedEvidence.every(row => row.rows[0].candidates[0].referencePath === 'node._prefab.instance'),
        'override evidence follows the PrefabInfo.instance reference used by Creator serialization');
    assert.ok(installed.diagnostics().installedMethods.some(name => name.endsWith('PrefabSceneProxy.serialize')));
    installed.uninstall();
    assert.equal(OwnedPrefabSceneProxy.prototype.serialize, nativeProxySerialize);

    const preexistingHidden = makeScope('preexisting-hidden-override:1');
    preexistingHidden.presenter.originalLayers[1] = 1 << 28;
    preexistingHidden.child._prefab = {fileId: 'preexisting-local-id'};
    const preexistingRow = {targetInfo: {localID: ['preexisting-local-id']}, propertyPath: ['_layer'], value: 1 << 28};
    const preexistingArray = [preexistingRow];
    preexistingHidden.root._prefab = {instance: {propertyOverrides: preexistingArray}};
    class PreexistingPrefabSceneProxy {
        constructor(root) { this.root = root; }
        getRootNode() { return this.root; }
        serialize() { return this.root._prefab.instance.propertyOverrides; }
    }
    Object.defineProperty(PreexistingPrefabSceneProxy, 'name', {value: 'PrefabSceneProxy'});
    const preexistingRequire = () => {};
    preexistingRequire.cache = {'/app/builtin/scene/prefab-scene-proxy.ccc': {
        id: 'preexisting-proxy', loaded: true, exports: {default: PreexistingPrefabSceneProxy},
    }};
    const preexistingInstall = install(cc, {serialize(input) { return input; }}, probeRealm, preexistingRequire);
    const preexistingResult = new PreexistingPrefabSceneProxy(preexistingHidden.root).serialize();
    assert.equal(preexistingResult, preexistingArray,
        'a hidden override already captured as authored state is not rewritten or cloned');
    assert.equal(preexistingHidden.root._prefab.instance.propertyOverrides, preexistingArray);
    preexistingInstall.uninstall();

    const ambiguous = makeScope('ambiguous-nested-layer-override:1');
    ambiguous.child._prefab = {fileId: 'ambiguous-local-id'};
    const ambiguousArray = [
        {targetInfo: {localID: ['ambiguous-local-id']}, propertyPath: ['_layer'], value: 1 << 28},
        {targetInfo: {localID: ['ambiguous-local-id']}, propertyPath: ['_layer'], value: 1 << 28},
    ];
    ambiguous.root._prefab = {instance: {propertyOverrides: ambiguousArray}};
    const ambiguousRequire = () => {};
    ambiguousRequire.cache = {'/app/builtin/scene/prefab-scene-proxy.ccc': {
        id: 'ambiguous-proxy', loaded: true, exports: {default: PreexistingPrefabSceneProxy},
    }};
    const ambiguousInstall = install(cc, {serialize(input) { return input; }}, probeRealm, ambiguousRequire);
    const ambiguousProxy = new PreexistingPrefabSceneProxy(ambiguous.root);
    assert.throws(() => ambiguousProxy.serialize(), /NESTED_LAYER_OVERRIDE_AMBIGUOUS/,
        'duplicate localID/property rows fail closed rather than editing an arbitrary override');
    assert.equal(ambiguous.root._prefab.instance.propertyOverrides, ambiguousArray,
        'an ambiguous input leaves its original override collection intact');
    ambiguousInstall.uninstall();

    const callProbe = installRuntimeCallProbe(probeCc, compiledExtends, probeRealm, lateRequire);
    compiledExtends.serializeCompiled({type: 'prefab-data'});
    new PrefabSceneProxy().save(false);
    new PrefabSceneProxy().serialize(false);
    new PrefabSceneFacade().saveScene(false);
    new GeneralSceneFacade().saveScene(false);
    new Parser().parse({type: 'serialized-data'});
    assert.equal(prefabUtils.getPrefabForSerialize(proxyScope.root).prefab.data, proxyScope.root);
    const runtimeCalls = callProbe.summary().callCounts;
    assert.equal(runtimeCalls['EditorExtends.serializeCompiled'], 1);
    assert.equal(runtimeCalls['cce:/builtin/scene/prefab-scene-proxy:PrefabSceneProxy.save'], 1);
    assert.equal(runtimeCalls['cce:/builtin/scene/prefab-scene-proxy:PrefabSceneProxy.serialize'], 1);
    assert.equal(runtimeCalls['cce:/builtin/scene/prefab-scene-facade:PrefabSceneFacade.saveScene'], 1);
    assert.equal(runtimeCalls['cce:/builtin/scene/general-scene-facade:GeneralSceneFacade.saveScene'], 1);
    assert.equal(runtimeCalls['cce:/builtin/engine/serialize-parser:Parser.prototype.parse'], 1);
    assert.equal(runtimeCalls['prefab-utils:exports.prefabUtils.getPrefabForSerialize'], 1,
        'the exact already-loaded Creator prefab metadata utility is observed');
    const utilityModule = callProbe.initialProbe.cachedBuiltinSceneModules.modules.find(row => row.filename.includes('prefab-utils'));
    assert.ok(utilityModule.nestedExportFunctions.some(row => row.nestedName === 'getPrefabForSerialize' &&
        row.function.source.includes('getPrefabForSerialize')),
    'runtime probe exposes the exact loaded getPrefabForSerialize source');
    callProbe.uninstall();
    assert.equal(compiledExtends.serializeCompiled, compiledSave);
    assert.equal(PrefabSceneProxy.prototype.save, proxySave);
    assert.equal(PrefabSceneFacade.prototype.saveScene, facadeSave);
    assert.equal(Parser.prototype.parse, parse, 'runtime call probes restore every exact SDK method descriptor');
} finally {
    console.info = originalInfo;
    uninstall();
}

console.log('creator static sort EditorExtends serialization guard contracts passed');
