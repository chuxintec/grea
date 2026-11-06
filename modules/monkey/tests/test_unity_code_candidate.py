import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from monkey.sources.compiled import ParseError
from monkey.unity_code_candidate import prepare_candidate
from monkey.unity_code_sources import inspect


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
    public interface IOrderRule {
        bool Allow(int value);
    }
}
"""


@unittest.skipUnless(UNITY_CSC.is_file() and UNITY_RESPONSE.is_file() and ILSPY.is_file() and DOTNET,
                     "Unity 6000.6.2f1 SDK and configured ILSpy provider are required for the legal Mono fixture")
class UnityCodeCandidateTests(unittest.TestCase):
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
        self.assertEqual(proc.returncode, 0, "self-authored Mono fixture compilation failed")
        return assembly, hashlib.sha256(assembly.read_bytes()).hexdigest()

    def _references(self) -> list[str]:
        return ['"' + line.strip().strip('"') + '"' for line in UNITY_RESPONSE.read_text(encoding="utf-8").splitlines()
                if line.strip().strip('"').startswith("-r:")]

    def test_exact_report_generates_isolated_csharp_and_target_compiles_and_behaves_as_expected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            assembly, source_hash = self._compile_fixture(root)
            source_result = inspect(assembly, root / "source-report", expected_sha256=source_hash,
                                    family="mono", provider=ILSPY)
            source_report = Path(source_result["report"])
            report_hash = hashlib.sha256(source_report.read_bytes()).hexdigest()
            body_method_ids = [row["methodId"] for row in json.loads(source_report.read_text(encoding="utf-8"))["methods"]
                               if row["name"] in {"Sum", "CanAfford", "AddNonNegative"}]
            result = prepare_candidate(source_report, root / "candidate", expected_report_sha256=report_hash,
                                       method_ids=body_method_ids)
            report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "draft_closed")
            self.assertFalse(report["sourceCodeExecuted"])
            self.assertFalse(report["originalAssemblyExecuted"])
            self.assertEqual(report["implementedMethods"], 0)
            self.assertTrue(report["closure"]["closedForObservedCalls"])
            self.assertTrue(report["closure"]["allMethodsHaveBodies"])
            source_files = [str(root / "candidate" / row["candidatePath"]) for row in report["candidateFiles"]]
            self.assertEqual(len(source_files), 2)

            target = root / "candidate-built.dll"
            target_rsp = root / "candidate-build.rsp"
            target_rsp.write_text("\n".join(['"-nologo"', '"-target:library"', '"-deterministic+"',
                                               '"-out:' + str(target) + '"', *self._references(),
                                               *['"' + path + '"' for path in source_files]]) + "\n", encoding="utf-8")
            compiled = subprocess.run([DOTNET, str(UNITY_CSC), "@" + str(target_rsp)], capture_output=True,
                                      timeout=60, check=False)
            self.assertEqual(compiled.returncode, 0, "generated candidate C# did not compile")
            self.assertTrue(target.is_file())

            harness = root / "BehaviorCheck.cs"
            harness.write_text("""using MonkeyFixture.Economy;
class BehaviorCheck {
    static int Main() {
        var calculator = new OrderCalculator();
        if (calculator.Sum(new[] { 1, 2, 3 }) != 6) return 1;
        if (calculator.Sum(null) != 0) return 2;
        if (!calculator.CanAfford(6, 6) || calculator.CanAfford(7, 6)) return 3;
        if (PriceMath.AddNonNegative(-2, 1) != 0) return 4;
        return 0;
    }
}
""", encoding="utf-8")
            harness_dll = root / "BehaviorCheck.dll"
            harness_rsp = root / "behavior-check.rsp"
            harness_rsp.write_text("\n".join(['"-nologo"', '"-target:exe"',
                                                 '"-out:' + str(harness_dll) + '"', *self._references(),
                                                 '"-r:' + str(target) + '"', '"' + str(harness) + '"']) + "\n",
                                   encoding="utf-8")
            harness_compile = subprocess.run([DOTNET, str(UNITY_CSC), "@" + str(harness_rsp)], capture_output=True,
                                             timeout=60, check=False)
            self.assertEqual(harness_compile.returncode, 0,
                             "independent behavior harness did not compile: " +
                             (harness_compile.stdout + harness_compile.stderr).decode("utf-8", "replace")[-1200:])
            (root / "BehaviorCheck.runtimeconfig.json").write_text(json.dumps({
                "runtimeOptions": {"tfm": "net8.0", "framework": {"name": "Microsoft.NETCore.App", "version": "8.0.0"}}
            }), encoding="utf-8")
            ran = subprocess.run([DOTNET, str(harness_dll)], capture_output=True, timeout=30, check=False)
            self.assertEqual(ran.returncode, 0, "generated fixture candidate failed independent expected behavior")

    def test_report_hash_is_required_and_metadata_only_methods_stay_drafts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            assembly, source_hash = self._compile_fixture(root)
            result = inspect(assembly, root / "source-report", expected_sha256=source_hash,
                             family="mono", provider=ILSPY)
            report_path = Path(result["report"])
            with self.assertRaisesRegex(ParseError, "UNITY_CANDIDATE_REPORT_HASH"):
                prepare_candidate(report_path, root / "wrong-report-hash", expected_report_sha256="0" * 64)
            report_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
            source_report_doc = json.loads(report_path.read_text(encoding="utf-8"))
            source_row = next(row for row in source_report_doc["outputs"] if row.get("role") == "decompiled-source")
            source_path = report_path.parent / source_row["path"]
            exact_source = source_path.read_bytes()
            source_path.write_bytes(exact_source + b"// altered after decompilation\n")
            with self.assertRaisesRegex(ParseError, "UNITY_CANDIDATE_INPUT_CHANGED"):
                prepare_candidate(report_path, root / "changed-decompiler-source", expected_report_sha256=report_hash)
            source_path.write_bytes(exact_source)
            candidate = prepare_candidate(report_path, root / "incomplete-candidate", expected_report_sha256=report_hash)
            candidate_doc = json.loads(Path(candidate["report"]).read_text(encoding="utf-8"))
            self.assertEqual(candidate["status"], "draft_incomplete")
            self.assertGreater(len(candidate_doc["closure"]["methodsWithoutBodies"]), 0)
            self.assertEqual(candidate_doc["implementedMethods"], 0)

    def test_provider_is_explicit_or_configured_and_never_guessed_from_adjacent_checkout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            assembly, source_hash = self._compile_fixture(root)
            with patch.dict("os.environ", {"MONKEY_ILSPY_PROVIDER": ""}):
                with self.assertRaisesRegex(ParseError, "UNITY_CODE_PROVIDER_REQUIRED"):
                    inspect(assembly, root / "no-provider", expected_sha256=source_hash, family="mono", provider=None)


if __name__ == "__main__":
    unittest.main()
