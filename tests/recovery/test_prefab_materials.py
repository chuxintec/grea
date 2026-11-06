import json
import hashlib
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from grea.recovery import prefab_materials
from grea.recovery.prefab_materials import (MaterialProfileError, _validate_binding_spec, emit_ui_color,
                                    generate_ui_color, inspect_ui_color, plan_ui_color,
                                    plan_ui_color_for_origins)
from grea.recovery import prefab_material_pipeline
from grea.recovery.prefab_static_presentation import apply_unity
from grea.recovery.prefab_static_button_targets import apply as apply_button_targets


def _asset(source_id, kind, index, doc, *, refs=None, path=None, ordinal=None):
    return {
        "sourceId": source_id,
        "kind": kind,
        "index": index,
        "logicalPath": path or kind,
        "bundle": "gameAsset",
        "importPath": "import/00/fixture.json",
        "pack": "fixture",
        "packOrdinal": ordinal if ordinal is not None else index,
        "references": refs or [],
        "document": {"root": 0, "instances": [doc]},
    }


def _fixture(tmp: Path, *, nonzero=True, add_unknown=False, changed_formula=False):
    pack = tmp / "source/import/00/fixture.json"
    pack.parent.mkdir(parents=True)
    pack.write_text('{"fixture":"immutable source bytes"}', encoding="utf-8")
    effect_uuid = "effect-fixture-id"
    mat_uuid = "material-fixture-id"
    vert = "vec4 vert () { return vec4(1.0); }"
    frag = "vec4 frag () { return vec4(1.0); }"
    if changed_formula:
        frag = "vec4 frag () { return vec4(0.0); }"
    effect = {
        "__type__": "cc.EffectAsset", "_uuid": effect_uuid, "_name": "shader-2d-uiColor",
        "shaders": [{"name": "shader-2d-uiColor|vs|fs",
                      "glsl1": {"vert": vert, "frag": frag},
                      "glsl3": {"vert": vert, "frag": frag}}],
        "techniques": [{"passes": [{"program": "shader-2d-uiColor|vs|fs", "properties": {
            "brightness": {"value": [1]}, "saturation": {"value": [1]},
            "constrast": {"value": [1]}, "gray": {"value": [0]},
            "silhouette": {"value": [1, 1, 1, 1]}, "texture": {"value": "white"},
        }}]}],
    }
    held_effect = {"__type__": "cc.EffectAsset", "_name": "unported-effect", "shaders": [], "techniques": []}
    props = ({"brightness": 1.25, "saturation": 0.6, "constrast": 1.4, "gray": 0.35,
              "silhouette": {"__value_type__": 4, "values": [0x336699CC]}} if nonzero
             else {"gray": 0, "saturation": 1})
    material = {"__type__": "cc.Material", "_uuid": mat_uuid, "_name": "shader-2d-uiColor",
                "_effectAsset": {"__uuid__": effect_uuid},
                "_techniqueData": {"0": {"defines": {"USE_TEXTURE": True}, "props": props}}}
    held_material = {"__type__": "cc.Material", "_name": "keep-me",
                     "_effectAsset": {"__uuid__": "held-effect-id"}, "_techniqueData": {"0": {"props": {"unknown": 7}}}}
    prefab = {"__type__": "cc.Prefab", "_name": "Fixture",
              "data": {"__id__": 1}}
    sprite = {"__type__": "cc.Sprite", "_materials": [{"__uuid__": mat_uuid}],
              "_spriteFrame": {"__uuid__": "frame-id"}}
    inline_node = {"__type__": "cc.Node", "_name": "inline-node", "_components": [
        {"__type__": "cc.Sprite", "_materials": [{"__uuid__": mat_uuid}],
         "_spriteFrame": {"__uuid__": "frame-id"}}]}
    frame = {"__type__": "cc.SpriteFrame", "_textureSetter": {"__uuid__": "texture-id"}}
    texture = {"__type__": "cc.Texture2D"}
    assets = [
        _asset("gameAsset:effect-fixture-id", "cc.EffectAsset", 11, effect, path="Shader/shader-2d-uiColor"),
        _asset("gameAsset:material-fixture-id", "cc.Material", 12, material, refs=[effect_uuid], path="Shader/shader-2d-uiColor"),
        _asset("gameAsset:fixture-prefab", "cc.Prefab", 1, prefab, refs=["material-fixture-id", "held-material-id"], path="Prefab/Fixture"),
        _asset("gameAsset:frame-id", "cc.SpriteFrame", 13, frame, path="Sprite/Frame"),
        _asset("gameAsset:texture-id", "cc.Texture2D", 14, texture, path="Texture/Frame"),
        _asset("gameAsset:held-material-id", "cc.Material", 15, held_material, refs=["held-effect-id"], path="Shader/Unported"),
        _asset("gameAsset:held-effect-id", "cc.EffectAsset", 16, held_effect, path="Shader/unported-effect"),
    ]
    assets[2]["document"]["instances"].append(sprite)
    assets[2]["document"]["instances"].append(inline_node)
    if add_unknown:
        assets[1]["document"]["instances"][0]["_techniqueData"]["0"]["props"]["mystery"] = 9
    manifest = {"assets": assets, "selection": [1], "sourceRoots": {"gameAsset": str(tmp / "source")}}
    path = tmp / "source-manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _fixture_profile(manifest_path):
    manifest = json.loads(Path(manifest_path).read_text())
    effect = manifest["assets"][0]["document"]["instances"][0]
    return patch.object(prefab_materials, "UI_COLOR_STAGE_HASHES", prefab_materials._stage_hashes(effect))


