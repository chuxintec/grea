"""Extract serialized custom-component fields without running source scripts.

The result is an evidence-preserving, static snapshot. It does not infer
declaration defaults or implement component behavior.
"""
from collections.abc import Mapping
import math
import re


_COMPONENT_ID = re.compile(
    r"^(?P<asset>[^#]+)#(?P<object>\d+(?:/_children/\d+)*)(?:/components/(?P<ordinal>\d+))?$"
)
_EXCLUDED = {
    "__type__", "node", "_enabled", "_id", "_objFlags", "_prefab", "_name",
    "_id_", "_objFlags_", "_prefab_", "_name_",
}


class StaticFieldError(ValueError):
    """Raised for malformed identities or cyclic serialized input."""


def _component_id(asset_id, node_index, ordinal=None):
    suffix = str(node_index) if ordinal is None else f"{node_index}/components/{ordinal}"
    return f"{asset_id}#{suffix}"


def _asset_uuid_index(manifest):
    index = {}
    assets={a.get('sourceId'):a for a in manifest.get('assets',[]) if isinstance(a,Mapping)}
    def destination(identity):
        seen=set()
        while identity in assets and assets[identity].get('kind')=='redirect':
            if identity in seen:return None
            seen.add(identity);identity=assets[identity].get('redirectTarget')
        return identity if identity in assets else None
    for asset in manifest.get("assets", []):
        if not isinstance(asset, Mapping):
            continue
        source_id = asset.get("sourceId")
        if not isinstance(source_id, str) or ":" not in source_id:
            continue
        bundle, uuid = source_id.split(":", 1)
        declared_bundle = asset.get("bundle", bundle)
        if declared_bundle != bundle:
            continue
        index.setdefault((bundle, uuid), []).append(destination(source_id))
    return index


def _resolve_uuid(uuid, bundle, uuid_index):
    # Cocos UUIDs are represented by the exact source-manifest UUID identity.
    # Try the owning bundle first; only use a global UUID match if unique.
    candidates = uuid_index.get((bundle, uuid), [])
    if not candidates:
        candidates = [sid for (candidate_bundle, candidate_uuid), ids in uuid_index.items()
                      if candidate_uuid == uuid for sid in ids]
        candidates=list(dict.fromkeys(candidates))
    return candidates[0] if len(candidates) == 1 else None


