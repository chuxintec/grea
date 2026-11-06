import unittest
import tempfile
import hashlib
from pathlib import Path
from unittest.mock import patch

from monkey.code_graph import facts
from monkey.code_draft_render import render_field, render_method


def n(node_type, **values):
    return {"type": node_type, **values}


def ident(name):
    return n("Identifier", name=name)


class CodeDraftRenderTests(unittest.TestCase):
    def test_collection_constructors_retain_values_length_and_set_receiver(self):
        raw = b"new Array(3); new Array('x'); new Set([this.id]); new Map([[\"k\", this.id]]);"
        def new(name, args):
            return n("NewExpression", callee=ident(name), arguments=args)
        array_length = render_method({"name": "length", "sourceBytes": {"start": 0, "end": len(raw)}},
            n("FunctionExpression", params=[], body=n("BlockStatement", body=[n("ReturnStatement", argument=new("Array", [n("Literal", value=3)]))])), raw)
        self.assertIn("__draftArrayArg = 3", array_length["source"])
        self.assertIn("Enumerable.Repeat<dynamic>(null, (int)__draftArrayLength)", array_length["source"])
        self.assertIn("System.Linq", array_length["usings"])
        array_value = render_method({"name": "value", "sourceBytes": {"start": 0, "end": len(raw)}},
            n("FunctionExpression", params=[], body=n("BlockStatement", body=[n("ReturnStatement", argument=new("Array", [n("Literal", value="x")]))])), raw)
        self.assertIn('new System.Collections.Generic.List<dynamic> { __draftArrayArg }', array_value["source"])
        set_value = render_method({"name": "set", "sourceBytes": {"start": 0, "end": len(raw)}},
            n("FunctionExpression", params=[], body=n("BlockStatement", body=[n("ReturnStatement", argument=new("Set", [n("ArrayExpression", elements=[n("MemberExpression", computed=False, object=n("ThisExpression"), property=ident("id"))])]))])), raw)
        self.assertIn("(this).id", set_value["source"])
        self.assertIn("__draftSet.Add(__draftSetItem)", set_value["source"])
        map_value = render_method({"name": "map", "sourceBytes": {"start": 0, "end": len(raw)}},
            n("FunctionExpression", params=[], body=n("BlockStatement", body=[n("ReturnStatement", argument=new("Map", [n("ArrayExpression", elements=[n("ArrayExpression", elements=[n("Literal", value="k"), n("MemberExpression", computed=False, object=n("ThisExpression"), property=ident("id"))])])]))])), raw)
        self.assertIn('__draftMap[__draftPair[0]] = __draftPair[1]', map_value["source"])
        self.assertIn("(this).id", map_value["source"])

    def test_unknown_collection_shape_evaluates_every_argument_before_throw(self):
        raw = b"new Map(first(), second());"
        call = lambda name: n("CallExpression", callee=ident(name), arguments=[])
        expr = n("NewExpression", callee=ident("Map"), arguments=[call("first"), call("second")])
        result = render_method({"name": "unknownMap", "sourceBytes": {"start": 0, "end": len(raw)}},
            n("FunctionExpression", params=[], body=n("BlockStatement", body=[n("ReturnStatement", argument=expr)])), raw)
        code = result["source"]
        self.assertLess(code.index("__draftArg0 = first()"), code.index("__draftArg1 = second()"))
        self.assertLess(code.index("__draftArg1 = second()"), code.index("Unsupported Map constructor shape"))
        self.assertIn("unknown_collection_constructor_shape", {d["code"] for d in result["diagnostics"]})

    def test_injected_identifier_and_member_targets_preserve_receiver_and_report_unknown(self):
        raw = b"return source.old + Old.staticField + source['old'] + source.unknown;"
        source_member = n("MemberExpression", computed=False, object=ident("source"), property=ident("old"),
                          _draftMember={"name": "newName", "ownerClass": "Thing", "receiver": "source"})
        static_member = n("MemberExpression", computed=False, object=ident("Old"), property=ident("staticField"),
                          _draftMember={"name": "Mapped", "ownerClass": "Domain.Thing", "receiver": "static_owner"})
        computed_member = n("MemberExpression", computed=True, object=ident("source"), property=n("Literal", value="old"),
                            _draftMember={"name": "newName", "ownerClass": "Thing", "receiver": "source"})
        unresolved = n("MemberExpression", computed=False, object=ident("source"), property=ident("unknown"),
                       _draftUnresolvedMember={"reason": "no owner binding"})
        ast = n("FunctionExpression", params=[n("Identifier", name="oldParam", bindingId="local-1", _draftIdentifierTarget="renamed")], body=n("BlockStatement", body=[
            n("ReturnStatement", argument=n("BinaryExpression", operator="+", left=source_member,
                right=n("BinaryExpression", operator="+", left=static_member, right=n("BinaryExpression", operator="+", left=computed_member, right=unresolved))))]))
        result = render_method({"name": "mapMembers", "static": True, "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        code = result["source"]
        self.assertIn("(source).newName", code)
        self.assertIn("Domain.Thing.Mapped", code)
        self.assertIn("(source).unknown", code)
        self.assertIn("unresolved_member_mapping", {d["code"] for d in result["diagnostics"]})
        self.assertNotIn("static_this_approximation", {d["code"] for d in result["diagnostics"]})
        self.assertIn("dynamic renamed", code)

    def test_nested_function_marker_and_capture_parameters_are_reported(self):
        raw = b"function outer(value){ return x => value + x; }"
        lambda_ast = n("ArrowFunctionExpression", draftFunctionId="function@42", params=[ident("x")],
                       body=n("BinaryExpression", operator="+", left=n("Identifier", name="value", bindingId="capture-1", _draftIdentifierTarget="capturedValue"), right=ident("x")))
        ast = n("FunctionExpression", params=[ident("value")], body=n("BlockStatement", body=[n("ReturnStatement", argument=lambda_ast)]))
        result = render_method({"name": "outer", "sourceBytes": {"start": 0, "end": len(raw)},
                               "captureParameters": [{"bindingId": "b1", "targetName": "capturedValue"}, {"bindingId": "b2", "targetName": "capturedValue"}]}, ast, raw)
        self.assertIn("/* source-function:function@42 */", result["source"])
        self.assertIn("dynamic capturedValue", result["source"])
        self.assertEqual(["function@42"], [row["id"] for row in result["embeddedFunctions"]])
        self.assertNotIn("method@", str(result["embeddedFunctions"]))

    def test_function_declaration_marker_and_shadowed_collection_name(self):
        raw = b"function outer(){ function inner(){ return 1; } return Array(); }"
        inner = n("FunctionDeclaration", draftFunctionId="method@91", id=ident("inner"), params=[],
                  body=n("BlockStatement", body=[n("ReturnStatement", argument=n("Literal", value=1))]))
        shadowed = n("NewExpression", callee=n("Identifier", name="Array", bindingId="local-array"), arguments=[])
        ast = n("FunctionExpression", params=[], body=n("BlockStatement", body=[
            inner, n("ReturnStatement", argument=shadowed)
        ]))
        result = render_method({"name": "outer", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        self.assertIn("/* source-function:method@91 */", result["source"])
        self.assertIn("new Array()", result["source"])
        self.assertEqual(["method@91"], [row["id"] for row in result["embeddedFunctions"]])

    def test_map_and_set_null_sources_evaluate_once_and_return_empty_collections(self):
        raw = b"new Map(getSource()); new Set(getSource());"
        source_call = lambda: n("CallExpression", callee=ident("getSource"), arguments=[])
        map_expr = n("NewExpression", callee=ident("Map"), arguments=[source_call()])
        set_expr = n("NewExpression", callee=ident("Set"), arguments=[source_call()])
        ast = n("FunctionExpression", params=[], body=n("BlockStatement", body=[
            n("ExpressionStatement", expression=map_expr), n("ReturnStatement", argument=set_expr)
        ]))
        result = render_method({"name": "nullCollections", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        code = result["source"]
        self.assertIn("__draftMapSource = getSource()", code)
        self.assertIn("if (__draftMapSource == null) return __draftMap", code)
        self.assertIn("__draftSetSource = getSource()", code)
        self.assertIn("if (__draftSetSource == null) return __draftSet", code)
        self.assertEqual(2, code.count("getSource()"))

    def test_ambiguous_global_names_are_not_lowered_as_builtins(self):
        raw = b"undefined; NaN; Infinity; new Array(2); Math.max(1,2); cc.log('x');"
        def ambiguous(name):
            return n("Identifier", name=name, bindingAmbiguous=True)
        math_max = n("CallExpression", callee=n("MemberExpression", computed=False, object=ambiguous("Math"), property=ident("max")),
                     arguments=[n("Literal", value=1), n("Literal", value=2)])
        cc_log = n("CallExpression", callee=n("MemberExpression", computed=False, object=ambiguous("cc"), property=ident("log")),
                   arguments=[n("Literal", value="x")])
        ast = n("FunctionExpression", params=[], body=n("BlockStatement", body=[
            n("ExpressionStatement", expression=ambiguous("undefined")),
            n("ExpressionStatement", expression=ambiguous("NaN")),
            n("ExpressionStatement", expression=ambiguous("Infinity")),
            n("ExpressionStatement", expression=n("NewExpression", callee=ambiguous("Array"), arguments=[n("Literal", value=2)])),
            n("ExpressionStatement", expression=math_max), n("ExpressionStatement", expression=cc_log),
        ]))
        result = render_method({"name": "ambiguous", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        code = result["source"]
        self.assertIn("dynamic __draftDiscard0 = undefined;", code)
        self.assertIn("dynamic __draftDiscard1 = NaN;", code)
        self.assertIn("dynamic __draftDiscard2 = Infinity;", code)
        self.assertIn("new Array(2)", code)
        self.assertIn("(Math).max(1, 2)", code)
        self.assertIn("(cc).log(\"x\")", code)
        self.assertNotIn("double.NaN", code)
        self.assertNotIn("UnityEngine.Debug.Log", code)

    def test_static_unknown_member_uses_known_owner_and_keeps_unknown_diagnostic(self):
        raw = b"return this.allRecipes;"
        receiver = n("ThisExpression", _draftStaticThisOwner="Game.Domain.RecipeCatalog")
        member = n("MemberExpression", computed=False, object=receiver, property=ident("allRecipes"),
                   _draftUnresolvedMember={"reason": "member is not represented in the target map"})
        ast = n("FunctionExpression", params=[], body=n("BlockStatement", body=[n("ReturnStatement", argument=member)]))
        result = render_method({"name": "recipes", "static": True, "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        self.assertIn("return Game.Domain.RecipeCatalog.allRecipes;", result["source"])
        codes = {diagnostic["code"] for diagnostic in result["diagnostics"]}
        self.assertIn("unresolved_member_mapping", codes)
        self.assertNotIn("static_this_approximation", codes)

    def test_dynamic_this_without_static_owner_annotation_is_unchanged(self):
        raw = b"return this;"
        ast = n("FunctionExpression", params=[], body=n("BlockStatement", body=[
            n("ReturnStatement", argument=n("ThisExpression"))
        ]))
        result = render_method({"name": "dynamicThis", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        self.assertIn("return this;", result["source"])

    def test_provably_empty_source_body_returns_null_without_unknown_placeholder(self):
        raw = b"function empty(){ /* comment only */ ; }"
        empty_block = n("FunctionExpression", params=[], body=n("BlockStatement", body=[]))
        result = render_method({"name": "empty", "sourceBytes": {"start": 0, "end": len(raw)}}, empty_block, raw)
        self.assertIn("return null;", result["source"])
        self.assertNotIn("NotImplementedException", result["source"])
        empty_statements = n("FunctionExpression", params=[], body=n("BlockStatement", body=[
            n("EmptyStatement"), n("BlockStatement", body=[n("EmptyStatement")])
        ]))
        result = render_method({"name": "emptyStatements", "sourceBytes": {"start": 0, "end": len(raw)}}, empty_statements, raw)
        self.assertIn("return null;", result["source"])
        self.assertNotIn("NotImplementedException", result["source"])

    def test_deep_empty_blocks_are_not_proven_empty_past_renderer_budget(self):
        raw = b"function deeplyNested(){ /* nested empty blocks */ }"
        nested = n("EmptyStatement")
        for _ in range(220):
            nested = n("BlockStatement", body=[nested])
        ast = n("FunctionExpression", params=[], body=n("BlockStatement", body=[nested]))
        result = render_method({"name": "deeplyNested", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        self.assertNotIn("return null;", result["source"])
        self.assertIn("renderer_budget_omission", {d["code"] for d in result["diagnostics"]})
        self.assertNotIn("empty_draft_body_blocked", {d["code"] for d in result["diagnostics"]})

    def test_source_underscore_assignment_survives_generated_discard_and_closure(self):
        raw = b"function use(_){ let __draftDiscard0=0; _ = _ + 1; let f=()=>{let _=2; _=_+1; 4;}; value + 2; }"
        nested = n("ArrowFunctionExpression", params=[], body=n("BlockStatement", body=[
            n("VariableDeclaration", kind="let", declarations=[n("VariableDeclarator", id=ident("_"), init=n("Literal", value=2))]),
            n("ExpressionStatement", expression=n("AssignmentExpression", operator="=", left=ident("_"), right=n("BinaryExpression", operator="+", left=ident("_"), right=n("Literal", value=1)))),
            n("ExpressionStatement", expression=n("Literal", value=4)),
        ]))
        ast = n("FunctionExpression", params=[ident("_")], body=n("BlockStatement", body=[
            n("VariableDeclaration", kind="let", declarations=[n("VariableDeclarator", id=ident("__draftDiscard0"), init=n("Literal", value=0))]),
            n("ExpressionStatement", expression=n("AssignmentExpression", operator="=", left=ident("_"), right=n("BinaryExpression", operator="+", left=ident("_"), right=n("Literal", value=1)))),
            n("VariableDeclaration", kind="let", declarations=[n("VariableDeclarator", id=ident("f"), init=nested)]),
            n("ExpressionStatement", expression=n("BinaryExpression", operator="+", left=ident("value"), right=n("Literal", value=2))),
            n("ExpressionStatement", expression=n("SequenceExpression", expressions=[ident("_"), n("Literal", value=7)])),
        ]))
        result = render_method({"name": "use", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        code = result["source"]
        self.assertIn("use(dynamic _)", code)
        self.assertIn("_ = (_ + 1);", code)
        self.assertIn("dynamic __draftDiscard0 = 0", code)
        self.assertIn("dynamic __draftDiscard2 = (value + 2);", code)
        self.assertIn("dynamic _ = 2", code)
        self.assertIn("dynamic __draftDiscard1 = 4;", code)
        self.assertIn("dynamic __draftDiscard3 = _;", code)
        self.assertIn("dynamic __draftDiscard4 = ((System.Func<dynamic>)", code)
        self.assertEqual(2, code.count("_ = (_ + 1);"))
        metadata_parameter = render_method({"name": "metadataParameter", "parameters": [{"name": "__draftDiscard0"}],
            "sourceBytes": {"start": 0, "end": len(raw)}},
            n("FunctionExpression", params=[], body=n("BlockStatement", body=[
                n("ExpressionStatement", expression=n("Literal", value=8))
            ])), raw)
        self.assertIn("metadataParameter(dynamic __draftDiscard0)", metadata_parameter["source"])
        self.assertIn("dynamic __draftDiscard1 = 8;", metadata_parameter["source"])

    def test_unbraced_control_flow_wraps_generated_discard_locals_in_blocks(self):
        raw = b"if(true) (_+100,99); else (_=_+1,42); while(_<7) (_=_+1,42); for(var i=0;i<1;i++) (i+1,0);"
        seq = lambda left, right: n("SequenceExpression", expressions=[left, right])
        assignment = n("AssignmentExpression", operator="=", left=ident("_"),
                       right=n("BinaryExpression", operator="+", left=ident("_"), right=n("Literal", value=1)))
        ast = n("FunctionExpression", params=[ident("_")], body=n("BlockStatement", body=[
            n("IfStatement", test=n("Literal", value=True),
              consequent=n("ExpressionStatement", expression=seq(n("BinaryExpression", operator="+", left=ident("_"), right=n("Literal", value=100)), n("Literal", value=99))),
              alternate=n("ExpressionStatement", expression=seq(assignment, n("Literal", value=42)))),
            n("WhileStatement", test=n("BinaryExpression", operator="<", left=ident("_"), right=n("Literal", value=7)),
              body=n("ExpressionStatement", expression=seq(assignment, n("Literal", value=42)))),
            n("ForStatement", init=n("VariableDeclaration", kind="var", declarations=[n("VariableDeclarator", id=ident("i"), init=n("Literal", value=0))]),
              test=n("BinaryExpression", operator="<", left=ident("i"), right=n("Literal", value=1)),
              update=n("UpdateExpression", operator="++", prefix=False, argument=ident("i")),
              body=n("ExpressionStatement", expression=seq(n("BinaryExpression", operator="+", left=ident("i"), right=n("Literal", value=1)), n("Literal", value=0))))
        ]))
        result = render_method({"name": "unbraced", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        code = result["source"]
        self.assertIn("if (true)\n        {", code)
        self.assertIn("else\n        {", code)
        self.assertIn("while ((_ < 7))\n        {", code)
        self.assertIn("for (dynamic i = 0; (i < 1); i++)\n        {", code)
        self.assertIn("dynamic __draftDiscard1 = ((System.Func<dynamic>)", code)
        self.assertGreaterEqual(code.count("_ = (_ + 1)"), 2)
        self.assertGreaterEqual(code.count("dynamic __draftDiscard"), 6)

    def test_binding_id_collision_maps_dollar_and_underscore_references_deterministically(self):
        raw = b"function scale($, _){ return $ + _; }"
        dollar = lambda: n("Identifier", name="$", bindingId="scale-dollar")
        under = lambda: n("Identifier", name="_", bindingId="scale-under")
        ast = n("FunctionExpression", params=[dollar(), under()], body=n("BlockStatement", body=[
            n("ReturnStatement", argument=n("BinaryExpression", operator="+", left=dollar(), right=under()))
        ]))
        method = {"name": "scale", "sourceBytes": {"start": 0, "end": len(raw)}}
        first = render_method(method, ast, raw)
        second = render_method(method, ast, raw)
        self.assertEqual(first["source"], second["source"])
        signature = first["source"].splitlines()[0]
        parameter_names = [part.strip().split(" ", 1)[1] for part in signature.split("(", 1)[1].split(")", 1)[0].split(",")]
        self.assertEqual(2, len(set(parameter_names)))
        return_line = next(line for line in first["source"].splitlines() if "return (" in line)
        self.assertTrue(all(name in return_line for name in parameter_names))
        self.assertNotIn("dynamic _,", signature)

    def test_binding_id_mapping_handles_capture_shadow_and_local_loop_catch_names(self):
        raw = b"function f($){ let _=2; let cb=(_)=>$+_; for(let $ of xs){} try{}catch(_){} }"
        outer = lambda: n("Identifier", name="$", bindingId="outer-dollar")
        local_ident = lambda: n("Identifier", name="_", bindingId="local-under")
        inner = lambda: n("Identifier", name="_", bindingId="inner-under")
        loop = n("ForOfStatement", left=n("VariableDeclaration", kind="let", declarations=[
            n("VariableDeclarator", id=n("Identifier", name="$", bindingId="loop-dollar"), init=None)
        ]), right=n("Identifier", name="xs", bindingId="xs-binding"), body=n("BlockStatement", body=[]))
        ast = n("FunctionExpression", params=[outer()], body=n("BlockStatement", body=[
            n("VariableDeclaration", kind="let", declarations=[n("VariableDeclarator", id=local_ident(), init=n("Literal", value=2))]),
            n("VariableDeclaration", kind="let", declarations=[n("VariableDeclarator", id=ident("cb"), init=n("ArrowFunctionExpression", params=[inner()], body=n("BinaryExpression", operator="+", left=outer(), right=inner())))]),
            loop,
            n("TryStatement", block=n("BlockStatement", body=[]), handler=n("CatchClause", param=n("Identifier", name="_", bindingId="catch-under"), body=n("BlockStatement", body=[])))
        ]))
        result = render_method({"name": "f", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        code = result["source"]
        for binding in ("outer-dollar", "local-under", "inner-under", "loop-dollar", "catch-under"):
            generated = "__draftBinding___" + hashlib.sha256(("str:" + binding).encode()).hexdigest()[:10]
            self.assertIn(generated, code)
        self.assertIn("foreach (dynamic __draftBinding___", code)

    def test_explicit_targets_are_fixed_member_targets_unchanged_and_collisions_diagnosed(self):
        raw = b"function f($, scale){ return $ + scale + owner.publicName; }"
        dollar = n("Identifier", name="$", bindingId="explicit-dollar", _draftIdentifierTarget="scale")
        other = n("Identifier", name="scale", bindingId="source-scale")
        mapped_member = n("MemberExpression", computed=False, object=ident("owner"), property=ident("oldName"),
                          _draftMember={"name": "PublicName", "ownerClass": "Thing", "receiver": "source"})
        ast = n("FunctionExpression", params=[dollar, other], body=n("BlockStatement", body=[
            n("ReturnStatement", argument=n("BinaryExpression", operator="+", left=dollar,
                right=n("BinaryExpression", operator="+", left=other, right=mapped_member)))
        ]))
        result = render_method({"name": "f", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        signature = result["source"].splitlines()[0]
        self.assertIn("dynamic scale", signature)
        self.assertIn("__draftBinding_scale_", signature)
        self.assertIn("(owner).PublicName", result["source"])
        fixed_underscore = n("Identifier", name="_", bindingId="fixed-under", _draftIdentifierTarget="_")
        source_underscore = n("Identifier", name="_", bindingId="source-under")
        underscore_result = render_method({"name": "underscoreTargets", "sourceBytes": {"start": 0, "end": len(raw)}},
            n("FunctionExpression", params=[fixed_underscore, source_underscore], body=n("BlockStatement", body=[
                n("ReturnStatement", argument=n("BinaryExpression", operator="+", left=fixed_underscore, right=source_underscore))
            ])), raw)
        underscore_signature = underscore_result["source"].splitlines()[0]
        self.assertIn("dynamic _", underscore_signature)
        self.assertIn("__draftBinding___", underscore_signature)
        conflict = n("FunctionExpression", params=[
            n("Identifier", name="$", bindingId="fixed-a", _draftIdentifierTarget="same"),
            n("Identifier", name="_", bindingId="fixed-b", _draftIdentifierTarget="same")
        ], body=n("BlockStatement", body=[n("ReturnStatement", argument=n("Literal", value=0))]))
        conflict_result = render_method({"name": "fixedConflict", "sourceBytes": {"start": 0, "end": len(raw)}}, conflict, raw)
        self.assertIn("fixedConflict(dynamic same, dynamic same)", conflict_result["source"])
        self.assertIn("identifier_explicit_target_collision", {d["code"] for d in conflict_result["diagnostics"]})

    def test_missing_binding_identity_reports_normalization_collision_without_guessing(self):
        raw = b"return $ + _;"
        ast = n("FunctionExpression", params=[], body=n("BlockStatement", body=[
            n("ReturnStatement", argument=n("BinaryExpression", operator="+", left=ident("$"), right=ident("_")))
        ]))
        result = render_method({"name": "missingBindings", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        self.assertIn("return (_ + _);", result["source"])
        self.assertIn("identifier_collision_missing_binding_id", {d["code"] for d in result["diagnostics"]})

    def test_root_function_binding_stays_on_public_signature_while_local_parameter_is_renamed(self):
        raw = b"function _($){ return _($); }"
        root_id = n("Identifier", name="_", bindingId="root-public")
        parameter = n("Identifier", name="$", bindingId="dollar-parameter")
        recursive = n("Identifier", name="_", bindingId="root-public")
        parameter_ref = n("Identifier", name="$", bindingId="dollar-parameter")
        ast = n("FunctionDeclaration", id=root_id, params=[parameter], body=n("BlockStatement", body=[
            n("ReturnStatement", argument=n("CallExpression", callee=recursive, arguments=[parameter_ref]))
        ]))
        result = render_method({"name": "_", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        generated_parameter = "__draftBinding___" + hashlib.sha256(b"str:dollar-parameter").hexdigest()[:10]
        self.assertIn(f"public dynamic _(dynamic {generated_parameter})", result["source"])
        self.assertIn(f"return _({generated_parameter});", result["source"])
        self.assertNotIn("root_function_binding_unmatched", {d["code"] for d in result["diagnostics"]})

    def test_unmatched_named_root_function_is_diagnosed_without_inventing_target(self):
        raw = b"var f = function _($){ return _($); };"
        ast = n("FunctionExpression", id=n("Identifier", name="_", bindingId="internal-root"),
            params=[n("Identifier", name="$", bindingId="internal-parameter")], body=n("BlockStatement", body=[
                n("ReturnStatement", argument=n("CallExpression", callee=n("Identifier", name="_", bindingId="internal-root"),
                    arguments=[n("Identifier", name="$", bindingId="internal-parameter")]))
            ]))
        result = render_method({"name": "run", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        parameter_name = "__draftBinding___" + hashlib.sha256(b"str:internal-parameter").hexdigest()[:10]
        self.assertIn("public dynamic run(", result["source"])
        self.assertIn(f"return _({parameter_name});", result["source"])
        self.assertIn("root_function_binding_unmatched", {d["code"] for d in result["diagnostics"]})
        no_identity = n("FunctionDeclaration", id=ident("_"), params=[], body=n("BlockStatement", body=[
            n("ReturnStatement", argument=n("CallExpression", callee=ident("_"), arguments=[]))
        ]))
        no_identity_result = render_method({"name": "run", "sourceBytes": {"start": 0, "end": len(raw)}}, no_identity, raw)
        self.assertIn("public dynamic run()", no_identity_result["source"])
        self.assertIn("return _();", no_identity_result["source"])
        self.assertIn("root_function_binding_identity_missing", {d["code"] for d in no_identity_result["diagnostics"]})

    def test_explicit_root_function_target_keeps_existing_signature_mapping(self):
        raw = b"function _(){ return _(); }"
        ast = n("FunctionDeclaration", id=n("Identifier", name="_", bindingId="root-explicit", _draftIdentifierTarget="recurseTarget"),
            params=[], body=n("BlockStatement", body=[n("ReturnStatement", argument=n("CallExpression",
                callee=n("Identifier", name="_", bindingId="root-explicit", _draftIdentifierTarget="recurseTarget"), arguments=[]))]))
        result = render_method({"name": "_", "targetName": "recurseTarget", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        self.assertIn("public dynamic recurseTarget()", result["source"])
        self.assertIn("return recurseTarget();", result["source"])
        self.assertNotIn("root_function_target_mismatch", {d["code"] for d in result["diagnostics"]})

    def test_plain_int32_literal_division_uses_double_but_other_operands_stay_unchanged(self):
        raw = b"return left / right;"
        def render_division(left, right, operator="/"):
            expression = n("BinaryExpression", operator=operator, left=left, right=right)
            ast = n("FunctionExpression", params=[], body=n("BlockStatement", body=[n("ReturnStatement", argument=expression)]))
            return render_method({"name": "division", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)["source"]
        literal = lambda value, **markers: n("Literal", value=value, **markers)
        for left, right, expected in (
            (1, 60, "((double)(1)) / 60"),
            (4, 2, "((double)(4)) / 2"),
            (0, 0, "((double)(0)) / 0"),
            (1, 0, "((double)(1)) / 0"),
        ):
            self.assertIn(expected, render_division(literal(left), literal(right)))
        self.assertIn("(true / 2)", render_division(literal(True), literal(2)))
        self.assertIn('(\"1\" / 2)', render_division(literal("1"), literal(2)))
        self.assertIn("(value / 2)", render_division(ident("value"), literal(2)))
        self.assertIn("(2147483648 / 2)", render_division(literal(2147483648), literal(2)))
        self.assertIn("(1 / 2)", render_division(literal(1, bigint="1"), literal(2)))
        self.assertIn("(1 / 2)", render_division(literal(1, regex={"pattern": "1", "flags": ""}), literal(2)))
        self.assertIn("(1 + 2)", render_division(literal(1), literal(2), operator="+"))

    def test_not_of_plain_int32_zero_and_one_is_constant_but_other_inputs_stay_approximate(self):
        raw = b"!0; !1;"
        for value, expected in ((0, "true"), (1, "false")):
            unary = n("UnaryExpression", operator="!", argument=n("Literal", value=value))
            method_ast = n("FunctionExpression", params=[], body=n("BlockStatement", body=[n("ReturnStatement", argument=unary)]))
            method_result = render_method({"name": "notLiteral", "sourceBytes": {"start": 0, "end": len(raw)}}, method_ast, raw)
            self.assertIn(f"return {expected};", method_result["source"])
            self.assertNotIn("truthiness_approximation", {d["code"] for d in method_result["diagnostics"]})
            field_result = render_field({"name": "flag", "static": True, "sourceBytes": {"start": 0, "end": len(raw)}}, unary, raw)
            self.assertIn(f"= {expected};", field_result["source"])
            self.assertNotIn("truthiness_approximation", {d["code"] for d in field_result["diagnostics"]})

        unsupported = [
            (n("Literal", value=2), "(!2)"),
            (n("Literal", value=1.0), "(!1.0)"),
            (ident("value"), "(!value)"),
            (n("Literal", value="0"), '(!"0")'),
            (n("Literal", value=False), "(!false)"),
            (n("Literal", value=0, bigint="0"), "(!0)"),
            (n("Literal", value=1, regex={"pattern": "1", "flags": ""}), "(!1)"),
            (n("Literal", value=2147483648), "(!2147483648)"),
        ]
        for argument, expected in unsupported:
            unary = n("UnaryExpression", operator="!", argument=argument)
            result = render_method({"name": "notApprox", "sourceBytes": {"start": 0, "end": len(raw)}},
                n("FunctionExpression", params=[], body=n("BlockStatement", body=[n("ReturnStatement", argument=unary)])), raw)
            self.assertIn(expected, result["source"])
            self.assertIn("truthiness_approximation", {d["code"] for d in result["diagnostics"]})
        field = render_field({"name": "unhandledFlag", "static": True, "sourceBytes": {"start": 0, "end": len(raw)}},
            n("UnaryExpression", operator="!", argument=n("Literal", value=2)), raw)
        self.assertIn("= (!2);", field["source"])
        self.assertIn("truthiness_approximation", {d["code"] for d in field["diagnostics"]})

    def test_field_target_name_does_not_guess_unrelated_dynamic_member_case(self):
        raw = b"this.scale_label"
        field = render_field({"name": "scale_label", "targetName": "ScaleLabel", "static": False,
                              "sourceBytes": {"start": 0, "end": len(raw)}}, n("Literal", value=1), raw)
        self.assertEqual("public dynamic ScaleLabel = 1;", field["source"])
        unresolved_member = n("MemberExpression", computed=False, object=n("ThisExpression"), property=ident("scale_label"),
                              _draftUnresolvedMember={"reason": "no owner field binding"})
        unresolved = render_method({"name": "readScale", "sourceBytes": {"start": 0, "end": len(raw)}},
            n("FunctionExpression", params=[], body=n("BlockStatement", body=[n("ReturnStatement", argument=unresolved_member)])), raw)
        self.assertIn("return (this).scale_label;", unresolved["source"])
        self.assertIn("unresolved_member_mapping", {d["code"] for d in unresolved["diagnostics"]})
        mapped_member = n("MemberExpression", computed=False, object=n("ThisExpression"), property=ident("scale_label"),
                          _draftMember={"name": "ScaleLabel", "ownerClass": "Owner", "receiver": "source"})
        mapped = render_method({"name": "readScale", "sourceBytes": {"start": 0, "end": len(raw)}},
            n("FunctionExpression", params=[], body=n("BlockStatement", body=[n("ReturnStatement", argument=mapped_member)])), raw)
        self.assertIn("return (this).ScaleLabel;", mapped["source"])

    def test_incomplete_binding_scan_reports_budget_and_skips_new_renames(self):
        raw = b"function f($,_){return $+_;}"
        dollar_param = n("Identifier", name="$", bindingId="budget-dollar", _draftIdentifierTarget="keptDollar")
        under_param = n("Identifier", name="_", bindingId="budget-under")
        ast = n("FunctionExpression", params=[dollar_param, under_param], body=n("BlockStatement", body=[
            n("ReturnStatement", argument=n("BinaryExpression", operator="+",
                left=n("Identifier", name="$", bindingId="budget-dollar", _draftIdentifierTarget="keptDollar"),
                right=n("Identifier", name="_", bindingId="budget-under")))
        ]), plannerNoise=[ident(f"noise{index}") for index in range(32)])
        with patch("monkey.code_draft_render.MAX_NODES", 8):
            result = render_method({"name": "f", "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        codes = {diagnostic["code"] for diagnostic in result["diagnostics"]}
        self.assertIn("identifier_binding_scan_budget_exceeded", codes)
        self.assertNotIn("__draftBinding_", result["source"])
        self.assertIn("dynamic keptDollar", result["source"])
        self.assertIn("return (keptDollar + _);", result["source"])

    def test_control_flow_calls_collections_math_string_and_callback_render_as_code(self):
        source = b'function update(x){ /* body */ }'
        ast = n("FunctionExpression", **{"async": False}, params=[ident("x")], body=n("BlockStatement", body=[
            n("IfStatement", test=ident("x"), consequent=n("BlockStatement", body=[
                n("ExpressionStatement", expression=n("AssignmentExpression", operator="+=", left=ident("x"), right=n("Literal", value=1)))
            ]), alternate=n("BlockStatement", body=[
                n("ExpressionStatement", expression=n("AssignmentExpression", operator="=", left=ident("x"), right=n("Literal", value=2)))
            ])),
            n("ForStatement", init=n("VariableDeclaration", kind="let", declarations=[n("VariableDeclarator", id=ident("i"), init=n("Literal", value=0))]),
              test=n("BinaryExpression", operator="<", left=ident("i"), right=n("Literal", value=2)),
              update=n("UpdateExpression", operator="++", prefix=False, argument=ident("i")),
              body=n("BlockStatement", body=[n("ExpressionStatement", expression=n("AssignmentExpression", operator="+=", left=ident("x"), right=ident("i")))])),
            n("WhileStatement", test=n("BinaryExpression", operator="<", left=ident("x"), right=n("Literal", value=10)),
              body=n("BlockStatement", body=[n("ExpressionStatement", expression=n("UpdateExpression", operator="++", prefix=False, argument=ident("x")))])),
            n("SwitchStatement", discriminant=ident("x"), cases=[
            n("SwitchCase", test=n("Literal", value=1), consequent=[
                    n("ExpressionStatement", expression=n("AssignmentExpression", operator="=", left=ident("x"), right=n("Literal", value=3))),
                    n("BreakStatement")]),
                n("SwitchCase", test=None, consequent=[n("ReturnStatement", argument=ident("x"))])]),
            n("TryStatement", block=n("BlockStatement", body=[n("ThrowStatement", argument=n("Literal", value="oops"))]),
              handler=n("CatchClause", param=ident("error"), body=n("BlockStatement", body=[n("ExpressionStatement", expression=n("CallExpression", callee=n("MemberExpression", computed=False, object=ident("cc"), property=ident("warn")), arguments=[ident("error")]))])),
              finalizer=n("BlockStatement", body=[n("ExpressionStatement", expression=n("CallExpression", callee=ident("cleanup"), arguments=[]))])),
            n("VariableDeclaration", kind="const", declarations=[n("VariableDeclarator", id=ident("values"), init=n("ArrayExpression", elements=[ident("x"), n("CallExpression", callee=n("MemberExpression", computed=False, object=ident("Math"), property=ident("max")), arguments=[ident("x"), n("Literal", value=4)])]))]),
            n("VariableDeclaration", kind="const", declarations=[n("VariableDeclarator", id=ident("record"), init=n("ObjectExpression", properties=[n("Property", kind="init", method=False, computed=False, key=ident("label"), value=n("TemplateLiteral", quasis=[n("TemplateElement", value={"cooked": "hp="}) , n("TemplateElement", value={"cooked": ""})], expressions=[ident("x")]))]))]),
            n("ExpressionStatement", expression=n("CallExpression", callee=n("MemberExpression", computed=False, object=ident("cc"), property=ident("log")), arguments=[ident("record")])),
            n("ExpressionStatement", expression=n("CallExpression", callee=n("MemberExpression", computed=False, object=ident("values"), property=ident("forEach")), arguments=[n("ArrowFunctionExpression", **{"async": False}, params=[ident("item")], body=n("UpdateExpression", operator="++", prefix=False, argument=ident("item")))])),
            n("ReturnStatement", argument=ident("values"))
        ]))
        result = render_method({"name": "update", "sourceBytes": {"start": 0, "end": len(source)}}, ast, source, class_name="HealthState")
        code = result["source"]
        for expected in ("public dynamic update(dynamic x)", "if (x)", "for (dynamic i = 0;", "while ((x < 10))", "switch (x)", "try", "throw new System.Exception", "catch (System.Exception", "finally", "new System.Collections.Generic.List<dynamic>", "System.Math.Max", "$\"hp={x}\"", "UnityEngine.Debug.LogWarning", "(dynamic item)", "return values;"):
            self.assertIn(expected, code)
        self.assertIn("System.Collections.Generic", result["usings"])
        self.assertIn("UnityEngine", result["usings"])
        self.assertTrue(result["draftOnly"])
        self.assertFalse(result["sourceExecuted"])
        self.assertTrue(any(d["code"] == "throw_approximation" for d in result["diagnostics"]))

    def test_unsupported_local_expression_is_escaped_and_following_statements_survive(self):
        source = b"function f(x){ weird*/operation(x); return x + 1; }"
        start = source.index(b"weird*/operation")
        end = source.index(b";", start)
        unsupported = n("FutureExpression", start=start, end=end)
        ast = n("FunctionExpression", params=[ident("x")], body=n("BlockStatement", body=[
            n("ExpressionStatement", expression=unsupported),
            n("ReturnStatement", argument=n("BinaryExpression", operator="+", left=ident("x"), right=n("Literal", value=1)))
        ]))
        result = render_method({"name": "f", "sourceBytes": {"start": 0, "end": len(source)}}, ast, source)
        code = result["source"]
        self.assertIn("draft omission FutureExpression", code)
        self.assertIn("weird* /operation", code)
        self.assertIn("NotImplementedException", code)
        self.assertIn("return (x + 1);", code)
        self.assertTrue(any(d["code"] == "unsupported_expression" for d in result["diagnostics"]))
        self.assertNotIn("weird*/operation(x); */", code)

    def test_async_unmapped_cc_api_and_csharp_member_collision_are_named(self):
        source = b"async function HealthState(x){ return await cc.remote(x); }"
        start = source.index(b"cc.remote")
        end = source.index(b")", start) + 1
        callee = n("MemberExpression", start=start, end=end, computed=False, object=ident("cc"), property=ident("remote"))
        ast = n("FunctionExpression", **{"async": True}, params=[ident("x")], body=n("BlockStatement", body=[
            n("ReturnStatement", argument=n("AwaitExpression", argument=n("CallExpression", callee=callee, arguments=[ident("x")])))
        ]))
        result = render_method({"name": "HealthState", "sourceBytes": {"start": 0, "end": len(source)}}, ast, source, class_name="HealthState")
        self.assertIn("Task<dynamic> HealthState_DraftMethod", result["source"])
        self.assertIn("await cc.remote(x)", result["source"])
        self.assertIn("unmapped_cc_api", {d["code"] for d in result["diagnostics"]})
        self.assertIn("method_name_class_collision", {d["code"] for d in result["diagnostics"]})
        self.assertIn("System.Threading.Tasks", result["usings"])

    def test_invalid_source_span_fails_without_silent_method_success(self):
        with self.assertRaisesRegex(ValueError, "sourceBytes"):
            render_method({"name": "bad", "sourceBytes": {"start": -1, "end": 4}},
                          n("FunctionExpression", params=[], body=n("BlockStatement", body=[])), b"x")
        with self.assertRaisesRegex(ValueError, "sourceSha256"):
            render_method({"name": "bad", "sourceBytes": {"start": 0, "end": 1}, "sourceSha256": "0" * 64},
                          n("FunctionExpression", params=[], body=n("BlockStatement", body=[])), b"x")

    def test_actual_acorn_method_ast_renders_from_exact_utf8_source(self):
        raw = 'var Box=(function(){function e(){};e.prototype.work=function(x){if(x<2){x++;}return Math.max(x,3);};return e;})();'.encode()
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            source = Path(directory) / "source.js"
            source.write_bytes(raw)
            index = facts(source)
            method = next(row for row in index["methods"] if row["name"] == "work")
            selected = facts(source, index["source"]["sha256"], [method["id"]])["selected"][0]
        result = render_method(method, selected["ast"], raw, class_name="Box")
        self.assertIn("if ((x < 2))", result["source"])
        self.assertIn("System.Math.Max", result["source"])
        self.assertTrue(result["sourceExecuted"] is False)

    def test_method_with_no_renderable_statement_is_explicitly_blocked(self):
        source = b"function unknown(x){futureSyntax(x); }"
        start = source.index(b"futureSyntax")
        end = source.index(b";", start)
        ast = n("FunctionExpression", params=[ident("x")], body=n("BlockStatement", body=[
            n("FutureStatement", start=start, end=end)
        ]))
        result = render_method({"name": "unknown", "sourceBytes": {"start": 0, "end": len(source)}}, ast, source)
        self.assertIn("NotImplementedException", result["source"])
        self.assertIn("empty_draft_body_blocked", {d["code"] for d in result["diagnostics"]})

    def test_field_literal_and_collection_initializer_reuse_expression_renderer(self):
        source = b'e.items = [1, "two"];'
        start = source.index(b"[1")
        end = source.index(b"]", start) + 1
        ast = n("ArrayExpression", start=start, end=end, elements=[n("Literal", value=1), n("Literal", value="two")])
        result = render_field({"name": "items", "static": True, "sourceBytes": {"start": 0, "end": len(source)}}, ast, source, class_name="Store")
        self.assertEqual(result["source"], 'public static dynamic items = new System.Collections.Generic.List<dynamic> { 1, "two" };')
        self.assertIn("System.Collections.Generic", result["usings"])
        self.assertTrue(result["draftOnly"])

    def test_field_missing_or_unsupported_initializer_never_defaults_to_success(self):
        source = b'e.unknown = new FutureType();'
        result = render_field({"name": "unknown", "static": True, "sourceBytes": {"start": 0, "end": len(source)}}, None, source)
        self.assertIn("Field initializer AST unavailable", result["source"])
        self.assertIn("field_initializer_missing", {d["code"] for d in result["diagnostics"]})
        start = source.index(b"new FutureType")
        end = len(source) - 1
        ast = n("FutureExpression", start=start, end=end)
        unsupported = render_field({"name": "unknown", "static": True, "sourceBytes": {"start": 0, "end": len(source)}}, ast, source)
        self.assertIn("FutureExpression", unsupported["source"])
        self.assertIn("NotImplementedException", unsupported["source"])
        self.assertIn("unsupported_expression", {d["code"] for d in unsupported["diagnostics"]})

    def test_acorn_multi_declarator_and_for_initializer_emit_one_dynamic_type(self):
        raw = b'var Model=(function(){function e(){};e.prototype.run=function(x){var a=1,b=2;for(var i=0,j=1;i<3;i++){a+=j;}return a+b+x;};return e;})();'
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            source = Path(directory) / "source.js"
            source.write_bytes(raw)
            index = facts(source)
            method = next(row for row in index["methods"] if row["name"] == "run")
            ast = facts(source, index["source"]["sha256"], [method["id"]])["selected"][0]["ast"]
        result = render_method(method, ast, raw, class_name="Model")
        code = result["source"]
        self.assertIn("dynamic a = 1, b = 2;", code)
        self.assertIn("for (dynamic i = 0, j = 1; (i < 3); i++)", code)
        self.assertNotIn("dynamic j =", code)

    def test_field_this_is_retained_with_static_initializer_diagnostic(self):
        raw = b'e.owner = this.active;'
        start = raw.index(b"this")
        ast = n("MemberExpression", start=start, end=len(raw) - 1, computed=False,
                object=n("ThisExpression", start=start, end=start + 4),
                property=n("Identifier", name="active", start=start + 5, end=len(raw) - 1))
        result = render_field({"name": "owner", "static": True, "sourceBytes": {"start": 0, "end": len(raw)}}, ast, raw)
        self.assertIn("(this).active", result["source"])
        self.assertIn("field_initializer_this", {d["code"] for d in result["diagnostics"]})


if __name__ == "__main__":
    unittest.main()
