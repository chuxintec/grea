"""Source-backed Layout/Widget completion contracts for the v0.7 Prefab pass.

The target algorithms below follow the official Creator 2.4.15 CCLayout and
CCWidgetManager source. They carry normalized component fields, not a source
engine object graph. Runtime behavior and business scripts are outside this
module.
"""
from __future__ import annotations

import math
import numbers
import re
from copy import deepcopy
from collections import defaultdict


SCHEMA = "monkey-prefab-static-layout-completion/1"
CREATOR_2415_LAYOUT_SOURCE = "https://github.com/cocos/cocos-engine/blob/v2.4.15/cocos2d/core/components/CCLayout.js"
CREATOR_2415_WIDGET_SOURCE = "https://github.com/cocos/cocos-engine/blob/v2.4.15/cocos2d/core/components/CCWidget.js"
CREATOR_2415_WIDGET_MANAGER_SOURCE = "https://github.com/cocos/cocos-engine/blob/v2.4.15/cocos2d/core/base-ui/CCWidgetManager.js"

LAYOUT_FIELDS = {
    "__type__", "node", "_N$layoutType", "_resize", "_N$cellSize", "_N$startAxis",
    "_N$paddingLeft", "_N$paddingRight", "_N$paddingTop", "_N$paddingBottom",
    "_N$spacingX", "_N$spacingY", "_N$horizontalDirection", "_N$verticalDirection",
    "_affectedByScale", "_N$affectedByScale", "_layoutSize", "_objFlags",
}
WIDGET_FIELDS = {
    "__type__", "node", "_alignFlags", "_target", "_left", "_right", "_top", "_bottom",
    "_horizontalCenter", "_verticalCenter", "_isAbsLeft", "_isAbsRight", "_isAbsTop",
    "_isAbsBottom", "_isAbsHorizontalCenter", "_isAbsVerticalCenter", "alignMode",
    "_originalWidth", "_originalHeight", "_objFlags",
}
_COMPONENT_SOURCE_ID = re.compile(r"^(?P<asset>[^#]+)#(?P<node>\d+)/components/(?P<ordinal>\d+)$")
_TARGETS = {"cc.Layout": "layout", "cc.Widget": "widget"}


class LayoutCompletionError(ValueError):
    pass


def _same_static_value(expected, actual, tolerance=1e-5):
    if isinstance(expected, bool) or isinstance(actual, bool):
        return type(expected) is bool and type(actual) is bool and expected is actual
    if isinstance(expected, numbers.Real) and isinstance(actual, numbers.Real):
        return math.isfinite(float(expected)) and math.isfinite(float(actual)) and abs(float(expected) - float(actual)) <= tolerance
    if isinstance(expected, dict) and isinstance(actual, dict):
        return expected.keys() == actual.keys() and all(_same_static_value(expected[key], actual[key], tolerance) for key in expected)
    if isinstance(expected, (list, tuple)) and isinstance(actual, (list, tuple)):
        return len(expected) == len(actual) and all(_same_static_value(a, b, tolerance) for a, b in zip(expected, actual))
    return type(expected) is type(actual) and expected == actual


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _value_vector(value, expected=2):
    if isinstance(value, dict) and isinstance(value.get("values"), list):
        value = value["values"]
    if not isinstance(value, list) or len(value) != expected or not all(_finite(v) for v in value):
        return None
    return [float(v) for v in value]


def _source_component(component_id, manifest_assets, sync_component_origins):
    origin_id = component_id
    mapped = sync_component_origins.get(component_id, [])
    if mapped:
        unique = sorted(set(mapped))
        if len(unique) != 1:
            return None, {"status": "source_component_origin_ambiguous", "candidates": unique}
        origin_id = unique[0]
    match = _COMPONENT_SOURCE_ID.fullmatch(origin_id)
    if not match:
        return None, {"status": "source_component_id_unresolved"}
    assets = manifest_assets.get(match.group("asset"), [])
    if len(assets) != 1:
        return None, {"status": "source_manifest_asset_missing_or_ambiguous"}
    instances = assets[0].get("document", {}).get("instances")
    node_index, component_index = int(match.group("node")), int(match.group("ordinal"))
    if not isinstance(instances, list) or node_index >= len(instances):
        return None, {"status": "source_node_index_missing"}
    node = instances[node_index]
    rows = node.get("_components") if isinstance(node, dict) else None
    if not isinstance(rows, list) or component_index >= len(rows):
        return None, {"status": "source_component_index_missing"}
    raw = rows[component_index]
    if isinstance(raw, dict) and set(raw) <= {"__id__"} and type(raw.get("__id__")) is int:
        object_index = raw["__id__"]
        raw = instances[object_index] if 0 <= object_index < len(instances) else None
    if not isinstance(raw, dict):
        return None, {"status": "source_component_object_invalid"}
    return {"originSourceId": origin_id, "raw": raw, "node": node, "asset": assets[0],
            "componentOrdinal": component_index, "nodeIndex": node_index}, {"status": "verified_source_component"}


def _component_origins(plan):
    result = defaultdict(list)
    for relation in plan.get("syncPrefabBindings", []) or []:
        for row in relation.get("componentOrigins", []) or []:
            if isinstance(row, dict) and isinstance(row.get("instanceSourceId"), str) and isinstance(row.get("templateSourceId"), str):
                result[row["instanceSourceId"]].append(row["templateSourceId"])
    return result


