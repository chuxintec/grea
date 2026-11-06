'use strict';
// Scene-local clone/layout application for a prepared source-backed clone batch.
// Source scripts are never enabled or invoked. Native mode runs cc.Layout;
// source-manual mode applies only the hash-pinned positions in the batch.
const cc = require('cc');
const states = require('./preview-state.js');
const sourceChildren = require('./static-richtext.js').sourceChildren;

const HASH = /^[0-9a-f]{64}$/;
const COLOR_KIND = 'sprite.color';

function need(value, label) {
    if (typeof value !== 'string' || !value.trim()) throw Error('PREVIEW_CLONE_INVALID: ' + label);
    return value;
}
function colorTarget(op, resolve) {
    const targetKind = op.targetKind || 'component';
    if (targetKind === 'node') {
        const node = resolve(op.targetNodeSourceId || op.sourceId);
        const sprite = resolve(op.targetComponentSourceId);
        if (!(node instanceof cc.Node) || !(sprite instanceof cc.Sprite) || sprite.node !== node)
            throw Error('PREVIEW_CLONE_COLOR_TARGET: ' + op.sourceId);
        // Creator 3 moves the source Node color to the renderer component.
        return {read: () => [sprite.color.r, sprite.color.g, sprite.color.b, sprite.color.a],
            write: value => { sprite.color = new cc.Color(...value); }};
    }
    if (targetKind !== 'component') throw Error('PREVIEW_CLONE_COLOR_TARGET_KIND: ' + targetKind);
    const sprite = resolve(op.targetComponentSourceId || op.sourceId);
    if (!(sprite instanceof cc.Sprite)) throw Error('PREVIEW_CLONE_COLOR_TARGET: ' + op.sourceId);
    return {read: () => [sprite.color.r, sprite.color.g, sprite.color.b, sprite.color.a],
        write: value => { sprite.color = new cc.Color(...value); }};
}
function equalColor(a, b) {
    return Array.isArray(a) && Array.isArray(b) && a.length === 4 && b.length === 4 &&
        a.every((v, i) => Number.isFinite(v) && v === b[i]);
}
function assertStaticOnly(root) {
    const pending = [root];
    while (pending.length) {
        const node = pending.pop();
        if (!(node instanceof cc.Node) || !node.isValid) throw Error('PREVIEW_CLONE_INVALID_NODE');
        for (const component of node.getComponents(cc.Component)) {
            const className = cc.js.getClassName(component.constructor) || '';
            if (!className.startsWith('cc.') && !className.startsWith('sp.') && component.enabled && !(className==='MonkeySpineUITransformPreserver' && require('./spine-ui-transform.js').isPreserver(component,cc)))
                throw Error('PREVIEW_CLONE_ENABLED_SOURCE_BEHAVIOR: ' + className);
        }
        pending.push(...node.children);
    }
}
function validate(batch, sourceNodes) {
    if (!batch || batch.schema !== 'monkey-prefab-preview-clone-batch/1' ||
        !HASH.test(batch.cloneSpecSha256 || '') || !HASH.test(batch.sourcePlanSha256 || '') ||
        !HASH.test(batch.sourceManifestSha256 || '') ||
        typeof batch.sourcePrefabId !== 'string' || !Array.isArray(batch.instances) || !batch.instances.length)
        throw Error('PREVIEW_CLONE_BATCH_INVALID');
    if (!(sourceNodes instanceof Map)) throw Error('PREVIEW_CLONE_SOURCE_NODE_MAP_REQUIRED');
    const layout = batch.template;
    if (!layout || !['native-layout', 'source-manual'].includes(layout.layoutMode) || layout.positionsAreTargetReadbackOnly !== true ||
        !Array.isArray(layout.sourceTree) || !layout.sourceTree.length)
        throw Error('PREVIEW_CLONE_LAYOUT_CONTRACT_REQUIRED');
    const rootId = need(layout.rootSourceId, 'template.rootSourceId');
    const parentId = need(layout.parentSourceId, 'template.parentSourceId');
    const templatePrefabId = need(batch.templatePrefabId || batch.sourcePrefabId, 'templatePrefabId');
    const external = templatePrefabId !== batch.sourcePrefabId;
    const sourceRootParentId = Object.prototype.hasOwnProperty.call(layout, 'sourceRootParentSourceId')
        ? layout.sourceRootParentSourceId : parentId;
    const placeholderId = layout.replacePlaceholderSourceId;
    const placementMode = layout.placementMode || (external ? 'replace-placeholder' : 'reuse-source-child');
    if (!['reuse-source-child', 'replace-placeholder', 'append-external'].includes(placementMode))
        throw Error('PREVIEW_CLONE_PLACEMENT_MODE_INVALID');
    const append = placementMode === 'append-external';
    const initialChildIds = layout.initialChildSourceIds;
    const appendStart = layout.appendStartSiblingIndex;
    const initialChildId = external ? placeholderId : rootId;
    if (!Array.isArray(initialChildIds) || initialChildIds.some(id => typeof id !== 'string'))
        throw Error('PREVIEW_CLONE_INITIAL_CHILDREN_INVALID');
    if (append) {
        if (!external || placeholderId != null || sourceRootParentId != null ||
            !Number.isInteger(appendStart) || appendStart !== initialChildIds.length)
            throw Error('PREVIEW_CLONE_APPEND_CONTRACT_INVALID');
    } else if (initialChildIds.length !== 1 || initialChildIds[0] !== initialChildId) {
        throw Error('PREVIEW_CLONE_PARENT_INITIAL_CHILDREN_MISMATCH');
    }
    if (!rootId.startsWith(templatePrefabId + '#') || !parentId.startsWith(batch.sourcePrefabId + '#'))
        throw Error('PREVIEW_CLONE_TEMPLATE_OUTSIDE_DECLARED_PREFABS');
    if (!sourceNodes.has(parentId) || (append ? initialChildIds.some(id => !sourceNodes.has(id)) :
        (external ? !sourceNodes.has(placeholderId) : !sourceNodes.has(rootId))))
        throw Error('PREVIEW_CLONE_SOURCE_NODE_MISSING');
    if (external && !append && (!placeholderId.startsWith(batch.sourcePrefabId + '#') ||
        sourceRootParentId === parentId || layout.initialChildSourceIds?.[0] !== placeholderId))
        throw Error('PREVIEW_CLONE_EXTERNAL_TEMPLATE_CONTRACT_INVALID');
    if (!external && (sourceRootParentId !== parentId || placeholderId != null))
        throw Error('PREVIEW_CLONE_SAME_PREFAB_CONTRACT_INVALID');
    const keys = new Set(), tree = new Map();
    for (const row of layout.sourceTree) {
        if (!row || typeof row.sourceId !== 'string' || tree.has(row.sourceId) ||
            !Array.isArray(row.childrenSourceIds) || !Array.isArray(row.componentSourceIds))
            throw Error('PREVIEW_CLONE_SOURCE_TREE_INVALID');
        tree.set(row.sourceId, row);
    }
    if (!tree.has(rootId)) throw Error('PREVIEW_CLONE_SOURCE_TREE_ROOT_MISSING');
    const seen = new Set(), pending = [rootId];
    while (pending.length) {
        const id = pending.pop();
        if (seen.has(id)) throw Error('PREVIEW_CLONE_SOURCE_TREE_CYCLE');
        seen.add(id);
        const row = tree.get(id);
        if (!row) throw Error('PREVIEW_CLONE_SOURCE_TREE_CHILD_MISSING: ' + id);
        for (const child of row.childrenSourceIds) pending.push(child);
    }
    if (seen.size !== tree.size) throw Error('PREVIEW_CLONE_SOURCE_TREE_EXTRA_NODE');
    const manual = layout.layoutMode === 'source-manual' ? layout.sourceManualLayout : null;
    if (manual && (!['centered-horizontal-linear/1', 'progress-threshold-centers/1', 'pass-task-linear-y/1'].includes(manual.formulaId) || manual.count !== batch.instances.length ||
        typeof manual.sourceEvidenceId !== 'string' || !HASH.test(manual.sourceCodeSha256 || '') ||
        !HASH.test(manual.sourceSpanSha256 || '') || !Number.isFinite(manual.sourceTemplateY) ||
        (manual.formulaId === 'centered-horizontal-linear/1' && (!Number.isFinite(manual.templateWidth) ||
            !Number.isFinite(manual.gap) || manual.templateWidth <= manual.gap)) ||
        (manual.formulaId === 'progress-threshold-centers/1' && (!Number.isFinite(manual.progressBarTotalLength) ||
            manual.progressBarTotalLength <= 0 || !Number.isInteger(manual.totalThresholdCount) || manual.totalThresholdCount <= manual.count)) ||
        (manual.formulaId === 'pass-task-linear-y/1' && (!Number.isFinite(manual.passItemHeight) || manual.passItemHeight <= 0 ||
            !Number.isFinite(manual.spacingY) || manual.spacingY < 0))))
        throw Error('PREVIEW_CLONE_SOURCE_MANUAL_EVIDENCE_INVALID');
    if (layout.layoutMode === 'source-manual' && (!manual || (external && !append) ||
        !Number.isInteger(manual.count))) throw Error('PREVIEW_CLONE_SOURCE_MANUAL_UNSUPPORTED');
    if (!Array.isArray(layout.initialChildSourceIds) || layout.initialChildSourceIds.some((id, index) =>
        index > 0 && layout.initialChildSourceIds.slice(0, index).includes(id)))
        throw Error('PREVIEW_CLONE_PARENT_INITIAL_CHILDREN_MISMATCH');
    const expectedChildCount = append ? initialChildIds.length + batch.instances.length : batch.instances.length + (layout.layoutMode === 'source-manual' ? 1 : 0);
    if (layout.expectedChildCount !== expectedChildCount) throw Error('PREVIEW_CLONE_EXPECTED_CHILD_COUNT_INVALID');
    if (append && layout.layoutMode === 'native-layout') {
        const rule = layout.appendLayoutRule;
        const derivedColumns = rule && Array.isArray(rule.sourceParentSize) && rule.sourceParentSize.length === 2 &&
            Array.isArray(rule.padding) && rule.padding.length === 4 && Array.isArray(rule.spacing) && rule.spacing.length === 2 &&
            Array.isArray(rule.cellSize) && rule.cellSize.length === 2
            ? Math.max(1, Math.floor((rule.sourceParentSize[0] - rule.padding[0] - rule.padding[2] + rule.spacing[0] + 1e-9) /
                (rule.cellSize[0] + rule.spacing[0]))) : 0;
        const derivedRows = derivedColumns > 0 ? Math.ceil(rule.count / derivedColumns) : 0;
        const derivedHeight = derivedRows * (rule?.cellSize?.[1] || 0) + Math.max(0, derivedRows - 1) * (rule?.spacing?.[1] || 0) +
            (rule?.padding?.[1] || 0) + (rule?.padding?.[3] || 0);
        if (!rule || rule.formulaId !== 'cocos-grid-auto-columns-top-left/1' || rule.count !== batch.instances.length ||
            rule.sourceLayoutType !== 3 || rule.sourceResizeMode !== 1 || rule.sourceStartAxis !== 0 || rule.sourceHorizontalDirection !== 0 ||
            rule.sourceVerticalDirection !== 1 || rule.sourceConstraint !== 0 ||
            !Number.isInteger(rule.sourceConstraintCount) || rule.sourceConstraintCount < 0 ||
            !Number.isInteger(rule.columns) || rule.columns !== derivedColumns || rule.rows !== derivedRows ||
            !Array.isArray(rule.cellSize) || rule.cellSize.length !== 2 || rule.cellSize.some(v => !Number.isFinite(v) || v <= 0) ||
            !Array.isArray(rule.spacing) || rule.spacing.length !== 2 || rule.spacing.some(v => !Number.isFinite(v) || v < 0) ||
            !Array.isArray(rule.padding) || rule.padding.length !== 4 || rule.padding.some(v => !Number.isFinite(v) || v < 0) ||
            !Array.isArray(rule.sourceParentSize) || rule.sourceParentSize.length !== 2 || rule.sourceParentSize.some(v => !Number.isFinite(v) || v <= 0) ||
            !Array.isArray(rule.expectedParentSize) || rule.expectedParentSize.length !== 2 ||
            Math.abs(rule.expectedParentSize[0]-rule.sourceParentSize[0])>1e-3 || Math.abs(rule.expectedParentSize[1]-derivedHeight)>1e-3 ||
            !Array.isArray(rule.inactiveOwnerChildSourceIds) || rule.inactiveOwnerChildSourceIds.length !== initialChildIds.length ||
            rule.inactiveOwnerChildSourceIds.some((id, i) => id !== initialChildIds[i]))
            throw Error('PREVIEW_CLONE_APPEND_LAYOUT_RULE_INVALID');
    }
    for (let i = 0; i < batch.instances.length; i++) {
        const row = batch.instances[i];
        const siblingIndex = append ? appendStart + i : layout.layoutMode === 'source-manual' ? i + 1 : i;
        const mode = append ? 'append-clone' : layout.layoutMode === 'source-manual' ? 'clone-template' : (i === 0 ? 'reuse-template' : 'clone-template');
        if (!row || typeof row.instanceId !== 'string' || keys.has(row.instanceId) ||
            row.siblingIndex !== siblingIndex || row.sourceNodeId !== rootId || row.parentSourceId !== parentId ||
            row.mode !== mode ||
            !row.previewState || row.previewState.sourcePrefabId !== templatePrefabId ||
            row.previewState.sourceManifestSha256 !== batch.sourceManifestSha256 ||
            !HASH.test(row.previewState.stateSha256 || '') || !Array.isArray(row.previewState.operations))
            throw Error('PREVIEW_CLONE_INSTANCE_INVALID: ' + i);
        keys.add(row.instanceId);
        if (manual) {
            let expectedX;
            if (manual.formulaId === 'centered-horizontal-linear/1') {
                const step = manual.templateWidth - manual.gap;
                expectedX = -(manual.count * step) / 2 + step / 2 + i * step;
            } else if (manual.formulaId === 'progress-threshold-centers/1') {
                const step = manual.progressBarTotalLength / manual.totalThresholdCount;
                expectedX = -manual.progressBarTotalLength / 2 + (i + 1) * step;
            } else {
                const layoutIndex = Number.isInteger(row.layoutIndex) && row.layoutIndex >= 0 ? row.layoutIndex : i;
                const expectedY = -manual.passItemHeight / 2 - layoutIndex * (manual.passItemHeight + manual.spacingY);
                if (!Array.isArray(row.position) || row.position.length !== 3 || row.positionEvidenceId !== manual.sourceEvidenceId ||
                    row.position.some((v,j) => !Number.isFinite(v) || Math.abs(v - [0, expectedY, 0][j]) > 1e-6))
                    throw Error('PREVIEW_CLONE_SOURCE_MANUAL_POSITION_INVALID: ' + row.instanceId);
                expectedX = null;
            }
            if (expectedX !== null) {
                const expected = [expectedX, manual.sourceTemplateY, 0];
                if (!Array.isArray(row.position) || row.position.length !== 3 || row.positionEvidenceId !== manual.sourceEvidenceId ||
                    row.position.some((v, j) => !Number.isFinite(v) || Math.abs(v - expected[j]) > 1e-6))
                    throw Error('PREVIEW_CLONE_SOURCE_MANUAL_POSITION_INVALID: ' + row.instanceId);
            }
        }
    const componentIds = new Set(layout.sourceTree.flatMap(node => node.componentSourceIds || []));
    const nodeIds = new Set(layout.sourceTree.map(node => node.sourceId));
        for (const op of row.extraOperations || []) {
            const targetKind = op && (op.targetKind || 'component');
            const validColorTarget = targetKind === 'node'
                ? nodeIds.has(op.sourceId) && op.targetNodeSourceId === op.sourceId && componentIds.has(op.targetComponentSourceId) &&
                    tree.get(op.sourceId).componentSourceIds.includes(op.targetComponentSourceId)
                : targetKind === 'component' && componentIds.has(op.sourceId) &&
                    (!op.targetComponentSourceId || op.targetComponentSourceId === op.sourceId) &&
                    (!op.targetNodeSourceId || nodeIds.has(op.targetNodeSourceId));
            if (!op || op.kind !== COLOR_KIND || !validColorTarget ||
                !Array.isArray(op.expectedValue) || !Array.isArray(op.value) ||
                op.expectedValue.length !== 4 || op.value.length !== 4 ||
                [...op.expectedValue, ...op.value].some(v => !Number.isInteger(v) || v < 0 || v > 255))
                throw Error('PREVIEW_CLONE_EXTRA_OPERATION_INVALID: ' + row.instanceId);
        }
    }
    return {tree, rootId, parentId, templatePrefabId, external, placeholderId, initialChildId,
        placementMode, append, appendStart, initialChildIds, manual: layout.layoutMode === 'source-manual'};
}
function mapCloneTree(tree, rootId, root) {
    const result = new Map(), pending = [[rootId, root]];
    while (pending.length) {
        const [sourceId, node] = pending.pop(), source = tree.get(sourceId);
        if (!(node instanceof cc.Node) || !node.isValid || !source || result.has(sourceId))
            throw Error('PREVIEW_CLONE_TREE_READBACK_INVALID: ' + sourceId);
        const children = sourceChildren(node);
        if (node.name !== source.name || children.length !== source.childrenSourceIds.length)
            throw Error('PREVIEW_CLONE_HIERARCHY_MISMATCH: ' + sourceId);
        result.set(sourceId, node);
        for (let i = source.childrenSourceIds.length - 1; i >= 0; i--)
            pending.push([source.childrenSourceIds[i], children[i]]);
    }
    return result;
}
function applyExtraOperations(row, resolve) {
    const results = [];
    for (const op of row.extraOperations || []) {
        const target = colorTarget(op, resolve);
        const before = target.read();
        if (!equalColor(before, op.expectedValue) && !equalColor(before, op.value))
            throw Error('PREVIEW_CLONE_REENTRY_MISMATCH: ' + op.sourceId);
        if (equalColor(before, op.expectedValue)) target.write(op.value);
        const actual = target.read();
        results.push({kind: op.kind, sourceId: op.sourceId, expectedValue: op.expectedValue,
            value: op.value, actualValue: actual, verified: equalColor(actual, op.value)});
    }
    return results;
}
function colorReadback(row, resolve) {
    return (row.extraOperations || []).map(op => {
        const actual = colorTarget(op, resolve).read();
        return {kind: op.kind, sourceId: op.sourceId, expectedValue: op.expectedValue,
            value: op.value, actualValue: actual, verified: equalColor(actual, op.value)};
    });
}
function layoutReadback(batch, parent, roots, tree) {
    const first = roots[0], expected = batch.template.firstSourcePosition;
    const layout = parent.getComponent(cc.Layout);
    if (batch.template.layoutMode === 'native-layout') {
        if (!layout || !layout.enabled || typeof layout.updateLayout !== 'function')
            return {status: 'layout_missing', verified: false, items: []};
        layout.updateLayout();
    }
    const rows = roots.map((node, index) => ({
        instanceId: batch.instances[index].instanceId,
        siblingIndex: node.getSiblingIndex(),
        parentMatches: node.parent === parent,
        size: [node.getComponent(cc.UITransform).width, node.getComponent(cc.UITransform).height],
        position: [node.position.x, node.position.y, node.position.z],
    }));
    const firstSourceMatches = Array.isArray(expected) && expected.length === 3 &&
        Math.abs(rows[0].position[0] - expected[0]) <= 1e-4 && Math.abs(rows[0].position[1] - expected[1]) <= 1e-4 &&
        Math.abs(rows[0].position[2] - expected[2]) <= 1e-4;
    if (batch.template.layoutMode === 'source-manual') {
        const positionsMatch = rows.every((row, i) => batch.instances[i].position.every((v, j) => Math.abs(row.position[j] - v) <= 1e-4));
        const append = batch.template.placementMode === 'append-external';
        const start = append ? batch.template.appendStartSiblingIndex : 1;
        const orderMatches = rows.every((row, index) => row.siblingIndex === start + index && row.parentMatches);
        return {status: positionsMatch && orderMatches ? 'source_manual_position_pass' : 'source_manual_position_partial',
            verified: positionsMatch && orderMatches, firstSourcePosition: rows[0].position,
            expectedSourcePosition: batch.instances[0].position, items: rows};
    }
    if (batch.template.placementMode === 'append-external') {
        const rule = batch.template.appendLayoutRule;
        const parentTransform = parent.getComponent(cc.UITransform);
        const parentSize = parentTransform ? [parentTransform.width, parentTransform.height] : [];
        const sizeMatches = parentSize.length === 2 && rule.expectedParentSize.every((value, i) => Math.abs(parentSize[i] - value) <= 1e-3);
        const orderMatches = rows.every((row, i) => row.siblingIndex === batch.template.appendStartSiblingIndex + i && row.parentMatches);
        const positionsMatch = rows.every((row, i) => {
            const col = i % rule.columns, r = Math.floor(i / rule.columns);
            const [left, _bottom, _right, top] = rule.padding;
            const [cw, ch] = rule.cellSize, [sx, sy] = rule.spacing;
            const expectedX = -parentSize[0] / 2 + left + cw / 2 + col * (cw + sx);
            const expectedY = parentSize[1] / 2 - top - ch / 2 - r * (ch + sy);
            return Math.abs(row.position[0] - expectedX) <= 1e-4 &&
                Math.abs(row.position[1] - expectedY) <= 1e-4 && Math.abs(row.position[2]) <= 1e-4 &&
                Math.abs(row.size[0] - cw) <= 1e-4 && Math.abs(row.size[1] - ch) <= 1e-4;
        });
        const verified = sizeMatches && orderMatches && positionsMatch;
        return {status: verified ? 'append_grid_source_rule_pass' : 'append_grid_source_rule_partial', verified,
            firstSourcePosition: rows[0].position, expectedSourcePosition: rows[0] ? [
                -parentSize[0] / 2 + rule.padding[0] + rule.cellSize[0] / 2,
                parentSize[1] / 2 - rule.padding[2] - rule.cellSize[1] / 2, 0] : [],
            parentSize, expectedParentSize: rule.expectedParentSize, items: rows};
    }
    const orderMatches = rows.every((row, index) => row.siblingIndex === index && row.parentMatches);
    return {status: firstSourceMatches && orderMatches ? 'native_layout_readback_pass' : 'native_layout_readback_partial',
        verified: firstSourceMatches && orderMatches, firstSourcePosition: rows[0].position,
        expectedSourcePosition: expected, items: rows};
}

