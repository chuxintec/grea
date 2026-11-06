import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from monkey.prefab_preview_state import PreviewStateError, prepare


def fixture(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    evidence_path = root / "reference-state.txt"
    evidence_path.write_text("independent reference capture\n")
    evidence_sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    manifest_sha = "a" * 64
    prefab = "bundle:prefab-1"
    label_id = prefab + "#2/components/0"
    sprite_id = prefab + "#2/components/1"
    plan = {
        "sourceManifestSha256": manifest_sha,
        "sourcePrefabs": [{"sourceId": prefab}],
        "nodes": [
            {"sourceId": prefab + "#1", "active": True, "scale": [1.0, 1.0, 1.0]},
            {"sourceId": prefab + "#2", "active": False, "scale": [1.0, 1.0, 1.0]},
        ],
        "components": [
            {"sourceId": label_id, "node": prefab + "#2", "type": "cc.Label", "text": "Before"},
            {"sourceId": sprite_id, "node": prefab + "#2", "type": "cc.Sprite", "spriteFrame": "bundle:sprite-old"},
        ],
        "assets": [{"sourceId": "bundle:sprite-old"}, {"sourceId": "bundle:sprite-new"}],
    }
    state = {
        "schemaVersion": 1,
        "id": "state-neutral-01",
        "sourcePrefabId": prefab,
        "sourceManifestSha256": manifest_sha,
        "sourceVersion": "2.4.15",
        "referenceVersion": "2.4.15-reference-capture",
        "evidence": [{"id": "capture-1", "path": evidence_path.name, "sha256": evidence_sha}],
        "operations": [
            {"kind": "node.active", "sourceId": prefab + "#2", "expectedValue": False,
             "value": True, "evidenceId": "capture-1"},
            {"kind": "node.scale", "sourceId": prefab + "#2", "expectedValue": [1.0, 1.0, 1.0],
             "value": [0.75, 0.75, 0.75], "evidenceId": "capture-1"},
            {"kind": "label.text", "sourceId": label_id, "expectedValue": "Before",
             "value": "Reference", "evidenceId": "capture-1"},
            {"kind": "sprite.asset", "sourceId": sprite_id, "expectedValue": "bundle:sprite-old",
             "value": "bundle:sprite-new", "evidenceId": "capture-1"},
        ],
    }
    state_path = root / "state.json"
    state_raw = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode()
    state_path.write_bytes(state_raw)
    return state_path, hashlib.sha256(state_raw).hexdigest(), plan, state, manifest_sha


class PrefabPreviewStateTests(unittest.TestCase):
    def test_prepare_validates_and_serializes_all_supported_operations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            state_path, digest, plan, original_plan, manifest_sha = fixture(root)
            plan_before = copy.deepcopy(plan)
            out = root / "candidate"
            spec = prepare(state_path, digest, plan, out)
            self.assertEqual(spec["schemaVersion"], 1)
            self.assertEqual(spec["sourceManifestSha256"], manifest_sha)
            self.assertEqual(spec["sourceVersion"], "2.4.15")
            self.assertEqual(spec["referenceVersion"], "2.4.15-reference-capture")
            self.assertEqual(len(spec["evidence"]), 1)
            self.assertEqual(spec["stateSha256"], digest)
            self.assertEqual(len(spec["operations"]), 4)
            self.assertEqual(spec["operations"][0]["expectedBoolValue"], False)
            self.assertEqual(spec["operations"][0]["boolValue"], True)
            self.assertEqual(spec["operations"][1]["vectorValue"], [0.75, 0.75, 0.75])
            self.assertEqual(spec["operations"][1]["expectedVectorValue"], [1.0, 1.0, 1.0])
            self.assertEqual(spec["operations"][2]["stringValue"], "Reference")
            self.assertEqual(spec["operations"][3]["assetId"], "bundle:sprite-new")
            self.assertEqual(spec["operations"][3]["expectedAssetId"], "bundle:sprite-old")
            self.assertEqual(plan, plan_before)
            saved = json.loads((out / "preview-state.json").read_text())
            self.assertEqual(saved, spec)

    def test_bad_state_hash_evidence_or_manifest_binding_fails_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            state_path, digest, plan, state, _ = fixture(root)
            out = root / "bad-hash"
            with self.assertRaises(PreviewStateError):
                prepare(state_path, "0" * 64, plan, out)
            self.assertFalse(out.exists())
            state["sourceManifestSha256"] = "b" * 64
            state_path.write_text(json.dumps(state, separators=(",", ":")))
            digest = hashlib.sha256(state_path.read_bytes()).hexdigest()
            with self.assertRaises(PreviewStateError):
                prepare(state_path, digest, plan, root / "wrong-manifest")
            self.assertFalse((root / "wrong-manifest").exists())

    def test_wrong_expected_value_outside_scope_and_missing_asset_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            state_path, digest, plan, state, _ = fixture(root)
            state["operations"][0]["expectedValue"] = True
            state_path.write_text(json.dumps(state, separators=(",", ":")))
            digest = hashlib.sha256(state_path.read_bytes()).hexdigest()
            with self.assertRaises(PreviewStateError):
                prepare(state_path, digest, plan, root / "wrong-value")

            state["operations"][0]["expectedValue"] = False
            state["operations"][0]["sourceId"] = "bundle:other#1"
            state_path.write_text(json.dumps(state, separators=(",", ":")))
            digest = hashlib.sha256(state_path.read_bytes()).hexdigest()
            with self.assertRaises(PreviewStateError):
                prepare(state_path, digest, plan, root / "outside")

            state["operations"][0]["sourceId"] = "bundle:prefab-1#2"
            state["operations"][3]["value"] = "bundle:missing"
            state_path.write_text(json.dumps(state, separators=(",", ":")))
            digest = hashlib.sha256(state_path.read_bytes()).hexdigest()
            with self.assertRaises(PreviewStateError):
                prepare(state_path, digest, plan, root / "missing-asset")

    def test_evidence_digest_and_operation_identity_are_mandatory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            state_path, digest, plan, state, _ = fixture(root)
            (root / "reference-state.txt").write_text("changed after capture")
            with self.assertRaises(PreviewStateError):
                prepare(state_path, digest, plan, root / "changed-evidence")
            self.assertFalse((root / "changed-evidence").exists())

            state_path, digest, plan, state, _ = fixture(root / "duplicate-case")
            state["operations"].append(dict(state["operations"][0]))
            state_path.write_text(json.dumps(state, separators=(",", ":")))
            digest = hashlib.sha256(state_path.read_bytes()).hexdigest()
            with self.assertRaises(PreviewStateError):
                prepare(state_path, digest, plan, root / "duplicate-operation")

    def test_creator_helper_applies_reads_and_rejects_reentry_without_business_code(self):
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("Node.js unavailable")
        helper = Path("src/monkey/targets/CreatorPreviewState.js").resolve()
        source = r'''const Module=require('module'),original=Module._load;
class Component{constructor(node){this.node=node;this.enabled=true}}
class Vec3{constructor(x=0,y=0,z=0){this.x=x;this.y=y;this.z=z}}
class Node{constructor(){this.active=false;this.scale=new Vec3(1,1,1);this.scene={};this.children=[];this.components=[];this.isValid=true}
add(c){this.components.push(c);return c}getComponents(){return this.components}getComponent(T){return this.components.find(c=>c instanceof T)||null}setScale(v){this.scale=v}}
class Scene extends Node{}
class Label extends Component{constructor(n){super(n);this.string='Before'}} class Sprite extends Component{constructor(n){super(n);this.spriteFrame=null}} class SpriteFrame{}
const names=new Map([[Node,'cc.Node'],[Label,'cc.Label'],[Sprite,'cc.Sprite'],[SpriteFrame,'cc.SpriteFrame']]);
Module._load=function(req){if(req==='cc')return{Node,Scene,Component,Label,Sprite,SpriteFrame,Vec3,js:{getClassName:C=>names.get(C)||C.name}};return original.apply(this,arguments)};
const api=require(process.argv[1]),hash='a'.repeat(64),p='bundle:prefab',nodeId=p+'#2',labelId=p+'#2/components/0',spriteId=p+'#2/components/1';
const node=new Node(),label=node.add(new Label(node)),sprite=node.add(new Sprite(node)),oldFrame=new SpriteFrame(),newFrame=new SpriteFrame();sprite.spriteFrame=oldFrame;node.parent=new Scene();
const refs={[nodeId]:node,[labelId]:label,[spriteId]:sprite,'bundle:sprite-old':oldFrame,'bundle:sprite-new':newFrame};
const spec={schemaVersion:1,stateId:'neutral',sourcePrefabId:p,sourceManifestSha256:hash,stateSha256:hash,sourceVersion:'source-v',referenceVersion:'reference-v',evidence:[{id:'e',path:'proof.txt',sha256:hash}],operations:[
{kind:'node.active',sourceId:nodeId,expectedBoolValue:false,boolValue:true,evidenceId:'e'},
{kind:'node.scale',sourceId:nodeId,expectedVectorValue:[1,1,1],vectorValue:[.75,.75,.75],evidenceId:'e'},
{kind:'label.text',sourceId:labelId,expectedStringValue:'Before',stringValue:'Reference',evidenceId:'e'},
{kind:'sprite.asset',sourceId:spriteId,expectedAssetId:'bundle:sprite-old',assetId:'bundle:sprite-new',sourceEnabled:true,evidenceId:'e'}]};
const result=api.Apply(spec,id=>refs[id]);if(!result.applied||!result.verified||result.businessBehaviorComplete||!node.active||label.string!=='Reference'||sprite.spriteFrame!==newFrame)throw Error('apply/readback failed');
label.string='unexpected';let rejected=false;try{api.Apply(spec,id=>refs[id])}catch(e){rejected=/PREVIEW_STATE_REENTRY_MISMATCH/.test(e.message)}if(!rejected||!node.active||label.string!=='unexpected')throw Error('reentry was not rejected before mutation');
process.stdout.write('ok');'''
        result = subprocess.run([node_bin, "-e", source, str(helper)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ok")


if __name__ == "__main__":
    unittest.main()