def _bundle_alias_fixture(tmp: Path, *, change_material=False, change_effect=False):
    tmp=tmp.resolve()
    manifest_path=_fixture(tmp/'base')
    manifest=json.loads(manifest_path.read_text())
    assets=manifest['assets']
    by_id={row['sourceId']:row for row in assets}
    mini_root=tmp/'miniGameRes';mini_pack=mini_root/'import/00/fixture.json'
    mini_pack.parent.mkdir(parents=True);mini_pack.write_text('{"bundle":"miniGameRes"}')
    manifest['sourceRoots']['miniGameRes']=str(mini_root)
    original_prefab=copy.deepcopy(by_id['gameAsset:fixture-prefab'])
    original_prefab.update(sourceId='miniGameRes:fixture-prefab-copy',bundle='miniGameRes',index=2,pack='fixture-mini')
    original_prefab['importPath']='import/00/fixture.json'
    original_prefab['references']=['material-fixture-id']
    aliases=[]
    for source_id in ('gameAsset:material-fixture-id','gameAsset:effect-fixture-id',
                      'gameAsset:frame-id','gameAsset:texture-id'):
        row=copy.deepcopy(by_id[source_id]);row['sourceId']='miniGameRes:'+source_id.split(':',1)[1]
        row['bundle']='miniGameRes';row['pack']='fixture-mini';row['importPath']='import/00/fixture.json'
        if row['sourceId']=='miniGameRes:material-fixture-id' and change_material:
            row['document']['instances'][0]['_techniqueData']['0']['props']['gray']=0.25
        if row['sourceId']=='miniGameRes:effect-fixture-id' and change_effect:
            row['document']['instances'][0]['shaders'][0]['glsl1']['frag']='vec4 frag () { return vec4(0.25); }'
        aliases.append(row)
    assets.extend([original_prefab,*aliases]);manifest['selection']=[1,2]
    manifest['sourceProfile']='cocos-2.4.15-bundle'
    manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
    manifest_sha=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    components=[]
    for bundle,prefab in [('gameAsset','fixture-prefab'),('miniGameRes','fixture-prefab-copy')]:
        for suffix in ('#1','#2/components/0'):
            components.append(dict(type='cc.Sprite',sourceId=f'{bundle}:{prefab}{suffix}',
                materials=[f'{bundle}:material-fixture-id'],spriteFrame=f'{bundle}:frame-id'))
    ir={'sourceProfile':'cocos-2.4.15-bundle','sourceManifestPath':str(manifest_path),
        'sourceManifestSha256':manifest_sha,'aliases':{},'components':components}
    ir_path=tmp/'bundle-alias-ir.json';ir_path.write_text(json.dumps(ir),encoding='utf-8')
    ir_raw=ir_path.read_bytes()
    (tmp/'manifest.json').write_text(json.dumps({'files':[{'path':ir_path.name,'bytes':len(ir_raw),
        'sha256':hashlib.sha256(ir_raw).hexdigest()}]}),encoding='utf-8')
    return manifest_path,ir_path,ir


