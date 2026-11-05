"""Resolve diagnostic capture contexts from exact serialized Prefab instances.

This does not choose gameplay state, move a template, or approve visual parity.
The caller supplies the frozen source manifest and the actual generated plan.
"""
from __future__ import annotations

from .prefab_sync_instances import _extract_edges


def contexts(manifest: dict, plan: dict, target_id: str) -> list[dict]:
    """Return every source-proven parent occurrence represented by this plan.

    An isolated leaf's position is not evidence for its position in a page.
    Reject mismatched planner relationships instead of guessing from node names.
    """
    if manifest.get("sourceProfile") not in ("cocos-2.4.15-bundle", "cocos-2.4.15-project"):
        raise ValueError("CONTEXT_SOURCE_PROFILE_UNSUPPORTED")
    prefabs = {row["sourceId"]: row for row in plan.get("sourcePrefabs", [])}
    nodes = {row["sourceId"]: row for row in plan.get("nodes", [])}
    relations = [row for row in plan.get("prefabInstances", []) if row.get("template") == target_id]
    owners = {row["owner"] for row in relations}
    _, edges = _extract_edges(manifest, owners)
    result = []
    seen = set()
    for relation in relations:
        owner, root = relation["owner"], relation["root"]
        matching = [edge for edge in edges.get(owner, []) if edge["root"] == root and edge["template"] == target_id
                    and edge["fileId"] == relation.get("sourceInstanceFileId")]
        if len(matching) != 1 or owner not in prefabs or target_id not in prefabs:
            raise ValueError("CONTEXT_SOURCE_INSTANCE_MISMATCH: " + root)
        parent = prefabs[owner]
        if root in seen or root not in parent["nodes"] or root not in nodes:
            raise ValueError("CONTEXT_INSTANCE_BOUNDARY: " + root)
        seen.add(root)
        expected = prefabs[target_id]["root"]
        root_pairs = [pair for pair in relation.get("nodes", []) if pair.get("instanceObject") == root]
        if root_pairs != [{"instanceObject": root, "templateObject": expected}]:
            raise ValueError("CONTEXT_TEMPLATE_ROOT_MISMATCH: " + root)
        chain, current = [], root
        while current:
            if current in chain or current not in parent["nodes"] or current not in nodes:
                raise ValueError("CONTEXT_PARENT_CHAIN: " + root)
            chain.append(current)
            current = nodes[current].get("parent")
        if chain[-1] != parent["root"]:
            raise ValueError("CONTEXT_PARENT_ROOT_MISMATCH: " + root)
        result.append({
            "sourcePrefabId": owner, "targetPrefabId": target_id, "targetNodeId": root,
            "sourceInstanceFileId": relation["sourceInstanceFileId"],
            "sourceDocumentSha256": matching[0]["sourceDocumentSha256"],
            "sourceParentChain": list(reversed(chain)),
            "sourceState": "authored-serialized-no-business-execution",
            "sourceRootActive": nodes[parent["root"]]["active"],
            "targetSourceState": nodes[root],
        })
    return sorted(result, key=lambda row: (row["sourcePrefabId"], row["targetNodeId"]))


def prepare(plan_path, manifest_path, target_id):
    """Bind context observations to the exact raw plan and source-manifest bytes."""
    from .io import safe, read, load, sha
    plan_raw = read(safe(plan_path), max_bytes=128 * 1024 * 1024)
    manifest_raw = read(safe(manifest_path), max_bytes=128 * 1024 * 1024)
    plan = load(plan_raw, max_nodes=8_000_000)
    manifest = load(manifest_raw, max_nodes=8_000_000)
    if plan.get("sourceManifestSha256") != sha(manifest_raw):
        raise ValueError("CONTEXT_SOURCE_MANIFEST_PIN")
    return {"planSha256": sha(plan_raw), "sourceManifestSha256": sha(manifest_raw),
            "contexts": contexts(manifest, plan, target_id)}


def prepare_request(project, manifest, parent_id, target_id, output):
    """Write a pinned request for CaptureContextPreview in a fresh diagnostic copy."""
    from importlib.resources import files
    from .layout import standard
    from .io import inside, new_output, read, safe, sha, stage_manifest, write_json, load
    root = safe(project)
    ownership = stage_manifest(root)
    relative = standard.locate(ownership, 'importPlan')
    instruction = inside(root, relative)
    proof = prepare(instruction, manifest, target_id)
    matches = [r for r in ownership['files'] if r['path'] == relative]
    if len(matches) != 1 or matches[0]['sha256'] != proof['planSha256']:
        raise ValueError('CONTEXT_IMPORT_PLAN_PIN')
    rows = [r for r in proof['contexts'] if r['sourcePrefabId'] == parent_id]
    if not rows:
        raise ValueError('CONTEXT_SOURCE_PARENT_MISSING')
    raw = read(instruction, 128 * 1024**2)
    if sha(raw) != proof['planSha256']:
        raise ValueError('CONTEXT_IMPORT_PLAN_CHANGED')
    parent, = [p for p in load(raw,max_nodes=8_000_000)['sourcePrefabs'] if p['sourceId'] == parent_id]
    keys = ('targetPrefabId','targetNodeId','sourceInstanceFileId','sourceDocumentSha256')
    request = dict(planSha256=proof['planSha256'], sourcePrefabId=parent_id,
                   prefabSha256=sha(read(inside(root,parent['path']))),
                   targets=[{k:r[k] for k in keys} for r in rows])
    out = new_output(output,[root,safe(manifest)])
    write_json(out/'context-preview-request.json',request)
    helper = inside(out, str(standard.unity('importer').rsplit('/',1)[0])+'/UnityContextPreview.cs')
    helper.parent.mkdir(parents=True,exist_ok=True)
    helper.write_bytes(files('monkey.targets').joinpath('UnityContextPreview.cs').read_bytes())
    return dict(status='prepared', occurrences=len(rows), entry='MonkeyImporter.CaptureContextPreview',
                request=str(out/'context-preview-request.json'), sourceManifestSha256=proof['sourceManifestSha256'])