def _layout_record(component, source):
    raw = source["raw"]
    extra = sorted(set(raw) - LAYOUT_FIELDS)
    # Serialized source values are authoritative when present. Some normalized
    # plans currently disagree on _N$affectedByScale; retain that discrepancy as
    # evidence, while compiling the value actually serialized by the source.
    layout_type = raw.get("_N$layoutType", component.get("layoutType"))
    resize = raw.get("_resize", component.get("resize"))
    padding = [raw.get("_N$paddingLeft", component.get("padding", [0, 0, 0, 0])[0]),
               raw.get("_N$paddingBottom", component.get("padding", [0, 0, 0, 0])[1]),
               raw.get("_N$paddingRight", component.get("padding", [0, 0, 0, 0])[2]),
               raw.get("_N$paddingTop", component.get("padding", [0, 0, 0, 0])[3])]
    spacing = [raw.get("_N$spacingX", component.get("spacingXY", [0, 0])[0]),
               raw.get("_N$spacingY", component.get("spacingXY", [0, 0])[1])]
    source_cell = _value_vector(raw.get("_N$cellSize")) if "_N$cellSize" in raw else None
    cell = source_cell or list(component.get("cellSize", [40, 40]))
    start_axis = raw.get("_N$startAxis", component.get("startAxis"))
    horizontal_direction = raw.get("_N$horizontalDirection", component.get("horizontalDirection"))
    vertical_direction = raw.get("_N$verticalDirection", component.get("verticalDirection"))
    affected_by_scale = raw.get("_N$affectedByScale", raw.get("_affectedByScale", component.get("affectedByScale")))
    expected_raw = {
        "_N$layoutType": layout_type, "_resize": resize,
        "_N$paddingLeft": padding[0], "_N$paddingBottom": padding[1],
        "_N$paddingRight": padding[2], "_N$paddingTop": padding[3],
        "_N$spacingX": spacing[0], "_N$spacingY": spacing[1],
        "_N$startAxis": component.get("startAxis"),
        "_N$horizontalDirection": component.get("horizontalDirection"),
        "_N$verticalDirection": component.get("verticalDirection"),
        "_affectedByScale": component.get("affectedByScale"),
        "_N$affectedByScale": component.get("affectedByScale"),
    }
    if "_N$cellSize" in raw:
        expected_raw["_N$cellSize"] = cell
    mismatches = []
    for key, expected in expected_raw.items():
        if key not in raw:
            continue
        actual = raw[key]
        if key == "_N$cellSize":
            actual = _value_vector(actual)
            if actual is not None and expected is not None:
                expected = [float(v) for v in expected]
        if actual != expected:
            mismatches.append(key)
    cache = _value_vector(raw.get("_layoutSize")) if "_layoutSize" in raw else None
    slot = {
        "sourceComponentId": component["sourceId"],
        "sourceNodeId": component.get("node"),
        "sourceType": "cc.Layout",
        "componentOrder": source["componentOrdinal"],
        "sourceEnabled": component.get("enabled") is True,
        "sourceEnabledKnown": type(component.get("enabled")) is bool,
        "layoutType": layout_type, "resize": resize,
        "spacingXY": spacing, "padding": padding, "cellSize": cell,
        "cellSizeFromSource": component.get("cellSizeFromSource") is True,
        "startAxis": start_axis,
        "horizontalDirection": horizontal_direction,
        "verticalDirection": vertical_direction,
        "affectedByScale": affected_by_scale is True,
        "sourceLayoutCacheSize": cache,
        "sourceLayoutCacheSizeKnown": cache is not None,
        "sourceFieldPresence": sorted(key for key in LAYOUT_FIELDS - {"__type__", "node", "_objFlags"} if key in raw),
        "fieldValues": {"layoutType": layout_type, "resize": resize, "spacingXY": spacing,
                        "padding": padding, "cellSize": cell, "startAxis": start_axis,
                        "horizontalDirection": horizontal_direction,
                        "verticalDirection": vertical_direction,
                        "affectedByScale": affected_by_scale,
                        "sourceLayoutCacheSizeKnown": cache is not None,
                        "sourceLayoutCacheSize": cache},
        "sourceSerializedFields": deepcopy(raw),
        "unknownSourceFields": extra,
        "sourceFieldMismatches": mismatches,
        "normalizedPlanMismatch": list(mismatches),
        "nativeAlgorithm": "creator-layout-horizontal-v2.4.15" if layout_type == 1 else
                           "creator-layout-vertical-v2.4.15" if layout_type == 2 else
                           "creator-layout-none-noop-v2.4.15" if layout_type == 0 and resize == 0 else "unsupported",
        "sourceCodeEvidence": CREATOR_2415_LAYOUT_SOURCE,
    }
    supported = (
        layout_type in (0, 1, 2) and resize in (0, 1, 2)
        and (layout_type != 0 or resize == 0)
        and len(padding) == 4 and all(_finite(v) for v in padding)
        and len(spacing) == 2 and all(_finite(v) for v in spacing)
        and len(cell) == 2 and all(_finite(v) for v in cell)
        # A mismatch is exposed, not copied forward: the native slot uses raw
        # serialized values above and therefore still represents source semantics.
    )
    slot["status"] = "native_algorithm_supported" if supported and not extra else "partial"
    slot["dynamicAlgorithmEnabled"] = component.get("enabled") is True and supported
    return slot


