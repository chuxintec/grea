const cc=require('cc');
/** Static import adapter only. Source event arrays are retained in the spec and never invoked. */
class CreatorStaticToggle {
    static Apply(spec, resolveNode, resolveComponent) {
        const gaps = [];
        if (!spec || !Array.isArray(spec.bindings)) return ['missing_toggle_spec'];
        const groupRows = new Map(), groupRowsByNode = new Map(), invalidGroupIds = new Set(), invalidGroupNodes = new Set();
        for (const row of spec.bindings) {
            if (!row || row.kind !== 'cc.ToggleContainer') continue;
            if (typeof row.sourceId !== 'string' || typeof row.nodeSourceId !== 'string') {
                gaps.push(`${row && row.sourceId || 'toggle_group'}:toggle_group_source_invalid`); continue;
            }
            if (groupRows.has(row.sourceId)) {
                invalidGroupIds.add(row.sourceId); gaps.push(`${row.sourceId}:toggle_group_source_duplicate`); continue;
            }
            if (groupRowsByNode.has(row.nodeSourceId)) {
                invalidGroupNodes.add(row.nodeSourceId);
                invalidGroupIds.add(row.sourceId);
                invalidGroupIds.add(groupRowsByNode.get(row.nodeSourceId).sourceId);
                gaps.push(`${row.sourceId}:multiple_toggle_groups_on_node`); continue;
            }
            groupRows.set(row.sourceId, row); groupRowsByNode.set(row.nodeSourceId, row);
        }

        // Create every source-backed container before resolving child Toggles.
        // Binding list order follows source component order and is not a contract.
        const groupComponents = new Map();
        for (const row of spec.bindings) {
            if (!row || row.kind !== 'cc.ToggleContainer' || invalidGroupIds.has(row.sourceId) || invalidGroupNodes.has(row.nodeSourceId)) continue;
            try {
                const node = resolveNode && resolveNode(row.nodeSourceId);
                if (!(node instanceof cc.Node)) { gaps.push(`${row.sourceId}:node_unresolved`); continue; }
                let group = node.getComponent(cc.ToggleContainer);
                if (!group) group = node.addComponent(cc.ToggleContainer);
                group.enabled = false;
                if (row.allowSwitchOffPresent || row.allowSwitchOffSourceDefaultVerified) group.allowSwitchOff = !!row.allowSwitchOffValue;
                groupComponents.set(row.sourceId, group);
            } catch (error) { gaps.push(`${row.sourceId}:apply_failed:${error && error.name || 'Error'}`); }
        }

        for (const row of spec.bindings) {
            if (!row || row.kind !== 'cc.Toggle') continue;
            try {
                const node = resolveNode && resolveNode(row.nodeSourceId);
                if (!(node instanceof cc.Node)) { gaps.push(`${row.sourceId}:node_unresolved`); continue; }
                let toggle = node.getComponent(cc.Toggle);
                if (!toggle) toggle = node.addComponent(cc.Toggle);
                toggle.enabled = false;
                if (row.checkedPresent || row.checkedSourceDefaultVerified) {
                    // Creator 3.8.8 public API updates the actual serialized _isChecked field without events.
                    toggle.setIsCheckedWithoutNotify(!!row.checkedValue);
                    if (toggle.checkMark && toggle.checkMark.node) toggle.checkMark.node.active = !!row.checkedValue;
                }
                if (row.interactablePresent || row.interactableSourceDefaultVerified) toggle.interactable = !!row.interactableValue;
                if (row.checkMarkPresent || row.checkMarkSourceDefaultVerified) {
                    if (!row.checkMarkSourceId) toggle.checkMark = null;
                    else { const mark = resolveComponent && resolveComponent(row.checkMarkSourceId);
                        if (mark instanceof cc.Sprite) toggle.checkMark = mark;
                        else gaps.push(`${row.sourceId}:checkmark_unresolved`); }
                }
                if ((row.checkedPresent || row.checkedSourceDefaultVerified) && toggle.checkMark && toggle.checkMark.node)
                    toggle.checkMark.node.active = !!row.checkedValue;
                if (row.targetPresent || row.targetSourceDefaultVerified) {
                    if (!row.targetSourceId) toggle.target = null;
                    else { const target = resolveNode && resolveNode(row.targetSourceId);
                        if (target instanceof cc.Node) toggle.target = target;
                        else gaps.push(`${row.sourceId}:target_unresolved`); }
                }
                if (row.normalColorValue && (row.normalColorPresent || row.normalColorSourceDefaultVerified)) {
                    const c = row.normalColorValue;
                    toggle.normalColor = new cc.Color(c.r, c.g, c.b, c.a);
                }
                if (row.zoomScalePresent || row.zoomScaleSourceDefaultVerified) toggle.zoomScale = row.zoomScaleValue;
                if (row.transitionPresent || row.transitionSourceDefaultVerified) toggle.transition = row.transitionValue;
                if (row.groupSourceId) {
                    const groupRow = groupRows.get(row.groupSourceId);
                    const groupNode = resolveNode && resolveNode(row.groupNodeSourceId);
                    const group = groupComponents.get(row.groupSourceId);
                    if (invalidGroupIds.has(row.groupSourceId) || !groupRow || groupRow.nodeSourceId !== row.groupNodeSourceId)
                        gaps.push(`${row.sourceId}:toggle_group_source_mismatch`);
                    // Creator 3.8.8 resolves Toggle's native ToggleContainer
                    // from its direct parent; confirm the source row maps to it.
                    else if (!(groupNode instanceof cc.Node) || node.parent !== groupNode || !group || groupNode.getComponent(cc.ToggleContainer) !== group)
                        gaps.push(`${row.sourceId}:toggle_group_unresolved`);
                } else if (node.parent instanceof cc.Node && node.parent.getComponent(cc.ToggleContainer)) {
                    gaps.push(`${row.sourceId}:unexpected_toggle_group`);
                }
            } catch (error) { gaps.push(`${row.sourceId}:apply_failed:${error && error.name || 'Error'}`); }
        }
        return gaps;
    }

