import hashlib
import json
import copy
import sys
import tempfile
import unittest
from types import ModuleType
from pathlib import Path
from unittest.mock import patch

from monkey.code_drafts import emit, prepare
from monkey.code_graph import draft_records as real_draft_records


class CodeDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.root = Path(self.temp.name)
        self.source = self.root / "source.js"
        self.source.write_text(
            "function first(x) { return x + 1; }\n"
            "function second(y) { return y - 1; }\n"
            "const VALUE = 5;\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def fake_symbols_module(self, calls):
        module = ModuleType("monkey.code_draft_symbols")
        class FakeDraftSymbols:
            def __init__(self, header, class_names, normalizer):
                calls.append(("init", header.get("draftDeclarations"), class_names))
            def target_name(self, row, kind="method"):
                result = f"Planned_{kind}_{row.get('id', 'unknown').replace('@', '_').replace(':', '_')}"
                calls.append(("name", kind, row.get("id"), result))
                return result
            def annotate(self, ast, method, captures=None):
                ast["plannerAnnotated"] = True
                ast["plannerCaptures"] = captures or []
                calls.append(("annotate", method.get("id"), captures or []))
                return ast
            def capture_parameters(self, method):
                return [{"bindingId": item["bindingId"], "sourceName": item.get("name"),
                         "targetName": "__capture_" + item["bindingId"].replace(":", "_")}
                        for item in method.get("captures", []) if isinstance(item, dict)]
            def summary(self):
                return {"planner": "fake", "calls": len(calls)}
        module.DraftSymbols = FakeDraftSymbols
        return module

    def stream(self, *, ast_null=False, field_ast_null=False, mutual_cycle=False):
        records = list(real_draft_records(self.source))
        header = records[0]
        header.pop("draftDeclarations", None)
        header.pop("draftFields", None)
        functions = [row for row in records if row.get("record") == "function"]
        classes = []
        for cid, name, binding, member in (
                ("class:one", "订单", "binding:one", "first"),
                ("class:two", "Caller", "binding:two", "second")):
            classes.append({"id": cid, "name": name, "bindingId": binding,
                "sourceBytes": {"start": 0, "end": 1}, "sourceSha256": "a" * 64,
                "methodBindings": [{"name": member}]})
        header["classes"] = classes
        header["summary"]["methods"] = len(functions)
        for i, row in enumerate(functions):
            method = row["method"]
            method["classId"] = "class:one" if i == 0 else "class:two"
            method["ownerBindingId"] = "binding:one" if i == 0 else "binding:two"
            row["kind"] = "indexed_method"
            if i == 1:
                method["calls"] = [{"receiver": "other", "bindingId": "binding:one", "member": "first"}]
            elif mutual_cycle:
                method["calls"] = [{"receiver": "other", "bindingId": "binding:two", "member": "second"}]
            if ast_null and i == 0:
                row["ast"] = None
                row["diagnostic"] = "test oversize AST fragment"
        value_offset = self.source.read_bytes().index(b"5")
        raw = self.source.read_bytes()
        field = {"record": "field", "field": {"id": "field:value", "name": "VALUE",
            "classId": "class:one", "ownerBindingId": "binding:one", "static": True,
            "sourceBytes": {"start": value_offset, "end": value_offset + 1},
            "sourceSha256": hashlib.sha256(raw[value_offset:value_offset + 1]).hexdigest()},
            "ast": {"type": "Literal", "value": 5, "start": value_offset, "end": value_offset + 1}}
        if field_ast_null:
            field["ast"] = None
        footer = next(row for row in records if row.get("record") == "footer")
        footer.update(functionsEmitted=len(functions), indexedMethods=len(functions),
                      classFactoriesFlattened=2, moduleContainersFlattened=3, staticFields=1, sourceExecuted=False)
        return [header, *functions, field, footer]

    def test_full_methods_fields_dependencies_and_pinyin_names(self):
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(self.stream())):
            prepared = prepare(self.source)
        report = prepared["report"]
        self.assertEqual(report["coverage"]["indexedMethodFunctionsEmitted"], 2)
        self.assertEqual(report["coverage"]["fieldRecords"], 1)
        self.assertEqual(report["coverage"]["classFactoriesFlattened"], 2)
        self.assertEqual(report["coverage"]["moduleContainersFlattened"], 3)
        self.assertEqual(report["fields"][0]["status"], "drafted")
        self.assertTrue(any("DingDan.cs" in path for path in prepared["files"]))
        cs = next(value.decode() for path, value in prepared["files"].items() if path.endswith("DingDan.cs"))
        self.assertIn("public dynamic First", cs)
        self.assertIn("public static dynamic VALUE = 5;", cs)
        caller = next(row for row in prepared["requests"] if any(
            item["sourceName"] == "second" for item in row["sourceMethodMappings"]))
        self.assertTrue(caller["dependencies"])

    def test_ast_null_fallback_preserves_function_excerpt_and_continues(self):
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(self.stream(ast_null=True))):
            prepared = prepare(self.source)
        first = next(row for row in prepared["report"]["functions"] if row["sourceName"] == "first")
        self.assertEqual(first["status"], "fallback_original_source_excerpt")
        draft = prepared["files"][first["targetPath"]].decode()
        self.assertIn("function first(x) { return x + 1; }", draft)
        self.assertEqual(prepared["report"]["coverage"]["indexedMethodFunctionsEmitted"], 2)
        self.assertEqual(prepared["report"]["coverage"]["methodsNotEmitted"], 0)

    def test_missing_field_ast_never_invents_a_default(self):
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(self.stream(field_ast_null=True))):
            prepared = prepare(self.source)
        field = prepared["report"]["fields"][0]
        self.assertEqual(field["status"], "fallback_initializer_in_source")
        draft = prepared["files"][field["targetPath"]].decode()
        self.assertIn("Field initializer AST unavailable", draft)
        self.assertNotIn("VALUE = 0", draft)

    def test_field_without_class_id_is_grouped_by_owner_binding(self):
        def records(_source):
            output = self.stream()
            field = next(row for row in output if row.get("record") == "field")
            field["field"]["classId"] = None
            field["field"]["ownerBindingId"] = "binding:orphan-field-owner"
            return iter(output)
        with patch("monkey.code_drafts.draft_records", side_effect=records):
            prepared = prepare(self.source)
        field = prepared["report"]["fields"][0]
        self.assertEqual(field["status"], "drafted")
        self.assertIn("Unresolved_", field["targetClass"])
        self.assertIn("public static dynamic VALUE = 5;", prepared["files"][field["targetPath"]].decode())

    def test_detailed_function_evidence_is_sharded_once(self):
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(self.stream())):
            prepared = prepare(self.source)
        report = prepared["report"]
        self.assertEqual(report["coverage"]["detailRecords"], 3)
        self.assertEqual(report["coverage"]["detailParts"], 1)
        self.assertNotIn("diagnostics", report["functions"][0])
        raw_report = prepared["files"][report["reportPath"]]
        self.assertLess(len(raw_report), 32 * 1024 * 1024)
        self.assertNotIn(b"\n", raw_report)
        shard_path = report["functions"][0]["detailsPath"]
        shard = json.loads(prepared["files"][shard_path])
        self.assertEqual(len(shard["records"]), 3)
        self.assertIn("diagnostics", shard["records"][0])

    def test_runtime_field_write_is_not_promoted_to_initializer(self):
        source = self.root / "runtime.js"
        source.write_text("function write() { this.VALUE = 5; }\n", encoding="utf-8")
        records = list(real_draft_records(source))
        records[0].pop("draftDeclarations", None)
        records[0].pop("draftFields", None)
        function = next(row for row in records if row.get("record") == "function")
        function["method"]["ownerBindingId"] = "binding:runtime"
        field_start = source.read_bytes().index(b"5")
        raw = source.read_bytes()
        field = {"record": "field", "field": {"id": "field:runtime-value", "name": "VALUE",
            "ownerBindingId": "binding:runtime", "static": True, "initializationContext": "runtime_write",
            "sourceBytes": {"start": field_start, "end": field_start + 1},
            "sourceSha256": hashlib.sha256(raw[field_start:field_start + 1]).hexdigest()},
            "ast": {"type": "Literal", "value": 5, "start": field_start, "end": field_start + 1}}
        footer = next(row for row in records if row.get("record") == "footer")
        footer["staticFields"] = 1
        records.insert(-1, field)
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(records)):
            prepared = prepare(source)
        report_field = prepared["report"]["fields"][0]
        self.assertEqual(report_field["status"], "runtime_write_preserved_in_method")
        self.assertEqual(prepared["report"]["coverage"]["runtimeFieldWrites"], 1)
        self.assertEqual(prepared["report"]["coverage"]["fieldsWithInitializers"], 0)
        draft = prepared["files"][report_field["targetPath"]].decode()
        self.assertIn("dynamic VALUE;", draft)
        self.assertNotIn("dynamic VALUE = 5;", draft)
        self.assertIn("(this).VALUE = 5;", draft)
        function_report = prepared["report"]["functions"][0]
        function_detail = json.loads(prepared["files"][function_report["detailsPath"]])["records"][function_report["detailsIndex"]]
        span = function_detail["sourceBytes"]
        self.assertIn(b"this.VALUE = 5", source.read_bytes()[span["start"]:span["end"]])
        field_detail = json.loads(prepared["files"][report_field["detailsPath"]])["records"][report_field["detailsIndex"]]
        self.assertIn("runtime_field_write_not_promoted", field_detail["diagnostics"][0]["code"])

    def test_duplicate_initializers_declare_once_and_keep_source_order(self):
        source = self.root / "duplicate-fields.js"
        source.write_text("const A = 1;\nconst B = A;\nconst A = 2;\n", encoding="utf-8")
        raw = source.read_bytes()
        header = {"record": "header", "source": {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)},
            "sourceExecuted": False, "summary": {"methods": 0},
            "classes": [{"id": "class:fields", "name": "Fields", "bindingId": "binding:fields",
                "sourceBytes": {"start": 0, "end": len(raw)}, "sourceSha256": hashlib.sha256(raw).hexdigest()}]}
        fields = []
        specs = [("a-first", "A", b"1", {"type": "Literal", "value": 1}),
                 ("b-middle", "B", b"A", {"type": "Identifier", "name": "A"}),
                 ("a-last", "A", b"2", {"type": "Literal", "value": 2})]
        for index, (label, name, value, expression) in enumerate(specs):
            start = raw.index(value, 0 if index == 0 else raw.index(b"\n", fields[-1]["field"]["sourceBytes"]["start"]) + 1)
            expression = dict(expression, start=start, end=start + len(value))
            fields.append({"record": "field", "field": {"id": f"field:{label}", "name": name,
                "classId": "class:fields", "ownerBindingId": "binding:fields", "static": True,
                "initializationContext": "class_factory", "sourceBytes": {"start": start, "end": start + 1},
                "sourceSha256": hashlib.sha256(raw[start:start + 1]).hexdigest()},
                "ast": expression})
        footer = {"record": "footer", "sourceExecuted": False, "functionsEmitted": 0,
            "indexedMethods": 0, "staticFields": 3, "classFactoriesFlattened": 0, "moduleContainersFlattened": 0}
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter([header, *fields, footer])):
            prepared = prepare(source)
        path = prepared["report"]["fields"][0]["targetPath"]
        draft = prepared["files"][path].decode()
        self.assertEqual(draft.count("dynamic A;"), 1)
        self.assertEqual(draft.count("dynamic B;"), 1)
        self.assertIn("static Fields()", draft)
        self.assertLess(draft.index("A = 1;"), draft.index("B = A;"))
        self.assertLess(draft.index("B = A;"), draft.index("A = 2;"))
        self.assertEqual(prepared["report"]["coverage"]["fieldDeclarations"], 2)
        self.assertEqual(prepared["report"]["coverage"]["fieldInitializers"], 3)
        self.assertTrue(all(row["status"] == "initialized_in_static_constructor" for row in prepared["report"]["fields"]))

    def test_distinct_source_names_that_normalize_together_get_stable_names(self):
        source = self.root / "case-collision.js"
        source.write_text("const foo = 1;\nconst Foo = 2;\n", encoding="utf-8")
        raw = source.read_bytes()
        header = {"record": "header", "source": {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)},
            "sourceExecuted": False, "summary": {"methods": 0}, "classes": [{"id": "class:fields",
            "name": "Fields", "bindingId": "binding:fields", "sourceBytes": {"start": 0, "end": len(raw)},
            "sourceSha256": hashlib.sha256(raw).hexdigest()}]}
        fields = []
        for index, (name, value) in enumerate((("foo", b"1"), ("Foo", b"2"))):
            start = raw.index(value, 0 if index == 0 else raw.index(b"\n") + 1)
            fields.append({"record": "field", "field": {"id": f"field:{index}", "name": name,
                "classId": "class:fields", "ownerBindingId": "binding:fields", "static": True,
                "initializationContext": "module", "sourceBytes": {"start": start, "end": start + 1},
                "sourceSha256": hashlib.sha256(raw[start:start + 1]).hexdigest()},
                "ast": {"type": "Literal", "value": index + 1, "start": start, "end": start + 1}})
        footer = {"record": "footer", "sourceExecuted": False, "functionsEmitted": 0,
            "indexedMethods": 0, "staticFields": 2}
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter([header, *fields, footer])):
            prepared = prepare(source)
        rows = prepared["report"]["fields"]
        self.assertEqual(len({row["targetMember"] for row in rows}), 2)
        self.assertTrue(all(any(item["code"] == "field_name_normalization_collision" for item in
            json.loads(prepared["files"][row["detailsPath"]])["records"][row["detailsIndex"]]["diagnostics"])
            for row in rows))
        draft = prepared["files"][rows[0]["targetPath"]].decode()
        self.assertIn(rows[0]["targetMember"] + " =", draft)
        self.assertIn(rows[1]["targetMember"] + " =", draft)

    def test_preplanned_names_and_embedded_function_mapping(self):
        records = self.stream()
        header = records[0]
        functions = [row for row in records if row.get("record") == "function"]
        outer, nested = functions
        outer["method"]["name"] = "outer"
        nested["method"]["name"] = "inner"
        nested["kind"] = "auxiliary_function"
        nested["method"]["parentFunctionId"] = outer["method"]["id"]
        nested["method"]["captures"] = [{"bindingId": "binding:captured", "name": "captured"}]
        header["draftDeclarations"] = [dict(row["method"], kind=row["kind"]) for row in functions]
        header["summary"]["methods"] = 1
        footer = next(row for row in records if row.get("record") == "footer")
        footer["indexedMethods"] = 1
        embedded_marker = "/* source-function:" + nested["method"]["id"] + " */"
        planner_calls, rendered_calls = [], []
        fake_module = self.fake_symbols_module(planner_calls)
        def render(method, ast, raw, *, class_name=None):
            self.assertTrue(ast.get("plannerAnnotated"))
            rendered_calls.append(method["id"])
            return {"source": f"public dynamic {method['targetName']}() {{ {embedded_marker} return 0; }}",
                "usings": [], "diagnostics": [], "approximateTypes": [], "members": [],
                "emittedName": method["targetName"],
                "embeddedFunctions": ([{"id": nested["method"]["id"], "marker": embedded_marker}]
                    if method["id"] == outer["method"]["id"] else []),
                "sourceExecuted": False, "draftOnly": True}
        with patch.dict(sys.modules, {"monkey.code_draft_symbols": fake_module}):
            with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(records)):
                with patch("monkey.code_draft_render.render_method", side_effect=render):
                    prepared = prepare(self.source)
        self.assertEqual(rendered_calls, [outer["method"]["id"]])
        nested_report = next(row for row in prepared["report"]["functions"] if row["methodId"] == nested["method"]["id"])
        self.assertEqual(nested_report["status"], "embedded_in_owner")
        self.assertEqual(nested_report["targetLocationMarker"], embedded_marker)
        self.assertEqual(nested_report["targetPath"], next(row for row in prepared["report"]["functions"]
            if row["methodId"] == outer["method"]["id"])["targetPath"])
        self.assertEqual(prepared["report"]["coverage"]["auxiliaryFunctionsEmbedded"], 1)
        self.assertEqual(prepared["report"]["coverage"]["auxiliaryFunctionsExtracted"], 0)
        self.assertTrue(prepared["report"]["draftSymbols"]["planner"] == "fake")
        self.assertTrue(any(call[0] == "name" and call[1] == "method" for call in planner_calls))
        self.assertTrue(any(call[0] == "name" and call[1] == "field" for call in planner_calls))

    def test_missing_embedded_marker_does_not_claim_nested_mapping(self):
        records = self.stream()
        header = records[0]
        outer, nested = [row for row in records if row.get("record") == "function"]
        nested["kind"] = "auxiliary_function"
        nested["method"]["parentFunctionId"] = outer["method"]["id"]
        header["draftDeclarations"] = [dict(row["method"], kind=row["kind"]) for row in (outer, nested)]
        header["summary"]["methods"] = 1
        footer = next(row for row in records if row.get("record") == "footer")
        footer["indexedMethods"] = 1
        marker = "/* source-function:" + nested["method"]["id"] + " */"
        fake_module = self.fake_symbols_module([])

        def render(method, ast, raw, *, class_name=None):
            # Deliberately lie in renderer metadata: the marker is absent from source.
            return {"source": f"public dynamic {method['targetName']}() {{ return 0; }}",
                "usings": [], "diagnostics": [], "approximateTypes": [], "members": [],
                "emittedName": method["targetName"],
                "embeddedFunctions": ([{"id": nested["method"]["id"], "marker": marker}]
                    if method["id"] == outer["method"]["id"] else []),
                "sourceExecuted": False, "draftOnly": True}

        with patch.dict(sys.modules, {"monkey.code_draft_symbols": fake_module}):
            with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(records)):
                with patch("monkey.code_draft_render.render_method", side_effect=render):
                    prepared = prepare(self.source)
        nested_report = next(row for row in prepared["report"]["functions"]
                             if row["methodId"] == nested["method"]["id"])
        self.assertNotEqual(nested_report["status"], "embedded_in_owner")
        self.assertIsNone(nested_report.get("targetLocationMarker"))
        self.assertEqual(prepared["report"]["coverage"]["indexedMethodFunctionsEmitted"], 1)
        self.assertEqual(prepared["report"]["coverage"]["embeddedFunctionsMapped"], 0)

    def test_repeated_embedded_id_uses_narrowest_indexed_owner(self):
        records = self.stream()
        header = records[0]
        first, second = [row for row in records if row.get("record") == "function"]
        nested = copy.deepcopy(second)
        first["kind"] = second["kind"] = "indexed_method"
        first["method"].update(name="wideOwner", sourceBytes={"start": 0, "end": 120})
        second["method"].update(name="nestedIndexedOwner", sourceBytes={"start": 20, "end": 55})
        nested["kind"] = "auxiliary_function"
        nested["method"].update(id="function:nested-callback", name="callback",
            parentFunctionId=second["method"]["id"], sourceBytes={"start": 40, "end": 50})
        marker = "/* source-function:" + nested["method"]["id"] + " */"
        header["draftDeclarations"] = [dict(row["method"], kind=row["kind"])
            for row in (first, second, nested)]
        header["summary"]["methods"] = 2
        footer = next(row for row in records if row.get("record") == "footer")
        footer["functionsEmitted"] = 3
        footer["indexedMethods"] = 2
        records.insert(records.index(footer), nested)
        fake_module = self.fake_symbols_module([])

        def render(method, ast, raw, *, class_name=None):
            embeds = method["id"] != nested["method"]["id"]
            return {"source": f"public dynamic {method['targetName']}() {{ "
                    f"{marker if embeds else ''} return 0; }}",
                "usings": [], "diagnostics": [], "approximateTypes": [], "members": [],
                "emittedName": method["targetName"],
                "embeddedFunctions": ([{"id": nested["method"]["id"], "marker": marker}] if embeds else []),
                "sourceExecuted": False, "draftOnly": True}

        with patch.dict(sys.modules, {"monkey.code_draft_symbols": fake_module}):
            with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(records)):
                with patch("monkey.code_draft_render.render_method", side_effect=render):
                    prepared = prepare(self.source)
        nested_report = next(row for row in prepared["report"]["functions"]
                             if row["methodId"] == nested["method"]["id"])
        second_report = next(row for row in prepared["report"]["functions"]
                             if row["methodId"] == second["method"]["id"])
        self.assertEqual(nested_report["status"], "embedded_in_owner")
        self.assertEqual(nested_report["targetMethod"], second_report["targetMethod"])
        self.assertEqual(nested_report["targetLocationMarker"], marker)
        self.assertEqual(prepared["report"]["coverage"]["indexedMethodFunctionsEmitted"], 2)
        self.assertEqual(prepared["report"]["coverage"]["embeddedFunctionsMapped"], 1)

    def test_real_nested_indexed_method_callback_maps_to_narrow_owner(self):
        self.source.write_text(
            "var Outer=(function(){function C(){};"
            "C.outer=function(){C.inner=function(){"
            "return function cb(){return 1;};};};return C;})();",
            encoding="utf-8")
        prepared = prepare(self.source)
        rows = prepared["report"]["functions"]
        inner = next(row for row in rows if row["sourceName"] == "inner")
        callback = next(row for row in rows if row["sourceName"] == "cb")
        self.assertEqual(inner["kind"], "indexed_method")
        self.assertEqual(callback["status"], "embedded_in_owner")
        self.assertEqual(callback["targetMethod"], inner["targetMethod"])
        self.assertEqual(callback["targetPath"], inner["targetPath"])
        self.assertTrue(callback["targetLocationMarker"] in prepared["files"][callback["targetPath"]].decode())

    def test_duplicate_embedded_id_in_one_render_is_rejected_as_embedding(self):
        records = self.stream()
        header = records[0]
        first, nested = [row for row in records if row.get("record") == "function"]
        nested["kind"] = "auxiliary_function"
        nested["method"]["parentFunctionId"] = first["method"]["id"]
        header["draftDeclarations"] = [dict(row["method"], kind=row["kind"]) for row in (first, nested)]
        header["summary"]["methods"] = 1
        footer = next(row for row in records if row.get("record") == "footer")
        footer["indexedMethods"] = 1
        marker = "/* source-function:" + nested["method"]["id"] + " */"
        fake_module = self.fake_symbols_module([])

        def render(method, ast, raw, *, class_name=None):
            return {"source": f"public dynamic {method['targetName']}() {{ {marker} return 0; }}",
                "usings": [], "diagnostics": [], "approximateTypes": [], "members": [],
                "emittedName": method["targetName"],
                "embeddedFunctions": ([{"id": nested["method"]["id"], "marker": marker}] * 2
                    if method["id"] == first["method"]["id"] else []),
                "sourceExecuted": False, "draftOnly": True}

        with patch.dict(sys.modules, {"monkey.code_draft_symbols": fake_module}):
            with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(records)):
                with patch("monkey.code_draft_render.render_method", side_effect=render):
                    prepared = prepare(self.source)
        nested_report = next(row for row in prepared["report"]["functions"]
                             if row["methodId"] == nested["method"]["id"])
        self.assertNotEqual(nested_report["status"], "embedded_in_owner")
        self.assertEqual(prepared["report"]["coverage"]["embeddedFunctionsMapped"], 0)

    def test_embedded_counts_are_per_owner_class_and_indexed_mappings_are_exact(self):
        prepared = prepare(self.source)
        report = prepared["report"]
        coverage = report["coverage"]
        indexed_rows = [row for row in report["functions"] if row["kind"] == "indexed_method"]
        embedded_rows = [row for row in report["functions"] if row["status"] == "embedded_in_owner"]
        self.assertEqual(coverage["indexedMethodFunctionsEmitted"], len(indexed_rows))
        self.assertEqual(coverage["embeddedFunctionsMapped"], len(embedded_rows))
        self.assertEqual(sum(row["embeddedFunctionCount"] for row in report["classes"]), len(embedded_rows))

    def test_unembedded_nested_function_gets_capture_parameters(self):
        records = self.stream()
        header = records[0]
        outer, nested = [row for row in records if row.get("record") == "function"]
        nested["kind"] = "auxiliary_function"
        nested["method"]["parentFunctionId"] = outer["method"]["id"]
        nested["method"]["captures"] = [{"bindingId": "binding:captured", "name": "captured"}]
        header["draftDeclarations"] = [dict(row["method"], kind=row["kind"]) for row in (outer, nested)]
        header["summary"]["methods"] = 1
        footer = next(row for row in records if row.get("record") == "footer")
        footer["indexedMethods"] = 1
        planner_calls, renderer_inputs = [], []
        fake_module = self.fake_symbols_module(planner_calls)
        def render(method, ast, raw, *, class_name=None):
            renderer_inputs.append(method)
            return {"source": f"public dynamic {method['targetName']}() {{ return 0; }}",
                "usings": [], "diagnostics": [], "approximateTypes": [], "members": [],
                "emittedName": method["targetName"], "embeddedFunctions": [],
                "sourceExecuted": False, "draftOnly": True}
        with patch.dict(sys.modules, {"monkey.code_draft_symbols": fake_module}):
            with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(records)):
                with patch("monkey.code_draft_render.render_method", side_effect=render):
                    prepared = prepare(self.source)
        nested_input = next(row for row in renderer_inputs if row["id"] == nested["method"]["id"])
        self.assertTrue(next(row for row in records if row.get("record") == "function" and
            row["method"]["id"] == nested["method"]["id"])["ast"].get("plannerAnnotated"))
        self.assertEqual(nested_input["captureParameters"][0]["bindingId"], "binding:captured")
        nested_report = next(row for row in prepared["report"]["functions"] if row["methodId"] == nested["method"]["id"])
        self.assertEqual(nested_report["status"], "extracted_with_capture_parameters")
        self.assertFalse(nested_report["captureCallSitesRewritten"])
        self.assertEqual(prepared["report"]["coverage"]["auxiliaryFunctionsExtractedWithCaptures"], 1)
        shard = json.loads(prepared["files"][nested_report["detailsPath"]])["records"][nested_report["detailsIndex"]]
        self.assertTrue(any(row["code"] == "capture_parameter_callsite_unwired" for row in shard["diagnostics"]))

    def test_real_symbol_planner_filters_owner_capture_from_parameters(self):
        records = self.stream()
        header = records[0]
        functions = [row for row in records if row.get("record") == "function"]
        outer, nested = functions
        outer["kind"] = "indexed_method"
        nested["kind"] = "auxiliary_function"
        outer["method"]["static"] = True
        nested["method"]["parentFunctionId"] = outer["method"]["id"]
        nested["method"]["captures"] = [
            {"bindingId": "binding:one", "name": "Owner"},
            {"bindingId": "local:capture", "name": "captured"}]
        captured_identifier = {"type": "Identifier", "name": "captured", "bindingId": "local:capture"}
        owner_identifier = {"type": "Identifier", "name": "Owner", "bindingId": "binding:one"}
        member_node = {"type": "MemberExpression", "computed": False,
            "object": {"type": "Identifier", "name": "Owner", "bindingId": "binding:one"},
            "property": {"type": "Identifier", "name": "first"}}
        nested["ast"] = {"type": "FunctionExpression", "params": [], "body": {"type": "BlockStatement",
            "body": [{"type": "ExpressionStatement", "expression": captured_identifier},
                     {"type": "ExpressionStatement", "expression": owner_identifier},
                     {"type": "ExpressionStatement", "expression": member_node}]}}
        header["draftDeclarations"] = [dict(row["method"], kind=row["kind"]) for row in functions]
        header["draftFields"] = [next(row["field"] for row in records if row.get("record") == "field")]
        header["summary"]["methods"] = 1
        footer = next(row for row in records if row.get("record") == "footer")
        footer["indexedMethods"] = 1
        renderer_inputs = []
        def render(method, ast, raw, *, class_name=None):
            renderer_inputs.append(method)
            return {"source": f"public dynamic {method['targetName']}() {{ return 0; }}",
                "usings": [], "diagnostics": [], "approximateTypes": [], "members": [],
                "emittedName": method["targetName"], "embeddedFunctions": [],
                "sourceExecuted": False, "draftOnly": True}
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(records)):
            with patch("monkey.code_draft_render.render_method", side_effect=render):
                prepared = prepare(self.source)
        nested_input = next(row for row in renderer_inputs if row["id"] == nested["method"]["id"])
        self.assertEqual([row["bindingId"] for row in nested_input["captureParameters"]], ["local:capture"])
        self.assertEqual(captured_identifier["_draftIdentifierTarget"], nested_input["captureParameters"][0]["targetName"])
        self.assertEqual(owner_identifier["_draftIdentifierTarget"], "DingDan")
        self.assertEqual(member_node["_draftMember"]["sourceDeclarationId"], outer["method"]["id"])
        self.assertEqual(member_node["_draftMember"]["receiver"], "static_owner")
        nested_report = next(row for row in prepared["report"]["functions"] if row["methodId"] == nested["method"]["id"])
        self.assertEqual(nested_report["status"], "extracted_with_capture_parameters")
        self.assertTrue(prepared["report"]["draftSymbols"]["counts"]["plannedDeclarations"] >= 3)

    def test_real_nested_function_is_mapped_to_embedded_owner(self):
        source = self.root / "nested.js"
        source.write_text("function outer(x) { function inner(y) { return x + y; } return inner(1); }\n",
                          encoding="utf-8")
        prepared = prepare(source)
        report = prepared["report"]
        self.assertEqual(report["coverage"]["functionsEmitted"], 2)
        self.assertEqual(report["coverage"]["functionsMapped"], 2)
        self.assertEqual(report["coverage"]["auxiliaryFunctionsEmbedded"], 1)
        inner = next(row for row in report["functions"] if row["sourceName"] == "inner")
        self.assertEqual(inner["status"], "embedded_in_owner")
        self.assertEqual(inner["capturedBindings"][0]["name"], "x")
        self.assertEqual(inner["targetPath"], next(row for row in report["functions"]
            if row["sourceName"] == "outer")["targetPath"])
        source_text = source.read_bytes()[inner["sourceBytes"]["start"]:inner["sourceBytes"]["end"]]
        self.assertEqual(hashlib.sha256(source_text).hexdigest(), inner["sourceSha256"])
        generated = prepared["files"][inner["targetPath"]].decode()
        self.assertIn(inner["targetLocationMarker"], generated)

    def test_real_static_stream_and_stable_prepare(self):
        source = self.root / "plain.js"
        source.write_text("function alpha(x) { return x + 1; }\n", encoding="utf-8")
        def legacy_stream(path):
            for row in real_draft_records(path):
                if row.get("record") == "header":
                    row.pop("draftDeclarations", None)
                    row.pop("draftFields", None)
                yield row
        with patch("monkey.code_drafts.draft_records", side_effect=legacy_stream):
            a = prepare(source)
        with patch("monkey.code_drafts.draft_records", side_effect=legacy_stream):
            b = prepare(source)
        self.assertEqual(a["files"], b["files"])
        report = a["report"]
        self.assertEqual(report["coverage"]["functionsEmitted"], 1)
        self.assertEqual(report["coverage"]["auxiliaryFunctionsEmitted"], 1)
        self.assertFalse(report["sourceExecuted"])

    def test_source_hash_guard_and_fresh_candidate_reuse(self):
        with self.assertRaises(Exception):
            prepare(self.source, "0" * 64)
        first = self.root / "candidate-a"
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(self.stream())):
            result = emit(self.source, first)
        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        manifest_sha = hashlib.sha256(Path(result["manifest"]).read_bytes()).hexdigest()
        second = self.root / "candidate-b"
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(self.stream())):
            reused = emit(self.source, second, reuse_from=first, expected_manifest_sha256=manifest_sha)
        self.assertEqual(reused["status"], "drafts_emitted")
        self.assertTrue(all(row["action"] == "reuse" for row in reused["regeneration"].values()))
        for entry in manifest["files"]:
            self.assertEqual((first / entry["path"]).read_bytes(), (second / entry["path"]).read_bytes())

    def test_dirty_owned_file_blocks_reuse(self):
        first = self.root / "candidate-dirty"
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(self.stream())):
            result = emit(self.source, first)
        manifest_path = Path(result["manifest"])
        manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        owned = json.loads(manifest_path.read_text(encoding="utf-8"))["files"][0]["path"]
        (first / owned).write_bytes(b"changed")
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(self.stream())):
            with self.assertRaises(Exception):
                emit(self.source, self.root / "candidate-blocked", reuse_from=first,
                     expected_manifest_sha256=manifest_sha)

    def test_mutual_call_cycle_does_not_block_full_source_emit(self):
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(self.stream(mutual_cycle=True))):
            result = emit(self.source, self.root / "candidate-cycle")
        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["scopeMode"], "whole-input")
        self.assertTrue(manifest["sourceDependencyDiagnostics"])
        self.assertTrue(all(not row["dependencies"] for row in manifest["codeModules"]))
        self.assertTrue(any(row["dependencies"] for row in manifest["sourceDependencies"]))
        self.assertEqual(result["coverage"]["indexedMethodFunctionsEmitted"], 2)
        original_manifest_sha = hashlib.sha256(Path(result["manifest"]).read_bytes()).hexdigest()
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(self.stream(mutual_cycle=True))):
            reused = emit(self.source, self.root / "candidate-cycle-reuse", reuse_from=result["candidate"],
                expected_manifest_sha256=original_manifest_sha)
        self.assertTrue(all(row["action"] == "reuse" for row in reused["regeneration"].values()))
        first_owned = manifest["files"][0]["path"]
        (Path(result["candidate"]) / first_owned).write_bytes(b"tampered")
        with patch("monkey.code_drafts.draft_records", side_effect=lambda _source: iter(self.stream(mutual_cycle=True))):
            with self.assertRaises(Exception):
                emit(self.source, self.root / "candidate-cycle-blocked", reuse_from=result["candidate"],
                    expected_manifest_sha256=original_manifest_sha)


if __name__ == "__main__":
    unittest.main()
