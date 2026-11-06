'use strict';

const cc = require('cc');
// Creator 3.8.8 official builtin asset identities; source GLSL profile is pinned in the plan.
const graphicsMaterialUuid='f0416e68-0200-4b77-a926-4f9d16e494da',graphicsEffectUuid='1c02ae6f-4492-4915-b8f8-7492a3b1e4cd';
const graphicsIdentity=material=>material&&(material._uuid||material.uuid)===graphicsMaterialUuid&&material.effectAsset&&(material.effectAsset._uuid||material.effectAsset.uuid)===graphicsEffectUuid;

function exactComponent(resolver, sourceId) {
    const value = resolver(sourceId);
    if (!value || !value.node || !value.uuid) throw Error('STATIC_CONTROL_REFERENCE_MISSING: ' + sourceId);
    return value;
}
function staticEditBoxType() {
    const ctor = cc.js && cc.js.getClassByName('MonkeyStaticEditBox');
    if (typeof ctor !== 'function' || !(ctor.prototype instanceof cc.EditBox))
        throw Error('STATIC_EDITBOX_TYPED_SUBCLASS_MISSING');
    return ctor;
}

function createAssign(bindings, nodes, resolveComponent, builtinMaterials) {
    if (!Array.isArray(bindings)) throw Error('STATIC_CONTROL_PLAN_INVALID');
    const created = new Map();
    for (const spec of bindings) {
        const node = nodes.get(spec.node);
        if (!node) throw Error('STATIC_CONTROL_NODE_MISSING: ' + spec.sourceId);
        if (!spec || spec.enabled !== false) throw Error('STATIC_CONTROL_MUST_BE_DISABLED: ' + spec.sourceId);
        const ctor = spec.sourceType === 'cc.EditBox' ? staticEditBoxType() : spec.sourceType === 'cc.Graphics' ? cc.Graphics : null;
        if (!ctor) throw Error('STATIC_CONTROL_TYPE_UNSUPPORTED: ' + spec.sourceId);
        if (node.getComponent(ctor)) throw Error('STATIC_CONTROL_ALREADY_EXISTS: ' + spec.sourceId);
        const component = node.addComponent(ctor);
        if (!component || !(component instanceof ctor)) throw Error('STATIC_CONTROL_CREATE_FAILED: ' + spec.sourceId);
        component.enabled = false;
        if (spec.sourceType === 'cc.EditBox') {
            if (!Number.isInteger(spec.maxLength) || spec.maxLength < 0 || !Array.isArray(spec.references) || spec.references.length !== 3)
                throw Error('STATIC_EDITBOX_PLAN_INVALID: ' + spec.sourceId);
            const refs = Object.fromEntries(spec.references.map(ref => [ref.field, exactComponent(resolveComponent, ref.sourceId)]));
            if (!(refs.background instanceof cc.Sprite) || !(refs.placeholderLabel instanceof cc.Label) || !(refs.textLabel instanceof cc.Label))
                throw Error('STATIC_EDITBOX_REFERENCE_TYPE_MISMATCH: ' + spec.sourceId);
            // The native base `_background` field is public but not serialized.
            // Keep the source Sprite in a typed subclass field; do not call the
            // EditBox lifecycle that creates/positions labels or resizes nodes.
            component.sourceComponentId = spec.sourceId;
            component.sourceNodeId = spec.node;
            component.sourceEnabled = spec.sourceEnabled === true;
            component.sourceBackground = refs.background;
            component.sourcePlaceholderLabel = refs.placeholderLabel;
            component.sourceTextLabel = refs.textLabel;
            component.sourceMaxLength = spec.maxLength;
            component._placeholderLabel = refs.placeholderLabel;
            component._textLabel = refs.textLabel;
            component._maxLength = spec.maxLength;
            if (component.enabled !== false || component._impl !== null || component._background !== null ||
                component.sourceBackground !== refs.background || component.sourcePlaceholderLabel !== refs.placeholderLabel ||
                component.sourceTextLabel !== refs.textLabel || component.sourceMaxLength !== spec.maxLength ||
                component._placeholderLabel !== refs.placeholderLabel || component._textLabel !== refs.textLabel ||
                component._maxLength !== spec.maxLength)
                throw Error('STATIC_EDITBOX_TYPED_REFERENCE_ASSIGNMENT_FAILED: ' + spec.sourceId);
        } else {
            if (spec.sourceDrawingCommands !== 'not-serialized-empty-in-fixed-state' || !Array.isArray(spec.materials) || !spec.materials.length)
                throw Error('STATIC_GRAPHICS_PLAN_INVALID: ' + spec.sourceId);
            if (spec.materials.length !== 1 || spec.materials[0].nativeCreatorMaterialLookup !== 'builtin-graphics')
                throw Error('STATIC_GRAPHICS_MATERIAL_PROFILE_UNSUPPORTED: ' + spec.sourceId);
            let material=builtinMaterials&&builtinMaterials.get('builtin-graphics');
            if(!material){if(typeof component._updateMtlForGraphics!=='function')throw Error('STATIC_GRAPHICS_NATIVE_INITIALIZER_MISSING');component._updateMtlForGraphics();material=component.getMaterial(0);}
            const effectName = material && material.effectAsset && material.effectAsset.name;
            if (!graphicsIdentity(material))
                throw Error('STATIC_GRAPHICS_BUILTIN_MATERIAL_MISMATCH: ' + spec.sourceId);
            component.customMaterial = material;
            if (component.customMaterial !== material || component.getMaterial(0) !== material)
                throw Error('STATIC_GRAPHICS_MATERIAL_ASSIGNMENT_FAILED: ' + spec.sourceId);
        }
        created.set(spec.sourceId, component);
    }
    return created;
}

