import tempfile
import unittest
from pathlib import Path
import shutil
import subprocess
import json

from monkey.prefab_static_carriers import StaticCarrierError, emit, prepare


def snapshot(source_id="asset:one#1/components/0", source_type="example.Panel", texture="bundle:tex-a"):
    return {"sourceId": source_id, "node": "asset:one#1", "sourceType": source_type,
            "behavior": "disabled", "gaps": ["source_declaration_defaults_not_verified"],
            "fields": [
                {"name": "visible", "kind": "bool", "value": True},
                {"name": "price", "kind": "float", "value": 1.125},
                {"name": "precise", "kind": "float", "value": 0.1234567890123456},
                {"name": "title", "kind": "string", "value": "Panel"},
                {"name": "owner", "kind": "node_ref", "value": "asset:one#2"},
                {"name": "icon", "kind": "asset_ref", "value": texture},
                {"name": "tags", "kind": "array", "value": [
                    {"kind": "string", "value": "a"}, {"kind": "string", "value": "b"}]},
                {"name": "targets", "kind": "array", "value": [
                    {"kind": "component_ref", "value": "asset:one#4"}]},
                {"name": "extra", "kind": "object", "value": {"x": {"kind": "float", "value": 3}}},
                {"name": "nothing", "kind": "null", "value": None},
                {"name": "mixed", "kind": "array", "value": [
                    {"kind": "float", "value": 2}, {"kind": "string", "value": "2"}]},
            ]}


