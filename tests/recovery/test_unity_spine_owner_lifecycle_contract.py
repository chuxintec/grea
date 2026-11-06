"""Regression contract for Spine renderer ownership across prefab replacement."""
from pathlib import Path
import hashlib
import json
import os
import pytest


ROOT = Path(__file__).resolve().parents[2]


def _body(source: str, signature: str) -> str:
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:end]


def test_prefab_clone_transfers_only_registered_renderer_before_old_root_destroy():
    source = (ROOT / "src/grea/recovery/targets/UnityStaticSpineRendering.cs").read_text()
    rebind = _body(source, "static partial void RebindOptionalStaticSpineNativeInstanceContext(")
    assert "expected.sourcePrefabId == instance.owner" in rebind
    assert "expected.templateComponentId.StartsWith(instance.template + \"#\"" in rebind
    assert "pair.instanceObject == expected.sourceNodeId" in rebind
    assert "component.sourceId == expected.templateComponentId" in rebind
    assert "templateComponentRows[0].node != pair.templateObject" in rebind
    assert "SPINE_OWNER_LIFECYCLE_TEMPLATE_COMPONENT_NODE_JOIN_INVALID" in rebind
    assert "parent.owner == oldOwner" in rebind
    assert "actualAsset == expectedAsset && oldAsset == expectedAsset" in rebind
    assert "StaticSpineRendererIdentityMatches(newOwner, expected)" in rebind
    assert "StaticSpineCloneCanvasMatchesSource(newOwner" in rebind
    assert "staticSpineNativeInstanceOwners.Remove(previous)" in rebind
    assert "staticSpineRetiredNativeInstanceOwners.Add(transfer.priorOwner)" in rebind
    assert "// Commit only after every mapped owner in this native replacement passed." in rebind

    instances = (ROOT / "src/grea/recovery/targets/UnityPrefabInstances.cs").read_text()
    clone = _body(instances, "static void PrepareNativeInstances(")
    assert clone.index("CopyNativeProperties") < clone.index("RebindOptionalStaticSpineNativeInstanceContext")
    assert clone.index("RebindOptionalStaticSpineNativeInstanceContext") < clone.index("DestroyImmediate(previousRoot)")


def test_source_proof_requires_live_registered_clone_and_saved_pair_release_is_scoped():
    source = (ROOT / "src/grea/recovery/targets/UnityStaticSpineRendering.cs").read_text()
    proof = _body(source, "public static bool TryGetStaticSpineSourceCanvasProof(")
    assert "row.owner == graphic" in proof
    assert "lifecycleOwner.lifecycle.verified" in proof
    assert "lifecycleOwner.sourceEvidence != staticSpineSourceCanvasContext" in proof
    assert "actualGraphic.SkeletonDataAsset != exactDataAsset" in proof
    assert "graphic.transform.IsChildOf(lifecycleOwner.instanceRoot.transform)" in proof
    assert 'contextKind = "native-instance-clone-lifecycle"' in proof

    save_pair = _body(source, "public static void RegisterStaticSpineReadbackOwnerContext(")
    assert "SPINE_READBACK_OWNER_PERSISTENT_ROOT_PATH_OR_IDENTITY_MISMATCH" in save_pair
    assert "SPINE_READBACK_OWNER_PERSISTENT_COMPONENT_PATH_OR_IDENTITY_MISMATCH" in save_pair
    assert "persistentComponents[0].SkeletonDataAsset != dataAsset" in save_pair
    assert "loadedComponents[0].SkeletonDataAsset != dataAsset" in save_pair
    assert "loadedCanvas != host.canvas" in save_pair
    assert "scope.rows.Add" in save_pair
    release = _body(source, "public static void UnregisterStaticSpineReadbackOwnerContext(")
    assert "staticSpineReadbackOwnerScopes.RemoveAll" in release


def test_owner_lifecycle_trace_records_atomic_transfer_and_retired_owner_state():
    source = (ROOT / "src/grea/recovery/targets/UnityStaticSpineRendering.cs").read_text()
    rebind = _body(source, "static partial void RebindOptionalStaticSpineNativeInstanceContext(")
    assert "lifecycle.priorOwnerRegistryRevoked = true" in rebind
    assert "staticSpineRetiredNativeInstanceOwners.Contains" in source
    writer = _body(source, "public static string WriteStaticSpineOwnerContextLifecycleEvidence(")
    assert "priorOwnerRetired" in writer
    assert "priorOwnerRegistryRevoked" in writer
    assert "component.transitions = staticSpineOwnerContextLifecycleRows" in writer
    assert "owner-context-lifecycle.json" in source


def test_actual_native16_spine_component_and_instance_origin_inventory_is_exact_when_supplied():
    inventory_value = os.environ.get("MONKEY_OWNER_LIFECYCLE_INVENTORY")
    import_plan_value = os.environ.get("MONKEY_OWNER_LIFECYCLE_IMPORT_PLAN")
    if not inventory_value or not import_plan_value:
        pytest.skip("set MONKEY_OWNER_LIFECYCLE_INVENTORY and MONKEY_OWNER_LIFECYCLE_IMPORT_PLAN for read-only actual-input joins")
    inventory_path, import_path = Path(inventory_value), Path(import_plan_value)
    before = [(path, hashlib.sha256(path.read_bytes()).hexdigest()) for path in (inventory_path, import_path)]
    inventory, plan = (json.loads(path.read_text(encoding="utf-8")) for path in (inventory_path, import_path))
    components = inventory["sourceComponents"]
    sync = [row for row in components if row.get("syncInstanceOwner")]
    assert len(components) == 75
    assert len(sync) == 36
    assert len(inventory["dataAssetPins"]) == 18

    instances = {(row["owner"], row["root"], row["template"]): row for row in inventory["prefabInstances"]}
    template_components = {}
    for row in plan["components"]:
        template_components.setdefault(row.get("sourceId"), []).append(row)
    origins = {}
    for row in plan["staticAnimationComponentOrigins"]:
        origins.setdefault(row.get("instanceSourceId"), []).append(row)
    for row in sync:
        key = (row["syncInstanceOwner"], row["syncInstanceRoot"], row["syncInstanceTemplate"])
        instance = instances[key]
        node_pairs = [pair for pair in instance["nodePairs"] if pair["instanceObject"] == row["sourceNodeId"]]
        assert len(node_pairs) == 1, row["sourceComponentId"]
        origin_rows = origins[row["sourceComponentId"]]
        assert len(origin_rows) == 1, row["sourceComponentId"]
        assert origin_rows[0]["templateSourceId"] == row["templateComponentId"]
        template_rows = template_components[row["templateComponentId"]]
        assert len(template_rows) == 1, row["templateComponentId"]
        assert template_rows[0]["type"] == "sp.Skeleton"
        assert template_rows[0]["node"] == node_pairs[0]["templateObject"]

    plan_nodes = {row["sourceId"]: row for row in plan["nodes"]}
    mounted_roots = set()
    for instance in plan.get("prefabInstances") or []:
        for group in instance.get("mountedChildren") or []:
            mounted_roots.update(group.get("roots") or [])
    def under_mounted_root(node_id):
        seen = set()
        while node_id and node_id not in seen:
            if node_id in mounted_roots:
                return True
            seen.add(node_id)
            node = plan_nodes.get(node_id)
            node_id = None if node is None else node.get("parent")
        return False
    assert sum(under_mounted_root(row["sourceNodeId"]) for row in components) == 0

    after = [(path, hashlib.sha256(path.read_bytes()).hexdigest()) for path in (inventory_path, import_path)]
    assert after == before, "actual source plan or inventory changed during read-only join checks"
