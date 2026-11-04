"""Bind Creator 2.4 auto-synced nested Prefabs into an already planned target graph.

This is an additive, pure post-planning pass. It never edits source evidence and
keeps the source template as an independent native Prefab. The returned plan is
ready for the existing native_relationships validator and target Prefab importers.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from .io import safe, read, load, sha


class SyncPrefabError(ValueError):
    """A source sync edge cannot be represented without guessing."""

    def __init__(self, code, where, detail):
        self.code, self.where, self.detail = code, where, detail
        super().__init__(f"{code} [{where}]: {detail}")


COCOS_24_PROFILES = frozenset(("cocos-2.4.15-bundle", "cocos-2.4.15-project"))


def needs_sync_prefab_binding(plan):
    """Empty resource-only plans have no source graph to bind or manifest to read."""
    return bool(plan.get("nodes") or plan.get("sourcePrefabs"))


def load_verified_source_manifest(path, expected_sha256, expected_profile):
    """Read and verify the manifest pinned by a Cocos 2.4 normalized IR."""
    if expected_profile not in COCOS_24_PROFILES:
        _fail("SYNC_PREFAB_PROFILE_UNSUPPORTED", str(path), "sync Prefab binding is limited to Cocos Creator 2.4.15")
    if not isinstance(path, (str, bytes, Path)) or not path:
        _fail("SYNC_PREFAB_MANIFEST_PIN", "$", "normalized IR has no sourceManifestPath")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        _fail("SYNC_PREFAB_MANIFEST_PIN", str(path), "normalized IR has no valid sourceManifestSha256")
    manifest_path = safe(path)
    raw = read(manifest_path)
    if sha(raw) != expected_sha256:
        _fail("SYNC_PREFAB_MANIFEST_HASH", str(manifest_path), "source manifest differs from the normalized IR pin")
    manifest = load(raw)
    if manifest.get("sourceProfile") != expected_profile:
        _fail("SYNC_PREFAB_MANIFEST_PROFILE", str(manifest_path), "manifest source profile differs from the normalized IR")
    return manifest


def _fail(code: str, where: str, detail: str) -> None:
    raise SyncPrefabError(code, where, detail)


def _stable_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _index_refs(value, instances):
    """Resolve a raw serialized reference without accepting ambiguous objects."""
    if isinstance(value, dict) and set(value) == {"__id__"} and type(value["__id__"]) is int:
        index = value["__id__"]
        if index < 0 or index >= len(instances):
            _fail("SYNC_PREFAB_REFERENCE", str(index), "serialized object reference is out of range")
        return index
    return None


def _extract_edges(manifest, included):
    assets = {item.get("sourceId"): item for item in manifest.get("assets", []) if item.get("sourceId")}
    by_uuid = {item.get("key"): item for item in assets.values() if item.get("key")}
    edges = defaultdict(list)
    for owner in sorted(included):
        asset = assets.get(owner)
        if not asset or asset.get("kind") != "cc.Prefab":
            continue
        document = asset.get("document") or {}
        objects = document.get("instances") or []
        if type(objects) is not list:
            _fail("SYNC_PREFAB_SOURCE", owner, "prefab document instances must be an array")
        for index, obj in enumerate(objects):
            if not isinstance(obj, dict) or obj.get("__type__") != "cc.Node":
                continue
            info = obj.get("_prefab")
            if not isinstance(info, dict) or info.get("sync") is not True:
                continue
            root_ref = _index_refs(info.get("root"), objects)
            if root_ref != index:
                _fail("SYNC_PREFAB_ROOT", f"{owner}#{index}", "sync PrefabInfo root must point to its owning node")
            allowed_info = {"__type__", "asset", "fileId", "root", "sync"}
            extras = sorted(set(info) - allowed_info)
            if extras:
                _fail("SYNC_PREFAB_OVERRIDE_UNSUPPORTED", f"{owner}#{index}", "unsupported PrefabInfo fields: " + ", ".join(extras))
            if info.get("__type__") not in (None, "cc.PrefabInfo"):
                _fail("SYNC_PREFAB_TYPE", f"{owner}#{index}", "expected cc.PrefabInfo")
            asset_ref = info.get("asset")
            if not isinstance(asset_ref, dict) or set(asset_ref) != {"__uuid__"} or not isinstance(asset_ref["__uuid__"], str):
                _fail("SYNC_PREFAB_TEMPLATE_MISSING", f"{owner}#{index}", "sync instance must name one UUID template")
            template = by_uuid.get(asset_ref["__uuid__"])
            if not template:
                _fail("SYNC_PREFAB_TEMPLATE_MISSING", f"{owner}#{index}", "template UUID is absent from the source manifest")
            file_id = info.get("fileId")
            if not isinstance(file_id, str) or not file_id:
                _fail("SYNC_PREFAB_FILE_ID", f"{owner}#{index}", "sync instance requires a nonempty fileId")
            allowed_node = {"__type__", "_name", "_parent", "_prefab", "_trs", "_active", "_objFlags", "_id", "__editorExtras__"}
            extras = sorted(set(obj) - allowed_node)
            if extras:
                _fail("SYNC_PREFAB_OVERRIDE_UNSUPPORTED", f"{owner}#{index}", "root carries fields outside the supported sync override surface: " + ", ".join(extras))
            parent = _index_refs(obj.get("_parent"), objects)
            if "_name" in obj and not isinstance(obj["_name"], str):
                _fail("SYNC_PREFAB_OVERRIDE_UNSUPPORTED", f"{owner}#{index}", "root _name must be a string")
            if "_active" in obj and type(obj["_active"]) is not bool:
                _fail("SYNC_PREFAB_OVERRIDE_UNSUPPORTED", f"{owner}#{index}", "root _active must be boolean")
            if "_trs" in obj:
                trs = obj["_trs"]
                if (not isinstance(trs, list) or len(trs) != 10 or
                        any(type(value) not in (int, float) or not math.isfinite(value) for value in trs)):
                    _fail("SYNC_PREFAB_OVERRIDE_UNSUPPORTED", f"{owner}#{index}", "root _trs must contain ten finite numeric values")
            edges[owner].append({
                "owner": owner,
                "root": f"{owner}#{index}",
                "template": template["sourceId"],
                "templateUuid": asset_ref["__uuid__"],
                "fileId": file_id,
                "rawRootIndex": index,
                "rawParentIndex": parent,
                "rootOverrides": {key: copy.deepcopy(obj[key]) for key in ("_name", "_active", "_trs") if key in obj},
                "sourceDocumentSha256": hashlib.sha256(_stable_json(document)).hexdigest(),
            })
    return assets, edges


def _replace_exact(value, mapping):
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [_replace_exact(item, mapping) for item in value]
    if isinstance(value, dict):
        return {key: _replace_exact(item, mapping) for key, item in value.items()}
    return value


def _remap_static_binding(value, mapping):
    if isinstance(value, list):
        return [_remap_static_binding(item, mapping) for item in value]
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key == "snapshotJson" and isinstance(item, str) and item:
                try:
                    parsed = json.loads(item)
                except (TypeError, ValueError):
                    _fail("SYNC_PREFAB_STATIC_REFERENCE", "$", "staticFieldBinding snapshotJson is not valid JSON")
                parsed = _replace_exact(parsed, mapping)
                out[key] = json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            else:
                out[key] = _remap_static_binding(item, mapping)
        return out
    return _replace_exact(value, mapping)


def _clone_id(root, origin, kind):
    token = hashlib.sha256(origin.encode("utf-8")).hexdigest()[:16]
    return f"{root}::sync-{kind}-{token}"


def _suffix_generated_paths(component, target_id):
    """Give component-owned generated Editor assets a deterministic clone path."""
    token = hashlib.sha256(target_id.encode("utf-8")).hexdigest()[:12]
    for key in ("controllerPath", "normalClipPath", "pressedClipPath", "materialPath"):
        path = component.get(key)
        if not isinstance(path, str) or not path:
            continue
        parent, sep, leaf = path.rpartition("/")
        stem, dot, extension = leaf.rpartition(".")
        if not dot:
            stem, extension = leaf, ""
        suffix = f"__sync_{token}{'.' + extension if extension else ''}"
        cloned = stem + suffix
        if len(cloned.encode("utf-8")) > 64:
            # Include asset role in the shortened identity: normal/pressed clips
            # share an extension and may lose their readable state suffix.
            bounded_token = hashlib.sha256((target_id + "\n" + key).encode("utf-8")).hexdigest()[:12]
            suffix = f"__sync_{bounded_token}{'.' + extension if extension else ''}"
            budget = 64 - len(suffix.encode("utf-8"))
            if budget < 1:
                _fail("SYNC_ASSET_EXTENSION_TOO_LONG", target_id, "generated asset extension exceeds leaf budget")
            cloned = stem.encode("utf-8")[:budget].decode("utf-8", errors="ignore").rstrip(" .") + suffix
        component[key] = f"{parent}{sep if sep else ''}{cloned}"


def bind_sync_prefab_instances(plan, source_manifest, source_ir=None, source_profile=None):
    """Return a deep-copied target plan with all supported raw sync edges bound.

    Source manifest is the frozen inspect manifest (it contains serialized raw
    prefab documents); target plan must already contain both owner and template
    sourcePrefabs. For Creator 3 profiles it returns the plan unchanged because
    their native PrefabInstance graph has separate semantics. Cocos 2.4 source
    relationships from source_ir are preserved and combined with raw sync edges.
    Any unsupported override, missing template, malformed mapping, or cycle fails closed.
    """
    result = copy.deepcopy(plan)
    if source_profile is not None and source_profile not in COCOS_24_PROFILES:
        return result
    prefabs = {item["sourceId"]: item for item in result.get("sourcePrefabs", [])}
    nodes = {item["sourceId"]: item for item in result.get("nodes", [])}
    components = {item["sourceId"]: item for item in result.get("components", [])}
    if len(nodes) != len(result.get("nodes", [])) or len(components) != len(result.get("components", [])):
        _fail("SYNC_PREFAB_PLAN_DUPLICATE", "$", "target plan has duplicate node or component source IDs")
    assets, edges = _extract_edges(source_manifest, set(prefabs))
    if sum(map(len, edges.values())) > 4096:
        _fail("SYNC_PREFAB_BUDGET", "$", "more than 4096 sync edges")

    if result.get("prefabInstances") and source_ir is None:
        _fail("SYNC_PREFAB_PLAN_STAGE", "$", "source IR is required to preserve existing native prefab relationships")
    source_links = copy.deepcopy((source_ir or {}).get("prefabInstances", []))
    previous_roots = {item.get("root") for item in result.get("prefabInstances", [])}
    source_roots = {item.get("root") for item in source_links}
    if source_ir is not None and previous_roots != source_roots:
        _fail("SYNC_PREFAB_MIXED_RELATIONSHIP_SET", "$", "existing target relationships differ from source IR before sync binding")
    links = source_links
    binding_reports = list(result.get("syncPrefabBindings", []))
    visiting, finished = set(), set()
    source_node_ids = {sid: set(spec.get("nodes", [])) for sid, spec in prefabs.items()}

    def expand(owner):
        if owner in visiting:
            _fail("SYNC_PREFAB_CYCLE", owner, "sync template dependency cycle")
        if owner in finished:
            return
        visiting.add(owner)
        for edge in edges.get(owner, []):
            template = edge["template"]
            if template not in prefabs:
                _fail("SYNC_PREFAB_TEMPLATE_MISSING", edge["root"], "template is not present in target sourcePrefabs")
            expand(template)
            root_id = edge["root"]
            if root_id not in nodes or root_id not in source_node_ids.get(owner, set()):
                _fail("SYNC_PREFAB_ROOT_MISSING", root_id, "root node is missing from the owner sourcePrefab")
            if not edge["fileId"]:
                _fail("SYNC_PREFAB_FILE_ID", root_id, "empty raw source fileId")
            template_nodes = [sid for sid in prefabs[template].get("nodes", []) if sid in nodes]
            template_root = prefabs[template].get("root")
            if not template_nodes or template_root not in template_nodes:
                _fail("SYNC_PREFAB_TEMPLATE_MISSING", root_id, "template root or graph is unavailable")
            template_asset = assets.get(template)
            template_document = (template_asset or {}).get("document") or {}
            template_objects = template_document.get("instances") or []
            template_asset_index = template_document.get("root")
            if (type(template_asset_index) is not int or template_asset_index < 0 or template_asset_index >= len(template_objects)
                    or not isinstance(template_objects[template_asset_index], dict)
                    or template_objects[template_asset_index].get("__type__") != "cc.Prefab"):
                _fail("SYNC_PREFAB_TEMPLATE_MISSING", root_id, "raw source document has no cc.Prefab root object")
            template_root_index = _index_refs(template_objects[template_asset_index].get("data"), template_objects)
            if template_root != f"{template}#{template_root_index}":
                _fail("SYNC_PREFAB_TEMPLATE_ROOT", root_id, "target template root differs from raw cc.Prefab.data")
            placeholder = nodes[root_id]
            if placeholder.get("children") or placeholder.get("components"):
                _fail("SYNC_PREFAB_ROOT_OVERRIDE_UNSUPPORTED", root_id, "placeholder already has child or component rows")

            origin_map = {template_root: root_id}
            for sid in template_nodes:
                if sid == template_root:
                    continue
                origin_map[sid] = _clone_id(root_id, sid, "node")
            template_components = [c for c in result.get("components", []) if c.get("node") in set(template_nodes)]
            component_map = {c["sourceId"]: _clone_id(root_id, c["sourceId"], "component") for c in template_components}
            identity_map = {**origin_map, **component_map}

            # Root exceptions documented by Creator 2.4: name, active, position,
            # rotation belong to the instance. Scale and visual data inherit.
            cloned_nodes = {}
            for sid in template_nodes:
                row = copy.deepcopy(nodes[sid])
                target_id = origin_map[sid]
                row["sourceId"] = target_id
                row["parent"] = placeholder.get("parent") if sid == template_root else origin_map.get(row.get("parent"), row.get("parent"))
                row["children"] = [origin_map.get(child, child) for child in row.get("children", [])]
                row["components"] = [component_map.get(cid, cid) for cid in row.get("components", [])]
                row = _replace_exact(row, identity_map)
                row["sourceId"] = target_id
                if sid == template_root:
                    for key, source_key in (("name", "_name"), ("active", "_active")):
                        if source_key in edge["rootOverrides"]:
                            row[key] = edge["rootOverrides"][source_key]
                    trs = edge["rootOverrides"].get("_trs")
                    if trs is not None:
                        if not isinstance(trs, list) or len(trs) != 10:
                            _fail("SYNC_PREFAB_OVERRIDE_UNSUPPORTED", root_id, "root _trs must contain the source 10-value transform")
                        row["position"] = copy.deepcopy(trs[0:3])
                        row["rotation"] = copy.deepcopy(trs[3:7])
                cloned_nodes[target_id] = row

            # The raw root's parent relationship is retained; template descendants
            # are added only after the full graph and component remap is known.
            for target_id, row in cloned_nodes.items():
                if target_id == root_id:
                    continue
                if target_id in nodes:
                    _fail("SYNC_PREFAB_ID_COLLISION", target_id, "stable clone identity collides with an existing plan node")
                nodes[target_id] = row
            nodes[root_id].update(cloned_nodes[root_id])
            parent = nodes[root_id].get("parent")
            expected_parent = f"{owner}#{edge['rawParentIndex']}" if edge["rawParentIndex"] is not None else None
            if parent != expected_parent:
                _fail("SYNC_PREFAB_PARENT_MISMATCH", root_id, "target placeholder parent differs from raw serialized parent")
            if parent not in nodes:
                _fail("SYNC_PREFAB_PARENT_MISSING", root_id, "instance root parent is absent")
            parent_children = nodes[parent].setdefault("children", [])
            if root_id not in parent_children:
                _fail("SYNC_PREFAB_PARENT_MISMATCH", root_id, "owner parent does not contain the instance root")

            for component in template_components:
                cloned = _remap_static_binding(copy.deepcopy(component), identity_map)
                cloned["sourceId"] = component_map[component["sourceId"]]
                cloned["node"] = origin_map[component["node"]]
                if cloned.get("staticFieldBinding"):
                    cloned["staticFieldBinding"]["sourceTemplateId"] = component["sourceId"]
                if cloned.get("spineBinding"):
                    cloned["spineBinding"]["sourceTemplateComponentId"] = component["sourceId"]
                    cloned["spineBinding"]["sourceComponentId"] = cloned["sourceId"]
                    cloned["spineBinding"]["sourcePrefabId"] = owner
                    cloned["spineBinding"]["sourceNodeId"] = cloned["node"]
                _suffix_generated_paths(cloned, cloned["sourceId"])
                if cloned["sourceId"] in components:
                    _fail("SYNC_PREFAB_ID_COLLISION", cloned["sourceId"], "stable clone identity collides with an existing plan component")
                result["components"].append(cloned)
                components[cloned["sourceId"]] = cloned

            owner_spec = prefabs[owner]
            owner_spec["nodes"] = sorted(set(owner_spec.get("nodes", [])) | set(cloned_nodes))
            owner_spec["nodeCount"] = len(owner_spec["nodes"])
            source_node_ids[owner] = set(owner_spec["nodes"])
            pairs = [{"instanceObject": origin_map[sid], "templateObject": sid} for sid in template_nodes]
            link = {"root": root_id, "template": template, "objects": pairs, "sourceInstanceFileId": edge["fileId"]}
            links.append(link)
            binding_reports.append({
                "owner": owner, "root": root_id, "template": template, "templateUuid": edge["templateUuid"],
                "sourceInstanceFileId": edge["fileId"], "sourceDocumentSha256": edge["sourceDocumentSha256"],
                "rootOverrides": {"name": "_name", "active": "_active", "position": "_trs[0:3]", "rotation": "_trs[3:7]"},
                "origins": [{"templateSourceId": source, "instanceSourceId": target} for source, target in sorted(origin_map.items())],
                "componentOrigins": [{"templateSourceId": source, "instanceSourceId": target} for source, target in sorted(component_map.items())],
            })
        visiting.remove(owner)
        finished.add(owner)

    for owner in sorted(edges):
        expand(owner)
    result["nodes"] = sorted(nodes.values(), key=lambda n: n["sourceId"])
    if links:
        from .targets.prefabs import native_relationships

        graph = {"nodes": list(nodes.values()), "components": result.get("components", []), "prefabInstances": links}
        ordered_prefabs, native_instances = native_relationships(graph, list(prefabs.values()), graph["components"])
        expected_roots = {item.get("root") for item in native_instances}
        if previous_roots and not previous_roots.issubset(expected_roots):
            _fail("SYNC_PREFAB_MIXED_RELATIONSHIP_SET", "$", "existing target relationships differ from source IR plus raw sync edges")
        result["sourcePrefabs"] = ordered_prefabs
        result["prefabInstances"] = native_instances
    else:
        if edges:
            _fail("SYNC_PREFAB_INTERNAL", "$", "sync edges were found but no native relationships were planned")
    result["syncPrefabBindings"] = binding_reports
    return expand_material_instance_bindings(result)


def expand_material_instance_bindings(plan):
    """Carry an already-proven material profile onto explicit sync instances."""
    result=copy.deepcopy(plan)
    material=(result.get('materialBinding') or {}).get('spec')
    if not material:
        return result
    known=set(material.get('sourceComponentIds',[]))
    components={c['sourceId']:c for c in result.get('components',[])}
    for relation in result.get('syncPrefabBindings',[]):
        for origin in relation.get('componentOrigins',[]):
            source,target=origin['templateSourceId'],origin['instanceSourceId']
            if source not in known or target in known:
                continue
            original,instance=components.get(source),components.get(target)
            if not original or not instance or original.get('nativeMaterialSourceId')!=instance.get('nativeMaterialSourceId'):
                _fail('SYNC_MATERIAL_PROFILE_MISMATCH',target,'material source identity differs from template')
            rows=[row for row in material.get('spriteBindings',[]) if row.get('sourceId')==source]
            if len(rows)!=1:
                _fail('SYNC_MATERIAL_BINDING_AMBIGUOUS',source,'expected exactly one bound template sprite')
            material['sourceComponentIds'].append(target);known.add(target)
            material['spriteBindings'].append({**copy.deepcopy(rows[0]),'sourceId':target})
            material.setdefault('syncInstanceOrigins',[]).append({'sourceId':target,'templateSourceId':source,'owner':relation['owner']})
            for row in list(material.get('sourceBindings',[])):
                if row.get('sourceId')==source:
                    material['sourceBindings'].append({**copy.deepcopy(row),'sourceId':target,'sourcePrefabId':relation['owner'],'templateSourceId':source})
    return result
