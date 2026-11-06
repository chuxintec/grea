from monkey.creator_presentation_evidence import CONTRACT, PHASE
from monkey.prefab_component_coverage import assess


def _creator_sprite_fixture():
    sid = "gameAsset:fixture#3/components/0"
    node = "gameAsset:fixture#3"
    owner = "gameAsset:fixture"
    digest = "a" * 64
    plan = {
        "sourceManifestSha256": digest,
        "nodes": [{"sourceId": node, "parent": None, "active": True}],
        "sourcePrefabs": [{"sourceId": owner, "path": "Assets/fixture.prefab", "nodes": [node]}],
        "assets": [{"sourceId": "gameAsset:frame", "uuid": "frame-uuid", "kind": "sprite"}],
        "components": [{"sourceId": sid, "sourcePrefabId": owner, "node": node,
                        "type": "cc.Sprite", "nativeType": "cc.Sprite", "enabled": True,
                        "spriteFrame": "gameAsset:frame"}],
    }
    proof = {
        "sourceId": sid, "sourceNodeId": node, "sourceNodeUuid": "node-uuid",
        "sourcePrefabId": owner, "sourcePrefabUuid": "prefab-uuid", "componentUuid": "component-uuid",
        "nativeType": "cc.Sprite", "sourceType": "cc.Sprite", "sourceVisible": True,
        "verified": True, "rendered": True, "reasonCode": "saved-renderer-geometry-read",
        "evidence": {
            "phase": PHASE, "sourceId": sid, "sourceNodeId": node, "sourceType": "cc.Sprite",
            "sourcePrefabId": owner, "sourcePrefabUuid": "prefab-uuid", "nodeUuid": "node-uuid",
            "componentUuid": "component-uuid", "nativeType": "cc.Sprite",
            "nodeActiveInHierarchy": True, "componentEnabled": True, "rendererKind": "sprite",
            "renderDataVertexCount": 4, "renderDataIndexCount": 6,
            "sourceSpriteFrameId": "gameAsset:frame", "expectedSpriteFrameUuid": "frame-uuid",
            "actualSpriteFrameUuid": "frame-uuid", "textureUuid": "texture-uuid",
        },
    }
    readback = {
        "components": [{"sourceId": sid, "type": "cc.Sprite", "nativeType": "cc.Sprite",
                        "nodeUuid": "node-uuid", "componentUuid": "component-uuid", "enabled": True,
                        "persistent": True, "sourceIdentityVerified": True}],
        "nodes": [{"sourceId": node, "nodeUuid": "node-uuid", "activeInHierarchy": True}],
        "sourcePrefabs": [{"sourceId": owner, "uuid": "prefab-uuid", "components": [sid]}],
        "staticPresentationValidation": {"schemaVersion": 1, "contract": CONTRACT,
            "sourceManifestSha256": digest, "phase": PHASE, "components": [proof]},
    }
    return plan, readback


def test_creator_coverage_uses_typed_saved_renderer_identity_owner_and_geometry():
    plan, readback = _creator_sprite_fixture()
    result = assess(plan, readback, "creator")
    assert result["nativeStaticValidation"] == "pass"
    assert result["staticPresentationValidation"]["status"] == "pass"
    assert result["components"][0]["nativeComponentReadback"]["componentUuid"] == "component-uuid"
    assert result["playerValidation"] == "not_run"


def test_creator_boolean_summary_without_exact_saved_owner_proof_stays_partial():
    plan, readback = _creator_sprite_fixture()
    readback["sourcePrefabs"] = []
    readback["staticPresentationValidation"]["components"][0].update(
        verified=True, rendered=True, sourceVisible=True)
    result = assess(plan, readback, "creator")
    assert result["nativeStaticValidation"] != "pass"
    assert result["staticPresentationValidation"]["status"] != "pass"
    assert any(row["code"] == "CREATOR_COMPONENT_OWNER_IDENTITY_INVALID" for row in result["diagnostics"])
    assert any(row["code"] == "CREATOR_STATIC_PRESENTATION_EVIDENCE_INVALID" for row in result["diagnostics"])


def test_creator_unknown_presentation_source_id_cannot_be_hidden_by_pass_summary():
    plan, readback = _creator_sprite_fixture()
    readback["staticPresentationValidation"]["components"].append({
        "sourceId": "gameAsset:unknown#9/components/0", "sourceNodeId": "node-missing",
        "sourceType": "cc.Sprite", "verified": True, "rendered": True,
        "sourceVisible": True, "evidence": {},
    })
    result = assess(plan, readback, "creator")
    assert result["nativeStaticValidation"] == "pass"
    assert result["staticPresentationValidation"]["status"] == "partial"
    assert any(row["code"] == "CREATOR_PRESENTATION_SOURCE_ID_UNKNOWN" for row in result["diagnostics"])
