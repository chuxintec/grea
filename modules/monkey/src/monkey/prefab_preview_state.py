"""Validate and freeze declarative, source-backed static preview operations."""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from pathlib import Path

from . import io


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_KINDS = {"node.active", "node.scale", "label.text", "sprite.asset", "node.opacity", "label.fontSize", "label.lineHeight", "progress.value"}


class PreviewStateError(ValueError):
    """Invalid state, source value, reference, or evidence receipt."""


def _nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise PreviewStateError(f"{label} must be a non-empty string")
    return value


def _json_equal(left, right):
    if type(left) is not type(right):
        if type(left) in (int, float) and type(right) in (int, float):
            return math.isfinite(left) and math.isfinite(right) and left == right
        return False
    if isinstance(left, float):
        return math.isfinite(left) and math.isfinite(right) and left == right
    if isinstance(left, list):
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_json_equal(left[key], right[key]) for key in left)
    return left == right


def _vector(value, label):
    if (not isinstance(value, list) or len(value) != 3 or
            any(type(number) not in (int, float) or not math.isfinite(number) for number in value)):
        raise PreviewStateError(f"{label} must be a finite three-number vector")
    return list(value)


def prepare(state_path, expected_sha, plan, out):
    """Verify a complete state/evidence set against a native target plan.

    The generated ``preview-state.json`` is an immutable, target-neutral
    contract. It does not interpret source scripts or infer product values.
    """
    state_path = io.safe(state_path)
    if not isinstance(expected_sha, str) or not _SHA256.fullmatch(expected_sha):
        raise PreviewStateError("expected_sha must be a lowercase SHA-256 digest")
    try:
        state_raw = io.read(state_path)
    except Exception as error:
        raise PreviewStateError(f"state file is missing or unreadable: {state_path}") from error
    state_sha = io.sha(state_raw)
    if state_sha != expected_sha:
        raise PreviewStateError("state file SHA-256 differs from expected_sha")
    state = io.load(state_raw, max_nodes=200_000, max_depth=64)
    if not isinstance(state, Mapping) or state.get("schemaVersion") != 1:
        raise PreviewStateError("expected preview state schemaVersion 1")
    if not isinstance(plan, Mapping):
        raise PreviewStateError("plan must be a mapping")

    state_id = _nonempty(state.get("id"), "state.id")
    prefab_id = _nonempty(state.get("sourcePrefabId"), "state.sourcePrefabId")
    manifest_sha = state.get("sourceManifestSha256")
    if not isinstance(manifest_sha, str) or not _SHA256.fullmatch(manifest_sha):
        raise PreviewStateError("state.sourceManifestSha256 must be a lowercase SHA-256 digest")
    if manifest_sha != plan.get("sourceManifestSha256"):
        raise PreviewStateError("state sourceManifestSha256 differs from plan")
    source_version = _nonempty(state.get("sourceVersion"), "state.sourceVersion")
    reference_version = _nonempty(state.get("referenceVersion"), "state.referenceVersion")
    if isinstance(plan.get("sourceVersion"), str) and plan["sourceVersion"] != source_version:
        raise PreviewStateError("state sourceVersion differs from plan")

    nodes = plan.get("nodes")
    components = plan.get("components")
    if not isinstance(nodes, list) or not isinstance(components, list):
        raise PreviewStateError("plan nodes and components must be arrays")
    node_by_id = {}
    for node in nodes:
        if not isinstance(node, Mapping) or not isinstance(node.get("sourceId"), str):
            raise PreviewStateError("plan contains a node without a sourceId")
        if node["sourceId"] in node_by_id:
            raise PreviewStateError(f"duplicate plan node sourceId: {node['sourceId']}")
        node_by_id[node["sourceId"]] = node
    component_by_id = {}
    for component in components:
        if not isinstance(component, Mapping) or not isinstance(component.get("sourceId"), str):
            raise PreviewStateError("plan contains a component without a sourceId")
        if component["sourceId"] in component_by_id:
            raise PreviewStateError(f"duplicate plan component sourceId: {component['sourceId']}")
        component_by_id[component["sourceId"]] = component
    core_node_ids = {sid for sid in node_by_id if sid.startswith(prefab_id + "#")}
    if not core_node_ids:
        raise PreviewStateError("sourcePrefabId is absent from plan nodes")
    core_component_ids = {sid for sid, component in component_by_id.items()
                          if component.get("node") in core_node_ids}
    source_prefabs = plan.get("sourcePrefabs", [])
    if source_prefabs and not any(isinstance(prefab, Mapping) and prefab.get("sourceId") == prefab_id
                                  for prefab in source_prefabs):
        raise PreviewStateError("sourcePrefabId is absent from plan sourcePrefabs")
    asset_ids = set()
    for collection, key in ((plan.get("assets", []), "sourceId"), (plan.get("assets", []), "id"),
                            (plan.get("textures", []), "id"), (plan.get("spriteFrames", []), "sourceId")):
        if not isinstance(collection, list):
            continue
        asset_ids.update(item[key] for item in collection
                         if isinstance(item, Mapping) and isinstance(item.get(key), str) and item[key])

    evidence = state.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise PreviewStateError("state.evidence must contain at least one hashed evidence file")
    evidence_by_id = {}
    evidence_paths = []
    evidence_rows = []
    for row in evidence:
        if not isinstance(row, Mapping):
            raise PreviewStateError("evidence row must be an object")
        evidence_id = _nonempty(row.get("id"), "evidence.id")
        path = row.get("path")
        digest = row.get("sha256")
        if not isinstance(path, str) or not path or Path(path).is_absolute():
            raise PreviewStateError(f"evidence {evidence_id} path must be relative to the state file")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise PreviewStateError(f"evidence {evidence_id} has an invalid SHA-256")
        if evidence_id in evidence_by_id:
            raise PreviewStateError(f"duplicate evidence id: {evidence_id}")
        try:
            evidence_path = io.inside(state_path.parent, path)
            raw = io.read(evidence_path)
        except Exception as error:
            raise PreviewStateError(f"evidence file is missing or unreadable: {evidence_id}") from error
        if io.sha(raw) != digest:
            raise PreviewStateError(f"evidence file SHA-256 mismatch: {evidence_id}")
        evidence_by_id[evidence_id] = row
        evidence_paths.append(evidence_path)
        evidence_rows.append({"id": evidence_id, "path": path, "sha256": digest})

    operations = state.get("operations")
    if not isinstance(operations, list) or not operations:
        raise PreviewStateError("state.operations must be a non-empty array")
    output_ops = []
    seen_ops = set()
    for operation in operations:
        if not isinstance(operation, Mapping):
            raise PreviewStateError("operation row must be an object")
        if "expectedValue" not in operation or "value" not in operation:
            raise PreviewStateError("operation must include expectedValue and value")
        kind = operation.get("kind")
        if kind not in _KINDS:
            raise PreviewStateError(f"unsupported preview operation kind: {kind!r}")
        source_id = _nonempty(operation.get("sourceId"), f"{kind}.sourceId")
        evidence_id = _nonempty(operation.get("evidenceId"), f"{kind}.evidenceId")
        if evidence_id not in evidence_by_id:
            raise PreviewStateError(f"operation references missing evidence id: {evidence_id}")
        identity = (kind, source_id)
        if identity in seen_ops:
            raise PreviewStateError(f"duplicate preview operation for {kind} / {source_id}")
        seen_ops.add(identity)
        expected = operation.get("expectedValue")
        value = operation.get("value")
        result = {"kind": kind, "sourceId": source_id, "evidenceId": evidence_id}
        if kind == "node.active":
            if source_id not in core_node_ids:
                raise PreviewStateError(f"node.active target is outside source prefab: {source_id}")
            source_value = node_by_id[source_id].get("active")
            if type(expected) is not bool or type(value) is not bool:
                raise PreviewStateError("node.active expectedValue/value must be bool")
            if type(source_value) is not bool or not _json_equal(expected, source_value):
                raise PreviewStateError(f"node.active expectedValue differs from source plan: {source_id}")
            result.update(boolValue=value, expectedBoolValue=expected)
        elif kind == "node.scale":
            if source_id not in core_node_ids:
                raise PreviewStateError(f"node.scale target is outside source prefab: {source_id}")
            source_value = node_by_id[source_id].get("scale")
            expected = _vector(expected, "node.scale expectedValue")
            value = _vector(value, "node.scale value")
            source_value = _vector(source_value, "plan node scale")
            if not _json_equal(expected, source_value):
                raise PreviewStateError(f"node.scale expectedValue differs from source plan: {source_id}")
            result.update(vectorValue=value, expectedVectorValue=expected)
        elif kind in ("node.opacity","label.fontSize","label.lineHeight","progress.value"):
            if kind=="node.opacity":
                if source_id not in core_node_ids:raise PreviewStateError("opacity target outside prefab")
                source_value=node_by_id[source_id]['opacity'];low,high=0,255
            else:
                if source_id not in core_component_ids:raise PreviewStateError("numeric target outside prefab")
                component=component_by_id[source_id]
                types=('cc.ProgressBar',)if kind=='progress.value'else('cc.Label','cc.RichText')
                if component['type']not in types:raise PreviewStateError("numeric target type differs")
                key='progress'if kind=='progress.value'else kind.split('.')[1]
                source_value=component[key];low,high=(0,1)if key=='progress'else(0.001,4096)
            if any(type(v)not in(int,float)or not math.isfinite(v)or not low<=v<=high for v in(expected,value)):
                raise PreviewStateError("numeric preview value outside supported bounds")
            if not _json_equal(expected,source_value):raise PreviewStateError("numeric expectedValue differs from source")
            result.update(numberValue=value,expectedNumberValue=expected)
        elif kind == "label.text":
            if source_id not in core_component_ids:
                raise PreviewStateError(f"label.text target is outside source prefab: {source_id}")
            component = component_by_id[source_id]
            if component.get("type") not in ("cc.Label","cc.RichText"):
                raise PreviewStateError(f"label.text target is not a source text component: {source_id}")
            source_value = component.get("text")
            if not isinstance(expected, str) or not isinstance(value, str) or not isinstance(source_value, str):
                raise PreviewStateError("label.text expectedValue/value/source must be strings")
            if expected != source_value:
                raise PreviewStateError(f"label.text expectedValue differs from source plan: {source_id}")
            result.update(stringValue=value, expectedStringValue=expected)
        else:
            if source_id not in core_component_ids:
                raise PreviewStateError(f"sprite.asset target is outside source prefab: {source_id}")
            component = component_by_id[source_id]
            if component.get("type") != "cc.Sprite":
                raise PreviewStateError(f"sprite.asset target is not a source cc.Sprite: {source_id}")
            source_value = component.get("spriteFrame")
            if value is not None and (not isinstance(value, str) or value not in asset_ids):
                raise PreviewStateError("sprite.asset value must be an existing plan asset sourceId")
            if expected is not None and (not isinstance(expected, str) or expected not in asset_ids):
                raise PreviewStateError("sprite.asset expectedValue must be null or an existing plan asset sourceId")
            if not _json_equal(expected, source_value):
                raise PreviewStateError(f"sprite.asset expectedValue differs from source plan: {source_id}")
            if not isinstance(source_value, str) and source_value is not None:
                raise PreviewStateError(f"sprite.asset source plan value is malformed: {source_id}")
            result.update(assetId=value, expectedAssetId=expected, sourceEnabled=component_by_id[source_id].get("enabled", True) and value is not None)
            if str(plan.get('targetProfile','')).startswith('unity'):
                texture_ids={t['id']for t in plan['textures']}
                def view(asset):
                    if asset is None:return None
                    desired=asset+('@original'if not component.get('trim',True)else '')
                    if desired not in texture_ids:raise PreviewStateError('preview sprite view absent: '+desired)
                    return desired
                result.update(nativeAssetId=view(value),nativeExpectedAssetId=view(expected))
        output_ops.append(result)

    spec = {"schemaVersion": 1, "stateId": state_id, "sourcePrefabId": prefab_id,
            "sourceManifestSha256": manifest_sha, "sourceVersion": source_version,
            "referenceVersion": reference_version, "stateSha256": state_sha,
            "evidence": evidence_rows, "operations": output_ops}
    output = io.new_output(out, [state_path, *evidence_paths])
    io.write_json(output / "preview-state.json", spec)
    return spec


