"""Plan a bounded, evidence-preserving graph from existing Unity typed objects.

``build(inputs, roots)`` accepts already loaded strict typed-object documents and
exact container roots. It does not parse source files, interpret behavior, or
write a target Prefab. The result records the complete reference closure available
in those documents, exact source identities, hierarchy/component expectations,
and explicit gaps. Unknown schemas and custom values remain source data.

PPtr resolution follows Unity's fileId semantics: zero is local to the owning
serialized file; nonzero must identify exactly one row in that file's external
table, whose complete serialized filename must be present in the supplied input
set. Ambiguous non-identical serialized files fail closed. Byte-identical aliases
are accepted only when complete object parse records and referenced schema
evidence also match. Input counts, graph records, field depth and aggregate typed
value size are explicitly bounded. Unity builtin externals remain unverified
engine references and are never guessed into source assets.
"""

from __future__ import annotations

import json
import re
from collections import deque
from typing import Any


CONTRACT = "monkey-unity-prefab-source-graph/1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SIGNED64 = re.compile(r"^-?(?:0|[1-9][0-9]*)$")
MAX_INPUTS = 512
MAX_ROOTS = 10_000
MAX_SERIALIZED_FILES = 50_000
MAX_OBJECTS = 250_000
MAX_REFERENCE_ROWS = 1_000_000
MAX_GRAPH_EDGES = 1_000_000
MAX_GAPS = 1_000_000
MAX_TYPED_VALUE_NODES = 2_000_000
MAX_TYPED_VALUE_DEPTH = 128
MAX_TYPED_VALUE_BYTES = 128 * 1024 * 1024


