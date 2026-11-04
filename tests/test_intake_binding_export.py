"""Bounded native-binding export fixtures; no Editor is launched."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from beaver.candidate_snapshot import snapshot as read_candidate, verify as verify_candidate
from beaver.errors import BeaverError
from beaver.intake import build_plan as intake_build_plan
from beaver.intake_binding_export import export_prepared
from beaver.intake_bindings import build_plan
from beaver.io import load, read, sha, write_json
from beaver.output_limits import digest_file
from beaver.unity import source_files
from helpers import finish
from test_intake import _project, _write_asset


SOURCE_GUID = "1" * 32
TARGET_GUID = "2" * 32
PREFAB_GUID = "3" * 32


class BindingExportTests(unittest.TestCase):
    def fixture(self, root):
        source = _project(root / "source")
        target = _project(root / "target")
        code = b"public class Widget : UnityEngine.MonoBehaviour { public int count; }"
        _write_asset(source, "Assets/Widget.cs", code, SOURCE_GUID)
        _write_asset(target, "Assets/Runtime/Widget.cs", code, TARGET_GUID)
        prefab_bytes = (b"--- !u!114 &11400000\nMonoBehaviour:\n  m_Script: "
                        b"{fileID: 11500000, guid: " + SOURCE_GUID.encode() + b", type: 3}\n")
        _write_asset(source, "Assets/Panel.prefab", prefab_bytes, PREFAB_GUID)
        finish(source, dict(schemaVersion=1, targetProfile="unity-6000.6.2f1-ugui",
                            namespace="source-partial", native="partial", diagnostics=["source remains partial"]))
        binding = dict(source="Assets/Widget.cs", sourceGuid=SOURCE_GUID, sourceType="Widget",
                       sourceAssembly="Assembly-CSharp", sourceLocalId=11500000,
                       target="Assets/Runtime/Widget.cs", targetGuid=TARGET_GUID, targetType="Widget",
                       targetAssembly="Assembly-CSharp", targetLocalId=11500000)
        for side in ("source", "target"):
            project = source if side == "source" else target
            for suffix, field in (("", "Sha256"), (".meta", "MetaSha256")):
                binding[side + field] = sha((project / (binding[side] + suffix)).read_bytes())
        spec = root / "bindings.json"
        write_json(spec, dict(schemaVersion=1, operation="prepare-script-bindings",
                              bindings=[binding], prefabs=["Assets/Panel.prefab"], bridgeReferences=[]))
        plan = build_plan(source, target, spec)
        stage = root / "prepared"
        project = stage / "UnityProject"
        project.mkdir(parents=True)
        for path in plan["sourceFiles"]:
            destination = project / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / path, destination)
        bridge = project / "Assets/BeaverIntakeBindings"
        bridge.mkdir(parents=True)
        (project / "Assets/BeaverIntakeBindings.meta").write_text(
            "fileFormatVersion: 2\nguid: " + "4" * 32 + "\n", encoding="utf-8")
        shutil.copyfile(target / binding["target"], bridge / "Widget.cs")
        shutil.copyfile(target / (binding["target"] + ".meta"), bridge / "Widget.cs.meta")
        write_json(bridge / "Beaver.IntakeBindings.asmdef",
                   dict(name="Beaver.IntakeBindings", references=[], autoReferenced=False))
        (bridge / "Beaver.IntakeBindings.asmdef.meta").write_text(
            "fileFormatVersion: 2\nguid: " + "5" * 32 + "\n", encoding="utf-8")
        prepared_prefab = project / "Assets/Panel.prefab"
        prepared_prefab.write_bytes(prepared_prefab.read_bytes().replace(SOURCE_GUID.encode(), TARGET_GUID.encode()))
        prepared_files = source_files(project)
        plan_sha = "a" * 64
        write_json(stage / "preparation-plan.json", plan)
        write_json(stage / "binding-job.json", dict(projectRoot=str(project), bridgeRoot="Assets/BeaverIntakeBindings",
                                                     bridgeAssembly="Beaver.IntakeBindings", planSha256=plan_sha, mode="verify"))
        script_ref = dict(guid=TARGET_GUID, localId=11500000, type="UnityEditor.MonoScript", assembly="UnityEditor.CoreModule",
                          name="Widget", assetPath="Assets/Runtime/Widget.cs",
                          scriptType="Widget", scriptAssembly="Assembly-CSharp")
        snapshot = dict(planSha256=plan_sha, prefabs=[dict(path="Assets/Panel.prefab", guid=PREFAB_GUID, owners=[
            dict(guid=PREFAB_GUID,localId=-120000,type="UnityEngine.UI.Image, UnityEngine.UI, Version=1.0.0.0",name="Icon",
                 properties=[dict(path="m_EditorClassIdentifier",type="String:string",value=""),dict(path="m_Color.r",type="Float:float",value="1")]),
            dict(guid=PREFAB_GUID, localId=11400000, type="binding:Assembly-CSharp/Widget", name="Panel",
                 properties=[
                     dict(path="m_Script", type="ObjectReference:PPtr<$MonoScript>",
                          value=f"{TARGET_GUID}#11500000|UnityEditor.MonoScript@UnityEditor.CoreModule|script:Widget@Assembly-CSharp",
                          reference=script_ref),
                     dict(path="m_Count", type="Integer:int", value="7"),
                     dict(path="m_EditorClassIdentifier", type="String", value="binding:Widget")
                 ])
        ])])
        snapshot_bytes = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        for mode in ("apply", "verify"):
            leaf = mode + "-snapshot.json"
            (stage / leaf).write_bytes(snapshot_bytes)
            write_json(stage / (mode + "-report.json"), dict(status="verified", mode=mode, planSha256=plan_sha,
                                                               snapshotFile=leaf, snapshotSha256=sha(snapshot_bytes),
                                                               snapshotBytes=len(snapshot_bytes)))
        return dict(root=root, source=source, target=target, spec=spec, plan=plan, stage=stage,
                    project=project, files=prepared_files, snapshot=snapshot)

    def export(self, fixture, **overrides):
        values = dict(stage=fixture["stage"], project=fixture["project"], plan=fixture["plan"],
                      prepared_files=fixture["files"], snapshot=fixture["snapshot"])
        values.update(overrides)
        return export_prepared(**values)

    def test_export_is_owned_and_existing_intake_build_plan_consumes_fragments(self):
        with tempfile.TemporaryDirectory() as temp:
            f = self.fixture(Path(temp).resolve())
            result = self.export(f)
            candidate = Path(result["candidate"])
            root, manifest, files, manifest_sha = read_candidate(candidate)
            verify_candidate(root, files)
            self.assertEqual(result["candidateManifestSha256"], manifest_sha)
            self.assertEqual(manifest["targetProfile"], "unity-6000.6.2f1-ugui")
            self.assertEqual(manifest["projectLayout"], "beaver-intake-prepared/1")
            self.assertTrue(manifest["namespace"].startswith("beaver-native-rebound/"))
            self.assertEqual(manifest["native"], "partial")
            self.assertEqual(manifest["preparation"]["adoption"], "not_run")
            lineage_path = candidate / manifest["preparation"]["lineagePath"]
            self.assertEqual(digest_file(lineage_path), manifest["preparation"]["lineageSha256"])
            fragments = load(read(Path(result["intakeSpecFragments"])))
            self.assertEqual(len(fragments["externalScripts"]), 1)
            self.assertEqual(fragments["externalScripts"][0]["sourceGuid"], TARGET_GUID)
            self.assertTrue(fragments["compilerCoverage"]["remainingCoverageRequired"] is False)
            spec4 = dict(schemaVersion=4, operation="additive-intake",
                         candidateManifestSha256=manifest_sha,
                         additions=[dict(source="Assets/Panel.prefab", target="Assets/Recovered/Panel.prefab")],
                         externalScripts=fragments["externalScripts"],
                         omittedCompilerInputs=fragments["omittedCompilerInputs"],
                         verifications=fragments["spec4Fragment"]["verifications"],
                         protectedAssets=[], evidence=[], externalAssets=[], packageScripts=[],
                         newScripts=[], engineObjects=fragments["spec4Fragment"]["engineObjects"])
            intake_spec = f["root"] / "intake-v4.json"
            write_json(intake_spec, spec4)
            plan = intake_build_plan(candidate, f["target"], intake_spec)
            self.assertEqual(plan["schemaVersion"], 4)
            self.assertEqual(len(plan["externalScripts"]), 1)
            self.assertEqual(plan["native"], "not_run")

    def test_wrong_mapped_script_guid_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            f = self.fixture(Path(temp).resolve())
            bad = copy.deepcopy(f["snapshot"])
            prop = bad["prefabs"][0]["owners"][1]["properties"][0]
            prop["reference"]["guid"] = SOURCE_GUID
            prop["value"] = f"{SOURCE_GUID}#11500000|UnityEditor.MonoScript@UnityEditor.CoreModule|script:Widget@Assembly-CSharp"
            self.refresh_native_snapshot(f, bad)
            with self.assertRaises(BeaverError) as caught:
                self.export(f, snapshot=bad)
            self.assertEqual(caught.exception.code, "INTAKE_BINDING_EXPORT_OWNER_GUID")
            self.assertFalse((f["stage"] / "frozen-candidate").exists())

    def test_duplicate_owner_id_and_prepared_source_drift_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            f = self.fixture(Path(temp).resolve())
            duplicate = copy.deepcopy(f["snapshot"])
            duplicate["prefabs"][0]["owners"].append(copy.deepcopy(duplicate["prefabs"][0]["owners"][0]))
            self.refresh_native_snapshot(f, duplicate)
            with self.assertRaises(BeaverError) as caught:
                self.export(f, snapshot=duplicate)
            self.assertEqual(caught.exception.code, "INTAKE_BINDING_EXPORT_DUPLICATE")
            self.refresh_native_snapshot(f, f["snapshot"])
            changed = f["project"] / "Assets/Widget.cs"
            changed.write_bytes(changed.read_bytes() + b"// drift\n")
            with self.assertRaises(BeaverError) as caught:
                self.export(f)
            self.assertEqual(caught.exception.code, "INTAKE_BINDING_EXPORT_DRIFT")

    @staticmethod
    def refresh_native_snapshot(f, snapshot):
        raw = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        for mode in ("apply", "verify"):
            leaf = mode + "-snapshot.json"
            (f["stage"] / leaf).write_bytes(raw)
            write_json(f["stage"] / (mode + "-report.json"),
                       dict(status="verified", mode=mode, planSha256="a" * 64,
                            snapshotFile=leaf, snapshotSha256=sha(raw), snapshotBytes=len(raw)))


if __name__ == "__main__":
    unittest.main()
