import shutil
import json
import tempfile
import unittest
import uuid
from pathlib import Path

from grea.development.adoption import build_plan, preview, prepare, project_files
from grea.development.adoption_native import job_spec, restore_code
from grea.development.errors import BeaverError
from grea.development.io import encoded, load, read, sha, write_json
from grea.development.adoption_sdk import load_spec
from grea.development.managed_metadata import inspect_managed
from grea.development.output_limits import digest_file
from .test_adoption import candidate
from .test_managed_metadata import managed_dll
from .helpers import finish
from unittest.mock import patch
from grea.development import adoption_sdk


EDITOR_GUID = "a" * 32
PLAYER_GUID = "b" * 32
OLD_DLL = "Assets/Plugins/Spine38/spine-unity.dll"
PLAYER_DLL = "Assets/Plugins/Spine38/Player/spine-unity.dll"
REF_ASSET = "Assets/Game/Legacy.asset"
INACTIVE_CSHARP = "Assets/Game/Adopted/MonkeyA10/Plugins/Spine38/EditorRuntime/spine-csharp.dll"
INACTIVE_UNITY = "Assets/Game/Adopted/MonkeyA10/Plugins/Spine38/EditorRuntime/spine-unity.dll"


def importer_meta(guid, domain):
    editor = domain == "editor"
    player = domain == "player"
    return (f"fileFormatVersion: 2\nguid: {guid}\nPluginImporter:\n  externalObjects: {{}}\n  platformData:\n"
            f"  - first:\n      Any:\n    second:\n      enabled: {int(player)}\n      settings:\n        Exclude Editor: {int(player)}\n"
            f"  - first:\n      Editor: Editor\n    second:\n      enabled: {int(editor)}\n      settings:\n        CPU: AnyCPU\n").encode()


def disabled_importer_meta(guid):
    return (f"fileFormatVersion: 2\nguid: {guid}\nPluginImporter:\n  externalObjects: {{}}\n  serializedVersion: 3\n"
            "  defineConstraints: []\n  platformData:\n    Any:\n      enabled: 0\n      settings: {}\n"
            "    Editor:\n      enabled: 0\n      settings:\n        CPU: AnyCPU\n        DefaultValueInitialized: true\n"
            "    WindowsStoreApps:\n      enabled: 0\n      settings:\n        CPU: AnyCPU\n").encode()


def put_dll(root, path, guid, domain, name="Spine.Unity", type_name="Spine.Unity.SkeletonGraphic"):
    dll = root / path; dll.parent.mkdir(parents=True, exist_ok=True)
    mvid=str(uuid.uuid5(uuid.NAMESPACE_URL,path+"\0"+guid+"\0"+domain))
    dll.write_bytes(managed_dll(name=name, namespace="Spine.Unity", type_name=type_name.split(".")[-1],mvid=mvid))
    Path(str(dll) + ".meta").write_bytes(importer_meta(guid, domain))
    return dll


def put_inactive_dll(root, path, guid, name="Spine.Unity", type_name="Spine.Unity.SkeletonGraphic"):
    dll=root/path;dll.parent.mkdir(parents=True,exist_ok=True)
    mvid=str(uuid.uuid5(uuid.NAMESPACE_URL,path+"\0"+guid+"\0disabled"))
    dll.write_bytes(managed_dll(name=name,namespace="Spine.Unity",type_name=type_name.split(".")[-1],mvid=mvid))
    Path(str(dll)+".meta").write_bytes(disabled_importer_meta(guid))
    return dll


def type_inventory():
    return {"metadataTypes": ["Spine.Unity.SkeletonGraphic"]}