def _widget_record(component, source, source_node_scale):
    raw = source["raw"]
    extra = sorted(set(raw) - WIDGET_FIELDS)
    plan_target = component.get("target")
    raw_target = raw.get("_target")
    target_source_id = plan_target
    target_plan_mismatch = False
    if isinstance(raw_target, dict) and type(raw_target.get("__id__")) is int:
        owner = source["asset"].get("sourceId")
        raw_target_id = f"{owner}#{raw_target['__id__']}"
        target_plan_mismatch = plan_target not in (None, raw_target_id)
        target_source_id = raw_target_id
    elif "_target" in raw and raw_target is None:
        target_plan_mismatch = plan_target is not None
        target_source_id = None
    plan_margins = list(component.get("margins", [0, 0, 0, 0]))
    plan_absolute = list(component.get("absolute", [True, True, True, True]))
    plan_center = list(component.get("center", [0, 0]))
    plan_center_absolute = list(component.get("centerAbsolute", [True, True]))
    margins = [raw.get("_left", plan_margins[0]), raw.get("_bottom", plan_margins[1]),
               raw.get("_right", plan_margins[2]), raw.get("_top", plan_margins[3])]
    absolute = [raw.get("_isAbsLeft", plan_absolute[0]), raw.get("_isAbsBottom", plan_absolute[1]),
                raw.get("_isAbsRight", plan_absolute[2]), raw.get("_isAbsTop", plan_absolute[3])]
    center = [raw.get("_horizontalCenter", plan_center[0]), raw.get("_verticalCenter", plan_center[1])]
    center_absolute = [raw.get("_isAbsHorizontalCenter", plan_center_absolute[0]),
                       raw.get("_isAbsVerticalCenter", plan_center_absolute[1])]
    flags = raw.get("_alignFlags", component.get("flags"))
    align_mode = raw.get("alignMode", component.get("alignMode", 1))
    source_values = {
        "_alignFlags": component.get("flags"), "_left": plan_margins[0], "_bottom": plan_margins[1],
        "_right": plan_margins[2], "_top": plan_margins[3],
        "_isAbsLeft": plan_absolute[0], "_isAbsBottom": plan_absolute[1],
        "_isAbsRight": plan_absolute[2], "_isAbsTop": plan_absolute[3],
        "_horizontalCenter": plan_center[0], "_verticalCenter": plan_center[1],
        "_isAbsHorizontalCenter": plan_center_absolute[0], "_isAbsVerticalCenter": plan_center_absolute[1],
        "alignMode": component.get("alignMode"),
    }
    mismatches = []
    for key, expected in source_values.items():
        if key in raw and raw[key] != expected:
            mismatches.append(key)
    flag = flags
    node_scale = source_node_scale
    owner_node_id = component.get("node")
    slot = {
        "sourceComponentId": component["sourceId"],
        "sourceNodeId": owner_node_id,
        "sourceType": "cc.Widget",
        "componentOrder": source["componentOrdinal"],
        "sourceEnabled": component.get("enabled") is True,
        "sourceEnabledKnown": type(component.get("enabled")) is bool,
        "targetSourceNodeId": target_source_id,
        "targetUsesParentWhenNull": target_source_id is None,
        "alignFlags": flags,
        "margins": margins,
        "absolute": absolute,
        "center": center,
        "centerAbsolute": center_absolute,
        "alignMode": align_mode,
        "sourceOriginalSize": [raw.get("_originalWidth") or 0.0, raw.get("_originalHeight") or 0.0],
        "sourceOriginalWidthKnown": "_originalWidth" in raw,
        "sourceOriginalHeightKnown": "_originalHeight" in raw,
        "sourceNodeScale": node_scale,
        "sourceFieldPresence": sorted(key for key in WIDGET_FIELDS - {"__type__", "node", "_objFlags"} if key in raw),
        "fieldValues": {"alignFlags": flag, "margins": margins, "absolute": absolute,
                        "center": center, "centerAbsolute": center_absolute,
                        "alignMode": align_mode,
                        "targetUsesParentWhenNull": target_source_id is None,
                        "targetSourceNodeId": target_source_id,
                        "sourceOriginalSize": [raw.get("_originalWidth") or 0.0, raw.get("_originalHeight") or 0.0]},
        "sourceSerializedFields": deepcopy(raw),
        "unknownSourceFields": extra,
        "sourceFieldMismatches": mismatches,
        "normalizedPlanMismatch": list(mismatches) + (["_target"] if target_plan_mismatch else []),
        "nativeAlgorithm": "creator-widget-manager-v2.4.15",
        "sourceCodeEvidence": CREATOR_2415_WIDGET_MANAGER_SOURCE,
    }
    supported = (
        type(flags) is int and 0 <= flags <= 63
        and len(margins) == 4 and all(_finite(v) for v in margins)
        and len(absolute) == 4 and all(type(v) is bool for v in absolute)
        and len(center) == 2 and all(_finite(v) for v in center)
        and len(center_absolute) == 2 and all(type(v) is bool for v in center_absolute)
        and slot["alignMode"] in (0, 1, 2)
        and (target_source_id is not None or (raw_target is None and component.get("target") is None))
    )
    # Compile exact serialized source values; keep normalizer disagreements visible.
    supported = bool(supported) and not extra
    slot["status"] = "native_constraint_supported" if supported else "partial"
    slot["constraintEnabled"] = component.get("enabled") is True and supported
    return slot