class PrefabMaterialTests(unittest.TestCase):
    def test_inspection_follows_selected_prefab_material_effect_spriteframe_texture(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = _fixture(Path(temp))
            with _fixture_profile(manifest):
                result = inspect_ui_color(manifest)
            self.assertEqual(result["profile"], "cocos24-ui-color-sprite-v1")
            self.assertEqual(result["source"]["effectSourceId"], "gameAsset:effect-fixture-id")
            self.assertEqual(result["source"]["materialSourceId"], "gameAsset:material-fixture-id")
            self.assertEqual(len(result["source"]["prefabOccurrences"]), 2)
            self.assertIn("gameAsset:fixture-prefab#2/components/0",
                          [row["componentSourceId"] for row in result["source"]["prefabOccurrences"]])
            self.assertEqual(result["source"]["textures"][0]["sourceId"], "gameAsset:texture-id")
            self.assertEqual(result["material"]["properties"]["silhouette"], [0x33 / 255, 0x66 / 255, 0x99 / 255, 0xCC / 255])
            self.assertEqual(result["source"]["selectedMaterialScope"]["retainedOutsideProfileCount"], 1)
            retained = next(row for row in result["source"]["selectedMaterialScope"]["materials"]
                            if row["materialSourceId"] == "gameAsset:held-material-id")
            self.assertEqual(retained["status"], "retained-outside-profile")
            self.assertEqual(retained["effectName"], "unported-effect")

    def test_dual_target_candidate_preserves_nonzero_parameter_counterexample(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = _fixture(root)
            with _fixture_profile(manifest):
                report = generate_ui_color(manifest, root / "candidate")
            self.assertEqual(report["nativeCompilation"], "not_run")
            self.assertEqual(report["creatorEditorImport"], "not_run")
            self.assertEqual(report["unity"]["properties"]["gray"], 0.35)
            self.assertEqual(report["unity"]["properties"]["brightness"], 1.25)
            self.assertEqual(report["creator38"]["properties"]["constrast"], 1.4)
            unity_mat = (root / "candidate/Unity/Shader2DUIColor.mat").read_text()
            creator_contract = json.loads((root / "candidate/Creator38/Shader2DUIColor.material-contract.json").read_text())
            self.assertIn("_Gray: 0.35", unity_mat)
            self.assertEqual(creator_contract["properties"]["silhouette"], [0x33 / 255, 0x66 / 255, 0x99 / 255, 0xCC / 255])
            self.assertTrue((root / "candidate/Unity/Shader2DUIColor.shader").is_file())
            self.assertTrue((root / "candidate/Creator38/Shader2DUIColor.effect").is_file())
            self.assertEqual(report["creator38"]["materialStatus"], "runtime-editor-contract-only-native-material-identity-pending")

    def test_rejects_unaccounted_material_parameter_instead_of_dropping_it(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = _fixture(Path(temp), add_unknown=True)
            with _fixture_profile(manifest):
                with self.assertRaisesRegex(MaterialProfileError, "outside the supported property contract"):
                    inspect_ui_color(manifest)

    def test_refuses_candidate_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = _fixture(root)
            output = root / "candidate"
            output.mkdir()
            (output / "keep.txt").write_text("human-owned")
            with _fixture_profile(manifest):
                with self.assertRaises(FileExistsError):
                    generate_ui_color(manifest, output)
            self.assertEqual((output / "keep.txt").read_text(), "human-owned")

    def test_same_program_name_with_changed_shader_formula_is_rejected_by_stage_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline = _fixture(root / "baseline")
            changed = _fixture(root / "changed", changed_formula=True)
            with _fixture_profile(baseline):
                with self.assertRaisesRegex(MaterialProfileError, "expected one exact uiColor source program profile"):
                    inspect_ui_color(changed)

    def test_pinned_plan_and_emit_keep_native_materials_out_of_owned_yaml_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = _fixture(root)
            with _fixture_profile(manifest):
                source = inspect_ui_color(manifest)
                source_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
                ir = {"sourceManifestSha256": source_sha,
                      "components": [{"type": "cc.Sprite", "materials": [source["source"]["materialSourceId"]],
                                      "sourceId": row["componentSourceId"],
                                      "spriteFrame":"gameAsset:"+row["spriteFrameUuid"]}
                                     for row in source["source"]["prefabOccurrences"]]}
                ir_path = root / "ir.json"
                ir_path.write_text(json.dumps(ir), encoding="utf-8")
                ir_sha = hashlib.sha256(ir_path.read_bytes()).hexdigest()
                plan = plan_ui_color(manifest, ir_path, "UiColorModule", source_sha, ir_sha)
                self.assertEqual(plan["spec"]["materialSourceId"], "gameAsset:material-fixture-id")
                self.assertNotIn("sourceMaterialId", plan["spec"])
                self.assertEqual(plan["spec"]["sourceIrComponentIds"]["exactMatch"], True)
                self.assertEqual(plan["spec"]["creator"]["materialPath"],
                                 "assets/resources/Materials/UiColorModule/Shader2DUIColor.mtl")
                self.assertEqual(plan["spec"]["unity"]["materialPath"],
                                 "Assets/Game/Content/Materials/UiColorModule/Shader2DUIColor.mat")
                self.assertFalse(any(row["path"].endswith(".mat") or row["path"].endswith(".mtl")
                                     for row in plan["ownedFiles"]))
                emitted = emit_ui_color(plan, Path(__file__).parents[2], root / "candidate")
                self.assertEqual(emitted["status"], "owned-files-emitted-native-assets-pending")
                self.assertTrue((root / "candidate/Assets/Game/Content/Shaders/UiColorModule/Shader2DUIColor.shader").is_file())
                self.assertTrue((root / "candidate/assets/resources/Shaders/UiColorModule/Shader2DUIColor.effect").is_file())
                self.assertTrue((root / "candidate/Assets/Game/Content/Materials/UiColorModule/Shader2DUIColor.mat.meta").is_file())
                self.assertFalse((root / "candidate/Assets/Game/Content/Materials/UiColorModule/Shader2DUIColor.mat").exists())

    def test_native_spec_structure_rejects_legacy_material_id_alias(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = _fixture(root)
            with _fixture_profile(manifest):
                source = inspect_ui_color(manifest)
                source_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
                ir = {"sourceManifestSha256": source_sha,
                      "components": [{"type": "cc.Sprite", "materials": [source["source"]["materialSourceId"]],
                                      "sourceId": row["componentSourceId"],
                                      "spriteFrame":"gameAsset:"+row["spriteFrameUuid"]}
                                     for row in source["source"]["prefabOccurrences"]]}
                ir_path = root / "ir.json"; ir_path.write_text(json.dumps(ir), encoding="utf-8")
                ir_sha = hashlib.sha256(ir_path.read_bytes()).hexdigest()
                spec = plan_ui_color(manifest, ir_path, "UiColorModule", source_sha, ir_sha)["spec"]
                _validate_binding_spec(spec)
                bad = copy.deepcopy(spec)
                bad["sourceMaterialId"] = bad.pop("materialSourceId")
                with self.assertRaisesRegex(MaterialProfileError, "canonical materialSourceId"):
                    _validate_binding_spec(bad)

    def test_bundle_qualified_duplicate_materials_share_only_exact_profile_and_keep_per_sprite_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);manifest_path,ir_path,ir=_bundle_alias_fixture(root)
            with _fixture_profile(manifest_path):
                source=inspect_ui_color(manifest_path,ir_path)
                manifest_sha=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
                ir_sha=hashlib.sha256(ir_path.read_bytes()).hexdigest()
                fragment=plan_ui_color(manifest_path,ir_path,'UiColorModule',manifest_sha,ir_sha)
                profile,gaps=prefab_material_pipeline.discover(ir,ir_path)
            spec=fragment['spec']
            self.assertEqual(spec['sourceMaterialIds'],['gameAsset:material-fixture-id','miniGameRes:material-fixture-id'])
            self.assertEqual(len(spec['sourceMaterialBindings']),2)
            self.assertEqual(len(spec['sourceComponentMaterialBindings']),4)
            self.assertTrue(source['source']['normalizedIR']['sourceToIRComponentIds']['exactMatch'])
            self.assertFalse(gaps);self.assertIsNotNone(profile)
            def resolve(value):return ir.get('aliases',{}).get(value,value)
            for component in ir['components']:
                self.assertTrue(prefab_material_pipeline.supported_component(component,profile,resolve))
            tampered=copy.deepcopy(profile)
            tampered['spec']['sourceComponentMaterialBindings'][0]['sourceMaterialId']='miniGameRes:material-fixture-id'
            for component in ir['components']:
                if component['sourceId']==tampered['spec']['sourceComponentMaterialBindings'][0]['sourceId']:
                    self.assertFalse(prefab_material_pipeline.supported_component(component,tampered,resolve))

    def test_nonidentical_bundle_material_copy_is_not_grouped_or_silently_projected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);manifest_path,ir_path,_=_bundle_alias_fixture(root,change_material=True)
            with _fixture_profile(manifest_path):
                with self.assertRaisesRegex(MaterialProfileError,'distinct bundle-qualified uiColor material profiles'):
                    inspect_ui_color(manifest_path,ir_path)

    def test_changed_duplicate_effect_does_not_promote_its_bundle_consumers(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);manifest_path,ir_path,ir=_bundle_alias_fixture(root,change_effect=True)
            with _fixture_profile(manifest_path):
                source=inspect_ui_color(manifest_path,ir_path)
            self.assertEqual(source['source']['materialSourceIds'],['gameAsset:material-fixture-id'])
            self.assertEqual({row['sourceId'] for row in source['source']['normalizedIR']['components']},
                             {'gameAsset:fixture-prefab#1','gameAsset:fixture-prefab#2/components/0'})

    def test_origin_scoped_material_fragment_and_plan_bound_instances_keep_exact_source_joins(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();manifest_path,ir_path,ir=_bundle_alias_fixture(root)
            origins=[row['sourceId'] for row in ir['components']]
            source_sha=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            ir_sha=hashlib.sha256(ir_path.read_bytes()).hexdigest()
            with _fixture_profile(manifest_path):
                physical=plan_ui_color_for_origins(manifest_path,ir_path,source_sha,ir_sha,origins)
                bindings=[]
                for row in ir['components']:
                    bindings.append(dict(sourceId=row['sourceId'],sourceOriginId=row['sourceId'],
                        sourceMaterialId=row['materials'][0],spriteFrameSourceId=row['spriteFrame']))
                bindings.extend([
                    dict(sourceId='instance:prefabA::sync-sprite',sourceOriginId=origins[1],
                         sourceMaterialId=ir['components'][1]['materials'][0],spriteFrameSourceId=ir['components'][1]['spriteFrame']),
                    dict(sourceId='instance:prefabB::sync-sprite',sourceOriginId=origins[3],
                         sourceMaterialId=ir['components'][3]['materials'][0],spriteFrameSourceId=ir['components'][3]['spriteFrame'])])
                projected=plan_ui_color(manifest_path,ir_path,'UiColorModule',source_sha,ir_sha,
                    source_component_bindings=bindings,source_plan_sha256='a'*64)
            self.assertEqual(physical['spec']['sourceComponentIds'],origins)
            self.assertEqual(physical['spec']['sourceComponentMaterialBindings'][0]['sourceOriginId'],origins[0])
            self.assertEqual(set(projected['spec']['sourceComponentIds']),{row['sourceId'] for row in bindings})
            self.assertEqual(projected['spec']['sourcePlanSha256'],'a'*64)
            self.assertEqual(len(projected['spec']['sourceIrComponentIds']['source']),4)
            tampered=copy.deepcopy(bindings);tampered[-1]['sourceMaterialId']='gameAsset:other-material-id'
            with _fixture_profile(manifest_path):
                with self.assertRaisesRegex(MaterialProfileError,'selected source component does not exactly join'):
                    plan_ui_color(manifest_path,ir_path,'UiColorModule',source_sha,ir_sha,
                        source_component_bindings=tampered,source_plan_sha256='a'*64)

    def test_material_resolved_sprite_remains_the_button_target_graphic(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();manifest_path,ir_path,ir=_bundle_alias_fixture(root)
            with _fixture_profile(manifest_path):
                profile,gaps=prefab_material_pipeline.discover(ir,ir_path)
                self.assertFalse(gaps)
                (root/'material-stage').mkdir()
                binding=prefab_material_pipeline.prepare(profile,'unity',root/'material-stage')
            target_id='gameAsset:fixture-prefab#target'
            button_id='gameAsset:fixture-prefab#button'
            sprite=copy.deepcopy(ir['components'][1]);sprite.update(node=target_id,convertible=False,mode=2,trim=True,sizeMode=0)
            button=dict(sourceId=button_id,node='gameAsset:fixture-prefab#button-node',target=target_id,
                        type='cc.Button',transition=1,interactable=True,convertible=True,
                        staticButtonBinding=dict(renderReady=True,sourceFields={'target':'authored'}))
            plan=dict(targetProfile='unity-6000.6.2f1-ugui',sourceManifestSha256=profile['spec']['sourceManifestSha256'],
                      sourceManifestPath=str(manifest_path),materialBinding=binding,components=[sprite,button],
                      textures=[dict(id='gameAsset:frame-id',path='Assets/Game/Content/Textures/frame.png',size=[16,16],originalSize=[16,16],offset=[0,0],border=[0,0,0,0]),
                                dict(id='gameAsset:frame-id@original',path='Assets/Game/Content/Textures/frame-untrimmed.png',size=[16,16],originalSize=[16,16],offset=[0,0],border=[0,0,0,0])],
                      assets=[],nodes=[])
            with _fixture_profile(manifest_path):
                profile_sha=prefab_materials._program_profile_hash(prefab_materials.UI_COLOR_STAGE_HASHES)
                with patch('grea.recovery.prefab_static_presentation._UI_COLOR_PROGRAM_SHA256',profile_sha):
                    apply_unity(plan,json.loads(manifest_path.read_text()))
            self.assertTrue(sprite['convertible'])
            self.assertEqual(sprite['nativeMaterialSourceId'],'gameAsset:material-fixture-id')
            self.assertEqual(button['target'],sprite['node'])
            self.assertEqual([],apply_button_targets(plan))
            importer=(Path(__file__).parents[2]/'src/grea/recovery/targets/UnityImporter.cs').read_text()
            self.assertIn('button.targetGraphic=target.GetComponent<UnityEngine.UI.Graphic>()',importer)
            self.assertIn('STATIC_BUTTON_TARGET_GRAPHIC_MISSING',importer)

    def test_plan_requires_explicit_matching_manifest_and_ir_pins(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = _fixture(root)
            source_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
            ir_path = root / "ir.json"
            ir_path.write_text(json.dumps({"sourceManifestSha256": source_sha, "components": []}), encoding="utf-8")
            ir_sha = hashlib.sha256(ir_path.read_bytes()).hexdigest()
            with _fixture_profile(manifest):
                with self.assertRaisesRegex(MaterialProfileError, "explicit source manifest/IR pin mismatch"):
                    plan_ui_color(manifest, ir_path, "UiColorModule", "0" * 64, ir_sha)

    def test_binding_helpers_use_native_asset_creation_and_persisted_readback_apis(self):
        target = Path(__file__).parents[2] / "src/grea/recovery/targets/materials/ui_color"
        unity = (target / "UnityMaterialBindings.cs").read_text()
        creator = (target / "CreatorMaterialBindings.js").read_text()
        self.assertIn("AssetDatabase.CreateAsset(material, spec.materialPath)", unity)
        self.assertIn("AssetDatabase.TryGetGUIDAndLocalFileIdentifier", unity)
        self.assertIn("EnsurePlannedMaterialMeta(spec)", unity)
        self.assertIn("ShaderUtil.ShaderHasError(shader)", unity)
        self.assertIn("EditorExtends.serialize(material)", creator)
        self.assertIn("saveAndReload({ assetPath: spec.creator.materialPath", creator)
        self.assertIn("record.metaContents", creator)
        self.assertIn("record.metaPath !== spec.creator.materialMetaPath", creator)
        self.assertIn("meta.uuid !== spec.creator.materialUuid", creator)
        self.assertIn("sprite.customMaterial = savedMaterial", creator)
        self.assertIn("MATERIAL_PROFILE_UNSUPPORTED", creator)


if __name__ == "__main__":
    unittest.main()
