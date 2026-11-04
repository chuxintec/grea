'use strict';
const assert = require('assert');
const Module = require('module');
const load = Module._load;
class Sprite { constructor(uuid) { this.uuid = uuid; } }
class ProgressBar {
    get barSprite() { return this._barSprite; }
    get progress() { return this._progress; }
    get totalLength() { return this._totalLength; }
    get mode() { return this._mode; }
    get reverse() { return this._reverse; }
}
Module._load = function (request, parent, isMain) {
    if (request === 'cc') return { Sprite, ProgressBar };
    return load.call(this, request, parent, isMain);
};
const helper = require('../src/monkey/targets/CreatorStaticProgress.js');
Module._load = load;

const sprite = new Sprite('sprite-component-uuid');
const component = new ProgressBar(); component.enabled = true;
const spec = {
    policy: 'native-static-progress-v1', sourceComponentId: 'prefab#12', sourceNodeId: 'prefab#3',
    barSpriteSourceId: 'prefab#9', progress: 0.35, totalLength: 200, mode: 1, reverse: true,
    sourceEnabled: true,
};
helper.bind(component, spec, sprite);
const result = helper.read(component, spec, sprite);
assert.deepStrictEqual(result, {
    sourceComponentId: 'prefab#12', sourceNodeId: 'prefab#3', barSpriteSourceId: 'prefab#9',
    barSpriteUuid: 'sprite-component-uuid', progress: 0.35, totalLength: 200, mode: 1,
    reverse: true, carrierEnabled: false, verified: true,
});
component._progress = 0.4;
assert.throws(() => helper.read(component, spec, sprite), /fields or Sprite reference differ/);
console.log('creator static progress bind/read passed');