def prepare(plan: dict, manifest: dict) -> dict:
    """Prepare source-complete layout/Widget DTOs without changing the plan or files."""
    components = [row for row in plan.get("components", []) if isinstance(row, dict)
                  and row.get("type") in _TARGETS and row.get("convertible") is not True]
    manifest_assets = defaultdict(list)
    for asset in manifest.get("assets", []):
        if isinstance(asset, dict) and isinstance(asset.get("sourceId"), str):
            manifest_assets[asset["sourceId"]].append(asset)
    origins = _component_origins(plan)
    grouped = defaultdict(lambda: {"layouts": [], "widgets": [], "diagnostics": []})
    for component in components:
        source, evidence = _source_component(component.get("sourceId", ""), manifest_assets, origins)
        kind = _TARGETS[component["type"]]
        node_id = component.get("node")
        if source is None:
            grouped[node_id]["diagnostics"].append({"code": "LAYOUT_SOURCE_EVIDENCE_UNRESOLVED",
                                                     "sourceComponentId": component.get("sourceId"), "status": evidence["status"]})
            continue
        if source["raw"].get("__type__") != component["type"]:
            grouped[node_id]["diagnostics"].append({"code": "LAYOUT_SOURCE_COMPONENT_TYPE_MISMATCH",
                                                     "sourceComponentId": component.get("sourceId"),
                                                     "actual": source["raw"].get("__type__"), "expected": component["type"]})
            continue
        node_row = next((row for row in plan.get("nodes", []) if row.get("sourceId") == node_id), None)
        node_scale = node_row.get("scale") if node_row else None
        slot = _layout_record(component, source) if kind == "layout" else _widget_record(component, source, node_scale)
        grouped[node_id][kind + "s"].append(slot)
    result_nodes = []
    for node_id, row in grouped.items():
        row["layouts"].sort(key=lambda slot: (slot.get("componentOrder", -1), slot["sourceComponentId"]))
        row["widgets"].sort(key=lambda slot: (slot.get("componentOrder", -1), slot["sourceComponentId"]))
        slots = [*row["layouts"], *row["widgets"]]
        statuses = [slot["status"] for slot in slots]
        result_nodes.append({
            "sourceNodeId": node_id,
            "componentSourceOrder": [slot["sourceComponentId"] for slot in sorted(slots, key=lambda slot: (slot["componentOrder"], slot["sourceComponentId"]))],
            "layouts": row["layouts"], "widgets": row["widgets"],
            "status": "native_algorithm_supported" if slots and all(status != "partial" for status in statuses) and not row["diagnostics"] else "partial",
            "diagnostics": row["diagnostics"],
            "initialPoseMustRemainUnchangedDuringPrefabSave": True,
            "runtimeInitializationMustBeReadBackSeparately": True,
        })
    return {
        "schema": SCHEMA,
        "status": "native_algorithm_supported" if result_nodes and all(row["status"] == "native_algorithm_supported" for row in result_nodes) else "partial" if result_nodes else "not_run",
        "sourceManifestSha256": plan.get("sourceManifestSha256"),
        "evidenceSources": {"layout": CREATOR_2415_LAYOUT_SOURCE, "widget": CREATOR_2415_WIDGET_SOURCE,
                            "widgetManager": CREATOR_2415_WIDGET_MANAGER_SOURCE},
        "nodes": sorted(result_nodes, key=lambda row: row["sourceNodeId"] or ""),
        "dynamicBusinessImplemented": False,
        "initialPoseUsedAsConstraintProof": False,
    }


def subset_for_nodes(contract: dict, source_node_ids) -> dict:
    """Return the exact static contract scope for one saved source prefab."""
    wanted = set(source_node_ids or [])
    known = {row.get("sourceNodeId") for row in contract.get("nodes", [])}
    unknown = wanted - known
    if unknown:
        raise LayoutCompletionError("STATIC_LAYOUT_NODE_SCOPE_UNKNOWN:" + ",".join(sorted(unknown)))
    result = dict(contract)
    result["nodes"] = [row for row in contract.get("nodes", []) if row.get("sourceNodeId") in wanted]
    if not result["nodes"] and wanted:
        raise LayoutCompletionError("STATIC_LAYOUT_NODE_SCOPE_EMPTY")
    result["status"] = "native_algorithm_supported" if all(row.get("status") == "native_algorithm_supported" for row in result["nodes"]) else "partial"
    return result


def _active(child):
    return child.get("active", True) is True


