"""Validate Creator saved-scene renderer observations used by static coverage.

The Creator adapter records observations from the reopened native scene. This
module validates their binding to the frozen plan and to the ordinary native
component/node readbacks; the booleans in a row are never sufficient alone.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import re
import math

CONTRACT = "monkey-creator-saved-renderer-evidence/1"
PHASE = "saved-scene-reopened"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
VISUAL_TYPES = frozenset({
    "cc.Sprite", "cc.Label", "cc.RichText", "cc.LabelOutline", "sp.Skeleton",
    "cc.Graphics", "cc.ParticleSystem", "cc.TiledMap",
})


def _source_visible(component: dict, nodes: dict[str, dict]) -> bool | None:
    kind = component.get("type")
    if kind not in VISUAL_TYPES:
        return False
    if kind == "cc.Sprite":
        if "spriteFrame" not in component:
            return None
        if component.get("spriteFrame") in (None, ""):
            return False
    if component.get("enabled") is False:
        return False
    node_id = component.get("node")
    if not isinstance(node_id, str) or node_id not in nodes:
        return None
    current, seen = node_id, set()
    while current is not None:
        if current in seen:
            return None
        seen.add(current)
        node = nodes.get(current)
        if not isinstance(node, dict) or type(node.get("active")) is not bool:
            return None
        opacity = node.get("opacity")
        if node["active"] is False or (type(opacity) in (int, float) and opacity <= 0):
            return False
        current = node.get("parent")
    return True


def _rows(readback: dict, key: str) -> list[dict]:
    value = readback.get(key)
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def validate_readback(plan: dict, readback: dict) -> dict:
    """Validate complete Creator presentation rows and return ID-keyed results.

    The returned ``rowsById`` values contain ``valid``, ``rendered``,
    ``sourceVisible`` and a stable ``reason``. A missing or malformed row is a
    gap; no source component is removed from the expected denominator.
    """
    gaps: list[dict] = []
    if not isinstance(plan, dict) or not isinstance(readback, dict):
        return {"rowsById": {}, "gaps": [{"code": "CREATOR_PRESENTATION_INPUT_INVALID"}]}
    envelope = readback.get("staticPresentationValidation")
    expected = [row for row in plan.get("components", [])
                if isinstance(row, dict) and row.get("type") in VISUAL_TYPES]
    expected_ids = [row.get("sourceId") for row in expected]
    if (not isinstance(envelope, dict) or envelope.get("schemaVersion") != 1 or
            envelope.get("contract") != CONTRACT or envelope.get("phase") != PHASE or
            not isinstance(plan.get("sourceManifestSha256"), str) or
            not _SHA256.fullmatch(plan["sourceManifestSha256"]) or
            envelope.get("sourceManifestSha256") != plan.get("sourceManifestSha256") or
            not isinstance(envelope.get("components"), list)):
        return {"rowsById": {}, "gaps": [{"code": "CREATOR_PRESENTATION_ENVELOPE_INVALID"}],
                "expectedSourceIds": expected_ids}

    proof_rows = envelope["components"]
    by_id: dict[str, list[dict]] = defaultdict(list)
    for row in proof_rows:
        if isinstance(row, dict) and isinstance(row.get("sourceId"), str):
            by_id[row["sourceId"]].append(row)
    native_by_id: dict[str, list[dict]] = defaultdict(list)
    for row in _rows(readback, "components"):
        sid = row.get("sourceId")
        if isinstance(sid, str):
            native_by_id[sid].append(row)
    node_by_id = {row.get("sourceId"): row for row in _rows(readback, "nodes")
                  if isinstance(row.get("sourceId"), str)}
    source_nodes = {row.get("sourceId"): row for row in plan.get("nodes", [])
                    if isinstance(row, dict) and isinstance(row.get("sourceId"), str)}

    owners: dict[str, list[dict]] = defaultdict(list)
    for owner in _rows(readback, "sourcePrefabs"):
        components = owner.get("components")
        if isinstance(components, list):
            for sid in components:
                if isinstance(sid, str):
                    owners[sid].append(owner)

    rows_by_id: dict[str, dict] = {}
    for component in expected:
        sid = component.get("sourceId")
        reason = "verified-rendered"
        source_visible = _source_visible(component, source_nodes)
        row_matches = by_id.get(sid, [])
        native_matches = native_by_id.get(sid, [])
        evidence = row_matches[0].get("evidence") if len(row_matches) == 1 else None
        valid = bool(sid and len(row_matches) == 1 and len(native_matches) == 1 and
                     isinstance(evidence, dict) and len(owners.get(sid, [])) == 1)
        rendered = False
        if not valid:
            reason = "presentation-or-native-owner-identity-missing-or-ambiguous"
        else:
            proof = row_matches[0]
            native = native_matches[0]
            owner = owners[sid][0]
            node_id = component.get("node")
            target_node = node_by_id.get(node_id)
            owner_id = owner.get("sourceId")
            owner_uuid = owner.get("uuid")
            vertex_count = evidence.get("renderDataVertexCount")
            index_count = evidence.get("renderDataIndexCount")
            numeric_geometry = (type(vertex_count) is int and type(index_count) is int and
                                vertex_count >= 0 and index_count >= 0)
            common = (
                proof.get("sourceType") == component.get("type") and
                proof.get("sourceNodeId") == node_id and proof.get("sourceVisible") is source_visible and
                proof.get("verified") is True and
                proof.get("sourceNodeUuid") == evidence.get("nodeUuid") and
                proof.get("sourcePrefabId") == owner_id and proof.get("sourcePrefabUuid") == owner_uuid and
                proof.get("componentUuid") == evidence.get("componentUuid") and
                proof.get("nativeType") == evidence.get("nativeType") and
                evidence.get("phase") == PHASE and
                evidence.get("sourceId") == sid and evidence.get("sourceNodeId") == node_id and
                evidence.get("sourceType") == component.get("type") and
                evidence.get("sourcePrefabId") == owner_id and evidence.get("sourcePrefabUuid") == owner_uuid and
                evidence.get("nodeUuid") == native.get("nodeUuid") and
                evidence.get("componentUuid") == native.get("componentUuid") and
                evidence.get("nativeType") == native.get("nativeType") and
                evidence.get("nodeUuid") == (target_node or {}).get("nodeUuid") and
                evidence.get("nodeActiveInHierarchy") is (target_node or {}).get("activeInHierarchy") and
                evidence.get("componentEnabled") is native.get("enabled") and
                native.get("type") == component.get("type") and numeric_geometry
            )
            if not common:
                valid = False
                reason = "saved-renderer-observation-does-not-join-native-identity-or-source"
            else:
                renderer_kind = evidence.get("rendererKind")
                if component.get("type") in ("cc.Sprite",):
                    asset_id = component.get("spriteFrame")
                    asset = next((item for item in plan.get("assets", [])
                                  if isinstance(item, dict) and item.get("sourceId") == asset_id), None)
                    expected_uuid = ((asset or {}).get("spriteFrameUuid") or (asset or {}).get("uuid"))
                    rendered = (renderer_kind == "sprite" and source_visible is True and
                                evidence.get("componentEnabled") is True and
                                evidence.get("nodeActiveInHierarchy") is True and
                                isinstance(expected_uuid, str) and expected_uuid and
                                evidence.get("sourceSpriteFrameId") == asset_id and
                                evidence.get("expectedSpriteFrameUuid") == expected_uuid and
                                evidence.get("actualSpriteFrameUuid") == expected_uuid and
                                isinstance(evidence.get("textureUuid"), str) and bool(evidence["textureUuid"]) and
                                vertex_count > 0 and index_count > 0 and proof.get("rendered") is True)
                elif component.get("type") in ("cc.Label", "cc.RichText"):
                    expected_text = component.get("text")
                    rich = component.get("staticRichText")
                    if isinstance(rich, dict):
                        expected_text = rich.get("creatorMarkup", expected_text)
                    expected_text_hash = (hashlib.sha256(expected_text.encode("utf-8")).hexdigest()
                                          if isinstance(expected_text, str) else None)
                    rendered = (renderer_kind == "label" and source_visible is True and
                                evidence.get("componentEnabled") is True and
                                evidence.get("nodeActiveInHierarchy") is True and
                                expected_text_hash is not None and
                                evidence.get("renderedText") == expected_text and
                                hashlib.sha256(str(evidence.get("renderedText", "")).encode("utf-8")).hexdigest() == expected_text_hash and
                                vertex_count > 0 and index_count > 0 and proof.get("rendered") is True)
                elif component.get("type") == "cc.LabelOutline":
                    color = component.get("outlineColor")
                    width = component.get("width")
                    rendered = (renderer_kind == "label-outline" and source_visible is True and
                                evidence.get("componentEnabled") is True and
                                evidence.get("nodeActiveInHierarchy") is True and
                                evidence.get("outlineEnabled") is True and
                                type(width) in (int, float) and evidence.get("outlineWidth") == width and
                                isinstance(color, list) and len(color) == 4 and
                                evidence.get("outlineColor") == color and
                                vertex_count > 0 and index_count > 0 and proof.get("rendered") is True)
                else:
                    # Spine, graphics, particles and tiled maps need their own
                    # source-specific renderer contract; generic mesh counts do
                    # not prove their native drawing semantics.
                    rendered = False
                if source_visible is False:
                    rendered = False
                    # A known invisible source may be structurally verified,
                    # but its source-specific reason and matching target state
                    # must be present.
                    reason = "source-not-visible"
                    reason_code = proof.get("reasonCode")
                    matched_invisibility = (
                        reason_code == "source-node-inactive" and evidence.get("nodeActiveInHierarchy") is False or
                        reason_code == "source-component-disabled" and evidence.get("componentEnabled") is False or
                        reason_code == "source-empty-sprite-frame" and component.get("type") == "cc.Sprite" and
                        evidence.get("actualSpriteFrameUuid") is None
                    )
                    valid = valid and matched_invisibility
                elif source_visible is None:
                    valid = False
                    reason = "source-visibility-unproven"
                elif not rendered:
                    valid = False
                    reason = "saved-renderer-geometry-or-source-reference-unverified"
        rows_by_id[sid] = {"valid": valid, "rendered": rendered,
                           "sourceVisible": source_visible, "reason": reason}
        if not valid:
            gaps.append({"code": "CREATOR_STATIC_PRESENTATION_EVIDENCE_INVALID", "sourceId": sid,
                         "reason": reason})

    unknown = sorted(set(by_id) - set(expected_ids))
    missing = sorted(set(expected_ids) - set(by_id))
    if unknown:
        gaps.append({"code": "CREATOR_PRESENTATION_SOURCE_ID_UNKNOWN", "sourceIds": unknown})
    if missing:
        gaps.append({"code": "CREATOR_PRESENTATION_SOURCE_ID_MISSING", "sourceIds": missing})
    if len(proof_rows) != len(expected_ids) or len(set(expected_ids)) != len(expected_ids):
        gaps.append({"code": "CREATOR_PRESENTATION_DENOMINATOR_MISMATCH",
                     "expectedCount": len(expected_ids), "actualCount": len(proof_rows)})
    return {"rowsById": rows_by_id, "gaps": gaps, "expectedSourceIds": expected_ids}
