"""Pinned six-script intake binding completion tests."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

TEST_DIR = Path(__file__).resolve().parent

from grea.development.intake_binding_completion import propose
from grea.development.io import encoded, sha, write_json
from grea.development.intake_bindings import BRIDGE
from grea.development.unity import source_files


FOUR = [
    ("NativeRectConstraints", "Assets/Game/Presentation/Common/Layout/NativeRectConstraints.cs", "Assets/Game/Presentation/Common/Layout/NativeRectConstraints.cs"),
    ("NativeLinearLayoutGroup", "Assets/Game/Presentation/Common/Layout/NativeLinearLayoutGroup.cs", "Assets/Game/Presentation/Common/Layout/NativeLinearLayoutGroup.cs"),
    ("IntrinsicGridLayoutGroup", "Assets/Game/Presentation/Common/Layout/IntrinsicGridLayoutGroup.cs", "Assets/Game/Presentation/Common/Layout/IntrinsicGridLayoutGroup.cs"),
    ("NativeTextLineBox", "Assets/Game/Presentation/Common/Layout/NativeTextLineBox.cs", "Assets/Game/Presentation/Common/Layout/NativeTextLineBox.cs"),
]
EXTRA = [
    ("NativeInputBlocker", "Assets/Game/Presentation/Common/Layout/NativeInputBlocker.cs", "Assets/Game/Adopted/MonkeyDev1Dependencies/NativeInputBlocker.cs"),
    ("NativeInputBlockerSurface", "Assets/Game/Presentation/Common/Layout/NativeInputBlockerSurface.cs", "Assets/Game/Adopted/MonkeyDev1Dependencies/NativeInputBlockerSurface.cs"),
]


class IntakeBindingCompletionTests(unittest.TestCase):
    def fixture(self, root, *, bridge=False, reuse_rows=None):
        source, target, candidate = root / "source", root / "target", root / "candidate"
        for project in (source, target):
            (project / "Assets").mkdir(parents=True)
            (project / "ProjectSettings").mkdir()
            (project / "ProjectSettings/ProjectVersion.txt").write_text("m_EditorVersion: 6000.6.2f1\n", encoding="utf-8")
            (project / "Packages").mkdir()
            write_json(project / "Packages/manifest.json", {"dependencies": {}})
        (target / "Assets/Game/Presentation/FoodStreet.Presentation.asmdef").parent.mkdir(parents=True)
        write_json(target / "Assets/Game/Presentation/FoodStreet.Presentation.asmdef", {"name": "FoodStreet.Presentation"})
        all_rows = FOUR + list(EXTRA if reuse_rows is None else reuse_rows)
        old, new = [], []
        for index, (name, src, dst) in enumerate(all_rows):
            code = ("public sealed class " + name + " : UnityEngine.MonoBehaviour { public int value; }\n").encode()
            src_file, dst_file = source / src, target / dst
            src_file.parent.mkdir(parents=True, exist_ok=True); dst_file.parent.mkdir(parents=True, exist_ok=True)
            src_file.write_bytes(code); dst_file.write_bytes(code)
            source_guid = f"{index + 1:032x}"; target_guid = f"{index + 101:032x}"
            Path(str(src_file) + ".meta").write_text(f"fileFormatVersion: 2\nguid: {source_guid}\n", encoding="utf-8")
            Path(str(dst_file) + ".meta").write_text(f"fileFormatVersion: 2\nguid: {target_guid}\n", encoding="utf-8")
            if index < 4:
                old.append(dict(source=src, sourceAssembly="Assembly-CSharp", sourceGuid=source_guid,
                    sourceMetaSha256=sha(Path(str(src_file) + ".meta").read_bytes()), sourceSha256=sha(code),
                    target=dst, targetAssembly="FoodStreet.Presentation", targetGuid=target_guid,
                    targetLocalId=11500000, targetMetaSha256=sha(Path(str(dst_file) + ".meta").read_bytes()),
                    targetSha256=sha(code), type=name))
            else:
                new.append(dict(path=src, guid=source_guid, sha256=sha(code), category="retained_type_requires_binding_review",
                    nativeReferenced=True, inSelectedClosure=True, scope={"assembly": "Assembly-CSharp"},
                    byteIdenticalTargetSources=[dst],
                    targetAssemblies=["Assembly-CSharp"], targetSourcePins=[dict(path=dst, guid=target_guid,
                        sha256=sha(code), metaSha256=sha(Path(str(dst_file) + ".meta").read_bytes()))],
                    types=[dict(fullName=name, assembly="Assembly-CSharp", unityObject=True,
                        fields=[dict(name="value", type="System.Int32", assembly="netstandard", serialized=True)],
                        interfaces=[], dependencies=[])], dependencies=[], lateBoundDependencies=[]))
        # New input blockers deliberately require a closed two-source cycle for preparation.
        pref = source / "Assets/Selected.prefab"
        pref.parent.mkdir(parents=True, exist_ok=True)
        refs = "".join("  m_Script: {fileID: 11500000, guid: " + f"{index + 1:032x}" + ", type: 3}\n" for index in range(len(all_rows)))
        pref.write_text("Prefab:\n" + refs, encoding="utf-8")
        Path(str(pref) + ".meta").write_text("fileFormatVersion: 2\nguid: " + "f" * 32 + "\n", encoding="utf-8")
        if bridge:
            (source / BRIDGE).mkdir(parents=True)

        candidate.mkdir()
        lineage_dir = candidate / "Analysis/BeaverIntakeBindings"
        lineage_dir.mkdir(parents=True)
        write_json(candidate / "Assets/BeaverIntakeBindings/Beaver.IntakeBindings.asmdef",
                   {"name": "Beaver.IntakeBindings", "autoReferenced": False, "references": ["UnityEngine.UI", "Unity.TextMeshPro"]})
        write_json(lineage_dir / "intake-spec-fragments.json", {"spec4Fragment": {"verifications": [{"asset": "Assets/Selected.prefab"}]}})
        write_json(lineage_dir / "source-origin.json", {"origin": {"root": str(source)}})
        lineage = {"source": {"root": str(source), "sourceFilesSha256": hashlib.sha256(encoded(source_files(source))).hexdigest()},
                   "rebind": {"sourceToRetainedBindings": old}}
        write_json(lineage_dir / "lineage.json", lineage)

        semantic_rows = []
        semantic_sources = []
        for name, src, _ in all_rows:
            semantic_sources.append({"path": src, "sha256": sha((source / src).read_bytes())})
            semantic_rows.append({"path": src, "types": [dict(fullName=name, assembly="Assembly-CSharp",
                unityObject=True, fields=[dict(name="value", type="System.Int32", assembly="netstandard", serialized=True)],
                interfaces=[], kind="Class")], "dependencies": ([dict(path=EXTRA[1][1], assembly="Assembly-CSharp", symbol="NativeInputBlockerSurface")]
                    if name == "NativeInputBlocker" else []), "unresolved": [], "lateBoundDependencies": []})
        semantic_path = candidate / "semantic-report.json"
        write_json(semantic_path, {"status": "ok", "assemblies": [{"name": "Assembly-CSharp", "sources": semantic_sources,
            "sourceSemantics": semantic_rows}]})
        for rel in ("Analysis/BeaverIntakeBindings/lineage.json", "Analysis/BeaverIntakeBindings/intake-spec-fragments.json",
                    "Analysis/BeaverIntakeBindings/source-origin.json", "Assets/BeaverIntakeBindings/Beaver.IntakeBindings.asmdef"):
            p = candidate / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            # Candidate manifest pins artifacts required by this planner.
        candidate_source_files = []
        for _, src, _ in all_rows:
            for relative in (src, src + ".meta"):
                source_file = source / relative
                candidate_file = candidate / relative
                candidate_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, candidate_file)
                candidate_source_files.append(relative)
        files = []
        for rel in ("Analysis/BeaverIntakeBindings/lineage.json", "Analysis/BeaverIntakeBindings/intake-spec-fragments.json",
                    "Analysis/BeaverIntakeBindings/source-origin.json", "Assets/BeaverIntakeBindings/Beaver.IntakeBindings.asmdef"):
            p = candidate / rel
            files.append(dict(path=rel, sha256=sha(p.read_bytes()), bytes=p.stat().st_size))
        for rel in candidate_source_files:
            p = candidate / rel
            files.append(dict(path=rel, sha256=sha(p.read_bytes()), bytes=p.stat().st_size))
        write_json(candidate / "manifest.json", {"files": files})
        evidence_path = root / "dependency-evidence.json"
        context_pin = root / "assembly.rsp"
        context_pin.write_text("/reference:System.Runtime.dll\n", encoding="utf-8")
        write_json(evidence_path, {"contract": "beaver-intake-dependencies/1",
            "candidateManifestSha256": sha((candidate / "manifest.json").read_bytes()),
            "sourceProject": str(candidate / "derived-source"),
            "contextPins": {str(context_pin): sha(context_pin.read_bytes())},
            "semanticReport": {"path": str(semantic_path), "sha256": sha(semantic_path.read_bytes())},
            "reuseCandidates": new})
        return candidate, target, source, evidence_path

    def test_complete_six_item_plan_is_future_only_and_native_not_run(self):
        with tempfile.TemporaryDirectory(dir=TEST_DIR) as temp:
            root = Path(temp); candidate, target, source, evidence = self.fixture(root)
            result = propose(candidate, target, source, root / "out", dependency_report=evidence)
            self.assertEqual(result["status"], "planned", result)
            completion = json.loads(Path(result["report"]).read_text())
            plan = json.loads(Path(result["plan"]).read_text())
            self.assertEqual(completion["bindingCount"], 6)
            self.assertEqual(len(plan["spec"]["bindings"]), 6)
            self.assertEqual(plan["native"], "not_run")
            self.assertFalse(plan["targetWrites"])
            self.assertEqual(completion["consumerPreparation"], "planned_not_executed")
            self.assertEqual(len(completion["consumerExternalScripts"]), 6)
            for item in completion["consumerExternalScripts"]:
                self.assertEqual(item["source"], BRIDGE + "/" + Path(item["target"]).name)
                self.assertEqual(item["sourceAssembly"], "Beaver.IntakeBindings")
                self.assertFalse(item["preparedNow"])
                self.assertEqual(item["status"], "planned_not_executed")

    def test_original_source_drift_is_blocked(self):
        with tempfile.TemporaryDirectory(dir=TEST_DIR) as temp:
            root = Path(temp); candidate, target, source, evidence = self.fixture(root)
            (source / FOUR[0][1]).write_text("changed", encoding="utf-8")
            result = propose(candidate, target, source, root / "out", dependency_report=evidence)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["code"], "INTAKE_BINDING_SOURCE_DRIFT")

    def test_target_drift_is_blocked(self):
        with tempfile.TemporaryDirectory(dir=TEST_DIR) as temp:
            root = Path(temp); candidate, target, source, evidence = self.fixture(root)
            (target / FOUR[0][2]).write_text("changed", encoding="utf-8")
            result = propose(candidate, target, source, root / "out", dependency_report=evidence)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["code"], "INTAKE_BINDING_DRIFT")

    def test_explicit_future_source_root_is_revalidated_against_original_evidence(self):
        with tempfile.TemporaryDirectory(dir=TEST_DIR) as temp:
            root = Path(temp); candidate, target, source, evidence = self.fixture(root)
            future_source = root / "future-source"
            shutil.copytree(source, future_source)
            shutil.rmtree(source)
            result = propose(candidate, target, future_source, root / "out", dependency_report=evidence)
            self.assertEqual(result["status"], "planned", result)
            completion = json.loads(Path(result["report"]).read_text())
            self.assertFalse(completion["sourceLineage"]["sourceIsLineageRoot"])
            self.assertFalse(completion["sourceLineage"]["lineageRootInventoryChecked"])
            self.assertEqual(completion["sourceLineage"]["sourceRoot"], str(future_source))
            self.assertEqual(completion["currentSourceFieldValidation"], "pending_fresh_compile_context_for_future_source")

    def test_native_reuse_candidates_are_discovered_without_filename_allowlist(self):
        extra = ("AdditionalNativeGate", "Assets/Game/Presentation/Common/Layout/AdditionalNativeGate.cs",
                 "Assets/Game/Adopted/AdditionalNativeGate.cs")
        with tempfile.TemporaryDirectory(dir=TEST_DIR) as temp:
            root = Path(temp); candidate, target, source, evidence = self.fixture(root, reuse_rows=EXTRA + [extra])
            result = propose(candidate, target, source, root / "out", dependency_report=evidence)
            self.assertEqual(result["status"], "planned", result)
            completion = json.loads(Path(result["report"]).read_text())
            self.assertEqual(completion["bindingCount"], 7)
            self.assertIn("AdditionalNativeGate", {row["type"] for row in completion["consumerDependencyEvidence"]})

    def test_existing_bridge_root_is_rejected_by_existing_planner(self):
        with tempfile.TemporaryDirectory(dir=TEST_DIR) as temp:
            root = Path(temp); candidate, target, source, evidence = self.fixture(root, bridge=True)
            result = propose(candidate, target, source, root / "out", dependency_report=evidence)
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["code"], "INTAKE_BINDING_RESERVED")


if __name__ == "__main__":
    unittest.main()