def simulate_layout(slot: dict, owner_size: list[float], owner_anchor: list[float], children: list[dict]) -> dict:
    """Pure-source H/V Layout execution for a disposable initialized-state probe."""
    if slot.get("layoutType") == 0 and slot.get("resize") == 0:
        return {"ownerSize": list(owner_size), "children": [dict(child) for child in children]}
    layout_type, resize = slot.get("layoutType"), slot.get("resize")
    if layout_type not in (1, 2) or resize not in (0, 1, 2):
        raise LayoutCompletionError("LAYOUT_ALGORITHM_UNSUPPORTED")
    active_indices = [index for index, child in enumerate(children) if _active(child)]
    if not active_indices:
        return {"ownerSize": list(owner_size), "children": [dict(child) for child in children]}
    padding = slot["padding"]
    spacing = slot["spacingXY"]
    affected = slot.get("affectedByScale") is True
    children_out = [dict(child) for child in children]
    axis = 0 if layout_type == 1 else 1
    gap = spacing[axis]
    p_before, p_after = (padding[0], padding[2]) if axis == 0 else (padding[1], padding[3])
    owner_length = owner_size[axis]
    if resize == 1:
        extents = [children[index]["size"][axis] * (abs(children[index]["scale"][axis]) if affected else 1) for index in active_indices]
        owner_length = sum(extents) + gap * (len(active_indices) - 1) + p_before + p_after
    child_lengths = None
    if resize == 2:
        count = len(active_indices)
        new_length = (owner_length - (p_before + p_after) - (count - 1) * gap) / count
        child_lengths = [new_length for _ in active_indices]
    owner_out = list(owner_size)
    owner_out[axis] = owner_length
    layout_anchor = owner_anchor[axis]
    direction = slot.get("horizontalDirection", 0) if axis == 0 else slot.get("verticalDirection", 1)
    reverse = direction == 1 if axis == 0 else direction == 1  # H: RTL; V: TOP_TO_BOTTOM.
    sign = -1 if reverse else 1
    start = (padding[2] if axis == 0 else padding[3]) if reverse else p_before
    boundary = (1 - layout_anchor) * owner_length if reverse else -layout_anchor * owner_length
    cursor = boundary + sign * start
    for active_index, child_index in enumerate(active_indices):
        result = children_out[child_index]
        factor = abs(result["scale"][axis]) if affected else 1.0
        if factor == 0 and resize == 2:
            raise LayoutCompletionError("LAYOUT_ZERO_SCALE_CHILD_RESIZE_UNDEFINED")
        if child_lengths is not None:
            size = list(result["size"])
            size[axis] = child_lengths[active_index] / factor
            result["size"] = size
        extent = result["size"][axis] * factor
        anchor = result["anchor"][axis]
        if reverse:
            anchor = 1 - anchor
        position = list(result["position"])
        cursor += sign * anchor * extent + sign * gap
        position[axis] = cursor
        result["position"] = position
        cursor += sign * (1 - anchor) * extent
    return {"ownerSize": owner_out, "children": children_out}


def probe_expected(contract: dict, geometry: dict) -> dict:
    """Run the source algorithm on explicit disposable-clone input geometry.

    `geometry` is keyed by source node ID. Each node row supplies position, size,
    scale and anchor; optional `children` lists direct source node IDs. Widget rows
    may provide `widgetParentChain` (owner-parent upward through explicit target).
    The input map order is the root-to-leaf execution order unless `nodeOrder` is set.
    """
    state = deepcopy(geometry)
    node_specs = {row["sourceNodeId"]: row for row in contract.get("nodes", [])}
    order = geometry.get("nodeOrder") or list(geometry.keys())
    for node_id in order:
        node_spec = node_specs.get(node_id)
        row = state.get(node_id)
        if node_spec is None or row is None:
            continue
        slots = [(slot.get("componentOrder", -1), "layout", slot) for slot in node_spec.get("layouts", [])]
        slots.extend((slot.get("componentOrder", -1), "widget", slot) for slot in node_spec.get("widgets", []))
        for _, kind, slot in sorted(slots, key=lambda item: item[0]):
            if not slot.get("sourceEnabled"):
                continue
            if kind == "layout":
                child_ids = row.get("children", [])
                child_rows = [state[child_id] for child_id in child_ids if child_id in state]
                result = simulate_layout(slot, row["size"], row["anchor"], child_rows)
                row["size"] = result["ownerSize"]
                for child_id, child_result in zip([child_id for child_id in child_ids if child_id in state], result["children"]):
                    state[child_id].update(child_result)
            else:
                target_id = slot.get("targetSourceNodeId") or row.get("parentSourceNodeId")
                if target_id not in state:
                    raise LayoutCompletionError("WIDGET_PROBE_TARGET_GEOMETRY_MISSING:" + str(target_id))
                target = dict(state[target_id])
                target["explicit"] = bool(slot.get("targetSourceNodeId"))
                chain = []
                if target["explicit"]:
                    cursor = row.get("parentSourceNodeId")
                    while cursor != target_id:
                        if cursor not in state or len(chain) > len(state):
                            raise LayoutCompletionError("WIDGET_PROBE_TARGET_NOT_ANCESTOR:" + str(target_id))
                        chain.append(state[cursor])
                        cursor = state[cursor].get("parentSourceNodeId")
                    chain.reverse()
                result = simulate_widget_alignment(slot, row, target, chain)
                row.update(result)
    rows = [{"sourceId": source_id, "position": list(state[source_id]["position"]), "size": list(state[source_id]["size"])}
            for source_id in order if source_id in state]
    return {"status": "oracle_ready", "rows": rows, "initialPoseUsedAsConstraintProof": False,
            "algorithmEvidence": contract.get("evidenceSources", {})}