class AdoptionSdkTests(unittest.TestCase):
    def fixture(self, root):
        baseline = candidate(root / "baseline")
        incoming = root / "incoming"; shutil.copytree(baseline, incoming)
        target = root / "target"; shutil.copytree(baseline, target)
        old = put_dll(target, OLD_DLL, EDITOR_GUID, "player")
        ref = target / REF_ASSET; ref.parent.mkdir(parents=True, exist_ok=True); ref.write_text("native object fixture\n")
        editor = put_dll(incoming, OLD_DLL, EDITOR_GUID, "editor")
        player = put_dll(incoming, PLAYER_DLL, PLAYER_GUID, "player")
        license_path = incoming / "Assets/Plugins/Spine38/LICENSE"; license_path.parent.mkdir(parents=True, exist_ok=True); license_path.write_text("MIT License\n")
        incoming_object=incoming/"Assets/Game/IncomingObject.asset";incoming_object.parent.mkdir(parents=True,exist_ok=True);incoming_object.write_text("serialized object fixture\n")
        finish(incoming, dict(schemaVersion=1, targetProfile="unity-6000.6.2f1-ugui", namespace="game", projectLayout="monkey-project/2.0.0", scopeMode="whole-input", diagnostics=[]))
        finish(target, dict(schemaVersion=1, targetProfile="unity-6000.6.2f1-ugui", namespace="game", projectLayout="monkey-project/2.0.0", scopeMode="whole-input", diagnostics=[]))
        return baseline, incoming, target, old, editor, player, ref

    def spec(self, root, incoming, target, old, editor, player, ref, *, bad_guid=False, mapped_script=False, retained_inactive_paths=None):
        editor_meta = Path(str(editor) + ".meta"); player_meta = Path(str(player) + ".meta")
        old_info = type_inventory(); new_info = type_inventory()
        before = {"guid": EDITOR_GUID, "sha256": digest_file(old), "metaSha256": digest_file(Path(str(old) + ".meta")),
                  "version": [1, 0, 0, 0], "culture": "neutral", "publicKeySha256": None,
                  "roles": ["player"], **old_info}
        def after(path, guid):
            return {"guid": guid, "sha256": digest_file(path), "metaSha256": digest_file(Path(str(path) + ".meta")),
                    "version": [1, 0, 0, 0], "culture": "neutral", "publicKeySha256": None, **new_info}
        spec = {
            "schemaVersion": 1, "contract": "beaver-sdk-migration/1", "unityVersion": "6000.6.2f1",
            "candidateManifestSha256": digest_file(incoming / "manifest.json"),
            "targetAssetsSha256": sha(encoded(project_files(target, "unity-6000.6.2f1-ugui"))),
            "referenceCoverage": "all-sdk-references-in-adopted-assets",
            "licenses": [{"id": "spine", "root": "candidate", "path": "Assets/Plugins/Spine38/LICENSE", "sha256": digest_file(incoming / "Assets/Plugins/Spine38/LICENSE")}],
            "assemblies": [{"role": "spine-runtime", "assemblyName": "Spine.Unity", "licenseId": "spine", "monoScriptPolicy": "capture-before-preserve-and-pair-localids", "variants": [
                {"domain": "editor", "action": "replace-preserve-guid", "path": OLD_DLL,
                 "after": after(editor, PLAYER_GUID if bad_guid else EDITOR_GUID), "before": before},
                {"domain": "player", "action": "add", "path": PLAYER_DLL,
                 "after": after(player, PLAYER_GUID), "before": None},
            ]}],
            "references": [{"root": "target", "assetPath": REF_ASSET, "assetSha256": digest_file(ref), "objectLocalId": 43001,
                 "propertyPath": "m_Script", "action": "map" if mapped_script else "preserve",
                             "source": {"guid": EDITOR_GUID, "localId": 11500000, "type": "Spine.Unity.SkeletonGraphic"},
                             "canonical": {"guid": PLAYER_GUID, "localId": 11500000, "type": "Spine.Unity.SkeletonGraphic"} if mapped_script else
                                         {"guid": EDITOR_GUID, "localId": 11500000, "type": "Spine.Unity.SkeletonGraphic"}}],
        }
        if retained_inactive_paths is not None:
            rows=[]
            for p in retained_inactive_paths:
                dll=target/p;meta=Path(str(dll)+".meta");info=inspect_managed(dll.read_bytes())
                guid=meta.read_text().split("guid: ",1)[1].splitlines()[0]
                rows.append({"path":p,"guid":guid,"sha256":digest_file(dll),"metaSha256":digest_file(meta),
                             "assemblyName":info["name"],"moduleVersionId":info["moduleVersionId"],"roles":[]})
            spec["retainedInactiveAssemblies"]={"policy":"preserve-exact-disabled-target-assemblies","assemblies":rows}
        path = root / "sdk-migration.json"; write_json(path, spec)
        return path, digest_file(path)

    def test_explicit_canonical_pair_plan_replaces_editor_preserves_guid_and_adds_player(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();base,incoming,target,old,editor,player,ref=self.fixture(root)
            spec,expected=self.spec(root,incoming,target,old,editor,player,ref)
            plan=build_plan(incoming,target,base,sdk_migration=spec,expected_sdk_migration_sha256=expected)
            self.assertEqual(plan["managedAssemblyMigration"]["assemblies"][0]["role"],"spine-runtime")
            self.assertEqual(plan["managedAssemblyCompatibility"]["status"],"preflight-verified")
            self.assertFalse(plan["conflicts"])
            normalized=plan["managedAssemblyMigration"]["assemblies"][0]["variants"]
            normalized_editor=next(v for v in normalized if v["domain"]=="editor")
            normalized_player=next(v for v in normalized if v["domain"]=="player")
            self.assertEqual(normalized_editor["after"]["moduleVersionId"],inspect_managed(editor.read_bytes())["moduleVersionId"])
            self.assertEqual(normalized_editor["before"]["moduleVersionId"],inspect_managed(old.read_bytes())["moduleVersionId"])
            self.assertNotEqual(normalized_editor["after"]["moduleVersionId"],normalized_player["after"]["moduleVersionId"])
            self.assertEqual({op["action"] for op in plan["operations"] if op["target"] in (OLD_DLL,PLAYER_DLL)}, {"add","update"})
            replacement=next(op for op in plan["operations"] if op["target"]==OLD_DLL)
            self.assertEqual(replacement["guid"],EDITOR_GUID)
            self.assertEqual(replacement["before"]["file"]["sha256"],digest_file(old))
            self.assertEqual(replacement["after"]["meta"]["sha256"],digest_file(Path(str(editor)+".meta")))

    def test_migration_stages_exact_native_before_after_images_and_compilation_boundary(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();base,incoming,target,old,editor,player,ref=self.fixture(root)
            spec,expected=self.spec(root,incoming,target,old,editor,player,ref)
            result=preview(incoming,target,root/"plan",base,sdk_migration=spec,expected_sdk_migration_sha256=expected)
            self.assertEqual(result["status"],"planned")
            stage,plan,journal=prepare(root/"plan/adoption-plan.json",root/"transaction")
            sdk_job=job_spec(stage,plan,journal,"code",60)
            self.assertTrue(sdk_job["sdkMigrationEnabled"])
            self.assertEqual(sdk_job["sdkMigration"]["sha256"],expected)
            added_variant=next(v for pair in sdk_job["sdkMigration"]["assemblies"] for v in pair["variants"] if v["action"]=="add")
            self.assertIsNone(added_variant["before"])
            editor_op=next(i for i,op in enumerate(plan["operations"]) if op["target"]==OLD_DLL)
            self.assertEqual((stage/f"before/{editor_op}/file").read_bytes(),old.read_bytes())
            self.assertEqual((stage/f"after/{editor_op}/file").read_bytes(),editor.read_bytes())
            self.assertEqual((stage/f"after/{editor_op}/meta").read_bytes(),Path(str(editor)+".meta").read_bytes())
            self.assertEqual((target/OLD_DLL).read_bytes(),old.read_bytes())

    def test_sdk_compiler_before_image_restores_dll_and_importer_meta_and_rejects_later_edits(self):
        for later_edit in (False,True):
            with self.subTest(later_edit=later_edit), tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve();base,incoming,target,old,editor,player,ref=self.fixture(root)
                spec,expected=self.spec(root,incoming,target,old,editor,player,ref)
                preview(incoming,target,root/"plan",base,sdk_migration=spec,expected_sdk_migration_sha256=expected)
                stage,plan,journal=prepare(root/"plan/adoption-plan.json",root/"transaction")
                index=next(i for i,op in enumerate(plan["operations"]) if op["target"]==OLD_DLL)
                write_json(stage/"native-code.json",{"planSha256":journal["planSha256"],"written":[index]})
                target_dll=target/OLD_DLL;target_meta=Path(str(target_dll)+".meta")
                target_dll.write_bytes(editor.read_bytes());target_meta.write_bytes(Path(str(editor)+".meta").read_bytes())
                if later_edit:target_dll.write_bytes(b"unowned later edit")
                if later_edit:
                    with self.assertRaises(BeaverError):restore_code(stage,plan,journal)
                    self.assertEqual(target_dll.read_bytes(),b"unowned later edit")
                else:
                    restore_code(stage,plan,journal)
                    self.assertEqual(target_dll.read_bytes(),old.read_bytes())
                    self.assertEqual(target_meta.read_bytes(),Path(str(old)+".meta").read_bytes())

    def test_stale_spec_bad_canonical_guid_and_unmapped_script_changes_refuse(self):
        for fault in ("guid","script","stale","producer-empty-monoscripts"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                root=Path(temp).resolve();base,incoming,target,old,editor,player,ref=self.fixture(root)
                spec,expected=self.spec(root,incoming,target,old,editor,player,ref,bad_guid=fault=="guid",mapped_script=fault=="script")
                if fault=="stale":
                    changed=target/REF_ASSET;changed.write_text("later edit\n")
                if fault=="producer-empty-monoscripts":
                    doc=load(read(spec));doc["assemblies"][0]["variants"][0]["after"]["monoScripts"]=[];write_json(spec,doc);expected=digest_file(spec)
                with self.assertRaises(BeaverError):
                    build_plan(incoming,target,base,sdk_migration=spec,expected_sdk_migration_sha256=expected)

    def test_no_migration_spec_keeps_existing_duplicate_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();base,incoming,target,old,editor,player,ref=self.fixture(root)
            plan=build_plan(incoming,target,base)
            self.assertTrue(any("managed-sdk" in row["reason"] for row in plan["conflicts"]))
            job=job_spec(root,plan,{"planSha256":"c"*64,"codeRestored":False},"apply",60)
            self.assertFalse(job["sdkMigrationEnabled"])
            self.assertIsNone(job["sdkMigration"])

    def test_guid_only_legacy_meta_requires_explicit_native_role_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();base,incoming,target,old,editor,player,ref=self.fixture(root)
            Path(str(old)+".meta").write_text("fileFormatVersion: 2\nguid: "+EDITOR_GUID+"\n")
            finish(target,dict(schemaVersion=1,targetProfile="unity-6000.6.2f1-ugui",namespace="game",projectLayout="monkey-project/2.0.0",scopeMode="whole-input",diagnostics=[]))
            spec,expected=self.spec(root,incoming,target,old,editor,player,ref)
            doc=load(read(spec));before=doc["assemblies"][0]["variants"][0]["before"];before["roles"]=["native-required"]
            doc["targetAssetsSha256"]=sha(encoded(project_files(target,"unity-6000.6.2f1-ugui")))
            write_json(spec,doc);expected=digest_file(spec)
            plan=build_plan(incoming,target,base,sdk_migration=spec,expected_sdk_migration_sha256=expected)
            self.assertFalse(plan["conflicts"])
            doc=load(read(spec));doc["assemblies"][0]["variants"][0]["before"]["roles"]=["player"];write_json(spec,doc)
            with self.assertRaises(BeaverError):
                build_plan(incoming,target,base,sdk_migration=spec,expected_sdk_migration_sha256=digest_file(spec))

    def test_explicit_non_script_reference_map_is_part_of_same_frozen_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();base,incoming,target,old,editor,player,ref=self.fixture(root)
            spec,expected=self.spec(root,incoming,target,old,editor,player,ref)
            doc=load(read(spec));asset=incoming/"Assets/Game/IncomingObject.asset"
            doc["references"].append({"root":"candidate","assetPath":"Assets/Game/IncomingObject.asset","assetSha256":digest_file(asset),"objectLocalId":44002,
                "propertyPath":"skeletonDataAsset","action":"map","source":{"guid":EDITOR_GUID,"localId":500,"type":"Spine.Unity.SkeletonDataAsset"},
                "canonical":{"guid":PLAYER_GUID,"localId":501,"type":"Spine.Unity.SkeletonDataAsset"}})
            write_json(spec,doc);expected=digest_file(spec)
            plan=build_plan(incoming,target,base,sdk_migration=spec,expected_sdk_migration_sha256=expected)
            self.assertFalse(plan["conflicts"])
            self.assertTrue(any(op["target"]=="Assets/Game/IncomingObject.asset" for op in plan["operations"]))

    def test_inactive_player_policy_requires_exact_editor_before_bytes_and_mvid(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();base,incoming,target,old,editor,player,ref=self.fixture(root)
            spec,expected=self.spec(root,incoming,target,old,editor,player,ref)
            doc=load(read(spec));doc["assemblies"][0]["monoScriptPolicy"]="capture-before-preserve-and-attest-inactive-player"
            write_json(spec,doc)
            with self.assertRaises(BeaverError):
                build_plan(incoming,target,base,sdk_migration=spec,expected_sdk_migration_sha256=digest_file(spec))

            player.write_bytes(old.read_bytes())
            finish(incoming,dict(schemaVersion=1,targetProfile="unity-6000.6.2f1-ugui",namespace="game",projectLayout="monkey-project/2.0.0",scopeMode="whole-input",diagnostics=[]))
            spec,expected=self.spec(root,incoming,target,old,editor,player,ref)
            doc=load(read(spec));doc["assemblies"][0]["monoScriptPolicy"]="capture-before-preserve-and-attest-inactive-player"
            write_json(spec,doc)
            plan=build_plan(incoming,target,base,sdk_migration=spec,expected_sdk_migration_sha256=digest_file(spec))
            pair=plan["managedAssemblyMigration"]["assemblies"][0]
            editor_before=next(v["before"] for v in pair["variants"] if v["domain"]=="editor")
            player_after=next(v["after"] for v in pair["variants"] if v["domain"]=="player")
            self.assertEqual(player_after["sha256"],editor_before["sha256"])
            self.assertEqual(player_after["moduleVersionId"],editor_before["moduleVersionId"])

    def test_signed_64_bit_unity_local_ids_are_preserved_without_rounding(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();base,incoming,target,old,editor,player,ref=self.fixture(root)
            spec,expected=self.spec(root,incoming,target,old,editor,player,ref)
            doc=load(read(spec));row=doc["references"][0]
            row["objectLocalId"]=-(1<<63)
            row["source"]["localId"]=-(1<<53)-1;row["canonical"]["localId"]=-(1<<53)-1
            write_json(spec,doc)
            plan=build_plan(incoming,target,base,sdk_migration=spec,expected_sdk_migration_sha256=digest_file(spec))
            ref=plan["managedAssemblyMigration"]["references"][0]
            self.assertEqual(ref["objectLocalId"],-(1<<63))
            self.assertEqual(ref["source"]["localId"],-(1<<53)-1)
            for invalid in (0,-(1<<63)-1,1<<63):
                bad=load(read(spec));bad["references"][0]["objectLocalId"]=invalid;write_json(spec,bad)
                with self.subTest(invalid=invalid),self.assertRaises(BeaverError):
                    build_plan(incoming,target,base,sdk_migration=spec,expected_sdk_migration_sha256=digest_file(spec))
            for invalid in (0,-(1<<63)-1,1<<63):
                bad=load(read(spec));bad["references"][0]["objectLocalId"]=43001
                bad["references"][0]["source"]["localId"]=invalid;bad["references"][0]["canonical"]["localId"]=invalid
                write_json(spec,bad)
                with self.subTest(local_id=invalid),self.assertRaises(BeaverError):
                    build_plan(incoming,target,base,sdk_migration=spec,expected_sdk_migration_sha256=digest_file(spec))

    def test_explicit_disabled_target_duplicates_are_only_narrow_collision_exemptions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();base,incoming,target,old,editor,player,ref=self.fixture(root)
            csharp_guid=uuid.uuid5(uuid.NAMESPACE_URL,INACTIVE_CSHARP).hex
            unity_guid=uuid.uuid5(uuid.NAMESPACE_URL,INACTIVE_UNITY).hex
            put_inactive_dll(target,INACTIVE_CSHARP,csharp_guid,name="Spine.Unity",type_name="Spine.Animation").write_bytes(editor.read_bytes())
            put_inactive_dll(target,INACTIVE_UNITY,unity_guid,name="Spine.Unity",type_name="SkeletonGraphic").write_bytes(editor.read_bytes())
            finish(target,dict(schemaVersion=1,targetProfile="unity-6000.6.2f1-ugui",namespace="game",projectLayout="monkey-project/2.0.0",scopeMode="whole-input",diagnostics=[]))

            unpinned,sha_unpinned=self.spec(root,incoming,target,old,editor,player,ref)
            plan=build_plan(incoming,target,base,sdk_migration=unpinned,expected_sdk_migration_sha256=sha_unpinned)
            self.assertTrue(any(c["reason"]=="managed-sdk-existing-identity-needs-native-migration" for c in plan["conflicts"]))

            one,sha_one=self.spec(root,incoming,target,old,editor,player,ref,retained_inactive_paths=[INACTIVE_CSHARP])
            plan_one=build_plan(incoming,target,base,sdk_migration=one,expected_sdk_migration_sha256=sha_one)
            self.assertTrue(any(c["reason"]=="managed-sdk-existing-identity-needs-native-migration" and INACTIVE_UNITY in c["current"] for c in plan_one["conflicts"]))

            both,sha_both=self.spec(root,incoming,target,old,editor,player,ref,retained_inactive_paths=[INACTIVE_CSHARP,INACTIVE_UNITY])
            plan_both=build_plan(incoming,target,base,sdk_migration=both,expected_sdk_migration_sha256=sha_both)
            self.assertFalse(plan_both["conflicts"])
            pinned={r["path"]:r for r in plan_both["managedAssemblyCompatibility"]["assemblies"] if r.get("explicitInactivePin")}
            self.assertEqual(set(pinned),{INACTIVE_CSHARP,INACTIVE_UNITY})
            self.assertTrue(all(r["roles"]==[] and r["explicitInactivePin"] for r in pinned.values()))
            normalized=plan_both["managedAssemblyMigration"]["retainedInactiveAssemblies"]
            self.assertEqual(normalized["policy"],"preserve-exact-disabled-target-assemblies")
            job=job_spec(root,plan_both,{"planSha256":"d"*64,"codeRestored":False},"code",60)
            self.assertEqual(len(job["sdkMigration"]["retainedInactiveAssemblies"]["assemblies"]),2)

    def test_inactive_duplicate_pins_reject_enabled_meta_and_new_references(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();base,incoming,target,old,editor,player,ref=self.fixture(root)
            inactive_guid=uuid.uuid5(uuid.NAMESPACE_URL,INACTIVE_CSHARP).hex
            put_inactive_dll(target,INACTIVE_CSHARP,inactive_guid,name="Spine.Unity",type_name="Spine.Animation").write_bytes(editor.read_bytes())
            finish(target,dict(schemaVersion=1,targetProfile="unity-6000.6.2f1-ugui",namespace="game",projectLayout="monkey-project/2.0.0",scopeMode="whole-input",diagnostics=[]))
            spec,expected=self.spec(root,incoming,target,old,editor,player,ref,retained_inactive_paths=[INACTIVE_CSHARP])
            dll=target/INACTIVE_CSHARP;meta=Path(str(dll)+".meta")
            meta.write_bytes(importer_meta(inactive_guid,"editor"))
            finish(target,dict(schemaVersion=1,targetProfile="unity-6000.6.2f1-ugui",namespace="game",projectLayout="monkey-project/2.0.0",scopeMode="whole-input",diagnostics=[]))
            spec,expected=self.spec(root,incoming,target,old,editor,player,ref,retained_inactive_paths=[INACTIVE_CSHARP])
            with self.assertRaises(BeaverError):
                build_plan(incoming,target,base,sdk_migration=spec,expected_sdk_migration_sha256=expected)

            meta.write_bytes(disabled_importer_meta(inactive_guid))
            finish(target,dict(schemaVersion=1,targetProfile="unity-6000.6.2f1-ugui",namespace="game",projectLayout="monkey-project/2.0.0",scopeMode="whole-input",diagnostics=[]))
            spec,expected=self.spec(root,incoming,target,old,editor,player,ref,retained_inactive_paths=[INACTIVE_CSHARP])
            doc=load(read(spec));asset=incoming/"Assets/Game/IncomingObject.asset"
            doc["references"].append({"root":"candidate","assetPath":"Assets/Game/IncomingObject.asset","assetSha256":digest_file(asset),"objectLocalId":777,
                "propertyPath":"skeletonDataAsset","action":"map","source":{"guid":EDITOR_GUID,"localId":500,"type":"Spine.Unity.SkeletonDataAsset"},
                "canonical":{"guid":inactive_guid,"localId":501,"type":"Spine.Unity.SkeletonDataAsset"}})
            write_json(spec,doc)
            with self.assertRaises(BeaverError):
                build_plan(incoming,target,base,sdk_migration=spec,expected_sdk_migration_sha256=digest_file(spec))

    def test_sdk_spec_budget_accepts_complete_4055_reference_shape_and_rejects_over_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            row={"root":"candidate","assetPath":"Assets/Game/Content.asset","assetSha256":"a"*64,"objectLocalId":123,
                 "propertyPath":"skeletonDataAsset","action":"preserve",
                 "source":{"guid":EDITOR_GUID,"localId":456,"type":"Spine.Unity.SkeletonDataAsset"},
                 "canonical":{"guid":EDITOR_GUID,"localId":456,"type":"Spine.Unity.SkeletonDataAsset"}}
            doc={"schemaVersion":1,"contract":"beaver-sdk-migration/1","unityVersion":"6000.6.2f1",
                 "candidateManifestSha256":"a"*64,"targetAssetsSha256":"b"*64,
                 "referenceCoverage":"all-sdk-references-in-adopted-assets","licenses":[],"assemblies":[],
                 "references":[dict(row,propertyPath=f"skeletonDataAsset[{i}]") for i in range(4055)]}
            path=root/"large-spec.json";write_json(path,doc);raw=path.read_bytes()
            self.assertLess(len(raw),4*1024*1024)
            with self.assertRaises(BeaverError) as low_budget:
                load(raw,max_nodes=100_000)
            self.assertEqual(low_budget.exception.code,"BUDGET_EXCEEDED")
            loaded,parsed,_=load_spec(path,digest_file(path))
            self.assertEqual(len(parsed["references"]),4055)

            over=dict(doc,references=[[0]*20 for _ in range(25_000)])
            path.write_text(json.dumps(over,separators=(",",":")));self.assertLess(path.stat().st_size,4*1024*1024)
            with self.assertRaises(BeaverError) as high_budget:
                load_spec(path,digest_file(path))
            self.assertEqual(high_budget.exception.code,"BUDGET_EXCEEDED")

    def test_repeated_reference_rows_read_and_recheck_each_unique_asset_once(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();base,incoming,target,old,editor,player,ref=self.fixture(root)
            spec,expected=self.spec(root,incoming,target,old,editor,player,ref)
            doc=load(read(spec));template=doc["references"][0]
            doc["references"]=[dict(template,objectLocalId=50000+i) for i in range(4055)]
            write_json(spec,doc);expected=digest_file(spec)
            actual=adoption_sdk._read_target;calls=[]
            def counted(root_path,files,path,digest,where):
                if path==REF_ASSET:calls.append(path)
                return actual(root_path,files,path,digest,where)
            with patch.object(adoption_sdk,"_read_target",counted):
                plan=build_plan(incoming,target,base,sdk_migration=spec,expected_sdk_migration_sha256=expected)
            self.assertFalse(plan["conflicts"])
            self.assertEqual(len(plan["managedAssemblyMigration"]["references"]),4055)
            self.assertEqual(calls.count(REF_ASSET),2)


if __name__=="__main__": unittest.main()
