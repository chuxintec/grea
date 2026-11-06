'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const Module = require('node:module');
const path = require('node:path');

const typescriptPath = '/Applications/Cocos/Creator/3.8.8/CocosCreator.app/Contents/Resources/app.asar.unpacked/node_modules/typescript/lib/typescript.js';
assert.ok(fs.existsSync(typescriptPath), 'Creator 3.8.8 TypeScript SDK is required');
const ts = require(typescriptPath);
const presenterPath = path.resolve(__dirname, '../src/monkey/targets/CreatorStaticSortQueueProxyPresenter.ts');
const source = fs.readFileSync(presenterPath, 'utf8');
assert.doesNotMatch(source, /serializeTag|_onBeforeSerialize/,
    'ordinary Editor save handling lives at the EditorExtends entry, not per-Node engine hooks');
const captureBlock = source.slice(source.indexOf('public captureOriginalLayers'), source.indexOf('public suppressSourceLayers'));
assert.doesNotMatch(captureBlock, /install.*Serialization/,
    'capturing source identity does not install a speculative serializer hook');
const transpiled = ts.transpileModule(source, {compilerOptions: {
    target: ts.ScriptTarget.ES2015,
    module: ts.ModuleKind.CommonJS,
    experimentalDecorators: true,
}}).outputText;

class Component {}
class Placeholder {}
const property = (...args) => args.length >= 2 ? undefined : () => undefined;
const cc = {_decorator: {ccclass: () => target => target, property, executeInEditMode: target => target},
    CCBoolean: Placeholder, CCInteger: Placeholder, Component, Label: Placeholder, Mask: Placeholder,
    Node: Placeholder, RichText: Placeholder, Sorting2D: Placeholder, Sprite: Placeholder, UITransform: Placeholder,
    UIRenderer: Placeholder};
const originalLoad = Module._load;
Module._load = function (request, parent, isMain) {
    if (request === 'cc') return cc;
    return originalLoad.call(this, request, parent, isMain);
};
const loaded = new Module(presenterPath, module);
loaded.filename = presenterPath;
loaded.paths = Module._nodeModulePaths(path.dirname(presenterPath));
loaded._compile(transpiled, presenterPath);
Module._load = originalLoad;

const Presenter = loaded.exports.CreatorStaticSortQueueProxyPresenter;
const presenter = new Presenter();
const node = {layer: 33554432, isValid: true};
presenter.captureOriginalLayers([node]);
presenter.hiddenLayer = 268435456;
presenter.suppressSourceLayers();
assert.equal(node.layer, 268435456, 'Editor source suppression remains active during ordinary editing');
presenter.restoreSourceLayers();
assert.equal(node.layer, 33554432, 'Presenter restores the recorded source layer on disable/serialization teardown');

console.log('creator static sort layer lifecycle contracts passed');
