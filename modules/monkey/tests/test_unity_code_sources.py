import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from monkey.evidence_queries import query_methods
from monkey.sources.compiled import ParseError
from monkey.unity_code_sources import MAX_SOURCE_BYTES, inspect


UNITY_CSC = Path("/Applications/Unity/Hub/Editor/6000.6.2f1/Unity.app/Contents/Resources/Scripting/DotNetSdk/sdk/8.0.318/Roslyn/bincore/csc.dll")
UNITY_RESPONSE = Path(__file__).resolve().parents[1] / ".private/v050-resources-20261026/clip-compile.rsp"
ILSPY = Path(__file__).resolve().parents[2] / "grea/bin/ilspy"
DOTNET = shutil.which("dotnet")
FIXTURE = """namespace MonkeyFixture.Economy {
    public static class PriceMath {
        public static int AddNonNegative(int left, int right) {
            var sum = left + right;
            if (sum < 0) return 0;
            return sum;
        }
    }
    public sealed class OrderCalculator {
        public int Sum(int[] quantities) {
            if (quantities == null) return 0;
            var total = 0;
            for (var i = 0; i < quantities.Length; i++) {
                total = PriceMath.AddNonNegative(total, quantities[i]);
            }
            return total;
        }
        public bool CanAfford(int total, int balance) => total <= balance;
    }
}
"""


@unittest.skipUnless(UNITY_CSC.is_file() and UNITY_RESPONSE.is_file() and ILSPY.is_file() and DOTNET,
                     "Unity 6000.6.2f1 SDK and registered ILSpy provider are required for the legal Mono fixture")