def attach(plan_path, state_path, expected_sha, out):
    """Produce a fresh owned target plan carrying a verified preview state."""
    from .output_limits import copy_verified
    plan_path=io.safe(plan_path);plan=io.stage_document(plan_path)
    target=io.new_output(out,[plan_path.parent,io.safe(state_path)])
    for item in io.stage_manifest(plan_path.parent)['files']:
        if item['path']=='plan.json':continue
        copy_verified(io.inside(plan_path.parent,item['path']),io.inside(target,item['path']),item['sha256'],item['bytes'])
    previous=plan.get('previewStates') or ([plan['previewState']] if plan.get('previewState') else [])
    if any(s['stateSha256']==expected_sha for s in previous):
        raise PreviewStateError('preview state already attached')
    state=prepare(state_path,expected_sha,plan,target/'preview-states'/expected_sha[:16])
    plan['previewStates']=[*previous,state]
    plan['previewState']=state
    io.write_json(target/'plan.json',plan)
    return io.finish(target,plan)


def attach_clones(plan_path, state_sha256, batch_paths, expected_batch_sha256, out):
    """Attach hash-pinned prepared clone batches to one existing preview state.

    The original state digest is retained; each batch carries its independent
    source/plan digest, and the resulting owned plan has its own stage digest.
    """
    from copy import deepcopy
    from .output_limits import copy_verified
    from .prefab_preview_clones import validate_clone_batch
    plan_path = io.safe(plan_path)
    plan = io.stage_document(plan_path)
    if not batch_paths or len(batch_paths) != len(expected_batch_sha256):
        raise PreviewStateError('clone batch paths and hashes must be nonempty and paired')
    states = plan.get('previewStates') or ([plan['previewState']] if plan.get('previewState') else [])
    matched = [s for s in states if s['stateSha256'] == state_sha256]
    if len(matched) != 1 or matched[0].get('cloneBatches'):
        raise PreviewStateError('clone target state must exist exactly once and have no batches')
    batches = []
    parent_ids = set()
    for path, digest in zip(batch_paths, expected_batch_sha256):
        raw = io.read(io.safe(path))
        if io.sha(raw) != digest:
            raise PreviewStateError('clone batch hash differs')
        batch = io.load(raw, max_nodes=1_000_000)
        validate_clone_batch(batch, plan)
        if batch['sourcePlanSha256'] != io.sha(io.stage_bytes(plan_path)):
            raise PreviewStateError('clone batch was prepared against a different plan')
        if batch['sourcePrefabId'] != matched[0]['sourcePrefabId']:
            raise PreviewStateError('clone batch owner differs from preview state')
        parent = batch['template']['parentSourceId']
        if parent in parent_ids:
            raise PreviewStateError('clone batches overlap the same parent')
        parent_ids.add(parent)
        batch = deepcopy(batch)
        batch['preparedBatchSha256'] = digest
        batches.append(batch)
    target = io.new_output(out, [plan_path.parent, *[io.safe(p).parent for p in batch_paths]])
    for item in io.stage_manifest(plan_path.parent)['files']:
        if item['path'] != 'plan.json':
            copy_verified(io.inside(plan_path.parent, item['path']), io.inside(target, item['path']), item['sha256'], item['bytes'])
    matched[0]['cloneBatches'] = batches
    plan['previewStates'] = states
    if plan.get('previewState', {}).get('stateSha256') == state_sha256:
        plan['previewState'] = matched[0]
    for i, batch in enumerate(batches):
        io.write_json(target / 'preview-clones' / state_sha256 / f'{i:03d}.json', batch)
    io.write_json(target / 'plan.json', plan)
    return io.finish(target, plan)