def _widget_target_to_parent_axis(value: float, axis: int, chain: list[dict] | None) -> float:
    """Convert target-local coordinates into Widget-parent space via ancestor scales/translations."""
    result = value
    for node in chain or []:  # ordered from the target's child down to the Widget owner's parent
        scale = node["scale"][axis]
        if scale == 0:
            raise LayoutCompletionError("WIDGET_ZERO_ANCESTOR_SCALE_UNSUPPORTED")
        result = (result - node["position"][axis]) / scale
    return result


def simulate_widget_alignment(widget: dict, node: dict, target: dict,
                              widget_parent_chain: list[dict] | None = None) -> dict:
    """Pure-source Creator 2.4 WidgetManager alignment for a disposable probe."""
    flags = widget["alignFlags"]
    margins, absolute = widget["margins"], widget["absolute"]
    center, center_absolute = widget["center"], widget["centerAbsolute"]
    target_size, target_anchor = target["size"], target["anchor"]
    chain = widget_parent_chain or []
    size = list(node["size"])
    position = list(node["position"])
    for axis, edge_low, edge_high, center_bit, center_offset, center_abs, scale_i, anchor_i in (
        (0, 8, 32, 16, 0, 0, 0, 0), (1, 4, 1, 2, 1, 1, 1, 1),
    ):
        mask = edge_low | edge_high | center_bit
        if flags & mask == 0:
            continue
        target_len = target_size[axis]
        if axis == 0:
            low_margin, high_margin = margins[0], margins[2]
            low_abs, high_abs = absolute[0], absolute[2]
            low = -target_anchor[axis] * target_len + (low_margin if low_abs else low_margin * target_len)
            high = low + target_len - (high_margin if high_abs else high_margin * target_len)
        else:
            low_margin, high_margin = margins[1], margins[3]
            low_abs, high_abs = absolute[1], absolute[3]
            low = -target_anchor[axis] * target_len + (low_margin if low_abs else low_margin * target_len)
            high = low + target_len - (high_margin if high_abs else high_margin * target_len)
        if target.get("explicit") is True:
            low = _widget_target_to_parent_axis(low, axis, chain)
            high = _widget_target_to_parent_axis(high, axis, chain)
        scale = node["scale"][scale_i]
        anchor = node["anchor"][anchor_i]
        if scale < 0:
            anchor = 1 - anchor
            scale = -scale
        stretched = bool(flags & edge_low) and bool(flags & edge_high)
        centered = bool(flags & center_bit)
        if stretched:
            extent = high - low
            if scale != 0:
                size[axis] = extent / scale
            position[axis] = low + anchor * extent
        else:
            extent = size[axis] * scale
            if centered:
                offset = center[center_offset] if center_absolute[center_abs] else center[center_offset] * target_len
                target_middle = (0.5 - target_anchor[axis]) * target_len
                if target.get("explicit") is True:
                    offset = _widget_target_to_parent_axis(offset, axis, chain) - _widget_target_to_parent_axis(0.0, axis, chain)
                    target_middle = _widget_target_to_parent_axis(target_middle, axis, chain)
                position[axis] = target_middle + (anchor - 0.5) * extent + offset
            elif flags & edge_low:
                position[axis] = low + anchor * extent
            else:
                position[axis] = high + (anchor - 1) * extent
    return {"size": size, "position": position}


