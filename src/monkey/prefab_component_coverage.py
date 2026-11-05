"""Whole-source component disposition and static-evidence coverage.

The denominator is always the complete frozen ``plan.components`` list. This
module never uses ``convertible`` to remove source components from coverage.
Native, retained, disabled and unsupported representations remain distinct;
retention or a disabled carrier cannot prove static presentation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import re
import math
import struct
from .io import diagnostic


SCHEMA = "monkey-prefab-component-coverage/1"
_VISUAL_TYPES = {
    "cc.Sprite", "cc.Label", "cc.RichText", "cc.LabelOutline", "sp.Skeleton",
    "cc.Graphics", "cc.ParticleSystem", "cc.TiledMap",
}
_UNSUPPORTED_CODES = (
    "UNSUPPORTED", "HANDOFF", "NOT_SUPPORTED", "SOURCE_COMPONENT_PROFILE",
)
_UNITY_NATIVE_TYPES={
    'cc.Sprite':'UnityEngine.UI.Image','cc.Label':'TMPro.TextMeshProUGUI',
    'cc.RichText':'TMPro.TextMeshProUGUI','cc.LabelOutline':'TMPro.TextMeshProUGUI',
    'cc.Button':'UnityEngine.UI.Button','cc.Toggle':'UnityEngine.UI.Toggle',
    'cc.ToggleContainer':'UnityEngine.UI.ToggleGroup','cc.Widget':'NativeRectConstraints',
    'cc.Layout':'UnityEngine.UI.LayoutGroup','cc.ScrollView':'UnityEngine.UI.ScrollRect',
    'cc.Mask':'UnityEngine.UI.RectMask2D','cc.ProgressBar':'UnityEngine.UI.Slider',
    'cc.BlockInputEvents':'NativeInputBlocker','sp.Skeleton':'Spine.Unity.SkeletonGraphic',
}
_GUID = re.compile(r"^[0-9a-fA-F]{32}$")
_SIGNED64 = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
_PHYSICAL_INVENTORY_CONTRACT = "monkey-unity-node-physical-components/1"
_PHYSICAL_INVENTORY_PHASE = "persistent-saved-reopened-node"
_SPINE_RENDERER_OWNER_CONTRACT = "monkey-unity-saved-spine-renderer-owner/1"
_KNOWN_GRAPHICS = frozenset(("UnityEngine.UI.Image", "UnityEngine.UI.RawImage",
    "TMPro.TextMeshProUGUI", "TMPro.TMP_SubMeshUI", "Spine.Unity.SkeletonGraphic"))


def _rows(readback: dict, key: str) -> list[dict]:
    value = readback.get(key)
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _nested_rows(readback: dict, key: str) -> list[dict]:
    rows = list(_rows(readback, key))
    visited = {id(readback)}
    stack = []
    for container_key in ("sourcePrefabs", "prefabInstances", "candidatePrefabInstances", "instances"):
        stack.extend(_rows(readback, container_key))
    while stack:
        container = stack.pop()
        if id(container) in visited:
            continue
        visited.add(id(container))
        rows.extend(_rows(container, key))
        for container_key in ("sourcePrefabs", "prefabInstances", "candidatePrefabInstances", "instances"):
            stack.extend(_rows(container, container_key))
    return rows


def _component_role(row: dict) -> tuple[str, bool]:
    """Resolve roles from saved type/status/representation, then cross-check tags."""
    if row.get("coverageRoleConflicts"):
        return "role-mismatch", True
    is_static_carrier = (row.get("nativeType") == "NativeStaticSpineReference" or
                         row.get("representation") == "disabled-source-data-carrier")
    if is_static_carrier:
        is_retained_collection = row.get("_coverageCollectionRole") == "retained-carrier"
        natural = ("retained-carrier" if row.get("status") == "retained" or
                   is_retained_collection and row.get("status") in (
                       "verified", "saved_static_references_verified", "retained_source_identity_verified")
                   else "role-mismatch")
    elif row.get("_coverageCollectionRole") == "retained-carrier":
        natural = "retained-carrier"
    elif row.get("status") == "retained":
        natural = "retained-carrier"
    elif row.get("status") in ("native", "disabled") and row.get("nativeType") == "Spine.Unity.SkeletonGraphic":
        natural = "native-renderer"
    elif row.get("_coverageCollectionRole") == "disabled-component":
        natural = "disabled-component"
    elif row.get("status") == "disabled":
        natural = "disabled-component"
    elif row.get("status") == "native":
        natural = "native-component"
    elif row.get("status") == "unsupported":
        natural = "unsupported-component"
    elif row.get("status") == "missing":
        natural = "missing-component"
    else:
        natural = "native-component"
    explicit = row.get("coverageRole")
    if explicit is None:
        return natural, natural == "role-mismatch"
    allowed = {"retained-carrier", "native-renderer", "native-component", "disabled-component",
               "unsupported-component", "missing-component"}
    if explicit not in allowed or explicit != natural:
        return "role-mismatch", True
    if explicit == "native-renderer" and (row.get("nativeType") != "Spine.Unity.SkeletonGraphic" or
                                           row.get("representation") != "native-component"):
        return "role-mismatch", True
    if explicit == "retained-carrier" and row.get("status") not in (
            "retained", "verified", "saved_static_references_verified", "retained_source_identity_verified"):
        return "role-mismatch", True
    return explicit, False


def _component_observations(readback: dict, engine: str = "unity") -> list[dict]:
    """Collect role-bearing component rows, coalescing only cross-scope copies.

    Unity emits a top-level saved row and repeats that same row inside its
    owning sourcePrefab record. One exact copy across those scopes is one
    observation. Repetitions within a peer list, or the same sourceId with a
    different role/persistent identity, remain visible for ambiguity checks.
    """
    root_rows = []
    root_keys = ("components", "retainedComponents", "disabledComponents")
    for key in root_keys:
        collection_role = "retained-carrier" if key == "retainedComponents" else "disabled-component" if key == "disabledComponents" else None
        for row in _rows(readback, key):
            scoped = dict(row)
            if collection_role:
                scoped["_coverageCollectionRole"] = collection_role
            root_rows.append(("root", scoped))
    def identity_key(row):
        identity = _unity_persistent_identity(row) if engine == "unity" else _native_id(row)
        if isinstance(identity, dict):
            identity = (identity.get("guid"), identity.get("localFileId"))
        if identity is None:
            identity = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return (_identity(row), _component_role(row)[0], identity)

    root_matches = defaultdict(list)
    for index, (_, row) in enumerate(root_rows):
        root_matches[identity_key(row)].append(index)
    root_remaining = {key: list(indices) for key, indices in root_matches.items()}
    result = [dict(row) for _, row in root_rows]
    nested_rows = []
    visited = {id(readback)}
    stack = []
    for key in ("sourcePrefabs", "prefabInstances", "candidatePrefabInstances", "instances"):
        for index, item in enumerate(_rows(readback, key)):
            stack.append((item, f"{key}/{index}"))
    while stack:
        container, scope = stack.pop()
        if id(container) in visited:
            continue
        visited.add(id(container))
        for key in root_keys:
            collection_role = "retained-carrier" if key == "retainedComponents" else "disabled-component" if key == "disabledComponents" else None
            for row in _rows(container, key):
                scoped = dict(row)
                if collection_role:
                    scoped["_coverageCollectionRole"] = collection_role
                nested_rows.append((scope + "/" + key, scoped))
        for key in ("sourcePrefabs", "prefabInstances", "candidatePrefabInstances", "instances"):
            for index, item in enumerate(_rows(container, key)):
                stack.append((item, scope + "/" + key + "/" + str(index)))
    for _, row in nested_rows:
        key = identity_key(row)
        matches = root_remaining.get(key, [])
        if matches:
            root_index = matches.pop(0)
            existing = result[root_index]
            merged = dict(existing)
            conflicts = dict(merged.get("coverageRoleConflicts", {}))
            evidence_keys = {
                "sourceId", "sourceComponentId", "coverageRole", "status", "representation", "nativeType",
                "componentUuid", "guid", "localFileId", "sourceEnabled", "nativeEnabled", "disabledReason",
                "sourceIdentityVerified", "persistent", "verified", "fieldsVerified", "sourceVisible",
                "nativeStaticFieldsVerified", "sourceNodeId",
            }
            for field, value in row.items():
                if field not in merged:
                    merged[field] = value
                elif field in evidence_keys and merged[field] != value:
                    conflicts[field] = {"primary": merged[field], "otherScope": value}
            if conflicts:
                merged["coverageRoleConflicts"] = conflicts
            result[root_index] = merged
            continue
        result.append(dict(row))
    return result


_UNITY_IDENTITY_FIELDS = ("sourceId", "node", "type", "nativeType", "status", "representation",
                         "componentUuid", "guid", "localFileId", "sourceIdentityVerified",
                         "persistent", "sourceEnabled", "nativeEnabled", "sourceVisible",
                         "nativeSlotId", "disabledReason")


def _owner_index(prefabs):
    by_node = defaultdict(list)
    owner_counts = Counter(row.get("sourceId") for row in prefabs
                           if isinstance(row, dict) and isinstance(row.get("sourceId"), str))
    for prefab in prefabs:
        if not isinstance(prefab, dict) or not isinstance(prefab.get("sourceId"), str):
            continue
        nodes = prefab.get("nodes")
        if not isinstance(nodes, list):
            continue
        node_ids = {row.get("sourceId") if isinstance(row, dict) else row for row in nodes}
        for node_id in node_ids:
            by_node[node_id].append(prefab["sourceId"])
    return owner_counts, by_node


def _planned_owner(plan: dict, component: dict, index=None) -> tuple[str | None, str | None]:
    """Resolve one source component to one explicit plan Prefab owner.

    A node may occur in nested/template scopes. In that case the component's
    sourcePrefabId is required to disambiguate; list order and sourceId string
    parsing are never used to guess an owner.
    """
    source_id = component.get("sourceId")
    node_id = component.get("node")
    prefabs = plan.get("sourcePrefabs")
    if not isinstance(prefabs, list) or not isinstance(node_id, str) or not node_id:
        return None, "plan-source-prefab-or-component-node-missing"
    declared_owner = component.get("sourcePrefabId") or component.get("ownerPrefabId")
    owner_counts, by_node = index if index is not None else _owner_index(prefabs)
    owners = by_node.get(node_id, ())
    if declared_owner is not None:
        if (not isinstance(declared_owner, str) or declared_owner not in owners or
                owner_counts.get(declared_owner) != 1):
            return None, "declared-source-prefab-does-not-own-component-node"
        return declared_owner, None
    if len(owners) != 1:
        return None, "source-component-node-has-no-unique-owner-prefab"
    return owners[0], None


def _strict_unity_identity(row: dict) -> dict | None:
    """Require both Unity persistent identity representations to agree."""
    identity = _unity_persistent_identity(row)
    if identity is None or row.get("persistent") is not True or row.get("sourceIdentityVerified") is not True:
        return None
    guid = row.get("guid")
    local_id = _signed64(row.get("localFileId"))
    component_uuid = row.get("componentUuid")
    if (not isinstance(guid, str) or not _GUID.fullmatch(guid) or local_id is None or
            not isinstance(component_uuid, str) or ":" not in component_uuid):
        return None
    paired_guid, paired_local = component_uuid.rsplit(":", 1)
    if (not _GUID.fullmatch(paired_guid) or _signed64(paired_local) is None or
            identity != {"guid": guid.lower(), "localFileId": local_id} or
            paired_guid.lower() != guid.lower() or _signed64(paired_local) != local_id):
        return None
    return identity


def _owner_scoped_component_rows(container: dict) -> list[dict]:
    """Read only the physical component rows owned by this saved Prefab."""
    rows = []
    for key in ("components", "retainedComponents", "disabledComponents"):
        for row in _rows(container, key):
            value = dict(row)
            if key == "retainedComponents":
                value["_coverageCollectionRole"] = "retained-carrier"
            elif key == "disabledComponents":
                value["_coverageCollectionRole"] = "disabled-component"
            rows.append(value)
    return rows


def _unique_nodes_by_id(rows):
    result = {}
    for row in rows if isinstance(rows, list) else ():
        if isinstance(row, dict) and isinstance(row.get("sourceId"), str):
            sid = row["sourceId"]
            result[sid] = None if sid in result else row
    return result


def _unique_node_row(rows, node_id):
    if not isinstance(rows, list):
        return None
    found = [row for row in rows if isinstance(row, dict) and row.get("sourceId") == node_id]
    return found[0] if len(found) == 1 else None


def _spine_renderer_owner_sidecars(plan: dict, readback: dict) -> tuple[dict[tuple[str, str], list[dict]], list[dict], set[str]]:
    """Validate the independent saved-Spine renderer owner receipts."""
    fragment = readback.get("staticSpineRendering")
    if not isinstance(fragment, dict):
        return {}, [], set()
    diagnostics = []
    invalid = set()
    source_components = {row.get("sourceId"): row for row in plan.get("components", [])
                         if isinstance(row, dict) and isinstance(row.get("sourceId"), str)}
    rendering_fragment = plan.get("staticSpineRendering")
    rendering_specs = defaultdict(list)
    if isinstance(rendering_fragment, dict) and isinstance(rendering_fragment.get("components"), list):
        for spec in rendering_fragment["components"]:
            if isinstance(spec, dict) and isinstance(spec.get("sourceComponentId"), str):
                rendering_specs[spec["sourceComponentId"]].append(spec)
    node_map = {row.get("sourceId"): row for row in plan.get("nodes", [])
                if isinstance(row, dict) and isinstance(row.get("sourceId"), str)}
    rows = fragment.get("components")
    if rows is None:
        # Older envelopes carry only a summary source ID set. This is not an
        # owner identity receipt and cannot prove a native renderer role.
        return {}, diagnostics, invalid
    if not isinstance(rows, list):
        diagnostics.append(diagnostic("SPINE_RENDERER_OWNER_SIDECAR_INVALID", "readback/staticSpineRendering/components",
            "Saved Spine renderer owner detail must be a typed component list"))
        return {}, diagnostics, invalid
    result: dict[tuple[str, str], list[dict]] = defaultdict(list)
    reported_rows = fragment.get("sourceComponentIds")
    reported = set(reported_rows) if isinstance(reported_rows, list) and all(isinstance(sid, str) for sid in reported_rows) else set()
    eligible_ids = {spec.get("sourceComponentId") for spec_rows in rendering_specs.values() for spec in spec_rows
                    if spec.get("eligible") is True}
    sidecar_ids = [row.get("sourceComponentId") or row.get("sourceId") for row in rows if isinstance(row, dict)]
    if (fragment.get("status") != "verified" or not isinstance(reported_rows, list) or
            len(reported_rows) != len(reported) or len(sidecar_ids) != len(rows) or
            len(sidecar_ids) != len(set(sidecar_ids)) or set(sidecar_ids) != reported or
            reported != eligible_ids):
        diagnostics.append(diagnostic("SPINE_RENDERER_OWNER_SIDECAR_DENOMINATOR_INVALID", "readback/staticSpineRendering",
            "Saved Spine renderer owner sidecars, summary IDs, and frozen eligible component denominator differ"))
        invalid.update(sid for sid in reported | eligible_ids if isinstance(sid, str))
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            diagnostics.append(diagnostic("SPINE_RENDERER_OWNER_SIDECAR_INVALID", f"readback/staticSpineRendering/components/{index}",
                "Saved Spine renderer owner detail row is malformed"))
            continue
        sid = raw.get("sourceComponentId") or raw.get("sourceId")
        source = source_components.get(sid) if isinstance(sid, str) else None
        node_id = raw.get("sourceNodeId") or raw.get("node")
        expected_owner, owner_error = _planned_owner(plan, source) if isinstance(source, dict) else (None, "unknown-source-id")
        identity = _strict_unity_identity(raw)
        source_visible = _is_source_visible(source, node_map, plan.get("components")) if isinstance(source, dict) else None
        source_enabled = source.get("enabled") if isinstance(source, dict) else None
        source_specs = rendering_specs.get(sid, []) if isinstance(sid, str) else []
        render_spec = source_specs[0] if len(source_specs) == 1 else None
        visible = source_visible is True
        data_identity = _unity_persistent_identity({"guid": raw.get("dataAssetGuid"),
                                                     "localFileId": raw.get("dataAssetLocalFileId")})
        flags = ("verified", "rendererCreated", "persistent", "dataPersistent", "serializedFieldsVerified",
                 "poseVerified", "colorVerified", "materialReferencesVerified", "unitMappingVerified",
                 "sourceVisibleVerified")
        actual_visible = raw.get("sourceVisible")
        vertex_count, triangle_count = raw.get("meshVertexCount"), raw.get("meshTriangleCount")
        valid = bool(
            isinstance(source, dict) and source.get("type") == "sp.Skeleton" and owner_error is None and
            isinstance(render_spec, dict) and len(source_specs) == 1 and render_spec.get("eligible") is True and
            raw.get("contract") == _SPINE_RENDERER_OWNER_CONTRACT and raw.get("phase") == "saved-prefab-reopen" and
            raw.get("sourceId", sid) == sid and raw.get("sourcePrefabId") == expected_owner and
            render_spec.get("sourceComponentId") == sid and render_spec.get("sourcePrefabId") == expected_owner and
            render_spec.get("sourceNodeId") == source.get("node") and
            render_spec.get("sourceDataAssetId") == raw.get("sourceDataAssetId") and
            render_spec.get("sourceVisible") is source_visible and
            render_spec.get("sourceComponentEnabled") is source_enabled and
            node_id == source.get("node") and node_id == render_spec.get("sourceNodeId") and node_id in node_map and
            raw.get("nativeType") == "Spine.Unity.SkeletonGraphic" and raw.get("type", "sp.Skeleton") == "sp.Skeleton" and
            identity is not None and raw.get("sourceIdentityVerified") is True and
            raw.get("rendererGuid", identity["guid"] if identity else None) == (identity["guid"] if identity else None) and
            _signed64(raw.get("rendererLocalId", identity["localFileId"] if identity else None)) ==
                (identity["localFileId"] if identity else None) and
            raw.get("coverageRole") == "native-renderer" and raw.get("representation") == "native-component" and
            raw.get("status") in ("native", "disabled") and raw.get("sourceEnabled") is source_enabled and
            type(raw.get("nativeEnabled")) is bool and raw.get("nativeEnabled") is raw.get("rendererEnabled") and
            raw.get("rendererEnabled") is source_enabled and raw.get("nativeStaticFieldsVerified") is True and
            raw.get("sourceCodeExecuted") is False and
            all(raw.get(flag) is True for flag in flags) and
            raw.get("sourceVisible") is visible and raw.get("sourceVisibleVerified") is True and
            data_identity is not None and raw.get("dataPersistent") is True and
            isinstance(raw.get("sourceDataAssetId"), str) and bool(raw.get("sourceDataAssetId")) and
            type(vertex_count) is int and type(triangle_count) is int and vertex_count >= 0 and triangle_count >= 0 and
            (not visible or vertex_count > 0 and triangle_count > 0) and
            (sid in reported))
        if not valid:
            diagnostics.append(diagnostic("SPINE_RENDERER_OWNER_SIDECAR_INVALID", sid or f"readback/staticSpineRendering/components/{index}",
                "Saved Spine renderer sidecar does not prove exact source owner/node, persistent identity, fields and pose", sid if isinstance(sid, str) else None))
            if isinstance(sid, str):
                invalid.add(sid)
            continue
        normalized = dict(raw)
        normalized.update(sourceId=sid, node=node_id, type="sp.Skeleton", status=raw["status"],
            representation="native-component", nativeType="Spine.Unity.SkeletonGraphic",
            coverageRole="native-renderer", componentUuid=raw["componentUuid"],
            guid=identity["guid"], localFileId=identity["localFileId"], persistent=True,
            sourceIdentityVerified=True, sourceEnabled=source_enabled, nativeEnabled=raw["rendererEnabled"],
            sourceVisible=visible, nativeStaticFieldsVerified=True, _coverageOwnerSidecar=True)
        result[(expected_owner, sid)].append(normalized)
    for key, matches in result.items():
        if len(matches) != 1:
            diagnostics.append(diagnostic("SPINE_RENDERER_OWNER_SIDECAR_AMBIGUOUS", key[1],
                "Multiple saved Spine renderer owner rows claim the same source component", key[1]))
            invalid.add(key[1])
    return dict(result), diagnostics, invalid


def _strict_unity_component_join(plan: dict, readback: dict) -> tuple[list[dict], list[dict], set[str]]:
    """Join top-level and owner-local native rows without cross-scope repair.

    Unity's root component inventory is a derived aggregate. It is useful as a
    second observation, but cannot replace its sourcePrefab-owned component
    row, or vice versa. Only a one-to-one, field-consistent pair is returned as
    positive evidence.
    """
    diagnostics = []
    invalid_sources: set[str] = set()
    spine_sidecars, spine_diagnostics, spine_invalid = _spine_renderer_owner_sidecars(plan, readback)
    diagnostics.extend(spine_diagnostics)
    invalid_sources.update(spine_invalid)
    source_components = [row for row in plan.get("components", []) if isinstance(row, dict)]
    owner_index = _owner_index(plan.get("sourcePrefabs") or [])
    source_nodes_by_id = _unique_nodes_by_id(plan.get("nodes"))
    top_nodes_by_id = _unique_nodes_by_id(readback.get("nodes"))
    by_source: dict[str, list[dict]] = defaultdict(list)
    owners_by_source: dict[str, str] = {}
    for component in source_components:
        sid = _identity(component)
        if not sid:
            continue
        owner_id, owner_error = _planned_owner(plan, component, owner_index)
        if owner_error:
            diagnostics.append(diagnostic("COMPONENT_SOURCE_OWNER_UNRESOLVED", sid,
                "Cannot prove a unique sourcePrefab owner for the source component node: " + owner_error, sid))
            invalid_sources.add(sid)
        else:
            owners_by_source[sid] = owner_id
        by_source[sid].append(component)

    top_rows = _owner_scoped_component_rows(readback)
    top_by_source: dict[str, list[dict]] = defaultdict(list)
    for row in top_rows:
        sid = _identity(row)
        if sid:
            top_by_source[sid].append(row)
        else:
            diagnostics.append(diagnostic("COMPONENT_TARGET_ID_MISSING", "readback/components",
                "Top-level saved component row has no source component ID"))
    for sid in sorted(set(top_by_source) - set(by_source)):
        diagnostics.append(diagnostic("COMPONENT_UNKNOWN_TARGET_SOURCE_ID", sid,
            "Saved top-level target component ID is absent from the frozen source component denominator", sid))
        invalid_sources.add(sid)

    raw_prefabs = readback.get("sourcePrefabs")
    if not isinstance(raw_prefabs, list):
        diagnostics.append(diagnostic("COMPONENT_OWNER_READBACK_MISSING", "readback/sourcePrefabs",
            "Saved sourcePrefab owner details are required for Unity component identity joins"))
        raw_prefabs = []
    actual_owners: dict[str, list[dict]] = defaultdict(list)
    for prefab in raw_prefabs:
        if isinstance(prefab, dict) and isinstance(prefab.get("sourceId"), str):
            actual_owners[prefab["sourceId"]].append(prefab)
    for owner_id, rows in actual_owners.items():
        if len(rows) != 1:
            diagnostics.append(diagnostic("COMPONENT_OWNER_READBACK_AMBIGUOUS", owner_id,
                "Multiple saved sourcePrefab records have the same owner identity", owner_id))

    owner_rows: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for owner_id, prefabs in actual_owners.items():
        for prefab in prefabs:
            for row in _owner_scoped_component_rows(prefab):
                sid = _identity(row)
                if sid:
                    owner_rows[(owner_id, sid)].append(row)
                else:
                    diagnostics.append(diagnostic("COMPONENT_OWNER_ROW_ID_MISSING", owner_id + "/components",
                        "Owner-local component row has no source component ID", owner_id))

    for owner_id, sid in sorted(owner_rows):
        if sid not in by_source:
            diagnostics.append(diagnostic("COMPONENT_UNKNOWN_OWNER_SOURCE_ID", sid,
                "Owner-local target component ID is absent from the frozen source component denominator", sid))
            invalid_sources.add(sid)

    for (owner_id, sid), sidecar_rows in spine_sidecars.items():
        existing = owner_rows.get((owner_id, sid), [])
        renderer_rows = [row for row in existing if _component_role(row)[0] == "native-renderer"]
        if not renderer_rows:
            # The renderer sidecar is an independent saved-prefab owner proof;
            # it can supply only the Spine renderer role and only after its own
            # GUID/localFileID, node and static-pose contract passed above.
            owner_rows[(owner_id, sid)].extend(sidecar_rows)
        elif (len(renderer_rows) != 1 or len(sidecar_rows) != 1 or
              any(renderer_rows[0].get(field) != sidecar_rows[0].get(field)
                  for field in _UNITY_IDENTITY_FIELDS)):
            diagnostics.append(diagnostic("SPINE_RENDERER_OWNER_SIDECAR_IDENTITY_MISMATCH", sid,
                "Owner component row and independently saved renderer receipt disagree on physical identity", sid))
            invalid_sources.add(sid)

    joined = []
    for sid, source_rows in by_source.items():
        if len(source_rows) != 1:
            invalid_sources.add(sid)
            continue
        source = source_rows[0]
        owner_id = owners_by_source.get(sid)
        if owner_id is None:
            continue
        owner_prefabs = actual_owners.get(owner_id, [])
        if len(owner_prefabs) != 1:
            diagnostics.append(diagnostic("COMPONENT_OWNER_READBACK_MISSING", owner_id,
                "The unique planned sourcePrefab owner has no unique saved owner detail", sid))
            invalid_sources.add(sid)
            continue
        owner = owner_prefabs[0]
        planned_owner = next((row for row in plan.get("sourcePrefabs", [])
                              if isinstance(row, dict) and row.get("sourceId") == owner_id), None)
        if (not isinstance(planned_owner, dict) or
                planned_owner.get("path") is not None and owner.get("path") != planned_owner.get("path")):
            diagnostics.append(diagnostic("COMPONENT_OWNER_PREFAB_IDENTITY_MISMATCH", owner_id,
                "Saved owner Prefab source identity/path differs from the frozen source owner", sid))
            invalid_sources.add(sid)
            continue
        owner_node_ids = {row.get("sourceId") if isinstance(row, dict) else row
                          for row in owner.get("nodes", [])} if isinstance(owner.get("nodes"), list) else set()
        node_id = source.get("node")
        if node_id not in owner_node_ids:
            diagnostics.append(diagnostic("COMPONENT_OWNER_NODE_MISMATCH", sid,
                "Saved owner Prefab node inventory does not contain the source component's planned node", sid))
            invalid_sources.add(sid)
            continue
        source_node = source_nodes_by_id.get(node_id)
        top_node = top_nodes_by_id.get(node_id)
        owner_node = _unique_node_row(owner.get("nodes"), node_id)
        if source_node is None or top_node is None or owner_node is None:
            diagnostics.append(diagnostic("COMPONENT_NODE_IDENTITY_EVIDENCE_MISSING", sid,
                "Source, top-level saved, and owner-local node identity rows must each be unique", sid))
            invalid_sources.add(sid)
            continue
        source_active = source_node.get("active")
        if (type(source_active) is not bool or type(top_node.get("active")) is not bool or
                type(owner_node.get("active")) is not bool or
                top_node.get("active") is not source_active or owner_node.get("active") is not source_active or
                top_node.get("active") is not owner_node.get("active")):
            diagnostics.append(diagnostic("COMPONENT_NODE_ACTIVITY_MISMATCH", sid,
                "Top-level and owner-local saved node activity must match the frozen source node", sid))
            invalid_sources.add(sid)
            continue

        root_candidates = top_by_source.get(sid, [])
        owned_candidates = owner_rows.get((owner_id, sid), [])
        # The top inventory and owner detail are independent requirements.
        if not root_candidates:
            diagnostics.append(diagnostic("COMPONENT_TOP_LEVEL_MIRROR_MISSING", sid,
                "Derived top-level component inventory is missing the source component row", sid))
            invalid_sources.add(sid)
            continue
        if not owned_candidates:
            diagnostics.append(diagnostic("COMPONENT_OWNER_DETAIL_MISSING", sid,
                "Owning sourcePrefab component detail is missing; top-level summary cannot fill it", sid))
            invalid_sources.add(sid)
            continue

        root_by_role: dict[str, list[dict]] = defaultdict(list)
        owner_by_role: dict[str, list[dict]] = defaultdict(list)
        for row in root_candidates:
            role, mismatch = _component_role(row)
            if mismatch:
                diagnostics.append(diagnostic("COMPONENT_ROLE_MISMATCH", sid,
                    "Top-level target role disagrees with its saved native type/status/representation", sid))
                invalid_sources.add(sid)
            root_by_role[role].append(row)
        for row in owned_candidates:
            role, mismatch = _component_role(row)
            if mismatch:
                diagnostics.append(diagnostic("COMPONENT_ROLE_MISMATCH", sid,
                    "Owner-local target role disagrees with its saved native type/status/representation", sid))
                invalid_sources.add(sid)
            owner_by_role[role].append(row)
        if set(root_by_role) != set(owner_by_role):
            diagnostics.append(diagnostic("COMPONENT_OWNER_ROLE_SET_MISMATCH", sid,
                "Top-level and owner-local role inventories differ; unmatched roles remain unverified", sid))
            invalid_sources.add(sid)
        pending_joined = []
        for role in sorted(set(root_by_role) | set(owner_by_role)):
            role_ok = role != "role-mismatch"
            roots = root_by_role.get(role, [])
            owned = owner_by_role.get(role, [])
            if not roots or not owned:
                diagnostics.append(diagnostic("COMPONENT_OWNER_ROLE_DETAIL_MISSING" if roots else
                    "COMPONENT_TOP_LEVEL_ROLE_MIRROR_MISSING", sid,
                    "A role is present in only one source identity scope and cannot be used as positive evidence", sid))
                invalid_sources.add(sid)
                continue
            if len(roots) != 1 or len(owned) != 1:
                diagnostics.append(diagnostic("COMPONENT_OWNER_ROLE_AMBIGUOUS", sid,
                    "A source component role must have exactly one top-level and one owner-local row", sid))
                invalid_sources.add(sid)
                continue
            root, detail = roots[0], owned[0]
            for field in _UNITY_IDENTITY_FIELDS:
                if root.get(field) != detail.get(field):
                    diagnostics.append(diagnostic("COMPONENT_SCOPE_IDENTITY_MISMATCH", sid,
                        "Top-level and owner-local component rows disagree on " + field, sid))
                    invalid_sources.add(sid)
                    role_ok = False
            if root.get("node") != source.get("node") or detail.get("node") != source.get("node"):
                diagnostics.append(diagnostic("COMPONENT_OWNER_NODE_MISMATCH", sid,
                    "Native component node differs from the source component's owning node", sid))
                invalid_sources.add(sid)
                role_ok = False
            if root.get("type") != source.get("type") or detail.get("type") != source.get("type"):
                diagnostics.append(diagnostic("COMPONENT_SOURCE_TYPE_MISMATCH", sid,
                    "Native component source type differs from the frozen plan", sid))
                invalid_sources.add(sid)
                role_ok = False
            if root.get("sourceEnabled") is not source.get("enabled") or detail.get("sourceEnabled") is not source.get("enabled"):
                diagnostics.append(diagnostic("COMPONENT_SOURCE_ENABLED_MISMATCH", sid,
                    "Saved component source-enabled state differs from the frozen plan", sid))
                invalid_sources.add(sid)
                role_ok = False
            status = root.get("status")
            if status in ("native", "disabled", "retained", "verified", "saved_static_references_verified",
                          "retained_source_identity_verified"):
                root_identity = _strict_unity_identity(root)
                detail_identity = _strict_unity_identity(detail)
                if root_identity is None or detail_identity is None or root_identity != detail_identity:
                    diagnostics.append(diagnostic("COMPONENT_PERSISTENT_IDENTITY_INCOMPLETE", sid,
                        "Top-level and owner-local GUID/localFileID/componentUuid identity is absent or inconsistent", sid))
                    invalid_sources.add(sid)
                    role_ok = False
            elif status in ("unsupported", "missing"):
                if _unity_persistent_identity(root) != _unity_persistent_identity(detail):
                    diagnostics.append(diagnostic("COMPONENT_SCOPE_IDENTITY_MISMATCH", sid,
                        "Top-level and owner-local unsupported/missing identity fields differ", sid))
                    invalid_sources.add(sid)
                    role_ok = False
            else:
                diagnostics.append(diagnostic("COMPONENT_TARGET_STATUS_INVALID", sid,
                    "Saved component row has an unknown status", sid))
                invalid_sources.add(sid)
                role_ok = False
            if role in ("native-component", "native-renderer", "disabled-component"):
                source_component_enabled = source.get("enabled")
                expected_native_enabled = source_component_enabled
                if source.get("type") == "cc.LabelOutline":
                    owner_labels = _outline_owner_labels(source, source_components)
                    if len(owner_labels) != 1 or type(owner_labels[0].get("enabled")) is not bool:
                        diagnostics.append(diagnostic("COMPONENT_OUTLINE_OWNER_UNRESOLVED", sid,
                            "LabelOutline native enabled state requires exactly one same-node source Label", sid))
                        invalid_sources.add(sid)
                        role_ok = False
                    else:
                        expected_native_enabled = owner_labels[0]["enabled"]
                if type(source_component_enabled) is not bool:
                    diagnostics.append(diagnostic("COMPONENT_SOURCE_ENABLED_UNKNOWN", sid,
                        "Frozen source component enabled state is missing or malformed", sid))
                    invalid_sources.add(sid)
                    role_ok = False
                elif status == "native" and (expected_native_enabled is not True or
                                               root.get("nativeEnabled") is not True or
                                               detail.get("nativeEnabled") is not True):
                    diagnostics.append(diagnostic("COMPONENT_NATIVE_ENABLED_MISMATCH", sid,
                        "A native component's enabled flag must match its source role's owning-component state", sid))
                    if source_component_enabled is True and root.get("sourceVisible") is True:
                        diagnostics.append(diagnostic("VISIBLE_SOURCE_NATIVE_COMPONENT_DISABLED", sid,
                            "A visible source component cannot be reported rendered while its saved native component is disabled", sid))
                    invalid_sources.add(sid)
                    role_ok = False
                # Keep the independently saved disabled counterpart. Source-
                # empty sprites, business-safe controls and verified queue
                # drivers have explicit disabled routes below; unknown reasons
                # remain partial rather than erasing an observed component.
                elif status == "disabled" and (root.get("nativeEnabled") is not False or
                                                 detail.get("nativeEnabled") is not False):
                    diagnostics.append(diagnostic("COMPONENT_NATIVE_ENABLED_MISMATCH", sid,
                        "A disabled component must actually be disabled in both saved scopes; its source semantics are checked separately", sid))
                    invalid_sources.add(sid)
                    role_ok = False
            # Only exact owner-local evidence can enter the assessor. Top-level
            # summary remains an independent equality check, never a source of
            # missing owner fields.
            if role_ok:
                pending_joined.append(dict(detail))
        joined.extend(pending_joined)
    return joined, diagnostics, invalid_sources


def _strict_unity_scene_component_join(plan: dict, readback: dict, owner_rows: list[dict]) -> tuple[list[dict], list[dict], set[str]]:
    """Validate the independently saved Candidate scene component scope.

    The Candidate prefab and source Prefab are separate SaveAsPrefabAsset
    products. Their persistent Unity identities are intentionally different;
    this join compares source semantics and validates each identity in its own
    scope instead of equating GUID/localFileID across the two assets.
    """
    diagnostics: list[dict] = []
    invalid: set[str] = set()
    sources = [row for row in plan.get("components", []) if isinstance(row, dict)]
    source_by_id: dict[str, list[dict]] = defaultdict(list)
    for source in sources:
        sid = _identity(source)
        if sid:
            source_by_id[sid].append(source)
    rows = readback.get("sceneComponents")
    if (readback.get("sceneComponentContract") != "monkey-unity-saved-scene-components/1" or
            readback.get("sceneComponentPhase") != "saved-scene-reopened" or not isinstance(rows, list)):
        diagnostics.append(diagnostic("COMPONENT_SCENE_SCOPE_MISSING", "readback/sceneComponents",
            "An independently saved-scene component inventory with its contract and phase is required"))
        invalid.update(source_by_id)
        return [], diagnostics, invalid
    by_id: dict[str, list[dict]] = defaultdict(list)
    for index, row in enumerate(rows):
        sid = _identity(row) if isinstance(row, dict) else None
        if not sid:
            diagnostics.append(diagnostic("COMPONENT_SCENE_SOURCE_ID_MISSING", f"readback/sceneComponents/{index}",
                "Saved-scene component row has no stable source component ID"))
            continue
        by_id[sid].append(row)
    for sid in sorted(set(by_id) - set(source_by_id)):
        diagnostics.append(diagnostic("COMPONENT_UNKNOWN_SCENE_SOURCE_ID", sid,
            "Saved-scene component ID is absent from the frozen source denominator", sid))
        invalid.add(sid)
    owner_by_id: dict[str, list[dict]] = defaultdict(list)
    for row in owner_rows:
        sid = _identity(row)
        if sid:
            owner_by_id[sid].append(row)
    joined: list[dict] = []
    for sid, source_matches in source_by_id.items():
        if len(source_matches) != 1:
            diagnostics.append(diagnostic("COMPONENT_SOURCE_ID_AMBIGUOUS", sid,
                "Source component ID occurs more than once in the frozen plan", sid))
            invalid.add(sid)
            continue
        source = source_matches[0]
        actual = by_id.get(sid, [])
        if len(actual) != 1:
            code = "COMPONENT_SCENE_DETAIL_MISSING" if not actual else "COMPONENT_SCENE_DETAIL_AMBIGUOUS"
            diagnostics.append(diagnostic(code, sid,
                "Saved-scene scope must contain exactly one row for every frozen source component", sid))
            invalid.add(sid)
            continue
        row = actual[0]
        owner = owner_by_id.get(sid, [])
        if (row.get("observationScope") != "saved-scene-correspondence" or
                (_strict_unity_identity(row) is not None and
                 row.get("identityOrigin") != "corresponding-prefab-source")):
            diagnostics.append(diagnostic("COMPONENT_SCENE_OBSERVATION_SCOPE_INVALID", sid,
                "Scene component identity must come from the saved scene's observed prefab correspondence", sid))
            invalid.add(sid)
        if (_planned_owner(plan, source)[0] is None or row.get("node") != source.get("node") or
                row.get("type") != source.get("type")):
            diagnostics.append(diagnostic("COMPONENT_SCENE_SOURCE_MAPPING_MISMATCH", sid,
                "Saved-scene component must retain the exact planned source owner node and component type", sid))
            invalid.add(sid)
        role, mismatch = _component_role(row)
        if mismatch:
            diagnostics.append(diagnostic("COMPONENT_SCENE_ROLE_MISMATCH", sid,
                "Saved-scene component role disagrees with its observed status and representation", sid))
            invalid.add(sid)
        if row.get("sourceEnabled") is not source.get("enabled"):
            diagnostics.append(diagnostic("COMPONENT_SCENE_SOURCE_ENABLED_MISMATCH", sid,
                "Saved-scene source-enabled state differs from the frozen source component", sid))
            invalid.add(sid)
        if role in ("native-component", "native-renderer", "disabled-component", "retained-carrier"):
            if _strict_unity_identity(row) is None:
                diagnostics.append(diagnostic("COMPONENT_SCENE_PERSISTENT_IDENTITY_INCOMPLETE", sid,
                    "Saved-scene role lacks a consistent persistent GUID/localFileID/componentUuid identity", sid))
                invalid.add(sid)
        elif role in ("unsupported-component", "missing-component"):
            pass
        else:
            diagnostics.append(diagnostic("COMPONENT_SCENE_ROLE_INVALID", sid,
                "Saved-scene component has no recognized native disposition", sid))
            invalid.add(sid)
        matching_owner = [owner_row for owner_row in owner if _component_role(owner_row)[0] == role]
        if len(matching_owner) != 1:
            diagnostics.append(diagnostic("COMPONENT_SCENE_OWNER_JOIN_MISSING", sid,
                "Saved-scene component must match exactly one same-role observation in the independently saved source Prefab", sid))
            invalid.add(sid)
        else:
            owner_row = matching_owner[0]
            owner_role, owner_mismatch = _component_role(owner_row)
            semantic_fields = ("node", "type", "nativeType", "status", "representation", "sourceEnabled",
                               "nativeEnabled", "sourceVisible", "disabledReason", "nativeSlotId")
            if (owner_mismatch or role != owner_role or
                    any(row.get(field) != owner_row.get(field) for field in semantic_fields)):
                diagnostics.append(diagnostic("COMPONENT_SCENE_OWNER_ROLE_MISMATCH", sid,
                    "Saved-scene and owner-Prefab observations disagree on source mapping or native role/state", sid))
                invalid.add(sid)
        if row.get("status") in ("native", "disabled") and row.get("nativeStaticFieldsVerified") is not True:
            diagnostics.append(diagnostic("COMPONENT_SCENE_STATIC_FIELDS_UNVERIFIED", sid,
                "Saved-scene native or retained row does not independently verify its static fields", sid))
            invalid.add(sid)
        if not mismatch and row.get("node") == source.get("node") and row.get("type") == source.get("type"):
            joined.append(dict(row))
    return joined, diagnostics, invalid


def _observation_token(row: dict, engine: str) -> tuple:
    identity = _unity_persistent_identity(row) if engine == "unity" else _native_id(row)
    if isinstance(identity, dict):
        identity = (identity.get("guid"), identity.get("localFileId"))
    return (_identity(row), _component_role(row)[0], row.get("status"), row.get("representation"),
            _native_type(row), identity)


def _dedupe_exact_rows(rows: list[dict]) -> list[dict]:
    output = []
    seen = set()
    for row in rows:
        signature = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        if signature not in seen:
            seen.add(signature)
            output.append(row)
    return output


def _dedupe_component_observations(rows: list[dict], engine: str) -> list[dict]:
    """Merge repeated observations of one persistent component, not conflicts."""
    output=[];by_key={}
    for row in rows:
        sid=_identity(row)
        identity=_unity_persistent_identity(row) if engine=='unity' else _native_id(row)
        if not sid or not identity:
            signature=json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
            key=('raw',signature)
        else:
            identity_key=(identity.get('guid'),identity.get('localFileId')) if isinstance(identity,dict) else identity
            # These fields define semantic agreement. Verification annotations
            # may be added by normalization without making a duplicate.
            key=(sid,row.get('status'),row.get('representation'),_native_type(row),identity_key,
                 row.get('sourceEnabled'),row.get('nativeEnabled'),row.get('disabledReason'))
        if key not in by_key:
            merged=dict(row);by_key[key]=merged;output.append(merged)
        else:
            by_key[key].update(row)
    return output


def _identity(row: dict) -> str | None:
    value = row.get("sourceId") or row.get("sourceComponentId")
    return value if isinstance(value, str) and value else None


def _signed64(value) -> int | None:
    if type(value) is int:
        number = value
    elif isinstance(value, str) and _SIGNED64.fullmatch(value):
        try:
            number = int(value, 10)
        except ValueError:
            return None
    else:
        return None
    return number if -(1 << 63) <= number <= (1 << 63) - 1 and number != 0 else None


def _unity_persistent_identity(row: dict) -> dict | None:
    guid = row.get("guid") or row.get("persistedGuid")
    local = row.get("localFileId", row.get("persistedLocalFileId"))
    component_uuid = row.get("componentUuid")
    paired_guid = paired_local = None
    if isinstance(component_uuid, str) and ":" in component_uuid:
        paired_guid, paired_id = component_uuid.rsplit(":", 1)
        parsed_paired_id = _signed64(paired_id)
        if not _GUID.fullmatch(paired_guid) or parsed_paired_id is None:
            return None
        paired_local = parsed_paired_id
    if not isinstance(guid, str):
        guid = paired_guid
    if not _GUID.fullmatch(guid or ""):
        return None
    local_id = _signed64(local) if local is not None else paired_local
    if local_id is None or paired_guid is not None and (guid.lower() != paired_guid.lower() or local_id != paired_local):
        return None
    return {"guid": guid.lower(), "localFileId": local_id}


def _native_id(row: dict) -> str | None:
    identity = _unity_persistent_identity(row)
    if identity is not None:
        return identity["guid"] + ":" + str(identity["localFileId"])
    for key in ("componentUuid", "nativeComponentId", "nativeId"):
        value = row.get(key)
        if isinstance(value, str) and value.strip() and value.strip() != "0" and ":" not in value:
            return value.strip()
    return None


def _native_type(row: dict) -> str | None:
    for key in ("nativeType", "type", "componentType"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _native_identity_verified(row: dict, engine: str = "unity") -> bool:
    if row.get("sourceIdentityVerified", True) is not True:
        return False
    if engine == "unity":
        return row.get("persistent") is True and _unity_persistent_identity(row) is not None
    if row.get("persistent", True) is not True:
        return False
    return _native_id(row) is not None


def _source_diagnostics(plan: dict, readback: dict) -> tuple[list[dict], dict[str, list[dict]]]:
    grouped = {}
    for origin, key in (("source", "diagnostics"), ("source", "sourceDiagnostics"), ("native", "diagnostics"),
                        ("source-readback", "sourceDiagnostics")):
        owner = plan if origin == "source" else readback
        rows = owner.get(key)
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if isinstance(row, dict):
                value = dict(row)
            else:
                raw = str(row)
                code, separator, body = raw.partition(":")
                code = code.strip() if separator and code.strip() else "SOURCE_OR_NATIVE_DIAGNOSTIC_PASSTHROUGH"
                subject = body.strip().split(maxsplit=1)[0] if separator and body.strip() else None
                source_id = subject if isinstance(subject, str) and ":" in subject and "#" in subject else None
                location = source_id or f"{origin}/diagnostics"
                value = diagnostic(code, location, raw, source_id)
                value["rawDiagnostic"] = row
                if code == "COMPONENT_NOT_IMPORTED" and source_id:
                    value["phase"] = "initial-component-creation"
                    value["resolution"] = "pending-source-coverage-join"
            source_id = value.get("sourceId") or value.get("sourceComponentId")
            identity = source_id if isinstance(source_id, str) and source_id else None
            key_tuple = (identity, value.get("code"), value.get("location"), value.get("message"))
            evidence = {"origin": origin, "index": index,
                        "raw": row}
            if key_tuple not in grouped:
                entry = dict(value)
                entry["sourceEvidence"] = [evidence]
                entry["origins"] = [origin]
                grouped[key_tuple] = entry
            else:
                entry = grouped[key_tuple]
                entry["sourceEvidence"].append(evidence)
                if origin not in entry["origins"]:
                    entry["origins"].append(origin)
    all_rows = list(grouped.values())
    by_source: dict[str, list[dict]] = defaultdict(list)
    for row in all_rows:
        source_id = row.get("sourceId") or row.get("sourceComponentId")
        if isinstance(source_id, str) and source_id:
            by_source[source_id].append(row)
    return all_rows, by_source


def _static_field_rows(readback: dict) -> list[dict]:
    rows = _nested_rows(readback, "staticFieldBindings")
    flattened = []
    for row in rows:
        if isinstance(row.get("binding"), dict):
            binding = dict(row["binding"])
            binding.setdefault("sourceId", row.get("sourceComponentId"))
            flattened.append(binding)
        else:
            flattened.append(row)
    return flattened


def _valid_static_fields(component: dict, fields_by_id: dict[str, list[dict]]) -> tuple[bool, str]:
    spec = component.get("staticFieldBinding")
    if not isinstance(spec, dict):
        return True, "not_required"
    sid = component.get("sourceId")
    rows = fields_by_id.get(sid, [])
    if len(rows) != 1:
        return False, "missing_or_ambiguous_static_field_readback"
    row = rows[0]
    # Creator's real readback contract has both nativeIdentityVerified and
    # fieldsVerified. Unity callers normalize its independently read carrier
    # and field reference proof to these same explicit booleans.
    if row.get("nativeIdentityVerified") is not True or row.get("fieldsVerified") is not True:
        return False, "static_field_identity_or_fields_unverified"
    expected_fields = spec.get("fields")
    actual_fields = row.get("fields")
    if not isinstance(expected_fields, list) or not isinstance(actual_fields, list):
        return False, "static_field_rows_missing"
    expected_names = [field.get("sourceFieldName") or field.get("name") for field in expected_fields if isinstance(field, dict)]
    actual_names = [field.get("sourceFieldName") or field.get("name") for field in actual_fields if isinstance(field, dict)]
    if len(expected_names) != len(expected_fields) or len(actual_names) != len(actual_fields) or sorted(expected_names) != sorted(actual_names):
        return False, "static_field_denominator_differs"
    for field in actual_fields:
        is_array=field.get('storageType')=='UnityEngine.Object[]'or field.get('elementKind')in ('node_ref','component_ref','asset_ref')
        is_ref=field.get('storageType')=='UnityEngine.Object'or field.get('kind')in ('node_ref','component_ref','asset_ref')
        if (field.get('verified')is False or is_array and field.get('referencesVerified')is False
                or is_ref and not is_array and field.get('referenceVerified')is False):
            return False, "static_field_value_or_reference_unverified"
    return True, "verified"


def _native_fields_verified(component: dict, native_row: dict, fields_by_id: dict[str, list[dict]]) -> tuple[bool, str]:
    explicit = native_row.get("nativeStaticFieldsVerified")
    if type(explicit) is bool:
        return explicit, "verified_native_importer" if explicit else "native_importer_fields_unverified"
    return _valid_static_fields(component, fields_by_id)


def _valid_retention(row: dict, engine: str = "unity") -> bool:
    return (row.get("sourceIdentityVerified") is True
            and row.get("persistent", True) is True
            and _native_identity_verified(row, engine)
            and (row.get("verified") is True or row.get("fieldsVerified") is True)
            and isinstance(row.get("representation"), str) and bool(row["representation"])
            and row.get("status") in ("verified", "retained", "disabled", "native", "retained_source_identity_verified", "saved_static_references_verified"))


def _progress_number_matches(actual, expected, engine):
    if (type(actual)not in(int,float)or type(expected)not in(int,float)
            or not math.isfinite(actual)or not math.isfinite(expected)):
        return False
    if engine!='unity':return actual==expected
    # UnityStaticProgress stores these fields as System.Single. Compare the
    # exact declared representation, rather than a permissive epsilon.
    try:return struct.pack('!f',actual)==struct.pack('!f',expected)
    except (OverflowError,struct.error):return False


def _valid_progress_retention(component: dict, row: dict, engine: str) -> bool:
    """Join a disabled progress carrier to its exact source profile and bar sprite."""
    binding = component.get("staticProgressBinding")
    if not isinstance(binding, dict) or row.get("retentionEvidenceKind") != "static-progress-carrier-readback":
        return False
    expected_id = component.get("sourceId")
    if (row.get("sourceId") != expected_id or row.get("verified") is not True
            or row.get("carrierDisabled") is not True or row.get("nativeEnabled") is not False
            or row.get("barSpritePersistent") is not True
            or row.get("barSpriteSourceId") != binding.get("barSpriteSourceId")
            or not _native_identity_verified(row, engine)):
        return False
    # The producer proves a disabled static carrier. The source behavior and
    # referenced bar must still match the frozen source plan exactly.
    expected = {
        "sourceEnabled": binding.get("sourceEnabled"),
        "mode": binding.get("mode"),
        "progress": binding.get("progress"),
        "reverse": binding.get("reverse"),
    }
    for key,value in expected.items():
        actual=row.get(key)
        if key=='progress':
            if not _progress_number_matches(actual,value,engine):return False
        elif type(actual)is not type(value)or actual!=value:
            return False
    if 'totalLength'in binding:
        if not _progress_number_matches(row.get('totalLength'),binding['totalLength'],engine):return False
    return True


def _native_disabled_reason(component: dict, row: dict) -> str | None:
    source_enabled = row.get("sourceEnabled")
    native_enabled = row.get("nativeEnabled")
    if type(source_enabled) is not bool or native_enabled is not False:
        return None
    if type(component.get("enabled")) is bool and component["enabled"] != source_enabled:
        return None
    reason = row.get("disabledReason")
    if reason == "source-disabled":
        return reason if source_enabled is False else None
    if reason == "owning-label-disabled":
        # LabelOutline is a serialized style role on the Label's TMP component.
        # Its own enabled bit may be true while the shared physical TMP target
        # is disabled because the unique same-node Label owner is disabled.
        # Require the owner row and target identity; the reason string alone is
        # never evidence.
        return None
    if reason == "source-empty-sprite":
        empty_sprite=(component.get("type")=="cc.Sprite" and "spriteFrame" in component and
                      component.get("spriteFrame") in (None, "") and
                      row.get("nativeStaticFieldsVerified") is True and
                      _native_type(row)=="UnityEngine.UI.Image")
        return reason if empty_sprite else None
    button = component.get("staticButtonBinding")
    button_proof = (component.get("type") == "cc.Button" and isinstance(button, dict)
                    and button.get("behavior") == "disabled" and button.get("renderReady") is True
                    and button.get("sourceEnabled") is True and source_enabled is True)
    if reason == "static-button-business-safety":
        return "static-button-business-safety" if button_proof else None
    return None


def _outline_owner_labels(component: dict, source_components: list[dict] | None) -> list[dict]:
    if component.get("type") != "cc.LabelOutline" or not isinstance(source_components, list):
        return []
    node_id = component.get("node")
    return [row for row in source_components if isinstance(row, dict) and
            row.get("type") == "cc.Label" and row.get("node") == node_id]


def _outline_disabled_owner_is_proven(component: dict, row: dict,
                                       source_components: list[dict] | None,
                                       target_components: list[dict] | None) -> bool:
    if component.get("type") != "cc.LabelOutline" or component.get("enabled") is not True:
        return False
    owners = _outline_owner_labels(component, source_components)
    if len(owners) != 1 or owners[0].get("enabled") is not False:
        return False
    owner = owners[0]
    outline_identity = _strict_unity_identity(row)
    if outline_identity is None or not isinstance(target_components, list):
        return False
    owner_id = _identity(owner)
    owner_rows = [target for target in target_components if isinstance(target, dict) and
                  _identity(target) == owner_id and target.get("node") == component.get("node") and
                  target.get("nativeType") in ("TMPro.TextMeshProUGUI", "UnityEngine.UI.Text")]
    return (len(owner_rows) == 1 and _strict_unity_identity(owner_rows[0]) == outline_identity and
            owner_rows[0].get("nativeEnabled") is False and owner_rows[0].get("status") == "disabled" and
            row.get("nativeEnabled") is False and row.get("status") == "disabled")


def _valid_sort_driver_disabled(component: dict, row: dict, engine: str) -> bool:
    """Require the source-bound, independently verified static sort queue driver."""
    binding = component.get("staticSortContinuationBinding")
    source_id = component.get("sourceId")
    expected_type = component.get("nativeType")
    local_id = row.get("queueDriverLocalFileId", row.get("queueDriverFileId", row.get("queueDriverFileID")))
    guid = row.get("queueDriverGuid")
    if (engine != "unity" or not isinstance(binding, dict)
            or component.get('type')not in ('cc.SortRoot','cc.SortOrder')
            or type(component.get('enabled'))is not bool or row.get('sourceEnabled')is not component['enabled']
            or not isinstance(source_id, str) or not source_id
            or binding.get("sourceComponentId", binding.get("sourceId")) != source_id
            or binding.get("expectedMarkerType") != expected_type
            or not isinstance(expected_type, str) or not expected_type
            or row.get("nativeType") != expected_type
            or row.get("representation") != "native-component"
            or row.get("nativeSlotId") is not None
            or row.get("disabledReason") != "native-static-sort-driver"
            or row.get("nativeEnabled") is not False
            or row.get("nativeStaticFieldsVerified") is not True
            or row.get("queueProofVerified") is not True
            or row.get("queueDriverPersistent") is not True
            or not isinstance(guid, str) or not _GUID.fullmatch(guid)
            or _signed64(local_id) is None
            or not _native_identity_verified(row, engine)):
        return False
    # If the source binding pins the queue driver identity, require that exact
    # identity. Otherwise the independently verified readback identity remains
    # mandatory, but is not confused with the disabled marker's own identity.
    expected_guid = binding.get("queueDriverGuid")
    expected_local = binding.get("queueDriverLocalFileId", binding.get("queueDriverFileId", binding.get("queueDriverFileID")))
    if expected_guid is not None and expected_guid.lower() != guid.lower():
        return False
    if expected_local is not None and _signed64(expected_local) != _signed64(local_id):
        return False
    observed_binding = row.get("staticSortContinuationBinding")
    if observed_binding is not None and observed_binding != binding:
        return False
    return True


def _valid_layout_slot(component: dict, row: dict, engine: str) -> bool:
    binding = component.get("staticLayoutContinuationBinding")
    source_id = component.get("sourceId")
    return bool(engine == "unity" and isinstance(binding, dict)
        and component.get("type") in ("cc.Layout", "cc.Widget")
        and type(component.get('enabled'))is bool and row.get('sourceEnabled')is component['enabled']
        and binding.get("sourceComponentId") == source_id
        and binding.get("sourceNodeId") == component.get("node")
        and binding.get("physicalNativeType") == "NativeStaticLayoutCompletion"
        and component.get("nativeType") == "NativeStaticLayoutCompletion"
        and row.get("sourceId") == source_id
        and row.get("nativeSlotId") == source_id
        and row.get("representation") == "native-component-slot"
        and row.get("status") == "native"
        and row.get("nativeType") == "NativeStaticLayoutCompletion"
        and row.get("nativeStaticFieldsVerified") is True
        and _native_identity_verified(row, engine))


def _shared_native_identity_role(rows: list[dict], source_by_id: dict[str, list[dict]], engine: str) -> str | None:
    """Return an explicitly justified shared physical role, if one exists."""
    if len(rows) < 2:
        return None
    source_ids = {_identity(row) for row in rows}
    pairs = [(source_by_id.get(_identity(row), [None])[0], row)
             if len(source_by_id.get(_identity(row), [])) == 1 else (None, row) for row in rows]
    source_components = [component for component, _ in pairs]
    if any(not isinstance(component, dict) for component in source_components):
        return None
    # Several source layout/widget slots are intentionally stored by one
    # NativeStaticLayoutCompletion component. The slot ID and binding prove
    # each source component's own logical entry; GUID sharing alone is not
    # enough.
    if engine == "unity" and all(row.get("representation") == "native-component-slot" and
           _valid_layout_slot(component, row, engine)
           for component, row in pairs):
        slots = [row.get("nativeSlotId") for row in rows]
        if len(set(slots)) == len(slots) and set(slots) == source_ids:
            return "layout-slots"

    # A Cocos LabelOutline is a role on its owning Label's TMP component, not
    # a second text component. Permit only one source Label + one Outline on
    # the same planned node with the same exact target type, persistent ID,
    # and saved TMP enabled state. A disabled owner Label can also legitimately
    # make both logical roles share the disabled TMP identity.
    if (len(rows) == 2 and len(source_components) == 2 and
            {component.get("type") for component in source_components} == {"cc.Label", "cc.LabelOutline"} and
            source_components[0].get("node") == source_components[1].get("node") and
            all(row.get("nativeType") in ("TMPro.TextMeshProUGUI", "cc.Label", "cc.LabelOutline") and
                row.get("representation") == "native-component" and row.get("status") in ("native", "disabled")
                for row in rows) and len({row.get("nativeEnabled") for row in rows}) == 1):
        return "label-outline-role"
    return None


def _duplicate_physical_identities(rows: list[dict], source_by_id: dict[str, list[dict]], engine: str) -> tuple[set[str], list[dict]]:
    by_identity: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in rows:
        if engine == "unity":
            identity = _strict_unity_identity(row)
            key = (identity["guid"], identity["localFileId"]) if identity is not None else None
        else:
            native_id = _native_id(row)
            key = (native_id, 0) if native_id else None
        if key is not None:
            by_identity[key].append(row)
    invalid = set()
    diagnostics = []
    for identity, group in by_identity.items():
        source_ids = {_identity(row) for row in group}
        if len(group) <= 1:
            continue
        role = _shared_native_identity_role(group, source_by_id, engine)
        if role is None:
            invalid.update(sid for sid in source_ids if sid)
            diagnostics.append(diagnostic("COMPONENT_PHYSICAL_IDENTITY_ALIAS", f"{identity[0]}:{identity[1]}",
                "Distinct source component roles claim one physical component identity without a source-bound shared-role contract"))
    return invalid, diagnostics


def _is_physical_graphic(row: dict) -> bool:
    bases = row.get("nativeBaseTypes")
    return (row.get("nativeType") in _KNOWN_GRAPHICS or
            isinstance(bases, list) and "UnityEngine.UI.Graphic" in bases)


def _physical_inventory_key(row: dict):
    identity = _unity_persistent_identity(row)
    if (identity is None or row.get("persistent") is not True or
            not isinstance(row.get("guid"), str) or _signed64(row.get("localFileId")) is None or
            not isinstance(row.get("componentUuid"), str) or ":" not in row["componentUuid"]):
        return None
    guid, local = row["componentUuid"].rsplit(":", 1)
    if (not _GUID.fullmatch(guid) or guid.lower() != identity["guid"] or
            _signed64(local) != identity["localFileId"]):
        return None
    path = row.get("identityPath")
    valid_path = isinstance(path, list) and bool(path)
    if valid_path:
        for value in path:
            if not isinstance(value, str) or ":" not in value:
                valid_path = False
                break
            path_guid, path_local = value.rsplit(":", 1)
            if not _GUID.fullmatch(path_guid) or _signed64(path_local) is None:
                valid_path = False
                break
    if not valid_path or path[-1].lower() != row["componentUuid"].lower():
        return None
    if row.get("identityOrigin") not in ("direct-observation", "corresponding-prefab-source"):
        return None
    return identity["guid"], identity["localFileId"]


def _valid_mask_contract(plan):
    try:
        from .prefab_static_mask_continuation import validate_import_contract
        validate_import_contract(plan)
    except (ImportError, ValueError):
        return False
    return True


def _mask_fields_prove_auxiliary(plan: dict, readback: dict, source_id: str, mask_target: dict) -> bool:
    mask_rows = [row for row in _nested_rows(readback, "staticMaskFields") if _identity(row) == source_id]
    contract = plan.get("staticMasks")
    planned = [row for row in contract.get("masks", []) if isinstance(row, dict) and row.get("sourceId") == source_id]
    if len(mask_rows) != 1 or len(planned) != 1:
        return False
    actual, expected = mask_rows[0], planned[0]
    return (actual.get("sourceId") == source_id and actual.get("node") == expected.get("node") and
            actual.get("verified") is True and actual.get("persistentIdentityVerified") is True and
            actual.get("enabled") is expected.get("enabled") and actual.get("maskType") == expected.get("maskType") and
            actual.get("inverted") is expected.get("inverted") and actual.get("alphaThreshold") == expected.get("alphaThreshold") and
            actual.get("sourceFieldsJson") == expected.get("sourceFieldsJson") and
            isinstance(actual.get("persistentIdentityGuid"), str) and _GUID.fullmatch(actual["persistentIdentityGuid"]) and
            _signed64(actual.get("persistentIdentityLocalFileId")) is not None and
            actual.get("persistentIdentityLocalFileId") != 0 and
            actual.get("nativeType") == mask_target.get("nativeType") == "UnityEngine.UI.Mask")


def _validate_unity_physical_inventory(plan: dict, readback: dict, joined: list[dict],
                                       scene_joined: list[dict] | None = None) -> tuple[list[dict], set[str]]:
    """Check every saved physical Graphic identity on mapped source nodes.

    Older readbacks contain componentTypes strings only. That is a bounded
    check for known Unity Graphic classes; it cannot classify custom Graphic
    subclasses, so those rows remain explicitly unverified.
    """
    diagnostics = []
    invalid_sources = set()
    source_components = [row for row in plan.get("components", []) if isinstance(row, dict)]
    source_by_id = {row.get("sourceId"): row for row in source_components if isinstance(row.get("sourceId"), str)}
    plan_nodes = {row.get("sourceId"): row for row in plan.get("nodes", [])
                  if isinstance(row, dict) and isinstance(row.get("sourceId"), str)}
    owners = {row.get("sourceId"): row for row in plan.get("sourcePrefabs", [])
              if isinstance(row, dict) and isinstance(row.get("sourceId"), str)}
    actual_owners = {row.get("sourceId"): row for row in readback.get("sourcePrefabs", [])
                     if isinstance(row, dict) and isinstance(row.get("sourceId"), str)}
    owner_index = _owner_index(plan.get("sourcePrefabs") or [])
    top_nodes_by_id = _unique_nodes_by_id(readback.get("nodes"))
    mask_contract_valid = None
    joined_by_node = defaultdict(list)
    for row in joined:
        if row.get("node"):
            joined_by_node[row["node"]].append(row)
    scene_joined_by_node = defaultdict(list)
    for row in scene_joined or []:
        if row.get("node"):
            scene_joined_by_node[row["node"]].append(row)
    sources_by_node = defaultdict(list)
    for source in source_components:
        if isinstance(source.get("node"), str):
            sources_by_node[source["node"]].append(source)

    for node_id, node_sources in sources_by_node.items():
        if node_id not in plan_nodes:
            continue
        involved_ids = {row.get("sourceId") for row in node_sources if isinstance(row.get("sourceId"), str)}
        # Inventory is necessary to rule out extra Graphics whenever the node
        # has a planned visual component or a mapped physical Graphic.
        needs_graphic_inventory = any(row.get("type") in _VISUAL_TYPES or row.get("type") == "cc.Mask"
                                      for row in node_sources)
        if not needs_graphic_inventory:
            continue
        expected_owners = {_planned_owner(plan, row, owner_index)[0] for row in node_sources}
        expected_owners.discard(None)
        root_node = top_nodes_by_id.get(node_id)
        owner_nodes = []
        for owner_id in expected_owners:
            owner = actual_owners.get(owner_id)
            if isinstance(owner, dict):
                owner_node = _unique_node_row(owner.get("nodes"), node_id)
                if owner_node is not None:
                    owner_nodes.append(owner_node)
        if root_node is None or not owner_nodes:
            diagnostics.append(diagnostic("COMPONENT_PHYSICAL_INVENTORY_UNVERIFIED", node_id,
                "Saved node lacks an owner-bound physical component inventory; unknown Graphic subclasses cannot be ruled out", node_id))
            invalid_sources.update(involved_ids)
            continue
        if root_node.get("physicalObservationScope") not in ("saved-scene-correspondence", "saved-source-prefab"):
            diagnostics.append(diagnostic("COMPONENT_PHYSICAL_INVENTORY_SCOPE_INVALID", node_id,
                "Top-level physical inventory is not bound to a saved/reopened source scene or Prefab", node_id))
            invalid_sources.update(involved_ids)
        owner_inventory_maps = []
        for owner_node in owner_nodes:
            if owner_node.get("physicalObservationScope") != "saved-source-prefab":
                diagnostics.append(diagnostic("COMPONENT_PHYSICAL_OWNER_SCOPE_INVALID", node_id,
                    "Owner-local physical inventory must come from its saved sourcePrefab", node_id))
                invalid_sources.update(involved_ids)
        root_inventory = root_node.get("physicalComponents")
        if (root_node.get("physicalInventoryContract") != _PHYSICAL_INVENTORY_CONTRACT or
                root_node.get("physicalInventoryPhase") != _PHYSICAL_INVENTORY_PHASE or
                not isinstance(root_inventory, list)):
            diagnostics.append(diagnostic("COMPONENT_PHYSICAL_INVENTORY_UNVERIFIED", node_id,
                "Saved node has only a type-name inventory, not persistent physical component identities", node_id))
            invalid_sources.update(involved_ids)
            # Continue with the old bounded name inventory below, but do not
            # promote its result to complete physical identity coverage.
            actual_types = root_node.get("componentTypes")
            expected_type_identities = set()
            for row in joined_by_node.get(node_id, []):
                if (row.get("status") in ("native", "disabled") and
                        row.get("representation") in ("native-component", "native-component-slot")):
                    identity = _strict_unity_identity(row)
                    if identity is not None:
                        expected_type_identities.add((row.get("nativeType"), identity["guid"], identity["localFileId"]))
            expected_types = Counter(native_type for native_type, _, _ in expected_type_identities)
            if isinstance(actual_types, list):
                for native_type, count in expected_types.items():
                    if native_type in _KNOWN_GRAPHICS and actual_types.count(native_type) < count:
                        diagnostics.append(diagnostic("COMPONENT_PHYSICAL_GRAPHIC_TYPE_MISSING", node_id,
                            "Saved node type inventory lacks a mapped native Graphic class: " + str(native_type), node_id))
                        invalid_sources.update(involved_ids)
                for native_type in _KNOWN_GRAPHICS:
                    if actual_types.count(native_type) > expected_types.get(native_type, 0):
                        diagnostics.append(diagnostic("COMPONENT_UNOWNED_NATIVE_GRAPHIC", node_id,
                            "Saved node contains an extra Graphic type without a source component or verified auxiliary role: " + native_type, node_id))
                        invalid_sources.update(involved_ids)
            continue

        root_rows = [row for row in root_inventory if isinstance(row, dict)]
        for physical_row in root_rows:
            bases = physical_row.get("nativeBaseTypes")
            if (not isinstance(bases, list) or not bases or
                    any(not isinstance(value, str) or not value for value in bases) or
                    bases[0] != physical_row.get("nativeType")):
                diagnostics.append(diagnostic("COMPONENT_PHYSICAL_TYPE_CHAIN_INVALID", node_id,
                    "Physical component inventory lacks a complete native type/base-type chain", node_id))
                invalid_sources.update(involved_ids)
        root_types = root_node.get("componentTypes")
        inventory_types = [row.get("nativeType") for row in root_rows]
        if (not isinstance(root_types, list) or
                Counter(root_types) != Counter(inventory_types)):
            diagnostics.append(diagnostic("COMPONENT_PHYSICAL_TYPE_INVENTORY_MISMATCH", node_id,
                "Unity node componentTypes and persistent physical component inventory disagree", node_id))
            invalid_sources.update(involved_ids)
        root_by_key = defaultdict(list)
        for row in root_rows:
            key = _physical_inventory_key(row)
            if key is None:
                diagnostics.append(diagnostic("COMPONENT_PHYSICAL_IDENTITY_INVALID", node_id,
                    "Physical inventory row lacks a consistent persistent GUID/localFileID pair", node_id))
                invalid_sources.update(involved_ids)
                if _is_physical_graphic(row) and not (
                        row.get("role") == "engine-auxiliary" and
                        row.get("auxiliaryKind") == "mask-stencil-graphic"):
                    diagnostics.append(diagnostic("COMPONENT_UNOWNED_NATIVE_GRAPHIC", node_id,
                        "A Graphic row with invalid physical identity cannot be proven as an owned source renderer", node_id))
                continue
            root_by_key[key].append(row)
        if any(len(rows) != 1 for rows in root_by_key.values()):
            diagnostics.append(diagnostic("COMPONENT_PHYSICAL_IDENTITY_DUPLICATE", node_id,
                "A persisted physical component identity occurs more than once in one saved node inventory", node_id))
            invalid_sources.update(involved_ids)
        for owner_node in owner_nodes:
            if (owner_node.get("physicalInventoryContract") != _PHYSICAL_INVENTORY_CONTRACT or
                    owner_node.get("physicalInventoryPhase") != _PHYSICAL_INVENTORY_PHASE or
                    not isinstance(owner_node.get("physicalComponents"), list)):
                diagnostics.append(diagnostic("COMPONENT_PHYSICAL_OWNER_INVENTORY_MISSING", node_id,
                    "Owning sourcePrefab node does not contain the physical component inventory", node_id))
                invalid_sources.update(involved_ids)
                continue
            owner_rows = [row for row in owner_node["physicalComponents"] if isinstance(row, dict)]
            for physical_row in owner_rows:
                bases = physical_row.get("nativeBaseTypes")
                if (not isinstance(bases, list) or not bases or
                        any(not isinstance(value, str) or not value for value in bases) or
                        bases[0] != physical_row.get("nativeType")):
                    diagnostics.append(diagnostic("COMPONENT_PHYSICAL_TYPE_CHAIN_INVALID", node_id,
                        "Owner Prefab physical component inventory lacks a complete native type/base-type chain", node_id))
                    invalid_sources.update(involved_ids)
            owner_types = owner_node.get("componentTypes")
            if (not isinstance(owner_types, list) or
                    Counter(owner_types) != Counter(row.get("nativeType") for row in owner_rows)):
                diagnostics.append(diagnostic("COMPONENT_PHYSICAL_TYPE_INVENTORY_MISMATCH", node_id,
                    "Owner Prefab node componentTypes and physical component inventory disagree", node_id))
                invalid_sources.update(involved_ids)
            owner_by_key = defaultdict(list)
            for row in owner_rows:
                key = _physical_inventory_key(row)
                if key is not None:
                    owner_by_key[key].append(row)
                else:
                    diagnostics.append(diagnostic("COMPONENT_PHYSICAL_IDENTITY_INVALID", node_id,
                        "Owner Prefab physical component lacks a consistent persistent GUID/localFileID pair", node_id))
                    invalid_sources.update(involved_ids)
                    if _is_physical_graphic(row) and not (
                            row.get("role") == "engine-auxiliary" and
                            row.get("auxiliaryKind") == "mask-stencil-graphic"):
                        diagnostics.append(diagnostic("COMPONENT_UNOWNED_NATIVE_GRAPHIC", node_id,
                            "An owner Prefab Graphic with invalid physical identity cannot be proven as an owned source renderer", node_id))
            if any(len(rows) != 1 for rows in owner_by_key.values()):
                diagnostics.append(diagnostic("COMPONENT_PHYSICAL_IDENTITY_DUPLICATE", node_id,
                    "A persisted physical component identity occurs more than once in one source-Prefab inventory", node_id))
                invalid_sources.update(involved_ids)
            owner_inventory_maps.append(owner_by_key)

        # The Candidate scene and each source Prefab were saved independently.
        # Validate the component IDs against the physical inventory from their
        # own scope; the two persistent GUID/localFileID sets must not be
        # equated across those distinct assets.
        scopes = [("scene", root_by_key, scene_joined_by_node.get(node_id, []))]
        scopes.extend(("owner", owner_map, joined_by_node.get(node_id, []))
                      for owner_map in owner_inventory_maps)
        for scope_name, physical_by_key, node_joined in scopes:
            joined_identity_rows = defaultdict(list)
            for row in node_joined:
                identity = _strict_unity_identity(row)
                if identity is not None:
                    joined_identity_rows[(identity["guid"], identity["localFileId"])].append(row)
            for key, logical_rows in joined_identity_rows.items():
                physical_rows = physical_by_key.get(key, [])
                source_ids = sorted({_identity(row) for row in logical_rows if _identity(row)})
                if len(physical_rows) != 1:
                    diagnostics.append(diagnostic("COMPONENT_PHYSICAL_TARGET_NOT_IN_NODE_INVENTORY", node_id,
                        f"Joined {scope_name} component identity is absent or ambiguous in its own saved node inventory", node_id))
                    invalid_sources.update(source_ids)
                    continue
                physical_row = physical_rows[0]
                mapped_ids = physical_row.get("sourceComponentIds")
                sidecar_backed = (len(logical_rows) == 1 and logical_rows[0].get("_coverageOwnerSidecar") is True)
                logical_physical_state_matches = all(
                    row.get("nativeType") == physical_row.get("nativeType") and
                    row.get("nativeEnabled") is physical_row.get("enabled") and
                    (row.get("nativeBaseTypes") is None or row.get("nativeBaseTypes") == physical_row.get("nativeBaseTypes"))
                    for row in logical_rows)
                physical_role_matches = (
                    physical_row.get("role") in ("source-component", "source-components") and
                    isinstance(mapped_ids, list) and set(mapped_ids) == set(source_ids))
                if sidecar_backed:
                    sidecar_role_matches = (physical_row.get("role") == "unmapped" and mapped_ids == [])
                    physical_role_matches = physical_role_matches or sidecar_role_matches
                if (physical_row.get("role") not in ("source-component", "source-components") or
                        not physical_role_matches or
                        physical_row.get("nativeType") != logical_rows[0].get("nativeType") or
                        (logical_rows[0].get("nativeBaseTypes") is not None and
                         physical_row.get("nativeBaseTypes") != logical_rows[0].get("nativeBaseTypes")) or
                        physical_row.get("enabledKnown") is not True or
                        physical_row.get("enabled") is not logical_rows[0].get("nativeEnabled") or
                        not logical_physical_state_matches):
                    # A typed saved Spine renderer sidecar can identify one
                    # physically observed but source-ID-unmapped Graphic. It does
                    # not rewrite the producer's raw inventory role or source IDs.
                    if not (sidecar_backed and physical_role_matches and
                            physical_row.get("nativeType") == logical_rows[0].get("nativeType") and
                            physical_row.get("enabledKnown") is True and
                            physical_row.get("enabled") is logical_rows[0].get("nativeEnabled") and
                            logical_physical_state_matches):
                        diagnostics.append(diagnostic("COMPONENT_PHYSICAL_TARGET_ROLE_MISMATCH", node_id,
                            f"Physical {scope_name} inventory does not bind the exact source IDs, type and enabled state", node_id))
                        invalid_sources.update(source_ids)
                        continue

            for key, physical_rows in physical_by_key.items():
                physical = physical_rows[0]
                if not _is_physical_graphic(physical) or key in joined_identity_rows:
                    continue
                if physical.get("role") == "engine-auxiliary" and physical.get("auxiliaryKind") == "mask-stencil-graphic":
                    owner_uuid = physical.get("auxiliaryOwnerComponentUuid")
                    masks = [row for row in node_joined if source_by_id.get(_identity(row), {}).get("type") == "cc.Mask"
                             and row.get("componentUuid") == owner_uuid and row.get("nativeEnabled") is physical.get("enabled")]
                    if mask_contract_valid is None:
                        mask_contract_valid = _valid_mask_contract(plan)
                    if len(masks) == 1 and mask_contract_valid and _mask_fields_prove_auxiliary(plan, readback, _identity(masks[0]), masks[0]):
                        continue
                diagnostics.append(diagnostic("COMPONENT_UNOWNED_NATIVE_GRAPHIC", node_id,
                    f"A persisted {scope_name} Graphic has no exact source identity or verified scope-local auxiliary owner", node_id))
                invalid_sources.update(involved_ids)
    return diagnostics, invalid_sources


def _valid_native_disabled(component: dict, row: dict, engine: str,
                           source_components: list[dict] | None = None,
                           target_components: list[dict] | None = None) -> tuple[bool, str | None]:
    if row.get("status") != "disabled" or row.get("representation") != "native-component":
        return False, None
    if row.get("nativeEnabled") is not False:
        return False, None
    if not _native_identity_verified(row, engine):
        return False, None
    if row.get("disabledReason") == "native-static-sort-driver":
        expected = component.get("nativeType")
        if (expected is None or _native_type(row) != expected
                or not _valid_sort_driver_disabled(component, row, engine)):
            return False, None
        return True, "native-static-sort-driver"
    expected = component.get("nativeType") or component.get("type")
    if engine == "unity":
        expected = _UNITY_NATIVE_TYPES.get(expected, expected)
    same_type = (_native_type(row) == expected or engine == "unity" and isinstance(row.get("nativeBaseTypes"), list)
                 and expected in row["nativeBaseTypes"])
    reason = _native_disabled_reason(component, row)
    if row.get("disabledReason") == "owning-label-disabled":
        reason = ("owning-label-disabled" if _outline_disabled_owner_is_proven(
            component, row, source_components, target_components) else None)
    # Existence is independent from whether the source/native disablement
    # semantics have been proven. Preserve a real disabled counterpart with a
    # partial status when its reason is unknown or conflicts with the plan.
    return bool(same_type), reason


def _is_source_visible(component: dict, node_map: dict[str, dict],
                        source_components: list[dict] | None = None) -> bool | None:
    if component.get("type") not in _VISUAL_TYPES:
        return False
    if component.get("type") == "cc.Sprite":
        if "spriteFrame" not in component:
            return None
        if component.get("spriteFrame") in (None, ""):
            return False
    if component.get("type") == "cc.LabelOutline":
        owners = _outline_owner_labels(component, source_components)
        if len(owners) != 1 or type(owners[0].get("enabled")) is not bool:
            return None
        if owners[0].get("enabled") is False:
            return False
    if component.get("enabled") is False:
        return False
    node_id = component.get("node")
    if not isinstance(node_id, str) or node_id not in node_map:
        return None
    current = node_id
    seen = set()
    while current is not None:
        if current in seen:
            return None
        seen.add(current)
        node = node_map.get(current)
        if not isinstance(node, dict):
            return None
        if node.get("active") is False or type(node.get('opacity'))in(int,float)and node['opacity']<=0:
            return False
        current = node.get("parent")
    return True


def assess(plan: dict, readback: dict, engine: str) -> dict:
    """Assess every planned source component against explicit native evidence.

    ``readback.components`` uses actual editor rows (Creator's existing
    ``sourceId/type/componentUuid`` shape is accepted). Unity can pass a
    normalized row using the same keys. Optional explicit rows are
    ``retainedComponents``, ``disabledComponents``, ``staticFieldBindings``
    and ``staticPresentationValidation.components``. No field is inferred from
    ``convertible`` alone.
    """
    if not isinstance(plan, dict) or not isinstance(readback, dict) or engine not in ("unity", "creator"):
        raise ValueError("PREFAB_COMPONENT_COVERAGE_INPUT_INVALID")
    source_rows = plan.get("components")
    if not isinstance(source_rows, list):
        source_rows = []
    source_diagnostics, diagnostics_by_source = _source_diagnostics(plan, readback)
    diagnostics = list(source_diagnostics)
    creator_presentation_evidence = None
    creator_presentation_incomplete = False
    if engine == "creator":
        from .creator_presentation_evidence import validate_readback
        creator_presentation_evidence = validate_readback(plan, readback)
        creator_presentation_gaps = creator_presentation_evidence.get("gaps", [])
        creator_presentation_incomplete = bool(creator_presentation_gaps)
        for gap in creator_presentation_gaps:
            if isinstance(gap, dict):
                diagnostics.append(diagnostic(gap.get("code", "CREATOR_PRESENTATION_EVIDENCE_GAP"),
                    gap.get("sourceId") or "readback/staticPresentationValidation",
                    str(gap.get("reason") or gap.get("sourceIds") or "Creator saved presentation proof is incomplete"),
                    gap.get("sourceId")))
    readback_available = any(key in readback for key in (
        "components", "sourceComponentCoverage", "sourcePrefabs", "retainedComponents",
        "prefabInstances", "candidatePrefabInstances", "disabledComponents", "staticFieldBindings",
        "staticPresentationValidation", "staticSpineRendering", "staticProgressFields", "componentPeerDuplicates",
        "sceneComponents"))

    source_by_id: dict[str, list[dict]] = defaultdict(list)
    components = []
    for index, component in enumerate(source_rows):
        if not isinstance(component, dict):
            diagnostics.append(diagnostic("SOURCE_COMPONENT_ROW_INVALID", f"components/{index}", "Source component row is not an object"))
            components.append({"sourceIndex": index, "sourceId": None, "disposition": "missing",
                               "nativeStatus": "missing", "retentionStatus": "not_applicable",
                               "staticPresentationStatus": "not_applicable", "playerStatus": "not_run"})
            continue
        source_id = component.get("sourceId")
        if not isinstance(source_id, str) or not source_id:
            diagnostics.append(diagnostic("SOURCE_COMPONENT_ID_MISSING", f"components/{index}", "Source component has no stable sourceId"))
            components.append({"sourceIndex": index, "sourceId": source_id, "sourceType": component.get("type"),
                               "disposition": "missing", "nativeStatus": "missing", "retentionStatus": "not_applicable",
                               "staticPresentationStatus": "not_applicable", "playerStatus": "not_run"})
            continue
        source_by_id[source_id].append(component)

    identity_invalid_sources: set[str] = set()
    if engine == "unity":
        owner_observations, identity_diagnostics, identity_invalid_sources = _strict_unity_component_join(plan, readback)
        diagnostics.extend(identity_diagnostics)
        scene_observations, scene_diagnostics, scene_invalid = _strict_unity_scene_component_join(
            plan, readback, owner_observations)
        diagnostics.extend(scene_diagnostics)
        identity_invalid_sources.update(scene_invalid)
        component_observations = scene_observations if isinstance(readback.get("sceneComponents"), list) else owner_observations
        inventory_diagnostics, inventory_invalid_sources = _validate_unity_physical_inventory(plan, readback,
            owner_observations, scene_observations if isinstance(readback.get("sceneComponents"), list) else None)
        diagnostics.extend(inventory_diagnostics)
        identity_invalid_sources.update(inventory_invalid_sources)
        alias_sources, alias_diagnostics = _duplicate_physical_identities(component_observations,
            {sid: rows for sid, rows in source_by_id.items()}, engine)
        identity_invalid_sources.update(alias_sources)
        diagnostics.extend(alias_diagnostics)
        if alias_sources:
            component_observations = [row for row in component_observations if _identity(row) not in alias_sources]
    else:
        component_observations = _component_observations(readback, engine)
        alias_sources, alias_diagnostics = _duplicate_physical_identities(component_observations,
            {sid: rows for sid, rows in source_by_id.items()}, engine)
        identity_invalid_sources.update(alias_sources)
        diagnostics.extend(alias_diagnostics)
        if alias_sources:
            component_observations = [row for row in component_observations if _identity(row) not in alias_sources]
    native_rows = []
    retained_observations = []
    disabled_observations = []
    unsupported_observations = []
    missing_observations = []
    for row in component_observations:
        role, mismatch = _component_role(row)
        if row.get("coverageRoleConflicts"):
            diagnostics.append(diagnostic("COMPONENT_ROLE_OBSERVATION_CONFLICT", _identity(row) or "readback/components",
                "Top-level and prefab-local observations disagree on saved role or identity evidence", _identity(row)))
        if mismatch:
            diagnostics.append(diagnostic("COMPONENT_ROLE_MISMATCH", _identity(row) or "readback/components",
                "Explicit coverage role disagrees with the saved native type/status/representation", _identity(row)))
        if role == "retained-carrier":
            # Retention identity/data are owned by the source Prefab scope.
            # Scene rows establish an independent native/static scene role,
            # but cannot replace owner-local retained payload proof.
            if engine != "unity":
                retained_observations.append(row)
        elif role == "disabled-component" or row.get("status") == "disabled":
            disabled_observations.append(row)
        elif role == "unsupported-component":
            unsupported_observations.append(row)
        elif role == "missing-component":
            missing_observations.append(row)
        else:
            native_rows.append(row)
    if engine == "unity":
        for row in owner_observations:
            role, mismatch = _component_role(row)
            if role == "retained-carrier":
                retained_observations.append(row)
    component_tokens = {_observation_token(row, engine) for row in component_observations}
    for observation in _rows(readback, "sourceComponentCoverage"):
        sid = _identity(observation)
        actual = observation.get("nativeComponentReadback")
        actual_rows = [actual] if isinstance(actual, dict) else actual if isinstance(actual, list) else []
        for actual_row in actual_rows:
            if not isinstance(actual_row, dict):
                continue
            # This channel is another derived summary. It is not an
            # owner-local source and cannot repair an incomplete join.
            token = _observation_token(actual_row, engine)
            if token not in component_tokens:
                actual_sid = _identity(actual_row)
                diagnostics.append(diagnostic("COMPONENT_UNJOINED_NATIVE_COMPONENT_OBSERVATION",
                    actual_sid or "readback/sourceComponentCoverage",
                    "Derived sourceComponentCoverage row is not backed by a physical top-level component observation",
                    actual_sid))
                if actual_sid:
                    identity_invalid_sources.add(actual_sid)
                continue
            # A matching row is a duplicate projection of the physical row
            # already admitted above, not a second component observation.
            continue
    native_by_id: dict[str, list[dict]] = defaultdict(list)
    for row in native_rows:
        sid = _identity(row)
        if sid:
            native_by_id[sid].append(row)
    if engine == "creator":
        owner_claims = defaultdict(list)
        for owner in _rows(readback, "sourcePrefabs"):
            owned = owner.get("components")
            if not isinstance(owned, list):
                continue
            for item in owned:
                sid = item.get("sourceId") if isinstance(item, dict) else item
                if isinstance(sid, str):
                    owner_claims[sid].append(owner)
        for sid, source_list in source_by_id.items():
            source = source_list[0] if len(source_list) == 1 else None
            if not isinstance(source, dict):
                continue
            expected_owner, owner_error = _planned_owner(plan, source)
            actual = owner_claims.get(sid, [])
            if owner_error or len(actual) != 1 or actual[0].get("sourceId") != expected_owner:
                diagnostics.append(diagnostic("CREATOR_COMPONENT_OWNER_IDENTITY_INVALID", sid,
                    "Creator target component must join one frozen sourcePrefab owner by source ID", sid))
                identity_invalid_sources.add(sid)
                native_by_id[sid] = []
        unknown_native_ids = set(native_by_id) - set(source_by_id)
        for sid in sorted(unknown_native_ids):
            diagnostics.append(diagnostic("COMPONENT_UNKNOWN_TARGET_SOURCE_ID", sid,
                "Creator saved native component ID is absent from the frozen source denominator", sid))
            identity_invalid_sources.add(sid)
    retained_by_id: dict[str, list[dict]] = defaultdict(list)
    for row in retained_observations:
        sid = _identity(row)
        if sid:
            retained_by_id[sid].append(row)
    disabled_by_id: dict[str, list[dict]] = defaultdict(list)
    for row in disabled_observations:
        sid = _identity(row)
        if sid:
            disabled_by_id[sid].append(row)
    unsupported_by_id: dict[str, list[dict]] = defaultdict(list)
    for row in unsupported_observations:
        sid = _identity(row)
        if sid:
            unsupported_by_id[sid].append(row)
    missing_by_id: dict[str, list[dict]] = defaultdict(list)
    for row in missing_observations:
        sid = _identity(row)
        if sid:
            missing_by_id[sid].append(row)
    # Normalizers may have to coalesce cross-scope mirrors while retaining a
    # compact record of duplicates inside one peer collection. Feed those
    # records into the same role-specific ambiguity paths as raw duplicate
    # rows; never let normalization turn a duplicate into a pass.
    peer_duplicates = defaultdict(int)
    for item in _rows(readback, "componentPeerDuplicates"):
        sid = item.get("sourceId") or item.get("sourceComponentId")
        role = item.get("coverageRole")
        count = item.get("duplicateCount")
        identity = item.get("persistentIdentity")
        if (not isinstance(sid, str) or role not in ("native-renderer", "retained-carrier", "native-component",
                                                       "disabled-component", "unsupported-component", "missing-component")
                or type(count) is not int or count < 2):
            diagnostics.append(diagnostic("COMPONENT_PEER_DUPLICATE_RECORD_INVALID", "readback/componentPeerDuplicates",
                "Peer duplicate record is malformed and cannot be used as positive evidence", sid if isinstance(sid, str) else None))
            continue
        if engine == "unity" and identity is not None:
            if not isinstance(identity, dict) or _unity_persistent_identity(identity) is None:
                diagnostics.append(diagnostic("COMPONENT_PEER_DUPLICATE_RECORD_INVALID", sid,
                    "Peer duplicate persistent identity is malformed", sid))
                continue
        peer_duplicates[(sid, role)] += count - 1
    for (sid, role), extra_count in peer_duplicates.items():
        marker = {"sourceId": sid, "_peerDuplicate": True}
        if role in ("native-renderer", "native-component"):
            marker.update(status="native", representation="native-component",
                          nativeType="Spine.Unity.SkeletonGraphic" if role == "native-renderer" else None,
                          coverageRole=role)
            native_by_id[sid].extend(dict(marker) for _ in range(extra_count))
            diagnostics.append(diagnostic("NATIVE_COMPONENT_READBACK_AMBIGUOUS", sid,
                "Normalizer preserved duplicate native peer observations in componentPeerDuplicates", sid))
        elif role == "retained-carrier":
            marker.update(status="retained", representation="disabled-source-data-carrier",
                          nativeType="NativeStaticSpineReference", coverageRole=role)
            retained_by_id[sid].extend(dict(marker) for _ in range(extra_count))
            diagnostics.append(diagnostic("STATIC_RETENTION_READBACK_AMBIGUOUS", sid,
                "Normalizer preserved duplicate retained peer observations in componentPeerDuplicates", sid))
        elif role == "disabled-component":
            marker.update(status="disabled", representation="native-component", coverageRole=role)
            disabled_by_id[sid].extend(dict(marker) for _ in range(extra_count))
        elif role == "unsupported-component":
            marker.update(status="unsupported", representation="unsupported", coverageRole=role)
            unsupported_by_id[sid].extend(dict(marker) for _ in range(extra_count))
        else:
            marker.update(status="missing", representation="missing", coverageRole=role)
            missing_by_id[sid].extend(dict(marker) for _ in range(extra_count))
    static_fields_by_id: dict[str, list[dict]] = defaultdict(list)
    seen_field_readbacks = set()
    for row in _static_field_rows(readback):
        sid = _identity(row)
        if sid:
            signature = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
            if (sid, signature) in seen_field_readbacks:
                continue
            seen_field_readbacks.add((sid, signature))
            static_fields_by_id[sid].append(row)

    duplicate_source_ids = {sid for sid, rows in source_by_id.items() if len(rows) != 1}
    for sid in sorted(duplicate_source_ids):
        diagnostics.append(diagnostic("SOURCE_COMPONENT_ID_DUPLICATE", sid,
                                      "Source component ID occurs more than once in the full plan denominator", sid))

    visible_rows = {}
    presentation = readback.get("staticPresentationValidation")
    presentation_incomplete = (isinstance(presentation, dict) and presentation.get("status") in ("partial", "fail")) or creator_presentation_incomplete
    if presentation_incomplete:
        diagnostics.append(diagnostic("STATIC_PRESENTATION_NATIVE_INCOMPLETE", "readback/staticPresentationValidation",
                                      "Native presentation inventory reports incomplete source static semantics"))
    if isinstance(presentation, dict) and isinstance(presentation.get("components"), list):
        for row in presentation["components"]:
            if isinstance(row, dict) and isinstance(row.get("sourceId"), str):
                visible_rows.setdefault(row["sourceId"], []).append(row)
    for source_id in sorted(set(visible_rows) - set(source_by_id)):
        diagnostics.append(diagnostic("STATIC_PRESENTATION_UNKNOWN_SOURCE_ID", source_id,
            "Presentation evidence names a source component absent from the frozen source denominator", source_id))
        presentation_incomplete = True
    for source_id, rows in visible_rows.items():
        if len(rows) > 1:
            diagnostics.append(diagnostic("STATIC_PRESENTATION_SOURCE_ID_AMBIGUOUS", source_id,
                "Multiple presentation proof rows claim one source component", source_id))
            identity_invalid_sources.add(source_id)
            presentation_incomplete = True
    # A pinned static Spine continuation proves only disabled retained source
    # data. Its contract explicitly states non_rendering and cannot satisfy
    # visual/static presentation coverage.
    spine_fragment = plan.get("staticSpineContinuation")
    spine_ids = set()
    if isinstance(spine_fragment, dict):
        spine_ids = {row.get("sourceComponentId") for row in spine_fragment.get("components", [])
                     if isinstance(row, dict) and isinstance(row.get("sourceComponentId"), str)}
    spine_rendering = readback.get("staticSpineRendering")
    reported_spine_render_ids = set(spine_rendering.get("sourceComponentIds", [])) if (
        isinstance(spine_rendering, dict) and spine_rendering.get("status") == "verified" and
        isinstance(spine_rendering.get("sourceComponentIds"), list)) else set()
    unknown_spine_render_ids = reported_spine_render_ids - spine_ids
    if unknown_spine_render_ids:
        diagnostics.append(diagnostic("STATIC_SPINE_RENDERING_ID_UNKNOWN", "readback/staticSpineRendering",
            "Renderer readback contains source IDs absent from the pinned Spine continuation: " +
            ",".join(sorted(str(value) for value in unknown_spine_render_ids))))
        identity_invalid_sources.update(unknown_spine_render_ids)
    verified_spine_render_ids = reported_spine_render_ids & spine_ids

    retention_expected = set()
    retention_verified = set()
    presentation_expected = set()
    presentation_verified = set()
    node_map = {row.get("sourceId"): row for row in plan.get("nodes", [])
                if isinstance(row, dict) and isinstance(row.get("sourceId"), str)}
    spine_fragment = plan.get("staticSpineContinuation")
    if isinstance(spine_fragment, dict):
        retention_expected.update(row.get("sourceComponentId") for row in spine_fragment.get("components", [])
                                  if isinstance(row, dict) and isinstance(row.get("sourceComponentId"), str))
    for row in plan.get("staticComponentRetentions", []):
        if isinstance(row, dict):
            sid = row.get("sourceComponentId") or row.get("sourceId")
            if isinstance(sid, str) and sid:
                retention_expected.add(sid)
    for row in source_rows:
        # The pinned Unity producer creates UnityStaticProgress only for its
        # fallback profile. Native Slider+driver mappings retain their own
        # static values/references and undergo the native-field proof instead.
        if (isinstance(row, dict) and isinstance(row.get("staticProgressBinding"), dict)
                and not(engine=='unity' and row.get('convertible')is True)):
            sid = row.get("sourceId")
            if isinstance(sid, str) and sid:
                retention_expected.add(sid)
    for source_id, rows in source_by_id.items():
        if len(rows) != 1:
            components.append({"sourceId": source_id, "sourceType": None,
                               "disposition": "missing", "nativeStatus": "missing",
                               "retentionStatus": "not_applicable", "staticPresentationStatus": "not_run",
                               "sourceVisible": None, "sourceDiagnostics": diagnostics_by_source.get(source_id, []),
                               "playerStatus": "not_run"})
            continue
        component = rows[0]
        if not readback_available:
            components.append({"sourceId": source_id, "sourceType": component.get("type"),
                               "expectedNativeType": component.get("nativeType") or component.get("type"),
                               "disposition": "missing", "nativeStatus": "not_run",
                               "staticFieldStatus": "not_run", "retentionStatus": "not_run",
                               "staticPresentationStatus": "not_run", "sourceVisible": None,
                               "sourceDiagnostics": diagnostics_by_source.get(source_id, []),
                               "playerStatus": "not_run"})
            continue
        expected_type = component.get("nativeType") or component.get("type")
        if engine=='unity':expected_type=_UNITY_NATIVE_TYPES.get(expected_type,expected_type)
        candidates = native_by_id.get(source_id, [])
        explicit = candidates[0] if len(candidates) == 1 else None
        disabled_reason = None
        disabled_behavior_status = None
        valid_native = [row for row in candidates if _native_identity_verified(row,engine) and
                        (_valid_layout_slot(component,row,engine) if (
                            row.get("representation") == "native-component-slot" or
                            isinstance(component.get("staticLayoutContinuationBinding"), dict)) else
                         (_native_type(row) == expected_type or engine=='unity'and isinstance(row.get('nativeBaseTypes'),list)and expected_type in row['nativeBaseTypes']))
                        and row.get("status") not in ("retained", "disabled", "unsupported", "missing")]
        if len(candidates) == 1 and len(valid_native) == 1:
            disposition = "native"
            field_ok, field_status = _native_fields_verified(component, valid_native[0], static_fields_by_id)
            native_status = "pass" if field_ok else "partial"
            if source_id in identity_invalid_sources:
                native_status = "partial"
            if engine == "unity" and _is_source_visible(component, node_map, source_rows) is True and valid_native[0].get("nativeEnabled") is not True:
                native_status = "partial"
                diagnostics.append(diagnostic("VISIBLE_SOURCE_NATIVE_COMPONENT_DISABLED", source_id,
                    "A visible source component cannot be accepted with nativeEnabled=false", source_id))
            if not field_ok:
                diagnostics.append(diagnostic("NATIVE_STATIC_FIELD_READBACK_INCOMPLETE", source_id,
                                              "Native component exists but its planned static fields lack exact verified readback: " + field_status,
                                              source_id))
        else:
            field_status = "not_applicable"
            native_status = "missing"
            disposition = "missing"
            disabled_rows = _dedupe_component_observations(disabled_by_id.get(source_id, []),engine)
            if len(disabled_by_id.get(source_id, [])) > 1:
                diagnostics.append(diagnostic("NATIVE_DISABLED_READBACK_AMBIGUOUS", source_id,
                    "Multiple disabled native role observations share one sourceId", source_id))
            valid_disabled = ([] if len(disabled_by_id.get(source_id, [])) > 1 else
                [(row, reason) for row in disabled_rows
                 for valid, reason in [_valid_native_disabled(component, row, engine, source_rows,
                     [item for rows in native_by_id.values() for item in rows] +
                     [item for rows in disabled_by_id.values() for item in rows])] if valid])
            candidates_only_disabled = all(row.get("status") == "disabled" for row in candidates)
            if (len(valid_disabled) == 1 and len(disabled_rows) == 1 and
                    (not candidates or candidates_only_disabled)):
                disabled_row, disabled_reason = valid_disabled[0]
                disposition = "disabled"
                explicit = disabled_row
                field_ok, field_status = _native_fields_verified(component, disabled_row, static_fields_by_id)
                native_status = "pass" if field_ok and disabled_reason else "partial"
                disabled_behavior_status = ("disabled_for_business_safety_behavior_not_restored"
                                            if disabled_reason == "static-button-business-safety" else
                                            "source_disabled" if disabled_reason == "source-disabled" else
                                            "source_empty_sprite" if disabled_reason == "source-empty-sprite" else
                                            "unproven_disabled_behavior")
                if not disabled_reason:
                    diagnostics.append(diagnostic("NATIVE_DISABLED_REASON_UNPROVEN", source_id,
                        "A persistent disabled native counterpart exists, but its disablement reason does not match a proven source profile", source_id))
                if not field_ok:
                    diagnostics.append(diagnostic("NATIVE_DISABLED_FIELDS_UNVERIFIED", source_id,
                        "Disabled native component identity/state is preserved but source static fields are not independently verified", source_id))
            elif len(candidates) > 1:
                diagnostics.append(diagnostic("NATIVE_COMPONENT_READBACK_AMBIGUOUS", source_id,
                                              "Multiple native component rows share one sourceId", source_id))
            elif candidates:
                diagnostics.append(diagnostic("NATIVE_COMPONENT_IDENTITY_MISMATCH", source_id,
                                              "Native component type or persistent identity differs", source_id))
            if not valid_disabled:
                disposition = "missing"
                unsupported_rows = unsupported_by_id.get(source_id, [])
                missing_rows = missing_by_id.get(source_id, [])
                explicit = (candidates[0] if len(candidates) == 1 else
                            unsupported_rows[0] if len(unsupported_rows) == 1 else
                            missing_rows[0] if len(missing_rows) == 1 else None)
                if isinstance(explicit, dict) and explicit.get("status") == "unsupported":
                    disposition = "unsupported"
                elif isinstance(explicit, dict) and explicit.get("status") == "missing":
                    disposition = "missing"
                if len(unsupported_rows) > 1:
                    disposition = "unsupported"
                    native_status = "partial"
                    diagnostics.append(diagnostic("UNSUPPORTED_COMPONENT_READBACK_AMBIGUOUS", source_id,
                        "Multiple unsupported observations share one source component ID", source_id))
            retained = retained_by_id.get(source_id, [])
            retained_fields_ok,retained_fields_status=_valid_static_fields(component,static_fields_by_id)
            progress_retained = (len(retained) == 1 and
                                 _valid_progress_retention(component, retained[0], engine))
            if (disposition == "missing" and progress_retained):
                disposition = "retained"
                field_status = "verified_progress_carrier_and_bar_reference"
                native_status = "partial"
                retention_expected.add(source_id)
                retention_verified.add(source_id)
            elif (disposition == "missing" and source_id in spine_ids and len(retained) == 1
                    and _valid_retention(retained[0], engine)
                    and isinstance(readback.get("staticSpineContinuation"), dict)
                    and readback["staticSpineContinuation"].get("status") == "verified"
                    and source_id in readback["staticSpineContinuation"].get("sourceComponentIds", [])):
                disposition = "retained"
                native_status = "partial"
                retention_expected.add(source_id)
                retention_verified.add(source_id)
            elif (disposition == "missing" and len(retained) == 1
                    and retained[0].get("retentionEvidenceKind") != "static-progress-carrier-readback"
                    and _valid_retention(retained[0],engine) and retained_fields_ok):
                disposition = "retained"
                field_status=retained_fields_status
                native_status = "partial"
                retention_expected.add(source_id)
                retention_verified.add(source_id)
            elif disposition == "missing" and len(retained) > 1:
                diagnostics.append(diagnostic("STATIC_RETENTION_READBACK_AMBIGUOUS", source_id,
                                              "Multiple retained representations share one source component ID", source_id))
            if disposition == "missing":
                static_field_ok, static_field_status = _valid_static_fields(component, static_fields_by_id)
                if isinstance(component.get("staticFieldBinding"), dict) and static_field_ok:
                    disposition = "disabled"
                    native_status = "partial"
                    field_status = "verified"
                else:
                    field_status = static_field_status
                    disabled = disabled_by_id.get(source_id, [])
                if disposition == "missing" and len(disabled) == 1 and _valid_retention(disabled[0],engine):
                    disposition = "disabled"
                    native_status = "partial"
                elif disposition == "missing" and isinstance(explicit, dict) and explicit.get("status") == "disabled" and _valid_retention(explicit,engine):
                    disposition = "disabled"
                    native_status = "partial"
                elif disposition == "missing":
                    codes = [str(row.get("code", "")) for row in diagnostics_by_source.get(source_id, [])]
                    if component.get("convertible") is False and any(token in code for code in codes for token in _UNSUPPORTED_CODES):
                        disposition = "unsupported"
                    elif component.get("convertible") is False and not component.get("nativeType"):
                        disposition = "unsupported"
                    else:
                        disposition = "missing"
                    diagnostics.append(diagnostic("SOURCE_COMPONENT_WITHOUT_NATIVE_DISPOSITION", source_id,
                                                  "No exact native component or verified explicit retention/disabled representation exists; disposition=" + disposition,
                                                  source_id))
        if disposition == "retained":
            retention_expected.add(source_id)
        elif component.get("retainedOnly") is True or component.get("retentionPolicy"):
            retention_expected.add(source_id)

        # Verify retained source state independently even when a matching
        # native renderer/component also exists for the same source ID.
        retained_rows = retained_by_id.get(source_id, [])
        if len(retained_rows) > 1:
            diagnostics.append(diagnostic("STATIC_RETENTION_READBACK_AMBIGUOUS", source_id,
                "Multiple retained carrier role observations share one sourceId", source_id))
        if source_id in retention_expected and len(retained_rows) == 1:
            retained_row = retained_rows[0]
            if retained_row.get("retentionEvidenceKind") == "static-progress-carrier-readback":
                retention_valid = _valid_progress_retention(component, retained_row, engine)
            elif source_id in spine_ids:
                spine_result = readback.get("staticSpineContinuation")
                retention_valid = (_valid_retention(retained_row, engine) and
                    isinstance(spine_result, dict) and spine_result.get("status") == "verified" and
                    source_id in spine_result.get("sourceComponentIds", []))
            else:
                retention_valid = (_valid_retention(retained_row, engine) and
                                   _valid_static_fields(component, static_fields_by_id)[0])
            if retention_valid:
                retention_verified.add(source_id)

        visible = _is_source_visible(component, node_map, source_rows)
        if isinstance(explicit, dict) and type(explicit.get("sourceVisible")) is bool and visible is not None and explicit.get("sourceVisible") is not visible:
            diagnostics.append(diagnostic("COMPONENT_SOURCE_VISIBILITY_MISMATCH", source_id,
                "Saved native component visibility differs from the frozen source node/component state", source_id))
            identity_invalid_sources.add(source_id)
        if source_id in spine_ids and visible is True:
            presentation_expected.add(source_id)
            rendered_candidates = [row for row in native_by_id.get(source_id, [])
                if row.get("status") == "native" and _native_type(row) == "Spine.Unity.SkeletonGraphic"
                and _native_identity_verified(row, engine) and row.get("nativeEnabled") is True
                and row.get("nativeStaticFieldsVerified") is True]
            if source_id in verified_spine_render_ids and len(rendered_candidates) == 1 and disposition == "native":
                presentation_verified.add(source_id)
                presentation_status = "pass"
            else:
                diagnostics.append(diagnostic("SOURCE_VISIBLE_SPINE_NOT_RENDERED", source_id,
                    "Static Spine source remains non-rendering unless an exact sidecar-verified SkeletonGraphic row is joined", source_id))
                presentation_status = "partial"
        elif visible is not True:
            presentation_status = "not_applicable" if visible is False else "not_run"
        else:
            presentation_expected.add(source_id)
            evidence_rows = visible_rows.get(source_id, [])
            creator_proof = (creator_presentation_evidence.get("rowsById", {}).get(source_id)
                             if engine == "creator" and isinstance(creator_presentation_evidence, dict) else None)
            creator_presentation_ok = (engine != "creator" or isinstance(creator_proof, dict) and
                                        creator_proof.get("valid") is True and creator_proof.get("rendered") is True)
            if (creator_presentation_ok and len(evidence_rows) == 1 and evidence_rows[0].get("sourceVisible") is True
                    and evidence_rows[0].get("verified") is True and evidence_rows[0].get("rendered") is True
                    and disposition == "native"
                    and source_id not in identity_invalid_sources
                    and isinstance(explicit, dict)
                    and (engine != "unity" or (explicit.get("nativeEnabled") is True and
                                                explicit.get("status") == "native" and
                                                explicit.get("sourceVisible") is True))):
                presentation_verified.add(source_id)
                presentation_status = "pass"
            elif (engine == "creator" and isinstance(creator_proof, dict) and creator_proof.get("valid") is True
                  and creator_proof.get("sourceVisible") is False):
                presentation_status = "not_applicable"
            elif (engine == "unity" and len(evidence_rows) == 1 and evidence_rows[0].get("rendered") is True and
                  isinstance(explicit, dict) and explicit.get("nativeEnabled") is not True):
                presentation_status = "partial"
                identity_invalid_sources.add(source_id)
                diagnostics.append(diagnostic("RENDERED_PRESENTATION_WITH_DISABLED_NATIVE", source_id,
                    "Presentation evidence claims rendered while the joined native component is disabled", source_id))
            elif len(evidence_rows) == 1 and evidence_rows[0].get("sourceVisible") is False and evidence_rows[0].get("verified") is True:
                presentation_status = "not_applicable"
            else:
                presentation_status = "partial"
                diagnostics.append(diagnostic("STATIC_PRESENTATION_READBACK_INCOMPLETE", source_id,
                                              "Visible source component lacks exact native rendered presentation proof", source_id))
        components.append({
            "sourceId": source_id,
            "sourceType": component.get("type"),
            "expectedNativeType": expected_type,
            "disposition": disposition,
            "nativeStatus": native_status,
            "nativeComponentReadback": valid_native[0] if len(valid_native) == 1 else
                explicit if isinstance(explicit, dict) and explicit.get("representation") == "native-component" else None,
            "nativeSlotId": valid_native[0].get("nativeSlotId") if len(valid_native) == 1 else None,
            "staticLayoutContinuationBinding": dict(component["staticLayoutContinuationBinding"])
                if isinstance(component.get("staticLayoutContinuationBinding"), dict) else None,
            "retainedComponentReadback": retained_rows[0] if len(retained_rows) == 1 else None,
            "nativeStaticFieldsVerified": bool(disposition in ("native", "disabled") and native_status == "pass" and
                (not isinstance(explicit, dict) or explicit.get("nativeStaticFieldsVerified") is True or field_status == "verified")),
            "disabledReason": disabled_reason or (explicit.get("disabledReason") if isinstance(explicit, dict) else None),
            "sourceEnabled": explicit.get("sourceEnabled") if isinstance(explicit, dict) else None,
            "nativeEnabled": explicit.get("nativeEnabled") if isinstance(explicit, dict) else None,
            "sourceBehaviorStatus": disabled_behavior_status,
            "staticFieldStatus": field_status,
            "retentionStatus": "verified" if source_id in retention_verified else "retained_only" if disposition == "retained" else "not_applicable",
            "staticPresentationStatus": presentation_status,
            "sourceVisible": visible,
            "sourceDiagnostics": diagnostics_by_source.get(source_id, []),
            "playerStatus": "not_run",
        })

    coverage_by_source = {row.get("sourceId"): row for row in components if isinstance(row.get("sourceId"), str)}
    for item in diagnostics:
        if item.get("code") != "COMPONENT_NOT_IMPORTED":
            continue
        if not item.get("phase"):
            item["phase"] = "initial-component-creation"
        if item["phase"] != "initial-component-creation":
            item.setdefault("resolution", "unresolved-noninitial-phase")
            continue
        source_id = item.get("sourceId") or item.get("sourceComponentId")
        coverage_row = coverage_by_source.get(source_id)
        native_row = coverage_row.get("nativeComponentReadback") if isinstance(coverage_row, dict) else None
        identity = _unity_persistent_identity(native_row) if isinstance(native_row, dict) and engine == "unity" else None
        static_fields_verified = isinstance(coverage_row, dict) and coverage_row.get("nativeStaticFieldsVerified") is True
        native_representation = native_row.get("representation") if isinstance(native_row, dict) else None
        layout_binding = coverage_row.get("staticLayoutContinuationBinding") if isinstance(coverage_row, dict) else None
        layout_slot = (native_representation == "native-component-slot"
            and isinstance(layout_binding, dict)
            and layout_binding.get("sourceComponentId") == source_id
            and layout_binding.get("physicalNativeType") == "NativeStaticLayoutCompletion"
            and native_row.get("nativeSlotId") == source_id
            and native_row.get("nativeType") == "NativeStaticLayoutCompletion")
        resolved = (isinstance(coverage_row, dict) and coverage_row.get("nativeStatus") == "pass" and
                    coverage_row.get("disposition") in ("native", "disabled") and static_fields_verified and
                    isinstance(native_row, dict) and (native_row.get("representation") == "native-component" or layout_slot) and
                    native_row.get("sourceIdentityVerified") is True and identity is not None)
        item["resolved"] = bool(resolved)
        item["resolution"] = "native-counterpart-present" if resolved else "pending-or-unverified-native-counterpart"
        if resolved:
            item["resolutionEvidence"] = {"sourceId": source_id, "guid": identity["guid"],
                "localFileId": identity["localFileId"], "disposition": coverage_row["disposition"],
                "nativeStaticFieldsVerified": True, "representation": native_row["representation"],
                **({"nativeSlotId": source_id} if layout_slot else {})}

    # Keep malformed/duplicate source entries in original order as well as in
    # diagnostics; the report count always reflects the complete source list.
    ordered = []
    seen: Counter = Counter()
    for index, raw in enumerate(source_rows):
        sid = raw.get("sourceId") if isinstance(raw, dict) else None
        if isinstance(sid, str) and source_by_id.get(sid):
            if seen[sid] == 0:
                ordered.append(next(row for row in components if row.get("sourceId") == sid))
            seen[sid] += 1
            if seen[sid] > 1:
                ordered.append({"sourceIndex": index, "sourceId": sid, "sourceType": raw.get("type"),
                                "disposition": "missing", "nativeStatus": "missing", "retentionStatus": "not_applicable",
                                "staticPresentationStatus": "not_run", "playerStatus": "not_run"})
        else:
            ordered.append(next((row for row in components if row.get("sourceIndex") == index),
                                {"sourceIndex": index, "sourceId": sid, "sourceType": raw.get("type") if isinstance(raw, dict) else None,
                                 "disposition": "missing", "nativeStatus": "missing", "retentionStatus": "not_applicable",
                                 "staticPresentationStatus": "not_run", "playerStatus": "not_run"}))

    if not readback_available:
        for row in ordered:
            row["nativeStatus"] = "not_run"
            row["staticPresentationStatus"] = "not_run"

    expected_retained = set(retention_expected)
    retention_status = ("not_run" if not readback_available else "not_applicable" if not expected_retained
                        else "pass" if expected_retained <= retention_verified else "partial")
    for source_id in sorted(expected_retained - retention_verified) if readback_available else []:
        diagnostics.append(diagnostic("STATIC_RETENTION_READBACK_INCOMPLETE", source_id,
                                      "Declared retained representation lacks exact verified identity and fields/payload evidence", source_id))
    has_spine_unrendered = any(row.get("code") == "SOURCE_VISIBLE_SPINE_NOT_RENDERED" for row in diagnostics)
    if not readback_available:
        presentation_status = "not_run"
    elif not presentation_expected:
        presentation_status = "not_run"
    elif (presentation_expected <= presentation_verified and not has_spine_unrendered and
          not presentation_incomplete and not identity_invalid_sources):
        presentation_status = "pass"
    else:
        presentation_status = "partial"
    if not source_rows:
        native_status = "not_applicable"
    elif not readback_available:
        native_status = "not_run"
    elif any(row.get("disposition") in ("missing", "unsupported") for row in ordered):
        native_status = "fail"
    elif any(row.get("disposition") in ("retained", "disabled") or row.get("nativeStatus") != "pass" for row in ordered):
        native_status = "partial"
    else:
        native_status = "pass"
    if native_status == "pass" and identity_invalid_sources:
        native_status = "partial"
    return {
        "schema": SCHEMA,
        "engine": engine,
        "status": "not_run" if native_status == "not_run" else
                  "pass" if native_status == "pass" and presentation_status == "pass" else
                  "partial" if native_status in ("pass", "partial") else "fail",
        "sourceComponentCount": len(source_rows),
        "uniqueSourceComponentCount": len(source_by_id),
        "dispositionCounts": dict(Counter(row.get("disposition", "missing") for row in ordered)),
        "components": ordered,
        "sourceDiagnostics": source_diagnostics,
        "diagnostics": diagnostics,
        "nativeStaticValidation": native_status,
        "retentionValidation": retention_status,
        "staticPresentationValidation": {"status": presentation_status,
                                         "expectedSourceVisibleCount": len(presentation_expected),
                                         "verifiedSourceVisibleCount": len(presentation_verified),
                                         "diagnostics": [row for row in diagnostics if row.get("code", "").startswith("STATIC_PRESENTATION_") or row.get("code") == "SOURCE_VISIBLE_SPINE_NOT_RENDERED"]},
        "runtimeCheck": "not_run",
        "playerValidation": "not_run",
    }