def replace_state(plan_path, expected_plan_sha, prior_state_sha, state_path, expected_state_sha, out):
    """Derive a fresh candidate state without modifying the prior owned stage."""
    from copy import deepcopy
    from .output_limits import copy_verified
    from .prefab_preview_clones import validate_clone_batch
    plan_path=io.safe(plan_path)
    if io.sha(io.stage_bytes(plan_path)) != expected_plan_sha:
        raise PreviewStateError('replacement source plan hash differs')
    plan=io.stage_document(plan_path)
    states=plan.get('previewStates') or ([plan['previewState']] if plan.get('previewState') else [])
    indexes=[i for i,state in enumerate(states) if state['stateSha256']==prior_state_sha]
    if len(indexes)!=1:
        raise PreviewStateError('replacement requires exactly one existing state')
    previous=states[indexes[0]]
    target=io.new_output(out,[plan_path.parent,io.safe(state_path)])
    for item in io.stage_manifest(plan_path.parent)['files']:
        if item['path']!='plan.json':
            copy_verified(io.inside(plan_path.parent,item['path']),io.inside(target,item['path']),item['sha256'],item['bytes'])
    state=prepare(state_path,expected_state_sha,plan,target/'preview-states'/expected_state_sha[:16])
    if state['sourcePrefabId']!=previous['sourcePrefabId']:
        raise PreviewStateError('replacement must retain the source prefab')
    batches=deepcopy(previous.get('cloneBatches',[]))
    for batch in batches:validate_clone_batch(batch,plan)
    if batches:state['cloneBatches']=batches
    state['replacementEvidence']={'previousStateSha256':prior_state_sha,'parentPlanSha256':expected_plan_sha,
        'cloneBatchesRetained':True,'sourceGraphChanged':False}
    states[indexes[0]]=state;plan['previewStates']=states
    if plan.get('previewState',{}).get('stateSha256')==prior_state_sha:plan['previewState']=state
    io.write_json(target/'plan.json',plan)
    return io.finish(target,plan)


