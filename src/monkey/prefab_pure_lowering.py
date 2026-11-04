"""Fail-closed lowering for a small, typed pure-JavaScript expression subset.

The source is parsed by monkey.code_graph's pinned Acorn worker and is never
executed. Caller-supplied types are explicit boundaries, not inferred claims.
Only returned expressions, boolean Array.filter predicates, and field-keyed
Array.sort comparators are accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any

from . import io
from .code_graph import facts
from .sources.compiled import fail

SCHEMA = "monkey-pure-expression-lowering/1"
TEMPLATE_ROOT = Path(__file__).resolve().parent / "targets/pure_lowering"
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KEYWORDS = {
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char", "checked", "class", "const",
    "continue", "decimal", "default", "delegate", "do", "double", "else", "enum", "event", "explicit", "extern",
    "false", "finally", "fixed", "float", "for", "foreach", "goto", "if", "implicit", "in", "int", "interface",
    "internal", "is", "lock", "long", "namespace", "new", "null", "object", "operator", "out", "override", "params",
    "private", "protected", "public", "readonly", "ref", "return", "sbyte", "sealed", "short", "sizeof", "stackalloc",
    "static", "string", "struct", "switch", "this", "throw", "true", "try", "typeof", "uint", "ulong", "unchecked",
    "unsafe", "ushort", "using", "virtual", "void", "volatile", "while", "async", "await", "yield", "var", "let",
    "function", "export", "import", "extends", "implements", "interface", "package", "private", "protected", "public",
}
_MAX_SOURCE_BYTES = 32 * 1024 * 1024
_MAX_CONTRACT_BYTES = 2 * 1024 * 1024
_MAX_CONTRACT_NODES = 100_000
_MAX_EXPR_NODES = 20_000


@dataclass(frozen=True)
class _Type:
    kind: str
    name: str = ""

    def child(self) -> "_Type":
        if self.kind != "Array":
            raise ValueError("not an array")
        return _Type("Record", self.name)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fail(code: str, location: str, message: str) -> None:
    fail(code, location, message)


def _identifier(value: Any, location: str) -> str:
    if not isinstance(value, str) or not _IDENT.fullmatch(value) or value in _KEYWORDS:
        _fail("PURE_LOWERING_CONTRACT", location, "Expected a non-keyword ASCII target identifier")
    return value


def _parse_type(value: Any, records: dict[str, Any], location: str) -> _Type:
    if not isinstance(value, str) or len(value) > 128:
        _fail("PURE_LOWERING_TYPE", location, "Type must be a bounded explicit string")
    if value in ("Number", "Boolean", "String"):
        return _Type(value)
    match = re.fullmatch(r"Array<([A-Za-z_][A-Za-z0-9_]*)>", value)
    if match and match.group(1) in records:
        return _Type("Array", match.group(1))
    if value in records:
        return _Type("Record", value)
    _fail("PURE_LOWERING_TYPE", location, "Unknown type; provide a primitive, declared record, or Array<Record>")


def _target_type(typ: _Type, target: str, records: dict[str, Any]) -> str:
    primitive = {"Number": "double" if target == "unity" else "number",
                 "Boolean": "bool" if target == "unity" else "boolean",
                 "String": "string"}
    if typ.kind in primitive:
        return primitive[typ.kind]
    row = records[typ.name]
    if typ.kind == "Record":
        return row["unityType" if target == "unity" else "creatorType"]
    item = _target_type(_Type("Record", typ.name), target, records)
    return f"IReadOnlyList<{item}>" if target == "unity" else f"ReadonlyArray<{item}>"


def _validate_contract(contract: Any, namespace: str, class_name: str, method_name: str) -> dict[str, Any]:
    if not isinstance(contract, dict) or set(contract) - {"schemaVersion", "records", "parameters", "returns"}:
        _fail("PURE_LOWERING_CONTRACT", "contract", "Expected only schemaVersion, records, parameters, and returns")
    if contract.get("schemaVersion") != 1:
        _fail("PURE_LOWERING_CONTRACT", "contract.schemaVersion", "Only schema version 1 is supported")
    records = contract.get("records")
    if not isinstance(records, dict) or not 1 <= len(records) <= 32:
        _fail("PURE_LOWERING_CONTRACT", "contract.records", "Declare 1..32 record types")
    normalized_records: dict[str, Any] = {}
    for record_name, row in records.items():
        _identifier(record_name, "contract.records.name")
        if not isinstance(row, dict) or set(row) != {"unityType", "creatorType", "fields"}:
            _fail("PURE_LOWERING_CONTRACT", "contract.records." + record_name, "Record requires unityType, creatorType, and fields")
        normalized_records[record_name] = {
            "unityType": _identifier(row["unityType"], "contract.records." + record_name + ".unityType"),
            "creatorType": _identifier(row["creatorType"], "contract.records." + record_name + ".creatorType"),
            "fields": {},
        }
    for record_name, row in records.items():
        fields = row["fields"]
        if not isinstance(fields, dict) or not 1 <= len(fields) <= 128:
            _fail("PURE_LOWERING_CONTRACT", "contract.records." + record_name + ".fields", "Declare 1..128 typed fields")
        for field_name, field in fields.items():
            _identifier(field_name, "contract.records." + record_name + ".field")
            if not isinstance(field, dict) or set(field) != {"type", "unity", "creator"}:
                _fail("PURE_LOWERING_CONTRACT", "contract.records." + record_name + "." + field_name,
                      "Field requires an explicit type and Unity/Creator member names")
            typ = _parse_type(field["type"], normalized_records, "contract.records." + record_name + "." + field_name + ".type")
            if typ.kind == "Array":
                _fail("PURE_LOWERING_CONTRACT", "contract.records." + record_name + "." + field_name,
                      "Nested arrays/collections are outside this expression subset")
            normalized_records[record_name]["fields"][field_name] = {
                "type": typ, "unity": _identifier(field["unity"], "contract.records." + record_name + "." + field_name + ".unity"),
                "creator": _identifier(field["creator"], "contract.records." + record_name + "." + field_name + ".creator"),
            }
    params = contract.get("parameters")
    if not isinstance(params, list) or not 1 <= len(params) <= 8:
        _fail("PURE_LOWERING_CONTRACT", "contract.parameters", "Declare 1..8 typed parameters")
    normalized_params = []
    source_names, target_names = set(), {"unity": set(), "creator": set()}
    for i, row in enumerate(params):
        loc = f"contract.parameters[{i}]"
        if not isinstance(row, dict) or set(row) != {"source", "type", "unity", "creator"}:
            _fail("PURE_LOWERING_CONTRACT", loc, "Parameter requires source, type, Unity/Creator target names")
        src = _identifier(row["source"], loc + ".source")
        if src in source_names:
            _fail("PURE_LOWERING_CONTRACT", loc, "Duplicate source parameter name")
        source_names.add(src)
        typ = _parse_type(row["type"], normalized_records, loc + ".type")
        if typ.kind not in ("Number", "Boolean", "String", "Record", "Array"):
            _fail("PURE_LOWERING_CONTRACT", loc + ".type", "Unsupported parameter type")
        names = {}
        for target in ("unity", "creator"):
            names[target] = _identifier(row[target], loc + "." + target)
            if names[target] in target_names[target]:
                _fail("PURE_LOWERING_CONTRACT", loc, "Target parameter names must be unique")
            target_names[target].add(names[target])
        normalized_params.append({"source": src, "type": typ, **names})
    returns = _parse_type(contract.get("returns"), normalized_records, "contract.returns")
    if returns.kind not in ("Number", "Boolean", "String", "Record", "Array"):
        _fail("PURE_LOWERING_CONTRACT", "contract.returns", "Unsupported return type")
    ns_parts = namespace.split(".") if isinstance(namespace, str) else []
    if not ns_parts or any(not _IDENT.fullmatch(part) or part in _KEYWORDS for part in ns_parts):
        _fail("PURE_LOWERING_CONTRACT", "namespace", "Expected a dotted non-keyword namespace")
    return {"schemaVersion": 1, "records": normalized_records, "parameters": normalized_params,
            "returns": returns, "namespace": namespace,
            "className": _identifier(class_name, "className"), "methodName": _identifier(method_name, "methodName")}


class _Builder:
    def __init__(self, records: dict[str, Any], reserved_target_names=(), max_nodes: int = _MAX_EXPR_NODES):
        self.records = records
        self.max_nodes = max_nodes
        self.node_count = 0
        self.callback_index = 0
        self.used_callback_names = set(reserved_target_names)

    def _node(self, value: dict[str, Any]) -> dict[str, Any]:
        self.node_count += 1
        if self.node_count > self.max_nodes:
            _fail("PURE_LOWERING_EXPR_BUDGET", "ast", "Pure expression exceeds the node budget")
        return value

    def body_expression(self, fn: dict[str, Any]) -> dict[str, Any]:
        if fn.get("type") not in ("FunctionExpression", "ArrowFunctionExpression") or fn.get("async") or fn.get("generator"):
            _fail("PURE_LOWERING_UNSUPPORTED", "function", "Only synchronous non-generator functions are supported")
        if fn.get("defaults") or fn.get("params") is None:
            _fail("PURE_LOWERING_UNSUPPORTED", "function.params", "Default/rest/destructured parameters are unsupported")
        body = fn.get("body", {})
        if body.get("type") == "BlockStatement":
            statements = body.get("body", [])
            if len(statements) != 1 or statements[0].get("type") != "ReturnStatement" or not statements[0].get("argument"):
                _fail("PURE_LOWERING_UNSUPPORTED", "function.body", "Pure functions must contain exactly one value return")
            return statements[0]["argument"]
        return body

    def expression(self, node: dict[str, Any], env: dict[str, tuple[_Type, str]]) -> dict[str, Any]:
        if not isinstance(node, dict):
            _fail("PURE_LOWERING_UNSUPPORTED", "expression", "Missing expression node")
        kind = node.get("type")
        if kind == "Literal":
            value = node.get("value")
            if type(value) is bool:
                return self._node({"kind": "literal", "value": value, "type": _Type("Boolean")})
            if type(value) in (int, float):
                if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
                    _fail("PURE_LOWERING_NUMBER", "literal", "Non-finite numeric literal is unsupported")
                return self._node({"kind": "literal", "value": value, "type": _Type("Number")})
            if isinstance(value, str):
                return self._node({"kind": "literal", "value": value, "type": _Type("String")})
            _fail("PURE_LOWERING_UNSUPPORTED", "literal", "Null, regex, and non-primitive literals are unsupported")
        if kind == "Identifier":
            binding = node.get("bindingId")
            if node.get("bindingAmbiguous") or not binding or binding not in env:
                _fail("PURE_LOWERING_BINDING", str(node.get("name")), "Identifier is not a uniquely typed parameter or callback variable")
            typ, names = env[binding]
            return self._node({"kind": "identifier", "sourceName": node["name"], "bindingId": binding,
                               "targetNames": names, "type": typ})
        if kind == "MemberExpression":
            if node.get("computed") or node.get("optional"):
                _fail("PURE_LOWERING_UNSUPPORTED", "member", "Computed/optional member access is unsupported")
            base = self.expression(node.get("object"), env)
            if base["type"].kind != "Record":
                _fail("PURE_LOWERING_TYPE", str(node.get("property", {}).get("name")), "Member access requires a declared record")
            field_name = node.get("property", {}).get("name")
            fields = self.records[base["type"].name]["fields"]
            if field_name not in fields:
                _fail("PURE_LOWERING_FIELD", str(field_name), "Field is absent from the explicit record contract")
            field = fields[field_name]
            return self._node({"kind": "field", "object": base, "sourceField": field_name,
                               "targetNames": {"unity": field["unity"], "creator": field["creator"]}, "type": field["type"]})
        if kind in ("BinaryExpression", "LogicalExpression"):
            left = self.expression(node.get("left"), env)
            right = self.expression(node.get("right"), env)
            op = node.get("operator")
            lt, rt = left["type"], right["type"]
            if kind == "LogicalExpression":
                if op not in ("&&", "||") or lt.kind != "Boolean" or rt.kind != "Boolean":
                    _fail("PURE_LOWERING_TYPE", "logical", "Logical operators require explicit Boolean operands")
                typ = _Type("Boolean")
            elif op in ("+", "-", "*", "/", "%"):
                if op == "+" and lt.kind == rt.kind == "String":
                    typ = _Type("String")
                elif lt.kind == rt.kind == "Number":
                    typ = _Type("Number")
                else:
                    _fail("PURE_LOWERING_TYPE", "binary", "Arithmetic requires same-type Number operands; + also supports String+String")
            elif op in ("<", "<=", ">", ">="):
                if lt.kind != rt.kind or lt.kind not in ("Number", "String"):
                    _fail("PURE_LOWERING_TYPE", "comparison", "Relational comparison requires matching Number or String operands")
                if lt.kind == "String":
                    _fail("PURE_LOWERING_UNSUPPORTED", "comparison", "Cross-runtime string ordering is not guaranteed")
                typ = _Type("Boolean")
            elif op in ("===", "!=="):
                if lt != rt or lt.kind not in ("Number", "Boolean", "String"):
                    _fail("PURE_LOWERING_TYPE", "equality", "Strict equality requires matching primitive types")
                typ = _Type("Boolean")
            else:
                _fail("PURE_LOWERING_UNSUPPORTED", "operator", "Unsupported binary operator")
            return self._node({"kind": "binary", "operator": op, "left": left, "right": right, "type": typ})
        if kind == "UnaryExpression":
            value = self.expression(node.get("argument"), env)
            op = node.get("operator")
            if op == "!" and value["type"].kind == "Boolean":
                typ = _Type("Boolean")
            elif op in ("+", "-") and value["type"].kind == "Number":
                typ = _Type("Number")
            else:
                _fail("PURE_LOWERING_TYPE", "unary", "Unary operator does not match the explicit operand type")
            return self._node({"kind": "unary", "operator": op, "value": value, "type": typ})
        if kind == "ConditionalExpression":
            test = self.expression(node.get("test"), env)
            yes = self.expression(node.get("consequent"), env)
            no = self.expression(node.get("alternate"), env)
            if test["type"].kind != "Boolean" or yes["type"] != no["type"]:
                _fail("PURE_LOWERING_TYPE", "conditional", "Conditional requires a Boolean test and identical branch types")
            return self._node({"kind": "conditional", "test": test, "yes": yes, "no": no, "type": yes["type"]})
        if kind == "CallExpression":
            return self._array_call(node, env)
        _fail("PURE_LOWERING_UNSUPPORTED", str(kind), "Expression node is outside the pure typed subset")

    def _callback(self, fn: dict[str, Any], expected_types: tuple[_Type, ...], env: dict[str, tuple[_Type, str]]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, tuple[_Type, str]]]:
        if fn.get("type") not in ("ArrowFunctionExpression", "FunctionExpression") or fn.get("async") or fn.get("generator"):
            _fail("PURE_LOWERING_CALLBACK", "callback", "Array callbacks must be synchronous functions")
        params = fn.get("params", [])
        if len(params) != len(expected_types) or any(p.get("type") != "Identifier" or not p.get("bindingId") for p in params):
            _fail("PURE_LOWERING_CALLBACK", "callback.params", "Callback arity and binding types must match the array operation")
        nested = dict(env)
        rows = []
        for p, typ in zip(params, expected_types):
            binding = p["bindingId"]
            while True:
                self.callback_index += 1
                target = "pureValue" + str(self.callback_index)
                if target not in self.used_callback_names:
                    break
            self.used_callback_names.add(target)
            rows.append({"sourceName": p["name"], "bindingId": binding, "type": typ,
                         "targetNames": {"unity": target, "creator": target}})
            nested[binding] = (typ, {"unity": target, "creator": target, "source": p["name"]})
        return self.body_expression(fn), rows, nested

    def _array_call(self, node: dict[str, Any], env: dict[str, tuple[_Type, str]]) -> dict[str, Any]:
        callee = node.get("callee", {})
        if callee.get("type") != "MemberExpression" or callee.get("computed") or callee.get("optional"):
            _fail("PURE_LOWERING_CALL", "callee", "Only direct Array.filter and Array.sort calls are supported")
        prop = callee.get("property", {}).get("name")
        args = node.get("arguments", [])
        if len(args) != 1 or args[0].get("type") == "SpreadElement":
            _fail("PURE_LOWERING_CALL", str(prop), "Array operation requires exactly one non-spread callback")
        array = self.expression(callee.get("object"), env)
        if array["type"].kind != "Array":
            _fail("PURE_LOWERING_TYPE", str(prop), "Array operation receiver requires an explicit Array<Record> type")
        item_type = _Type("Record", array["type"].name)
        if prop == "filter":
            callback_ast, callback_params, nested = self._callback(args[0], (item_type,), env)
            predicate = self.expression(callback_ast, nested)
            if predicate["type"].kind != "Boolean":
                _fail("PURE_LOWERING_FILTER", "filter", "Filter predicate must be explicitly Boolean")
            return self._node({"kind": "filter", "array": array, "predicate": predicate, "callbackParameters": callback_params,
                               "type": array["type"], "fresh": True})
        if prop == "sort":
            if not array.get("fresh"):
                _fail("PURE_LOWERING_SORT_MUTATION", "sort", "Sorting the input array would mutate caller-owned data; sort only a fresh filter result")
            callback_ast, callback_params, nested = self._callback(args[0], (item_type, item_type), env)
            comparator = self._sort_comparator(callback_ast, callback_params, nested)
            return self._node({"kind": "sort", "array": array, "comparator": comparator, "callbackParameters": callback_params,
                               "type": array["type"], "fresh": True, "stable": True})
        _fail("PURE_LOWERING_CALL", str(prop), "Unknown array call; no generic calls or host APIs are executed")

    def _sort_comparator(self, body: dict[str, Any], params: list[dict[str, Any]], env: dict[str, tuple[_Type, str]]) -> dict[str, Any]:
        left_name, right_name = params[0]["sourceName"], params[1]["sourceName"]
        first_id, second_id = params[0]["bindingId"], params[1]["bindingId"]
        record_type = params[0]["type"]
        if record_type != params[1]["type"] or record_type.kind != "Record":
            _fail("PURE_LOWERING_SORT_COMPARATOR", "sort", "Comparator parameters must have the same declared record type")
        is_difference = body.get("type") == "BinaryExpression" and body.get("operator") == "-"
        first = self._sort_field(body.get("left"), first_id, record_type) if is_difference else None
        second = self._sort_field(body.get("right"), second_id, record_type) if is_difference else None
        first_right = self._sort_field(body.get("right"), first_id, record_type) if is_difference else None
        second_left = self._sort_field(body.get("left"), second_id, record_type) if is_difference else None
        if first and second and first["sourceField"] == second["sourceField"] and first["type"].kind == "Number":
            return {"kind": "sortComparator", "field": first["sourceField"], "direction": "ascending", "form": "difference"}
        if first_right and second_left and first_right["sourceField"] == second_left["sourceField"] and first_right["type"].kind == "Number":
            return {"kind": "sortComparator", "field": first_right["sourceField"], "direction": "descending", "form": "difference"}
        node = body
        if node.get("type") != "ConditionalExpression" or node.get("alternate", {}).get("type") != "ConditionalExpression":
            _fail("PURE_LOWERING_SORT_COMPARATOR", "sort", "Comparator must be one numeric-field difference or explicit three-way numeric-field comparison")
        test1, test2 = node["test"], node["alternate"]["test"]
        field1 = self._same_comparator_fields(test1, first_id, second_id, record_type)
        field2 = self._same_comparator_fields(test2, first_id, second_id, record_type)
        if not field1 or not field2 or field1["sourceField"] != field2["sourceField"] or field1["type"].kind != "Number":
            _fail("PURE_LOWERING_SORT_COMPARATOR", "sort", "Three-way comparator must compare one declared Number field of its two callback records")
        op1, op2 = test1.get("operator"), test2.get("operator")
        yes = self._numeric_constant(node.get("consequent", {}))
        mid = self._numeric_constant(node["alternate"].get("consequent", {}))
        no = self._numeric_constant(node["alternate"].get("alternate", {}))
        if ({op1, op2} != {"<", ">"} or type(yes) not in (int, float) or type(mid) not in (int, float) or
                type(no) not in (int, float) or (yes, mid, no) not in ((-1, 1, 0), (1, -1, 0))):
            _fail("PURE_LOWERING_SORT_COMPARATOR", "sort", "Three-way comparator must return exact -1/1/0 in opposite field comparison branches")
        ascending = (op1 == "<" and yes == -1) or (op1 == ">" and yes == 1)
        return {"kind": "sortComparator", "field": field1["sourceField"],
                "direction": "ascending" if ascending else "descending", "form": "three-way"}

    @staticmethod
    def _numeric_constant(node: dict[str, Any]) -> int | float | None:
        if not isinstance(node, dict):
            return None
        if node.get("type") == "Literal" and type(node.get("value")) in (int, float):
            return node["value"]
        if (node.get("type") == "UnaryExpression" and node.get("operator") == "-" and
                node.get("argument", {}).get("type") == "Literal" and type(node["argument"].get("value")) in (int, float)):
            return -node["argument"]["value"]
        return None

    def _sort_field(self, node: dict[str, Any] | None, binding_id: str, record_type: _Type) -> dict[str, Any] | None:
        if not isinstance(node, dict) or node.get("type") != "MemberExpression" or node.get("computed"):
            return None
        receiver = node.get("object", {})
        if receiver.get("type") != "Identifier" or receiver.get("bindingId") != binding_id:
            return None
        field_name = node.get("property", {}).get("name")
        field = self.records[record_type.name]["fields"].get(field_name)
        return {"sourceField": field_name, "type": field["type"]} if field else None

    def _same_comparator_fields(self, test: dict[str, Any], first_id: str, second_id: str, record_type: _Type) -> dict[str, Any] | None:
        if not isinstance(test, dict) or test.get("type") != "BinaryExpression" or test.get("operator") not in ("<", ">"):
            return None
        left = self._sort_field(test.get("left"), first_id, record_type)
        right = self._sort_field(test.get("right"), second_id, record_type)
        if left and right and left["sourceField"] == right["sourceField"]:
            return left
        return None


def _emit_expr(node: dict[str, Any], target: str) -> str:
    kind = node["kind"]
    typ = node["type"]
    if kind == "literal":
        if typ.kind == "String":
            return json.dumps(node["value"], ensure_ascii=True)
        if typ.kind == "Boolean":
            return "true" if node["value"] else "false"
        value = repr(float(node["value"]))
        if target == "unity":
            value += "d"
        return value
    if kind == "identifier":
        name = node["targetNames"][target]
        if typ.kind == "Number":
            return _finite(target, name, "parameter " + node["sourceName"])
        return name
    if kind == "field":
        base = _emit_expr(node["object"], target)
        name = node["targetNames"][target]
        access = base + "." + name
        if typ.kind == "Number":
            return _finite(target, access, "field " + node["sourceField"])
        return access
    if kind == "unary":
        operand = _emit_expr(node["value"], target)
        value = f"({node['operator']}{operand})"
        return _finite(target, value, "unary result") if typ.kind == "Number" else value
    if kind == "binary":
        left = _emit_expr(node["left"], target)
        right = _emit_expr(node["right"], target)
        op = ({"===": "==", "!==": "!="}.get(node["operator"], node["operator"]) if target == "unity" else node["operator"])
        value = f"({left} {op} {right})"
        return _finite(target, value, "numeric result") if typ.kind == "Number" else value
    if kind == "conditional":
        test = _emit_expr(node["test"], target)
        yes = _emit_expr(node["yes"], target)
        no = _emit_expr(node["no"], target)
        return f"({test} ? {yes} : {no})"
    if kind == "filter":
        value = _emit_expr(node["array"], target)
        param = node["callbackParameters"][0]["targetNames"][target]
        predicate = _emit_expr(node["predicate"], target)
        method = "Filter" if target == "unity" else "filter"
        return f"PureSequence.{method}({value}, {param} => {predicate})"
    if kind == "sort":
        value = _emit_expr(node["array"], target)
        params = [row["targetNames"][target] for row in node["callbackParameters"]]
        cmp = node["comparator"]
        field_info = node["_recordFields"][cmp["field"]]
        a = f"{params[0]}.{field_info[target]}"
        b = f"{params[1]}.{field_info[target]}"
        a = _finite(target, a, "sort key " + cmp["field"])
        b = _finite(target, b, "sort key " + cmp["field"])
        if cmp["form"] == "three-way":
            if cmp["direction"] == "ascending":
                comparator = f"({a} < {b} ? -1 : {a} > {b} ? 1 : 0)"
            else:
                comparator = f"({a} > {b} ? -1 : {a} < {b} ? 1 : 0)"
        else:
            sign = "1" if cmp["direction"] == "ascending" else "-1"
            comparator = _finite(target, f"(({a} - {b}) * {sign})", "sort comparator")
        method = "StableSort" if target == "unity" else "stableSort"
        return f"PureSequence.{method}({value}, ({params[0]}, {params[1]}) => {comparator})"
    _fail("PURE_LOWERING_IR", kind, "Unknown typed expression IR node")


def _finite(target: str, expression: str, location: str) -> str:
    method = "RequireFinite" if target == "unity" else "requireFinite"
    return "PureSequence." + method + "(" + expression + ", " + json.dumps(location) + ")"


def _render(ir: dict[str, Any], contract: dict[str, Any], target: str) -> tuple[bytes, bytes]:
    namespace = contract["namespace"]
    class_name = contract["className"]
    method_name = contract["methodName"]
    records = contract["records"]
    params = ir["parameters"]
    if target == "unity":
        param_text = ", ".join(_target_type(p["type"], target, records) + " " + p[target] for p in params)
        return_type = _target_type(ir["returnType"], target, records)
        body = _emit_expr(ir["expression"], target)
        text = ("using System;\nusing System.Collections.Generic;\n\nnamespace " + namespace + "\n{\n"
                + "    public static class " + class_name + "\n    {\n"
                + "        public static " + return_type + " " + method_name + "(" + param_text + ")\n        {\n"
                + "            return " + body + ";\n        }\n    }\n}\n")
        helper = (TEMPLATE_ROOT / "PureSequence.cs").read_bytes().decode("utf-8").replace("{{NAMESPACE}}", namespace).encode("utf-8")
        return text.encode("utf-8"), helper
    param_text = ", ".join(p["creator"] + ": " + _target_type(p["type"], target, records) for p in params)
    return_type = _target_type(ir["returnType"], target, records)
    body = _emit_expr(ir["expression"], target)
    text = ("import { PureSequence } from \"./PureSequence\";\n\nexport class " + class_name + " {\n"
            + "    static " + method_name + "(" + param_text + "): " + return_type + " {\n"
            + "        return " + body + ";\n    }\n}\n")
    helper = (TEMPLATE_ROOT / "PureSequence.ts").read_bytes()
    return text.encode("utf-8"), helper


def _ir_type(typ: _Type) -> dict[str, Any]:
    return {"kind": typ.kind, **({"name": typ.name} if typ.name else {})}


def prepare_pure_lowering(
    source_path: str | Path,
    selector: dict[str, str],
    contract: dict[str, Any],
    output: str | Path,
    *,
    expected_source_sha256: str,
    namespace: str,
    class_name: str,
    method_name: str,
) -> dict[str, Any]:
    """Lower one exact source method to a fresh Unity/Cocos pure-expression candidate.

    The method must be a synchronous static class function with one returned
    expression. The typed contract is complete and strict; it is not inferred
    from source names, comments, UUIDs, or examples.
    """
    source = io.safe(source_path)
    if not isinstance(expected_source_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_source_sha256):
        _fail("PURE_LOWERING_SOURCE_PIN", str(source), "Expected a lowercase SHA-256 source pin")
    raw = io.read(source, max_bytes=_MAX_SOURCE_BYTES)
    if _sha(raw) != expected_source_sha256:
        _fail("PURE_LOWERING_SOURCE_PIN", source.name, "Source bytes differ from the required SHA-256")
    if not isinstance(selector, dict) or set(selector) != {"classId", "methodId"} or not all(isinstance(v, str) for v in selector.values()):
        _fail("PURE_LOWERING_SELECTOR", "selector", "Expected exact classId and methodId")
    normalized_contract = _validate_contract(contract, namespace, class_name, method_name)
    contract_raw = io.encoded(contract)
    if len(contract_raw) > _MAX_CONTRACT_BYTES:
        _fail("PURE_LOWERING_CONTRACT_BUDGET", "contract", "Typed contract exceeds its byte budget")
    io.load(contract_raw, max_nodes=_MAX_CONTRACT_NODES)
    graph = facts(source, expected_source_sha256, [selector["methodId"]])
    selected = [row for row in graph.get("selected", []) if row.get("method", {}).get("id") == selector["methodId"]]
    if len(selected) != 1 or selected[0]["method"].get("classId") != selector["classId"]:
        _fail("PURE_LOWERING_SELECTOR", selector["methodId"], "Exact method/class pair is absent or ambiguous")
    method = selected[0]["method"]
    ast = selected[0]["ast"]
    if method.get("async") or method.get("generator"):
        _fail("PURE_LOWERING_UNSUPPORTED", method["id"], "Async and generator methods are not pure-expression candidates")
    span = method.get("functionBytes", {})
    if (type(span.get("start")) is not int or type(span.get("end")) is not int or
            not 0 <= span["start"] < span["end"] <= len(raw) or
            ast.get("start") != span["start"] or ast.get("end") != span["end"]):
        _fail("PURE_LOWERING_METHOD_SPAN", method["id"], "Function AST and exact source byte span differ")
    ast_params = ast.get("params", [])
    if len(ast_params) != len(normalized_contract["parameters"]):
        _fail("PURE_LOWERING_SIGNATURE", method["id"], "Parameter count differs from typed contract")
    env: dict[str, tuple[_Type, str]] = {}
    parameters = []
    for i, (ast_param, declared) in enumerate(zip(ast_params, normalized_contract["parameters"])):
        if ast_param.get("type") != "Identifier" or ast_param.get("name") != declared["source"] or not ast_param.get("bindingId"):
            _fail("PURE_LOWERING_SIGNATURE", f"{method['id']}.parameters[{i}]", "Source parameter identity/name differs from typed contract")
        typ = declared["type"]
        env[ast_param["bindingId"]] = (typ, {"unity": declared["unity"], "creator": declared["creator"], "source": declared["source"]})
        parameters.append({**declared, "bindingId": ast_param["bindingId"]})
    builder = _Builder(normalized_contract["records"],
                       [name for row in normalized_contract["parameters"] for name in (row["unity"], row["creator"])])
    try:
        expression_ast = builder.body_expression(ast)
        expression = builder.expression(expression_ast, env)
    except RecursionError:
        _fail("PURE_LOWERING_DEPTH_BUDGET", method["id"], "Expression nesting exceeds the bounded lowering depth")
    if expression["type"] != normalized_contract["returns"]:
        _fail("PURE_LOWERING_RETURN_TYPE", method["id"], "Expression type differs from the explicit return type")
    def type_names(node: dict[str, Any]) -> None:
        if node["kind"] == "sort":
            node["_recordFields"] = normalized_contract["records"][node["type"].name]["fields"]
        for value in node.values():
            if isinstance(value, dict) and "kind" in value and "type" in value:
                type_names(value)
            elif isinstance(value, list):
                for row in value:
                    if isinstance(row, dict) and "kind" in row and "type" in row:
                        type_names(row)
    try:
        type_names(expression)
    except RecursionError:
        _fail("PURE_LOWERING_DEPTH_BUDGET", method["id"], "Typed IR nesting exceeds the bounded traversal depth")
    ir = {"schemaVersion": 1, "kind": "typed-pure-function", "parameters": parameters,
          "returnType": normalized_contract["returns"], "expression": expression,
          "semantics": {"arrayFilter": "stable source order; new array", "arraySort": "stable; filter-produced arrays only",
                        "numbers": "finite IEEE-754 binary64 checked at runtime", "coercion": "none"}}
    public_ir = _clean_ir(ir)
    try:
        unity_source, unity_helper = _render(ir, normalized_contract, "unity")
        creator_source, creator_helper = _render(ir, normalized_contract, "creator")
    except RecursionError:
        _fail("PURE_LOWERING_DEPTH_BUDGET", method["id"], "Target rendering exceeds the bounded expression depth")
    inputs = [source]
    output_path = io.new_output(output, inputs)
    committed = False
    try:
        namespace_dir = Path(*namespace.split("."))
        outputs = [
            ("Targets/Unity/" + namespace_dir.as_posix() + "/" + class_name + ".cs", unity_source),
            ("Targets/Unity/" + namespace_dir.as_posix() + "/PureSequence.cs", unity_helper),
            ("Targets/Creator/" + namespace_dir.as_posix() + "/" + class_name + ".ts", creator_source),
            ("Targets/Creator/" + namespace_dir.as_posix() + "/PureSequence.ts", creator_helper),
            ("IR/pure-function.json", io.encoded(public_ir)),
        ]
        emitted = []
        for relative, data in outputs:
            destination = io.inside(output_path, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            emitted.append({"path": relative, "sha256": _sha(data), "bytes": len(data)})
        report = {"schemaVersion": SCHEMA, "candidateKind": "typed-pure-expression",
                  "status": "candidate", "sourceExecuted": False,
                  "source": {"sha256": expected_source_sha256, "bytes": len(raw), "pathLabel": source.name},
                  "method": {"classId": method["classId"], "methodId": method["id"], "name": method["name"],
                             "sourceSha256": method["sourceSha256"], "functionSha256": _sha(raw[span["start"]:span["end"]]),
                             "sourceBytes": method["sourceBytes"], "functionBytes": span},
                  "contractSha256": _sha(contract_raw), "semanticIrSha256": _sha(io.encoded(public_ir)),
                  "contract": _contract_report(normalized_contract), "semanticScope": "finite numeric/boolean/field expression; typed filter; field-keyed stable sort",
                  "limitations": ["Input numeric fields/parameters must be finite; generated code throws on NaN/Infinity.",
                                  "Sort is supported only on arrays created by filter in this expression, so caller-owned input is never mutated.",
                                  "Sort comparators are constrained to one Number record field and direction is extracted from the AST.",
                                  "Record declarations must exist in the target domain and match the explicit field mapping."],
                  "generatedFiles": emitted, "diagnostics": []}
        report = io.finish(output_path, report)
        committed = True
        return {"output": str(output_path), "manifestPath": str(output_path / "manifest.json"),
                "status": "candidate", "sourceExecuted": False, "ir": public_ir, "files": emitted, "manifest": report}
    except Exception:
        if not committed and output_path.exists():
            shutil.rmtree(output_path)
        raise


def _clean_ir(value: Any) -> Any:
    if isinstance(value, _Type):
        return _ir_type(value)
    if isinstance(value, dict):
        return {key: _clean_ir(item) for key, item in value.items() if key not in ("bindingId", "targetNames", "_recordFields")}
    if isinstance(value, list):
        return [_clean_ir(item) for item in value]
    return value


def _contract_report(contract: dict[str, Any]) -> dict[str, Any]:
    return {"schemaVersion": 1, "namespace": contract["namespace"], "className": contract["className"],
            "methodName": contract["methodName"],
            "parameters": [{"source": p["source"], "type": _ir_type(p["type"]), "unity": p["unity"], "creator": p["creator"]}
                           for p in contract["parameters"]],
            "returns": _ir_type(contract["returns"]),
            "records": {name: {"unityType": row["unityType"], "creatorType": row["creatorType"],
                               "fields": {field: {"type": _ir_type(spec["type"]), "unity": spec["unity"], "creator": spec["creator"]}
                                          for field, spec in row["fields"].items()}}
                        for name, row in contract["records"].items()}}


prepare = prepare_pure_lowering
