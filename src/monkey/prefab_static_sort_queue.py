"""Source-bound, non-hierarchical sort queue planning for Cocos 2.4 Prefabs."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
import json
import hashlib
from typing import Any

from .prefab_static_mask_sort import StaticMaskSortError, _raw_component, prepare as prepare_static_mask_sort


_RENDER_TYPES = {"cc.Sprite", "cc.Label", "cc.RichText", "cc.Graphics", "sp.Skeleton"}


class StaticSortQueueError(ValueError):
    pass


def build_queue(plan: Mapping) -> dict:
    """Build Cocos RenderFlow stable nested queues plus Creator mask barriers."""
    nodes = {row["sourceId"]: row for row in plan.get("nodes", [])}
    components_by_node: dict[str, list[dict]] = defaultdict(list)
    for row in plan.get("components", []):
        components_by_node[row.get("node")].append(row)

    orders_by_node: dict[str, list[dict]] = defaultdict(list)
    roots_by_node: dict[str, list[dict]] = defaultdict(list)
    masks_by_node: dict[str, list[dict]] = defaultdict(list)
    for row in plan.get("components", []):
        if row.get("type") == "cc.SortOrder":
            orders_by_node[row["node"]].append(row)
        elif row.get("type") == "cc.SortRoot":
            roots_by_node[row["node"]].append(row)
        elif row.get("type") == "cc.Mask":
            masks_by_node[row["node"]].append(row)

    for node_id, rows in orders_by_node.items():
        effective = {row.get("sourceSortOrder", row.get("sortOrder")) for row in rows}
        # Plan carries source SortOrder values in the hash-bound prepared rows,
        # assigned by prepare() below. Synthetic inputs may instead provide it.
        if len(rows) > 1:
            raise StaticSortQueueError(f"multiple cc.SortOrder components on one source node: {node_id}")
    for node_id in (set(roots_by_node) & set(masks_by_node)):
        raise StaticSortQueueError(f"SortRoot and Mask share one source node; queue ordering is ambiguous: {node_id}")

    def active(node_id: str) -> bool:
        node = nodes.get(node_id)
        if not node or node.get("active") is not True:
            return False
        parent = node.get("parent")
        return parent is None or active(parent)

    def enabled(rows: list[dict]) -> bool:
        return any(row.get("enabled", True) is True for row in rows)

    def order_value(node_id: str) -> float:
        rows = orders_by_node.get(node_id, [])
        if not rows or not enabled(rows):
            return 0
        value = rows[0].get("sourceSortOrder", rows[0].get("sortOrder", 0))
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise StaticSortQueueError(f"invalid effective SortOrder at {node_id}")
        return value

    def source_renderers(node_id: str) -> list[dict]:
        return [row for row in components_by_node.get(node_id, [])
                if row.get("type") in _RENDER_TYPES and row.get("enabled", True) is True]

    all_renderers: list[dict] = []
    for node_id in nodes:
        rows = source_renderers(node_id)
        if len(rows) > 1:
            raise StaticSortQueueError(f"multiple source UIRenderers on one node are outside Sorting2D mapping: {node_id}")
        if rows:
            all_renderers.append({"node": node_id, "sourceComponentId": rows[0].get("sourceId"),
                                  "sourceType": rows[0].get("type"), "sourceSortOrder": order_value(node_id),
                                  "enabled": rows[0].get("enabled", True) is True})

    # A shared monotonically increasing visit counter gives deterministic stable
    # tie handling while queue sort values remain the original Cocos numbers.
    visit = 0
    mask_barrier_specs = []
    unsupported = []

    def traverse(node_id: str, queue: list[dict], root_scope: str):
        nonlocal visit
        if not active(node_id):
            return
        node = nodes[node_id]
        sort_root = roots_by_node.get(node_id, [])
        mask_rows = masks_by_node.get(node_id, [])
        is_root = enabled(sort_root)
        is_mask = enabled(mask_rows)
        if is_root and is_mask:
            raise StaticSortQueueError(f"enabled SortRoot+Mask overlap: {node_id}")
        if (is_root or is_mask) and source_renderers(node_id):
            # RenderFlow treats the structural SortRoot / Mask owner as the
            # queue block; a second ordinary leaf on that node is ambiguous.
            unsupported.append({"node": node_id, "code": "STRUCTURAL_COMPONENT_SHARES_NODE_WITH_RENDERER"})

        if is_root:
            items: list[dict] = []
            for child in node.get("children", []):
                traverse(child, items, node_id)
            entry = {"kind": "sortRoot", "node": node_id, "sortOrder": order_value(node_id),
                     "visit": visit, "items": items, "rootScope": root_scope}
            visit += 1
            queue.append(entry)
            return

        if is_mask:
            items: list[dict] = []
            for child in node.get("children", []):
                traverse(child, items, root_scope)
            entry = {"kind": "maskBlock", "node": node_id, "sortOrder": order_value(node_id),
                     "visit": visit, "items": items, "rootScope": root_scope}
            visit += 1
            queue.append(entry)
            mask_row = mask_rows[0] if mask_rows else {}
            mask_barrier_specs.append({"node": node_id, "sourceId": mask_row.get("sourceId"),
                                       "nativeId": mask_row.get("nativeId"), "sourceType": "cc.Mask",
                                       "sourceSortOrder": entry["sortOrder"], "maskType": mask_row.get("maskType", 0),
                                       "inverted": mask_row.get("inverted", False),
                                       "convertible": mask_row.get("convertible", False), "rootScope": root_scope})
            return

        # Cocos 2.4 RenderFlow runs RENDER before CHILDREN: _render submits
        # fillBuffers before invoking its next flow. Equal sort keys must
        # therefore keep the parent's renderer before its descendants.
        for renderer in source_renderers(node_id):
            entry = {"kind": "leaf", "node": node_id, "sourceComponentId": renderer.get("sourceId"),
                     "sourceType": renderer.get("type"), "sortOrder": order_value(node_id),
                     "enabled": renderer.get("enabled", True) is True,
                     "visit": visit, "rootScope": root_scope}
            visit += 1
            queue.append(entry)
        for child in node.get("children", []):
            traverse(child, queue, root_scope)

    def sort_and_flatten(entries: list[dict], output: list[dict]):
        # Cocos RenderFlow uses an ascending sortOrder comparator. Preserve
        # insertion order for equal keys, matching the source traversal queue.
        ordered = sorted(entries, key=lambda entry: (entry["sortOrder"], entry["visit"]))
        for entry in ordered:
            if entry["kind"] == "leaf":
                output.append({"kind": "renderer", "node": entry["node"],
                               "sourceComponentId": entry.get("sourceComponentId"),
                               "sourceType": entry.get("sourceType"), "sourceSortOrder": entry["sortOrder"],
                               "enabled": entry.get("enabled", True),
                               "rootScope": entry["rootScope"]})
            elif entry["kind"] == "sortRoot":
                sort_and_flatten(entry["items"], output)
            elif entry["kind"] == "maskBlock":
                output.append({"kind": "maskEnter", "node": entry["node"],
                               "sourceSortOrder": entry["sortOrder"], "rootScope": entry["rootScope"]})
                sort_and_flatten(entry["items"], output)
                output.append({"kind": "maskExit", "node": entry["node"],
                               "sourceSortOrder": entry["sortOrder"], "rootScope": entry["rootScope"]})

    roots = [node_id for node_id, node in nodes.items() if node.get("parent") is None]
    expected_by_root = {}
    native_ranks = []
    barrier_results = []
    for root_id in roots:
        queue: list[dict] = []
        traverse(root_id, queue, root_id)
        flattened: list[dict] = []
        sort_and_flatten(queue, flattened)
        expected_renderers = [row for row in flattened if row["kind"] in ("renderer", "maskEnter")]
        mask_count = sum(row["kind"] == "maskEnter" for row in flattened)
        expected_ids = [(row["kind"], row["node"], row.get("sourceComponentId")) for row in expected_renderers]
        rank_by_id = {}
        for rank, row in enumerate(expected_renderers):
            key = (row["kind"], row["node"], row.get("sourceComponentId"))
            if key in rank_by_id:
                raise StaticSortQueueError(f"duplicate render leaf identity in source queue: {key}")
            rank_by_id[key] = rank
            native_ranks.append({"rootScope": root_id, "node": row["node"],
                                 "sourceComponentId": row.get("sourceComponentId"),
                                 "sourceType": row.get("sourceType", "cc.Mask"),
                                 "sourceSortOrder": row["sourceSortOrder"], "nativeSortingOrder": rank,
                                 "enabled": row.get("enabled", True),
                                 "kind": row["kind"]})
        # Creator 3.8 Sorting2D sorts one priority queue between Mask enter/exit
        # barriers. Compare its achievable traversal segments with Cocos' exact
        # flattened nested queue. Any displaced mask block remains a real gap.
        segments: list[list[tuple[str, str, str | None]]] = []
        current: list[tuple[str, str, str | None]] = []

        def flush():
            nonlocal current
            if current:
                segments.append(current)
                current = []

        def target_walk(node_id: str):
            if not active(node_id):
                return
            if enabled(masks_by_node.get(node_id, [])):
                flush()
                current.append(("maskEnter", node_id, None))
                for child in nodes[node_id].get("children", []):
                    target_walk(child)
                flush()
                return
            for renderer in source_renderers(node_id):
                current.append(("renderer", node_id, renderer.get("sourceId")))
            for child in nodes[node_id].get("children", []):
                target_walk(child)

        target_walk(root_id)
        flush()
        candidate = []
        for segment in segments:
            # Native Sorting2D receives unique compressed ranks; tie stability
            # is therefore encoded in the rank rather than runtime sort claims.
            candidate.extend(sorted(segment, key=lambda key: rank_by_id.get(key, 1 << 31)))
        creator_representable = candidate == expected_ids
        native_dfs = []

        def native_walk(node_id: str):
            if not active(node_id):
                return
            if enabled(masks_by_node.get(node_id, [])):
                native_dfs.append(("maskEnter", node_id, None))
                for child in nodes[node_id].get("children", []):
                    native_walk(child)
                native_dfs.append(("maskExit", node_id, None))
                return
            for renderer in source_renderers(node_id):
                native_dfs.append(("renderer", node_id, renderer.get("sourceId")))
            for child in nodes[node_id].get("children", []):
                native_walk(child)

        native_walk(root_id)
        source_draw_events = [(row["kind"], row["node"], row.get("sourceComponentId"))
                              for row in flattened if row["kind"] in ("renderer", "maskEnter", "maskExit")]
        native_dfs_matches = source_draw_events == native_dfs
        barrier_results.append({"rootScope": root_id, "sourceRendererCount": len(expected_renderers),
                                "sourceMaskBlockCount": mask_count,
                                "creatorSorting2DRepresentable": creator_representable,
                                "expectedOrder": expected_ids, "nativeMaskBarrierOrder": candidate,
                                "sourceDrawEvents": source_draw_events, "nativeDfsDrawEvents": native_dfs,
                                "nativeDfsMatchesSource": native_dfs_matches,
                                "creatorMode": "source-fixed-tree" if native_dfs_matches else
                                    "sorting2d" if creator_representable else "unsupported",
                                "diagnostic": None if creator_representable else "CREATOR_MASK_BARRIER_REORDERS_SOURCE_QUEUE",
                                "unityQueueMapped": mask_count == 0 or native_dfs_matches,
                                "unityMode": "source-fixed-tree" if mask_count > 0 and native_dfs_matches else
                                    "canvas-rank" if mask_count == 0 else "unsupported",
                                "unityDiagnostic": None if mask_count == 0 or native_dfs_matches else
                                    "UNITY_NESTED_CANVAS_BREAKS_MASK_STENCIL_BLOCK"})
        expected_by_root[root_id] = flattened

    if len(native_ranks) > 32768:
        unsupported.append({"code": "SORTING2D_INT16_ORDER_CAPACITY_EXCEEDED", "count": len(native_ranks)})
    return {"schemaVersion": 1, "roots": roots, "renderers": all_renderers,
            "queueByRoot": expected_by_root, "nativeRanks": native_ranks,
            "maskBarriers": barrier_results, "maskBarrierSpecs": mask_barrier_specs,
            "unsupported": unsupported,
            "creatorQueueMapped": not unsupported and all(row["creatorMode"] != "unsupported" for row in barrier_results),
            "unityQueueMapped": not unsupported and all(row["unityQueueMapped"] for row in barrier_results)}


def prepare(plan: Mapping, manifest: Mapping) -> dict:
    """Verify source binding, resolve source SortOrder identities, and plan both targets."""
    plan_for_source = dict(plan)
    origin_rows = list(plan.get("staticAnimationComponentOrigins", []))
    for binding in plan.get("syncPrefabBindings", []):
        origin_rows.extend(binding.get("componentOrigins", []))
    plan_for_source["staticAnimationComponentOrigins"] = origin_rows
    source = prepare_static_mask_sort(plan_for_source, manifest)
    values_by_native = {row["nativeId"]: row["sortOrder"] for row in source["sortOrders"]}
    sort_by_source = {row["sourceId"]: row for row in source["sortOrders"]}
    sort_root_by_source = {row["sourceId"]: row for row in source["sortRoots"]}
    order_occurrences = source["sortOrders"]
    plan_copy = dict(plan)
    components = []
    for row in plan.get("components", []):
        item = dict(row)
        if item.get("type") == "cc.SortOrder":
            bound = sort_by_source.get(item.get("sourceId")) or next(
                (candidate for candidate in source["sortOrders"] if candidate.get("nativeId") == item.get("nativeId")), None)
            value = bound.get("sortOrder") if bound else values_by_native.get(item.get("nativeId"))
            if value is None or bound is None:
                raise StaticSortQueueError(f"source SortOrder value was not bound: {item.get('sourceId')}")
            item["nativeId"] = bound["nativeId"]
            item["sourceSortOrder"] = value if item.get("enabled", True) else 0
        elif item.get("type") == "cc.SortRoot":
            bound = sort_root_by_source.get(item.get("sourceId")) or next(
                (candidate for candidate in source["sortRoots"] if candidate.get("nativeId") == item.get("nativeId")), None)
            if bound is not None:
                item["nativeId"] = bound["nativeId"]
        components.append(item)
    plan_copy["components"] = components
    result = build_queue(plan_copy)
    residual_masks = {row["nativeId"]: row for row in source["masks"]}
    component_origins = {row.get("instanceSourceId"): row.get("templateSourceId") for row in origin_rows}

    def component_origin(source_id: str) -> str:
        seen = set()
        while source_id in component_origins:
            if source_id in seen:
                raise StaticSortQueueError("component source-origin cycle")
            seen.add(source_id)
            source_id = component_origins[source_id]
        return source_id

    for mask_row in result["maskBarrierSpecs"]:
        bound = residual_masks.get(mask_row.get("nativeId"))
        raw_source_id = bound.get("sourceOriginId") if bound else component_origin(mask_row["sourceId"])
        raw = _raw_component(manifest, raw_source_id)
        if raw.get("__type__") != "cc.Mask":
            raise StaticSortQueueError(f"mask identity resolves to a different source type: {mask_row['sourceId']}")
        source_type = raw.get("_type", 0)
        source_inverted = raw.get("_N$inverted", False)
        source_threshold = raw.get("_N$alphaThreshold", 0.1)
        if source_type != mask_row["maskType"] or source_inverted is not mask_row["inverted"]:
            raise StaticSortQueueError(f"plan mask fields differ from hash-bound source: {mask_row['sourceId']}")
        if type(source_type) is not int or source_type not in (0, 1, 2) or type(source_inverted) is not bool:
            raise StaticSortQueueError(f"unsupported hash-bound source mask fields: {mask_row['sourceId']}")
        if isinstance(source_threshold, bool) or not isinstance(source_threshold, (int, float)) or not 0 <= source_threshold <= 1:
            raise StaticSortQueueError(f"invalid hash-bound source mask threshold: {mask_row['sourceId']}")
        sprite_ref = raw.get("_spriteFrame")
        mask_row.update({"alphaThreshold": source_threshold,
                         "spriteFrameUuid": sprite_ref.get("__uuid__") if isinstance(sprite_ref, Mapping) else None,
                         "sourceFields": dict(raw),
                         "sourceFieldsJson": json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))})
        if bound:
            for key in ("spriteFrameUuid", "alphaThreshold", "sourceFields", "sourceMaterialId",
                        "resolvedSourceMaterialId", "sourceEffectId", "sourceEffectName",
                        "sourceEffectDocumentSha256", "unityMaskShaderPath", "unityMaskShaderSha256",
                        "unityMaskMaterialGuid", "unityMaskMaterialPath"):
                if key in bound:
                    mask_row[key] = bound[key]
            # The raw component object is the complete, hash-bound source
            # field payload, including inspector references skipped by the
            # simpler non-inverted rectangular mask converter.
            mask_row["sourceFieldsJson"] = json.dumps(mask_row["sourceFields"], ensure_ascii=False,
                                                       sort_keys=True, separators=(",", ":"))
    node_root = {}
    source_child_order = {}
    source_node_active = {}
    nodes = {row["sourceId"]: row for row in plan.get("nodes", [])}
    for root_id in result["roots"]:
        stack = [root_id]
        while stack:
            node_id = stack.pop()
            node_root[node_id] = root_id
            node = nodes[node_id]
            source_child_order[node_id] = list(node.get("children", []))
            source_node_active[node_id] = node.get("active") is True
            stack.extend(node.get("children", []))
    result.update({"sourceManifestSha256": source["sourceManifestSha256"],
                   "sortOrderOccurrences": order_occurrences,
                   "sortRootOccurrences": source["sortRoots"],
                   "sortGroupProposal": source["sortGroups"],
                   "nodeRoot": node_root, "sourceChildOrder": source_child_order,
                   "sourceNodeActive": source_node_active,
                   "creatorAdapter": "cc.Sorting2D.defaultLayer.compressedStableRenderRank",
                   "unityAdapter": "Canvas.overrideSorting+stencil-bridge-required"})
    return result


def for_root(queue_contract: Mapping, root_scope: str) -> dict:
    """Filter the immutable full-plan contract to one Prefab root for execution."""
    if root_scope not in queue_contract.get("roots", []):
        raise StaticSortQueueError(f"source Prefab root is not in sort contract: {root_scope}")
    root_result = next(row for row in queue_contract["maskBarriers"] if row["rootScope"] == root_scope)
    node_root = queue_contract["nodeRoot"]
    unity_type_map = {"cc.Sprite": "UnityEngine.UI.Image", "cc.Label": "TMPro.TextMeshProUGUI",
                      "cc.RichText": "TMPro.TextMeshProUGUI",
                      "cc.Graphics": "NativeStaticGraphics",
                      "sp.Skeleton": "Spine.Unity.SkeletonGraphic"}
    native_ranks = []
    for row in queue_contract["nativeRanks"]:
        if row["rootScope"] != root_scope:
            continue
        item = dict(row)
        item["expectedGraphicType"] = unity_type_map.get(item["sourceType"])
        native_ranks.append(item)
    unity_ranks = [row for row in native_ranks if row["kind"] == "renderer"]
    unity_masks = []
    for source_mask in queue_contract["maskBarrierSpecs"]:
        if source_mask["rootScope"] != root_scope:
            continue
        row = dict(source_mask)
        fields = row.get("sourceFields")
        row["sourceFieldsJson"] = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")) if fields is not None else ""
        row["enabled"] = True
        unity_masks.append(row)
    proxy_root = {"kind": "root", "sourceNode": root_scope, "children": []}
    proxy_stack = [proxy_root]
    mask_by_node = {row["node"]: row for row in unity_masks}
    rank_by_component = {row.get("sourceComponentId"): row for row in native_ranks if row.get("sourceComponentId")}
    for kind, node_id, component_id in root_result["sourceDrawEvents"]:
        if kind == "maskEnter":
            group = {"kind": "maskGroup", "sourceNode": node_id,
                     "mask": mask_by_node[node_id], "children": []}
            proxy_stack[-1]["children"].append(group)
            proxy_stack.append(group)
        elif kind == "maskExit":
            if len(proxy_stack) <= 1 or proxy_stack[-1].get("sourceNode") != node_id:
                raise StaticSortQueueError(f"unbalanced source mask block in proxy plan at {node_id}")
            proxy_stack.pop()
        elif kind == "renderer":
            row = rank_by_component.get(component_id)
            if row is None:
                raise StaticSortQueueError(f"proxy draw event is missing native renderer rank: {component_id}")
            proxy_stack[-1]["children"].append({"kind": "rendererProxy", "sourceNode": node_id,
                "sourceComponentId": component_id, "sourceType": row["sourceType"],
                "sourceSortOrder": row["sourceSortOrder"], "nativeSortingOrder": row["nativeSortingOrder"]})
        else:
            raise StaticSortQueueError(f"unknown source draw event kind: {kind}")
    if len(proxy_stack) != 1:
        raise StaticSortQueueError("unclosed source mask block in proxy plan")
    return {"schemaVersion": queue_contract["schemaVersion"], "sourceManifestSha256": queue_contract["sourceManifestSha256"],
            "rootScope": root_scope, "creatorQueueMapped": root_result["creatorMode"] != "unsupported",
            "creatorMode": root_result["creatorMode"], "unityQueueMapped": root_result["unityQueueMapped"],
            "unityMode": root_result["unityMode"],
            "nativeDfsMatchesSource": root_result["nativeDfsMatchesSource"],
            "sourceDrawEvents": root_result["sourceDrawEvents"],
            "nativeDfsDrawEvents": root_result["nativeDfsDrawEvents"],
            "maskDiagnostic": root_result["unityDiagnostic"],
            "unitySourceDrawEvents": [row for row in root_result["sourceDrawEvents"] if row[0] == "renderer"],
            "unityRenderers": unity_ranks,
            "unityProxyTree": proxy_root,
            # Keep every source mask field and its hash-bound asset proof in
            # the execution DTO; adapters must not reconstruct masks from the
            # compact presentation summary above.
            "unityMasks": unity_masks,
            "unityMaskScopes": [{"node": row["node"], "maskType": row["maskType"],
                                 "inverted": row["inverted"], "convertible": row["convertible"]}
                                for row in unity_masks],
            "maskNodeIds": [row["node"] for row in unity_masks],
            "maskSourceTypes": {row["node"]: {"maskType": row["maskType"], "inverted": row["inverted"],
                                                "convertible": row["convertible"]} for row in unity_masks},
            "maskBarrier": root_result,
            "nativeRanks": native_ranks,
            "sortOrderFields": [row for row in queue_contract["sortOrderOccurrences"] if node_root.get(row["node"]) == root_scope],
            "sortRootOccurrences": [row for row in queue_contract["sortRootOccurrences"] if node_root.get(row["node"]) == root_scope],
            "sourceChildOrder": {node: children for node, children in queue_contract["sourceChildOrder"].items()
                                 if node_root.get(node) == root_scope},
            "sourceNodeActive": {node: active for node, active in queue_contract["sourceNodeActive"].items()
                                 if node_root.get(node) == root_scope},
            "creatorAdapter": queue_contract["creatorAdapter"],
            "unityAdapter": queue_contract["unityAdapter"]}


def to_unity_proxy_spec(plan: Mapping, manifest: Mapping, root_scope: str) -> dict:
    """Emit one Editor-helper DTO for creating/readback of one Unity Prefab proxy.

    The source Prefab path and mesh folder are derived from the hash-bound
    plan. Mesh names are content-addressed by the Editor helper using the
    source component ID, submesh index, source mesh hash, and transformed mesh
    hash, so repeated imports reuse the same asset identity.
    """
    contract = prepare(plan, manifest)
    root = for_root(contract, root_scope)
    matches = [row for row in plan.get("sourcePrefabs", []) if row.get("root") == root_scope]
    if len(matches) != 1:
        raise StaticSortQueueError(f"source Prefab root does not resolve to one Unity asset: {root_scope}")
    prefab = matches[0]
    prefab_path = prefab.get("path")
    prefab_id = prefab.get("sourceId")
    if not isinstance(prefab_path, str) or not prefab_path.startswith("Assets/") or not isinstance(prefab_id, str):
        raise StaticSortQueueError(f"source Prefab binding is incomplete: {root_scope}")
    prefix = prefab_path.rsplit("/", 1)[0]
    folder_key = hashlib.sha256((prefab_id + "|" + root_scope).encode("utf-8")).hexdigest()[:12]
    mesh_folder = prefix + "/StaticSortQueue_" + folder_key
    unity_type_map = {"cc.Sprite": "UnityEngine.UI.Image", "cc.Label": "TMPro.TextMeshProUGUI",
                      "cc.RichText": "TMPro.TextMeshProUGUI", "cc.Graphics": "NativeStaticGraphics",
                      "sp.Skeleton": "Spine.Unity.SkeletonGraphic"}
    draw_events = [{"kind": kind, "node": node, "sourceComponentId": component_id}
                   for kind, node, component_id in root["sourceDrawEvents"]]
    components_by_id = {row.get("sourceId"): row for row in plan.get("components", []) if isinstance(row, Mapping)}
    source_active = root.get("sourceNodeActive", {})
    source_nodes = {row.get("sourceId"): row for row in plan.get("nodes", []) if isinstance(row, Mapping)}

    def active_in_hierarchy(node_id):
        seen = set()
        cursor = node_id
        while cursor is not None:
            if cursor in seen:
                raise StaticSortQueueError("source node parent cycle while proving active renderer")
            seen.add(cursor)
            if source_active.get(cursor) is not True:
                return False
            node = source_nodes.get(cursor)
            cursor = node.get("parent") if node else None
        return True
    origins = {row.get("instanceSourceId"): row.get("templateSourceId")
               for row in plan.get("staticAnimationComponentOrigins", []) if isinstance(row, Mapping)}
    for binding in plan.get("syncPrefabBindings", []):
        for row in binding.get("componentOrigins", []):
            origins[row.get("instanceSourceId")] = row.get("templateSourceId")

    def origin(source_id):
        seen = set()
        while source_id in origins:
            if source_id in seen:
                raise StaticSortQueueError("static renderer source-origin cycle")
            seen.add(source_id)
            source_id = origins[source_id]
        return source_id

    def renderer_spec(row):
        component = components_by_id.get(row["sourceComponentId"], {})
        source_type = row["sourceType"]
        rich = component.get("staticRichText") or {}
        raw = None
        raw_sha = None
        commands_empty = False
        source_drawing_commands = None
        source_material_guids = []
        if source_type == "cc.Graphics":
            raw = _raw_component(manifest, origin(row["sourceComponentId"]))
            if raw.get("__type__") != "cc.Graphics" or set(raw) - {"__type__", "_materials", "node"}:
                raise StaticSortQueueError(f"Unity static Graphics has serialized commands: {row['sourceComponentId']}")
            raw_json = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            raw_sha = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
            commands_empty = True
            binding = component.get("staticControlBinding") or {}
            if binding.get("sourceDrawingCommands") != "not-serialized-empty-in-fixed-state":
                raise StaticSortQueueError(f"Unity static Graphics lacks empty-command source proof: {row['sourceComponentId']}")
            source_drawing_commands = binding.get("sourceDrawingCommands")
            source_material_guids = [material.get("unityMaterialGuid") for material in binding.get("materials", [])
                                     if isinstance(material, Mapping)]
            if not source_material_guids or any(not isinstance(guid, str) or not guid for guid in source_material_guids):
                raise StaticSortQueueError(f"Unity static Graphics source Material identities are incomplete: {row['sourceComponentId']}")
        source_text = rich.get("serializedSourceText", rich.get("text", component.get("text", "")))
        if source_type == "cc.Label":
            source_text = component.get("text", "")
        native_text = rich.get("unityMarkup", source_text) if source_type == "cc.RichText" else source_text
        spec = {"node": row["node"], "sourceComponentId": row["sourceComponentId"],
                "sourceType": source_type, "expectedGraphicType": row["expectedGraphicType"],
                "sourceSortOrder": row["sourceSortOrder"], "sourceQueueIndex": row["nativeSortingOrder"],
                "sourceEnabled": component.get("enabled", True) is True,
                "sourceActive": active_in_hierarchy(row["node"]),
                "sourceTextureBound": bool(component.get("spriteFrame")) if source_type == "cc.Sprite" else False,
                "sourceText": source_text if source_type in ("cc.Label", "cc.RichText") else "",
                "nativeTextExpectation": native_text if source_type in ("cc.Label", "cc.RichText") else "",
                "sourceTextEmpty": rich.get("plainText", source_text) == "" if source_type == "cc.RichText" else
                    source_text == "" if source_type == "cc.Label" else False,
                "sourceFontMissing": (not component.get("font") and not component.get("nativeSystemFont"))
                    if source_type in ("cc.Label", "cc.RichText") else False,
                "sourceCommandsEmpty": commands_empty, "sourceDrawingCommands": source_drawing_commands,
                "sourceMaterialGuids": source_material_guids}
        if source_type == "cc.RichText":
            raw = _raw_component(manifest, origin(row["sourceComponentId"]))
            planned_raw = component.get("sourceRichText")
            if (not isinstance(raw, Mapping) or raw.get("__type__") != "cc.RichText" or
                    not isinstance(planned_raw, Mapping) or
                    json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")) !=
                    json.dumps(planned_raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))):
                raise StaticSortQueueError(f"Creator RichText lacks hash-bound serialized source fields: {row['sourceComponentId']}")
            raw_json = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            raw_sha = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
        if raw is not None:
            spec["sourceFieldsJson"] = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            spec["sourceFieldsSha256"] = raw_sha
        return spec

    renderer_specs = [renderer_spec(row) for row in root["unityRenderers"]]
    active_component_ids = {row.get("sourceComponentId") for row in root["unityRenderers"]}
    non_draw_specs = []
    for component in plan.get("components", []):
        if (not isinstance(component, Mapping) or component.get("node") not in root["sourceChildOrder"] or
                component.get("type") not in _RENDER_TYPES or
                component.get("sourceId") in active_component_ids):
            continue
        source_is_active = active_in_hierarchy(component["node"])
        if component.get("enabled", True) is True and source_is_active:
            if component.get("type") == "cc.Graphics":
                continue
            raise StaticSortQueueError(f"active Unity source renderer was omitted from draw events: {component['sourceId']}")
        disabled_row = {"node": component["node"], "sourceComponentId": component["sourceId"],
                        "sourceType": component["type"], "expectedGraphicType": unity_type_map.get(component["type"]),
                        "sourceSortOrder": 0, "nativeSortingOrder": -1}
        # Disabled source components are captured as typed no-draw field rows,
        # but are not inserted into Cocos' renderer event sequence.
        non_draw_specs.append(renderer_spec(disabled_row))
    # Keep this local binding adjacent to renderer_spec for closures above.
    renderers = renderer_specs
    return {"schemaVersion": 1, "rootScope": root_scope, "sourcePrefabId": prefab_id,
            "prefabPath": prefab_path, "sourcePrefabRootName": next(
                (row.get("name") for row in plan.get("nodes", []) if row.get("sourceId") == root_scope), None),
            "sourceManifestSha256": contract["sourceManifestSha256"], "meshAssetFolder": mesh_folder,
            "meshAssetNaming": "QueueMesh_<sha256(sourceComponentId|submeshIndex|sourceMeshSha256|proxyMeshSha256)[0:24]>.asset",
            "renderers": renderers, "nonDrawRenderers": non_draw_specs,
            "masks": [dict(row) for row in root["unityMasks"]],
            "drawEvents": draw_events,
            "sourceFields": [{"sourceId": row["sourceId"], "nativeId": row["nativeId"], "node": row["node"],
                              "sortOrder": row["sortOrder"], "enabled": row["enabled"]}
                             for row in root["sortOrderFields"]],
            "sourceSortRoots": [{"sourceId": row["sourceId"], "nativeId": row["nativeId"], "node": row["node"],
                                 "enabled": row["enabled"]}
                                for row in root["sortRootOccurrences"]],
            "sourceChildOrder": [{"node": node, "children": children}
                                  for node, children in root["sourceChildOrder"].items()],
            "sourceNodeActive": [{"node": node, "active": active}
                                 for node, active in root["sourceNodeActive"].items()],
            "unityProxyTree": root["unityProxyTree"], "unityQueueMapped": root["unityQueueMapped"],
            "unityMode": root["unityMode"], "maskDiagnostic": root["maskDiagnostic"]}


def to_creator_proxy_spec(plan: Mapping, manifest: Mapping, root_scope: str) -> dict:
    """Emit Creator 3.8 native proxy queue data bound to the source manifest."""
    contract = prepare(plan, manifest)
    root = for_root(contract, root_scope)
    prefab_rows = [row for row in plan.get("sourcePrefabs", []) if row.get("root") == root_scope]
    if len(prefab_rows) != 1:
        raise StaticSortQueueError(f"source Creator Prefab root does not resolve uniquely: {root_scope}")
    prefab = prefab_rows[0]
    component_origins = {row.get("instanceSourceId"): row.get("templateSourceId")
                         for row in plan.get("staticAnimationComponentOrigins", [])}
    for binding in plan.get("syncPrefabBindings", []):
        for row in binding.get("componentOrigins", []):
            component_origins[row.get("instanceSourceId")] = row.get("templateSourceId")
    creator_assets_by_id = {}
    for asset in plan.get("assets", []):
        if isinstance(asset, Mapping) and isinstance(asset.get("sourceId"), str):
            creator_assets_by_id.setdefault(asset["sourceId"], []).append(asset)

    def component_origin(source_id: str) -> str:
        seen = set()
        while source_id in component_origins:
            if source_id in seen:
                raise StaticSortQueueError("source Graphics component origin cycle")
            seen.add(source_id)
            source_id = component_origins[source_id]
        return source_id

    graphics_proofs = {}
    graphics_no_draw_proofs = {}
    richtext_proofs = {}
    for row in plan.get("components", []):
        if row.get("type") != "cc.Graphics" or row.get("node") not in root["sourceChildOrder"]:
            continue
        raw = _raw_component(manifest, component_origin(row["sourceId"]))
        if raw.get("__type__") != "cc.Graphics" or set(raw) - {"__type__", "_materials", "node"}:
            raise StaticSortQueueError(f"source Graphics has serialized drawing data that cannot be copied natively: {row['sourceId']}")
        fields_json = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        static_control = row.get("staticControlBinding") or {}
        if static_control.get("sourceDrawingCommands") != "not-serialized-empty-in-fixed-state":
            raise StaticSortQueueError(f"Creator cc.Graphics lacks an empty command-stream proof: {row['sourceId']}")
        materials = static_control.get("materials", [])
        source_material_ids = [material.get("sourceId") for material in materials if isinstance(material, Mapping)]
        if not source_material_ids or any(not isinstance(value, str) or not value for value in source_material_ids):
            raise StaticSortQueueError(f"Creator cc.Graphics source material identities are incomplete: {row['sourceId']}")
        graphics_proofs[row["sourceId"]] = {"sourceFields": dict(raw),
            "sourceFieldsSha256": hashlib.sha256(fields_json.encode("utf-8")).hexdigest(),
            "sourceFieldsJson": fields_json, "initialCommandStreamEmpty": True}
        graphics_no_draw_proofs[row["sourceId"]] = {"initialCommandStreamEmpty": True,
            "sourceDrawingCommands": static_control["sourceDrawingCommands"],
            "sourceMaterialIds": source_material_ids, "sourceMaterialBindings": materials,
            "nativeEnabledExpected": False}
    for row in plan.get("components", []):
        if row.get("type") != "cc.RichText" or row.get("node") not in root["sourceChildOrder"]:
            continue
        raw = _raw_component(manifest, component_origin(row["sourceId"]))
        planned_raw = row.get("sourceRichText")
        static = row.get("staticRichText") or {}
        if (not isinstance(raw, Mapping) or raw.get("__type__") != "cc.RichText" or
                not isinstance(planned_raw, Mapping) or
                json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")) !=
                json.dumps(planned_raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")) or
                not static.get("renderReady")):
            raise StaticSortQueueError(f"RichText lacks exact serialized text/font fields: {row.get('sourceId')}")
        fields_json = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        font_binding = static.get("fontBinding") or {}
        richtext_proofs[row["sourceId"]] = {
            "sourceFields": dict(raw), "sourceFieldsJson": fields_json,
            "sourceFieldsSha256": hashlib.sha256(fields_json.encode("utf-8")).hexdigest(),
            "sourceEnabled": row.get("enabled", True) is True,
            "sourceText": static.get("serializedSourceText", static.get("text", "")),
            "sourceTextEmpty": static.get("serializedSourceText", static.get("text", "")) == "",
            "sourceFontId": row.get("font"),
            "sourceFontMissing": not row.get("font"),
            "nativeFontAssetId": font_binding.get("nativeFontAssetId"),
            "nativeFallbackAssetIds": list(font_binding.get("nativeFallbackAssetIds", [])),
            "targetSystemFontFamily": font_binding.get("targetSystemFontFamily"),
            "creatorMarkup": static.get("creatorMarkup"), "renderReady": static.get("renderReady") is True,
        }
    source_nodes = {row.get("sourceId"): row for row in plan.get("nodes", []) if isinstance(row, Mapping)}

    def source_active_hierarchy(node_id):
        seen = set()
        cursor = node_id
        while cursor is not None:
            if cursor in seen:
                raise StaticSortQueueError("source node parent cycle while proving Creator non-draw renderer")
            seen.add(cursor)
            node = source_nodes.get(cursor)
            if not node or node.get("active") is not True:
                return False
            cursor = node.get("parent")
        return True

    creator_type_map = {"cc.Sprite": "Sprite", "cc.Label": "Label", "cc.RichText": "RichText",
                        "cc.Graphics": "Graphics", "sp.Skeleton": "Skeleton"}
    active_renderer_ids = {row.get("sourceComponentId") for row in root["unityRenderers"]}
    non_draw_renderers = []
    active_no_draw = {}
    def needs_creator_sprite_binding(component, raw, source_id):
        if component.get("type") != "cc.Sprite":
            return False, False, None, None
        needs_binding_declared = "needsSpriteBinding" in component
        needs_binding = component.get("needsSpriteBinding", False)
        if needs_binding_declared and type(needs_binding) is not bool:
            raise StaticSortQueueError(f"Creator Sprite lacks typed needsSpriteBinding policy: {source_id}")
        frame = raw.get("_spriteFrame")
        source_frame_bound = isinstance(frame, Mapping) and bool(frame.get("__uuid__"))
        if needs_binding and source_frame_bound:
            raise StaticSortQueueError(f"Creator Sprite source reference is nonempty but its native binding is unresolved: {source_id}")
        if not source_frame_bound and (not needs_binding_declared or not needs_binding):
            raise StaticSortQueueError(f"Creator Sprite null source frame conflicts with native binding policy: {source_id}")
        if needs_binding:
            if component.get("spriteFrame") is not None:
                raise StaticSortQueueError(f"Creator null-frame Sprite has a normalized frame binding: {source_id}")
            return True, needs_binding_declared, None, None
        frame_id = component.get("spriteFrame")
        candidates = creator_assets_by_id.get(frame_id, [])
        if not isinstance(frame_id, str) or len(candidates) != 1 or candidates[0].get("kind") != "sprite" or not candidates[0].get("uuid"):
            raise StaticSortQueueError(f"Creator Sprite source frame lacks an exact native asset mapping: {source_id}")
        return False, needs_binding_declared, frame_id, candidates[0]["uuid"]
    for component in plan.get("components", []):
        if (not isinstance(component, Mapping) or component.get("sourceId") not in active_renderer_ids or
                component.get("node") not in root["sourceChildOrder"]):
            continue
        source_id = component["sourceId"]
        source_type = component["type"]
        raw = _raw_component(manifest, component_origin(source_id))
        source_needs_sprite_binding, source_needs_sprite_binding_declared, source_sprite_frame_asset_id, native_sprite_image_uuid_expected = \
            needs_creator_sprite_binding(component, raw, source_id)
        reason = None
        if source_type == "cc.Graphics":
            reason = "empty-command-stream"
        elif source_type == "cc.Sprite":
            if source_needs_sprite_binding:
                reason = "null-sprite-frame"
        elif source_type == "cc.Label" and raw.get("_string", component.get("text", "")) == "":
            reason = "empty-text"
        elif source_type == "cc.RichText":
            static_text = component.get("staticRichText") or {}
            source_plain = static_text.get("plainText", static_text.get("serializedSourceText",
                static_text.get("text", component.get("text", ""))))
            if source_plain == "":
                reason = "empty-text"
        if reason is None:
            continue
        fields_json = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        sprite_frame = raw.get("_spriteFrame")
        static = component.get("staticRichText") or {}
        source_text = (static.get("serializedSourceText", static.get("text", "")) if source_type == "cc.RichText"
                       else raw.get("_string", component.get("text", "")) if source_type == "cc.Label" else None)
        static_control = component.get("staticControlBinding") or {}
        source_enabled = component.get("enabled", True) is True
        if source_type == "cc.Graphics":
            reason = "empty-command-stream"
        active_no_draw[source_id] = {"sourceId": source_id, "nativeId": component.get("nativeId"),
            "node": component["node"], "sourceType": source_type,
            "expectedNativeType": creator_type_map[source_type], "sourceEnabled": source_enabled,
            "sourceActive": source_active_hierarchy(component["node"]),
            "sourceFields": dict(raw), "sourceFieldsJson": fields_json,
            "sourceFieldsSha256": hashlib.sha256(fields_json.encode("utf-8")).hexdigest(),
            "sourceSpriteFrameUuid": sprite_frame.get("__uuid__") if isinstance(sprite_frame, Mapping) else None,
            "sourceTextureBound": bool(isinstance(sprite_frame, Mapping) and sprite_frame.get("__uuid__")),
            "sourceNeedsSpriteBinding": source_needs_sprite_binding,
            "sourceNeedsSpriteBindingDeclared": source_needs_sprite_binding_declared,
            "sourceSpriteFrameAssetId": source_sprite_frame_asset_id,
            "nativeSpriteImageUuidExpected": native_sprite_image_uuid_expected,
            "sourceText": source_text,
            "sourceTextEmpty": reason == "empty-text",
            "nativeTextExpectation": (static.get("creatorMarkup", source_text) if source_type == "cc.RichText" else
                                      source_text if source_type == "cc.Label" else None),
            "sourceFontId": component.get("font") if source_type in ("cc.Label", "cc.RichText") else None,
            "creatorMarkup": static.get("creatorMarkup") if source_type == "cc.RichText" else None,
            "nativeFontAssetId": (static.get("fontBinding") or {}).get("nativeFontAssetId") if source_type == "cc.RichText" else None,
            "nativeFallbackAssetIds": list((static.get("fontBinding") or {}).get("nativeFallbackAssetIds", []))
                if source_type == "cc.RichText" else [],
            "targetSystemFontFamily": (static.get("fontBinding") or {}).get("targetSystemFontFamily")
                if source_type == "cc.RichText" else None,
            **graphics_no_draw_proofs.get(source_id, {}),
            "noDrawReason": reason, "nativeEnabledExpected": False if source_type == "cc.Graphics" else
                source_enabled and not source_needs_sprite_binding if source_type == "cc.Sprite" else source_enabled}
    for component in plan.get("components", []):
        if (not isinstance(component, Mapping) or component.get("type") not in _RENDER_TYPES or
                component.get("node") not in root["sourceChildOrder"] or component.get("sourceId") in active_no_draw or
                component.get("sourceId") in active_renderer_ids):
            continue
        source_active = source_active_hierarchy(component["node"])
        source_enabled = component.get("enabled", True) is True
        if source_active and source_enabled:
            # An active source renderer must be represented by a draw event or
            # a dedicated static no-draw proof (e.g. cc.Graphics empty stream).
            if component.get("type") == "cc.Graphics":
                continue
            raise StaticSortQueueError(f"active source renderer was omitted from Creator draw events: {component['sourceId']}")
        raw = _raw_component(manifest, component_origin(component["sourceId"]))
        if raw.get("__type__") != component.get("type"):
            raise StaticSortQueueError(f"Creator non-draw source component type differs: {component['sourceId']}")
        source_needs_sprite_binding, source_needs_sprite_binding_declared, source_sprite_frame_asset_id, native_sprite_image_uuid_expected = \
            needs_creator_sprite_binding(component, raw, component["sourceId"])
        fields_json = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        sprite_frame = raw.get("_spriteFrame")
        sprite_frame_uuid = sprite_frame.get("__uuid__") if isinstance(sprite_frame, Mapping) else None
        static = component.get("staticRichText") or {}
        source_text = (static.get("serializedSourceText", static.get("text", "")) if component.get("type") == "cc.RichText"
                       else raw.get("_string", component.get("text", "")) if component.get("type") == "cc.Label" else None)
        font_binding = static.get("fontBinding") or {}
        no_draw_reason = "inactive-source" if not source_active else "disabled-source"
        non_draw_renderers.append({"sourceId": component["sourceId"], "nativeId": component.get("nativeId"),
            "node": component["node"], "sourceType": component["type"],
            "expectedNativeType": creator_type_map[component["type"]], "sourceEnabled": source_enabled,
            "sourceActive": source_active, "sourceFields": dict(raw), "sourceFieldsJson": fields_json,
            "sourceFieldsSha256": hashlib.sha256(fields_json.encode("utf-8")).hexdigest(),
            "sourceSpriteFrameUuid": sprite_frame_uuid,
            "sourceTextureBound": bool(sprite_frame_uuid),
            "sourceNeedsSpriteBinding": source_needs_sprite_binding,
            "sourceNeedsSpriteBindingDeclared": source_needs_sprite_binding_declared,
            "sourceSpriteFrameAssetId": source_sprite_frame_asset_id,
            "nativeSpriteImageUuidExpected": native_sprite_image_uuid_expected,
            "sourceText": source_text,
            "sourceTextEmpty": source_text == "" if component.get("type") in ("cc.Label", "cc.RichText") else False,
            "nativeTextExpectation": (static.get("creatorMarkup", source_text) if component.get("type") == "cc.RichText" else
                                      source_text if component.get("type") == "cc.Label" else None),
            "sourceFontId": component.get("font") if component.get("type") in ("cc.Label", "cc.RichText") else None,
            "creatorMarkup": static.get("creatorMarkup") if component.get("type") == "cc.RichText" else None,
            "nativeFontAssetId": font_binding.get("nativeFontAssetId") if component.get("type") == "cc.RichText" else None,
            "nativeFallbackAssetIds": list(font_binding.get("nativeFallbackAssetIds", []))
                if component.get("type") == "cc.RichText" else [],
            "targetSystemFontFamily": font_binding.get("targetSystemFontFamily")
                if component.get("type") == "cc.RichText" else None,
            "nativeEnabledExpected": False if component.get("type") == "cc.Graphics" else
                source_enabled and not source_needs_sprite_binding if component.get("type") == "cc.Sprite" else source_enabled,
            **graphics_no_draw_proofs.get(component["sourceId"], {}),
            "noDrawReason": no_draw_reason})
    # The Creator target project owns the persisted node layer/transform values;
    # runtime proxy creation captures those typed fields directly from native
    # Nodes. The frozen source manifest binds the node identities and source
    # child order in this DTO.
    filtered_source_ids = set(active_no_draw)
    source_original_events = [{"kind": kind, "node": node, "sourceComponentId": component_id}
                              for kind, node, component_id in root["sourceDrawEvents"]]
    draw_events = [{"kind": kind, "node": node, "sourceComponentId": component_id}
                   for kind, node, component_id in root["sourceDrawEvents"]
                   if not (kind == "renderer" and component_id in filtered_source_ids)]
    non_draw_rows = non_draw_renderers + list(active_no_draw.values())
    source_event_indices = {}
    for index, (kind, node, component_id) in enumerate(root["sourceDrawEvents"]):
        if kind == "renderer" and component_id:
            source_event_indices.setdefault(component_id, []).append(index)
    source_non_draw_mappings = []
    for row in non_draw_rows:
        indexes = source_event_indices.get(row.get("sourceId"), [])
        if len(indexes) > 1:
            raise StaticSortQueueError(f"source non-draw component occurs more than once in original queue: {row.get('sourceId')}")
        source_non_draw_mappings.append({"sourceComponentId": row.get("sourceId"), "node": row.get("node"),
            "disposition": "source-render-event" if indexes else "source-component-only",
            "sourceEventIndex": indexes[0] if indexes else None, "noDrawReason": row.get("noDrawReason")})
    return {"schemaVersion": 1, "rootScope": root_scope, "sourcePrefabId": prefab.get("sourceId"),
            "prefabPath": prefab.get("path"), "sourceRootName": prefab.get("nativeRootName"),
            "sourceManifestSha256": contract["sourceManifestSha256"],
            "sourceOriginalDrawEvents": source_original_events,
            "sourceDrawEvents": draw_events,
            "renderers": [{"node": row["node"], "sourceComponentId": row["sourceComponentId"],
                           "sourceType": row["sourceType"], "nativeSortingOrder": row["nativeSortingOrder"],
                           "sourceSortOrder": row["sourceSortOrder"],
                           **graphics_proofs.get(row["sourceComponentId"], {}),
                           **richtext_proofs.get(row["sourceComponentId"], {})} for row in root["unityRenderers"]
                          if row["sourceComponentId"] not in filtered_source_ids],
            "masks": [dict(row) for row in root["unityMasks"]], "proxyTree": root["unityProxyTree"],
            "sourceSortOrderFields": [{"sourceId": row["sourceId"], "nativeId": row["nativeId"],
                                        "node": row["node"], "sortOrder": row["sortOrder"], "enabled": row["enabled"]}
                                       for row in root["sortOrderFields"]],
            "sourceSortRoots": [{"sourceId": row["sourceId"], "nativeId": row["nativeId"],
                                  "node": row["node"], "enabled": row["enabled"]}
                                 for row in root["sortRootOccurrences"]],
            "nonDrawRenderers": non_draw_rows, "sourceNonDrawRenderers": source_non_draw_mappings,
            "sourceChildOrder": root["sourceChildOrder"], "sourceNodeActive": root["sourceNodeActive"],
            "sourceNodeIds": list(root["sourceChildOrder"]), "sourceLayerHiddenValue": 1 << 28,
            "creatorQueueMapped": root["creatorQueueMapped"], "creatorMode": root["creatorMode"]}