def verify_readback(expected: dict, actual: list[dict], expected_geometry: dict | None = None) -> dict:
    """Strictly verify saved target fields, then optional source-algorithm geometry probes."""
    errors = []
    expected_nodes = {row["sourceNodeId"]: row for row in expected.get("nodes", [])}
    actual_nodes = {row.get("sourceNodeId"): row for row in actual or [] if isinstance(row, dict)}
    if set(expected_nodes) != set(actual_nodes):
        errors.append("layout_completion_node_set_mismatch")
    for node_id, node_spec in expected_nodes.items():
        saved = actual_nodes.get(node_id)
        if saved is None:
            continue
        for kind, expected_slots in (("layouts", node_spec.get("layouts", [])), ("widgets", node_spec.get("widgets", []))):
            actual_slots = saved.get(kind, [])
            if len(expected_slots) != len(actual_slots):
                errors.append(f"{node_id}:{kind}_count_mismatch")
            for index, source in enumerate(expected_slots):
                if index >= len(actual_slots):
                    continue
                row = actual_slots[index]
                if row.get("sourceComponentId") != source.get("sourceComponentId") or row.get("componentOrder") != source.get("componentOrder"):
                    errors.append(f"{node_id}:{kind}_identity_or_order_mismatch:{index}")
                actual_values = deepcopy(row.get("fieldValues"))
                expected_values = source.get("fieldValues")
                # Unity JsonUtility cannot preserve null for reference/array fields.
                # Known flags preserve the distinction: normalize only the exact
                # null encodings for fields whose source absence was recorded.
                if isinstance(expected_values, dict) and isinstance(actual_values, dict):
                    if kind == "layouts" and expected_values.get("sourceLayoutCacheSizeKnown") is False:
                        if actual_values.get("sourceLayoutCacheSize") in (None, []):
                            actual_values["sourceLayoutCacheSize"] = None
                    if kind == "widgets" and expected_values.get("targetUsesParentWhenNull") is True:
                        if actual_values.get("targetSourceNodeId") in (None, ""):
                            actual_values["targetSourceNodeId"] = None
                if not _same_static_value(expected_values, actual_values):
                    errors.append(f"{node_id}:{kind}_field_value_mismatch:{index}")
                if row.get("sourceFieldPresence") != source.get("sourceFieldPresence"):
                    errors.append(f"{node_id}:{kind}_source_field_presence_mismatch:{index}")
                if row.get("unknownSourceFields") != source.get("unknownSourceFields"):
                    errors.append(f"{node_id}:{kind}_unknown_source_fields_mismatch:{index}")
                if row.get("sourceEnabled") != source.get("sourceEnabled"):
                    errors.append(f"{node_id}:{kind}_enabled_mismatch:{index}")
                if row.get("nativeComponentPresent") is not True or row.get("savedReferenceVerified") is not True:
                    errors.append(f"{node_id}:{kind}_native_component_missing:{index}")
    if expected_geometry is not None:
        geometry_rows = expected_geometry.get("rows", [])
        actual_geometry_rows = expected_geometry.get("actual", [])
        actual_by_id = {row.get("sourceId"): row for row in actual_geometry_rows if isinstance(row, dict)}
        for row in geometry_rows:
            actual_row = actual_by_id.get(row.get("sourceId"))
            if actual_row is None:
                errors.append(f"initialized_geometry_missing:{row.get('sourceId')}")
                continue
            for field in ("position", "size"):
                want, got = row.get(field), actual_row.get(field)
                if not isinstance(want, list) or not isinstance(got, list) or len(want) != len(got) or any(abs(a-b) > 1e-3 for a,b in zip(want,got)):
                    errors.append(f"initialized_geometry_mismatch:{row.get('sourceId')}:{field}")
    return {"status": "verified_static_layout_fields" if not errors else "mismatch",
            "errors": errors,
            "runtimeInitializationSeparatelyVerified": expected_geometry is not None and not errors,
            "initialPoseUsedAsConstraintProof": False}