    static Create(spec, resolveNode, resolveComponent) { return this.Apply(spec, resolveNode, resolveComponent); }

    static Read(spec, resolveNode, resolveComponent) {
        const fields = [];
        if (!spec || !Array.isArray(spec.bindings)) return { dynamicBehaviorComplete: false, fields };
        const groupRows = new Map(), groupRowsByNode = new Map(), invalidGroupIds = new Set(), invalidGroupNodes = new Set();
        for (const row of spec.bindings) {
            if (!row || row.kind !== 'cc.ToggleContainer') continue;
            if (groupRows.has(row.sourceId) || groupRowsByNode.has(row.nodeSourceId)) {
                invalidGroupIds.add(row.sourceId); invalidGroupNodes.add(row.nodeSourceId);
                if (groupRowsByNode.has(row.nodeSourceId)) invalidGroupIds.add(groupRowsByNode.get(row.nodeSourceId).sourceId);
            } else { groupRows.set(row.sourceId, row); groupRowsByNode.set(row.nodeSourceId, row); }
        }
        for (const row of spec.bindings) {
            const result = { sourceId: row.sourceId, kind: row.kind, verified: false, gaps: [...(row.gaps || [])] };
            try {
                const node = resolveNode && resolveNode(row.nodeSourceId);
                if (!(node instanceof cc.Node)) result.gaps.push('node_unresolved');
                else if (row.kind === 'cc.Toggle') {
                    const toggle = node.getComponent(cc.Toggle);
                    if (!toggle || toggle.enabled) result.gaps.push('toggle_missing_or_enabled');
                    else {
                        result.checkedValue = toggle.isChecked;
                        result.interactableValue = toggle.interactable;
                        result.zoomScaleValue = toggle.zoomScale;
                        result.checkMarkSourceId = row.checkMarkPresent ? row.checkMarkSourceId : null;
                        result.targetSourceId = row.targetPresent ? row.targetSourceId : null;
                        result.groupSourceId = row.groupSourceId || null;
                        result.groupNodeSourceId = row.groupNodeSourceId || null;
                        let ok = (!(row.checkedPresent || row.checkedSourceDefaultVerified) || toggle.isChecked === row.checkedValue)
                            && (!(row.interactablePresent || row.interactableSourceDefaultVerified) || toggle.interactable === row.interactableValue);
                        if (row.checkMarkPresent || row.checkMarkSourceDefaultVerified)
                            ok = ok && (row.checkMarkSourceId ? toggle.checkMark === (resolveComponent && resolveComponent(row.checkMarkSourceId)) : toggle.checkMark === null);
                        if (row.targetPresent || row.targetSourceDefaultVerified)
                            ok = ok && (row.targetSourceId ? toggle.target === (resolveNode && resolveNode(row.targetSourceId)) : toggle.target === null);
                        if (row.normalColorValue && (row.normalColorPresent || row.normalColorSourceDefaultVerified)) {
                            const c = toggle.normalColor, e = row.normalColorValue;
                            ok = ok && c.r === e.r && c.g === e.g && c.b === e.b && c.a === e.a;
                        }
                        if (row.zoomScalePresent || row.zoomScaleSourceDefaultVerified)
                            ok = ok && toggle.zoomScale === row.zoomScaleValue;
                        result.transitionValue = toggle.transition;
                        if (row.transitionPresent || row.transitionSourceDefaultVerified) ok = ok && toggle.transition === row.transitionValue;
                        result.normalColorValue = toggle.normalColor ? { r: toggle.normalColor.r, g: toggle.normalColor.g,
                            b: toggle.normalColor.b, a: toggle.normalColor.a } : null;
                        if (row.groupSourceId) {
                            const groupRow = groupRows.get(row.groupSourceId);
                            const groupNode = resolveNode && resolveNode(row.groupNodeSourceId);
                            const group = groupNode instanceof cc.Node ? groupNode.getComponent(cc.ToggleContainer) : null;
                            const attachedGroup = node.parent instanceof cc.Node ? node.parent.getComponent(cc.ToggleContainer) : null;
                            const groupMatches = !invalidGroupIds.has(row.groupSourceId) && groupRow
                                && groupRow.nodeSourceId === row.groupNodeSourceId && groupNode instanceof cc.Node
                                && node.parent === groupNode && group && attachedGroup === group;
                            ok = ok && !!groupMatches;
                            if (!groupMatches) result.gaps.push('toggle_group_mismatch');
                        } else if (node.parent instanceof cc.Node && node.parent.getComponent(cc.ToggleContainer)) {
                            ok = false; result.gaps.push('unexpected_toggle_group');
                        }
                        result.verified = !!ok;
                        if (!ok) result.gaps.push('toggle_fields_mismatch');
                    }
                } else {
                    const group = node.getComponent(cc.ToggleContainer);
                    result.allowSwitchOffValue = !!(group && group.allowSwitchOff);
                    result.verified = !invalidGroupIds.has(row.sourceId) && !invalidGroupNodes.has(row.nodeSourceId)
                        && groupRows.get(row.sourceId) === row && !!group && !group.enabled
                        && (!(row.allowSwitchOffPresent || row.allowSwitchOffSourceDefaultVerified) || group.allowSwitchOff === row.allowSwitchOffValue);
                    if (!result.verified) result.gaps.push('toggle_container_mismatch');
                }
            } catch (error) { result.gaps.push(`read_failed:${error && error.name || 'Error'}`); }
            fields.push(result);
        }
        return { dynamicBehaviorComplete: false, fields };
    }
}

module.exports = CreatorStaticToggle;
