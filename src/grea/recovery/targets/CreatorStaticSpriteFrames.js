'use strict';
// Scene-local projection for validated source SpriteFrames. This helper never
// loads resources or executes source components; the caller supplies the
// exact target SpriteFrame resolver.
const cc = require('cc');

const PLAN_SCHEMA = 'monkey-prefab-static-sprite-projection-plan/1';

function vec3(value, field) {
    if (!Array.isArray(value) || value.length !== 3 || value.some(v => typeof v !== 'number' || !Number.isFinite(v)))
        throw Error('STATIC_SPRITE_VECTOR_INVALID: ' + field);
    return new cc.Vec3(value[0], value[1], value[2]);
}
function color(value, field) {
    if (!Array.isArray(value) || value.length !== 4 || value.some(v => !Number.isInteger(v) || v < 0 || v > 255))
        throw Error('STATIC_SPRITE_COLOR_INVALID: ' + field);
    return new cc.Color(value[0], value[1], value[2], value[3]);
}
function sceneClone(node, id) {
    let root = node;
    while (root && root.parent) root = root.parent;
    if (!(node instanceof cc.Node) || !node.isValid || !(root instanceof cc.Scene))
        throw Error('STATIC_SPRITE_REQUIRES_SCENE_CLONE: ' + id);
    return root;
}
function behaviorsDisabled(root) {
    const pending = [root];
    while (pending.length) {
        const node = pending.pop();
        for (const component of node.getComponents(cc.Component)) {
            const name = cc.js.getClassName(component.constructor) || '';
            if (!name.startsWith('cc.') && !name.startsWith('sp.') && component.enabled && !(name==='MonkeySpineUITransformPreserver' && require('./spine-ui-transform.js').isPreserver(component,cc)))
                throw Error('STATIC_SPRITE_ENABLED_USER_BEHAVIOR: ' + name);
        }
        pending.push(...node.children);
    }
}
function spriteComponent(node) {
    return node instanceof cc.Node ? node.getComponent(cc.Sprite) : null;
}
function assertSprite(sprite, entry, expectedFrame) {
    const frame = sprite && sprite.spriteFrame;
    const rect = frame && frame.rect;
    if (!sprite || !(frame instanceof cc.SpriteFrame) || !(expectedFrame instanceof cc.SpriteFrame) ||
        !frame._uuid || frame._uuid !== expectedFrame._uuid || !rect || Math.abs(rect.width - entry.spriteChild.originalSize[0]) > 0.01 ||
        Math.abs(rect.height - entry.spriteChild.originalSize[1]) > 0.01 ||
        sprite.sizeMode !== cc.Sprite.SizeMode.TRIMMED || sprite.enabled !== entry.spriteChild.enabled)
        throw Error('STATIC_SPRITE_READBACK_MISMATCH: ' + entry.projectionId);
}
function assertGeometry(parent,root,entry){
 const ui=root.getComponent(cc.UITransform),child=root.children[0],childUI=child&&child.getComponent(cc.UITransform);
 const near=(actual,expected)=>actual.length===expected.length&&actual.every((x,i)=>Number.isFinite(x)&&Math.abs(x-expected[i])<=0.0001);
 if(parent.children.length!==entry.expectedParentChildSourceIds.length+1||root.parent!==parent||root.getSiblingIndex()!==0||
    root.name!=='__monkey_static_sprite__'+entry.projectionId||root.children.length!==1||child.name!==entry.spriteChild.name||
    !ui||!childUI||root.active!==entry.root.active||root.layer!==parent.layer||child.layer!==parent.layer||
    !near([ui.width,ui.height],entry.root.size)||!near([root.position.x,root.position.y,root.position.z],entry.root.localPosition)||
    !near([root.scale.x,root.scale.y,root.scale.z],entry.root.localScale)||
    !near([childUI.width,childUI.height],entry.spriteChild.originalSize)||!near([childUI.anchorX,childUI.anchorY],entry.spriteChild.anchor)||
    !near([child.position.x,child.position.y,child.position.z],entry.spriteChild.localPosition))throw Error('STATIC_SPRITE_GEOMETRY_READBACK_MISMATCH: '+entry.projectionId);
 const c=child.getComponent(cc.Sprite).color;if(!near([c.r,c.g,c.b,c.a],entry.spriteChild.color))throw Error('STATIC_SPRITE_COLOR_READBACK_MISMATCH');
}
function Apply(plan, sourceNodes, resolveSpriteFrame) {
    if (!plan || plan.schema !== PLAN_SCHEMA || !Array.isArray(plan.entries) || !plan.entries.length)
        throw Error('STATIC_SPRITE_PLAN_INVALID');
    if (!(sourceNodes instanceof Map) || typeof resolveSpriteFrame !== 'function')
        throw Error('STATIC_SPRITE_RESOLVER_MISSING');
    const results = [];
    for (const entry of plan.entries) {
        if (!entry.targetResourceBound)
            throw Error('STATIC_SPRITE_TARGET_RESOURCE_UNBOUND: ' + entry.spriteChild.spriteFrameSourceId);
        const expectedFrame = resolveSpriteFrame(entry.spriteChild.spriteFrameSourceId);
        if (!(expectedFrame instanceof cc.SpriteFrame))
            throw Error('STATIC_SPRITE_TARGET_ASSET_TYPE: ' + entry.spriteChild.spriteFrameSourceId);
        const parent = sourceNodes.get(entry.parentSourceId);
        sceneClone(parent, entry.parentSourceId);
        if (parent.children.length !== entry.expectedParentChildSourceIds.length)
            throw Error('STATIC_SPRITE_PARENT_CHILDREN_MISMATCH: ' + entry.parentSourceId);
        behaviorsDisabled(parent);
        const generatedName = '__monkey_static_sprite__' + entry.projectionId;
        let root = parent.children.find(child => child.name === generatedName);
        if (!root) {
            root = new cc.Node(generatedName);
            root.layer=parent.layer;
            const rootUI=root.addComponent(cc.UITransform);rootUI.setContentSize(...entry.root.size);rootUI.setAnchorPoint(0.5,0.5);
            root.setPosition(vec3(entry.root.localPosition, 'root.localPosition'));
            root.setScale(vec3(entry.root.localScale, 'root.localScale'));
            color(entry.root.color,'root.color'); // Source grouping node has no renderer.
            root.active = entry.root.active;
            // The verified source parent is empty, so this sole child is sibling 0.
            parent.addChild(root);
            const child = new cc.Node(entry.spriteChild.name);child.layer=parent.layer;
            const childUI=child.addComponent(cc.UITransform);
            child.setPosition(vec3(entry.spriteChild.localPosition, 'spriteChild.localPosition'));
            childUI.setAnchorPoint(...entry.spriteChild.anchor);
            root.addChild(child);
            const sprite = child.addComponent(cc.Sprite);
            sprite.sizeMode = cc.Sprite.SizeMode.TRIMMED;
            sprite.spriteFrame = expectedFrame;
            childUI.setContentSize(...entry.spriteChild.originalSize);
            sprite.color = color(entry.spriteChild.color, 'spriteChild.color');
            sprite.enabled = entry.spriteChild.enabled;
        } else if (root.children.length !== 1 || root.children[0].name !== entry.spriteChild.name) {
            throw Error('STATIC_SPRITE_REENTRY_SHAPE_MISMATCH: ' + entry.projectionId);
        }
        const sprite = spriteComponent(root.children[0]);
        assertSprite(sprite, entry, expectedFrame);assertGeometry(parent,root,entry);
        results.push({ projectionId: entry.projectionId, parentSourceId: entry.parentSourceId,
            generatedNodeName: generatedName, spriteFrameSourceId: entry.spriteChild.spriteFrameSourceId,
            size: [sprite.node.getComponent(cc.UITransform).width, sprite.node.getComponent(cc.UITransform).height], verified: true, sourceBehaviorsExecuted: false });
    }
    return { schema: plan.schema, verified: results.every(row => row.verified), projections: results,
        sourceBehaviorsExecuted: false };
}

