import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from monkey.code_postprocess_plan import prepare_plan
from monkey.sources.compiled import ParseError


def _sha(data):
    return hashlib.sha256(data).hexdigest()


class CodePostprocessPlanTests(unittest.TestCase):
    def build_candidate(self, root, *, sizes=(32, 16), cycle=True, extra_code=None,
                        extra_sources=None, owners=None):
        source = b"function outer(){ return function inner(){ return 1; }; }\n"
        source_sha = _sha(source)
        digest = source_sha[:12]
        source_path = f"SourceRecovery/Code/Source/{digest}/Source.js"
        report_path = f"Analysis/Code/Drafts/{digest}/csharp-drafts.json"
        package_path = "Analysis/Code/package-csharp-drafts.json"
        detail_path = f"Analysis/Code/Drafts/{digest}/Details/Part0001.json"
        targets = [f"SourceRecovery/CSharp/{digest}/Unclassified/Class{i}.cs" for i in range(len(sizes))]
        files = {}
        files[source_path] = source
        for index, size in enumerate(sizes):
            files[targets[index]] = (f"// class {index}\n".encode() + b"x" * max(0, size - len(f"// class {index}\n")))[:size]
        for path, data in (extra_code or {}).items():
            files[path] = data
        for path, data in (extra_sources or {}).items():
            files[path] = data
        files[detail_path] = b'{"records":[]}'

        function_rows = []
        if targets:
            function_rows.append({"kind": "indexed_method", "methodId": "method@1", "sourceName": "outer",
                "sourceSha256": _sha(source[0:56]), "sourceBytes": {"start": 0, "end": 56},
                "functionBytes": {"start": 0, "end": 56}, "targetPath": targets[0], "targetClass": "Class0",
                "targetMethod": "Outer", "targetLocationMarker": None, "status": "drafted",
                "detailsPath": detail_path, "detailsIndex": 0})
        if len(targets) > 1:
            function_rows.append({"kind": "auxiliary_function", "methodId": "function@20", "sourceName": "inner",
                "sourceSha256": _sha(source[20:54]), "sourceBytes": {"start": 20, "end": 54},
                "functionBytes": {"start": 20, "end": 54}, "targetPath": targets[1], "targetClass": "Class1",
                "targetMethod": "Inner", "targetLocationMarker": None, "status": "drafted",
                "detailsPath": detail_path, "detailsIndex": 1})
        field_rows = []
        if len(targets) > 1:
            field_rows.append({"fieldId": "field@2", "sourceName": "VALUE", "sourceSha256": _sha(source[0:8]),
                "sourceBytes": {"start": 0, "end": 8}, "targetPath": targets[1], "targetClass": "Class1",
                "targetMember": "Value", "initializationContext": "class_factory", "status": "drafted",
                "detailsPath": detail_path, "detailsIndex": 2})
        modules = []
        for index, target in enumerate(targets):
            module_id = f"Module{index}"
            dependency = f"Module{1-index}" if cycle and len(targets) > 1 else None
            modules.append({"id": module_id, "targetPaths": [target], "dependencies": [dependency] if dependency else [],
                "methodIds": [row["methodId"] for row in function_rows if row["targetPath"] == target]})
        report = {"schemaVersion": 1, "status": "full_source_csharp_drafts; compile_excluded",
            "source": {"sha256": source_sha, "bytes": len(source)}, "sourcePath": source_path,
            "coverage": {"functionsMapped": len(function_rows), "functionsEmitted": len(function_rows),
                "indexedMethodFunctionsEmitted": sum(row["kind"] == "indexed_method" for row in function_rows),
                "indexedMethodsInSource": sum(row["kind"] == "indexed_method" for row in function_rows),
                "fieldRecords": len(field_rows)},
            "classes": [{"targetPath": target, "classId": f"class@{i}", "sourceName": f"Class{i}",
                "group": "Unclassified", "indexedMethodCount": sum(row["targetPath"] == target and row["kind"] == "indexed_method" for row in function_rows),
                "auxiliaryFunctionCount": sum(row["targetPath"] == target and row["kind"] != "indexed_method" for row in function_rows)}
                for i, target in enumerate(targets)],
            "modules": modules, "functions": function_rows, "fields": field_rows,
            "details": [{"path": detail_path, "records": 3}],
            "diagnostics": {"count": 2, "countsByCode": {"unresolved_member_mapping": 2}}}
        package = {"schemaVersion": 1, "kind": "full-csharp-drafts-v1", "sourceExecuted": False,
            "sources": [{"reportPath": report_path}]}
        files[report_path] = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
        files[package_path] = json.dumps(package, sort_keys=True, separators=(",", ":")).encode()
        for path, data in files.items():
            absolute = root / path
            absolute.parent.mkdir(parents=True, exist_ok=True)
            absolute.write_bytes(data)
        inventory = [{"path": path, "sha256": _sha(data), "bytes": len(data),
            "owner": (owners or {}).get(path, "generated")}
            for path, data in sorted(files.items())]
        manifest = {"schemaVersion": 1, "scopeMode": "whole-input",
            "codeDrafts": {"kind": "full-csharp-drafts-v1", "sourceFiles": 1, "report": package_path},
            "files": inventory}
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        return _sha(manifest_path.read_bytes()), targets

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.root = Path(self.temp.name) / "candidate"
        self.root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_once_file_and_method_field_mapping_with_cycle_hints(self):
        pin, targets = self.build_candidate(self.root)
        plan = prepare_plan(self.root, pin, max_files=1, max_code_bytes=48)
        self.assertEqual(plan["coverage"]["codeFiles"], 2)
        self.assertEqual(plan["coverage"]["functions"], 2)
        self.assertEqual(plan["coverage"]["indexedMethods"], 1)
        self.assertEqual(plan["coverage"]["fields"], 1)
        self.assertEqual(plan["coverage"]["exactOnceFiles"], 2)
        self.assertTrue(all(len(batch["paths"]) == 1 for batch in plan["batches"]))
        self.assertTrue(all(batch["dependsOn"] == [] for batch in plan["batches"]))
        self.assertTrue(all(batch["dependencyOrdering"] == "advisory_only_cycles_never_block_queue"
                            for batch in plan["batches"]))
        self.assertTrue(all(batch["dependencyReferences"] for batch in plan["batches"]))
        self.assertTrue(all(batch["dependencyBatchHints"] for batch in plan["batches"]))
        self.assertEqual(sum(len(batch["mappingRefs"]) for batch in plan["batches"]), 3)
        self.assertEqual(sum(len(row["functions"]) for row in plan["files"]), 2)
        self.assertEqual(sum(len(row["fields"]) for row in plan["files"]), 1)
        self.assertTrue(all("methodId" in row for file in plan["files"] for row in file["functions"]))
        self.assertTrue(all("fieldId" in row for file in plan["files"] for row in file["fields"]))
        self.assertTrue(any(ref["sourceSpan"]["start"] == 0
                            for row in plan["files"] for ref in row["sourceSpanRefs"]))
        self.assertEqual(plan["sources"][0]["sha256"], plan["files"][0]["sourceId"])

    def test_oversize_class_file_is_kept_whole_in_one_marked_batch(self):
        pin, targets = self.build_candidate(self.root, sizes=(100, 16), cycle=False)
        plan = prepare_plan(self.root, pin, max_files=8, max_code_bytes=32)
        oversized = [batch for batch in plan["batches"] if batch["oversizeSingleFile"]]
        self.assertEqual(len(oversized), 1)
        self.assertEqual(oversized[0]["paths"], [targets[0]])
        self.assertEqual(oversized[0]["bytes"], 100)

    def test_assets_legacy_cs_is_included_as_explicit_extra_code(self):
        legacy_path = "Assets/legacy.cs"
        pin, _ = self.build_candidate(self.root, extra_code={legacy_path: b"// native helper fixture\n"})
        plan = prepare_plan(self.root, pin)
        legacy = next(row for row in plan["files"] if row["path"] == legacy_path)
        self.assertTrue(legacy["extraCode"])
        self.assertIsNone(legacy["sourceId"])
        self.assertIsNone(legacy["sourceSha256"])
        self.assertIsNone(legacy["sourcePath"])
        self.assertEqual(legacy["functions"], [])
        self.assertEqual(legacy["fields"], [])
        self.assertIn("review exact owning C# bytes", legacy["absentSourceReason"])
        self.assertIn(legacy_path, {path for batch in plan["batches"] for path in batch["paths"]})
        self.assertEqual(plan["coverage"]["codeFiles"], 3)
        self.assertEqual(plan["coverage"]["extraCodeFiles"], 1)

    def test_non_generated_cs_is_read_only_blocked_and_not_batched(self):
        legacy_path = "Assets/legacy.cs"
        pin, _ = self.build_candidate(self.root, extra_code={legacy_path: b"// manual fixture\n"},
            owners={legacy_path: "manual"})
        plan = prepare_plan(self.root, pin)
        row = next(row for row in plan["files"] if row["path"] == legacy_path)
        self.assertEqual(row["status"], "blocked_owner")
        self.assertEqual(row["owner"], "manual")
        self.assertNotIn(legacy_path, {path for batch in plan["batches"] for path in batch["paths"]})
        self.assertEqual(plan["coverage"]["blockedFiles"], 1)

    def test_legacy_module_source_requires_exact_header_hash_match(self):
        legacy_path = "SourceRecovery/Code/Drafts/CSharp/Domain/Legacy.cs"
        module_path = "SourceRecovery/Code/Modules/Unclassified/Legacy.js"
        module = b"function Legacy(){return 1;}\n"
        header = ("// Source module SHA256: " + _sha(module) + "\n" +
                  "public class Legacy {}\n").encode()
        pin, _ = self.build_candidate(self.root, extra_code={legacy_path: header},
            extra_sources={module_path: module})
        plan = prepare_plan(self.root, pin)
        legacy = next(row for row in plan["files"] if row["path"] == legacy_path)
        self.assertEqual(legacy["sourceKind"], "hash-proven-legacy-module")
        self.assertTrue(legacy["sourceWholeModule"])
        self.assertEqual(legacy["sourcePath"], module_path)
        self.assertEqual(legacy["sourceSha256"], _sha(module))
        self.assertEqual(legacy["functions"], [])
        self.assertEqual(legacy["fields"], [])

    def test_legacy_modules_share_directory_batch_but_keep_per_file_source_pins(self):
        modules = {
            "SourceRecovery/Code/Modules/Unclassified/One.js": b"function One(){return 1;}\n",
            "SourceRecovery/Code/Modules/Unclassified/Two.js": b"function Two(){return 2;}\n",
        }
        legacy_files = {
            "SourceRecovery/Code/Drafts/CSharp/Domain/One.cs": (
                "// Source module SHA256: " + _sha(modules["SourceRecovery/Code/Modules/Unclassified/One.js"])
                + "\npublic class One {}\n").encode(),
            "SourceRecovery/Code/Drafts/CSharp/Domain/Two.cs": (
                "// Source module SHA256: " + _sha(modules["SourceRecovery/Code/Modules/Unclassified/Two.js"])
                + "\npublic class Two {}\n").encode(),
        }
        pin, _ = self.build_candidate(self.root, extra_code=legacy_files, extra_sources=modules)
        plan = prepare_plan(self.root, pin, max_files=128, max_code_bytes=512 * 1024)
        rows = {row["path"]: row for row in plan["files"] if row.get("extraCode")}
        one, two = legacy_files.keys()
        self.assertEqual(rows[one]["sourceKind"], "hash-proven-legacy-module")
        self.assertEqual(rows[two]["sourceKind"], "hash-proven-legacy-module")
        self.assertNotEqual(rows[one]["sourceSha256"], rows[two]["sourceSha256"])
        batches_by_path = {path: batch for batch in plan["batches"] for path in batch["paths"]}
        self.assertEqual(batches_by_path[one]["id"], batches_by_path[two]["id"])
        batch = batches_by_path[one]
        self.assertEqual(set(batch["sourceIds"]), {_sha(modules[p]) for p in modules})

    def test_manifest_pin_and_owned_csharp_integrity_are_enforced(self):
        pin, targets = self.build_candidate(self.root)
        with self.assertRaises(ParseError):
            prepare_plan(self.root, "0" * 64)
        (self.root / targets[0]).write_bytes(b"changed")
        with self.assertRaises(ParseError):
            prepare_plan(self.root, pin)

    def test_batch_limits_are_bounded(self):
        pin, _ = self.build_candidate(self.root)
        with self.assertRaises(ParseError):
            prepare_plan(self.root, pin, max_files=0)
        with self.assertRaises(ParseError):
            prepare_plan(self.root, pin, max_code_bytes=1024 * 1024 + 1)


if __name__ == "__main__":
    unittest.main()