def attach_sprite_projection(plan_path, state_sha256, projection_path, expected_sha256, out):
    """Bind a verified source construction recipe to one static preview."""
    from .output_limits import copy_verified
    plan_path=io.safe(plan_path);plan=io.stage_document(plan_path)
    raw=io.read(io.safe(projection_path))
    if io.sha(raw)!=expected_sha256:
        raise PreviewStateError('sprite projection hash differs')
    projection=io.load(raw)
    if (projection.get('schema')!='monkey-prefab-static-sprite-projection-plan/1' or
        projection.get('sourcePlanSha256')!=io.sha(io.stage_bytes(plan_path)) or
        projection.get('sourceManifestSha256')!=plan.get('sourceManifestSha256')):
        raise PreviewStateError('sprite projection source plan differs')
    states=plan.get('previewStates')or[]
    matches=[s for s in states if s['stateSha256']==state_sha256]
    if len(matches)!=1 or matches[0].get('spriteProjection'):
        raise PreviewStateError('projection target state must exist once and be unbound')
    state=matches[0]
    if projection.get('sourcePrefabId')!=state['sourcePrefabId']:
        raise PreviewStateError('projection source prefab differs')
    entries=projection.get('entries')or[]
    nodes={n['sourceId']:n for n in plan['nodes']}
    clone_parents={b['template']['parentSourceId']for b in state.get('cloneBatches',[])}
    parents=set()
    for entry in entries:
        parent=entry['parentSourceId']
        if (not entry.get('targetResourceBound') or parent not in nodes or parent in parents or parent in clone_parents or
            nodes[parent]['children']!=[] or entry['expectedParentChildSourceIds']!=[]):
            raise PreviewStateError('projection requires a unique resource-bound empty source parent')
        parents.add(parent)
    if not entries:raise PreviewStateError('projection cannot be empty')
    target=io.new_output(out,[plan_path.parent,io.safe(projection_path)])
    for item in io.stage_manifest(plan_path.parent)['files']:
        if item['path']!='plan.json':copy_verified(io.inside(plan_path.parent,item['path']),io.inside(target,item['path']),item['sha256'],item['bytes'])
    state['spriteProjection']=projection
    if plan.get('previewState',{}).get('stateSha256')==state_sha256:plan['previewState']=state
    io.write_json(target/'sprite-projections'/f'{expected_sha256}.json',projection)
    io.write_json(target/'plan.json',plan);return io.finish(target,plan)