function Apply(batch, sourceNodes, resolverFactory, settleLayout, templateProvider) {
    const validated = validate(batch, sourceNodes);
    if (typeof resolverFactory !== 'function' || (!validated.manual && typeof settleLayout !== 'function'))
        throw Error('PREVIEW_CLONE_CALLBACK_REQUIRED');
    const parent = sourceNodes.get(validated.parentId);
    const append = validated.append;
    if (append && batch.template.layoutMode === 'native-layout' &&
        (!parent.activeInHierarchy || !validated.initialChildIds.every(id => !sourceNodes.get(id).activeInHierarchy)))
        throw Error('PREVIEW_CLONE_APPEND_LAYOUT_ACTIVE_OWNER_CHILD_UNSUPPORTED');
    const placeholder = validated.external && !append ? sourceNodes.get(validated.placeholderId) : null;
    const template = validated.external
        ? (typeof templateProvider === 'function' ? templateProvider(validated.templatePrefabId, validated.rootId) : null)
        : sourceNodes.get(validated.rootId);
    if (!(template instanceof cc.Node) || !template.isValid)
        throw Error(validated.external ? 'PREVIEW_CLONE_EXTERNAL_TEMPLATE_PROVIDER_REQUIRED' : 'PREVIEW_CLONE_SOURCE_NODE_MISSING');
    const layout = parent.getComponent(cc.Layout);
    if (!validated.manual && (!layout || !layout.enabled)) throw Error('PREVIEW_CLONE_NATIVE_LAYOUT_MISSING');
    const initialChildren = parent.children.slice();
    if (initialChildren.length !== validated.initialChildIds.length ||
        !validated.initialChildIds.every((id, index) => initialChildren[index] === sourceNodes.get(id)))
        throw Error('PREVIEW_CLONE_PARENT_STATE_MISMATCH');
    if (validated.external && (template.parent || template === placeholder))
        throw Error('PREVIEW_CLONE_EXTERNAL_TEMPLATE_MUST_BE_DETACHED');
    const originalPosition = [template.position.x, template.position.y, template.position.z];
    if (!Array.isArray(batch.template.firstSourcePosition) ||
        originalPosition.some((v, i) => Math.abs(v - batch.template.firstSourcePosition[i]) > 1e-4))
        throw Error('PREVIEW_CLONE_TEMPLATE_POSITION_MISMATCH');
    assertStaticOnly(template);
    const roots = (validated.manual || append) ? [] : [template], added = [];
    const oldActive = template.active;
    const oldPlaceholderActive = placeholder && placeholder.active;
    const oldLayoutEnabled = layout && layout.enabled;
    try {
        // Native mode reuses row 0, matching the source pool. Manual mode retains
        // the original hidden template and clones every row. All copies start inactive.
        template.active = false;
        if (append && validated.manual && layout) layout.enabled = false;
        if (validated.external && !append) { placeholder.active = false; placeholder.parent = null; template.parent = parent; }
        if (validated.manual) {
            for (let i = 0; i < batch.instances.length; i++) {
                const row = batch.instances[i], clone = cc.instantiate(template);
                clone.active = false; assertStaticOnly(clone); clone.parent = parent;
                clone.setSiblingIndex(row.siblingIndex); clone.setPosition(...row.position);
                added.push(clone); roots.push(clone);
            }
        } else if (append) {
            for (const row of batch.instances) {
                const clone = cc.instantiate(template);
                clone.active = false; assertStaticOnly(clone); clone.parent = parent;
                clone.setSiblingIndex(row.siblingIndex);
                added.push(clone); roots.push(clone);
            }
        } else for (let i = 1; i < batch.instances.length; i++) {
            const clone = cc.instantiate(template);
            clone.active = false;
            assertStaticOnly(clone);
            clone.parent = parent;
            added.push(clone);
            roots.push(clone);
        }
        for (let i = 0; i < roots.length; i++) {
            const row = batch.instances[i], root = roots[i];
            root.setSiblingIndex(row.siblingIndex);
            const nodeMap = mapCloneTree(validated.tree, validated.rootId, root);
            const resolver = resolverFactory(nodeMap);
            if (typeof resolver !== 'function') throw Error('PREVIEW_CLONE_RESOLVER_INVALID');
            const result = states.Apply(row.previewState, resolver);
            if (!result.verified) throw Error('PREVIEW_CLONE_STATE_APPLY_FAILED: ' + row.instanceId);
            const colors = applyExtraOperations(row, resolver);
            if (colors.some(x => !x.verified)) throw Error('PREVIEW_CLONE_COLOR_READBACK_FAILED: ' + row.instanceId);
        }
        roots.forEach(root => { root.active = true; });
        if (!validated.manual) settleLayout(parent);
        const layoutResult = layoutReadback(batch, parent, roots, validated.tree);
        const instanceReadbacks = roots.map((root, i) => {
            const row = batch.instances[i], nodeMap = mapCloneTree(validated.tree, validated.rootId, root);
            const resolver = resolverFactory(nodeMap);
            const state = states.Read(row.previewState, resolver);
            const colors = colorReadback(row, resolver);
            return {instanceId: row.instanceId, state, colors,
                verified: state.verified && colors.every(x => x.verified)};
        });
        return {schema: 'monkey-prefab-preview-clone-readback/1', sourcePrefabId: batch.sourcePrefabId,
            cloneSpecSha256: batch.cloneSpecSha256, sourcePlanSha256: batch.sourcePlanSha256,
            cloneCount: roots.length, applied: true, verified: instanceReadbacks.every(x => x.verified) && layoutResult.verified,
            businessBehaviorComplete: false, layout: layoutResult, instances: instanceReadbacks, gaps: layoutResult.verified ? [] : ['native_layout_readback_mismatch']};
    } catch (error) {
        for (const clone of added) if (clone && clone.isValid) clone.destroy();
        if (template && template.isValid) {
            template.active = oldActive;
            if (validated.external && !append && template.parent === parent) template.parent = null;
            else if (!validated.external && template.parent !== parent) template.parent = parent;
        }
        if (placeholder && placeholder.isValid) { placeholder.parent = parent; placeholder.active = oldPlaceholderActive; }
        if (layout && oldLayoutEnabled !== null && oldLayoutEnabled !== undefined) layout.enabled = oldLayoutEnabled;
        if (!validated.manual) settleLayout(parent);
        throw error;
    }
}

