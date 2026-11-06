'use strict';
const cc = require('cc');

// Apply source-authored fields to the native Creator ProgressBar component.
// Backing fields are serialized by Creator 3.8.8; assigning them directly
// avoids setters that recalculate Sprite geometry while constructing a static
// prefab. The component is disabled before serialization and has no live driver.
function bind(component, spec, sprite) {
    if (!(component instanceof cc.ProgressBar) || !spec || spec.policy !== 'native-static-progress-v1')
        throw new Error('STATIC_PROGRESS_SPEC_INVALID');
    if (!(sprite instanceof cc.Sprite)) throw new Error('STATIC_PROGRESS_SPRITE_MISSING: ' + spec.sourceComponentId);
    component.enabled = false;
    component._barSprite = sprite;
    component._progress = spec.progress;
    component._totalLength = spec.totalLength;
    component._mode = spec.mode;
    component._reverse = spec.reverse;
}

function read(component, spec, sprite) {
    if (!(component instanceof cc.ProgressBar) || !(sprite instanceof cc.Sprite) ||
        component.barSprite !== sprite || component.progress !== spec.progress ||
        component.totalLength !== spec.totalLength || component.mode !== spec.mode ||
        component.reverse !== spec.reverse || component.enabled !== false)
        throw new Error('Saved native static progress fields or Sprite reference differ: ' + spec.sourceComponentId);
    const spriteUuid = sprite && (sprite._uuid || sprite.uuid);
    if (typeof spriteUuid !== 'string' || !spriteUuid)
        throw new Error('Saved native static progress Sprite identity is unavailable: ' + spec.sourceComponentId);
    return {
        sourceComponentId: spec.sourceComponentId,
        sourceNodeId: spec.sourceNodeId,
        barSpriteSourceId: spec.barSpriteSourceId,
        barSpriteUuid: spriteUuid,
        progress: component.progress,
        totalLength: component.totalLength,
        mode: component.mode,
        reverse: component.reverse,
        carrierEnabled: component.enabled,
        verified: true,
    };
}

module.exports = { bind, read };