def extract_static_fields(manifest, ir):
    """Return serialized fields for non-engine components, preserving source IDs.

    ``manifest`` must contain source assets with ``document.instances`` and
    ``ir`` must contain normalized nodes/components. No source code is read.
    """
    if not isinstance(manifest, Mapping) or not isinstance(ir, Mapping):
        raise StaticFieldError("manifest and ir must be mappings")
    assets = manifest.get("assets", [])
    if not isinstance(assets, list):
        raise StaticFieldError("manifest.assets must be an array")
    asset_by_id = {}
    for asset in assets:
        if not isinstance(asset, Mapping):
            raise StaticFieldError("manifest.assets contains a non-object entry")
        sid = asset.get("sourceId")
        if not isinstance(sid, str) or not sid or "#" in sid or ":" not in sid:
            raise StaticFieldError(f"invalid manifest asset owner identity: {sid!r}")
        if sid in asset_by_id:
            raise StaticFieldError(f"duplicate asset identity: {sid}")
        asset_by_id[sid] = asset
    ir_nodes = ir.get("nodes", [])
    if not isinstance(ir_nodes, list):
        raise StaticFieldError("ir.nodes must be an array")
    nodes = {}
    for row in ir_nodes:
        if not isinstance(row, Mapping):
            raise StaticFieldError("ir.nodes contains a non-object entry")
        sid = row.get("sourceId")
        match = _COMPONENT_ID.fullmatch(sid) if isinstance(sid, str) else None
        if not match or match.group("ordinal") is not None:
            raise StaticFieldError(f"invalid IR node identity: {sid!r}")
        if sid in nodes:
            raise StaticFieldError(f"duplicate node identity: {sid}")
        nodes[sid] = row
    components = {}
    ir_components = ir.get("components", [])
    if not isinstance(ir_components, list):
        raise StaticFieldError("ir.components must be an array")
    for row in ir_components:
        if not isinstance(row, Mapping):
            raise StaticFieldError("ir.components contains a non-object entry")
        sid = row.get("sourceId")
        if not isinstance(sid, str) or not _COMPONENT_ID.fullmatch(sid):
            raise StaticFieldError(f"invalid IR component identity: {sid!r}")
        if not isinstance(row.get("type"), str) or not row["type"]:
            raise StaticFieldError(f"invalid IR sourceType at {sid}")
        node_id = row.get("node")
        if not isinstance(node_id, str) or node_id not in nodes:
            raise StaticFieldError(f"invalid or missing IR component node at {sid}: {node_id!r}")
        if sid in components:
            raise StaticFieldError(f"duplicate component identity: {sid}")
        components[sid] = row
    wanted_ids = {sid for sid, row in components.items()
                  if isinstance(row.get("type"), str) and not row["type"].startswith(("cc.", "sp."))}
    selected_assets = {sid.split("#", 1)[0] for sid in nodes}

    uuid_index = _asset_uuid_index(manifest)
    diagnostics = []
    records = []
    for asset_id, asset in asset_by_id.items():
        if asset_id not in selected_assets or asset.get("kind") not in {"cc.Prefab", "cc.SceneAsset"}:
            continue
        document = asset.get("document")
        objects = document.get("instances") if isinstance(document, Mapping) else None
        if not isinstance(objects, list):
            diagnostics.append({"code": "SOURCE_DOCUMENT_INVALID", "sourceId": asset_id,
                                "message": "Prefab/SceneAsset has no document.instances array"})
            continue
        bundle = asset.get("bundle", asset_id.split(":", 1)[0])
        discovered = {}
        for node_index, node_obj in enumerate(objects):
            if not isinstance(node_obj, Mapping) or node_obj.get("__type__") not in {"cc.Node", "cc.Scene"}:
                continue
            node_id = f"{asset_id}#{node_index}"
            refs = node_obj.get("_components", [])
            if not isinstance(refs, list):
                diagnostics.append({"code": "INVALID_COMPONENT_LIST", "sourceId": node_id,
                                    "message": "Node._components is not an array"})
                continue
            for ordinal, ref in enumerate(refs):
                target = None
                if isinstance(ref, Mapping) and isinstance(ref.get("__type__"), str):
                    target = ref
                    comp_id = _component_id(asset_id, node_index, ordinal)
                elif isinstance(ref, Mapping) and type(ref.get("__id__")) is int:
                    object_index = ref["__id__"]
                    if 0 <= object_index < len(objects) and isinstance(objects[object_index], Mapping):
                        target = objects[object_index]
                        comp_id = _component_id(asset_id, object_index)
                    else:
                        diagnostics.append({"code": "UNRESOLVED_COMPONENT_OBJECT", "sourceId": node_id,
                                            "message": f"component __id__ {object_index} is outside document.instances"})
                        continue
                else:
                    continue
                source_type = target.get("__type__")
                if isinstance(source_type, str) and not source_type.startswith(("cc.", "sp.")):
                    if not source_type:
                        raise StaticFieldError(f"empty source component type at {comp_id}")
                    if comp_id in discovered:
                        raise StaticFieldError(f"duplicate source component identity: {comp_id}")
                    discovered[comp_id] = (node_id, source_type, target)

        for comp_id, (node_id, source_type, source_obj) in discovered.items():
            ir_component = components.get(comp_id)
            if ir_component is None:
                diagnostics.append({"code": "IR_COMPONENT_MISSING", "sourceId": comp_id,
                                    "message": "serialized custom component in selected asset has no matching IR identity"})
                continue
            if node_id not in nodes or ir_component.get("node") != node_id:
                diagnostics.append({"code": "COMPONENT_NODE_IDENTITY_MISMATCH", "sourceId": comp_id,
                                    "message": "serialized component owner does not match the exact IR node identity"})
                wanted_ids.discard(comp_id)
                continue
            if ir_component.get("type") != source_type:
                diagnostics.append({"code": "COMPONENT_TYPE_MISMATCH", "sourceId": comp_id,
                                    "message": "IR component type differs from serialized source type"})
            wanted_ids.discard(comp_id)
            fields = []
            seen_field_names = set()
            for name, raw in source_obj.items():
                if name in _EXCLUDED:
                    continue
                if name in seen_field_names:
                    raise StaticFieldError(f"duplicate field identity {name!r} at {comp_id}")
                seen_field_names.add(name)
                kind, value = _encode(raw, asset_id, bundle, objects, uuid_index, nodes, components, diagnostics,
                                      f"{comp_id}.{name}", set())
                fields.append({"name": name, "kind": kind, "value": value})
            records.append({"sourceId": comp_id, "node": node_id, "sourceType": source_type,
                            "fields": fields, "behavior": "disabled",
                            "gaps": ["source_declaration_defaults_not_verified"]})

    for comp_id in sorted(wanted_ids):
        diagnostics.append({"code": "SOURCE_COMPONENT_MISSING", "sourceId": comp_id,
                            "message": "custom IR component has no matching serialized component identity"})

    records.sort(key=lambda row: row["sourceId"])
    return {"schemaVersion": 1, "components": records, "diagnostics": diagnostics,
            "assetRedirects":[{"sourceId":a['sourceId'],"target":a.get('redirectTarget')}for a in assets if a.get('kind')=='redirect']}


