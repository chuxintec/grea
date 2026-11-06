"""Bounded source-bound selection and typed dependency preflight for code modules.

This module only consumes the static lexical facts produced by ``code_graph``.
It never executes source and it does not infer types. The returned contract is
intended for the existing typed module emitter; a ``selected_ready`` result
means selection and statically provable source-class dependencies are closed,
not that a method has compiled or passed behavior tests.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

from .code_graph import facts
from .code_semantics import parse_type, walk
from .io import encoded, load, safe
from .sources.compiled import ParseError, fail

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_MAX_METHODS = 256


def _evidence(value):
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, dict):
        raw = encoded(value)
    else:
        fail("CODE_SELECTION_EVIDENCE", "$", "Expected typed contract mapping or canonical JSON bytes")
    if len(raw) > 128 * 1024:
        fail("CODE_SELECTION_BUDGET", "$", "Typed evidence exceeds 128 KiB")
    doc = load(raw, max_nodes=40_000, max_depth=48)
    if not isinstance(doc, dict) or doc.get("schemaVersion") != 1:
        fail("CODE_SELECTION_EVIDENCE", "$", "Expected schemaVersion 1 typed module contract")
    if not isinstance(doc.get("sourceSha256"), str) or not _HEX.fullmatch(doc["sourceSha256"]):
        fail("CODE_SELECTION_EVIDENCE", "sourceSha256", "Expected exact lowercase source SHA256")
    if not isinstance(doc.get("namespace"), str) or not doc["namespace"]:
        fail("CODE_SELECTION_EVIDENCE", "namespace", "Expected an explicit target namespace")
    modules, records = doc.get("modules"), doc.get("records", [])
    if not isinstance(modules, list) or not 1 <= len(modules) <= _MAX_METHODS:
        fail("CODE_SELECTION_EVIDENCE", "modules", "Expected 1..256 typed modules")
    if not isinstance(records, list) or len(records) > 256:
        fail("CODE_SELECTION_EVIDENCE", "records", "Expected at most 256 record type declarations")
    module_ids, class_ids, method_ids, target_names = set(), set(), set(), set()
    for mi, module in enumerate(modules):
        loc = f"modules[{mi}]"
        if not isinstance(module, dict): fail("CODE_SELECTION_EVIDENCE", loc, "Expected module object")
        for key in ("id", "targetClass", "classId", "classSha256"):
            if not isinstance(module.get(key), str) or not module[key]:
                fail("CODE_SELECTION_EVIDENCE", loc + "." + key, "Missing explicit module identity")
        if not _HEX.fullmatch(module["classSha256"]): fail("CODE_SELECTION_EVIDENCE", loc + ".classSha256", "Expected lowercase SHA256")
        if module["id"] in module_ids or module["classId"] in class_ids:
            fail("CODE_SELECTION_EVIDENCE", loc, "Duplicate module or source class identity")
        if module["targetClass"].casefold() in target_names:
            fail("CODE_SELECTION_EVIDENCE", loc, "Target type names collide case-insensitively")
        target_names.add(module["targetClass"].casefold())
        module_ids.add(module["id"]); class_ids.add(module["classId"])
        if not isinstance(module.get("fields", {}), dict) or len(module.get("fields", {})) > 64:
            fail("CODE_SELECTION_EVIDENCE", loc + ".fields", "Expected at most 64 explicit field types")
        methods = module.get("methods")
        if not isinstance(methods, list): fail("CODE_SELECTION_EVIDENCE", loc + ".methods", "Expected method list")
        for j, method in enumerate(methods):
            mloc = f"{loc}.methods[{j}]"
            if not isinstance(method, dict) or any(not isinstance(method.get(k), str) for k in ("id", "name", "sha256")):
                fail("CODE_SELECTION_EVIDENCE", mloc, "Method needs id, name and sha256")
            if not _HEX.fullmatch(method["sha256"]): fail("CODE_SELECTION_EVIDENCE", mloc + ".sha256", "Expected lowercase SHA256")
            if method["id"] in method_ids: fail("CODE_SELECTION_EVIDENCE", mloc, "Method identity appears more than once")
            method_ids.add(method["id"])
            if not isinstance(method.get("parameters"), list) or not isinstance(method.get("returns"), str):
                fail("CODE_SELECTION_EVIDENCE", mloc, "Explicit parameter and return type contracts are required")
            if not isinstance(method.get("locals", {}), dict): fail("CODE_SELECTION_EVIDENCE", mloc + ".locals", "Expected local type map")
            if len(method.get("locals", {})) > 256: fail("CODE_SELECTION_EVIDENCE", mloc + ".locals", "At most 256 explicit local types")
    if not 1 <= len(method_ids) <= _MAX_METHODS:
        fail("CODE_SELECTION_BUDGET", "modules", "Typed evidence must cover 1..256 methods")
    for ri, record in enumerate(records):
        if not isinstance(record, dict) or not isinstance(record.get("name"), str) or not isinstance(record.get("fields"), dict):
            fail("CODE_SELECTION_EVIDENCE", f"records[{ri}]", "Record requires explicit name and field map")
        if not 1 <= len(record["fields"]) <= 64:
            fail("CODE_SELECTION_EVIDENCE", f"records[{ri}].fields", "Expected 1..64 explicit record fields")
    return copy.deepcopy(doc)


def _diag(code, location, message, *, method_id=None, source_bytes=None):
    row = {"code": code, "location": location, "message": message}
    if method_id is not None: row["methodId"] = method_id
    if source_bytes is not None: row["sourceBytes"] = source_bytes
    return row


def _type_diagnostics(spec):
    names = [m["targetClass"] for m in spec["modules"]] + [r.get("name") for r in spec.get("records", []) if isinstance(r, dict)]
    out = []
    for ri, record in enumerate(spec.get("records", [])):
        if not isinstance(record, dict) or not isinstance(record.get("name"), str) or not isinstance(record.get("fields"), dict):
            out.append({**_diag("CODE_SELECTION_TYPE_CONTRACT", f"records[{ri}]", "Record requires a name and explicit fields"), "shared": True}); continue
        for field, typ in record["fields"].items():
            try: parse_type(typ, names)
            except ParseError as exc: out.append({**_diag(exc.code, f"records[{ri}].fields.{field}", exc.message), "shared": True})
    for module in spec["modules"]:
        for field, typ in module.get("fields", {}).items():
            try: parse_type(typ, names)
            except ParseError as exc: out.append({**_diag(exc.code, f"modules.{module['id']}.fields.{field}", exc.message), "moduleId": module["id"]})
        for method in module["methods"]:
            for i, typ in enumerate(method.get("parameters", [])):
                try: parse_type(typ, names)
                except ParseError as exc: out.append(_diag(exc.code, f"{method['id']}.parameters[{i}]", exc.message, method_id=method["id"]))
            try: parse_type(method.get("returns"), names)
            except ParseError as exc: out.append(_diag(exc.code, method["id"] + ".returns", exc.message, method_id=method["id"]))
            for local, typ in method.get("locals", {}).items():
                try: parse_type(typ, names)
                except ParseError as exc: out.append(_diag(exc.code, method["id"] + ".locals." + local, exc.message, method_id=method["id"]))
    return out


def _non_null_or_right_calls(ast, method_contract, module, spec):
    """Return call starts in RHS branches proven unreachable by typed truthiness.

    The emitter's explicit non-null collection/record domain makes these
    references truthy in JavaScript. This is intentionally narrow: only ``x ||
    rhs`` where ``x`` is an explicitly typed parameter/local of a non-null
    reference type is pruned. Numeric, optional, callback and computed values
    are not assumed truthy.
    """
    names = [m["targetClass"] for m in spec["modules"]] + [r.get("name") for r in spec.get("records", []) if isinstance(r, dict)]
    truthy = set()
    for i, param in enumerate(ast.get("params", [])):
        if i < len(method_contract.get("parameters", [])):
            try:
                typ = parse_type(method_contract["parameters"][i], names)
                if typ.kind in {"Map", "Set", "List", *names}: truthy.add(param.get("bindingId"))
            except ParseError:
                pass
    for node in ast.get("body", {}).get("body", []):
        pending = [node]
        while pending:
            current = pending.pop()
            if current.get("type") == "VariableDeclarator" and current.get("id", {}).get("type") == "Identifier":
                ident = current["id"]
                text = method_contract.get("locals", {}).get(ident.get("bindingId"), method_contract.get("locals", {}).get(ident.get("name")))
                if text:
                    try:
                        if parse_type(text, names).kind in {"Map", "Set", "List", *names}: truthy.add(ident.get("bindingId"))
                    except ParseError:
                        pass
            for value in current.values():
                if isinstance(value, dict) and "type" in value: pending.append(value)
                elif isinstance(value, list): pending.extend(x for x in value if isinstance(x, dict) and "type" in x)
    unreachable = set()
    pending = [(ast, False)]
    while pending:
        node, dead = pending.pop()
        if node.get("type") == "CallExpression" and dead: unreachable.add(node.get("start"))
        prune_right = False
        if node.get("type") == "LogicalExpression" and node.get("operator") == "||":
            left = node.get("left", {})
            prune_right = left.get("type") == "Identifier" and left.get("bindingId") in truthy
        for key, value in node.items():
            if isinstance(value, dict) and "type" in value:
                pending.append((value, dead or (key == "right" and prune_right)))
            elif isinstance(value, list):
                pending.extend((x, dead) for x in value if isinstance(x, dict) and "type" in x)
    return unreachable


def _used_records(modules, records):
    """Keep only the explicit record schemas referenced by selected types."""
    record_by_name = {row["name"]: row for row in records}
    names = [m["targetClass"] for m in modules] + list(record_by_name)
    pending, needed = [], set()
    for module in modules:
        for typ in module.get("fields", {}).values(): pending.append(typ)
        for method in module["methods"]:
            pending.extend(method.get("parameters", [])); pending.append(method.get("returns"))
            pending.extend(method.get("locals", {}).values())
    while pending:
        try: parsed = parse_type(pending.pop(), names)
        except ParseError: continue
        types = [parsed]
        while types:
            current = types.pop()
            if current.kind in record_by_name and current.kind not in needed:
                needed.add(current.kind)
                pending.extend(record_by_name[current.kind].get("fields", {}).values())
            types.extend(current.args)
    return [copy.deepcopy(record_by_name[name]) for name in sorted(needed)]


def _uses_record_name(module, record_name, spec):
    names = [m["targetClass"] for m in spec["modules"]] + [r["name"] for r in spec.get("records", []) if isinstance(r, dict)]
    values = list(module.get("fields", {}).values())
    for method in module["methods"]:
        values.extend(method.get("parameters", [])); values.append(method.get("returns")); values.extend(method.get("locals", {}).values())
    for text in values:
        try: root = parse_type(text, names)
        except ParseError: continue
        pending = [root]
        while pending:
            typ = pending.pop()
            if typ.kind == record_name: return True
            pending.extend(typ.args)
    return False


def select_modules(source_path, selectors, type_evidence, *, namespace=None):
    """Select exact ``{classId, methodId}`` roots and close known class calls.

    ``type_evidence`` is a schemaVersion-1 contract mapping or its canonical
    JSON bytes (including bytes returned by ``load_profile``). Only methods
    declared in that evidence can be auto-added. A statically observed source
    method with no reviewed type contract is reported as a missing dependency
    contract; it is never assigned guessed types.

    The result contains a subset ``contract`` for the existing code-modules
    emitter, per-module actions, stable mappings and byte-span diagnostics.
    Missing source identity/selector returns ``missing_source``; invalid
    evidence and unsafe inputs fail closed with ``ParseError``.
    """
    spec = _evidence(type_evidence)
    if namespace is not None:
        if namespace != spec["namespace"]:
            fail("CODE_SELECTION_NAMESPACE", "namespace", "Override must equal the reviewed evidence namespace")
    if not isinstance(selectors, list) or not 1 <= len(selectors) <= _MAX_METHODS:
        fail("CODE_SELECTION_SELECTORS", "selectors", "Expected 1..256 exact selector objects")
    roots, seen = [], set()
    for i, selector in enumerate(selectors):
        if not isinstance(selector, dict) or 'classId'not in selector or not (selector['classId']is None or isinstance(selector['classId'],str)) or not isinstance(selector.get("methodId"), str):
            fail("CODE_SELECTION_SELECTORS", f"selectors[{i}]", "Each selector requires classId (or null for unresolved source owner) and methodId")
        key = (selector["classId"], selector["methodId"])
        if key in seen: fail("CODE_SELECTION_SELECTORS", f"selectors[{i}]", "Duplicate selector")
        seen.add(key); roots.append(key)
    evidence_methods = {m["id"]: (module, m) for module in spec["modules"] for m in module["methods"]}
    # Facts receives the bounded set of reviewed methods so it can return their
    # ASTs in one parse. Global inventory is lexical metadata only.
    selected_evidence_ids = sorted(evidence_methods)
    try:
        source = safe(Path(source_path))
        graph = facts(source, spec["sourceSha256"], selected_evidence_ids)
    except ParseError as exc:
        status = "unsupported_semantics" if exc.code in {"CODE_GRAPH_PARSE_FAILED", "CODE_GRAPH_TIME_BUDGET", "CODE_GRAPH_OUTPUT_BUDGET"} else "missing_source"
        return {"status": status, "actions": {}, "contract": None, "moduleRecords": [],
                "selected": [], "autoAdded": [], "diagnostics": [_diag(exc.code, exc.location, exc.message)]}
    inventory = {row["id"]: row for row in graph.get("methodInventory", [])}
    asts = {row["method"]["id"]: row["ast"] for row in graph.get("selected", [])}
    indexed = {row["id"]: row for row in graph.get("methods", [])}
    class_rows = {row["id"]: row for row in graph.get("classes", [])}
    classes_by_binding = {}
    for cls in class_rows.values():
        for binding in (cls.get("bindingId"), cls.get("constructorBindingId")):
            if binding: classes_by_binding.setdefault(binding, cls["id"])
    bindings_by_class = {cid: {b["name"]: b for b in cls.get("methodBindings", [])}
                         for cid, cls in class_rows.items()}
    for cid, mid in roots:
        row = inventory.get(mid)
        if row is not None and row.get('classId')is None:
            return dict(status='unsupported_semantics',actions={},contract=None,moduleRecords=[],selected=[],autoAdded=[],sourceExecuted=False,
                        diagnostics=[_diag('CODE_SELECTION_CLASS_UNRESOLVED',mid,'Method bytes exist, but decorated/inherited/dynamic source class ownership is not proven; this is not missing source',method_id=mid,source_bytes=row['sourceBytes'])])
        if row is None or row.get("classId") != cid:
            return {"status": "missing_source", "actions": {}, "contract": None, "moduleRecords": [],
                    "selected": [], "autoAdded": [], "diagnostics": [_diag("CODE_SELECTION_METHOD_NOT_FOUND", mid, "Exact method/class identity is absent from source inventory", method_id=mid)]}
        if mid not in evidence_methods or evidence_methods[mid][0]["classId"] != cid:
            return {"status": "missing_type_or_dependency_contract", "actions": {}, "contract": None,
                    "moduleRecords": [], "selected": [], "autoAdded": [],
                    "diagnostics": [_diag("CODE_SELECTION_TYPE_CONTRACT_MISSING", mid, "Source method exists but no reviewed type evidence covers it", method_id=mid)]}
    queue = list(roots)
    closure, dependency_edges = set(), {}
    diagnostics = []
    while queue:
        cid, mid = queue.pop()
        if mid in closure: continue
        closure.add(mid)
        original = indexed.get(mid)
        if original is None:
            diagnostics.append(_diag("CODE_SELECTION_TYPE_CONTRACT_MISSING", mid, "Method AST is not available from bounded typed evidence", method_id=mid)); continue
        if original.get("factsCoverage"):
            diagnostics.append(_diag("CODE_SELECTION_UNSUPPORTED_FACTS", mid, original["factsCoverage"], method_id=mid)); continue
        if original.get("async") or original.get("generator"):
            diagnostics.append(_diag("CODE_SELECTION_UNSUPPORTED_ASYNC", mid, "Async/generator method semantics are outside this selector", method_id=mid)); continue
        current_class = original.get("classId")
        evidence_module, method_contract = evidence_methods[mid]
        dead_call_starts = _non_null_or_right_calls(asts.get(mid, {}), method_contract, evidence_module, spec)
        for call in original.get("calls", []):
            if call.get("sourceBytes", {}).get("start") in dead_call_starts:
                continue
            target_class = current_class if call.get("receiver") == "this" else classes_by_binding.get(call.get("bindingId"))
            if not target_class: continue
            member = call.get("member")
            if not isinstance(member, str):
                diagnostics.append(_diag("CODE_SELECTION_UNSUPPORTED_DYNAMIC_CALL", mid, "Computed source-class call cannot be resolved", method_id=mid, source_bytes=call.get("sourceBytes"))); continue
            binding = bindings_by_class.get(target_class, {}).get(member)
            # The source inventory supplies the exact method identity. A missing
            # binding can be a field or non-method call and is not guessed.
            if binding is None: continue
            dependency_id = binding["id"]
            if dependency_id == mid: continue
            if dependency_id not in inventory:
                diagnostics.append(_diag("CODE_SELECTION_DEPENDENCY_SOURCE_MISSING", mid, f"Referenced source method {member} is absent from inventory", method_id=mid, source_bytes=call.get("sourceBytes"))); continue
            dep_module = evidence_methods.get(dependency_id)
            if dep_module is None or dep_module[0]["classId"] != target_class:
                diagnostics.append(_diag("CODE_SELECTION_DEPENDENCY_TYPE_MISSING", dependency_id, f"{member} is a proven source dependency but has no reviewed type evidence", method_id=mid, source_bytes=call.get("sourceBytes"))); continue
            dependency_edges.setdefault(mid, set()).add(dependency_id)
            if dependency_id not in closure:
                queue.append((target_class, dependency_id))
    method_status = {}
    for row in diagnostics:
        mid = row.get("methodId")
        if not mid: continue
        issue = "unsupported_semantics" if row["code"].startswith("CODE_SELECTION_UNSUPPORTED") else "missing_type_or_dependency_contract"
        if method_status.get(mid) != "unsupported_semantics": method_status[mid] = issue
    changed = True
    while changed:
        changed = False
        for caller, dependencies in dependency_edges.items():
            dependency_issues = [method_status.get(dep) for dep in dependencies if method_status.get(dep)]
            if not dependency_issues: continue
            issue = "unsupported_semantics" if "unsupported_semantics" in dependency_issues else "missing_type_or_dependency_contract"
            if method_status.get(caller) != issue:
                method_status[caller] = issue; changed = True
                diagnostics.append(_diag("CODE_SELECTION_DEPENDENCY_BLOCKED", caller,
                                         "A required selected source dependency has a contract or semantic blocker", method_id=caller))
    # Project the full seed to just modules/methods reached. Keep records as
    # evidence supplied by the author; pruning can change emitter type names.
    picked_modules = []
    module_records = []
    mappings = []
    actions = {}
    for original_module in spec["modules"]:
        mids = [m["id"] for m in original_module["methods"] if m["id"] in closure]
        if not mids: continue
        module = copy.deepcopy(original_module)
        module["methods"] = [m for m in module["methods"] if m["id"] in closure]
        picked_modules.append(module)
        rows = []
        for method in module["methods"]:
            source_row = indexed.get(method["id"], {})
            mapping = {"sourceMethodId": method["id"], "sourceName": source_row.get("name", method["name"]),
                       "targetClass": module["targetClass"], "targetMethod": method["name"],
                       "sourceBytes": source_row.get("sourceBytes"), "sourceSha256": method["sha256"]}
            mappings.append(mapping); rows.append(mapping)
        module_records.append({"id": module["id"], "classId": module["classId"], "classSha256": module["classSha256"],
                               "methods": [m["id"] for m in module["methods"]], "sourceMethodMappings": rows})
        affected = {mid for mid in mids if method_status.get(mid)}
        module_diags = [d for d in diagnostics if d.get("methodId") in mids or d.get("location") in mids or d.get("methodId") in affected]
        status = "selected_ready"
        if any(method_status.get(mid) == "unsupported_semantics" for mid in mids): status = "unsupported_semantics"
        elif any(method_status.get(mid) for mid in mids) or module_diags: status = "missing_type_or_dependency_contract"
        actions[module["id"]] = {"action": "select" if status == "selected_ready" else "blocked", "status": status,
                                  "selectedMethodIds": sorted(mids), "diagnostics": module_diags}
    picked_records = _used_records(picked_modules, spec.get("records", []))
    type_diags = _type_diagnostics({**spec, "modules": picked_modules, "records": picked_records})
    selected_asts = [asts[mid] for mid in closure if mid in asts]
    observed_fields = {n["property"]["name"] for ast in selected_asts for n in walk(ast)
                       if n.get("type") == "MemberExpression" and not n.get("computed")}
    observed_fields.update(p["key"].get("name") for ast in selected_asts for n in walk(ast)
                          if n.get("type") == "ObjectExpression" for p in n["properties"] if p.get("type") == "Property")
    shape_evidence, record_shape_diags = [], []
    witness_rows = []
    for method_id, (module, method) in evidence_methods.items():
        original = indexed.get(method_id)
        ast = asts.get(method_id)
        if original and ast and original.get("sourceSha256") == method["sha256"]:
            properties = {n["property"]["name"] for n in walk(ast) if n.get("type") == "MemberExpression" and not n.get("computed")}
            properties.update(p["key"].get("name") for n in walk(ast) if n.get("type") == "ObjectExpression" for p in n["properties"] if p.get("type") == "Property")
            witness_rows.append((method_id, method["sha256"], properties))
    for record in picked_records:
        for field in record["fields"]:
            if field not in observed_fields:
                witness = next((row for row in witness_rows if field in row[2]), None)
                if witness:
                    shape_evidence.append({"methodId": witness[0], "methodSha256": witness[1]})
                    continue
                record_shape_diags.append({**_diag("CODE_SELECTION_RECORD_SHAPE_NOT_OBSERVED", record["name"] + "." + field,
                                                      "No exact-source typed evidence method demonstrates this record field"),
                                           "recordName": record["name"]})
    shape_evidence = sorted({(row["methodId"], row["methodSha256"]) for row in shape_evidence})
    shape_evidence = [{"methodId": method_id, "methodSha256": method_sha} for method_id, method_sha in shape_evidence]
    if len(shape_evidence) > 64:
        record_shape_diags.append(_diag("CODE_SELECTION_RECORD_SHAPE_EVIDENCE_BUDGET", "recordShapeEvidence",
                                        "Required field-shape witnesses exceed the 64-method contract limit"))
        shape_evidence = []
        type_diags.extend(record_shape_diags[-1:])
    type_diags.extend(record_shape_diags)
    if type_diags:
        diagnostics.extend(type_diags)
        for row in type_diags:
            mid = row.get("methodId")
            for module in picked_modules:
                uses_record = row.get("recordName") and any(_uses_record_name(m, row["recordName"], spec) for m in [module])
                if row.get("shared") or row.get("moduleId") == module["id"] or (mid and any(m["id"] == mid for m in module["methods"])) or uses_record:
                    actions[module["id"]] = {**actions[module["id"]], "action": "blocked", "status": "missing_type_or_dependency_contract"}
    status = "selected_ready"
    selection_status = "selected_ready"
    if any(a["status"] == "unsupported_semantics" for a in actions.values()): selection_status = "unsupported_semantics"
    elif any(a["status"] != "selected_ready" for a in actions.values()): selection_status = "missing_type_or_dependency_contract"
    if any(a["status"] == "unsupported_semantics" for a in actions.values()): status = "unsupported_semantics"
    elif any(a["status"] != "selected_ready" for a in actions.values()) or type_diags: status = "missing_type_or_dependency_contract"
    contract = {"schemaVersion": 1, "sourceSha256": spec["sourceSha256"], "namespace": spec["namespace"],
                "records": picked_records, "modules": picked_modules,
                "callDomain": spec.get("callDomain"), "recordShapeEvidence": shape_evidence}
    return {"status": status, "selectionStatus": selection_status, "source": graph["source"], "selected": sorted(closure),
            "requested": [mid for _, mid in roots], "autoAdded": sorted(closure - {mid for _, mid in roots}),
            "actions": actions, "contract": contract, "moduleRecords": module_records,
            "diagnostics": diagnostics, "sourceMethodMappings": sorted(mappings, key=lambda row: row["sourceMethodId"]),
            "sourceExecuted": False}


def plan_selection(source_path, selectors, type_evidence, *, namespace=None):
    """Alias for callers that name a read-only selection operation as planning."""
    return select_modules(source_path, selectors, type_evidence, namespace=namespace)


def write_selection(source, selectors, output, *, type_evidence=None, module_profile=None):
    """CLI boundary: serialize the selection and check the actual emitter too."""
    import tempfile
    from .io import read, write_json, new_output
    from .code_modules import prepare
    from .code_profiles import load_profile
    if bool(type_evidence)==bool(module_profile):
        fail('CODE_SELECTION_EVIDENCE','$','Use exactly one typed evidence file or built-in profile')
    source,selectors=safe(source),safe(selectors)
    evidence=read(safe(type_evidence),max_bytes=128*1024)if type_evidence else load_profile(module_profile,source)
    roots=load(read(selectors,max_bytes=64*1024))
    result=select_modules(source,roots,evidence)
    result.setdefault('requested',[row['methodId']for row in roots]);result['sourceExecuted']=False
    result['lowering']='not_run'
    if result['status']=='selected_ready':
        with tempfile.TemporaryDirectory(prefix='monkey-code-selection-')as temp:
            contract=Path(temp).resolve()/'contract.json';write_json(contract,result['contract'])
            try:
                prepared=prepare(source,contract)
                result['lowering']='passed';result['emittableMethods']=prepared['report']['coverage']['implementedMethods']
            except ParseError as error:
                message=error.message.lower()
                result['status']='missing_type_or_dependency_contract'if any(token in message for token in ('type','callee absent','field absent','unknown field','unproven'))else'unsupported_semantics'
                result['lowering']='blocked';result['diagnostics'].append(error.as_dict())
                for action in result.get('actions',{}).values():
                    action.update(action='blocked',status=result['status'],lowering='batch_blocked')
    out=new_output(output,[source,selectors]+([safe(type_evidence)]if type_evidence else[]))
    write_json(out/'selection.json',result)
    if result['status']=='selected_ready':write_json(out/'module-contract.json',result['contract'])
    return dict(status=result['status'],lowering=result['lowering'],requested=len(result.get('requested',[])),selected=len(result.get('selected',[])),
                autoAdded=result.get('autoAdded',[]),diagnostics=result['diagnostics'],report=str(out/'selection.json'),
                contract=str(out/'module-contract.json')if result['status']=='selected_ready'else None,sourceExecuted=False)