def verify_native_probe(contract: dict, probe: dict, tolerance: float = 0.001) -> dict:
    """Independently execute source formulas and compare a disposable native probe.

    The probe must contain before/input/after transforms for the full prefab node
    map. Every constrained owner receives a size input delta of (+17,+11); only
    that disposable instance is changed. Formula output is calculated from the
    captured input geometry and pinned Creator 2.4 rules, never from saved pose.
    """
    errors = []
    if not isinstance(probe, dict) or probe.get("status") != "probe_captured":
        return {"status": "mismatch", "errors": ["native_layout_probe_missing_or_failed"],
                "formulaVerified": False, "initialPoseUsedAsConstraintProof": False}
    if probe.get("disposableCloneRequired") is not True or probe.get("persistentPrefabMutated") is not False:
        errors.append("probe_not_isolated_from_saved_prefab")
    if probe.get("baselineInitialized") is not True or probe.get("baselineIsConstraintProof") is not False:
        errors.append("probe_initialized_baseline_missing_or_misrepresented")
    probe_rows = probe.get("nodes")
    if not isinstance(probe_rows, list) or not probe_rows:
        return {"status": "mismatch", "errors": errors + ["native_layout_probe_nodes_missing"],
                "formulaVerified": False, "initialPoseUsedAsConstraintProof": False}
    by_id = {}
    for row in probe_rows:
        if not isinstance(row, dict) or not isinstance(row.get("sourceNodeId"), str) or row["sourceNodeId"] in by_id:
            errors.append("native_layout_probe_node_identity_invalid_or_duplicate")
            continue
        by_id[row["sourceNodeId"]] = row
    expected_owner_ids = {row.get("sourceNodeId") for row in contract.get("nodes", [])}
    if not expected_owner_ids or not expected_owner_ids.issubset(by_id):
        errors.append("native_layout_probe_contract_scope_missing")
    expected_components = sorted(
        slot["sourceComponentId"]
        for node in contract.get("nodes", [])
        for slot in [*(node.get("layouts", []) or []), *(node.get("widgets", []) or [])]
        if slot.get("sourceEnabled") is True
    )
    actual_components = sorted(probe.get("appliedSourceComponentIds") or [])
    if expected_components != actual_components:
        errors.append("native_layout_probe_applied_component_set_differs")
    participation_rows = probe.get("layoutParticipation") or []
    participation_by_id = {}
    for row in participation_rows:
        if not isinstance(row, dict) or not isinstance(row.get("sourceComponentId"), str) or row["sourceComponentId"] in participation_by_id:
            errors.append("native_layout_probe_layout_participation_invalid_or_duplicate")
            continue
        participation_by_id[row["sourceComponentId"]] = row

    geometry = {"nodeOrder": [row["sourceNodeId"] for row in probe_rows if row.get("sourceNodeId") in by_id]}
    def stage_geometry(row, name):
        nested = row.get(name)
        if isinstance(nested, dict):
            return nested
        # Accept flattened native records from an older probe producer only when
        # all required topology and transform fields are present.
        return None

    for source_id, row in by_id.items():
        before, input_state, after = (stage_geometry(row, key) for key in ("before", "input", "after"))
        if any(not isinstance(value, dict) for value in (before, input_state, after)):
            errors.append(f"{source_id}:probe_stage_geometry_missing")
            continue
        required = ("position", "size", "anchor", "scale", "parentSourceNodeId", "childrenSourceNodeIds", "activeInHierarchy")
        if any(key not in input_state for key in required):
            errors.append(f"{source_id}:probe_input_geometry_incomplete")
            continue
        for stage_name, value in (("before", before), ("input", input_state), ("after", after)):
            if any(key not in value for key in required):
                errors.append(f"{source_id}:{stage_name}_geometry_incomplete")
                continue
        if before.get("parentSourceNodeId") != input_state.get("parentSourceNodeId") or before.get("childrenSourceNodeIds") != input_state.get("childrenSourceNodeIds"):
            errors.append(f"{source_id}:probe_topology_changed_before_initialization")
        for field in ("anchor", "scale"):
            if not _same_static_value(before.get(field), input_state.get(field), tolerance):
                errors.append(f"{source_id}:probe_input_{field}_changed")
        if not _same_static_value(before.get("position"), input_state.get("position"), tolerance):
            errors.append(f"{source_id}:probe_input_position_changed")
        expected_size = list(before.get("size") or [])
        if source_id in expected_owner_ids and len(expected_size) == 2:
            expected_size = [expected_size[0] + 17.0, expected_size[1] + 11.0]
        if not _same_static_value(expected_size, input_state.get("size"), tolerance):
            errors.append(f"{source_id}:probe_input_size_delta_differs")
        for field in ("activeSelf", "activeInHierarchy"):
            if input_state.get(field) != after.get(field):
                errors.append(f"{source_id}:probe_activation_changed_during_formula")
        for field in ("parentSourceNodeId", "childrenSourceNodeIds", "anchor", "scale"):
            if not _same_static_value(input_state.get(field), after.get(field), tolerance):
                errors.append(f"{source_id}:probe_{field}_changed_during_formula")
        geometry[source_id] = {
            "sourceNodeId": source_id,
            "parentSourceNodeId": input_state.get("parentSourceNodeId"),
            "children": list(input_state.get("childrenSourceNodeIds") or []),
            "active": input_state.get("activeInHierarchy") is True,
            "position": list(input_state.get("position") or []),
            "size": list(input_state.get("size") or []),
            "anchor": list(input_state.get("anchor") or []),
            "scale": list(input_state.get("scale") or []),
        }
        if source_id in expected_owner_ids and input_state.get("activeInHierarchy") is not True:
            errors.append(f"{source_id}:probe_owner_not_active_in_hierarchy")
        if source_id in expected_owner_ids and before.get("activeInHierarchy") is not True:
            errors.append(f"{source_id}:probe_baseline_owner_not_active_in_hierarchy")
    for node_spec in contract.get("nodes", []):
        node_id = node_spec.get("sourceNodeId")
        owner_geometry = geometry.get(node_id)
        if owner_geometry is None:
            continue
        for slot in node_spec.get("layouts", []):
            if slot.get("sourceEnabled") is not True:
                continue
            row = participation_by_id.get(slot.get("sourceComponentId"))
            if row is None:
                errors.append(f"{slot.get('sourceComponentId')}:layout_participation_missing")
                continue
            effective = [child_id for child_id in owner_geometry.get("children", [])
                         if child_id in geometry and geometry[child_id].get("active") is True]
            if row.get("algorithmInvoked") is not True or row.get("ownerSourceNodeId") != node_id:
                errors.append(f"{slot.get('sourceComponentId')}:layout_algorithm_not_invoked")
            if row.get("effectiveChildSourceNodeIds") != effective:
                errors.append(f"{slot.get('sourceComponentId')}:layout_effective_children_mismatch")
            if slot.get("layoutType") in (1, 2) and not effective:
                errors.append(f"{slot.get('sourceComponentId')}:layout_has_no_active_source_children")
    oracle = None
    if not any(error.endswith("probe_input_geometry_incomplete") for error in errors):
        try:
            oracle = probe_expected(contract, geometry)
        except (LayoutCompletionError, KeyError, IndexError, TypeError, ValueError) as exc:
            errors.append("source_formula_oracle_failed:" + str(exc))
    if oracle is not None:
        expected_by_id = {row["sourceId"]: row for row in oracle["rows"]}
        for source_id, want in expected_by_id.items():
            actual_row = by_id.get(source_id)
            after = actual_row.get("after") if actual_row else None
            if not isinstance(after, dict):
                errors.append(f"{source_id}:native_after_geometry_missing")
                continue
            for field in ("position", "size"):
                if not _same_static_value(want.get(field), after.get(field), tolerance):
                    errors.append(f"{source_id}:native_{field}_differs_from_source_formula")
    return {"status": "verified_native_layout_constraints" if not errors else "mismatch",
            "errors": errors, "formulaVerified": oracle is not None and not errors,
            "oracleRows": oracle["rows"] if oracle else [], "appliedSourceComponentIds": actual_components,
            "initialPoseUsedAsConstraintProof": False}
