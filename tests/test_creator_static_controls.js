'use strict';

const assert = require('node:assert/strict');
const Module = require('node:module');
const load = Module._load;

let componentCounter = 0;
class Component { constructor(node) { this.node = node; this.enabled = true; this.uuid = 'component-' + (++componentCounter); } }
class Sprite extends Component {}
class Label extends Component {}
class EditBox extends Component {
    constructor(node) { super(node); this._background = null; this._placeholderLabel = null; this._textLabel = null; this._maxLength = 20; }
    __preload() { this.node.position = [-15, 0, 0]; this._background = new Sprite(this.node); }
    onEnable() { this.node.position = [-15, 0, 0]; }
}
class MonkeyStaticEditBox extends EditBox {
    constructor(node) {
        super(node); this._impl = null; this.sourceComponentId = ''; this.sourceNodeId = '';
        this.sourceEnabled = false; this.sourceBackground = null; this.sourcePlaceholderLabel = null;
        this.sourceTextLabel = null; this.sourceMaxLength = 0;
    }
    __preload() {}
    onEnable() {}
    onDisable() {}
    onDestroy() {}
}
class Graphics extends Component {
    constructor(node) { super(node); this.customMaterial = null; this.builtin = {uuid: 'f0416e68-0200-4b77-a926-4f9d16e494da', effectAsset: {name: 'builtin-graphics',_uuid:'1c02ae6f-4492-4915-b8f8-7492a3b1e4cd'}}; }
    _updateMtlForGraphics() {}
    getMaterial() { return this.customMaterial || this.builtin; }
}
class Node {
    constructor(uuid) { this.uuid = uuid; this.components = []; }
    getComponent(type) { return this.components.find(row => row instanceof type) || null; }
    getComponents(type) { return this.components.filter(row => row instanceof type); }
    addComponent(type) { const row = new type(this); this.components.push(row); if (row.__preload) row.__preload(); return row; }
}
Module._load = function (request, parent, isMain) {
    if (request === 'cc') return {Sprite, Label, EditBox, Graphics,
        js: {getClassByName: name => name === 'MonkeyStaticEditBox' ? MonkeyStaticEditBox : null}};
    return load.call(this, request, parent, isMain);
};

const controls = require('../src/monkey/targets/CreatorStaticControls.js');
const root = new Node('input-node');
root.position = [265, 0, 0];
const graphicsNodeA = new Node('graphics-a');
const graphicsNodeB = new Node('graphics-b');
const backgroundNode = new Node('background-node');
const placeholderNode = new Node('placeholder-node');
const textNode = new Node('text-node');
const background = backgroundNode.addComponent(Sprite);
const placeholder = placeholderNode.addComponent(Label);
const text = textNode.addComponent(Label);
const nodes = new Map([['input-node', root], ['graphics-a', graphicsNodeA], ['graphics-b', graphicsNodeB]]);
const targets = new Map([['background', background], ['placeholder', placeholder], ['text', text]]);
const bindings = [
    {sourceId: 'editbox-1', node: 'input-node', sourceType: 'cc.EditBox', nativeCreatorType: 'cc.EditBox',
        enabled: false, maxLength: 150, inputBehavior: 'disabled-static-only', references: [
            {field: 'background', sourceId: 'background'}, {field: 'placeholderLabel', sourceId: 'placeholder'},
            {field: 'textLabel', sourceId: 'text'}]},
    {sourceId: 'graphics-1', node: 'graphics-a', sourceType: 'cc.Graphics', nativeCreatorType: 'cc.Graphics',
        enabled: false, sourceDrawingCommands: 'not-serialized-empty-in-fixed-state', materials: [
            {sourceId: 'source-material', effectName: 'builtin-graphics', nativeCreatorMaterialLookup: 'builtin-graphics'}]},
    {sourceId: 'graphics-2', node: 'graphics-b', sourceType: 'cc.Graphics', nativeCreatorType: 'cc.Graphics',
        enabled: false, sourceDrawingCommands: 'not-serialized-empty-in-fixed-state', materials: [
            {sourceId: 'source-material', effectName: 'builtin-graphics', nativeCreatorMaterialLookup: 'builtin-graphics'}]},
];
const resolver = id => targets.get(id);
const created = controls.createAssign(bindings, nodes, resolver);
const rows = controls.read(bindings, nodes, resolver, created);
assert.equal(rows.length, 3);
assert.equal(rows[0].enabled, false);
assert.equal(rows[0].nativeType, 'MonkeyStaticEditBox');
assert.equal(rows[0].sourceType, 'cc.EditBox');
assert.equal(rows[0].maxLength, 150);
assert.equal(rows[0].sourceMaxLength, 150);
assert.equal(rows[0].staticEditBoxPolicy, 'typed-source-references-without-base-lifecycle-v1');
assert.strictEqual(created.get('editbox-1')._background, null);
assert.strictEqual(created.get('editbox-1')._impl, null);
assert.deepStrictEqual(root.position, [265, 0, 0]);
assert.strictEqual(created.get('editbox-1').sourceBackground, background);
assert(rows[0].references.every(row => row.verified));
assert(rows.slice(1).every(row => row.enabled === false && row.materials[0].verified));

created.get('editbox-1').sourceBackground = text;
assert(controls.read(bindings, nodes, resolver, created)[0].references.some(row => !row.verified));
created.get('graphics-1').customMaterial = {uuid: 'wrong', effectAsset: {name: 'other-effect'}};
assert.equal(controls.read(bindings, nodes, resolver, created)[1].materials[0].verified, false);

assert.throws(() => controls.createAssign([{...bindings[0], enabled: true}], nodes, resolver), /MUST_BE_DISABLED/);
