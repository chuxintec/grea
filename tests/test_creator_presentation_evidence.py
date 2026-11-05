import json
import subprocess
from pathlib import Path

from monkey.creator_presentation_evidence import CONTRACT, PHASE, validate_readback


def _sprite_fixture():
    sid = "gameAsset:fixture#3/components/0"
    node_id = "gameAsset:fixture#3"
    plan = {
        "sourceManifestSha256": "a" * 64,
        "nodes": [{"sourceId": node_id, "parent": None, "active": True}],
        "assets": [{"sourceId": "gameAsset:frame", "uuid": "frame-uuid", "kind": "sprite"}],
        "sourcePrefabs": [{"sourceId": "gameAsset:fixture", "path": "assets/gameAsset/fixture.prefab",
                           "nodes": [node_id]}],
        "components": [{"sourceId": sid, "sourcePrefabId": "gameAsset:fixture",
                        "node": node_id, "type": "cc.Sprite", "enabled": True,
                        "spriteFrame": "gameAsset:frame"}],
    }
    evidence = {
        "phase": PHASE, "sourceId": sid, "sourceNodeId": node_id, "sourceType": "cc.Sprite",
        "sourcePrefabId": "gameAsset:fixture", "sourcePrefabUuid": "prefab-uuid",
        "nodeUuid": "node-uuid", "componentUuid": "component-uuid", "nativeType": "cc.Sprite",
        "nodeActiveInHierarchy": True, "componentEnabled": True, "rendererKind": "sprite",
        "renderDataVertexCount": 4, "renderDataIndexCount": 6,
        "sourceSpriteFrameId": "gameAsset:frame", "expectedSpriteFrameUuid": "frame-uuid",
        "actualSpriteFrameUuid": "frame-uuid", "textureUuid": "texture-uuid",
    }
    proof = {"sourceId": sid, "sourceNodeId": node_id, "sourceNodeUuid": "node-uuid",
             "sourcePrefabId": "gameAsset:fixture", "sourcePrefabUuid": "prefab-uuid",
             "componentUuid": "component-uuid", "nativeType": "cc.Sprite", "sourceType": "cc.Sprite",
             "sourceVisible": True, "verified": True, "rendered": True,
             "reasonCode": "saved-renderer-geometry-read", "evidence": evidence}
    readback = {
        "components": [{"sourceId": sid, "type": "cc.Sprite", "nodeUuid": "node-uuid",
                        "componentUuid": "component-uuid", "nativeType": "cc.Sprite", "enabled": True}],
        "nodes": [{"sourceId": node_id, "nodeUuid": "node-uuid", "activeInHierarchy": True}],
        "sourcePrefabs": [{"sourceId": "gameAsset:fixture", "uuid": "prefab-uuid", "path": "assets/gameAsset/fixture.prefab",
                            "components": [sid], "nodes": [{"sourceId": node_id, "nodeUuid": "node-uuid",
                                "activeInHierarchy": True}]}],
        "staticPresentationValidation": {"schemaVersion": 1, "contract": CONTRACT,
            "sourceManifestSha256": plan["sourceManifestSha256"], "phase": PHASE, "components": [proof]},
    }
    return plan, readback, proof, evidence


def test_typed_saved_renderer_evidence_joins_exact_source_component_owner_node_and_geometry():
    plan, readback, _, _ = _sprite_fixture()
    result = validate_readback(plan, readback)
    sid = plan["components"][0]["sourceId"]
    assert result["rowsById"][sid] == {"valid": True, "rendered": True,
                                         "sourceVisible": True, "reason": "verified-rendered"}
    assert result["gaps"] == []


def test_claimed_rendered_flag_cannot_replace_mesh_or_source_asset_observations():
    for mutation in ("empty-mesh", "wrong-frame", "wrong-owner", "wrong-component"):
        plan, readback, proof, evidence = _sprite_fixture()
        if mutation == "empty-mesh":
            evidence["renderDataVertexCount"] = 0
        elif mutation == "wrong-frame":
            evidence["actualSpriteFrameUuid"] = "other-frame"
        elif mutation == "wrong-owner":
            evidence["sourcePrefabUuid"] = "other-prefab"
        else:
            readback["components"][0]["componentUuid"] = "other-component"
        sid = proof["sourceId"]
        result = validate_readback(plan, readback)
        assert result["rowsById"][sid]["valid"] is False
        assert result["rowsById"][sid]["rendered"] is False


def test_saved_readback_producer_observes_real_renderer_geometry_and_emits_into_saved_result():
    repo = Path(__file__).resolve().parents[1]
    script = repo / "src/monkey/targets/CreatorScene.js"
    harness = r'''const fs=require('fs'),vm=require('vm');
const cc={Sprite:function Sprite(){},Label:function Label(){},RichText:function RichText(){},
  js:{getClassName:x=>x.nativeType}};
const stubs={
  './static-richtext.js':{sourceChildren:n=>n.children||[]},
};
const source=fs.readFileSync(process.argv[1],'utf8');
const box={module:{exports:{}},cc,require:name=>name==='cc'?cc:(stubs[name]||{}),
  console,Date,Map,Set,Promise,Error,Number,Object,String,Array,Math,JSON};
vm.runInNewContext(source,box,{filename:process.argv[1]});
const scene=box.module.exports;
const sid='fixture#3/components/0',nodeId='fixture#3';
const renderer={uuid:'component-uuid',nativeType:'cc.Sprite',enabled:true,
 spriteFrame:{_uuid:'frame-uuid',texture:{_uuid:'texture-uuid'}},
 renderData:{vertexCount:4,indexCount:6},_assembler:{updateRenderData(){}}};
const node={uuid:'node-uuid',activeInHierarchy:true,getComponent:type=>type===cc.Sprite?renderer:null};
const plan={sourceManifestSha256:'a'.repeat(64),nodes:[{sourceId:nodeId,parent:null,active:true}],
 assets:[{sourceId:'frame',uuid:'frame-uuid'}],
 components:[{sourceId:sid,node:nodeId,type:'cc.Sprite',enabled:true,spriteFrame:'frame'}]};
const refs=[{sourceId:sid,nodeUuid:'node-uuid',componentUuid:'component-uuid',nativeType:'cc.Sprite',enabled:true}];
const owners=[{sourceId:'fixture',uuid:'prefab-uuid',components:[sid]}];
const result=scene.methods.readStaticPresentation(plan,new Map([[nodeId,node]]),refs,owners);
const out={result,returnedSavedField:source.includes('const staticPresentationValidation=readStaticPresentation(plan,mapped,refs,sourcePrefabs)')&&source.includes('staticPresentationValidation,staticRetainedAssetReadback')};
renderer.renderData.vertexCount=0;
out.zeroGeometry=scene.methods.readStaticPresentation(plan,new Map([[nodeId,node]]),refs,owners).components[0];
renderer.renderData.vertexCount=4;renderer.spriteFrame._uuid='different-frame';
out.wrongFrame=scene.methods.readStaticPresentation(plan,new Map([[nodeId,node]]),refs,owners).components[0];
process.stdout.write(JSON.stringify(out));'''
    result = subprocess.run(["node", "-e", harness, str(script)], check=True, capture_output=True, text=True)
    value = json.loads(result.stdout)
    assert value["returnedSavedField"] is True
    row = value["result"]["components"][0]
    assert value["result"]["contract"] == CONTRACT
    assert row["verified"] is True and row["rendered"] is True
    assert row["evidence"]["renderDataVertexCount"] == 4
    assert value["zeroGeometry"]["rendered"] is False
    assert value["wrongFrame"]["rendered"] is False