function read(bindings, nodes, resolveComponent, controls) {
    if (!Array.isArray(bindings)) throw Error('STATIC_CONTROL_PLAN_INVALID');
    return bindings.map(spec => {
        const node = nodes.get(spec.node);
        const ctor = spec.sourceType === 'cc.EditBox' ? staticEditBoxType() : spec.sourceType === 'cc.Graphics' ? cc.Graphics : null;
        const hasNativeQuery = node && ctor && typeof node.getComponents === 'function';
        const existing = hasNativeQuery ? node.getComponents(ctor) : [];
        if (hasNativeQuery && existing.length !== 1)
            throw Error('STATIC_CONTROL_NATIVE_COMPONENT_COUNT_MISMATCH: ' + spec.sourceId);
        const component = hasNativeQuery ? existing[0] : controls && controls.get(spec.sourceId);
        if (!component || component.enabled !== false || component.node !== nodes.get(spec.node))
            throw Error('STATIC_CONTROL_NATIVE_IDENTITY_MISMATCH: ' + spec.sourceId);
        const row = {sourceId: spec.sourceId, sourceType: spec.nativeCreatorType,
            nativeType: cc.js && cc.js.getClassName ? cc.js.getClassName(component) : component.constructor.name, enabled: component.enabled,
            componentUuid: component.uuid};
        if (spec.sourceType === 'cc.EditBox') {
            if (!(component instanceof staticEditBoxType()) || component._impl !== null || component._background !== null ||
                component.sourceComponentId !== spec.sourceId || component.sourceNodeId !== spec.node ||
                component.sourceEnabled !== (spec.sourceEnabled === true) || component.sourceMaxLength !== spec.maxLength ||
                component._maxLength !== spec.maxLength || component._placeholderLabel !== component.sourcePlaceholderLabel ||
                component._textLabel !== component.sourceTextLabel)
                throw Error('STATIC_EDITBOX_STATIC_CARRIER_MISMATCH: ' + spec.sourceId);
            const references = spec.references.map(ref => {
                const expected = exactComponent(resolveComponent, ref.sourceId);
                const actual = ref.field === 'background' ? component.sourceBackground :
                    ref.field === 'placeholderLabel' ? component.sourcePlaceholderLabel : component.sourceTextLabel;
                const baseActual = ref.field === 'background' ? component._background :
                    ref.field === 'placeholderLabel' ? component._placeholderLabel : component._textLabel;
                return {field: ref.field, sourceId: ref.sourceId, verified: actual === expected &&
                    (ref.field === 'background' ? baseActual === null : baseActual === expected),
                    nativeComponentUuid: actual && actual.uuid, baseFieldSerialized: ref.field !== 'background'};
            });
            row.maxLength = component._maxLength;
            row.sourceMaxLength = component.sourceMaxLength;
            row.sourceComponentId = component.sourceComponentId;
            row.sourceNodeId = component.sourceNodeId;
            row.sourceEnabled = component.sourceEnabled;
            row.staticEditBoxPolicy = 'typed-source-references-without-base-lifecycle-v1';
            row.references = references;
        } else {
            const material = component.customMaterial;
            const expected = spec.materials[0];
            const effectName = material && material.effectAsset && material.effectAsset.name;
            row.sourceDrawingCommands = spec.sourceDrawingCommands;
            row.materials = [{sourceId: expected.sourceId, effectName,
                nativeUuid: material && (material._uuid||material.uuid),nativeEffectUuid:material&&material.effectAsset&&(material.effectAsset._uuid||material.effectAsset.uuid),
                verified: material === component.customMaterial && graphicsIdentity(material)}];
        }
        return row;
    });
}

module.exports = {createAssign, read};
