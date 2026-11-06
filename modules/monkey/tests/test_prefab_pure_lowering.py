import hashlib
from pathlib import Path
import tempfile
import unittest

from monkey.code_graph import facts
from monkey.io import sha
from monkey.prefab_pure_lowering import prepare_pure_lowering
from monkey.sources.compiled import ParseError


RECORDS = {
    "Entry": {
        "unityType": "Entry",
        "creatorType": "Entry",
        "fields": {
            "active": {"type": "Boolean", "unity": "Active", "creator": "active"},
            "score": {"type": "Number", "unity": "Score", "creator": "score"},
        },
    }
}


def contract():
    return {
        "schemaVersion": 1,
        "records": RECORDS,
        "parameters": [{"source": "rows", "type": "Array<Entry>", "unity": "rows", "creator": "rows"}],
        "returns": "Array<Entry>",
    }


def source_for(alias="Rules", threshold="3", direction="ascending", comment=""):
    comparator = "a.score-b.score" if direction == "ascending" else "b.score-a.score"
    return (
        f"// {comment}\n"
        f"var {alias}=(function(){{function C(){{}} C.select=function(rows){{"
        f"return rows.filter(function(row){{return row.active&&row.score>={threshold};}})"
        f".sort(function(a,b){{return {comparator};}});}};return C;}})();"
    ).encode("utf-8")