function Read(batch, sourceNodes, resolverFactory, settleLayout) {
    const validated = validate(batch, sourceNodes);
    if (typeof resolverFactory !== 'function' || (!validated.manual && typeof settleLayout !== 'function'))
        throw Error('PREVIEW_CLONE_CALLBACK_REQUIRED');
    const parent = sourceNodes.get(validated.parentId), layout = parent.getComponent(cc.Layout);
    if (!validated.manual && (!layout || !layout.enabled)) throw Error('PREVIEW_CLONE_NATIVE_LAYOUT_MISSING');
    const append = validated.append;
    const expected = batch.instances.length;
    const expectedChildren = append ? validated.initialChildIds.length + expected : expected + (validated.manual ? 1 : 0);
    if (parent.children.length !== expectedChildren) throw Error('PREVIEW_CLONE_SAVED_CHILD_COUNT_MISMATCH');
    let roots;
    if (append) {
        if (!validated.initialChildIds.every((id, index) => parent.children[index] === sourceNodes.get(id)))
            throw Error('PREVIEW_CLONE_SAVED_SOURCE_CHILD_PREFIX_MISMATCH');
        roots = parent.children.slice(validated.appendStart);
    } else if (validated.manual) {
        if (parent.children[0] !== sourceNodes.get(validated.rootId) || parent.children[0].active !== false)
            throw Error('PREVIEW_CLONE_SOURCE_MANUAL_TEMPLATE_STATE_MISMATCH');
        roots = parent.children.slice(1);
    } else roots = parent.children.slice();
    if (append && validated.manual) {
        const layout = parent.getComponent(cc.Layout);
        if (layout && layout.enabled) throw Error('PREVIEW_CLONE_SOURCE_MANUAL_LAYOUT_MUST_BE_DISABLED');
    }
    if (!validated.manual) settleLayout(parent);
    const layoutResult = layoutReadback(batch, parent, roots, validated.tree);
    const instances = roots.map((root, i) => {
        const row = batch.instances[i], nodes = mapCloneTree(validated.tree, validated.rootId, root);
        const resolver = resolverFactory(nodes), state = states.Read(row.previewState, resolver), colors = colorReadback(row, resolver);
        return {instanceId: row.instanceId, state, colors, verified: state.verified && colors.every(x => x.verified)};
    });
    return {schema: 'monkey-prefab-preview-clone-readback/1', sourcePrefabId: batch.sourcePrefabId,
        cloneSpecSha256: batch.cloneSpecSha256, sourcePlanSha256: batch.sourcePlanSha256,
        cloneCount: instances.length, applied: false, verified: instances.every(x => x.verified) && layoutResult.verified,
        businessBehaviorComplete: false, layout: layoutResult, instances, gaps: layoutResult.verified ? [] : ['native_layout_readback_mismatch']};
}

module.exports = {Apply, Read, validate};