class GraphInputError(ValueError):
    """The supplied strict typed-object documents violate graph identity rules."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise GraphInputError(message)


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _identity(container_sha: str, file_row: dict, path_id: str) -> dict:
    return {
        "containerSha256": container_sha,
        "serializedFileSha256": file_row["serializedFileSha256"],
        "serializedFile": file_row["name"],
        "pathId": path_id,
    }


def _identity_id(identity: dict) -> str:
    return _canon(identity)


def _valid_ptr(value: Any) -> bool:
    return (isinstance(value, dict) and value.get("$type") == "UnityPPtr"
            and isinstance(value.get("fileId"), str) and isinstance(value.get("pathId"), str)
            and _SIGNED64.fullmatch(value["fileId"]) is not None
            and _SIGNED64.fullmatch(value["pathId"]) is not None)


def _scan_ptrs(value: Any, location: str = "$"):
    """Iteratively enumerate pointers; depth and node budgets are preflighted."""
    stack = [(value, location)]
    while stack:
        current, current_location = stack.pop()
        if isinstance(current, dict):
            if current.get("$type") == "UnityPPtr":
                yield current_location, current
            else:
                for key, child in reversed(list(current.items())):
                    stack.append((child, f"{current_location}/{key}"))
        elif isinstance(current, list):
            for index in range(len(current) - 1, -1, -1):
                stack.append((current[index], f"{current_location}/{index}"))


def _count_values(value: Any, *, limit: int, byte_limit: int, depth_limit: int, label: str) -> tuple[int, int]:
    count = 0
    byte_count = 0
    stack = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        count += 1
        _require(count <= limit, f"{label}: typed value node budget exceeded ({limit})")
        _require(depth <= depth_limit, f"{label}: typed value depth budget exceeded ({depth_limit})")
        if isinstance(current, dict):
            byte_count += sum(len(key.encode("utf-8")) for key in current if isinstance(key, str))
            stack.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            stack.extend((child, depth + 1) for child in current)
        elif isinstance(current, str):
            byte_count += len(current.encode("utf-8"))
        _require(byte_count <= byte_limit, f"{label}: typed value byte budget exceeded ({byte_limit})")
    return count, byte_count


def _filename(external_path: Any) -> str | None:
    """Return only a fully evidenced serialized filename, never a loose basename."""
    if not isinstance(external_path, str) or not external_path or "\\" in external_path:
        return None
    if not external_path.startswith("archive:/"):
        return external_path if "/" not in external_path else None
    tail = external_path[len("archive:/"):]
    parts = tail.split("/")
    # Unity archive references in the strict snapshots repeat the CAB name.
    if len(parts) == 2 and parts[0] == parts[1] and parts[0]:
        return parts[0]
    return None


def _builtin_external(path: Any) -> str | None:
    if not isinstance(path, str):
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", path.lower()).strip()
    if "unity default resources" in normalized:
        return "unity-default-resources"
    if "unity builtin extra" in normalized or "unity builtins" in normalized or "unity builtin resources" in normalized:
        return "unity-builtin-resources"
    return None


def _file_evidence_signature(key: tuple[str, str], members: list[dict], doc: dict) -> str:
    """Include each complete parse record and every schema shape it relies on."""
    evidence = []
    for obj in members:
        row = {"object": obj}
        for field, pool_name in (("embeddedSchemaId", "embeddedSchemas"), ("borrowedSchemaId", "borrowedSchemas")):
            schema_id = obj.get(field)
            if schema_id is not None:
                _require(isinstance(schema_id, str), f"serialized file {key}: {field} must be a string")
                pool = doc.get(pool_name, {})
                row[field] = {"id": schema_id, "schema": pool.get(schema_id, {"missing": True}) if isinstance(pool, dict) else {"missing": True}}
        evidence.append(_canon(row))
    return _canon(sorted(evidence))


def build(inputs: list[dict], roots: list[dict]) -> dict:
    """Build a deterministic bounded graph from loaded typed-object documents.

    ``inputs`` rows are ``{sourceSha256, document}``; roots are
    ``{sourceSha256, file, pathId}``. Input document hashes refer to their
    original containers, not the JSON snapshot bytes.
    """
    _require(isinstance(inputs, list) and inputs, "inputs must be a nonempty list")
    _require(isinstance(roots, list) and roots, "roots must be a nonempty list")
    _require(len(inputs) <= MAX_INPUTS, f"input count budget exceeded ({MAX_INPUTS})")
    _require(len(roots) <= MAX_ROOTS, f"root count budget exceeded ({MAX_ROOTS})")

    input_by_sha: dict[str, dict] = {}
    file_rows: dict[tuple[str, str], dict] = {}
    file_docs: dict[tuple[str, str], dict] = {}
    file_objects: dict[tuple[str, str], list[dict]] = {}
    file_groups: dict[str, list[tuple[str, str]]] = {}
    objects: dict[tuple[str, str, str], dict] = {}
    object_ids: dict[tuple[str, str, str], str] = {}
    reference_row_count = 0
    typed_value_count = 0
    typed_value_bytes = 0

    for item in inputs:
        _require(isinstance(item, dict), "input row must be an object")
        container_sha, doc = item.get("sourceSha256"), item.get("document")
        _require(isinstance(container_sha, str) and _SHA256.fullmatch(container_sha) is not None,
                 "sourceSha256 must be lowercase SHA-256")
        _require(container_sha not in input_by_sha, f"duplicate input container {container_sha}")
        _require(isinstance(doc, dict) and doc.get("sourceFamily") == "unity" and
                 isinstance(doc.get("files"), list) and isinstance(doc.get("objects"), list),
                 f"{container_sha}: strict Unity typed-object document required")
        source_record = doc.get("source")
        if isinstance(source_record, dict) and "sha256" in source_record:
            _require(source_record.get("sha256") == container_sha,
                     f"{container_sha}: document source.sha256 differs from input sourceSha256")
        _require(len(file_rows) + len(doc["files"]) <= MAX_SERIALIZED_FILES,
                 f"serialized-file count budget exceeded ({MAX_SERIALIZED_FILES})")
        _require(len(objects) + len(doc["objects"]) <= MAX_OBJECTS,
                 f"object count budget exceeded ({MAX_OBJECTS})")
        for schema_field in ("embeddedSchemas", "borrowedSchemas"):
            schema_pool = doc.get(schema_field, {})
            _require(isinstance(schema_pool, dict), f"{container_sha}: {schema_field} must be an object")
        payload_files = doc.get("payloadFiles", [])
        _require(isinstance(payload_files, list), f"{container_sha}: payloadFiles must be a list")
        nodes, byte_count = _count_values(payload_files, limit=MAX_TYPED_VALUE_NODES - typed_value_count,
                                          byte_limit=MAX_TYPED_VALUE_BYTES - typed_value_bytes,
                                          depth_limit=MAX_TYPED_VALUE_DEPTH, label=f"{container_sha}:payloadFiles")
        typed_value_count += nodes
        typed_value_bytes += byte_count
        input_by_sha[container_sha] = doc
        local_file_ids = set()
        for f in doc["files"]:
            _require(isinstance(f, dict) and isinstance(f.get("id"), str) and isinstance(f.get("name"), str)
                     and f["name"] and isinstance(f.get("serializedFileSha256"), str)
                     and _SHA256.fullmatch(f["serializedFileSha256"]) is not None
                     and isinstance(f.get("externals"), list),
                     f"{container_sha}: file requires exact name, serialized hash and external table")
            _require(f["id"] not in local_file_ids, f"{container_sha}: duplicate serialized-file id {f['id']}")
            reference_row_count += len(f["externals"])
            _require(reference_row_count <= MAX_REFERENCE_ROWS,
                     f"reference/external row budget exceeded ({MAX_REFERENCE_ROWS})")
            local_file_ids.add(f["id"])
            key = (container_sha, f["id"])
            row = dict(f, containerSha256=container_sha)
            file_rows[key] = row
            file_docs[key] = doc
            file_groups.setdefault(f["name"], []).append(key)

        for obj in doc["objects"]:
            _require(isinstance(obj, dict) and isinstance(obj.get("file"), str)
                     and isinstance(obj.get("pathId"), str) and _SIGNED64.fullmatch(obj["pathId"]) is not None
                     and isinstance(obj.get("type"), str) and isinstance(obj.get("references", []), list),
                     f"{container_sha}: malformed typed object identity")
            key = (container_sha, obj["file"], obj["pathId"])
            _require((container_sha, obj["file"]) in file_rows, f"object refers to unknown file id {obj['file']}")
            _require(key not in objects, f"duplicate object identity {key}")
            refs = obj.get("references", [])
            reference_row_count += len(refs)
            _require(reference_row_count <= MAX_REFERENCE_ROWS,
                     f"reference row budget exceeded ({MAX_REFERENCE_ROWS})")
            objects[key] = obj
            file_objects.setdefault((container_sha, obj["file"]), []).append(obj)
            object_ids[key] = _identity_id(_identity(container_sha, file_rows[(container_sha, obj["file"])], obj["pathId"]))

    # Same serialized name can only be shared by byte- and object-identical files.
    canonical_file: dict[tuple[str, str], tuple[str, str]] = {}
    for name, group in file_groups.items():
        hashes = {file_rows[k]["serializedFileSha256"] for k in group}
        _require(len(hashes) == 1, f"serialized filename collision with different bytes: {name}")
        if len(group) > 1:
            signatures = []
            for key in group:
                # Aliasing is a whole-file equality claim, so its complete
                # comparison retains a separate hard budget before encoding.
                members = file_objects.get(key, [])
                used_shapes = [file_docs[key].get(pool, {}).get(obj[field], {})
                              for obj in members for field, pool in (("embeddedSchemaId", "embeddedSchemas"), ("borrowedSchemaId", "borrowedSchemas"))
                              if isinstance(obj.get(field), str)]
                _count_values(dict(objects=members, schemas=used_shapes), limit=MAX_TYPED_VALUE_NODES,
                              byte_limit=MAX_TYPED_VALUE_BYTES, depth_limit=MAX_TYPED_VALUE_DEPTH, label="serialized alias " + name)
                signatures.append(_file_evidence_signature(key, file_objects.get(key, []), file_docs[key]))
            _require(len(set(signatures)) == 1, f"serialized filename collision with different object identities/data: {name}")
        ordered = sorted(group)
        chosen = ordered[0]
        for key in group:
            canonical_file[key] = chosen

    # Resolve using owner-local file IDs and an exact complete external filename.
    def resolve(origin: tuple[str, str, str], ptr: dict) -> tuple[str, str, str] | None:
        _require(_valid_ptr(ptr), f"malformed UnityPPtr on {object_ids[origin]}")
        if ptr["pathId"] == "0":
            return None
        owner_file = file_rows[(origin[0], origin[1])]
        target_file = (origin[0], origin[1])
        if ptr["fileId"] != "0":
            matches = [e for e in owner_file["externals"] if e.get("fileId") == ptr["fileId"]]
            if len(matches) != 1:
                return None
            name = _filename(matches[0].get("path"))
            if name is None:
                return None
            candidates = file_groups.get(name, [])
            if not candidates:
                return None
            # A duplicate same-name group was validated above as byte/data identical.
            target_file = canonical_file[candidates[0]]
        target_key = (target_file[0], target_file[1], ptr["pathId"])
        return target_key if target_key in objects else None

    root_records = []
    queue = deque()
    for root in roots:
        _require(isinstance(root, dict) and root.get("sourceSha256") in input_by_sha
                 and isinstance(root.get("file"), str) and isinstance(root.get("pathId"), str)
                 and _SIGNED64.fullmatch(root["pathId"]) is not None, "root must name an exact supplied source object")
        key = (root["sourceSha256"], root["file"], root["pathId"])
        _require(key in objects, f"missing root object {root}")
        _require(objects[key].get("type") == "GameObject", f"root is not a GameObject: {root}")
        rid = object_ids[key]
        root_records.append(dict(sourceObjectId=rid, identity=_identity(root["sourceSha256"], file_rows[key[:2]], key[2])))
        queue.append(key)

    reachable: set[tuple[str, str, str]] = set()
    edges: dict[str, dict] = {}
    gaps: list[dict] = []
    def add_gap(gap: dict) -> None:
        _require(len(gaps) < MAX_GAPS, f"gap count budget exceeded ({MAX_GAPS})")
        gaps.append(gap)

    def external_row(origin: tuple[str, str, str], ptr: dict) -> dict | None:
        if ptr["fileId"] == "0":
            return None
        file_row = file_rows[(origin[0], origin[1])]
        matches = [e for e in file_row["externals"] if e.get("fileId") == ptr["fileId"]]
        return matches[0] if len(matches) == 1 else None

    counted_schemas = set()
    while queue:
        key = queue.popleft()
        if key in reachable:
            continue
        reachable.add(key)
        obj = objects[key]
        oid = object_ids[key]
        nodes, byte_count = _count_values(obj, limit=MAX_TYPED_VALUE_NODES - typed_value_count,
                                          byte_limit=MAX_TYPED_VALUE_BYTES - typed_value_bytes,
                                          depth_limit=MAX_TYPED_VALUE_DEPTH, label=oid)
        typed_value_count += nodes
        typed_value_bytes += byte_count
        for field, pool_name in (("embeddedSchemaId", "embeddedSchemas"), ("borrowedSchemaId", "borrowedSchemas")):
            schema_id = obj.get(field)
            _require(schema_id is None or isinstance(schema_id, str), f"{oid}: schema ID must be a string")
            schema_key = (key[0], pool_name, schema_id)
            if schema_id is not None and schema_key not in counted_schemas:
                counted_schemas.add(schema_key)
                schema = input_by_sha[key[0]].get(pool_name, {}).get(schema_id, {})
                nodes, byte_count = _count_values(schema, limit=MAX_TYPED_VALUE_NODES - typed_value_count,
                                                  byte_limit=MAX_TYPED_VALUE_BYTES - typed_value_bytes,
                                                  depth_limit=MAX_TYPED_VALUE_DEPTH, label=oid + "/schema")
                typed_value_count += nodes
                typed_value_bytes += byte_count
        if obj.get("status") != "parsed":
            add_gap(dict(sourceObjectId=oid, kind="object-unparsed", status=obj.get("status", "unknown")))
        if obj.get("type") == "MonoBehaviour":
            if not obj.get("embeddedSchemaId") and not obj.get("borrowedSchemaId"):
                add_gap(dict(sourceObjectId=oid, kind="schema-unknown", type=obj.get("type"),
                                 typeTreeSource=obj.get("typeTreeSource")))
            elif obj.get("typeTreeSource") not in ("embedded", "exact-frozen-bundle"):
                add_gap(dict(sourceObjectId=oid, kind="schema-provenance-unknown", typeTreeSource=obj.get("typeTreeSource")))

        listed = obj.get("references", [])
        listed_by_location: dict[str, list[dict]] = {}
        for ref in listed:
            _require(isinstance(ref, dict) and isinstance(ref.get("location"), str)
                     and isinstance(ref.get("fileId"), str) and isinstance(ref.get("pathId"), str),
                     f"malformed source reference record on {oid}")
            listed_by_location.setdefault(ref["location"], []).append(ref)
        field_ptrs = list(_scan_ptrs(obj.get("data", {}))) if obj.get("status") == "parsed" else []
        combined = []
        for location, ptr in field_ptrs:
            if not _valid_ptr(ptr):
                add_gap(dict(sourceObjectId=oid, kind="malformed-pointer", location=location, pointer=ptr))
                continue
            combined.append((location, ptr, "field"))
        for location, refs in listed_by_location.items():
            for ref in refs:
                ptr = {"$type": "UnityPPtr", "fileId": ref["fileId"], "pathId": ref["pathId"]}
                match = any(p.get("fileId") == ptr["fileId"] and p.get("pathId") == ptr["pathId"] for loc, p in field_ptrs if loc == location)
                if not match:
                    # Reference rows can represent streamed PPtrs. Preserve and follow
                    # them even when the field value is not inlined in ``data``.
                    combined.append((location, ptr, "reference-record"))
                    if obj.get("parseMetrics", {}).get("streamedValues", 0):
                        pass
                    else:
                        add_gap(dict(sourceObjectId=oid, kind="reference-data-mismatch", location=location, pointer=ptr))
        for location, ptr, evidence in combined:
            edge = dict(sourceObjectId=oid, location=location, fileId=ptr["fileId"], pathId=ptr["pathId"], evidence=evidence)
            if ptr["pathId"] == "0":
                edge["status"] = "null"
                edge["targetSourceObjectId"] = None
            else:
                external = external_row(key, ptr)
                builtin_kind = _builtin_external(external.get("path")) if external else None
                if builtin_kind:
                    edge["status"] = "engine-provided-unverified"
                    edge["targetSourceObjectId"] = None
                    edge["externalIdentity"] = {
                        "category": builtin_kind,
                        "ownerSerializedFile": {"containerSha256": file_rows[key[:2]]["containerSha256"],
                                                "serializedFileSha256": file_rows[key[:2]]["serializedFileSha256"],
                                                "name": file_rows[key[:2]]["name"]},
                        "fileId": ptr["fileId"], "path": external.get("path"), "guid": external.get("guid"),
                        "guidEncoding": "serialized-guid-bytes-hex",
                    }
                    add_gap(dict(sourceObjectId=oid, kind="engine-reference-unverified", location=location,
                                 category=builtin_kind, pointer=dict(fileId=ptr["fileId"], pathId=ptr["pathId"]),
                                 externalIdentity=edge["externalIdentity"], reason="native engine identity not verified"))
                else:
                    target = resolve(key, ptr)
                    if target is None:
                        edge["status"] = "unresolved"
                        edge["targetSourceObjectId"] = None
                        add_gap(dict(sourceObjectId=oid, kind="reference-unresolved", location=location,
                                     pointer=dict(fileId=ptr["fileId"], pathId=ptr["pathId"]),
                                     reason="external identity absent/ambiguous or target object missing"))
                    else:
                        edge["status"] = "resolved"
                        edge["targetSourceObjectId"] = object_ids[target]
                        queue.append(target)
            _require(_canon(edge) in edges or len(edges) < MAX_GRAPH_EDGES,
                     f"graph edge budget exceeded ({MAX_GRAPH_EDGES})")
            edges[_canon(edge)] = edge

        listed_ptr_keys = {(loc, ref["fileId"], ref["pathId"]) for loc, refs in listed_by_location.items() for ref in refs}
        for location, ptr in field_ptrs:
            if _valid_ptr(ptr) and (location, ptr["fileId"], ptr["pathId"]) not in listed_ptr_keys:
                add_gap(dict(sourceObjectId=oid, kind="field-reference-not-indexed", location=location,
                                 pointer=dict(fileId=ptr["fileId"], pathId=ptr["pathId"])))
        # An unparsed object may contain reference blocks which cannot be enumerated.
        if obj.get("status") != "parsed":
            add_gap(dict(sourceObjectId=oid, kind="reference-closure-incomplete", reason="object data was not parsed"))

    # Build semantic GameObject/Transform/component expectations from source records.
    by_type = {key: obj.get("type") for key, obj in objects.items()}
    def ptr_target(owner: tuple[str, str, str], ptr: Any, expected: str, location: str) -> tuple[str, str, str] | None:
        if not _valid_ptr(ptr):
            add_gap(dict(sourceObjectId=object_ids[owner], kind="hierarchy-pointer-malformed", location=location))
            return None
        if ptr["pathId"] == "0":
            return None
        target = resolve(owner, ptr)
        if target is None:
            add_gap(dict(sourceObjectId=object_ids[owner], kind="hierarchy-reference-unresolved", location=location,
                             pointer=dict(fileId=ptr["fileId"], pathId=ptr["pathId"])))
            return None
        matches = by_type[target] == expected or (expected == "Transform" and by_type[target] == "RectTransform")
        if not matches:
            add_gap(dict(sourceObjectId=object_ids[owner], kind="hierarchy-type-mismatch", location=location,
                             expected=expected, actual=by_type[target], targetSourceObjectId=object_ids[target]))
            return None
        return target

    game_objects = [k for k in reachable if objects[k].get("type") == "GameObject"]
    hierarchy = []
    parent_of: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    child_lists: dict[tuple[str, str, str], list[tuple[str, str, str]]] = {}
    for go in game_objects:
        data = objects[go].get("data", {})
        comps = data.get("m_Component")
        component_rows = []
        if not isinstance(comps, list):
            add_gap(dict(sourceObjectId=object_ids[go], kind="components-list-missing"))
            comps = []
        for index, wrapper in enumerate(comps):
            ptr = wrapper.get("component") if isinstance(wrapper, dict) else None
            target = resolve(go, ptr) if _valid_ptr(ptr) and ptr["pathId"] != "0" else None
            if target is not None and not (isinstance(objects[target].get("data"), dict)
                                           and "m_GameObject" in objects[target]["data"]):
                add_gap(dict(sourceObjectId=object_ids[go], kind="component-type-mismatch",
                                 location=f"$/m_Component/{index}/component", actual=by_type[target]))
                target = None
            if target is None:
                component_rows.append(dict(index=index, pointer=ptr, sourceObjectId=None, status="unresolved"))
            else:
                component_rows.append(dict(index=index, pointer=ptr, sourceObjectId=object_ids[target],
                                           type=objects[target].get("type"), status="resolved"))
                actual_owner = ptr_target(target, objects[target].get("data", {}).get("m_GameObject"), "GameObject", "$/m_GameObject")
                if actual_owner != go:
                    add_gap(dict(sourceObjectId=object_ids[target], kind="component-owner-mismatch",
                                 expectedGameObject=object_ids[go],
                                 actualGameObject=object_ids[actual_owner] if actual_owner else None))
        transform_targets = [row for row in component_rows if row.get("type") in ("Transform", "RectTransform")]
        if len(transform_targets) != 1:
            add_gap(dict(sourceObjectId=object_ids[go], kind="transform-cardinality", count=len(transform_targets)))
        transform = None
        if transform_targets:
            transform = next((k for k in reachable if object_ids[k] == transform_targets[0]["sourceObjectId"]), None)
        parent_id = None
        children_ids = []
        if transform:
            tdata = objects[transform].get("data", {})
            father = tdata.get("m_Father")
            if _valid_ptr(father) and father["pathId"] != "0":
                parent_t = ptr_target(transform, father, "Transform", "$/m_Father")
                if parent_t:
                    parent_go = ptr_target(parent_t, objects[parent_t].get("data", {}).get("m_GameObject"), "GameObject", "$/m_GameObject")
                    if parent_go:
                        parent_id = object_ids[parent_go]
                        parent_of[go] = parent_go
            elif not _valid_ptr(father):
                add_gap(dict(sourceObjectId=object_ids[transform], kind="father-field-missing-or-malformed"))
            child_ptrs = tdata.get("m_Children")
            if not isinstance(child_ptrs, list):
                add_gap(dict(sourceObjectId=object_ids[transform], kind="children-list-missing"))
            else:
                for index, child_ptr in enumerate(child_ptrs):
                    child_t = ptr_target(transform, child_ptr, "Transform", f"$/m_Children/{index}")
                    if child_t:
                        child_go = ptr_target(child_t, objects[child_t].get("data", {}).get("m_GameObject"), "GameObject", "$/m_GameObject")
                        if child_go:
                            child_lists.setdefault(go, []).append(child_go)
                            children_ids.append(object_ids[child_go])
            transform_data = {k: v for k, v in tdata.items() if k in {
                "m_LocalRotation", "m_LocalPosition", "m_LocalScale", "m_Children", "m_Father",
                "m_AnchorMin", "m_AnchorMax", "m_AnchoredPosition", "m_SizeDelta", "m_Pivot",
            }}
        else:
            transform_data = None
        hierarchy.append(dict(sourceObjectId=object_ids[go], name=data.get("m_Name"), active=data.get("m_IsActive"),
                              layer=data.get("m_Layer"), tag=data.get("m_Tag"), parentSourceObjectId=parent_id,
                              childSourceObjectIds=children_ids, orderedComponents=component_rows,
                              transformType=objects[transform].get("type") if transform else None,
                              transformData=transform_data))

    # Report orphan/mismatched hierarchy records and parent cycles within closure.
    for parent, children in child_lists.items():
        for child in children:
            if parent_of.get(child) != parent:
                add_gap(dict(sourceObjectId=object_ids[child], kind="parent-child-inconsistency",
                                 childParent=object_ids[parent_of[child]] if child in parent_of else None,
                                 listedBy=object_ids[parent]))
    transform_to_go = {}
    for row in hierarchy:
        for comp in row["orderedComponents"]:
            if comp.get("type") in ("Transform", "RectTransform") and comp.get("sourceObjectId"):
                transform_to_go[comp["sourceObjectId"]] = row["sourceObjectId"]
    for go in game_objects:
        transform = next((k for k in reachable if object_ids[k] in transform_to_go and transform_to_go[object_ids[k]] == object_ids[go]), None)
        if transform:
            for index, child_ptr in enumerate(objects[transform].get("data", {}).get("m_Children", []) if isinstance(objects[transform].get("data", {}).get("m_Children"), list) else []):
                child_t = resolve(transform, child_ptr) if _valid_ptr(child_ptr) and child_ptr.get("pathId") != "0" else None
                if child_t:
                    child_go = ptr_target(child_t, objects[child_t].get("data", {}).get("m_GameObject"), "GameObject", "$/m_GameObject")
                    if child_go and child_go not in game_objects:
                        add_gap(dict(sourceObjectId=object_ids[go], kind="hierarchy-child-outside-reference-closure", childSourceObjectId=object_ids[child_go]))

    state = {}
    for start in game_objects:
        if state.get(start, 0) == 2:
            continue
        stack = [(start, False)]
        while stack:
            node, exiting = stack.pop()
            if exiting:
                state[node] = 2
                continue
            mark = state.get(node, 0)
            if mark == 1:
                add_gap(dict(sourceObjectId=object_ids[node], kind="hierarchy-cycle"))
                continue
            if mark == 2:
                continue
            state[node] = 1
            stack.append((node, True))
            for child in reversed(child_lists.get(node, [])):
                if state.get(child, 0) == 1:
                    add_gap(dict(sourceObjectId=object_ids[child], kind="hierarchy-cycle"))
                elif state.get(child, 0) != 2:
                    stack.append((child, False))

    records = []
    for key in sorted(reachable, key=lambda k: object_ids[k]):
        obj = objects[key]
        file_row = file_rows[key[:2]]
        record = dict(sourceObjectId=object_ids[key], identity=_identity(key[0], file_row, key[2]),
                      type=obj.get("type"), classId=obj.get("classId"), name=obj.get("name"), status=obj.get("status"),
                      rawSha256=obj.get("rawSha256"), data=obj.get("data"), typeTreeSource=obj.get("typeTreeSource"),
                      embeddedSchemaId=obj.get("embeddedSchemaId"), borrowedSchemaId=obj.get("borrowedSchemaId"),
                      bytes=obj.get("bytes"), parseMetrics=obj.get("parseMetrics"),
                      semanticValidation=obj.get("semanticValidation"), texturePayload=obj.get("texturePayload"),
                      referenceEdges=sorted((e for e in edges.values() if e["sourceObjectId"] == object_ids[key]), key=lambda e: (e["location"], e["fileId"], e["pathId"])))
        if obj.get("type") == "MonoScript" and isinstance(obj.get("data"), dict):
            record["monoScript"] = {k: obj["data"].get(k) for k in ("m_AssemblyName", "m_Namespace", "m_ClassName")}
        if obj.get("type") == "MonoBehaviour":
            script_ptr = obj.get("data", {}).get("m_Script")
            script_target = resolve(key, script_ptr) if _valid_ptr(script_ptr) and script_ptr.get("pathId") != "0" else None
            record["monoScriptIdentity"] = object_ids[script_target] if script_target and objects[script_target].get("type") == "MonoScript" else None
            if record["monoScriptIdentity"] is None:
                add_gap(dict(sourceObjectId=object_ids[key], kind="mono-script-unresolved"))
        records.append(record)

    # Stable de-duplication for gaps which can be discovered by multiple checks.
    gap_map = {_canon(g): g for g in gaps}
    return {
        "contract": CONTRACT,
        "sourceUnityVersions": sorted({f.get("unityVersion") for f in file_rows.values() if f.get("unityVersion")}),
        "targetVersion": "6000.6.2f1",
        "roots": sorted(root_records, key=lambda r: r["sourceObjectId"]),
        "reachableObjects": records,
        "referenceEdges": sorted(edges.values(), key=lambda e: (e["sourceObjectId"], e["location"], e["fileId"], e["pathId"])),
        "gameObjects": sorted(hierarchy, key=lambda r: r["sourceObjectId"]),
        "payloadFiles": sorted((dict(payload, containerSha256=container_sha)
                                 for container_sha, doc in input_by_sha.items()
                                 for payload in doc.get("payloadFiles", []) if isinstance(payload, dict)),
                                key=_canon),
        "serializedFileAliases": [dict(name=name, serializedFileSha256=file_rows[group[0]]["serializedFileSha256"],
                                        canonical=dict(containerSha256=canonical_file[group[0]][0], fileId=canonical_file[group[0]][1]),
                                        aliases=[dict(containerSha256=c, fileId=fid) for c, fid in sorted(group[1:])])
                                  for name, group in sorted(file_groups.items()) if len(group) > 1],
        "gaps": [gap_map[k] for k in sorted(gap_map)],
        "budgetUsage": {"scope": "selected-reachable-object-values-and-used-schemas;all-input-identities-and-reference-counts-checked",
                        "typedValueNodes": typed_value_count, "typedStringBytes": typed_value_bytes,
                        "maxTypedValueNodes": MAX_TYPED_VALUE_NODES, "maxTypedStringBytes": MAX_TYPED_VALUE_BYTES},
        "execution": {"sourceCode": "not_run", "nativeEditor": "not_run", "runtime": "not_run"},
    }