class PrefabStaticCarrierTests(unittest.TestCase):
    def test_conflicting_source_enum_does_not_coerce_boolean_or_claim_complete(self):
        from monkey.prefab_static_carriers import _field_plan
        result,gap=_field_plan(dict(name='option',kind='bool',value=False,sourceDeclaredType='cc.Enum(cc.Boolean)'),0)
        self.assertEqual(result['storageType'],'bool')
        self.assertIs(result['boolValue'],False)
        self.assertEqual(result['creatorType'],'CCBoolean')
        self.assertEqual(result['sourceDeclaredType'],'cc.Enum(cc.Boolean)')
        self.assertEqual(gap,'source_declared_primitive_conflict:option')

    def test_packed_source_color_and_serialized_default_override(self):
        from monkey.prefab_static_carriers import _field_plan
        encoded={"__value_type__":{"kind":"float","value":4},"values":{"kind":"array","value":[{"kind":"float","value":0x2948BF0D}]}}
        field={"name":"accent","kind":"object","value":encoded,"sourceDeclaredType":"cc.Color","serializedOverride":True,"declarationEvidence":{"sourceConstant":"cc.Color.WHITE"}}
        result,gap=_field_plan(field,0)
        self.assertIsNone(gap)
        self.assertEqual([result[k]for k in ('colorR','colorG','colorB','colorA')],[13,191,72,41])
        self.assertEqual(result['sourceConstant'],'')
        self.assertEqual(json.loads(result['sourceValueEncodingJson']),encoded)
        for malformed in (-1,0x100000000,True):
            bad={**field,'value':{'__value_type__':4,'values':[malformed]}}
            with self.assertRaises(StaticCarrierError):_field_plan(bad,0)

    def test_cc_color_preserves_channels_evidence_and_native_types_on_both_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            row = {"sourceId": "asset:color#1/components/0", "node": "asset:color#1",
                   "sourceType": "example.ColorFields", "gaps": [], "fields": [
                       {"name": "silhouette", "kind": "object", "value": {"r": 255, "g": 255, "b": 255, "a": 255},
                        "sourceDeclaredType": "cc.Color", "declarationEvidence": {
                            "sourceConstant": "cc.Color.WHITE", "accessorBacking": {
                                "propertyName": "silhouette", "backingFieldName": "_silhouette", "sourceBytes": {"start": 10, "end": 20}}}},
                       {"name": "accent", "kind": "object", "value": {"r": 13, "g": 72, "b": 191, "a": 41},
                        "sourceDeclaredType": "cc.Color"},
                       {"name": "rendersPreset", "kind": "array", "value": [],
                        "sourceDeclaredType": "[cc.RenderComponent]"},
                   ]}
            unity = prepare([row], "unity", "Recovered", root / "unity")
            creator = prepare([row], "creator", "Recovered", root / "creator")
            unity_fields = {field["sourceFieldName"]: field for field in unity["bindings"][row["sourceId"]]["fields"]}
            creator_fields = {field["sourceFieldName"]: field for field in creator["bindings"][row["sourceId"]]["fields"]}
            self.assertEqual(unity_fields["silhouette"]["storageType"], "Color")
            self.assertEqual(unity_fields["silhouette"]["sourceConstant"], "cc.Color.WHITE")
            self.assertEqual(unity_fields["silhouette"]["accessorBacking"]["backingFieldName"], "_silhouette")
            self.assertEqual([unity_fields["accent"][key] for key in ("colorR", "colorG", "colorB", "colorA")], [13, 72, 191, 41])
            self.assertEqual(creator_fields["rendersPreset"]["storageType"], "UnityEngine.Object[]")
            self.assertEqual(creator_fields["rendersPreset"]["creatorElementType"], "Component")
            self.assertEqual(unity_fields["rendersPreset"]["storageType"], "UnityEngine.Object[]")
            self.assertEqual(unity_fields["rendersPreset"]["creatorElementType"], "Component")
            unity_script = Path(root, "unity", unity["scripts"][0]["source"]).read_text()
            creator_script = Path(root, "creator", creator["scripts"][0]["source"]).read_text()
            self.assertIn("Color32 __sf_000_silhouette = new Color32(255, 255, 255, 255)", unity_script)
            self.assertIn("Color32 __sf_001_accent = new Color32(13, 72, 191, 41)", unity_script)
            self.assertIn("@property(Color) public __sf_000_silhouette: Color = new Color(255, 255, 255, 255)", creator_script)
            self.assertIn("@property([Component])", creator_script)
            # Real Pure03 + game.js declaration enrichment wraps each numeric
            # channel as a static-field typed literal: {kind:float,value:255}.
            encoded = {**row, "fields": [dict(row["fields"][0]), *row["fields"][1:]]}
            encoded_value = {channel: {"kind": "float", "value": value}
                             for channel, value in (("r", 255), ("g", 255), ("b", 255), ("a", 255))}
            encoded["fields"][0]["value"] = encoded_value
            encoded_report = prepare([encoded], "unity", "Recovered", root / "encoded")
            encoded_field = encoded_report["bindings"][row["sourceId"]]["fields"][0]
            self.assertEqual([encoded_field[key] for key in ("colorR", "colorG", "colorB", "colorA")], [255, 255, 255, 255])
            self.assertEqual(encoded_field["sourceValueEncoding"], "nested_static_float_channel_values/1")
            self.assertEqual(json.loads(encoded_field["sourceValueEncodingJson"]), encoded_value)
            malformed_encoded = {**encoded, "fields": [dict(encoded["fields"][0])]}
            malformed_encoded["fields"][0]["value"] = {**encoded_value, "g": {"kind": "string", "value": 255}}
            with self.assertRaisesRegex(StaticCarrierError, "source-encoded float literals"):
                prepare([malformed_encoded], "creator", "Recovered", root / "bad-encoding")
            with self.assertRaisesRegex(StaticCarrierError, r"\[0,255\]"):
                invalid = {**row, "fields": [{"name": "bad", "kind": "object", "value": {"r": 0, "g": 256, "b": 0, "a": 255}, "sourceDeclaredType": "cc.Color"}]}
                prepare([invalid], "unity", "Recovered", root / "invalid")
            with self.assertRaisesRegex(StaticCarrierError, "conflicts with sourceConstant"):
                inconsistent = {**row, "fields": [{"name": "white", "kind": "object",
                    "value": {"r": 1, "g": 255, "b": 255, "a": 255}, "sourceDeclaredType": "cc.Color",
                    "sourceConstant": "cc.Color.WHITE"}]}
                prepare([inconsistent], "creator", "Recovered", root / "inconsistent")

    def test_creator_color_assign_and_read_verify_nonwhite_alpha_and_reject_wrong_type(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable")
        helper = Path("src/monkey/targets/CreatorStaticFields.js").resolve()
        source = r'''const Module=require('module'),original=Module._load;
class Component{constructor(){this.enabled=true}} class Node extends Component{addComponent(C){const c=new C();c.node=this;return c}}
class Color{constructor(r,g,b,a){this.r=r;this.g=g;this.b=b;this.a=a}} class Carrier extends Component{constructor(){super();this.__monkeySourceId='';this.white=null;this.accent=null}}
const guid='12345678-1234-1234-1234-123456789abc',raw=guid.replace(/-/g,''),alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';let id=raw.slice(0,5);for(let i=5;i<32;i+=3){const n=parseInt(raw.slice(i,i+3),16);id+=alphabet[n>>6]+alphabet[n&63]}
Module._load=function(req){if(req==='cc')return{Component,Node,Color,js:{getClassByName:()=>Carrier,getClassId:()=>id}};return original.apply(this,arguments)};
const api=require(process.argv[1]),guidValue=guid,spec={sourceId:'asset:color#1/components/0',typeName:'Recovered.Carrier',scriptGuid:guidValue,declarationDefaultsVerified:true,gaps:[],fields:[{sourceFieldName:'white',fieldName:'white',kind:'object',sourceDeclaredType:'cc.Color',sourceConstant:'cc.Color.WHITE',sourceValueEncoding:'nested_static_float_channel_values/1',sourceValueEncodingJson:'{"r":{"kind":"float","value":255}}',storageType:'Color',colorR:255,colorG:255,colorB:255,colorA:255},{sourceFieldName:'accent',fieldName:'accent',kind:'object',sourceDeclaredType:'cc.Color',storageType:'Color',colorR:13,colorG:72,colorB:191,colorA:41}]};
const node=new Node(),c=api.Create(spec,node),assigned=api.Assign(spec,c,null),read=api.Read(spec,c,null);if(!assigned.fieldsAssigned||!read.fieldsVerified||!read.nativeComplete||c.enabled||!(c.accent instanceof Color)||c.accent.r!==13||c.accent.g!==72||c.accent.b!==191||c.accent.a!==41||read.fields[1].colorA!==41||read.fields[0].sourceValueEncodingJson!==spec.fields[0].sourceValueEncodingJson)throw Error('Creator Color assign/read failed');c.accent=new Color(13,72,191,40);if(api.Read(spec,c,null).fieldsVerified)throw Error('Creator Color mismatch passed');process.stdout.write('ok');'''
        result = subprocess.run([node, "-e", source, str(helper)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ok")

    def test_prepare_emits_deduplicated_scripts_and_typed_binding_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve()
            first = snapshot()
            second = snapshot("asset:two#3/components/0", texture="bundle:tex-b")
            second["node"] = first["node"]
            report = prepare([first, second], "unity", "Recovered", directory)
            self.assertEqual(len(report["scripts"]), 1)
            self.assertEqual(set(report["bindings"]), {first["sourceId"], second["sourceId"]})
            spec = report["bindings"][first["sourceId"]]
            self.assertEqual(spec["behavior"], "disabled")
            self.assertFalse(spec["enabled"])
            self.assertEqual(spec["nativeCreate"], "no-callbacks")
            self.assertEqual(spec["declarationDefaults"], "unverified")
            self.assertEqual(spec["sourceId"], first["sourceId"])
            self.assertNotIn("__monkeySourceId", {field["sourceFieldName"] for field in spec["fields"]})
            fields = {field["sourceFieldName"]: field for field in spec["fields"]}
            self.assertEqual(fields["price"]["numberValue"], 1.125)
            self.assertEqual(fields["precise"]["numberValue"], 0.1234567890123456)
            self.assertEqual(fields["precise"]["storageType"], "double")
            self.assertEqual(fields["owner"]["refValue"], "asset:one#2")
            self.assertEqual(fields["tags"]["stringValues"], ["a", "b"])
            self.assertEqual(fields["targets"]["refValues"], ["asset:one#4"])
            self.assertEqual(fields["extra"]["mode"], "snapshot-json")
            self.assertIn("field_snapshot_json_not_native:extra", spec["gaps"])
            self.assertNotIn("field_snapshot_json_not_native:nothing", spec["gaps"])
            self.assertTrue(fields["nothing"]["nullExpected"])
            self.assertEqual(fields["nothing"]["dynamicType"], "unverified")
            self.assertIn("array_not_native_typed:mixed", spec["gaps"])
            self.assertTrue(any(row["sourceId"] == first["sourceId"] and row["message"] == "array_not_native_typed:mixed"
                                for row in report["diagnostics"]))
            script = Path(directory, report["scripts"][0]["source"]).read_text()
            self.assertIn("public double", script)
            self.assertIn("[SerializeField, HideInInspector] public string __monkeySourceId", script)
            self.assertNotIn("DisallowMultipleComponent", script)
            self.assertNotIn("void Update", script)
            self.assertNotIn("void OnEnable", script)

    def test_creator_uses_serializable_typed_properties_and_renamed_source_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve()
            row = snapshot("renamed:prefab#1/components/2", "renamed.Widget", "renamed:asset")
            report = prepare([row], "creator", "Game.Recovered", directory)
            spec = report["bindings"][row["sourceId"]]
            self.assertIn("renamed.Widget", spec["sourceType"])
            self.assertEqual(next(f for f in spec["fields"] if f["sourceFieldName"] == "icon")["refValue"], "renamed:asset")
            script = Path(directory, report["scripts"][0]["source"]).read_text()
            self.assertIn("@property(CCBoolean)", script)
            self.assertIn("@property(CCFloat)", script)
            self.assertIn("@property([CCString])", script)
            self.assertIn("extends Component", script)
            self.assertIn("visible: false", script)
            helper = Path("src/monkey/targets/CreatorStaticFields.js").read_text()
            self.assertIn("component.__monkeySourceId = spec.sourceId", helper)
            self.assertIn("native_source_id_mismatch", helper)
            unity_helper = Path("src/monkey/targets/UnityStaticFields.cs").read_text()
            self.assertIn("nativeScriptGuid = NativeScriptGuid(component)", unity_helper)
            self.assertIn("native_source_id_mismatch", unity_helper)

    def test_bad_schema_and_duplicate_field_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve()
            row = snapshot()
            row["fields"].append(dict(row["fields"][0]))
            with self.assertRaises(StaticCarrierError):
                prepare([row], "unity", "Recovered", directory)
            row = snapshot()
            row["fields"][0] = {"name": "broken", "kind": "date", "value": "today"}
            with self.assertRaises(StaticCarrierError):
                prepare([row], "unity", "Recovered", directory)

    def test_literal_null_and_empty_declared_component_array_are_native(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve()
            row = {"sourceId": "asset:null#2/components/0", "node": "asset:null#2",
                   "sourceType": "example.NullFields", "declarationDefaults": "verified", "gaps": [],
                   "fields": [
                       {"name": "optionalNode", "kind": "null", "value": None, "sourceDeclaredType": "cc.Node"},
                       {"name": "optionalAsset", "kind": "null", "value": None, "sourceDeclaredType": "cc.Asset"},
                       {"name": "skeletons", "kind": "array", "value": [], "sourceDeclaredType": "[sp.Skeleton]"},
                       {"name": "dynamicNull", "kind": "null", "value": None},
                   ]}
            unity = prepare([row], "unity", "Recovered", directory / "unity")
            creator = prepare([row], "creator", "Game.Recovered", directory / "creator")
            spec = unity["bindings"][row["sourceId"]]
            self.assertTrue(spec["declarationDefaultsVerified"])
            self.assertEqual(spec["gaps"], [])
            fields = {field["sourceFieldName"]: field for field in spec["fields"]}
            self.assertEqual(fields["optionalNode"]["storageType"], "UnityEngine.Object")
            self.assertTrue(fields["optionalNode"]["nullExpected"])
            self.assertEqual(fields["optionalAsset"]["referenceKind"], "asset_ref")
            self.assertEqual(fields["skeletons"]["storageType"], "UnityEngine.Object[]")
            self.assertEqual(fields["skeletons"]["elementKind"], "component_ref")
            self.assertEqual(fields["skeletons"]["refValues"], [])
            self.assertEqual(fields["dynamicNull"]["dynamicType"], "unverified")
            self.assertEqual(unity["diagnostics"], [])
            unity_script = Path(directory, "unity", unity["scripts"][0]["source"]).read_text()
            creator_script = Path(directory, "creator", creator["scripts"][0]["source"]).read_text()
            self.assertIn("public UnityEngine.Object", unity_script)
            self.assertIn("public UnityEngine.Object[]", unity_script)
            self.assertIn("Node | null = null", creator_script)
            self.assertIn("Asset | null = null", creator_script)
            self.assertIn("Component[] = []", creator_script)
            creator_fields = creator["bindings"][row["sourceId"]]["fields"]
            self.assertTrue(next(f for f in creator_fields if f["sourceFieldName"] == "optionalNode")["nullExpected"])

    def test_creator_null_and_empty_reference_array_skip_resolver(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable")
        helper = Path("src/monkey/targets/CreatorStaticFields.js").resolve()
        source = r'''const Module=require('module'),original=Module._load;
class Component{constructor(){this.enabled=true}} class Node extends Component{addComponent(C){const c=new C();c.node=this;return c}}
class Carrier extends Component{constructor(){super();this.__monkeySourceId='';this.ref=null;this.items=[]}}
const guid='12345678-1234-1234-1234-123456789abc',raw=guid.replace(/-/g,''),alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';let id=raw.slice(0,5);for(let i=5;i<32;i+=3){const n=parseInt(raw.slice(i,i+3),16);id+=alphabet[n>>6]+alphabet[n&63]}
Module._load=function(req){if(req==='cc')return{Component,Node,Asset:class Asset{},js:{getClassByName:()=>Carrier,getClassId:()=>id}};return original.apply(this,arguments)};
const api=require(process.argv[1]),spec={sourceId:'asset:x#1',typeName:'Recovered.Carrier',scriptGuid:guid,declarationDefaultsVerified:true,gaps:[],fields:[{sourceFieldName:'ref',fieldName:'ref',kind:'null',referenceKind:'component_ref',nullExpected:true,storageType:'UnityEngine.Object'},{sourceFieldName:'items',fieldName:'items',kind:'array',elementKind:'component_ref',refValues:[],storageType:'UnityEngine.Object[]'}]};
const c=api.Create(spec,new Node()),a=api.Assign(spec,c,()=>{throw Error('resolver must not run for null/empty')});const r=api.Read(spec,c,()=>{throw Error('resolver must not run for null/empty')});if(c.enabled||!a.fieldsAssigned||a.fieldsVerified||!r.fieldsVerified||!r.nativeIdentityVerified||!r.fields[0].referenceVerified||!r.nativeComplete)throw Error('null/empty native preservation failed');process.stdout.write('ok');'''
        result = subprocess.run([node, "-e", source, str(helper)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ok")

    def test_creator_record_array_instantiates_references_and_verifies_each_value(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable")
        helper = Path("src/monkey/targets/CreatorStaticFields.js").resolve()
        source = r'''const Module=require('module'),original=Module._load;
class Component{constructor(){this.enabled=true}} class Node extends Component{addComponent(C){const c=new C();c.node=this;return c}}
class Asset{constructor(uuid='asset:exact-texture'){this._uuid=uuid}} class Record{constructor(){this.state=0;this.texture=null}} class Carrier extends Component{constructor(){super();this.__monkeySourceId='';this.entries=[]}}
const guid='12345678-1234-1234-1234-123456789abc',raw=guid.replace(/-/g,''),alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';let id=raw.slice(0,5);for(let i=5;i<32;i+=3){const n=parseInt(raw.slice(i,i+3),16);id+=alphabet[n>>6]+alphabet[n&63]}
Module._load=function(req){if(req==='cc')return{Component,Node,Asset,js:{getClassByName:n=>n==='Recovered.StaticRecord'?Record:Carrier,getClassId:()=>id}};return original.apply(this,arguments)};
const api=require(process.argv[1]),texture=new Asset(),spec={sourceId:'asset:records#1/components/0',typeName:'Recovered.Carrier',scriptGuid:guid,declarationDefaultsVerified:true,gaps:[],fields:[{sourceFieldName:'entries',fieldName:'entries',kind:'array',elementKind:'record',recordTypeName:'StaticRecord',storageType:'StaticRecord[]',recordValues:[{index:0,fields:[{sourceFieldName:'state',fieldName:'state',storageType:'double',numberValue:1},{sourceFieldName:'texture',fieldName:'texture',kind:'asset_ref',referenceKind:'asset_ref',storageType:'UnityEngine.Object',refValue:'asset:exact-texture'}]}]}]};
const c=api.Create(spec,new Node());c.__monkeySourceId='template-source-id';const a=api.Assign(spec,c,id=>id==='asset:exact-texture'?texture:null),good=api.Read(spec,c,id=>id==='asset:exact-texture'?texture:null);if(c.enabled||c.__monkeySourceId!==spec.sourceId||!a.fieldsAssigned||!good.fieldsVerified||!good.nativeIdentityVerified||!good.fields[0].recordValues[0].fields[1].referenceVerified||c.entries[0].texture!==texture)throw Error('record/instance identity assign/read failed');c.entries[0].texture=new Asset('wrong-texture');const bad=api.Read(spec,c,id=>texture);if(bad.fieldsVerified||!bad.gaps.some(x=>x.includes('record_reference_readback_mismatch')))throw Error('record reference mismatch passed');const partial=api.Assign(spec,c,()=>null);if(partial.fieldsAssigned||!partial.gaps.some(x=>x.includes('reference_unresolved'))||c.entries[0].state!==1||c.__monkeySourceId!==spec.sourceId)throw Error('missing record reference was not reported as partial');process.stdout.write('ok');'''
        result = subprocess.run([node, "-e", source, str(helper)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ok")

    def test_creator_reference_readback_uses_uuid_class_and_exact_source_identity(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable")
        helper = Path("src/monkey/targets/CreatorStaticFields.js").resolve()
        source = r'''const Module=require('module'),original=Module._load;
class Component{constructor(uuid='component'){this.enabled=true;this.uuid=uuid}}
class Node extends Component{constructor(uuid='node',name='same-name'){super(uuid);this.name=name}addComponent(C){return new C()}}
class Asset{constructor(uuid='asset'){this._uuid=uuid}}
class WrongAsset extends Asset{}
class Record{constructor(){this.texture=null}}
class Carrier extends Component{constructor(){super('carrier');this.__monkeySourceId='';this.asset=null;this.items=[];this.entries=[];this.nodeRef=null;this.componentRef=null}}
const guid='12345678-1234-1234-1234-123456789abc',raw=guid.replace(/-/g,''),alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';let id=raw.slice(0,5);for(let i=5;i<32;i+=3){const n=parseInt(raw.slice(i,i+3),16);id+=alphabet[n>>6]+alphabet[n&63]}
Module._load=function(req){if(req==='cc')return{Component,Node,Asset,js:{getClassByName:n=>n==='Recovered.StaticRecord'?Record:Carrier,getClassId:()=>id}};return original.apply(this,arguments)};
const api=require(process.argv[1]);
const assetId='bundle:asset-1',asset2Id='bundle:asset-2',nodeId='bundle:node-1',componentId='bundle:component-1';
const expectedAsset=new Asset('native-asset-1'),expectedAsset2=new Asset('native-asset-2');
const expectedNode=new Node('native-node-1','same-name');
const expectedComponent=new Component('native-component-1');expectedComponent.__monkeySourceId=componentId;
const spec={sourceId:'prefab:owner#1/components/0',typeName:'Recovered.Carrier',scriptGuid:guid,declarationDefaultsVerified:true,gaps:[],fields:[
 {sourceFieldName:'asset',fieldName:'asset',kind:'asset_ref',referenceKind:'asset_ref',storageType:'UnityEngine.Object',refValue:assetId},
 {sourceFieldName:'items',fieldName:'items',kind:'array',elementKind:'asset_ref',storageType:'UnityEngine.Object[]',refValues:[assetId,asset2Id]},
 {sourceFieldName:'entries',fieldName:'entries',kind:'array',elementKind:'record',recordTypeName:'StaticRecord',storageType:'StaticRecord[]',recordValues:[{index:0,fields:[{sourceFieldName:'texture',fieldName:'texture',kind:'asset_ref',referenceKind:'asset_ref',storageType:'UnityEngine.Object',refValue:asset2Id}]}]},
 {sourceFieldName:'nodeRef',fieldName:'nodeRef',kind:'node_ref',referenceKind:'node_ref',storageType:'UnityEngine.Object',refValue:nodeId},
 {sourceFieldName:'componentRef',fieldName:'componentRef',kind:'component_ref',referenceKind:'component_ref',storageType:'UnityEngine.Object',refValue:componentId}
]};
const resolve=id=>({[assetId]:expectedAsset,[asset2Id]:expectedAsset2,[nodeId]:expectedNode,[componentId]:expectedComponent})[id]||null;
const c=api.Create(spec,new Node('carrier-node'));const assigned=api.Assign(spec,c,resolve);if(!assigned.fieldsAssigned)throw Error('reference setup failed '+JSON.stringify(assigned.gaps));
// Simulate deserialization wrappers: identity differs, native UUID/class/source identity remains exact.
c.asset=new Asset('native-asset-1');c.items=[new Asset('native-asset-1'),new Asset('native-asset-2')];c.entries[0].texture=new Asset('native-asset-2');c.nodeRef=new Node('native-node-1','same-name');c.componentRef=new Component('native-component-1');c.componentRef.__monkeySourceId=componentId;
const good=api.Read(spec,c,resolve);const scalarEvidence=good.fields[0].referenceEvidence,arrayEvidence=good.fields[1].referenceEvidence[0],recordEvidence=good.fields[2].recordValues[0].fields[0].referenceEvidence;if(!good.fieldsVerified||!good.fields[0].referenceVerified||!good.fields[1].referencesVerified||!good.fields[2].recordValues[0].fields[0].referenceVerified||!good.fields[3].referenceVerified||!good.fields[4].referenceVerified||scalarEvidence.actual.nativeUuid!=='native-asset-1'||scalarEvidence.expected.nativeUuid!=='native-asset-1'||scalarEvidence.actual.nativeClass!=='Asset'||scalarEvidence.expected.nativeClass!=='Asset'||!arrayEvidence.verified||!recordEvidence.verified||good.fields[4].referenceEvidence.actual.sourceIdentity!==componentId)throw Error('same UUID/type or exact source identity should pass '+JSON.stringify(good.gaps));
c.asset=new Asset('different-native-uuid');let bad=api.Read(spec,c,resolve);if(bad.fieldsVerified||bad.fields[0].referenceEvidence.actual.nativeUuid!=='different-native-uuid'||bad.fields[0].referenceEvidence.expected.nativeUuid!=='native-asset-1')throw Error('wrong asset UUID passed or actual/expected identity was not reported');
c.asset=new WrongAsset('native-asset-1');bad=api.Read(spec,c,resolve);if(bad.fieldsVerified||bad.fields[0].referenceEvidence.actual.nativeClass!=='WrongAsset')throw Error('wrong asset class passed or class evidence was not reported');
c.asset=new Asset('native-asset-1');c.items[1]=new Asset('wrong-array-uuid');if(api.Read(spec,c,resolve).fieldsVerified)throw Error('wrong array UUID passed');
c.items=[new Asset('native-asset-1'),new Asset('native-asset-2')];c.entries[0].texture=new Asset('wrong-record-uuid');if(api.Read(spec,c,resolve).fieldsVerified)throw Error('wrong record-leaf UUID passed');
c.entries[0].texture=new Asset('native-asset-2');c.nodeRef=new Node('other-native-node','same-name');if(api.Read(spec,c,resolve).fieldsVerified)throw Error('same-name wrong node passed');
c.nodeRef=new Node('native-node-1','same-name');c.componentRef=new Component('native-component-1');c.componentRef.__monkeySourceId='other-source-id';if(api.Read(spec,c,resolve).fieldsVerified)throw Error('wrong persistent component source identity passed');
const missing=api.Read(spec,c,()=>null);if(missing.fieldsVerified||!missing.gaps.some(x=>x.includes('reference_unresolved'))||missing.fields[0].referenceEvidence.expected!==null)throw Error('unresolved reference was hidden or marked verified');
process.stdout.write('ok');'''
        result = subprocess.run([node, "-e", source, str(helper)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ok")

    def test_creator_sync_inherited_component_source_alias_requires_origin_proof(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js unavailable")
        fields_helper = Path("src/monkey/targets/CreatorStaticFields.js").resolve()
        integration_helper = Path("src/monkey/targets/CreatorStaticFieldIntegration.js").resolve()
        source = r'''const Module=require('module'),original=Module._load;
class Component{constructor(uuid){this.uuid=uuid;this.enabled=false}}
class Node{constructor(uuid,components=[]){this.uuid=uuid;this._components=components}getComponents(C){return this._components.filter(c=>c instanceof C)}}
class Asset{}
const guid='12345678-1234-1234-1234-123456789abc',raw=guid.replace(/-/g,''),alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';let classId=raw.slice(0,5);for(let i=5;i<32;i+=3){const n=parseInt(raw.slice(i,i+3),16);classId+=alphabet[n>>6]+alphabet[n&63]}
class OwnerCarrier extends Component{constructor(){super('owner-carrier');this.__monkeySourceId='owner-carrier-source';this.target=null}}
class TargetCarrier extends Component{constructor(){super('persistent-target-component');this.__monkeySourceId=''}}
Module._load=function(req){if(req==='cc')return{Component,Node,Asset,js:{getClassByName:n=>n==='Recovered.OwnerCarrier'?OwnerCarrier:n==='Recovered.TargetCarrier'?TargetCarrier:null,getClassId:()=>classId}};if(req==='./static-fields.js')return require(process.argv[2]);return original.apply(this,arguments)};
const integration=require(process.argv[1]),fields=require(process.argv[2]);
const logical='gameAsset:owner#8::sync-component-copy',template='gameAsset:template#21/components/0',fieldSpec={sourceId:'owner-carrier-source',typeName:'Recovered.OwnerCarrier',scriptGuid:guid,declarationDefaultsVerified:true,gaps:[],fields:[{sourceFieldName:'target',fieldName:'target',kind:'component_ref',referenceKind:'component_ref',storageType:'UnityEngine.Object',refValue:logical}]};
function makePlan(includeOrigin=true,originTemplate=template){return {components:[
 {sourceId:logical,node:'owner-instance-node',staticFieldBinding:{typeName:'Recovered.TargetCarrier',sourceTemplateId:template}},
 {sourceId:template,node:'template-node'}],sourcePrefabs:[{sourceId:'owner-prefab',nodes:['owner-instance-node']},{sourceId:'template-prefab',nodes:['template-node']}],
 syncPrefabBindings:includeOrigin?[{owner:'owner-prefab',template:'template-prefab',componentOrigins:[{instanceSourceId:logical,templateSourceId:originTemplate}]}]:[]}}
function run(plan,actualIdentity=template){
 const target=new TargetCarrier();target.__monkeySourceId=actualIdentity;
 const nodes=new Map([['owner-instance-node',new Node('owner-node')],['template-node',new Node('template-node')]]);nodes.get('owner-instance-node')._components.push(target);
 const resolve=integration.resolver(plan,nodes,new Map());
 const owner=new OwnerCarrier();owner.target=target;
 return {read:fields.Read(fieldSpec,owner,resolve),proof:resolve.sourceIdentityProof(logical,target,resolve(logical))};
}
const good=run(makePlan());if(!good.read.fieldsVerified||!good.read.fields[0].referenceVerified||!good.read.fields[0].referenceEvidence.sourceIdentityAlias||good.read.fields[0].referenceEvidence.sourceIdentityAlias.proof!=='syncPrefabBindings.componentOrigins')throw Error('verified sync source-template alias rejected '+JSON.stringify(good.read.gaps));
const noOrigin=run(makePlan(false));if(noOrigin.read.fieldsVerified||noOrigin.proof!==null)throw Error('unproven source-template alias passed');
const wrongOrigin=run(makePlan(true,'unrelated-template-component'));if(wrongOrigin.read.fieldsVerified||wrongOrigin.proof!==null)throw Error('mismatched origin alias passed');
const wrongMarker=run(makePlan(),'forged-template-component');if(wrongMarker.read.fieldsVerified||wrongMarker.proof!==null)throw Error('wrong marker passed despite origin proof');
process.stdout.write('ok');'''
        result = subprocess.run([node, "-e", source, str(integration_helper), str(fields_helper)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "ok")

    def test_unity_assign_rewrites_cloned_template_source_identity_only_after_type_check(self):
        dotnet = shutil.which("dotnet")
        if not dotnet:
            self.skipTest(".NET SDK unavailable")
        helper = Path("src/monkey/targets/UnityStaticFields.cs").resolve()
        source = r'''using System;using System.Linq;using System.Reflection;using System.Text.Json;
namespace UnityEngine { public class Object {} public struct Color32 { public byte r,g,b,a; public Color32(byte r,byte g,byte b,byte a){this.r=r;this.g=g;this.b=b;this.a=a;} } public class GameObject:Object { public object AddComponent(Type t)=>Activator.CreateInstance(t); } public class MonoBehaviour:Object { public bool enabled=true; } [AttributeUsage(AttributeTargets.Field)] public class SerializeField:Attribute{} [AttributeUsage(AttributeTargets.Field)] public class HideInInspector:Attribute{} public static class JsonUtility { static JsonSerializerOptions o=new JsonSerializerOptions{IncludeFields=true}; public static string ToJson(object v)=>JsonSerializer.Serialize(v,v.GetType(),o); public static T FromJson<T>(string v)=>JsonSerializer.Deserialize<T>(v,o); } }
namespace Recovered { [Serializable] public sealed class StaticRecord { public double state; public UnityEngine.Object texture; } public sealed class Carrier:UnityEngine.MonoBehaviour { public string __monkeySourceId=""; public StaticRecord[] entries=Array.Empty<StaticRecord>(); public UnityEngine.Color32 silhouette; public UnityEngine.Color32 accent; } public sealed class Other:UnityEngine.MonoBehaviour { public string __monkeySourceId=""; } public sealed class Asset:UnityEngine.Object {} }
namespace UnityEditor { public class MonoScript:UnityEngine.Object { public Type GetClass()=>typeof(Recovered.Carrier); public static MonoScript FromMonoBehaviour(UnityEngine.MonoBehaviour c)=>new MonoScript(); } public static class AssetDatabase { public static string GUIDToAssetPath(string g)=>"Assets/Game/Scripts/Presentation/Recovered/StaticFields/Carrier.cs"; public static T LoadAssetAtPath<T>(string p) where T:class=>new MonoScript() as T; public static string GetAssetPath(UnityEngine.Object o)=>"Assets/Game/Scripts/Presentation/Recovered/StaticFields/Carrier.cs"; public static string AssetPathToGUID(string p)=>"12345678123412341234123456789abc"; } }
'''
        program = r'''class Program{static void Main(){
var guid="12345678123412341234123456789abc";
var spec=new UnityStaticFields.Spec{sourceId="prefab#instance/components/0",typeName="Recovered.Carrier",scriptGuid=guid,behavior="disabled",enabled=false,declarationDefaultsVerified=true,gaps=Array.Empty<string>(),fields=Array.Empty<UnityStaticFields.FieldSpec>()};
var clone=new Recovered.Carrier{__monkeySourceId="prefab#template/components/0"};var assigned=UnityStaticFields.Assign(spec,clone,null);var read=UnityStaticFields.Read(spec,clone,null);
if(clone.__monkeySourceId!=spec.sourceId||clone.enabled||!assigned.fieldsAssigned||!read.fieldsVerified||!read.nativeIdentityVerified||!read.nativeComplete)throw new Exception("cloned native identity was not rebound and verified");
var wrong=new Recovered.Other{__monkeySourceId="foreign"};UnityStaticFields.Assign(spec,wrong,null);if(wrong.__monkeySourceId!="foreign")throw new Exception("wrong script identity was mutated");var wrongRead=UnityStaticFields.Read(spec,wrong,null);if(wrongRead.nativeIdentityVerified||wrongRead.fieldsVerified)throw new Exception("wrong native script passed readback");
var asset=new Recovered.Asset();
var recordSpec=new UnityStaticFields.Spec{sourceId="prefab#record/components/0",typeName="Recovered.Carrier",scriptGuid=guid,behavior="disabled",enabled=false,declarationDefaultsVerified=true,gaps=Array.Empty<string>(),fields=new[]{new UnityStaticFields.FieldSpec{sourceFieldName="entries",fieldName="entries",kind="array",elementKind="record",recordTypeName="StaticRecord",storageType="StaticRecord[]",recordValues=new[]{new UnityStaticFields.RecordValueSpec{index=0,fields=new[]{new UnityStaticFields.RecordFieldValueSpec{sourceFieldName="state",fieldName="state",kind="float",storageType="double",numberValue=1},new UnityStaticFields.RecordFieldValueSpec{sourceFieldName="texture",fieldName="texture",kind="asset_ref",storageType="UnityEngine.Object",referenceKind="asset_ref",refValue="asset:exact"}}}}}}};
var recordCarrier=new Recovered.Carrier();var resolver=new Func<string,UnityEngine.Object>(id=>id=="asset:exact"?asset:null);var recordAssign=UnityStaticFields.Assign(recordSpec,recordCarrier,resolver);var recordRead=UnityStaticFields.Read(recordSpec,recordCarrier,resolver);
if(!recordAssign.recordSpecStructureVerified||!recordRead.recordSpecStructureVerified||!recordRead.fieldsVerified||!recordRead.nativeComplete||recordCarrier.entries.Length!=1||recordCarrier.entries[0].state!=1||!ReferenceEquals(recordCarrier.entries[0].texture,asset))throw new Exception("typed record/reference roundtrip failed");
var colorSpec=new UnityStaticFields.Spec{sourceId="prefab#color/components/0",typeName="Recovered.Carrier",scriptGuid=guid,behavior="disabled",enabled=false,declarationDefaultsVerified=true,gaps=Array.Empty<string>(),fields=new[]{
new UnityStaticFields.FieldSpec{sourceFieldName="silhouette",fieldName="silhouette",kind="object",sourceDeclaredType="cc.Color",sourceConstant="cc.Color.WHITE",accessorBackingJson="{\"propertyName\":\"silhouette\",\"backingFieldName\":\"_silhouette\"}",sourceValueEncoding="nested_static_float_channel_values/1",sourceValueEncodingJson="{\"r\":{\"kind\":\"float\",\"value\":255},\"g\":{\"kind\":\"float\",\"value\":255},\"b\":{\"kind\":\"float\",\"value\":255},\"a\":{\"kind\":\"float\",\"value\":255}}",storageType="Color",colorR=255,colorG=255,colorB=255,colorA=255},
new UnityStaticFields.FieldSpec{sourceFieldName="accent",fieldName="accent",kind="object",sourceDeclaredType="cc.Color",storageType="Color",colorR=13,colorG=72,colorB=191,colorA=41}}};
var colorCarrier=new Recovered.Carrier();var colorAssign=UnityStaticFields.Assign(colorSpec,colorCarrier,null);var colorRead=UnityStaticFields.Read(colorSpec,colorCarrier,null);
if(!colorAssign.fieldsAssigned||!colorRead.fieldsVerified||!colorRead.nativeComplete||colorCarrier.silhouette.r!=255||colorCarrier.accent.r!=13||colorCarrier.accent.g!=72||colorCarrier.accent.b!=191||colorCarrier.accent.a!=41||colorRead.fields[0].sourceValueEncodingJson.IndexOf("kind")<0||colorRead.fields[1].colorA!=41)throw new Exception("Unity Color32 channel assignment/readback failed");
colorSpec.fields[1].colorA=256;var badColor=UnityStaticFields.Assign(colorSpec,new Recovered.Carrier(),null);if(badColor.fieldsAssigned||badColor.fieldsVerified)throw new Exception("out-of-range Color channel passed");
Console.WriteLine("ok");}}
'''
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            (directory/"Probe.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>disable</Nullable><EnableDefaultCompileItems>false</EnableDefaultCompileItems></PropertyGroup><ItemGroup><Compile Include="Probe.cs"/><Compile Include="UnityStaticFields.cs"/></ItemGroup></Project>')
            (directory/"NuGet.Config").write_text('<configuration><packageSources><clear /></packageSources></configuration>')
            (directory/"Probe.cs").write_text(source+program)
            shutil.copy2(helper,directory/"UnityStaticFields.cs")
            restore=subprocess.run([dotnet,"restore",str(directory/"Probe.csproj"),"--configfile",str(directory/"NuGet.Config")],capture_output=True,text=True,check=False)
            self.assertEqual(restore.returncode,0,restore.stdout+restore.stderr)
            result=subprocess.run([dotnet,"run","--project",str(directory/"Probe.csproj"),"--no-restore"],capture_output=True,text=True,check=False)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(result.stdout.strip(),"ok")

    def test_declared_primitive_and_reference_arrays_keep_supported_native_types(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve()
            row = {"sourceId": "asset:arrays#1/components/0", "node": "asset:arrays#1",
                   "sourceType": "example.ArrayFields", "gaps": [], "fields": [
                       {"name": "visible", "kind": "bool", "value": True, "sourceDeclaredType": "cc.Boolean"},
                       {"name": "index", "kind": "float", "value": 4, "sourceDeclaredType": "cc.Integer"},
                       {"name": "ratio", "kind": "float", "value": 1.25, "sourceDeclaredType": "cc.Float"},
                       {"name": "labels", "kind": "array", "value": [], "sourceDeclaredType": "[cc.String]"},
                       {"name": "indices", "kind": "array", "value": [], "sourceDeclaredType": "[cc.Integer]"},
                       {"name": "flags", "kind": "array", "value": [], "sourceDeclaredType": "[cc.Boolean]"},
                       {"name": "renders", "kind": "array", "value": [], "sourceDeclaredType": "[cc.RenderComponent]"},
                       {"name": "sprites", "kind": "array", "value": [], "sourceDeclaredType": "[cc.Sprite]"},
                       {"name": "frames", "kind": "array", "value": [], "sourceDeclaredType": "[cc.SpriteFrame]"},
                       {"name": "spriteRefs", "kind": "array", "value": [
                           {"kind": "component_ref", "value": "asset:arrays#1/components/5"}],
                        "sourceDeclaredType": "[cc.Sprite]"},
                       {"name": "opaque", "kind": "array", "value": [], "sourceDeclaredType": "[lD]"},
                       {"name": "strings", "kind": "array", "value": [
                           {"kind": "string", "value": "a"}], "sourceDeclaredType": "[cc.String]"},
                   ]}
            report = prepare([row], "creator", "Recovered", directory)
            fields = {field["sourceFieldName"]: field for field in report["bindings"][row["sourceId"]]["fields"]}
            self.assertEqual(fields["labels"]["storageType"], "string[]")
            self.assertEqual(fields["labels"]["creatorElementType"], "CCString")
            self.assertEqual(fields["indices"]["creatorElementType"], "CCInteger")
            self.assertEqual(fields["flags"]["creatorElementType"], "CCBoolean")
            self.assertEqual(fields["renders"]["creatorElementType"], "Component")
            self.assertEqual(fields["sprites"]["creatorElementType"], "Sprite")
            self.assertEqual(fields["frames"]["creatorElementType"], "SpriteFrame")
            self.assertEqual(fields["spriteRefs"]["refValues"], ["asset:arrays#1/components/5"])
            self.assertEqual(fields["spriteRefs"]["creatorElementType"], "Sprite")
            self.assertEqual(fields["strings"]["stringValues"], ["a"])
            self.assertEqual(fields["opaque"]["mode"], "snapshot-json")
            self.assertIn("array_not_native_typed:opaque", report["bindings"][row["sourceId"]]["gaps"])
            script = Path(directory, report["scripts"][0]["source"]).read_text()
            self.assertIn("@property(CCBoolean)", script)
            self.assertIn("@property(CCInteger)", script)
            self.assertIn("@property(CCFloat)", script)
            self.assertIn("@property([CCString])", script)
            self.assertIn("@property([CCInteger])", script)
            self.assertIn("@property([CCBoolean])", script)
            self.assertIn("@property([Component])", script)
            self.assertIn("@property([Sprite])", script)
            self.assertIn("@property([Sprite]) public __sf_009_spriteRefs: Sprite[] = []", script)
            self.assertIn("@property([SpriteFrame])", script)
            self.assertIn("Sprite[] = []", script)
            self.assertIn("SpriteFrame[] = []", script)
            self.assertNotIn("@property(Boolean)", script)
            self.assertNotIn("@property(Number)", script)
            self.assertNotIn("@property(String)", script)
            self.assertNotIn("type: String", script)

    def test_declared_object_record_array_generates_typed_classes_and_preserves_refs(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve()
            descriptor = {"kind": "array", "element": {"kind": "record", "name": "WeekTaskStateBgEntry", "fields": [
                {"name": "state", "kind": "float", "value": 0, "sourceDeclaredType": "cc.Enum(State)",
                 "enumValues": [{"name": "INCOMPLETE", "value": 0}, {"name": "COMPLETED", "value": 1}]},
                {"name": "texture", "kind": "null", "value": None, "sourceDeclaredType": "cc.SpriteFrame"},
            ]}}
            row = {"sourceId": "asset:records#1/components/0", "node": "asset:records#1",
                   "sourceType": "example.RecordFields", "declarationDefaults": "verified", "gaps": [],
                   "fields": [{"name": "entries", "kind": "array", "sourceDeclaredType": "__monkey_static_type_v1__:" + json.dumps(descriptor),
                       "value": [
                           {"kind": "object", "value": {"__type__": {"kind": "string", "value": "WeekTaskStateBgEntry"},
                               "texture": {"kind": "asset_ref", "value": "bundle:exact-sprite-frame"}}},
                           {"kind": "object", "value": {"__type__": {"kind": "string", "value": "WeekTaskStateBgEntry"},
                               "state": {"kind": "float", "value": 1},
                               "texture": {"kind": "asset_ref", "value": "bundle:second-sprite-frame"}}},
                       ]}]}
            for target in ("unity", "creator"):
                report = prepare([row], target, "Recovered", directory / target)
                spec = report["bindings"][row["sourceId"]]
                field = spec["fields"][0]
                self.assertFalse(any("array_not_native_typed" in gap for gap in spec["gaps"]))
                self.assertEqual(field["elementKind"], "record")
                self.assertEqual(len(field["recordValues"]), 2)
                first = {item["sourceFieldName"]: item for item in field["recordValues"][0]["fields"]}
                self.assertEqual(first["state"]["value"], 0)
                self.assertEqual(first["texture"]["value"], "bundle:exact-sprite-frame")
                self.assertEqual(first["texture"]["refValue"], "bundle:exact-sprite-frame")
                second = {item["sourceFieldName"]: item for item in field["recordValues"][1]["fields"]}
                self.assertEqual(second["texture"]["value"], "bundle:second-sprite-frame")
                script = Path(directory, target, report["scripts"][0]["source"]).read_text()
                self.assertIn("WeekTaskStateBgEntry", script)
                self.assertIn("state", script)
                self.assertIn("texture", script)
                if target == "creator":
                    self.assertIn("SpriteFrame", script.splitlines()[1])
                    self.assertIn("SpriteFrame | null", script)

    def test_declared_object_record_array_rejects_unknown_object_identity(self):
        descriptor = {"kind": "array", "element": {"kind": "record", "name": "TypedEntry", "fields": [
            {"name": "value", "kind": "float", "value": 0, "sourceDeclaredType": "cc.Float"}]}}
        row = {"sourceId": "asset:bad-record#1/components/0", "node": "asset:bad-record#1",
               "sourceType": "example.BadRecord", "gaps": [], "fields": [
                   {"name": "entries", "kind": "array", "sourceDeclaredType": "__monkey_static_type_v1__:" + json.dumps(descriptor),
                    "value": [{"kind": "object", "value": {"__type__": {"kind": "string", "value": "DifferentEntry"},
                        "value": {"kind": "float", "value": 1}}}]}]}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(StaticCarrierError):
                prepare([row], "unity", "Recovered", Path(directory) / "out")

    def test_emit_verifies_hash_and_writes_owned_meta(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve()
            prepared = prepare([snapshot()], "unity", "Recovered", directory)
            plan = {"staticFieldScripts": prepared["scripts"]}
            candidate = Path(directory, "candidate")
            written = emit(plan, directory, "unity", candidate)
            self.assertEqual(written, [prepared["scripts"][0]["target"]])
            meta = Path(candidate, written[0] + ".meta")
            self.assertIn(prepared["scripts"][0]["identity"], meta.read_text())
            with self.assertRaises(StaticCarrierError):
                emit(plan, directory, "unity", candidate)


if __name__ == "__main__":
    unittest.main()
