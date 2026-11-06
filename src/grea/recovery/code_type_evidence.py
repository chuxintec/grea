"""Conservative, source-bound inference of a small explicit JS type domain.

This is evidence extraction for the typed module contract, not a JavaScript
type system. Unknown dynamic behavior remains a named gap; the source is only
parsed by the bounded static code graph and is never executed.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

from .code_graph import facts
from .code_semantics import parse_type
from .io import encoded, load, safe
from .sources.compiled import ParseError, fail

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_MAX_ROOTS = 16
_MAX_METHODS = 64
_MAX_PASSES = 12
_PRIMITIVES = {"Number", "Boolean", "String", "Void"}


def _read_seed(seed):
    if seed is None: return None
    if isinstance(seed, dict): raw = encoded(seed)
    elif isinstance(seed, bytes): raw = seed
    elif isinstance(seed, (str, Path)):
        from .io import read
        raw = read(seed, max_bytes=128 * 1024)
    else: fail("CODE_TYPE_EVIDENCE_SEED", "$", "Expected schema-1 typed contract mapping, bytes, path, or None")
    if len(raw) > 128 * 1024: fail("CODE_TYPE_EVIDENCE_BUDGET", "$", "Typed evidence exceeds 128 KiB")
    doc = load(raw, max_nodes=40_000, max_depth=48)
    if not isinstance(doc, dict) or doc.get("schemaVersion") != 1:
        fail("CODE_TYPE_EVIDENCE_SEED", "$", "Expected schemaVersion 1 typed module contract")
    if not isinstance(doc.get("sourceSha256"), str) or not _HEX.fullmatch(doc["sourceSha256"]):
        fail("CODE_TYPE_EVIDENCE_SEED", "sourceSha256", "Expected exact lowercase source SHA256")
    if not isinstance(doc.get("modules"), list) or len(doc["modules"]) > _MAX_METHODS:
        fail("CODE_TYPE_EVIDENCE_SEED", "modules", "Expected bounded module array")
    methods, modules = {}, {}
    for module in doc["modules"]:
        if not isinstance(module, dict) or not all(isinstance(module.get(k), str) for k in ("id", "targetClass", "classId", "classSha256")):
            fail("CODE_TYPE_EVIDENCE_SEED", "modules", "Each module requires exact source and target identities")
        if module["classId"] in modules: fail("CODE_TYPE_EVIDENCE_SEED", module["classId"], "Duplicate class identity")
        modules[module["classId"]] = module
        fields = module.get("fields", {})
        if not isinstance(fields, dict): fail("CODE_TYPE_EVIDENCE_SEED", module["classId"], "Expected field type map")
        for method in module.get("methods", []):
            if not isinstance(method, dict) or not all(isinstance(method.get(k), str) for k in ("id", "name", "sha256")) or "returns" not in method:
                fail("CODE_TYPE_EVIDENCE_SEED", module["id"], "Seed method requires id/name/hash and a returns field (type or null)")
            if method["id"] in methods: fail("CODE_TYPE_EVIDENCE_SEED", method["id"], "Duplicate method identity")
            if not isinstance(method.get("parameters"), list) or any(value is not None and not isinstance(value, str) for value in method["parameters"]):
                fail("CODE_TYPE_EVIDENCE_SEED", method["id"], "Expected parameter type strings or null placeholders")
            if method.get("returns") is not None and not isinstance(method["returns"], str):
                fail("CODE_TYPE_EVIDENCE_SEED", method["id"], "Expected return type string or null placeholder")
            if not isinstance(method.get("locals", {}), dict) or any(value is not None and not isinstance(value, str) for value in method.get("locals", {}).values()):
                fail("CODE_TYPE_EVIDENCE_SEED", method["id"], "Expected local type strings or null placeholders")
            methods[method["id"]] = (module, method)
    names = [row["targetClass"] for row in modules.values()] + [row.get("name") for row in doc.get("records", []) if isinstance(row, dict)]
    for cid, module in modules.items():
        for field, typ in module.get("fields", {}).items():
            if typ is None: continue
            try: parse_type(typ, names)
            except ParseError as exc: fail("CODE_TYPE_EVIDENCE_SEED", f"{cid}.fields.{field}", exc.message)
    for mid, (module, method) in methods.items():
        for i, typ in enumerate(method.get("parameters", [])):
            if typ is None: continue
            try: parse_type(typ, names)
            except ParseError as exc: fail("CODE_TYPE_EVIDENCE_SEED", f"{mid}.parameters[{i}]", exc.message)
        if method["returns"] is not None:
            try: parse_type(method["returns"], names)
            except ParseError as exc: fail("CODE_TYPE_EVIDENCE_SEED", mid + ".returns", exc.message)
        for key, typ in method.get("locals", {}).items():
            if typ is None: continue
            try: parse_type(typ, names)
            except ParseError as exc: fail("CODE_TYPE_EVIDENCE_SEED", f"{mid}.locals.{key}", exc.message)
    return doc, methods, modules


def _diagnostic(code, location, message, method_id=None, source_bytes=None):
    row = {"code": code, "location": location, "message": message}
    if method_id: row["methodId"] = method_id
    if source_bytes: row["sourceBytes"] = source_bytes
    return row


def _class_dependencies(graph, ids, seed_methods=None, seed_spec=None):
    classes = {row["id"]: row for row in graph.get("classes", [])}
    class_by_binding = {}
    for cls in classes.values():
        for binding in (cls.get("bindingId"), cls.get("constructorBindingId")):
            if binding: class_by_binding[binding] = cls["id"]
    bindings = {cid: {row["name"]: row for row in cls.get("methodBindings", [])} for cid, cls in classes.items()}
    methods = {row["id"]: row for row in graph.get("methods", [])}
    asts = {row["method"]["id"]: row["ast"] for row in graph.get("selected", [])}
    edges, unresolved = {}, []
    for mid in sorted(ids):
        method = methods.get(mid)
        if not method: continue
        edges[mid] = set()
        dead_starts = set()
        if seed_methods and seed_spec and mid in seed_methods and mid in asts:
            from .code_selection import _non_null_or_right_calls
            module, seed_method = seed_methods[mid]
            if module["classId"] == method.get("classId") and seed_method["sha256"] == method.get("sourceSha256"):
                dead_starts = _non_null_or_right_calls(asts[mid], seed_method, module, seed_spec)
        for call in method.get("calls", []):
            if call.get("sourceBytes", {}).get("start") in dead_starts: continue
            cls_id = method.get("classId") if call.get("receiver") == "this" else class_by_binding.get(call.get("bindingId"))
            if not cls_id: continue
            member = call.get("member")
            if not isinstance(member, str) or call.get("computed"):
                unresolved.append((mid, call))
                continue
            target = bindings.get(cls_id, {}).get(member) if isinstance(member, str) else None
            if target and target["id"] != mid:
                edges[mid].add(target["id"])
    return edges, unresolved


def _literal_type(node):
    if node.get("type") != "Literal": return None
    value = node.get("value")
    if type(value) in (int, float): return "Number"
    if type(value) is bool: return "Boolean"
    if isinstance(value, str): return "String"
    return None


def _walk_method(node):
    """Walk one method body without attributing nested function scopes to it."""
    pending = [node]
    while pending:
        current = pending.pop()
        if not isinstance(current, dict): continue
        yield current
        if current is not node and current.get("type") in ("FunctionExpression", "FunctionDeclaration", "ArrowFunctionExpression"):
            continue
        for key, value in current.items():
            if key in ("start", "end"): continue
            if isinstance(value, dict) and "type" in value: pending.append(value)
            elif isinstance(value, list): pending.extend(x for x in value if isinstance(x, dict) and "type" in x)


def _type_record_names(types, record_rows, class_names):
    by_name = {row["name"]: row for row in record_rows if isinstance(row, dict) and isinstance(row.get("name"), str)}
    names = list(class_names) + list(by_name)
    pending, needed = list(types), set()
    while pending:
        text = pending.pop()
        try: typ = parse_type(text, names)
        except ParseError: continue
        stack = [typ]
        while stack:
            current = stack.pop()
            if current.kind in by_name and current.kind not in needed:
                needed.add(current.kind)
                pending.extend(by_name[current.kind].get("fields", {}).values())
            stack.extend(current.args)
    return [copy.deepcopy(by_name[name]) for name in sorted(needed)]


def _ast_property_names(ast):
    names = set()
    pending = [ast]
    nodes = []
    while pending:
        node = pending.pop()
        if not isinstance(node, dict): continue
        nodes.append(node)
        for value in node.values():
            if isinstance(value, dict) and "type" in value: pending.append(value)
            elif isinstance(value, list): pending.extend(x for x in value if isinstance(x, dict) and "type" in x)
    for node in nodes:
        if node.get("type") == "MemberExpression" and not node.get("computed"):
            name = node.get("property", {}).get("name")
            if isinstance(name, str): names.add(name)
        elif node.get("type") == "ObjectExpression":
            for prop in node.get("properties", []):
                if prop.get("type") == "Property" and not prop.get("computed"):
                    name = prop.get("key", {}).get("name")
                    if isinstance(name, str): names.add(name)
    return names


class _Infer:
    def __init__(self, methods, asts, seed_methods, classes, namespace):
        self.methods, self.asts, self.seed_methods = methods, asts, seed_methods
        self.classes = classes
        self.namespace = namespace
        self.vars = {mid: {} for mid in methods}
        self.var_evidence = {mid: {} for mid in methods}
        self.returns = {mid: None for mid in methods}
        self.return_evidence = {mid: [] for mid in methods}
        self.conflicts, self.gaps, self.unsupported = [], [], []
        self.seed_valid = set()
        self.module_fields = {}
        self.module_field_evidence = {}
        self.method_classes = {mid: row.get("classId") for mid, row in methods.items()}
        self.class_bindings = {}
        for cid, cls in classes.items():
            self.class_bindings[cls.get("bindingId")] = cid
            self.class_bindings[cls.get("constructorBindingId")] = cid
        self.method_ids_by_class_name = {}
        for cls in classes.values():
            for row in cls.get("methodBindings", []): self.method_ids_by_class_name[(cls["id"], row["name"])] = row["id"]
        for module, _ in seed_methods.values():
            cid = module.get("classId")
            cls = classes.get(cid, {})
            if cid and module.get("classSha256") == cls.get("sourceSha256") and cid not in self.module_fields:
                self.module_fields[cid] = copy.deepcopy(module.get("fields", {}))
                self.module_field_evidence[cid] = {
                    key: {"type": typ, "rule": "reviewed-seed", "sourceBytes": cls.get("sourceBytes")}
                    for key, typ in module.get("fields", {}).items()}
        for mid, method in methods.items():
            seed = seed_methods.get(mid)
            if seed:
                module, row = seed
                original = methods[mid]
                original_class = classes.get(original.get("classId"), {})
                if module["classId"] != original.get("classId") or module["classSha256"] != original_class.get("sourceSha256") or row["sha256"] != original["sourceSha256"]:
                    self.gaps.append(_diagnostic("CODE_TYPE_EVIDENCE_SEED_IDENTITY", mid, "Seed type does not match exact source class/method hash", mid))
                    continue
                ast = asts[mid]
                for i, typ in enumerate(row.get("parameters", [])):
                    if i < len(ast.get("params", [])):
                        self.set(mid, ast["params"][i].get("bindingId"), typ, "reviewed-seed", original["sourceBytes"])
                self.returns[mid] = row.get("returns")
                self.return_evidence[mid].append({"rule": "reviewed-seed", "sourceBytes": original["sourceBytes"]})
                for node in _walk_method(ast.get("body", {})):
                    if node.get("type") == "VariableDeclarator" and node.get("id", {}).get("type") == "Identifier":
                        ident = node["id"]
                        typ = row.get("locals", {}).get(ident.get("bindingId"), row.get("locals", {}).get(ident.get("name")))
                        if typ: self.set(mid, ident.get("bindingId"), typ, "reviewed-seed", original["sourceBytes"])
                self.module_fields[original["classId"]] = copy.deepcopy(module.get("fields", {}))
                self.module_field_evidence[original["classId"]] = {
                    key: {"type": typ, "rule": "reviewed-seed", "sourceBytes": original["sourceBytes"]}
                    for key, typ in module.get("fields", {}).items()}
                local_ids = [node.get("id", {}) for node in _walk_method(ast.get("body", {}))
                             if node.get("type") == "VariableDeclarator" and node.get("id", {}).get("type") == "Identifier"]
                locals_complete = all(row.get("locals", {}).get(local.get("bindingId"), row.get("locals", {}).get(local.get("name")))
                                      for local in local_ids)
                if len(row.get("parameters", [])) == len(ast.get("params", [])) and all(row.get("parameters", [])) and row.get("returns") and locals_complete:
                    self.seed_valid.add(mid)

    def set(self, mid, binding, typ, rule, span):
        if not binding or not isinstance(typ, str): return False
        current = self.vars[mid].get(binding)
        if current and current != typ:
            diag = _diagnostic("CODE_TYPE_EVIDENCE_CONFLICT", mid + ":" + binding,
                               f"Conflicting proven types {current} and {typ}", mid, span)
            if diag not in self.conflicts: self.conflicts.append(diag)
            return False
        if not current:
            self.vars[mid][binding] = typ
            self.var_evidence[mid][binding] = {"type": typ, "rule": rule, "sourceBytes": span}
            return True
        return False

    def constrain(self, mid, node, typ, rule):
        if node.get("type") == "Identifier": return self.set(mid, node.get("bindingId"), typ, rule, {"start": node.get("start"), "end": node.get("end")})
        known = self.expr(mid, node)
        if known and known != typ:
            diag = _diagnostic("CODE_TYPE_EVIDENCE_CONFLICT", mid + ":" + str(node.get("start")),
                               f"Expected {typ}, found {known}", mid, {"start": node.get("start"), "end": node.get("end")})
            if diag not in self.conflicts: self.conflicts.append(diag)
        return False

    def target(self, mid, node):
        if node.get("type") != "CallExpression": return None
        callee = node.get("callee", {})
        if callee.get("type") != "MemberExpression" or callee.get("computed"): return None
        obj = callee.get("object", {})
        if obj.get("type") == "ThisExpression": cid = self.method_classes.get(mid)
        elif obj.get("type") == "Identifier": cid = self.class_bindings.get(obj.get("bindingId"))
        else: cid = None
        if not cid: return None
        return self.method_ids_by_class_name.get((cid, callee.get("property", {}).get("name")))

    def expr(self, mid, node):
        if not isinstance(node, dict): return None
        kind = node.get("type")
        literal = _literal_type(node)
        if literal: return literal
        if kind == "Identifier": return self.vars[mid].get(node.get("bindingId"))
        if kind in ("ThisExpression",): return "Class:" + str(self.method_classes.get(mid))
        if kind == "UnaryExpression":
            op = node.get("operator")
            if op in ("-", "+"):
                self.constrain(mid, node.get("argument", {}), "Number", "numeric-unary-operator")
                return "Number"
            if op == "!": return "Boolean"
            return None
        if kind == "UpdateExpression":
            self.constrain(mid, node.get("argument", {}), "Number", "numeric-update")
            return "Number"
        if kind == "BinaryExpression":
            op, left, right = node.get("operator"), node.get("left", {}), node.get("right", {})
            lt, rt = self.expr(mid, left), self.expr(mid, right)
            span = {"start": node.get("start"), "end": node.get("end")}
            if op in ("-", "*", "/", "%", "**"):
                self.constrain(mid, left, "Number", "numeric-binary-operator")
                self.constrain(mid, right, "Number", "numeric-binary-operator")
                return "Number"
            if op == "+":
                inferred = lt or rt
                if inferred in ("Number", "String"):
                    self.constrain(mid, left, inferred, "typed-addition")
                    self.constrain(mid, right, inferred, "typed-addition")
                    return inferred
                return None
            if op in ("<", "<=", ">", ">="):
                inferred = lt if lt in ("Number", "String") else rt if rt in ("Number", "String") else None
                if inferred:
                    self.constrain(mid, left, inferred, "typed-relational-operand")
                    self.constrain(mid, right, inferred, "typed-relational-operand")
                return "Boolean"
            if op in ("==", "!=", "===", "!=="): return "Boolean"
            return None
        if kind == "LogicalExpression":
            lt, rt = self.expr(mid, node.get("left", {})), self.expr(mid, node.get("right", {}))
            return lt if lt and lt == rt else None
        if kind == "ConditionalExpression":
            left, right = node.get("consequent", {}), node.get("alternate", {})
            lt, rt = self.expr(mid, left), self.expr(mid, right)
            if lt and not rt: self.constrain(mid, right, lt, "same-typed-conditional-branches")
            if rt and not lt: self.constrain(mid, left, rt, "same-typed-conditional-branches")
            return lt or rt if lt == rt or not lt or not rt else None
        if kind == "SequenceExpression":
            values = node.get("expressions", [])
            return self.expr(mid, values[-1]) if values else None
        if kind == "AssignmentExpression":
            typ = self.expr(mid, node.get("right", {}))
            if typ: self.constrain(mid, node.get("left", {}), typ, "assignment")
            return typ or self.expr(mid, node.get("left", {}))
        if kind == "CallExpression":
            target = self.target(mid, node)
            if target in self.returns:
                callee = self.methods[target]
                params = self.asts[target].get("params", [])
                for i, arg in enumerate(node.get("arguments", [])):
                    if i < len(params):
                        expected = self.vars[target].get(params[i].get("bindingId"))
                        if expected: self.constrain(mid, arg, expected, "direct-source-call-parameter")
                        actual = self.expr(mid, arg)
                        if actual: self.set(target, params[i].get("bindingId"), actual, "direct-source-call-argument", node.get("sourceBytes"))
                return self.returns[target]
            return None
        if kind == "MemberExpression":
            obj = node.get("object", {})
            if obj.get("type") == "ThisExpression":
                return self.module_fields.get(self.method_classes.get(mid), {}).get(node.get("property", {}).get("name"))
            return None
        if kind == "ArrayExpression": return None
        return None

    def run_pass(self, edges):
        changed = False
        for mid, ast in self.asts.items():
            row = self.methods[mid]
            if mid in self.seed_valid:
                continue
            if row.get("async") or row.get("generator") or row.get("factsCoverage"):
                diag = _diagnostic("CODE_TYPE_EVIDENCE_UNSUPPORTED_METHOD", mid,
                                   "Async, generator, or deferred graph method facts are outside supported evidence", mid,
                                   row.get("sourceBytes"))
                if diag not in self.unsupported: self.unsupported.append(diag)
                continue
            body = ast.get("body", {})
            for node in _walk_method(body):
                if node.get("type") in ("FunctionExpression", "ArrowFunctionExpression"):
                    diag = _diagnostic("CODE_TYPE_EVIDENCE_CALLBACK_UNSUPPORTED", mid + ":" + str(node.get("start")),
                                       "Nested callback/function type is outside automatic inference; supply reviewed Function evidence", mid,
                                       {"start": node.get("start"), "end": node.get("end")})
                    if diag not in self.unsupported: self.unsupported.append(diag)
                if node.get("type") == "VariableDeclarator" and node.get("init"):
                    ident, init = node.get("id", {}), node["init"]
                    if ident.get("type") == "Identifier":
                        before = self.vars[mid].get(ident.get("bindingId")); typ = self.expr(mid, init)
                        if typ: self.set(mid, ident.get("bindingId"), typ, "initializer-expression", {"start": node.get("start"), "end": node.get("end")})
                        if before != self.vars[mid].get(ident.get("bindingId")): changed = True
                if node.get("type") == "AssignmentExpression" and node.get("left", {}).get("type") == "MemberExpression":
                    left = node["left"]
                    if left.get("object", {}).get("type") == "ThisExpression" and not left.get("computed"):
                        field = left.get("property", {}).get("name"); typ = self.expr(mid, node.get("right", {}))
                        if field and typ in _PRIMITIVES:
                            fields = self.module_fields.setdefault(self.method_classes.get(mid), {})
                            if field not in fields:
                                fields[field] = typ; changed = True
                                self.module_field_evidence.setdefault(self.method_classes.get(mid), {})[field] = {
                                    "type": typ, "rule": "this-field-primitive-assignment", "sourceBytes": {"start": node.get("start"), "end": node.get("end")}}
                            elif fields[field] != typ:
                                diag = _diagnostic("CODE_TYPE_EVIDENCE_FIELD_CONFLICT", mid + ":" + field, "Conflicting inferred source field types", mid, {"start": node.get("start"), "end": node.get("end")})
                                if diag not in self.conflicts: self.conflicts.append(diag)
                if node.get("type") == "ReturnStatement":
                    value = node.get("argument")
                    typ = "Void" if value is None else self.expr(mid, value)
                    if typ in _PRIMITIVES:
                        current = self.returns.get(mid)
                        if current and current != typ:
                            diag = _diagnostic("CODE_TYPE_EVIDENCE_RETURN_CONFLICT", mid, f"Return paths yield {current} and {typ}", mid, {"start": node.get("start"), "end": node.get("end")})
                            if diag not in self.conflicts: self.conflicts.append(diag)
                        elif not current:
                            self.returns[mid] = typ; self.return_evidence[mid].append({"rule": "return-expression", "sourceBytes": {"start": node.get("start"), "end": node.get("end")}}); changed = True
            for node in _walk_method(body):
                if node.get("type") == "BinaryExpression":
                    self.expr(mid, node)
            if not any(node.get("type") == "ReturnStatement" for node in _walk_method(body)):
                if self.returns.get(mid) is None:
                    self.returns[mid] = "Void"
                    self.return_evidence[mid].append({"rule": "no-value-return", "sourceBytes": row.get("sourceBytes")})
                    changed = True
                elif self.returns[mid] != "Void":
                    diag = _diagnostic("CODE_TYPE_EVIDENCE_RETURN_CONFLICT", mid, "Reviewed return type conflicts with source method having no return statement", mid, row.get("sourceBytes"))
                    if diag not in self.conflicts: self.conflicts.append(diag)
        return changed


def extract_type_evidence(source_path, selectors, type_evidence=None, *, namespace=None):
    """Infer a bounded, explicit primitive contract from exact source ASTs.

    Selectors are exact ``{classId, methodId}`` objects. An optional schema-1
    typed contract supplies reviewed method/field/record types and namespace;
    an explicit ``namespace`` is required when no seed provides one. Direct
    ``this`` and source-constructor member calls are closed iteratively, up to
    64 methods and 12 graph passes.
    """
    seed_result = _read_seed(type_evidence)
    seed = seed_result[0] if seed_result else None
    seed_methods = seed_result[1] if seed_result else {}
    seed_modules = seed_result[2] if seed_result else {}
    if seed and namespace is not None and seed.get("namespace") is not None and namespace != seed.get("namespace"):
        fail("CODE_TYPE_EVIDENCE_NAMESPACE", "namespace", "Override must equal the reviewed seed namespace")
    namespace = (seed.get("namespace") or namespace) if seed else namespace
    if not isinstance(selectors, list) or not 1 <= len(selectors) <= _MAX_ROOTS:
        fail("CODE_TYPE_EVIDENCE_SELECTORS", "selectors", "Expected 1..16 exact class/method selectors")
    roots, seen = [], set()
    for i, row in enumerate(selectors):
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) for k in ("classId", "methodId")):
            fail("CODE_TYPE_EVIDENCE_SELECTORS", f"selectors[{i}]", "Each selector requires classId and methodId")
        key = (row["classId"], row["methodId"])
        if key in seen: fail("CODE_TYPE_EVIDENCE_SELECTORS", f"selectors[{i}]", "Duplicate selector")
        seen.add(key); roots.append(key)
    expected = seed.get("sourceSha256") if seed else None
    ids = {mid for _, mid in roots}
    seed_ids = set(seed_methods)
    if len(seed_ids) > _MAX_METHODS:
        fail("CODE_TYPE_EVIDENCE_BUDGET", "type_evidence", "Seed type evidence covers more than 64 methods")
    diagnostics = []
    graph = None
    try:
        source = safe(Path(source_path))
        for attempt in range(_MAX_PASSES):
            graph = facts(source, expected, sorted(ids | seed_ids))
            expected = graph["source"]["sha256"]
            classes = {c["id"]: c for c in graph.get("classes", [])}
            inventory = {m["id"]: m for m in graph.get("methods", [])}
            for cid, mid in roots:
                if mid not in inventory or inventory[mid].get("classId") != cid:
                    return {"status": "missing_source", "contract": None, "fillableContract": None,
                            "diagnostics": [_diagnostic("CODE_TYPE_EVIDENCE_METHOD_NOT_FOUND", mid, "Exact source method/class identity is absent", mid)], "sourceExecuted": False}
            edges, _ = _class_dependencies(graph, ids, seed_methods, seed)
            new = set().union(*edges.values()) - ids if edges else set()
            if not new: break
            if len(ids | new) > _MAX_METHODS:
                diagnostics.append(_diagnostic("CODE_TYPE_EVIDENCE_METHOD_BUDGET", "$", "Direct source method closure exceeds 64 methods")); break
            ids.update(new)
        else:
            diagnostics.append(_diagnostic("CODE_TYPE_EVIDENCE_DEPTH_BUDGET", "$", "Direct source method closure exceeded 12 graph passes"))
    except ParseError as exc:
        status = "unsupported_semantics" if exc.code in {"CODE_GRAPH_PARSE_FAILED", "CODE_GRAPH_TIME_BUDGET", "CODE_GRAPH_OUTPUT_BUDGET"} else "missing_source"
        return {"status": status, "contract": None, "fillableContract": None,
                "diagnostics": [_diagnostic(exc.code, exc.location, exc.message)], "sourceExecuted": False}
    assert graph is not None
    selected_all = {r["method"]["id"]: r["ast"] for r in graph.get("selected", [])}
    selected = {mid: selected_all[mid] for mid in ids if mid in selected_all}
    methods = {row["id"]: row for row in graph.get("methods", []) if row["id"] in ids}
    classes = {row["id"]: row for row in graph.get("classes", [])}
    edges, _ = _class_dependencies(graph, ids, seed_methods, seed)
    infer = _Infer(methods, selected, seed_methods, classes, namespace)
    for _ in range(16):
        if not infer.run_pass(edges): break
    diagnostics.extend(infer.conflicts)
    diagnostics.extend(infer.unsupported)
    diagnostics.extend(infer.gaps)
    _, unsupported_calls = _class_dependencies(graph, ids, seed_methods, seed)
    for mid, call in unsupported_calls:
        diagnostics.append(_diagnostic("CODE_TYPE_EVIDENCE_UNSUPPORTED_DYNAMIC_CALL", mid,
                                       "Computed source-class method call cannot be closed statically", mid,
                                       call.get("sourceBytes")))
    if not namespace:
        diagnostics.append(_diagnostic("CODE_TYPE_EVIDENCE_NAMESPACE_MISSING", "namespace", "Supply an explicit target namespace or reviewed seed"))
    # Emit fully typed methods only; incomplete methods stay in a fillable report
    # with exact, named holes rather than invalid code_modules placeholders.
    modules, fillable, evidence = {}, [], []
    fillable_modules, missing_evidence = {}, []
    for mid in sorted(ids):
        row = methods.get(mid)
        if not row: continue
        cid = row.get("classId")
        cls = classes.get(cid)
        if not cls: continue
        seed_module, seed_method = seed_methods.get(mid, ({}, {}))
        ast = selected.get(mid, {})
        fillable_module = fillable_modules.setdefault(cid, {"id": seed_module.get("id", cls["name"]),
            "targetClass": seed_module.get("targetClass", cls["name"]), "classId": cid,
            "classSha256": cls["sourceSha256"],
            "fields": copy.deepcopy(infer.module_fields.get(cid, {})), "methods": []})
        for field, typ in sorted(fillable_module["fields"].items()):
            if typ is None:
                item = {"moduleId": fillable_module["id"], "classId": cid, "classSha256": cls["sourceSha256"],
                        "field": "fields." + field, "neededEvidence": "reviewed non-null source field type"}
                missing_evidence.append(item)
                diag = _diagnostic("CODE_TYPE_EVIDENCE_FIELD_MISSING", cid + ".fields." + field, item["neededEvidence"])
                if diag not in diagnostics: diagnostics.append(diag)
        params = []
        missing = []
        for i, param in enumerate(ast.get("params", [])):
            typ = infer.vars[mid].get(param.get("bindingId"))
            if not typ:
                item = {"field": f"parameters[{i}]", "name": param.get("name"), "bindingId": param.get("bindingId"),
                                "sourceBytes": {"start": param.get("start"), "end": param.get("end")},
                                "neededEvidence": "explicit primitive/module/record type or call-site constraint"}
                missing.append(item)
                missing_evidence.append({"moduleId": fillable_module["id"], "classId": cid, "classSha256": cls["sourceSha256"],
                    "methodId": mid, "methodSha256": row["sourceSha256"], **item})
            params.append(typ)
        return_type = infer.returns.get(mid)
        if not return_type:
            item = {"field": "returns", "sourceBytes": row.get("sourceBytes"),
                    "neededEvidence": "reviewed return contract or supported primitive return expression"}
            missing.append(item)
            missing_evidence.append({"moduleId": fillable_module["id"], "classId": cid, "classSha256": cls["sourceSha256"],
                "methodId": mid, "methodSha256": row["sourceSha256"], **item})
        local_types = {}
        local_nodes = {}
        for node in _walk_method(ast.get("body", {})):
            if node.get("type") == "VariableDeclarator" and node.get("id", {}).get("type") == "Identifier":
                binding = node["id"].get("bindingId")
                local_nodes[binding] = node["id"]
                typ = infer.vars[mid].get(binding)
                if typ: local_types[binding] = typ
                else:
                    item = {"field": "locals." + str(node["id"].get("name")), "name": node["id"].get("name"), "bindingId": binding,
                                    "sourceBytes": {"start": node["id"].get("start"), "end": node["id"].get("end")},
                                    "neededEvidence": "explicit local type or supported initializer/assignment inference"}
                    missing.append(item)
                    missing_evidence.append({"moduleId": fillable_module["id"], "classId": cid, "classSha256": cls["sourceSha256"],
                        "methodId": mid, "methodSha256": row["sourceSha256"], **item})
        fillable_module["methods"].append({"id": mid, "name": seed_method.get("name", row["name"]),
            "sha256": row["sourceSha256"], "parameters": params, "returns": return_type,
            "locals": {binding: infer.vars[mid].get(binding) for binding in local_nodes}})
        method_nodes = list(_walk_method(ast.get("body", {})))
        call_callees = {id(node.get("callee")) for node in method_nodes if node.get("type") == "CallExpression"}
        for node in method_nodes:
            if node.get("type") != "MemberExpression" or node.get("computed") or node.get("object", {}).get("type") != "ThisExpression": continue
            if id(node) in call_callees: continue
            field = node.get("property", {}).get("name")
            if not isinstance(field, str): continue
            if field not in fillable_module["fields"] or fillable_module["fields"][field] is None:
                fillable_module["fields"][field] = None
                item = {"field": "fields." + field, "bindingId": None,
                    "sourceBytes": {"start": node.get("start"), "end": node.get("end")},
                    "neededEvidence": "reviewed field type or supported primitive this.field assignment"}
                missing.append(item)
                missing_evidence.append({"moduleId": fillable_module["id"], "classId": cid, "classSha256": cls["sourceSha256"],
                    "methodId": mid, "methodSha256": row["sourceSha256"], "field": "fields." + field,
                    "bindingId": None, "sourceBytes": item["sourceBytes"], "neededEvidence": item["neededEvidence"]})
        if any(item.get("field", "").startswith("parameters") for item in missing):
            for item in missing:
                if item.get("field", "").startswith("parameters"):
                    diagnostics.append(_diagnostic("CODE_TYPE_EVIDENCE_PARAMETER_MISSING", mid + "." + item["field"], "No supported evidence constrains this parameter", mid, item["sourceBytes"]))
        if any(item.get("field") == "returns" for item in missing):
            diagnostics.append(_diagnostic("CODE_TYPE_EVIDENCE_RETURN_MISSING", mid + ".returns", "Return type is ambiguous or unsupported", mid, row.get("sourceBytes")))
        for item in missing:
            if item.get("field", "").startswith("locals."):
                diagnostics.append(_diagnostic("CODE_TYPE_EVIDENCE_LOCAL_MISSING", mid + "." + item["field"], "Local type is ambiguous or unsupported", mid, item["sourceBytes"]))
            elif item.get("field", "").startswith("fields."):
                diagnostics.append(_diagnostic("CODE_TYPE_EVIDENCE_FIELD_MISSING", mid + "." + item["field"], "Field type is ambiguous or unsupported", mid, item["sourceBytes"]))
        evidence_fields = []
        for i, param in enumerate(ast.get("params", [])):
            binding = param.get("bindingId")
            if binding in infer.var_evidence[mid]: evidence_fields.append({"field": f"parameters[{i}]", **infer.var_evidence[mid][binding]})
        evidence_fields.extend({"field": "returns", **item} for item in infer.return_evidence[mid])
        evidence_fields.extend({"field": "locals." + key, **value} for key, value in sorted(infer.var_evidence[mid].items()) if key not in {p.get("bindingId") for p in ast.get("params", [])})
        evidence.append({"methodId": mid, "classId": cid, "classSha256": cls["sourceSha256"], "methodSha256": row["sourceSha256"],
                         "types": evidence_fields})
        if missing:
            fillable.append({"methodId": mid, "classId": cid, "sourceName": row["name"], "methodSha256": row["sourceSha256"], "missing": missing})
            continue
        module = modules.setdefault(cid, {"id": seed_module.get("id", cls["name"]), "targetClass": seed_module.get("targetClass", cls["name"]),
                                          "classId": cid, "classSha256": cls["sourceSha256"],
                                          "fields": {key: value for key, value in infer.module_fields.get(cid, {}).items() if value is not None}, "methods": []})
        module["methods"].append({"id": mid, "name": seed_method.get("name", row["name"]), "sha256": row["sourceSha256"],
                                  "parameters": params, "returns": return_type, "locals": local_types})
    for cid in sorted(modules):
        cls = classes[cid]
        evidence.append({"classId": cid, "classSha256": cls["sourceSha256"], "fields": [
            {"name": key, **value} for key, value in sorted(infer.module_field_evidence.get(cid, {}).items())]})
    seed_records = seed.get("records", []) if seed else []
    all_type_names = [m["targetClass"] for m in modules.values()] + [r.get("name") for r in seed_records if isinstance(r, dict)]
    referenced_type_texts = []
    for module in modules.values():
        referenced_type_texts.extend(module.get("fields", {}).values())
        for method in module["methods"]:
            referenced_type_texts.extend(method["parameters"]); referenced_type_texts.append(method["returns"])
            referenced_type_texts.extend(method["locals"].values())
    records = _type_record_names(referenced_type_texts, seed_records, [m["targetClass"] for m in modules.values()])
    used_fields = {name for mid in ids if mid in selected for name in _ast_property_names(selected[mid])}
    seed_witnesses = []
    graph_method_by_id = {row["id"]: row for row in graph.get("methods", [])}
    for mid, (seed_module, seed_method) in seed_methods.items():
        source_method, ast = graph_method_by_id.get(mid), selected_all.get(mid)
        if not source_method or not ast: continue
        source_class = classes.get(source_method.get("classId"), {})
        if (seed_module.get("classId") != source_method.get("classId") or
                seed_module.get("classSha256") != source_class.get("sourceSha256") or
                seed_method.get("sha256") != source_method.get("sourceSha256")):
            continue
        seed_witnesses.append((mid, seed_method["sha256"], _ast_property_names(ast)))
    shape_evidence, shape_missing = [], []
    for record in records:
        for field in record.get("fields", {}):
            if field in used_fields: continue
            witness = next((row for row in seed_witnesses if field in row[2]), None)
            if witness:
                shape_evidence.append({"methodId": witness[0], "methodSha256": witness[1]})
            else:
                shape_missing.append({"record": record["name"], "field": field,
                                      "neededEvidence": "typed exact-source method AST that reads or constructs this field"})
    shape_evidence = sorted({(row["methodId"], row["methodSha256"]) for row in shape_evidence})
    shape_evidence = [{"methodId": mid, "methodSha256": digest} for mid, digest in shape_evidence]
    for item in shape_missing:
        diagnostics.append(_diagnostic("CODE_TYPE_EVIDENCE_RECORD_FIELD_MISSING", item["record"] + "." + item["field"],
                                       item["neededEvidence"]))
        missing_evidence.append({"recordName": item["record"], "field": "records." + item["field"],
                                 "neededEvidence": item["neededEvidence"]})
    if not namespace:
        missing_evidence.append({"field": "namespace", "neededEvidence": "explicit target namespace"})
    call_domain = seed.get("callDomain") if seed else None
    if not call_domain:
        missing_evidence.append({"field": "callDomain", "neededEvidence": "human-reviewed finite call-domain statement"})
    contract = None
    if modules and namespace:
        contract = {"schemaVersion": 1, "sourceSha256": graph["source"]["sha256"], "namespace": namespace,
                    "records": records, "recordShapeEvidence": shape_evidence,
                    "modules": [modules[cid] for cid in sorted(modules)],
                    "callDomain": seed.get("callDomain") if seed and seed.get("callDomain") else "Explicit inferred primitive call domain; unknown dynamic inputs excluded"}
    unique_missing, missing_keys = [], set()
    for item in missing_evidence:
        key = tuple((name, repr(value)) for name, value in sorted(item.items()))
        if key not in missing_keys:
            missing_keys.add(key); unique_missing.append(item)
    fillable_contract = {"schemaVersion": 1, "sourceSha256": graph["source"]["sha256"],
        "namespace": namespace, "records": copy.deepcopy(seed_records),
        "recordShapeEvidence": copy.deepcopy(shape_evidence),
        "modules": [fillable_modules[cid] for cid in sorted(fillable_modules)],
        "callDomain": call_domain, "missingEvidence": unique_missing}
    status = "ready" if not diagnostics and not fillable and contract else "missing_type_or_dependency_contract"
    if infer.unsupported or any(d["code"].startswith("CODE_TYPE_EVIDENCE_UNSUPPORTED") for d in diagnostics): status = "unsupported_semantics"
    return {"status": status, "source": graph["source"], "contract": contract,
            "fillableContract": fillable_contract,
            "dependencies": {mid: sorted(values) for mid, values in sorted(edges.items())},
            "evidence": evidence, "diagnostics": diagnostics, "sourceExecuted": False}
