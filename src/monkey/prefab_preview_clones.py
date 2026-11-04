"""Prepare source-backed, repeatable static template clones for preview.

This module only lowers declarative clone and field-state contracts. It never
executes source scripts or chooses layout coordinates; the target's native
Layout component places the cloned children and reports the resulting geometry.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from pathlib import Path

from . import io
from .prefab_preview_state import PreviewStateError, prepare as prepare_preview_state


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_INSTANCES = 10000
_MAX_TEMPLATE_NODES = 50000
_STATE_KINDS = {"node.active", "node.scale", "label.text", "sprite.asset",
                "node.opacity", "label.fontSize", "label.lineHeight", "progress.value"}


class PreviewCloneError(ValueError):
    """Invalid clone spec, source plan, or source-backed operation."""


def _need(value, label):
    if not isinstance(value, str) or not value.strip():
        raise PreviewCloneError(f"{label} must be a non-empty string")
    return value


def _digest(value, label):
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise PreviewCloneError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _object(value, label):
    if not isinstance(value, Mapping):
        raise PreviewCloneError(f"{label} must be an object")
    return value


def _read_bounded(path, limit=128 * 1024 * 1024):
    path = io.safe(path)
    try:
        return io.read(path, max_bytes=limit)
    except Exception as error:
        raise PreviewCloneError(f"input unreadable or over budget: {path}") from error


def _json_value_equal(left, right):
    if type(left) is not type(right):
        if type(left) in (int, float) and type(right) in (int, float):
            return math.isfinite(left) and math.isfinite(right) and left == right
        return False
    if isinstance(left, float):
        return math.isfinite(left) and math.isfinite(right) and left == right
    if isinstance(left, list):
        return len(left) == len(right) and all(_json_value_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_json_value_equal(left[k], right[k]) for k in left)
    return left == right


def _value(plan, operation, node_by_id, component_by_id, asset_ids, template_node_ids, template_component_ids):
    kind = operation.get("kind")
    source_id = _need(operation.get("sourceId"), f"{kind}.sourceId")
    if kind not in _STATE_KINDS:
        raise PreviewCloneError(f"unsupported state operation kind: {kind!r}")
    if source_id not in template_node_ids and source_id not in template_component_ids:
        raise PreviewCloneError(f"operation target outside source template: {source_id}")
    if "expectedValue" not in operation or "value" not in operation:
        raise PreviewCloneError(f"operation {kind} must include expectedValue and value")
    expected, value = operation["expectedValue"], operation["value"]
    if kind == "node.active":
        source = node_by_id.get(source_id, {}).get("active")
        if type(expected) is not bool or type(value) is not bool or type(source) is not bool:
            raise PreviewCloneError("node.active values must be bool")
    elif kind == "node.scale":
        source = node_by_id.get(source_id, {}).get("scale")
        for label, candidate in (("source", source), ("expectedValue", expected), ("value", value)):
            if (not isinstance(candidate, list) or len(candidate) != 3 or
                    any(type(n) not in (int, float) or not math.isfinite(n) for n in candidate)):
                raise PreviewCloneError(f"node.scale {label} must be a finite three-number vector")
    elif kind == "node.opacity":
        source = node_by_id.get(source_id, {}).get("opacity")
        if any(type(n) not in (int, float) or not math.isfinite(n) or n < 0 or n > 255
               for n in (source, expected, value)):
            raise PreviewCloneError("node.opacity must be finite in [0,255]")
    elif kind in ("label.text", "label.fontSize", "label.lineHeight"):
        component = component_by_id.get(source_id)
        if not component or component.get("type") not in ("cc.Label", "cc.RichText"):
            raise PreviewCloneError(f"{kind} target must be a source text component")
        field = "text" if kind == "label.text" else kind.split(".", 1)[1]
        source = component.get(field)
        if kind == "label.text":
            if not all(isinstance(x, str) for x in (source, expected, value)):
                raise PreviewCloneError("label.text source, expectedValue and value must be strings")
        elif any(type(x) not in (int, float) or not math.isfinite(x) or x < 0
                 for x in (source, expected, value)):
            raise PreviewCloneError(f"{kind} values must be finite non-negative numbers")
    elif kind == "progress.value":
        component = component_by_id.get(source_id)
        if not component or component.get("type") != "cc.ProgressBar":
            raise PreviewCloneError("progress.value target must be a source cc.ProgressBar")
        source = component.get("progress")
        if any(type(n) not in (int, float) or not math.isfinite(n) or n < 0 or n > 1
               for n in (source, expected, value)):
            raise PreviewCloneError("progress.value must be finite in [0,1]")
    else:  # sprite.asset
        component = component_by_id.get(source_id)
        if not component or component.get("type") != "cc.Sprite":
            raise PreviewCloneError("sprite.asset target must be a source cc.Sprite")
        source = component.get("spriteFrame")
        if expected is not None and (not isinstance(expected, str) or expected not in asset_ids):
            raise PreviewCloneError("sprite.asset expectedValue is absent from source plan assets")
        if value is not None and (not isinstance(value, str) or value not in asset_ids):
            raise PreviewCloneError("sprite.asset value is absent from source plan assets")
    if not _json_value_equal(expected, source):
        raise PreviewCloneError(f"{kind} expectedValue differs from source plan: {source_id}")
    return {"kind": kind, "sourceId": source_id, "expectedValue": expected, "value": value}


def _tree(plan, root_id, parent_id, source_root_parent_id, initial_child_ids):
    nodes = plan.get("nodes")
    components = plan.get("components")
    if not isinstance(nodes, list) or not isinstance(components, list):
        raise PreviewCloneError("plan must contain nodes and components arrays")
    node_by_id = {}
    for row in nodes:
        if not isinstance(row, Mapping) or not isinstance(row.get("sourceId"), str):
            raise PreviewCloneError("source plan contains a node without sourceId")
        if row["sourceId"] in node_by_id:
            raise PreviewCloneError("duplicate source node identity")
        node_by_id[row["sourceId"]] = row
    component_by_id = {}
    for row in components:
        if not isinstance(row, Mapping) or not isinstance(row.get("sourceId"), str):
            raise PreviewCloneError("source plan contains a component without sourceId")
        if row["sourceId"] in component_by_id:
            raise PreviewCloneError("duplicate source component identity")
        component_by_id[row["sourceId"]] = row
    if root_id not in node_by_id or parent_id not in node_by_id:
        raise PreviewCloneError("template root or parent node absent from plan")
    if source_root_parent_id is not None and source_root_parent_id not in node_by_id:
        raise PreviewCloneError("template source root parent absent from source plan")
    if node_by_id[root_id].get("parent") != source_root_parent_id:
        raise PreviewCloneError("template root source parent differs from clone contract")
    parent_children = node_by_id[parent_id].get("children")
    if (not isinstance(initial_child_ids, list) or any(not isinstance(x, str) for x in initial_child_ids) or
            not isinstance(parent_children, list) or parent_children != initial_child_ids or
            len(set(initial_child_ids)) != len(initial_child_ids) or
            any(x not in node_by_id or node_by_id[x].get("parent") != parent_id for x in initial_child_ids)):
        raise PreviewCloneError("declared initial source children differ from exact parent hierarchy/order")

    pending = [root_id]
    seen = set()
    while pending:
        source_id = pending.pop()
        if source_id in seen:
            raise PreviewCloneError("source template hierarchy contains a cycle or duplicate child")
        seen.add(source_id)
        if len(seen) > _MAX_TEMPLATE_NODES:
            raise PreviewCloneError("source template node budget exceeded")
        node = node_by_id.get(source_id)
        if not node:
            raise PreviewCloneError(f"template child absent from plan: {source_id}")
        children = node.get("children", [])
        if not isinstance(children, list) or any(not isinstance(x, str) for x in children):
            raise PreviewCloneError(f"malformed template children: {source_id}")
        pending.extend(reversed(children))
    template_components = {cid for sid in seen for cid in node_by_id[sid].get("components", [])}
    if any(cid not in component_by_id for cid in template_components):
        raise PreviewCloneError("template component identity missing from plan")
    asset_ids = set()
    for collection, keys in ((plan.get("assets", []), ("sourceId", "id")),
                             (plan.get("spriteFrames", []), ("sourceId", "id")),
                             (plan.get("textures", []), ("id",))):
        if not isinstance(collection, list):
            continue
        for row in collection:
            if isinstance(row, Mapping):
                asset_ids.update(row[k] for k in keys if isinstance(row.get(k), str) and row[k])
    return node_by_id, component_by_id, seen, template_components, asset_ids


def _validate_color(operation, component_by_id, node_by_id, template_node_ids, template_component_ids):
    if not isinstance(operation, Mapping) or operation.get("kind") != "sprite.color":
        raise PreviewCloneError("clone extras only support sprite.color")
    source_id = _need(operation.get("sourceId"), "sprite.color.sourceId")
    if source_id in template_component_ids:
        component = component_by_id[source_id]
        if component.get("type") != "cc.Sprite":
            raise PreviewCloneError("sprite.color component target must be a source cc.Sprite")
        target_node_id = component.get("node")
        target_kind = "component"
    elif source_id in template_node_ids:
        target_node_id = source_id
        node_components = node_by_id[source_id].get("components", [])
        sprites = [component_by_id[cid] for cid in node_components if cid in component_by_id and component_by_id[cid].get("type") == "cc.Sprite"]
        if len(sprites) != 1:
            raise PreviewCloneError("node sprite.color target must have exactly one source cc.Sprite")
        component = sprites[0]
        target_kind = "node"
    else:
        raise PreviewCloneError("sprite.color target outside source template")
    node = node_by_id[target_node_id]
    expected = operation.get("expectedValue")
    value = operation.get("value")
    source = node.get("color")
    for label, candidate in (("source", source), ("expectedValue", expected), ("value", value)):
        if (not isinstance(candidate, list) or len(candidate) != 4 or
                any(type(x) is not int or x < 0 or x > 255 for x in candidate)):
            raise PreviewCloneError(f"sprite.color {label} must be four byte channels")
    if expected != source:
        raise PreviewCloneError(f"sprite.color expectedValue differs from source node: {component['node']}")
    return {"kind": "sprite.color", "sourceId": source_id, "targetKind": target_kind,
            "targetNodeSourceId": target_node_id, "targetComponentSourceId": component["sourceId"],
            "expectedValue": expected, "value": value}


def _verify_evidence_files(spec_path, workspace_root, rows):
    if not isinstance(rows, list) or not rows:
        raise PreviewCloneError("sourceEvidenceFiles must be a non-empty array")
    workspace_root = io.safe(workspace_root)
    result = []
    seen = set()
    for row in rows:
        _object(row, "sourceEvidenceFiles row")
        relative = _need(row.get("path"), "sourceEvidenceFiles.path")
        digest = _digest(row.get("sha256"), f"sourceEvidenceFiles[{relative}].sha256")
        if relative in seen:
            raise PreviewCloneError(f"duplicate source evidence path: {relative}")
        seen.add(relative)
        try:
            source_path = io.inside(workspace_root, relative)
            raw = _read_bounded(source_path)
        except Exception as error:
            raise PreviewCloneError(f"source evidence path unavailable: {relative}") from error
        if io.sha(raw) != digest:
            raise PreviewCloneError(f"source evidence hash mismatch: {relative}")
        result.append({"path": relative, "sha256": digest, "bytes": len(raw)})
    return result


def _verify_manual_layout(spec, workspace_root, instance_count):
    layout = _object(spec.get("template", {}).get("sourceManualLayout"), "template.sourceManualLayout")
    formula_id = layout.get("formulaId")
    if formula_id not in ("centered-horizontal-linear/1", "progress-threshold-centers/1", "pass-task-linear-y/1"):
        raise PreviewCloneError("unsupported source-manual placement formula")
    evidence_id = _need(layout.get("sourceEvidenceId"), "sourceManualLayout.sourceEvidenceId")
    path = _need(layout.get("sourceCodePath"), "sourceManualLayout.sourceCodePath")
    digest = _digest(layout.get("sourceCodeSha256"), "sourceManualLayout.sourceCodeSha256")
    span = _object(layout.get("sourceBytes"), "sourceManualLayout.sourceBytes")
    start, end = span.get("start"), span.get("end")
    if type(start) is not int or type(end) is not int or start < 0 or end <= start:
        raise PreviewCloneError("sourceManualLayout sourceBytes must be a non-empty byte range")
    span_digest = _digest(layout.get("sourceSpanSha256"), "sourceManualLayout.sourceSpanSha256")
    files = spec.get("sourceEvidenceFiles")
    if not any(isinstance(row, Mapping) and row.get("path") == path and row.get("sha256") == digest for row in files or []):
        raise PreviewCloneError("source-manual code must be among hash-pinned sourceEvidenceFiles")
    try:
        raw = _read_bounded(io.inside(io.safe(workspace_root), path))
    except Exception as error:
        raise PreviewCloneError("source-manual source code unavailable") from error
    if io.sha(raw) != digest or end > len(raw) or io.sha(raw[start:end]) != span_digest:
        raise PreviewCloneError("source-manual source code or span hash mismatch")
    count, source_y = layout.get("count"), layout.get("sourceTemplateY")
    if type(count) is not int or count != instance_count or type(source_y) not in (int, float) or type(source_y) is bool or not math.isfinite(source_y):
        raise PreviewCloneError("source-manual formula parameters are invalid or disagree with clone count")
    normalized = {"formulaId": formula_id, "sourceEvidenceId": evidence_id,
            "sourceCodePath": path, "sourceCodeSha256": digest,
            "sourceBytes": {"start": start, "end": end}, "sourceSpanSha256": span_digest,
            "count": count, "sourceTemplateY": source_y}
    if formula_id == "centered-horizontal-linear/1":
        width, gap = layout.get("templateWidth"), layout.get("gap")
        if (type(width) not in (int, float) or type(gap) not in (int, float) or
                type(width) is bool or type(gap) is bool or not math.isfinite(width) or not math.isfinite(gap) or
                width <= gap or gap < 0):
            raise PreviewCloneError("centered source-manual width/gap parameters are invalid")
        normalized.update(templateWidth=width, gap=gap)
    elif formula_id == "progress-threshold-centers/1":
        total_length, thresholds = layout.get("progressBarTotalLength"), layout.get("totalThresholdCount")
        if (type(total_length) not in (int, float) or type(total_length) is bool or not math.isfinite(total_length) or
                total_length <= 0 or type(thresholds) is not int or thresholds <= count):
            raise PreviewCloneError("progress threshold source-manual parameters are invalid")
        normalized.update(progressBarTotalLength=total_length, totalThresholdCount=thresholds)
    else:
        item_height, spacing_y = layout.get("passItemHeight"), layout.get("spacingY")
        if (type(item_height) not in (int, float) or type(item_height) is bool or not math.isfinite(item_height) or item_height <= 0 or
                type(spacing_y) not in (int, float) or type(spacing_y) is bool or not math.isfinite(spacing_y) or spacing_y < 0):
            raise PreviewCloneError("source progression list source-manual height/spacing parameters are invalid")
        first_y = -item_height / 2
        if not math.isclose(source_y, first_y, rel_tol=0, abs_tol=1e-6):
            raise PreviewCloneError("source progression list source-manual first Y differs from half-height source formula")
        normalized.update(passItemHeight=item_height, spacingY=spacing_y)
    return normalized


def _manual_expected_position(layout, index):
    if layout["formulaId"] == "centered-horizontal-linear/1":
        item_width = layout["templateWidth"] - layout["gap"]
        first_x = -(layout["count"] * item_width) / 2 + item_width / 2
        x = first_x + index * item_width
    elif layout["formulaId"] == "progress-threshold-centers/1":
        step = layout["progressBarTotalLength"] / layout["totalThresholdCount"]
        start = -layout["progressBarTotalLength"] / 2
        x = start + (index + 1) * step
        return [x, layout["sourceTemplateY"], 0]
    else:
        y = -layout["passItemHeight"] / 2 - index * (layout["passItemHeight"] + layout["spacingY"])
        return [0, y, 0]
    return [x, layout["sourceTemplateY"], 0]


def _source_grid_append_rule(layout, parent_node, template_node, initial_child_ids, node_by_id, count):
    """Build a plan-pinned Cocos 2.4 horizontal Grid auto-wrap rule."""
    if (layout.get("type") != "cc.Layout" or layout.get("enabled") is not True or
            layout.get("layoutType") != 3 or layout.get("resize") != 1 or
            layout.get("startAxis") != 0 or layout.get("horizontalDirection") != 0 or
            layout.get("verticalDirection") != 1):
        raise PreviewCloneError("append native Layout currently requires source-evidenced top-left horizontal Grid with container resize")
    constraint = layout.get("constraint", 0)
    constraint_count = layout.get("constraintCount", 0)
    cell = layout.get("cellSize")
    spacing = layout.get("spacingXY")
    padding = layout.get("padding")
    parent_size = parent_node.get("size")
    template_size = template_node.get("size")
    if (constraint != 0 or type(constraint_count) is not int or constraint_count < 0 or
            not isinstance(cell, list) or len(cell) != 2 or any(type(x) not in (int, float) or type(x) is bool or x <= 0 for x in cell) or
            not isinstance(spacing, list) or len(spacing) != 2 or any(type(x) not in (int, float) or type(x) is bool or x < 0 for x in spacing) or
            not isinstance(padding, list) or len(padding) != 4 or any(type(x) not in (int, float) or type(x) is bool or x < 0 for x in padding) or
            not isinstance(parent_size, list) or len(parent_size) != 2 or
            not isinstance(template_size, list) or len(template_size) < 2):
        raise PreviewCloneError("append grid source Layout dimensions are incomplete")
    if any(not math.isclose(float(template_size[i]), float(cell[i]), rel_tol=0, abs_tol=1e-6) for i in range(2)):
        raise PreviewCloneError("detached source template size differs from pinned Grid cellSize")
    # Source normalization pins Cocos padding in [left, bottom, right, top] order.
    left, bottom, right, top = [float(x) for x in padding]
    cell_w, cell_h = [float(x) for x in cell]
    gap_x, gap_y = [float(x) for x in spacing]
    if parent_node.get("active") is not True or any(node_by_id[x].get("active") is not False for x in initial_child_ids):
        raise PreviewCloneError("append grid rule currently requires an active parent and only inactive retained owner children")
    available_width = float(parent_size[0]) - left - right
    pitch = cell_w + gap_x
    if available_width + gap_x < pitch:
        raise PreviewCloneError("source parent width cannot fit one source Grid cell")
    # Creator 2.4's horizontal GRID rowBreak uses the active child widths,
    # right padding and container width; equal-sized cells reduce to this floor.
    columns = max(1, math.floor((available_width + gap_x + 1e-9) / pitch))
    rows = (count + columns - 1) // columns
    expected_parent_height = top + bottom + rows * cell_h + max(0, rows - 1) * gap_y
    return {"formulaId": "cocos-grid-auto-columns-top-left/1",
            "sourceLayoutType": 3, "sourceResizeMode": 1, "sourceStartAxis": 0,
            "sourceHorizontalDirection": 0, "sourceVerticalDirection": 1,
            "sourceConstraint": constraint, "sourceConstraintCount": constraint_count,
            "inactiveOwnerChildSourceIds": list(initial_child_ids),
            "columns": columns, "rows": rows, "cellSize": [cell_w, cell_h],
            "spacing": [gap_x, gap_y], "padding": [left, bottom, right, top],
            "sourceParentSize": [float(parent_size[0]), float(parent_size[1])],
            "expectedParentSize": [float(parent_size[0]), expected_parent_height],
            "count": count}


def _grid_expected_position(rule, parent_size, index):
    columns = rule["columns"]
    row, column = divmod(index, columns)
    width, height = float(parent_size[0]), float(parent_size[1])
    left, _bottom, _right, top = rule["padding"]
    cell_w, cell_h = rule["cellSize"]
    gap_x, gap_y = rule["spacing"]
    x = -width / 2 + left + cell_w / 2 + column * (cell_w + gap_x)
    y = height / 2 - top - cell_h / 2 - row * (cell_h + gap_y)
    return [x, y, 0]


def prepare_clones(clone_spec_path, expected_sha256, plan_path,
                   expected_plan_sha256, workspace_root, output):
    """Validate a source-backed clone specification and prepare per-clone state specs.

    ``plan_path`` must be a manifest-owned plan document. The caller remains
    responsible for wiring the resulting clone batch into a native isolated
    preview and for reporting native Layout readback separately.
    """
    clone_spec_path = io.safe(clone_spec_path)
    clone_raw = _read_bounded(clone_spec_path)
    _digest(expected_sha256, "expected_sha256")
    if io.sha(clone_raw) != expected_sha256:
        raise PreviewCloneError("clone spec hash differs from expected_sha256")
    spec = io.load(clone_raw, max_nodes=500_000, max_depth=64)
    _object(spec, "clone spec")
    if spec.get("schema") != "monkey-prefab-preview-clones/1":
        raise PreviewCloneError("unsupported clone spec schema")

    plan_path = io.safe(plan_path)
    _digest(expected_plan_sha256, "expected_plan_sha256")
    try:
        plan_raw = io.stage_bytes(plan_path)
        plan = io.stage_document(plan_path)
    except Exception as error:
        raise PreviewCloneError("plan is not an intact manifest-owned stage document") from error
    if io.sha(plan_raw) != expected_plan_sha256:
        raise PreviewCloneError("source plan hash differs from expected_plan_sha256")
    source_id = _need(spec.get("sourcePrefabId"), "sourcePrefabId")
    template_source_id = _need(spec.get("templatePrefabId", source_id), "templatePrefabId")
    manifest_sha = _digest(spec.get("sourceManifestSha256"), "sourceManifestSha256")
    plan_manifest_sha = plan.get("sourceManifestSha256") or (plan.get("previewState") or {}).get("sourceManifestSha256")
    if plan_manifest_sha != manifest_sha:
        raise PreviewCloneError("source plan manifest differs from clone spec")
    source_prefabs = plan.get("sourcePrefabs")
    if not isinstance(source_prefabs, list) or any(not any(
            isinstance(row, Mapping) and row.get("sourceId") == required for row in source_prefabs)
            for required in {source_id, template_source_id}):
        raise PreviewCloneError("container or template prefab identity is absent from source plan")

    template = _object(spec.get("template"), "template")
    root_id = _need(template.get("rootSourceId"), "template.rootSourceId")
    parent_id = _need(template.get("parentSourceId"), "template.parentSourceId")
    layout_mode = template.get("layoutMode")
    if layout_mode not in ("native-layout", "source-manual"):
        raise PreviewCloneError("clone spec must use native-layout or evidenced source-manual")
    layout_id = (_need(template.get("layoutComponentSourceId"), "template.layoutComponentSourceId")
                 if layout_mode == "native-layout" else template.get("layoutComponentSourceId"))
    external_template = template_source_id != source_id
    source_root_parent_id = template.get("sourceRootParentSourceId", parent_id)
    placeholder_id = template.get("replacePlaceholderSourceId")
    placement_mode = template.get("placementMode", "replace-placeholder" if external_template else "reuse-source-child")
    if placement_mode not in ("reuse-source-child", "replace-placeholder", "append-external"):
        raise PreviewCloneError("unsupported clone placementMode")
    if placement_mode == "append-external" and not external_template:
        raise PreviewCloneError("append-external placement requires a distinct external template prefab")
    initial_child_ids = template.get("initialChildSourceIds")
    if not isinstance(initial_child_ids, list):
        raise PreviewCloneError("template.initialChildSourceIds must list exact original parent children")
    append_start = template.get("appendStartSiblingIndex")
    if placement_mode == "append-external":
        if placeholder_id is not None or source_root_parent_id is not None:
            raise PreviewCloneError("append-external cannot replace a placeholder or parent the detached template")
        if type(append_start) is not int or append_start != len(initial_child_ids):
            raise PreviewCloneError("appendStartSiblingIndex must equal the exact original child count")
    else:
        initial_child_id = placeholder_id if external_template else root_id
        if initial_child_ids != [initial_child_id]:
            raise PreviewCloneError("non-append clone placement requires its exact original single child")
    if (not root_id.startswith(template_source_id + "#") or
            not parent_id.startswith(source_id + "#")):
        raise PreviewCloneError("template root and layout parent must belong to declared source prefabs")
    if external_template and placement_mode != "append-external" and not isinstance(placeholder_id, str):
        raise PreviewCloneError("external template requires an explicit source placeholder child")
    if not external_template and (source_root_parent_id != parent_id or placeholder_id is not None):
        raise PreviewCloneError("same-prefab template must be the original child under its layout parent")
    node_by_id, component_by_id, template_nodes, template_components, asset_ids = _tree(
        plan, root_id, parent_id, source_root_parent_id, initial_child_ids)
    if external_template and placement_mode != "append-external" and not placeholder_id.startswith(source_id + "#"):
        raise PreviewCloneError("external template placeholder must belong to container prefab")
    if layout_mode == "native-layout":
        layout = component_by_id.get(layout_id)
        if not layout or layout.get("node") != parent_id or layout.get("type") != "cc.Layout" or layout.get("enabled") is not True:
            raise PreviewCloneError("template parent must have the enabled source cc.Layout component")
        if "position" in template or "position" in template.get("layout", {}):
            raise PreviewCloneError("native-layout clone spec cannot prescribe projected coordinates")
    elif layout_id is not None:
        layout = component_by_id.get(layout_id)
        if not (placement_mode == "append-external" and layout and layout.get("node") == parent_id
                and layout.get("type") == "cc.Layout"):
            raise PreviewCloneError("source-manual mode must not claim an unrelated native Layout component")

    instances = spec.get("instances")
    if not isinstance(instances, list) or not instances or len(instances) > _MAX_INSTANCES:
        raise PreviewCloneError("instances must be a non-empty bounded array")
    if not isinstance(spec.get("sourceVersion"), str) or not spec["sourceVersion"].strip():
        raise PreviewCloneError("sourceVersion is required")
    if not isinstance(spec.get("referenceVersion"), str) or not spec["referenceVersion"].strip():
        raise PreviewCloneError("referenceVersion is required")
    evidence = _verify_evidence_files(clone_spec_path, workspace_root, spec.get("sourceEvidenceFiles"))
    manual_layout = _verify_manual_layout(spec, workspace_root, len(instances)) if layout_mode == "source-manual" else None
    append_grid_rule = None
    if placement_mode == "append-external" and layout_mode == "native-layout":
        append_grid_rule = _source_grid_append_rule(component_by_id[layout_id], node_by_id[parent_id],
                                                    node_by_id[root_id], initial_child_ids, node_by_id, len(instances))
    if manual_layout:
        source_position = node_by_id[root_id].get("position")
        source_size = node_by_id[root_id].get("size")
        if not isinstance(source_position, list) or len(source_position) != 3:
            raise PreviewCloneError("source-manual template root source position is malformed")
        if (manual_layout["formulaId"] != "pass-task-linear-y/1" and
                not math.isclose(source_position[1], manual_layout["sourceTemplateY"], rel_tol=0, abs_tol=1e-6)):
            raise PreviewCloneError("source-manual Y differs from frozen template source position")
        if (manual_layout["formulaId"] == "centered-horizontal-linear/1" and
                (not isinstance(source_size, list) or not source_size or
                 not math.isclose(source_size[0], manual_layout["templateWidth"], rel_tol=0, abs_tol=1e-6))):
            raise PreviewCloneError("source-manual templateWidth differs from frozen source node size")

    missing_assets = sorted({
        operation.get("value")
        for row in instances if isinstance(row, Mapping)
        for operation in row.get("operations", []) if isinstance(operation, Mapping)
        if operation.get("kind") == "sprite.asset" and isinstance(operation.get("value"), str)
        and operation.get("value") not in asset_ids
    })
    if missing_assets:
        raise PreviewCloneError("sprite assets absent from target source plan: " + ", ".join(missing_assets))

    # Verify that instances replace exactly the one source template child and
    # that their sibling order has no holes or repeated identities.
    parent_children = node_by_id[parent_id].get("children")
    if parent_children != initial_child_ids:
        raise PreviewCloneError("clone parent initial children must exactly match the ordered source list")
    seen_keys = set()
    prepared_instances = []
    source_ops = None
    extra_shapes = None
    for index, row in enumerate(instances):
        _object(row, f"instances[{index}]")
        instance_id = _need(row.get("instanceId"), f"instances[{index}].instanceId")
        if instance_id in seen_keys:
            raise PreviewCloneError(f"duplicate clone instanceId: {instance_id}")
        seen_keys.add(instance_id)
        expected_sibling_index = (append_start + index if placement_mode == "append-external" else
                                  index if layout_mode == "native-layout" else index + 1)
        if row.get("siblingIndex") != expected_sibling_index:
            raise PreviewCloneError("clone siblingIndex values differ from the declared source-order contract")
        expected_mode = ("append-clone" if placement_mode == "append-external" else
                         (("reuse-template" if index == 0 else "clone-template")
                          if layout_mode == "native-layout" else "clone-template"))
        if row.get("mode") != expected_mode:
            raise PreviewCloneError("clone mode differs from native reuse or source-manual instantiate behavior")
        if row.get("sourceNodeId") != root_id:
            raise PreviewCloneError("every clone must use the declared source template node")
        if layout_mode == "native-layout" and "position" in row:
            raise PreviewCloneError("native-layout clone instance cannot contain a projected position")
        position = row.get("sourcePosition", row.get("position"))
        if layout_mode == "source-manual":
            if (not isinstance(position, list) or len(position) != 3 or
                    any(type(x) not in (int, float) or type(x) is bool or not math.isfinite(x) for x in position) or
                    row.get("positionEvidenceId") != manual_layout["sourceEvidenceId"]):
                raise PreviewCloneError("source-manual clone requires a finite explicit position and pinned evidence ID")
            manual_index = row.get("layoutIndex", index)
            if type(manual_index) is not int or manual_index < 0:
                raise PreviewCloneError("source-manual layoutIndex must be a non-negative integer")
            expected_position = _manual_expected_position(manual_layout, manual_index)
            if any(not math.isclose(float(position[i]), expected_position[i], rel_tol=0, abs_tol=1e-6) for i in range(3)):
                raise PreviewCloneError("source-manual explicit position differs from the pinned formula")
        operations = row.get("operations")
        if not isinstance(operations, list) or not operations:
            raise PreviewCloneError(f"instances[{index}].operations must be non-empty")
        normalized_ops = []
        seen_op_ids = set()
        for op in operations:
            _object(op, "instance operation")
            op = dict(op)
            op["evidenceId"] = "clone-spec"
            normalized = _value(plan, op, node_by_id, component_by_id, asset_ids,
                                template_nodes, template_components)
            identity = (normalized["kind"], normalized["sourceId"])
            if identity in seen_op_ids:
                raise PreviewCloneError(f"duplicate operation for clone {instance_id}: {identity}")
            seen_op_ids.add(identity)
            normalized_ops.append({**normalized, "evidenceId": "clone-spec"})
        shape = tuple(sorted((op["kind"], op["sourceId"]) for op in normalized_ops))
        if source_ops is None:
            source_ops = shape
        elif shape != source_ops:
            raise PreviewCloneError("all clones must carry the same complete source-backed operation set")
        extras = row.get("extraOperations", [])
        if not isinstance(extras, list):
            raise PreviewCloneError("extraOperations must be an array")
        normalized_extras = [_validate_color(op, component_by_id, node_by_id, template_nodes, template_components) for op in extras]
        extra_shape = tuple(sorted((op["kind"], op["sourceId"]) for op in normalized_extras))
        if extra_shapes is None:
            extra_shapes = extra_shape
        elif extra_shape != extra_shapes:
            raise PreviewCloneError("all clones must carry the same complete extra operation set")
        prepared_instances.append((row, normalized_ops, normalized_extras))

    workspace_root = io.safe(workspace_root)
    evidence_inputs = [io.inside(workspace_root, row["path"]) for row in spec["sourceEvidenceFiles"]]
    output = io.new_output(output, [clone_spec_path, plan_path.parent, *evidence_inputs])
    state_input_dir = output / "state-inputs"
    state_input_dir.mkdir()
    evidence_copy = state_input_dir / "clone-spec-evidence.json"
    evidence_copy.write_bytes(clone_raw)
    batch_rows = []
    from .prefab_preview_state import prepare as prepare_state
    for row, operations, extra_ops in prepared_instances:
        state_id = f"{spec.get('id', 'preview-clones')}:{row['instanceId']}"
        state = {
            "schemaVersion": 1,
            "id": state_id,
            "sourcePrefabId": template_source_id,
            "sourceManifestSha256": manifest_sha,
            "sourceVersion": spec["sourceVersion"],
            "referenceVersion": spec["referenceVersion"],
            "evidence": [{"id": "clone-spec", "path": evidence_copy.name,
                          "sha256": io.sha(clone_raw)}],
            "operations": operations,
        }
        state_path = state_input_dir / f"state-{len(batch_rows):05d}.json"
        state_raw = io.encoded(state)
        state_path.write_bytes(state_raw)
        state_sha = io.sha(state_raw)
        state_out = output / "prepared-states" / f"state-{len(batch_rows):05d}"
        try:
            state_spec = prepare_state(state_path, state_sha, plan, state_out)
        except PreviewStateError as error:
            raise PreviewCloneError(f"source preview state validation failed for {row['instanceId']}: {error}") from error
        batch_rows.append({
            "instanceId": row["instanceId"],
            "sourceRowId": row.get("sourceRowId"),
            "configOrderIndex": row.get("configOrderIndex"),
            "siblingIndex": row["siblingIndex"],
            "mode": row["mode"],
            "sourceNodeId": root_id,
            "parentSourceId": parent_id,
            "previewState": state_spec,
            "extraOperations": extra_ops,
        })
        if "layoutIndex" in row:
            batch_rows[-1]["layoutIndex"] = row["layoutIndex"]
        if layout_mode == "source-manual":
            batch_rows[-1]["position"] = list(row.get("sourcePosition", row.get("position")))
            batch_rows[-1]["positionEvidenceId"] = row["positionEvidenceId"]

    batch = {
        "schema": "monkey-prefab-preview-clone-batch/1",
        "cloneSpecSha256": expected_sha256,
        "sourcePlanSha256": expected_plan_sha256,
        "sourceManifestSha256": manifest_sha,
        "sourcePrefabId": source_id,
        "templatePrefabId": template_source_id,
        "template": {
            "rootSourceId": root_id,
            "templatePrefabId": template_source_id,
            "parentSourceId": parent_id,
            "sourceRootParentSourceId": source_root_parent_id,
            "replacePlaceholderSourceId": placeholder_id,
            "layoutComponentSourceId": layout_id,
            "layoutMode": layout_mode,
            "placementMode": placement_mode,
            "firstSourcePosition": node_by_id[root_id].get("position"),
            "firstSourceSize": node_by_id[root_id].get("size"),
            "appendStartSiblingIndex": append_start if placement_mode == "append-external" else None,
            "initialSiblingIndex": append_start if placement_mode == "append-external" else parent_children.index(initial_child_ids[0]),
            "initialChildSourceIds": parent_children,
            "expectedChildCount": (len(parent_children) + len(instances) if placement_mode == "append-external" else
                                   len(instances) + (1 if layout_mode == "source-manual" else 0)),
            "positionsAreTargetReadbackOnly": True,
            "retainedTemplateDisposition": ("preserve-owner-children" if placement_mode == "append-external" else
                "inactive" if layout_mode == "source-manual" else "reused-as-row-zero"),
            "sourceTree": [
                {"sourceId": sid, "name": node_by_id[sid].get("name"),
                 "parentSourceId": node_by_id[sid].get("parent"),
                 "childrenSourceIds": node_by_id[sid].get("children", []),
                 "componentSourceIds": node_by_id[sid].get("components", [])}
                for sid in sorted(template_nodes, key=lambda x: x)
            ],
        },
        "evidenceFiles": evidence,
        "instances": batch_rows,
        "layoutReadbackRequired": True,
        "sourceBehaviorExecuted": False,
        "diagnostics": [],
    }
    if manual_layout:
        batch["template"]["sourceManualLayout"] = manual_layout
    if append_grid_rule:
        batch["template"]["appendLayoutRule"] = append_grid_rule
    io.write_json(output / "clone-batch.json", batch)
    result = io.finish(output, batch)
    return result


def validate_clone_batch(batch, plan):
    """Read-only schema/source identity guard used by target adapters and tests."""
    _object(batch, "clone batch")
    if batch.get("schema") != "monkey-prefab-preview-clone-batch/1":
        raise PreviewCloneError("unsupported clone batch schema")
    source_id = _need(batch.get("sourcePrefabId"), "sourcePrefabId")
    template_source_id = _need(batch.get("templatePrefabId", source_id), "templatePrefabId")
    expected_manifest = plan.get("sourceManifestSha256") or (plan.get("previewState") or {}).get("sourceManifestSha256")
    if batch.get("sourceManifestSha256") != expected_manifest:
        raise PreviewCloneError("clone batch manifest differs from target source plan")
    if not _SHA256.fullmatch(batch.get("cloneSpecSha256", "")) or not _SHA256.fullmatch(batch.get("sourcePlanSha256", "")):
        raise PreviewCloneError("clone batch is missing source hashes")
    nodes = {row.get("sourceId"): row for row in plan.get("nodes", []) if isinstance(row, Mapping)}
    prefabs = {row.get("sourceId") for row in plan.get("sourcePrefabs", []) if isinstance(row, Mapping)}
    if source_id not in prefabs or template_source_id not in prefabs:
        raise PreviewCloneError("clone batch container or template prefab absent from source plan")
    template = _object(batch.get("template"), "clone batch template")
    layout_mode = template.get("layoutMode")
    if layout_mode not in ("native-layout", "source-manual"):
        raise PreviewCloneError("clone batch layout mode unsupported")
    root_id = template.get("rootSourceId")
    parent_id = template.get("parentSourceId")
    source_root_parent_id = template.get("sourceRootParentSourceId")
    placeholder_id = template.get("replacePlaceholderSourceId")
    external = template_source_id != source_id
    placement_mode = template.get("placementMode", "replace-placeholder" if external else "reuse-source-child")
    if placement_mode not in ("reuse-source-child", "replace-placeholder", "append-external"):
        raise PreviewCloneError("clone batch placement mode unsupported")
    initial_children = template.get("initialChildSourceIds")
    append_start = template.get("appendStartSiblingIndex")
    if not isinstance(initial_children, list) or any(not isinstance(x, str) for x in initial_children):
        raise PreviewCloneError("clone batch initial source child list missing")
    if placement_mode == "append-external":
        if not external or placeholder_id is not None or source_root_parent_id is not None or type(append_start) is not int or append_start != len(initial_children):
            raise PreviewCloneError("clone batch append placement contract invalid")
    else:
        initial_child_id = placeholder_id if external else root_id
        if initial_children != [initial_child_id]:
            raise PreviewCloneError("clone batch single-source-child contract invalid")
    if root_id not in nodes or parent_id not in nodes or nodes[root_id].get("parent") != source_root_parent_id:
        raise PreviewCloneError("clone batch template no longer matches source hierarchy")
    if (not root_id.startswith(template_source_id + "#") or not parent_id.startswith(source_id + "#")):
        raise PreviewCloneError("clone batch template/layout parent outside declared source prefab")
    if template_source_id == source_id:
        if source_root_parent_id != parent_id or placeholder_id is not None:
            raise PreviewCloneError("same-prefab clone batch has invalid source-child contract")
    elif placement_mode != "append-external" and (not isinstance(placeholder_id, str) or not placeholder_id.startswith(source_id + "#") or
          initial_child_id not in nodes):
        raise PreviewCloneError("external clone batch requires a container placeholder child")
    if layout_mode == "native-layout":
        layout = next((c for c in plan.get("components", []) if c.get("sourceId") == template.get("layoutComponentSourceId")), None)
        if not layout or layout.get("node") != parent_id or layout.get("type") != "cc.Layout" or not layout.get("enabled"):
            raise PreviewCloneError("clone batch native Layout source component missing")
    elif template.get("layoutComponentSourceId") is not None:
        source_layout = next((c for c in plan.get("components", []) if c.get("sourceId") == template.get("layoutComponentSourceId")), None)
        if not (placement_mode == "append-external" and source_layout and
                source_layout.get("node") == parent_id and source_layout.get("type") == "cc.Layout"):
            raise PreviewCloneError("source-manual batch cannot claim an unrelated native Layout")
    if (nodes[parent_id].get("children") != initial_children or len(set(initial_children)) != len(initial_children) or
            any(x not in nodes or nodes[x].get("parent") != parent_id for x in initial_children)):
        raise PreviewCloneError("clone batch parent initial child set differs")
    if placement_mode != "append-external" and initial_children != [initial_child_id]:
        raise PreviewCloneError("clone batch parent initial child boundary differs")
    rows = batch.get("instances")
    if not isinstance(rows, list) or not rows:
        raise PreviewCloneError("clone batch instances missing")
    expected_child_count = (len(initial_children) + len(rows) if placement_mode == "append-external" else
                            len(rows) + (1 if layout_mode == "source-manual" else 0))
    if template.get("expectedChildCount") != expected_child_count:
        raise PreviewCloneError("clone batch expected child count differs from placement contract")
    manual = template.get("sourceManualLayout") if layout_mode == "source-manual" else None
    if layout_mode == "source-manual" and (not isinstance(manual, Mapping) or
            manual.get("formulaId") not in ("centered-horizontal-linear/1", "progress-threshold-centers/1", "pass-task-linear-y/1") or
            manual.get("count") != len(rows)):
        raise PreviewCloneError("clone batch source-manual proof missing or inconsistent")
    if placement_mode == "append-external" and layout_mode == "native-layout":
        layout_id = template.get("layoutComponentSourceId")
        source_layout = next((c for c in plan.get("components", []) if c.get("sourceId") == layout_id), None)
        if not source_layout:
            raise PreviewCloneError("append source grid Layout missing")
        expected_rule = _source_grid_append_rule(source_layout, nodes[parent_id], nodes[root_id], initial_children, nodes, len(rows))
        if template.get("appendLayoutRule") != expected_rule:
            raise PreviewCloneError("append Layout rule differs from source plan formula")
    ids = set()
    for i, row in enumerate(rows):
        expected_sibling = (append_start + i if placement_mode == "append-external" else
                            i if layout_mode == "native-layout" else i + 1)
        if not isinstance(row, Mapping) or row.get("siblingIndex") != expected_sibling or row.get("sourceNodeId") != root_id or row.get("parentSourceId") != parent_id:
            raise PreviewCloneError("clone batch instance order/source identity mismatch")
        if row.get("instanceId") in ids:
            raise PreviewCloneError("clone batch duplicate instance identity")
        ids.add(row.get("instanceId"))
        expected_mode = ("append-clone" if placement_mode == "append-external" else
                         (("reuse-template" if i == 0 else "clone-template")
                          if layout_mode == "native-layout" else "clone-template"))
        if row.get("mode") != expected_mode:
            raise PreviewCloneError("clone batch instance mode invalid")
        if layout_mode == "source-manual":
            position = row.get("position")
            if (row.get("positionEvidenceId") != manual.get("sourceEvidenceId") or
                    not isinstance(position, list) or len(position) != 3 or
                    any(type(x) not in (int, float) or type(x) is bool or not math.isfinite(x) for x in position)):
                raise PreviewCloneError("clone batch source-manual position evidence malformed")
            manual_index = row.get("layoutIndex", i)
            if type(manual_index) is not int or manual_index < 0:
                raise PreviewCloneError("clone batch manual layoutIndex malformed")
            expected_position = _manual_expected_position(manual, manual_index)
            if any(not math.isclose(float(position[j]), expected_position[j], rel_tol=0, abs_tol=1e-6) for j in range(3)):
                raise PreviewCloneError("clone batch source-manual position differs from source formula")
        state = _object(row.get("previewState"), "instance.previewState")
        if state.get("sourcePrefabId") != template_source_id or state.get("sourceManifestSha256") != expected_manifest:
            raise PreviewCloneError("instance PreviewState binding differs")
        if not _SHA256.fullmatch(state.get("stateSha256", "")):
            raise PreviewCloneError("instance PreviewState hash missing")
        extras = row.get("extraOperations")
        if not isinstance(extras, list):
            raise PreviewCloneError("instance extraOperations must be an array")
        comp_by_id = {c.get("sourceId"): c for c in plan.get("components", []) if isinstance(c, Mapping)}
        for op in extras:
            if not isinstance(op, Mapping) or op.get("kind") != "sprite.color":
                raise PreviewCloneError("clone batch extra operation is not a source Sprite color")
            if op.get("targetKind") == "component":
                component = comp_by_id.get(op.get("sourceId"))
                if (not component or component.get("type") != "cc.Sprite" or
                        op.get("targetComponentSourceId") != op.get("sourceId") or
                        op.get("targetNodeSourceId") != component.get("node")):
                    raise PreviewCloneError("clone batch sprite.color component binding differs")
                node = nodes[component["node"]]
            elif op.get("targetKind") == "node":
                node = nodes.get(op.get("sourceId"))
                component = comp_by_id.get(op.get("targetComponentSourceId"))
                if (not node or op.get("targetNodeSourceId") != op.get("sourceId") or
                        not component or component.get("type") != "cc.Sprite" or component.get("node") != op.get("sourceId") or
                        op.get("targetComponentSourceId") not in node.get("components", [])):
                    raise PreviewCloneError("clone batch sprite.color node binding differs")
            else:
                raise PreviewCloneError("clone batch sprite.color target kind is missing")
            if op.get("expectedValue") != node.get("color"):
                raise PreviewCloneError("clone batch Sprite color expected value differs from plan")
            value = op.get("value")
            if (not isinstance(value, list) or len(value) != 4 or
                    any(type(channel) is not int or channel < 0 or channel > 255 for channel in value)):
                raise PreviewCloneError("clone batch Sprite color must be four byte channels")
        tree_ids = {item.get("sourceId") for item in template.get("sourceTree", []) if isinstance(item, Mapping)}
        component_ids = {cid for item in template.get("sourceTree", []) if isinstance(item, Mapping)
                         for cid in item.get("componentSourceIds", [])}
        node_ids = {item.get("sourceId") for item in template.get("sourceTree", []) if isinstance(item, Mapping)}
        if any(op.get("targetNodeSourceId") not in node_ids or op.get("targetComponentSourceId") not in component_ids for op in extras):
            raise PreviewCloneError("sprite.color target is not a source node/component in the cloned subtree")
    return True