class UnityCodeSourceTests(unittest.TestCase):
    def _compile_fixture(self, root: Path) -> tuple[Path, str]:
        source = root / "OrderModule.cs"
        assembly = root / "OrderModule.dll"
        source.write_text(FIXTURE, encoding="utf-8")
        references = []
        for line in UNITY_RESPONSE.read_text(encoding="utf-8").splitlines():
            value = line.strip().strip('"')
            if value.startswith("-r:"):
                references.append('"' + value + '"')
        rsp = root / "fixture.rsp"
        rsp.write_text("\n".join(['"-nologo"', '"-target:library"', '"-deterministic+"',
                                    '"-out:' + str(assembly) + '"', *references,
                                    '"' + str(source) + '"']) + "\n", encoding="utf-8")
        proc = subprocess.run([DOTNET, str(UNITY_CSC), "@" + str(rsp)], capture_output=True, timeout=60, check=False)
        self.assertEqual(proc.returncode, 0, "Unity SDK fixture compilation failed")
        self.assertTrue(assembly.is_file())
        return assembly, hashlib.sha256(assembly.read_bytes()).hexdigest()

    def test_mono_fixture_decompiles_bodies_and_resolves_cross_class_call_without_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            assembly, source_hash = self._compile_fixture(root)
            result = inspect(assembly, root / "candidate", expected_sha256=source_hash, family="mono", provider=ILSPY)
            report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "decompiled_body_not_verified")
            self.assertFalse(report["sourceCodeExecuted"])
            self.assertEqual(report["source"]["sha256"], source_hash)
            self.assertEqual(report["summary"]["decompiledBodies"], 3)
            self.assertEqual(report["summary"]["implementedMethods"], 0)
            self.assertIn("MonkeyFixture.Economy.OrderCalculator", {row["declaringType"] for row in report["methods"]})
            summation = next(row for row in report["methods"] if row["name"] == "Sum")
            self.assertIsNotNone(summation["bodyEvidence"])
            self.assertTrue(any(edge["symbol"] == "PriceMath.AddNonNegative" for edge in report["callEdges"]))
            self.assertEqual(report["provider"]["version"].splitlines()[0], "ilspycmd: 9.1.0.7988")

    def test_wrong_hash_and_non_pe_dummy_dll_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            assembly, source_hash = self._compile_fixture(root)
            with self.assertRaisesRegex(ParseError, "UNITY_CODE_INPUT_CHANGED"):
                inspect(assembly, root / "bad-hash", expected_sha256="0" * 64, provider=ILSPY)
            dummy = root / "Dummy.dll"
            dummy.write_bytes(b"CODEPHPY-not-a-PE-image")
            result = inspect(dummy, root / "not-pe", expected_sha256=hashlib.sha256(dummy.read_bytes()).hexdigest())
            report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "unsupported")
            self.assertEqual(report["summary"]["implementedMethods"], 0)
            self.assertEqual(report["diagnostics"][0]["code"], "MONO_INPUT_NOT_MANAGED_PE")
            self.assertNotIn(source_hash, json.dumps(report))

    def test_il2cpp_map_requires_same_binary_and_metadata_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            wasm = root / "fixture.wasm"
            wasm.write_bytes(b"\0asm\x01\0\0\0" + b"fixture-body-bytes")
            metadata = root / "metadata.json"
            metadata_doc = {"sourceSha256": hashlib.sha256(wasm.read_bytes()).hexdigest(), "revision": "fixture-r1"}
            metadata.write_text(json.dumps(metadata_doc), encoding="utf-8")
            metadata_sha = hashlib.sha256(metadata.read_bytes()).hexdigest()
            method_map = root / "methods.json"
            method_map.write_text(json.dumps({"sourceSha256": "f" * 64, "metadataSha256": metadata_sha,
                                              "methods": [{"module": "fixture.wasm", "function": 3,
                                                           "type": "OrderCalculator", "name": "Sum"}]}), encoding="utf-8")
            with self.assertRaisesRegex(ParseError, "UNITY_CODE_MAP_SOURCE_MISMATCH"):
                inspect(wasm, root / "mismatched", expected_sha256=hashlib.sha256(wasm.read_bytes()).hexdigest(),
                        family="il2cpp-wasm", metadata=metadata, expected_metadata_sha256=metadata_sha,
                        method_map=method_map, expected_method_map_sha256=hashlib.sha256(method_map.read_bytes()).hexdigest())

    def test_hash_bound_il2cpp_method_map_remains_metadata_only_without_body(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            wasm = root / "fixture.wasm"
            wasm.write_bytes(b"\0asm\x01\0\0\0" + b"not-executed")
            source_hash = hashlib.sha256(wasm.read_bytes()).hexdigest()
            metadata = root / "metadata.json"
            metadata.write_text(json.dumps({"sourceSha256": source_hash, "revision": "fixture-r1"}), encoding="utf-8")
            metadata_sha = hashlib.sha256(metadata.read_bytes()).hexdigest()
            method_map = root / "methods.json"
            method_map.write_text(json.dumps({"sourceSha256": source_hash, "metadataSha256": metadata_sha,
                                              "methods": [{"module": "fixture.wasm", "function": 7,
                                                           "type": "OrderCalculator", "name": "Sum"}]}), encoding="utf-8")
            result = inspect(wasm, root / "metadata-only", expected_sha256=source_hash, family="il2cpp-wasm",
                             metadata=metadata, expected_metadata_sha256=metadata_sha,
                             method_map=method_map, expected_method_map_sha256=hashlib.sha256(method_map.read_bytes()).hexdigest())
            report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "metadata_only")
            self.assertFalse(report["sourceCodeExecuted"])
            self.assertEqual(report["methods"][0]["status"], "metadata_only")
            self.assertEqual(report["summary"]["implementedMethods"], 0)
            self.assertEqual(report["methodMap"]["sourceBinding"], "verified")

    def test_existing_query_methods_receipt_retains_exact_map_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            wasm = root / "fixture.wasm"
            wasm.write_bytes(b"\0asm\x01\0\0\0" + b"static-metadata-fixture")
            source_hash = hashlib.sha256(wasm.read_bytes()).hexdigest()
            metadata = root / "metadata.json"
            metadata.write_text(json.dumps({"sourceSha256": source_hash, "revision": "fixture-r2"}), encoding="utf-8")
            metadata_sha = hashlib.sha256(metadata.read_bytes()).hexdigest()
            method_map = root / "methods.json"
            method_map.write_text(json.dumps([{"type": "OrderCalculator", "name": "Sum", "module": "fixture.wasm",
                                               "function": 11, "sourceSha256": source_hash,
                                               "metadataSha256": metadata_sha}]), encoding="utf-8")
            query = query_methods(method_map, hashlib.sha256(method_map.read_bytes()).hexdigest(), root / "query-receipt")
            query_report = root / "query-receipt/inspection.json"
            result = inspect(wasm, root / "joined-report", expected_sha256=source_hash, family="il2cpp-wasm",
                             metadata=metadata, expected_metadata_sha256=metadata_sha,
                             method_map=query_report, expected_method_map_sha256=hashlib.sha256(query_report.read_bytes()).hexdigest())
            report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
            self.assertEqual(query["status"], "verified-metadata")
            self.assertEqual(report["methodMap"]["inputKind"], "evidence_queries.query_methods")
            self.assertEqual(report["methodMap"]["sourceBinding"], "verified")
            self.assertEqual(report["methodMap"]["inputArtifacts"][0]["sha256"], hashlib.sha256(method_map.read_bytes()).hexdigest())
            self.assertEqual(report["methods"][0]["status"], "metadata_only")
            self.assertEqual(report["summary"]["implementedMethods"], 0)

    def test_input_byte_budget_applies_before_provider_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            oversized = root / "oversized.dll"
            with oversized.open("wb") as stream:
                stream.truncate(MAX_SOURCE_BYTES + 1)
            with self.assertRaisesRegex(ParseError, "UNITY_CODE_FILE_BUDGET"):
                inspect(oversized, root / "oversized-output", expected_sha256="0" * 64)
            self.assertFalse((root / "oversized-output").exists())


if __name__ == "__main__":
    unittest.main()