class PureLoweringTests(unittest.TestCase):
    def _prepare(self, source_bytes, root, contract_value=None):
        source = root / "neutral.js"
        source.write_bytes(source_bytes)
        method = facts(source, sha(source_bytes))["methods"][0]
        result = prepare_pure_lowering(
            source,
            {"classId": method["classId"], "methodId": method["id"]},
            contract_value or contract(),
            root / "candidate",
            expected_source_sha256=sha(source_bytes),
            namespace="Fixture.Domain",
            class_name="EntryRules",
            method_name="Select",
        )
        return result, source

    def test_ast_to_typed_ir_and_dual_target_helpers(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
            root = Path(temp).resolve()
            result, _ = self._prepare(source_for(), root)
            self.assertEqual(result["status"], "candidate")
            self.assertFalse(result["sourceExecuted"])
            expr = result["ir"]["expression"]
            self.assertEqual(expr["kind"], "sort")
            self.assertEqual(expr["comparator"], {"kind": "sortComparator", "field": "score", "direction": "ascending", "form": "difference"})
            self.assertEqual(expr["array"]["kind"], "filter")
            self.assertEqual(expr["array"]["predicate"]["operator"], "&&")
            unity = (root / "candidate/Targets/Unity/Fixture/Domain/EntryRules.cs").read_text()
            creator = (root / "candidate/Targets/Creator/Fixture/Domain/EntryRules.ts").read_text()
            unity_helper = (root / "candidate/Targets/Unity/Fixture/Domain/PureSequence.cs").read_text()
            creator_helper = (root / "candidate/Targets/Creator/Fixture/Domain/PureSequence.ts").read_text()
            self.assertIn("PureSequence.Filter", unity)
            self.assertIn("PureSequence.StableSort", unity)
            self.assertIn("PureSequence.RequireFinite", unity)
            self.assertIn("PureSequence.filter", creator)
            self.assertIn("PureSequence.stableSort", creator)
            self.assertIn("PureSequence.requireFinite", creator)
            self.assertIn("cursor >= 0", unity_helper)
            self.assertIn("cursor >= 0", creator_helper)
            self.assertIn("Non-finite Number", unity_helper)
            self.assertIn("Number.isFinite", creator_helper)

    def test_alias_uuid_comment_and_owner_names_do_not_select_semantics(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as a, tempfile.TemporaryDirectory(dir="/private/tmp") as b:
            left, _ = self._prepare(source_for("Rules", comment="asset 01234567-89ab-cdef-0123-456789abcdef"), Path(a).resolve())
            right, _ = self._prepare(source_for("RenamedOwner", comment="asset fedcba98-7654-3210-fedc-ba9876543210"), Path(b).resolve())
            left_code = (Path(a) / "candidate/Targets/Unity/Fixture/Domain/EntryRules.cs").read_bytes()
            right_code = (Path(b) / "candidate/Targets/Unity/Fixture/Domain/EntryRules.cs").read_bytes()
            self.assertEqual(left_code, right_code)
            self.assertNotEqual(left["manifest"]["method"]["methodId"], right["manifest"]["method"]["methodId"])
            self.assertNotEqual(left["manifest"]["source"]["sha256"], right["manifest"]["source"]["sha256"])
            self.assertEqual(left["manifest"]["semanticIrSha256"], right["manifest"]["semanticIrSha256"])

    def test_changed_threshold_and_sort_direction_follow_source_ast(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as a, tempfile.TemporaryDirectory(dir="/private/tmp") as b, tempfile.TemporaryDirectory(dir="/private/tmp") as c:
            ascending, _ = self._prepare(source_for(threshold="3"), Path(a).resolve())
            raised_threshold, _ = self._prepare(source_for(threshold="4"), Path(b).resolve())
            descending, _ = self._prepare(source_for(threshold="3", direction="descending"), Path(c).resolve())
            a_code = (Path(a) / "candidate/Targets/Unity/Fixture/Domain/EntryRules.cs").read_text()
            b_code = (Path(b) / "candidate/Targets/Unity/Fixture/Domain/EntryRules.cs").read_text()
            c_code = (Path(c) / "candidate/Targets/Unity/Fixture/Domain/EntryRules.cs").read_text()
            self.assertIn(">= 3.0d", a_code)
            self.assertIn(">= 4.0d", b_code)
            self.assertIn("* -1", c_code)
            self.assertNotEqual(ascending["manifest"]["semanticIrSha256"], raised_threshold["manifest"]["semanticIrSha256"])
            self.assertEqual(descending["ir"]["expression"]["comparator"]["direction"], "descending")

    def test_three_way_comparator_is_proved_and_emitted_in_both_directions(self):
        source = ("var R=(function(){function C(){} C.select=function(rows){return rows.filter(function(x){return x.active;})"
                  ".sort(function(a,b){return a.score<b.score?-1:a.score>b.score?1:0;});};return C;})();").encode()
        with tempfile.TemporaryDirectory(dir="/private/tmp") as tmp:
            result, _ = self._prepare(source, Path(tmp).resolve())
            self.assertEqual(result["ir"]["expression"]["comparator"]["form"], "three-way")
            code = (Path(tmp) / "candidate/Targets/Creator/Fixture/Domain/EntryRules.ts").read_text()
            self.assertIn('PureSequence.requireFinite(pureValue2.score, "sort key score") < PureSequence.requireFinite(pureValue3.score, "sort key score") ? -1', code)

    def test_unknown_calls_coercion_and_input_mutating_sort_are_rejected(self):
        cases = [
            (source_for().replace(b".sort(function(a,b){return a.score-b.score;});", b".map(function(x){return x;});"), "PURE_LOWERING_CALL"),
            (source_for().replace(b"row.score>=3", b"row.score>='3'"), "PURE_LOWERING_TYPE"),
            (b"var R=(function(){function C(){} C.select=function(rows){return rows.sort(function(a,b){return a.score-b.score;});};return C;})();", "PURE_LOWERING_SORT_MUTATION"),
            (source_for().replace(b"a.score-b.score", b"a.score-Math.floor(b.score)"), "PURE_LOWERING_SORT_COMPARATOR"),
        ]
        for raw, error_code in cases:
            with self.subTest(error_code=error_code), tempfile.TemporaryDirectory(dir="/private/tmp") as temp:
                root = Path(temp).resolve()
                source = root / "neutral.js"
                source.write_bytes(raw)
                method = facts(source, sha(raw))["methods"][0]
                with self.assertRaisesRegex(ParseError, error_code):
                    prepare_pure_lowering(source, {"classId": method["classId"], "methodId": method["id"]},
                                          contract(), root / "candidate", expected_source_sha256=sha(raw),
                                          namespace="Fixture.Domain", class_name="EntryRules", method_name="Select")

    def test_runtime_and_target_scope_remain_explicit(self):
        root = Path(__file__).resolve().parents[1]
        csharp = (root / "src/monkey/targets/pure_lowering/PureSequence.cs").read_text()
        creator = (root / "src/monkey/targets/pure_lowering/PureSequence.ts").read_text()
        self.assertIn("StableSort<T>", csharp)
        self.assertIn("static stableSort<T>", creator)
        self.assertIn("double.IsNaN", csharp)
        self.assertIn("double.IsInfinity", csharp)
        self.assertIn("Number.isFinite", creator)


if __name__ == "__main__":
    unittest.main()