function Read(plan, sourceNodes, resolveSpriteFrame) {
    if (!plan || plan.schema !== PLAN_SCHEMA || !(sourceNodes instanceof Map) || typeof resolveSpriteFrame !== 'function')
        throw Error('STATIC_SPRITE_PLAN_INVALID');
    const projections = plan.entries.map(entry => {
        const expectedFrame = resolveSpriteFrame(entry.spriteChild.spriteFrameSourceId);
        if (!(expectedFrame instanceof cc.SpriteFrame)) throw Error('STATIC_SPRITE_TARGET_ASSET_TYPE: ' + entry.spriteChild.spriteFrameSourceId);
        const parent = sourceNodes.get(entry.parentSourceId);
        sceneClone(parent, entry.parentSourceId);
        const name = '__monkey_static_sprite__' + entry.projectionId;
        const root = parent.children.find(child => child.name === name);
        if (!root || root.children.length !== 1) return { projectionId: entry.projectionId, verified: false };
        const sprite = spriteComponent(root.children[0]);
        try { assertSprite(sprite, entry, expectedFrame);assertGeometry(parent,root,entry); } catch (error) { return { projectionId: entry.projectionId, verified: false, error: String(error.message || error) }; }
        const rect = sprite.spriteFrame.rect;
        return { projectionId: entry.projectionId, parentSourceId: entry.parentSourceId,
            spriteFrameSourceId: entry.spriteChild.spriteFrameSourceId,
            size: [rect.width, rect.height], active: root.active, verified: true };
    });
    return { schema: plan.schema, verified: projections.length > 0 && projections.every(row => row.verified),
        projections, sourceBehaviorsExecuted: false };
}

module.exports = { Apply, Read };
