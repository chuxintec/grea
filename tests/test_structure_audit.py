import tempfile
import unittest
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from beaver.errors import BeaverError
from beaver.structure_audit import _case_collisions, build_plan, inspect


def put(root, rel, text=b"x"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text if isinstance(text, bytes) else text.encode())
    return path


def native_readback(root, asset_path, imported_type="Texture2D", local_id=2800000, guid="a" * 32):
    source = root / asset_path
    meta = Path(str(source) + ".meta")
    meta.write_text("fileFormatVersion: 2\nguid: " + guid + "\n", encoding="utf-8")
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "schemaVersion": 1, "contract": "beaver-native-readback/1", "status": "observed",
        "editorVersion": "6000.6.2f1", "assets": [{"path": asset_path, "importedType": imported_type,
          "objects": [{"path": asset_path, "guid": guid, "type": "Sprite", "name": "Coin",
                       "state": "persistent", "localId": local_id}]}],
        "fields": [], "capture": None, "errors": [], "editorExitCode": 0,
        "sourceUnchanged": True, "unplannedProjectChanges": [], "helperCleaned": True,
        "inputState": {asset_path: {"sha256": digest(source), "bytes": source.stat().st_size},
                       asset_path + ".meta": {"sha256": digest(meta), "bytes": meta.stat().st_size}},
        "nativeReadback": "read_only_native_snapshot", "visualAcceptance": "not-established",
        "gameplayAcceptance": "not-established", "provenance": {"collector": "synthetic-test"}}


class StructureAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.root = Path(self.tmp.name) / "Project"
        self.root.mkdir()
        (self.root / "Assets").mkdir()
        (self.root / "Packages").mkdir()
        (self.root / "ProjectSettings").mkdir()
        self.product = self.root.parent
        put(self.product, "grea-project.json", json.dumps({"schemaVersion": 1, "paths": {"unityProject": "Project"}}))
        put(self.product, "Docs/PROJECT-STRUCTURE.md", "Synthetic public fixture structure contract.\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_inspect_reports_resources_dynamic_loads_old_roots_and_hashes(self):
        put(self.root, "Assets/Product/Resources/Icons/Coin.png", b"image")
        put(self.root, "Assets/Product/Resources/Icons/Coin.png.meta", "guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
        put(self.root, "Assets/Scripts/Loader.cs", 'var a=Resources.Load<Sprite>("Icons/Coin"); var b=Resources.Load(key);')
        report = inspect(self.root)
        resource = next(x for x in report["resourceLoads"] if x["key"] == "Icons/Coin")
        self.assertEqual(resource["candidateAssets"], ["Assets/Product/Resources/Icons/Coin.png"])
        self.assertTrue(any(x["code"] == "DYNAMIC_LOAD_UNRESOLVED" for x in report["issues"]))
        self.assertTrue(any(x["code"] == "RETIRED_ROOT" for x in report["issues"]))
        self.assertEqual(len(report["sourceHashes"]["Assets/Product/Resources/Icons/Coin.png"]), 64)

    def test_unity_subroot_uses_parent_product_profile_and_bound_docs(self):
        report = inspect(self.root)
        self.assertEqual(report["productRoot"], str(self.product))
        self.assertEqual(report["profileIdentity"]["path"], "grea-project.json")
        self.assertEqual(report["profileIdentity"]["unityProject"], "Project")
        self.assertEqual(report["structureDocumentationIdentity"]["path"], "Docs/PROJECT-STRUCTURE.md")
        self.assertTrue(report["structureDocumentationIdentity"]["present"])
        self.assertTrue(all(not p.startswith("Project/") for p in report["scannedInputPaths"]))
        explicit = inspect(self.root, product_root=self.product, profile_path="grea-project.json")
        self.assertEqual(explicit["profileIdentity"], report["profileIdentity"])

    def test_explicit_profile_wrong_binding_or_escape_fails_closed(self):
        wrong_root = self.product / "Wrong"
        wrong_root.mkdir()
        put(wrong_root, "grea-project.json", json.dumps({"schemaVersion": 1, "paths": {"unityProject": "Project"}}))
        with self.assertRaises(BeaverError):
            inspect(self.root, product_root=wrong_root, profile_path="grea-project.json")
        profile = self.product / "grea-project.json"
        profile.write_text(json.dumps({"schemaVersion": 1, "paths": {"unityProject": "../outside"}}), encoding="utf-8")
        with self.assertRaises(BeaverError):
            inspect(self.root, product_root=self.product, profile_path="grea-project.json")

    def test_profile_change_invalidates_plan_governance_precondition(self):
        put(self.root, "Assets/Game/A.asset", b"asset")
        native = native_readback(self.root, "Assets/Game/A.asset", "ScriptableObject", 77)
        audit = inspect(self.root)
        (self.product / "grea-project.json").write_text(
            json.dumps({"schemaVersion": 1, "paths": {"unityProject": "Other"}}), encoding="utf-8")
        plan = build_plan(audit, [{"source": "Assets/Game/A.asset", "target": "Assets/Game/Domain/A.asset"}], native)
        self.assertEqual(plan["status"], "blocked")
        self.assertIn("GOVERNANCE_INPUT_STALE", {x["code"] for x in plan["blockers"]})

    def test_structure_document_deletion_invalidates_plan(self):
        put(self.root, "Assets/Game/A.asset", b"asset")
        native = native_readback(self.root, "Assets/Game/A.asset", "ScriptableObject", 77)
        audit = inspect(self.root)
        (self.product / "Docs/PROJECT-STRUCTURE.md").unlink()
        plan = build_plan(audit, [{"source": "Assets/Game/A.asset", "target": "Assets/Game/Domain/A.asset"}], native)
        self.assertEqual(plan["status"], "blocked")
        self.assertIn("GOVERNANCE_INPUT_STALE", {x["code"] for x in plan["blockers"]})

    def test_missing_profile_is_explicit_and_blocks_planning(self):
        (self.product / "grea-project.json").unlink()
        put(self.root, "Assets/Game/A.asset", b"asset")
        report = inspect(self.root)
        codes = {x["code"] for x in report["issues"]}
        self.assertIn("PRODUCT_ROOT_UNLOCATED", codes)
        self.assertIn("PROFILE_MISSING", codes)
        plan = build_plan(report, [{"source": "Assets/Game/A.asset", "target": "Assets/Game/Domain/A.asset"}])
        self.assertEqual(plan["status"], "blocked")
        self.assertIn("PROFILE_BINDING_MISSING", {x["code"] for x in plan["blockers"]})

    def test_plan_requires_native_identity_and_preserves_subasset_ids(self):
        source = put(self.root, "Assets/Product/Resources/Icons/Coin.png", b"image")
        put(self.root, "Assets/Product/Resources/Icons/Coin.png.meta", "guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")
        audit = inspect(self.root)
        mapping = [{"source": "Assets/Product/Resources/Icons/Coin.png",
                    "target": "Assets/Game/Content/Images/UI/Coin.png"}]
        blocked = build_plan(audit, mapping)
        self.assertEqual(blocked["status"], "blocked")
        native = native_readback(self.root, mapping[0]["source"])
        audit = inspect(self.root)
        declared = build_plan(audit, mapping, native)
        self.assertEqual(declared["status"], "declaration_only")
        self.assertEqual(declared["batchReadiness"], "not_evaluated")
        self.assertEqual(declared["mappings"][0]["objects"][0]["localId"], 2800000)
        self.assertEqual(declared["mappings"][0]["nativeProvenance"], {"collector": "synthetic-test"})
        self.assertEqual(declared["mappings"][0]["resourceKeyMapping"],
                         {"old": "Icons/Coin", "new": None, "consumerPatchesRequired": True,
                          "candidateAssets": [mapping[0]["source"]]})
        self.assertEqual(declared["batchSpec"]["steps"], [{"kind": "asset.move", **mapping[0]}])
        self.assertTrue(source.exists(), "Planning must not move or edit source files")

    def test_stale_native_source_or_meta_readback_blocks_plan(self):
        source = put(self.root, "Assets/Game/A.asset", b"before")
        native = native_readback(self.root, "Assets/Game/A.asset", "ScriptableObject", 77)
        audit = inspect(self.root)
        source.write_bytes(b"after")
        plan = build_plan(audit, [{"source": "Assets/Game/A.asset", "target": "Assets/Game/A2.asset"}], native)
        self.assertEqual(plan["status"], "blocked")
        self.assertIn("SOURCE_SNAPSHOT_STALE_OR_MISSING", {x["code"] for x in plan["blockers"]})
        source.write_bytes(b"before")
        (self.root / "Assets/Game/A.asset.meta").write_text("fileFormatVersion: 2\nguid: " + "b" * 32 + "\n")
        plan = build_plan(inspect(self.root), [{"source": "Assets/Game/A.asset", "target": "Assets/Game/A2.asset"}], native)
        self.assertIn("META_SNAPSHOT_STALE_OR_MISSING", {x["code"] for x in plan["blockers"]})

    def test_unverified_readback_is_rejected(self):
        put(self.root, "Assets/Game/A.asset", b"source")
        native = native_readback(self.root, "Assets/Game/A.asset", "ScriptableObject", 77)
        native["sourceUnchanged"] = False
        with self.assertRaises(BeaverError):
            build_plan(inspect(self.root), [{"source": "Assets/Game/A.asset", "target": "Assets/Game/A2.asset"}], native)

    def test_consumer_changed_after_audit_blocks_and_no_batch_spec_is_emitted(self):
        put(self.root, "Assets/Game/A.asset", b"source")
        consumer = put(self.root, "Assets/Game/Consumer.cs", "class Consumer {}")
        native = native_readback(self.root, "Assets/Game/A.asset", "ScriptableObject", 77)
        audit = inspect(self.root)
        consumer.write_text('Resources.Load(key);', encoding="utf-8")
        plan = build_plan(audit, [{"source": "Assets/Game/A.asset", "target": "Assets/Game/Domain/A.asset"}], native)
        self.assertEqual(plan["status"], "blocked")
        self.assertIsNone(plan["batchSpec"])
        self.assertEqual(plan["batchReadiness"], "not_evaluated")
        self.assertIn("AUDIT_CONSUMER_STALE", {x["code"] for x in plan["blockers"]})

    def test_mapping_count_and_import_extension_are_validated(self):
        audit = {"schema": "beaver-structure-audit/1"}
        with self.assertRaises(BeaverError):
            build_plan(audit, [])
        with self.assertRaises(BeaverError):
            build_plan(audit, [{"source": "Assets/A.png", "target": "Assets/Game/Content/Textures/A.jpg"}])

    def test_case_collisions_and_occupied_targets_are_reported_or_blocked(self):
        put(self.root, "Assets/Game/A.txt")
        report = inspect(self.root)
        self.assertEqual(_case_collisions(["Assets/Game/A.txt", "Assets/game/a.txt"]),
                         [["Assets/Game/A.txt", "Assets/game/a.txt"]])
        put(self.root, "Assets/Game/Occupied.txt")
        occupied_report = inspect(self.root)
        native = native_readback(self.root, "Assets/Game/A.txt", "TextAsset", 1)
        plan = build_plan(occupied_report, [{"source": "Assets/Game/A.txt", "target": "Assets/Game/Occupied.txt"}], native)
        self.assertEqual(plan["status"], "blocked")
        self.assertIsNone(plan["batchSpec"])
        self.assertEqual(plan["proposedSteps"], [{"kind": "asset.move", "source": "Assets/Game/A.txt", "target": "Assets/Game/Occupied.txt"}])

    def test_exceptions_require_complete_owned_rationale(self):
        put(self.root, "Assets/Product/Kept.asset", b"source")
        with self.assertRaises(BeaverError):
            inspect(self.root, exceptions={"schemaVersion": 1, "exceptions": [{"path": "Assets/Product", "reason": "legacy"}]})
        config = {"schemaVersion": 1, "exceptions": [{"path": "Assets/Product/Kept.asset", "ruleId": "STR-01",
                   "scope": "path", "reason": "serialized package identity", "alternativeConstraint": "preserve GUID",
                   "validation": "native readback", "owner": "project", "reviewTrigger": "package upgrade"}]}
        report = inspect(self.root, exceptions=config)
        issue = next(x for x in report["issues"] if x.get("path") == "Assets/Product/Kept.asset")
        self.assertEqual(issue["exceptionRuleId"], "STR-01")
        self.assertEqual(issue["severity"], "exception")

    def test_exception_requires_matching_rule_and_exact_path_scope(self):
        rel = "Assets/Game/Content/Textures/Panel.mat"
        put(self.root, rel, b"material")
        native = native_readback(self.root, rel, "UnityEngine.Material", 1)
        base = {"path": rel, "scope": "path", "reason": "serialized composite bundle",
                "alternativeConstraint": "keep companion material inside registered group",
                "validation": "native dependency readback", "owner": "project", "reviewTrigger": "bundle revision"}
        wrong_rule = inspect(self.root, native, {"schemaVersion": 1, "exceptions": [dict(base, ruleId="STR-02")]})
        wrong = next(x for x in wrong_rule["issues"] if x["code"] == "TYPE_DIRECTORY_MISMATCH")
        self.assertEqual(wrong["severity"], "warning")
        matching = inspect(self.root, native, {"schemaVersion": 1, "exceptions": [dict(base, ruleId="STR-05")]})
        type_issue = next(x for x in matching["issues"] if x["code"] == "TYPE_DIRECTORY_MISMATCH")
        self.assertEqual(type_issue["severity"], "exception")
        self.assertEqual(type_issue["exceptionRuleId"], "STR-05")

    def test_unhandled_dynamic_and_literal_key_consumers_block(self):
        source = put(self.root, "Assets/Product/Resources/Icons/Coin.png", b"image")
        put(self.root, "Assets/Scripts/Loader.cs", 'Resources.Load<Sprite>("Icons/Coin"); Resources.Load(key);')
        native = native_readback(self.root, "Assets/Product/Resources/Icons/Coin.png")
        audit = inspect(self.root)
        plan = build_plan(audit, [{"source": "Assets/Product/Resources/Icons/Coin.png",
                                   "target": "Assets/Game/Content/Images/Coin.png"}], native)
        codes = {x["code"] for x in plan["blockers"]}
        self.assertIn("DYNAMIC_RESOURCE_KEY_UNRESOLVED", codes)
        self.assertIn("RESOURCE_KEY_CONSUMER_UNHANDLED", codes)
        self.assertTrue(source.exists())

    def test_duplicate_resources_keys_and_conflicting_import_types_are_reported(self):
        first = put(self.root, "Assets/One/Resources/Icons/Coin.png", b"one")
        second = put(self.root, "Assets/Two/Resources/Icons/Coin.asset", b"two")
        put(self.root, "Assets/Scripts/Loader.cs", 'Resources.Load("Icons/Coin");')
        native1 = native_readback(self.root, "Assets/One/Resources/Icons/Coin.png", "Texture2D", 1)
        native2 = native_readback(self.root, "Assets/Two/Resources/Icons/Coin.asset", "CoinData", 2, "b" * 32)
        native1["assets"].extend(native2["assets"])
        native1["inputState"].update(native2["inputState"])
        report = inspect(self.root, native1)
        codes = {x["code"] for x in report["issues"] if x.get("key") == "Icons/Coin"}
        self.assertIn("RESOURCE_KEY_AMBIGUOUS", codes)
        self.assertIn("RESOURCE_TYPE_AMBIGUOUS", codes)
        self.assertTrue(first.exists() and second.exists())

    def test_native_types_flag_material_texture_mismatch_but_leave_unknown_types_unclassified(self):
        material = "Assets/Game/Content/Textures/Panel.mat"
        texture = "Assets/Game/Content/Materials/Panel.png"
        unknown = "Assets/Game/Content/Textures/Custom.blob"
        put(self.root, material, b"material")
        put(self.root, texture, b"texture")
        put(self.root, unknown, b"custom")
        snapshots = [native_readback(self.root, material, "UnityEngine.Material", 1, "a" * 32),
                     native_readback(self.root, texture, "UnityEngine.Texture2D", 2, "b" * 32),
                     native_readback(self.root, unknown, "Vendor.CustomAsset", 3, "c" * 32)]
        native = snapshots[0]
        for snap in snapshots[1:]:
            native["assets"].extend(snap["assets"])
            native["inputState"].update(snap["inputState"])
        report = inspect(self.root, native)
        mismatch = {x["path"] for x in report["issues"] if x["code"] == "TYPE_DIRECTORY_MISMATCH"}
        self.assertEqual(mismatch, {material, texture})
        self.assertTrue(any(x["code"] == "LEGACY_TEXTURES_PATH" and x["path"] == material
                            for x in report["issues"]))
        inventory = {row["path"]: row for row in report["inventory"]}
        self.assertEqual(inventory[unknown]["importedType"], "Vendor.CustomAsset")
        self.assertEqual(inventory[unknown]["nativeStatus"], "observed")
        self.assertFalse(any(x.get("path") == unknown for x in report["issues"] if x["code"] == "TYPE_DIRECTORY_MISMATCH"))

    def test_build_settings_scene_outside_standard_scenes_root_is_reported(self):
        scene = "Assets/Legacy/Start.unity"
        put(self.root, scene, "%YAML 1.1\n--- !u!1 &1\nGameObject:\n")
        put(self.root, scene + ".meta", "fileFormatVersion: 2\nguid: dddddddddddddddddddddddddddddddd\n")
        put(self.root, "ProjectSettings/EditorBuildSettings.asset",
            "%YAML 1.1\nEditorBuildSettings:\n  m_Scenes:\n  - enabled: 1\n    path: Assets/Legacy/Start.unity\n    guid: dddddddddddddddddddddddddddddddd\n")
        report = inspect(self.root)
        self.assertIn(scene, report["buildSceneEntries"])
        self.assertTrue(any(x["code"] == "BUILD_SCENE_NONSTANDARD_PATH" and x["path"] == scene
                            for x in report["issues"]))

    def test_entry_budget_returns_explicit_partial_blocking_audit(self):
        for name in ("A.asset", "B.asset", "C.asset", "D.asset"):
            put(self.root, "Assets/Game/" + name, b"data")
        with patch("beaver.structure_audit.MAX_AUDIT_FILES", 3):
            report = inspect(self.root)
        self.assertEqual(report["scanStatus"], "partial_budget")
        self.assertTrue(any(x["code"] == "STRUCTURE_SCAN_BUDGET_EXCEEDED" for x in report["issues"]))
        source = report["inventory"][0]["path"]
        target = "Assets/Game/Domain/" + Path(source).name
        plan = build_plan(report, [{"source": source, "target": target}])
        self.assertEqual(plan["status"], "blocked")
        self.assertIsNone(plan["batchSpec"])


    def test_legacy_scene_does_not_deadlock_incremental_remediation(self):
        scene='Assets/Legacy/Start.unity';item='Assets/Legacy/Item.prefab'
        put(self.root,scene,b'scene');put(self.root,scene+'.meta','guid: '+'d'*32+'\n')
        put(self.root,'ProjectSettings/EditorBuildSettings.asset','%YAML 1.1\nEditorBuildSettings:\n  m_Scenes:\n  - enabled: 1\n    path: '+scene+'\n    guid: '+'d'*32+'\n')
        put(self.root,item,b'prefab');native=native_readback(self.root,item,'UnityEngine.GameObject',1)
        audit=inspect(self.root,native)
        plan=build_plan(audit,[{'source':item,'target':'Assets/Game/Content/Prefabs/Item.prefab'}])
        self.assertEqual(plan['status'],'declaration_only')
        self.assertEqual(plan['projectConformance'],'not-established')
        self.assertTrue(any(x.get('path')==scene for x in plan['remainingStructureIssues']))
        self.assertIsNotNone(plan['batchSpec'])

    def test_legacy_scene_itself_can_be_planned_into_standard_location(self):
        scene='Assets/Legacy/Start.unity';put(self.root,scene,b'scene')
        native=native_readback(self.root,scene,'UnityEditor.SceneAsset',102900000,'d'*32)
        put(self.root,'ProjectSettings/EditorBuildSettings.asset','%YAML 1.1\nEditorBuildSettings:\n  m_Scenes:\n  - enabled: 1\n    path: '+scene+'\n    guid: '+'d'*32+'\n')
        plan=build_plan(inspect(self.root,native),[{'source':scene,'target':'Assets/Game/Scenes/Start.unity'}])
        self.assertEqual(plan['status'],'declaration_only')
        self.assertEqual(plan['remainingStructureIssues'],[])

    def test_generator_paths_in_any_root_and_json_consumers_block(self):
        asset='Assets/Legacy/Coin.png';put(self.root,asset,b'image')
        native=native_readback(self.root,asset)
        put(self.root,'Assets/Game/Editor/Generate.cs','class G { string p=@"Assets/Legacy/Coin.png"; }')
        put(self.root,'Assets/Game/Index.json','{"asset":"Assets/Legacy/Coin.png"}')
        plan=build_plan(inspect(self.root,native),[{'source':asset,'target':'Assets/Game/Content/Images/Coin.png'}])
        codes={x['code'] for x in plan['blockers']}
        self.assertIn('OLD_PATH_CONSUMER_UNHANDLED',codes)
        self.assertIn('JSON_ASSET_PATH_CONSUMER_UNHANDLED',codes)
        self.assertIsNone(plan['batchSpec'])

    def test_comments_do_not_become_generator_consumers(self):
        asset='Assets/Legacy/Coin.png';put(self.root,asset,b'image');native=native_readback(self.root,asset)
        put(self.root,'Assets/Game/Comment.cs','// old source "Assets/Legacy/Coin.png"\nclass C {}')
        plan=build_plan(inspect(self.root,native),[{'source':asset,'target':'Assets/Game/Content/Images/Coin.png'}])
        self.assertEqual(plan['status'],'declaration_only')

    def test_substring_assets_length_marker_is_ignored_but_exact_old_path_still_blocks(self):
        asset='Assets/Product/Coin.png';put(self.root,asset,b'image');native=native_readback(self.root,asset)
        put(self.root,'Assets/Game/Editor/Diagnostic.cs',
            'class D { string key=CandidatePrefab.Substring("Assets/".Length); string actual="Assets/Product/Coin.png"; }')
        audit=inspect(self.root,native)
        self.assertEqual([x['value'] for x in audit['pathConsumers']],['Assets/Product/Coin.png'])
        plan=build_plan(audit,[{'source':asset,'target':'Assets/Game/Content/Images/Coin.png'}])
        matches=[x for x in plan['blockers'] if x['code']=='OLD_PATH_CONSUMER_UNHANDLED']
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]['value'],'Assets/Product/Coin.png')

    def test_assets_root_lookup_and_dynamic_opaque_root_remain_conservatively_blocked(self):
        asset='Assets/Product/Coin.png';put(self.root,asset,b'image');native=native_readback(self.root,asset)
        put(self.root,'Assets/Game/Editor/Diagnostic.cs',
            'class D { object a=AssetDatabase.LoadAssetAtPath<GameObject>("Assets/" + key); string b=$"Assets/{folder}/Coin.png"; }')
        audit=inspect(self.root,native)
        self.assertTrue(any(x['code']=='OLD_PATH_CONSUMER' and x['value']=='Assets/' for x in audit['issues']))
        self.assertTrue(any(x['code']=='DYNAMIC_ASSET_PATH_UNRESOLVED' and x['prefix']=='Assets/' for x in audit['issues']))
        plan=build_plan(audit,[{'source':asset,'target':'Assets/Game/Content/Images/Coin.png'}])
        codes={x['code'] for x in plan['blockers']}
        self.assertIn('OLD_PATH_CONSUMER_UNHANDLED',codes)
        self.assertIn('DYNAMIC_ASSET_PATH_UNRESOLVED',codes)
        self.assertIn('DYNAMIC_ASSET_PATH_UNRESOLVED',{x['code'] for x in plan['blockers']})

    def test_same_resources_key_keeps_dynamic_coverage_without_blocking_move(self):
        asset='Assets/Product/Resources/Configuration/AiTasks.json'
        put(self.root,asset,b'{"task":1}')
        native=native_readback(self.root,asset,'TextAsset',1)
        put(self.root,'Assets/Game/Services/Configuration/Loader.cs',
            'class Loader { object Load(string key) { return Resources.Load(key); } }')
        audit=inspect(self.root,native)
        self.assertTrue(audit['dynamicLoads'])
        plan=build_plan(audit,[{'source':asset,'target':'Assets/Game/Content/Config/Resources/Configuration/AiTasks.json'}])
        self.assertEqual(plan['status'],'declaration_only')
        self.assertFalse(any(x['code']=='DYNAMIC_RESOURCE_KEY_UNRESOLVED' for x in plan['blockers']))
        row=plan['mappings'][0]
        self.assertEqual(row['resourceKeyMapping']['old'],row['resourceKeyMapping']['new'])
        self.assertEqual(len(plan['dynamicLoadCoverage']),len(audit['dynamicLoads']))
        self.assertIsNone(plan['dynamicLoadCoverage'][0]['staticPrefix'])

    def test_changed_resources_key_still_blocks_unresolved_dynamic_call(self):
        asset='Assets/Product/Resources/Configuration/AiTasks.json'
        put(self.root,asset,b'{"task":1}')
        native=native_readback(self.root,asset,'TextAsset',1)
        put(self.root,'Assets/Game/Services/Configuration/Loader.cs',
            'class Loader { object Load(string key) { return Resources.Load(key); } }')
        plan=build_plan(inspect(self.root,native),[
            {'source':asset,'target':'Assets/Game/Content/Config/Resources/NewConfiguration/AiTasks.json'}])
        self.assertIn('DYNAMIC_RESOURCE_KEY_UNRESOLVED',{x['code'] for x in plan['blockers']})

    def test_same_key_with_duplicate_resources_candidate_still_blocks(self):
        asset='Assets/Product/Resources/Configuration/AiTasks.json'
        put(self.root,asset,b'{"task":1}')
        put(self.root,'Assets/Other/Resources/Configuration/AiTasks.asset',b'duplicate')
        native=native_readback(self.root,asset,'TextAsset',1)
        put(self.root,'Assets/Game/Services/Configuration/Loader.cs',
            'class Loader { object Load(string key) { return Resources.Load(key); } }')
        plan=build_plan(inspect(self.root,native),[
            {'source':asset,'target':'Assets/Game/Content/Config/Resources/Configuration/AiTasks.json'}])
        self.assertIn('RESOURCE_KEY_CANDIDATE_AMBIGUOUS',{x['code'] for x in plan['blockers']})

    def test_resources_prefix_and_candidate_matching_are_case_insensitive(self):
        asset='Assets/Product/Resources/configuration/AiTasks.json'
        put(self.root,asset,b'{"task":1}')
        native=native_readback(self.root,asset,'TextAsset',1)
        put(self.root,'Assets/Game/Services/Configuration/Loader.cs',
            'class Loader { object Load(string path) { Resources.Load<TextAsset>("CONFIGURATION/AITASKS"); return Resources.Load<TextAsset>("Configuration/"+path); } }')
        audit=inspect(self.root,native)
        self.assertEqual(next(x for x in audit['resourceLoads'] if x['key']=='CONFIGURATION/AITASKS')['candidateAssets'],[asset])
        plan=build_plan(audit,[
            {'source':asset,'target':'Assets/Game/Content/Config/Resources/CONFIGURATION/aitasks.json'}])
        self.assertEqual(plan['status'],'declaration_only')
        self.assertFalse(plan['mappings'][0]['resourceKeyMapping']['consumerPatchesRequired'])
        self.assertEqual(plan['mappings'][0]['resourceKeyMapping']['candidateAssets'],[asset])

    def test_case_only_duplicate_key_across_resources_folders_still_blocks(self):
        asset='Assets/One/Resources/Configuration/AiTasks.json'
        put(self.root,asset,b'{"task":1}')
        put(self.root,'Assets/Two/Resources/configuration/aitasks.asset',b'duplicate')
        native=native_readback(self.root,asset,'TextAsset',1)
        plan=build_plan(inspect(self.root,native),[
            {'source':asset,'target':'Assets/Game/Content/Config/Resources/Configuration/AiTasks.json'}])
        self.assertIn('RESOURCE_KEY_CANDIDATE_AMBIGUOUS',{x['code'] for x in plan['blockers']})

    def test_dynamic_literal_prefix_only_blocks_related_old_or_new_keys(self):
        put(self.root,'Assets/Game/Services/Configuration/Loader.cs',
            'class Loader { object Load(string path) { return Resources.Load<TextAsset>("Configuration/"+path); } }')
        cases=(
            ('Assets/Product/Resources/Configuration/BattleCore/monsters.json',
             'Assets/Game/Content/Prefabs/monsters.json',True),
            ('Assets/Product/Resources/model/monster.prefab',
             'Assets/Game/Content/Prefabs/monster.prefab',False),
            ('Assets/Product/Resources/ConfigurationX/monster.prefab',
             'Assets/Game/Content/Prefabs/monster.prefab',False),
        )
        for source,target,should_block in cases:
            put(self.root,source,b'asset')
            native=native_readback(self.root,source,'TextAsset' if source.endswith('.json') else 'UnityEngine.GameObject',1)
            plan=build_plan(inspect(self.root,native),[{'source':source,'target':target}])
            codes={x['code'] for x in plan['blockers']}
            self.assertEqual('DYNAMIC_RESOURCE_KEY_UNRESOLVED' in codes,should_block,source)
            self.assertEqual(plan['dynamicLoadCoverage'][0]['staticPrefix'],'Configuration/')

    def test_dynamic_literal_prefix_also_blocks_new_keys_entering_namespace(self):
        source='Assets/Product/Resources/model/monster.prefab'
        put(self.root,source,b'asset')
        native=native_readback(self.root,source,'UnityEngine.GameObject',1)
        put(self.root,'Assets/Game/Services/Configuration/Loader.cs',
            'class Loader { object Load(string path) { return Resources.Load<TextAsset>("Configuration/"+path); } }')
        plan=build_plan(inspect(self.root,native),[{'source':source,
            'target':'Assets/Game/Content/Config/Resources/Configuration/monster.prefab'}])
        self.assertIn('DYNAMIC_RESOURCE_KEY_UNRESOLVED',{x['code'] for x in plan['blockers']})

    def test_unknown_conditional_resources_expression_remains_strict(self):
        source='Assets/Product/Resources/model/monster.prefab'
        put(self.root,source,b'asset')
        native=native_readback(self.root,source,'UnityEngine.GameObject',1)
        put(self.root,'Assets/Game/Services/Configuration/Loader.cs',
            'class Loader { object Load(string path) { return Resources.Load<GameObject>(("Configuration/"+path)=="x" ? "model/foo" : "mat/bar"); } }')
        plan=build_plan(inspect(self.root,native),[{'source':source,
            'target':'Assets/Game/Content/Prefabs/monster.prefab'}])
        self.assertIn('DYNAMIC_RESOURCE_KEY_UNRESOLVED',{x['code'] for x in plan['blockers']})
        self.assertIsNone(plan['dynamicLoadCoverage'][0]['staticPrefix'])

    def test_transformed_dynamic_tail_is_not_claimed_as_proven_prefix(self):
        source='Assets/Product/Resources/model/monster.prefab'
        put(self.root,source,b'asset');native=native_readback(self.root,source,'UnityEngine.GameObject',1)
        put(self.root,'Assets/Game/Services/Configuration/Loader.cs',
            'class Loader { object Load(string path) { return Resources.Load<GameObject>("Configuration/"+path.Replace("../","")); } }')
        plan=build_plan(inspect(self.root,native),[{'source':source,'target':'Assets/Game/Content/Prefabs/monster.prefab'}])
        self.assertIsNone(plan['dynamicLoadCoverage'][0]['staticPrefix'])
        self.assertIn('DYNAMIC_RESOURCE_KEY_UNRESOLVED',{x['code'] for x in plan['blockers']})

    def test_noncanonical_dynamic_prefix_segments_are_not_proven(self):
        source='Assets/Product/Resources/model/monster.prefab'
        put(self.root,source,b'asset');native=native_readback(self.root,source,'UnityEngine.GameObject',1)
        expressions=('"Configuration\\\\"+path','"Configuration/../"+path','"Configuration//"+path')
        for index,expression in enumerate(expressions):
            consumer='Assets/Game/Services/Configuration/Loader'+str(index)+'.cs'
            put(self.root,consumer,'class Loader { object Load(string path) { return Resources.Load<GameObject>('+expression+'); } }')
        audit=inspect(self.root,native)
        self.assertEqual([x['staticPrefix'] for x in audit['dynamicLoads']],[None,None,None])
        plan=build_plan(audit,[{'source':source,'target':'Assets/Game/Content/Prefabs/monster.prefab'}])
        self.assertIn('DYNAMIC_RESOURCE_KEY_UNRESOLVED',{x['code'] for x in plan['blockers']})

    def test_source_identity_consumer_resolution_is_narrow_and_reported_as_review_only(self):
        source='Assets/Resources/level/map/sample_World.prefab'
        literal='assets/resources/level/map/sample_world.prefab'
        put(self.root,source,b'prefab')
        native=native_readback(self.root,source,'UnityEngine.GameObject',1)
        consumer='Assets/Game/Policy/Reader.cs'
        put(self.root,consumer,'if(d.sourceMapPrefab.containerPath!="'+literal+'") throw new InvalidDataException();')
        audit=inspect(self.root,native)
        issue=next(x for x in audit['issues'] if x['code']=='OLD_PATH_CONSUMER' and x['file']==consumer)
        resolution={'file':consumer,'fileSha256':audit['sourceHashes'][consumer],
                    'span':issue['span'],'literal':literal,'kind':'source-identity-comparison',
                    'reason':'Retained package identity is compared as evidence only.',
                    'evidence':'Policy reader compares containerPath to the immutable source identity.'}
        mapping=[{'source':source,'target':'Assets/Game/Content/Prefabs/World/sample_World.prefab'}]
        unresolved=build_plan(audit,mapping)
        self.assertIn('OLD_PATH_CONSUMER_UNHANDLED',{x['code'] for x in unresolved['blockers']})
        plan=build_plan(audit,mapping,consumer_resolutions={'schemaVersion':1,'resolutions':[resolution]})
        self.assertEqual(plan['status'],'declaration_only')
        self.assertEqual(plan['acceptedConsumerResolutions'][0]['state'],'caller-reviewed-not-native-proof')
        self.assertEqual(plan['consumerResolutionsSha256'],hashlib.sha256(
            json.dumps({'schemaVersion':1,'resolutions':[resolution]},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())

    def test_consumer_resolution_rejects_stale_or_duplicate_declarations(self):
        source='Assets/Resources/level/map/start.prefab';literal='Assets/Resources/level/map/start.prefab'
        put(self.root,source,b'prefab');native=native_readback(self.root,source,'UnityEngine.GameObject',1)
        consumer='Assets/Game/Policy/Reader.cs';put(self.root,consumer,'if(path!="'+literal+'") throw new Exception();')
        audit=inspect(self.root,native);issue=next(x for x in audit['issues'] if x['code']=='OLD_PATH_CONSUMER' and x['file']==consumer)
        resolution={'file':consumer,'fileSha256':audit['sourceHashes'][consumer],'span':issue['span'],
                    'literal':literal,'kind':'source-identity-comparison','reason':'identity check','evidence':'policy assertion'}
        mapping=[{'source':source,'target':'Assets/Game/Content/Prefabs/start.prefab'}]
        variants=[dict(resolution,fileSha256='0'*64),dict(resolution,literal='Assets/Other.prefab'),
                  dict(resolution,span=[issue['span'][0]+1,issue['span'][1]])]
        for invalid in variants:
            with self.subTest(invalid=invalid):
                with self.assertRaises(BeaverError):
                    build_plan(audit,mapping,consumer_resolutions={'schemaVersion':1,'resolutions':[invalid]})
        with self.assertRaises(BeaverError):
            build_plan(audit,mapping,consumer_resolutions={'schemaVersion':1,'resolutions':[resolution,resolution]})

    def test_deeply_nested_lookup_comparison_remains_unsupported(self):
        from beaver.references import _csharp_tokens
        from beaver.structure_audit import _source_comparison_context
        # The enclosing lookup remains relevant even beyond a short token window.
        source='var result=AssetDatabase.LoadAssetAtPath<GameObject>(Select('+','.join('arg'+str(i) for i in range(80))+', name=="Assets/Original.prefab" ? name : ""));'
        tokens=_csharp_tokens(source)
        index=next(i for i,t in enumerate(tokens) if t[0]=='string' and t[1]=='"Assets/Original.prefab"')
        self.assertFalse(_source_comparison_context(tokens,index))

    def test_consumer_resolution_cannot_silence_a_direct_resource_lookup(self):
        source='Assets/Resources/level/map/start.prefab';literal='Assets/Resources/level/map/start.prefab'
        put(self.root,source,b'prefab');native=native_readback(self.root,source,'UnityEngine.GameObject',1)
        consumer='Assets/Game/Policy/Lookup.cs'
        put(self.root,consumer,'var x=AssetDatabase.LoadAssetAtPath<GameObject>(name=="'+literal+'" ? name : "");')
        audit=inspect(self.root,native);issue=next(x for x in audit['issues'] if x['code']=='OLD_PATH_CONSUMER' and x['file']==consumer)
        resolution={'file':consumer,'fileSha256':audit['sourceHashes'][consumer],'span':issue['span'],
                    'literal':literal,'kind':'source-identity-comparison','reason':'claimed identity check','evidence':'not supported'}
        with self.assertRaises(BeaverError):
            build_plan(audit,[{'source':source,'target':'Assets/Game/Content/Prefabs/start.prefab'}],
                       consumer_resolutions={'schemaVersion':1,'resolutions':[resolution]})

    def test_consumer_resolution_supports_narrow_string_equals_comparison(self):
        source='Assets/Resources/level/map/start.prefab';literal='Assets/Resources/level/map/start.prefab'
        put(self.root,source,b'prefab');native=native_readback(self.root,source,'UnityEngine.GameObject',1)
        consumer='Assets/Game/Policy/Reader.cs'
        put(self.root,consumer,'if(!String.Equals(sourcePath,"'+literal+'",StringComparison.Ordinal)) throw new Exception();')
        audit=inspect(self.root,native);issue=next(x for x in audit['issues'] if x['code']=='OLD_PATH_CONSUMER' and x['file']==consumer)
        resolution={'file':consumer,'fileSha256':audit['sourceHashes'][consumer],'span':issue['span'],
                    'literal':literal,'kind':'source-identity-comparison','reason':'identity check','evidence':'ordinal comparison'}
        plan=build_plan(audit,[{'source':source,'target':'Assets/Game/Content/Prefabs/start.prefab'}],
                        consumer_resolutions={'schemaVersion':1,'resolutions':[resolution]})
        self.assertEqual(plan['status'],'declaration_only')

    def test_new_consumer_or_metadata_after_audit_invalidates_scope(self):
        asset='Assets/Legacy/Coin.png';put(self.root,asset,b'image');native=native_readback(self.root,asset)
        audit=inspect(self.root,native)
        put(self.root,'Assets/Game/Late.cs','class L { string p="Assets/Legacy/Coin.png"; }')
        plan=build_plan(audit,[{'source':asset,'target':'Assets/Game/Content/Images/Coin.png'}])
        self.assertIn('AUDIT_INPUT_SET_STALE',{x['code'] for x in plan['blockers']})
        (self.root/'Assets/Game/Late.cs').unlink()
        Path(str(self.root/asset)+'.meta').write_text('guid: '+'b'*32+'\n')
        plan=build_plan(audit,[{'source':asset,'target':'Assets/Game/Content/Images/Coin.png'}])
        self.assertIn('AUDIT_CONSUMER_STALE',{x['code'] for x in plan['blockers']})

    def test_proposed_targets_and_parent_case_collisions_block(self):
        a='Assets/Legacy/A.png';b='Assets/Legacy/B.png';put(self.root,a,b'a');put(self.root,b,b'b')
        native=native_readback(self.root,a);other=native_readback(self.root,b,guid='b'*32)
        native['assets']+=other['assets'];native['inputState'].update(other['inputState'])
        audit=inspect(self.root,native)
        for target in ['Assets/Game/Content/Images/a.png','Assets/Game/Content/images/B.png']:
            plan=build_plan(audit,[{'source':a,'target':'Assets/Game/Content/Images/A.png'},{'source':b,'target':target}])
            self.assertIn('TARGET_CASE_COLLISION',{x['code'] for x in plan['blockers']})
            self.assertIsNone(plan['batchSpec'])

    def test_symlink_is_reported_as_scan_blocker(self):
        target = put(self.root, "Outside/Hidden.asset", b"hidden")
        (self.root / "Assets" / "Linked.asset").symlink_to(target)
        report = inspect(self.root)
        self.assertTrue(any(row["code"] == "SYMLINK_SCAN_BLOCKED" and row["path"] == "Assets/Linked.asset"
                            for row in report["issues"]))
        self.assertEqual(report["dependencies"], {})

    def test_large_asset_is_indexed_but_not_hashed_or_plannable(self):
        source = self.root / "Assets/Game/Large.bin"
        source.parent.mkdir(parents=True, exist_ok=True)
        with source.open("wb") as stream:
            stream.truncate(64 * 1024 * 1024 + 1)
        put(self.root, "Assets/Game/Large.bin.meta", "guid: cccccccccccccccccccccccccccccccc\n")
        report = inspect(self.root)
        self.assertTrue(any(row["code"] == "SOURCE_HASH_BUDGET_EXCEEDED" for row in report["issues"]))
        plan = build_plan(report, [{"source": "Assets/Game/Large.bin", "target": "Assets/Game/Large2.bin"}])
        self.assertEqual(plan["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