def _encode(value, owner_asset, bundle, objects, uuid_index, nodes, components, diagnostics, path, active):
    identity = id(value)
    if isinstance(value, (Mapping, list)):
        if identity in active:
            raise StaticFieldError(f"cyclic serialized value at {path}")
        active.add(identity)
    try:
        if value is None:
            return "null", None
        if type(value) is bool:
            return "bool", value
        if type(value) in (int, float):
            if type(value) is float and not math.isfinite(value):
                raise StaticFieldError(f"non-finite number at {path}")
            return "float", value
        if isinstance(value, str):
            return "string", value
        if isinstance(value, Mapping):
            if "__id__" in value:
                index = value.get("__id__")
                if set(value) != {"__id__"}:
                    raise StaticFieldError(f"object reference has extra fields at {path}")
                if type(index) is int and 0 <= index < len(objects) and isinstance(objects[index], Mapping):
                    target = objects[index]
                    target_type = target.get("__type__")
                    target_id = f"{owner_asset}#{index}"
                    if target_type in {"cc.Prefab", "cc.SceneAsset"}:
                        return "asset_ref", owner_asset
                    if target_type in {"cc.Node", "cc.Scene"}:
                        if target_id in nodes:
                            return "node_ref", target_id
                        return _unresolved(diagnostics, path, f"node target {target_id} is absent from IR", dict(value))
                    if target_id in components:
                        return "component_ref", target_id
                return _unresolved(diagnostics, path, f"invalid object-table reference {index!r}", dict(value))
            if "__uuid__" in value:
                if set(value) != {"__uuid__"}:
                    raise StaticFieldError(f"asset reference has extra fields at {path}")
                uuid = value.get("__uuid__")
                if isinstance(uuid, str):
                    resolved = _resolve_uuid(uuid, bundle, uuid_index)
                    if resolved:
                        return "asset_ref", resolved
                return _unresolved(diagnostics, path, f"UUID reference {uuid!r} is missing or ambiguous", dict(value))
            result = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise StaticFieldError(f"non-string object key at {path}")
                if key in result:
                    raise StaticFieldError(f"duplicate field identity {key!r} at {path}")
                child_kind, child_value = _encode(item, owner_asset, bundle, objects, uuid_index, nodes, components,
                                                  diagnostics, f"{path}.{key}", active)
                result[key] = {"kind": child_kind, "value": child_value}
            return "object", result
        if isinstance(value, list):
            result = []
            for index, item in enumerate(value):
                child_kind, child_value = _encode(item, owner_asset, bundle, objects, uuid_index, nodes, components,
                                                  diagnostics, f"{path}[{index}]", active)
                result.append({"kind": child_kind, "value": child_value})
            return "array", result
        raise StaticFieldError(f"unsupported serialized value {type(value).__name__} at {path}")
    finally:
        if isinstance(value, (Mapping, list)):
            active.remove(identity)


def _unresolved(diagnostics, path, message, raw_value):
    diagnostics.append({"code": "UNRESOLVED_REFERENCE", "sourceId": path, "message": message})
    return "unresolved_ref", raw_value
