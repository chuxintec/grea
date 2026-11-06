"""Full-source, best-effort JavaScript-function to isolated C# draft export.

This writer treats every streamed Acorn function as data. It emits drafts even
when local rendering fails, retaining the corresponding original source span
and a method-level diagnostic. Drafts live outside Unity's Assets tree and are
not compilation or behavior claims.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from .code_graph import draft_records
from .code_regeneration import plan_modules, select_reuse
from .io import encoded, load, new_output, read, safe, sha, write_json
from .output_limits import CHUNK_BYTES, FILE_BYTES, SELECTION_BYTES, SELECTION_FILES
from .sources.compiled import fail

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_KEYWORDS = set("abstract as base bool break byte case catch char checked class const continue decimal default delegate do double dynamic else enum event explicit extern false finally fixed float for goto if implicit in int interface internal is lock long namespace new object operator out override params private protected public readonly ref return sbyte sealed short sizeof stackalloc static string struct switch this throw true try typeof uint ulong unchecked unsafe ushort using virtual void volatile while var".split())


def _identifier(value, fallback="DraftClass"):
    from .layout.casing import pascal
    text = re.sub(r"[^A-Za-z0-9_]", "_", pascal(str(value or "")))
    if not text or text[0].isdigit(): text = "_" + text
    if text in _KEYWORDS: text = "_" + text
    return text or fallback


def _module_id(path):
    return "Draft_" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:28]


def _embedded_owner_precedence(owner):
    """Prefer the most local source span, with stable ties for incomplete spans."""
    span = owner.get("sourceBytes") or {}
    start, end = span.get("start"), span.get("end")
    if isinstance(start, int) and isinstance(end, int) and 0 <= start <= end:
        return (end - start, start, owner.get("targetPath", ""), owner.get("targetMethod", ""))
    return (2**63 - 1, 2**63 - 1, owner.get("targetPath", ""), owner.get("targetMethod", ""))


def _span_bytes(row, raw):
    span = row.get("functionBytes") or row.get("sourceBytes") or {}
    start, end = span.get("start"), span.get("end")
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw):
        return None
    return raw[start:end]


def _rename_field_declaration(source, old_name, new_name):
    """Rename only a field declarator, leaving its initializer expression intact."""
    if not isinstance(source, str):
        return source
    prefix, separator, suffix = source.partition(" = ")
    pattern = r"(?<![A-Za-z0-9_])" + re.escape(old_name) + r"(?=\s*(?:=|;))"
    updated, count = re.subn(pattern, new_name, prefix, count=1)
    return updated + separator + suffix if count else source


def _fallback(method, source_raw, class_name, target_name, diagnostic, capture_parameters=None):
    span = method.get("functionBytes") or method.get("sourceBytes") or {}
    start, end = span.get("start"), span.get("end")
    if type(start) is int and type(end) is int and 0 <= start < end <= len(source_raw):
        original = source_raw[start:end].decode("utf-8", errors="replace")
    else:
        original = "<source function span unavailable>"
    candidate_name = str(target_name or method.get("name") or "DraftMethod")
    name = (candidate_name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", candidate_name)
            and candidate_name not in _KEYWORDS else _identifier(candidate_name, "DraftMethod"))
    if name.casefold() == class_name.casefold(): name += "_DraftMethod"
    parameters = method.get("parameters", [])
    arguments = [f"dynamic arg{i}" for i, _ in enumerate(parameters if isinstance(parameters, list) else [])]
    arguments.extend("dynamic " + row["targetName"] for row in (capture_parameters or [])
                     if isinstance(row, dict) and isinstance(row.get("targetName"), str))
    args = ", ".join(arguments)
    comments = "".join("        // " + line for line in original.splitlines(keepends=True))
    if original and not original.endswith(("\n", "\r")): comments += "\n"
    body = (f"    public dynamic {name}({args})\n    {{\n"
            f"        // DRAFT ONLY: renderer failed for this function; source is preserved below.\n"
            f"{comments}"
            f"        throw new System.NotImplementedException(\"C# draft renderer failed\");\n"
            f"    }}")
    return {"source": body, "usings": ["System"],
            "diagnostics": [diagnostic], "approximateTypes": ["fallback dynamic signature; body intentionally throws"],
            "members": [], "emittedName": name, "sourceExecuted": False, "draftOnly": True}


def _class_records(header):
    records = {row["id"]: row for row in header.get("classes", []) if isinstance(row, dict) and isinstance(row.get("id"), str)}
    class_by_binding = {}
    for cid, row in records.items():
        for binding in (row.get("bindingId"), row.get("constructorBindingId")):
            if isinstance(binding, str): class_by_binding[binding] = cid
    # Groups and class names are deliberately conservative. Registration names
    # are retained as nearby evidence, never used to call a class business code.
    bases = {cid: _identifier(row.get("name"), "Class") for cid, row in records.items()}
    collisions = {}
    for cid, base in bases.items(): collisions.setdefault(base.casefold(), []).append(cid)
    names = {}
    for cid, base in bases.items():
        names[cid] = base if len(collisions[base.casefold()]) == 1 else base + "_" + sha(cid.encode())[:8]
    return records, class_by_binding, names


def _classification_candidate(record):
    """Weak lexical hint only; never removes output or proves ownership."""
    registration = record.get("precedingRegistration") or {}
    text = " ".join(str(value or "") for value in (
        record.get("name"), registration.get("identity"), registration.get("name"))).casefold()
    groups = (
        ("SdkCandidate", ("sdk", "analytics", "adservice", "wechat", "wxapi", "platformsdk")),
        ("FrameworkCandidate", ("cocos", "ccclass", "component", "director", "eventemitter", "framework")),
        ("EngineCandidate", ("engine", "assetbundle", "renderer", "texture", "sprite", "shader", "scene")),
    )
    for label, needles in groups:
        found = [needle for needle in needles if needle in text]
        if found:
            return label, found
    return "Unclassified", []


def _row_class_id(method, class_records, class_by_binding):
    cid = method.get("classId")
    if cid in class_records: return cid
    owner = method.get("ownerBindingId")
    return class_by_binding.get(owner)


def _dependencies(function_rows, class_records, class_by_binding, bucket_module_ids):
    dependencies = {module_id: set() for module_id in bucket_module_ids.values()}
    for record in function_rows:
        method = record["method"]
        caller_class = _row_class_id(method, class_records, class_by_binding)
        caller_bucket = caller_class or method.get("ownerBindingId") or ("function:" + method["id"])
        caller_id = bucket_module_ids.get(caller_bucket)
        if not caller_id: continue
        for call in method.get("calls", []):
            if call.get("receiver") == "this": target_class = caller_class
            else: target_class = class_by_binding.get(call.get("bindingId"))
            target_method = call.get("member")
            target = class_records.get(target_class, {}) if target_class else {}
            bindings = [item for item in target.get("methodBindings", []) if item.get("name") == target_method]
            if target_class and bindings:
                target_bucket = target_class
                target_id = bucket_module_ids.get(target_bucket)
                if target_id and target_id != caller_id: dependencies[caller_id].add(target_id)
    return {mid: sorted(values) for mid, values in dependencies.items()}


def _capture_parameters(row, ast, symbol_planner=None):
    if symbol_planner:
        method = dict(row.get("method", {}))
        if row.get("captures") and not method.get("captures"):
            method["captures"] = row["captures"]
        return symbol_planner.capture_parameters(method)
    raw_captures = row.get("captures") or row.get("method", {}).get("captures") or []
    if not isinstance(raw_captures, list):
        return []
    names = {}
    stack = [ast]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            binding = node.get("bindingId")
            name = node.get("name")
            if isinstance(binding, str) and isinstance(name, str):
                names.setdefault(binding, name)
            stack.extend(value for value in node.values() if isinstance(value, (dict, list)))
        elif isinstance(node, list):
            stack.extend(value for value in node if isinstance(value, (dict, list)))
    result, used = [], set()
    for capture in raw_captures:
        if isinstance(capture, dict):
            binding = capture.get("bindingId") or capture.get("id")
            source_name = capture.get("name") or capture.get("sourceName")
        else:
            binding, source_name = capture, None
        if not isinstance(binding, str):
            continue
        source_name = source_name if isinstance(source_name, str) else names.get(binding)
        target = _identifier(source_name or ("Capture_" + sha(binding.encode())[:8]), "DraftCapture")
        base = target
        index = 2
        while target.casefold() in used:
            target = base + "_" + str(index)
            index += 1
        used.add(target.casefold())
        result.append({"bindingId": binding, "targetName": target})
    return result


def _signature():
    root = Path(__file__).parent
    parts = ("code_drafts.py", "code_graph.py", "code-graph.cjs", "code_draft_render.py", "code_regeneration.py",
             "io.py", "layout/casing.py", "sources/source-offsets.cjs", "sources/acorn.cjs")
    if (root / "code_draft_symbols.py").is_file():
        parts += ("code_draft_symbols.py",)
    return sha(encoded({name: sha(read(root / name)) for name in parts}))


def prepare(source, expected_source_sha256=None):
    """Prepare all function drafts with bounded, one-row-at-a-time AST memory."""
    source = safe(Path(source))
    raw = read(source)
    source_sha = sha(raw)
    if expected_source_sha256 is not None:
        if not isinstance(expected_source_sha256, str) or not _HEX.fullmatch(expected_source_sha256):
            fail("CODE_DRAFT_SOURCE_IDENTITY", "expected_source_sha256", "Expected lowercase SHA-256")
        if source_sha != expected_source_sha256:
            fail("CODE_DRAFT_SOURCE_IDENTITY", source.name, "Source bytes do not match expected SHA-256")
    digest = source_sha[:12]
    draft_root = f"SourceRecovery/CSharp/{digest}"
    source_path = f"SourceRecovery/Code/Source/{digest}/Source.js"
    report_path = f"Analysis/Code/Drafts/{digest}/csharp-drafts.json"
    docs_path = f"Docs/CSharpDrafts/{digest}.md"
    files = {source_path: raw}
    diagnostics, function_meta, function_reports, field_reports = [], [], [], []
    header = footer = None
    classes = class_by_binding = class_names = {}
    buckets, bucket_names, bucket_paths, bucket_module_ids, bucket_groups = set(), {}, {}, {}, {}
    grouped, used_names, field_name_sources = {}, {}, {}
    namespace = "Monkey.Generated.Drafts.Source" + digest
    indexed_emitted = auxiliary_emitted = 0
    auxiliary_extracted = auxiliary_embedded = auxiliary_with_captures = 0
    symbol_planner = None
    inline_registry = {}

    def add_bucket(bucket):
        if bucket in buckets:
            return
        buckets.add(bucket)
        if bucket in class_names:
            bucket_names[bucket] = class_names[bucket]
            bucket_groups[bucket] = _classification_candidate(classes[bucket])[0]
        elif bucket.startswith("function:"):
            bucket_names[bucket] = "Function_" + sha(bucket.encode())[:10]
            bucket_groups[bucket] = "Unclassified"
        else:
            bucket_names[bucket] = "Unresolved_" + sha(str(bucket).encode())[:10]
            bucket_groups[bucket] = "Unclassified"
        bucket_paths[bucket] = f"{draft_root}/{bucket_groups[bucket]}/{bucket_names[bucket]}.cs"
        bucket_module_ids[bucket] = _module_id(bucket_paths[bucket])
        grouped[bucket] = {"usings": {"System", "System.Collections.Generic"}, "methods": [], "fields": [], "records": []}
        used_names[bucket] = set()
        field_name_sources[bucket] = {}

    for row in draft_records(source):
        kind = row.get("record")
        if kind == "header":
            header = row
            if row.get("source") != {"sha256": source_sha, "bytes": len(raw)}:
                fail("CODE_DRAFT_SOURCE_IDENTITY", source.name, "Graph header source identity changed")
            if row.get("sourceExecuted") is not False:
                fail("CODE_DRAFT_SOURCE_EXECUTION", source.name, "Static graph reported source execution")
            classes, class_by_binding, class_names = _class_records(row)
            if "draftDeclarations" in row:
                try:
                    from .code_draft_symbols import DraftSymbols
                except ImportError as exc:
                    fail("CODE_DRAFT_SYMBOL_PLANNER_MISSING", source.name,
                         "Header contains draftDeclarations but code_draft_symbols is unavailable")
                symbol_planner = DraftSymbols(row, class_names, _identifier)
            for class_id in classes:
                add_bucket(class_id)
            continue
        if kind == "footer":
            footer = row
            continue
        if kind == "field":
            if header is None:
                fail("CODE_DRAFT_INCOMPLETE", source.name, "Field row appeared before source header")
            field = row.get("field", {})
            bucket = _row_class_id(field, classes, class_by_binding)
            if not bucket and isinstance(field.get("ownerBindingId"), str):
                bucket = field["ownerBindingId"]
            if bucket:
                add_bucket(bucket)
                context = field.get("initializationContext", "program")
                is_initializer = context in ("program", "class_factory", "module")
                planned_field_name = (symbol_planner.target_name(field, kind="field") if symbol_planner
                                      else _identifier(field.get("name"), "DraftField"))
                rendered_field = None
                if is_initializer:
                    try:
                        from .code_draft_render import render_field
                        field_ast = row.get("ast")
                        if symbol_planner and isinstance(field_ast, dict):
                            field_ast = symbol_planner.annotate(field_ast, field, captures=None)
                        rendered_field = render_field(dict(field, targetName=planned_field_name),
                                                      field_ast, raw, class_name=bucket_names[bucket])
                        if not isinstance(rendered_field, dict) or not isinstance(rendered_field.get("source"), str):
                            raise ValueError("Renderer returned an incomplete field draft")
                        field_status = "drafted"
                    except Exception as exc:
                        name = _identifier(field.get("name"), "DraftField")
                        span = field.get("sourceBytes") or {}
                        original = raw[span.get("start", 0):span.get("end", 0)].decode("utf-8", errors="replace")
                        rendered_field = {"source": "public static dynamic " + name + " = ((System.Func<dynamic>)(() => { /* "
                            + original.replace("*/", "* /").replace("\n", " ")
                            + " */ throw new System.NotImplementedException(\"Field initializer draft failed\"); }))();",
                            "usings": ["System"], "members": [], "diagnostics": [{"code": "field_renderer_exception",
                            "message": "Field renderer failed with " + type(exc).__name__ + "; initializer remains source-linked."}]}
                        field_status = "fallback_initializer_in_source"
                    field_source = rendered_field["source"]
                    field_diags = [dict(item, fieldId=field.get("id")) for item in rendered_field.get("diagnostics", []) if isinstance(item, dict)]
                    if row.get("ast") is None or any(item.get("code") == "field_initializer_missing" for item in field_diags):
                        field_status = "fallback_initializer_in_source"
                    grouped[bucket]["usings"].update(item for item in rendered_field.get("usings", []) if isinstance(item, str))
                    emitted_name = rendered_field.get("emittedName", planned_field_name)
                else:
                    emitted_name = planned_field_name
                    field_status = ("runtime_write_preserved_in_method" if context == "runtime_write"
                                    else "unknown_initialization_context")
                    diagnostic_code = ("runtime_field_write_not_promoted" if context == "runtime_write"
                                       else "unknown_field_initialization_context")
                    field_diags = [{"code": diagnostic_code, "fieldId": field.get("id"),
                        "message": ("Runtime assignment remains in its source method and was not promoted to a class initializer."
                            if context == "runtime_write" else "Unknown field context was not treated as an initializer.") }]
                source_name_key = str(field.get("name", ""))
                base_name = emitted_name
                name_map = field_name_sources[bucket].setdefault(base_name, {})
                if source_name_key in name_map:
                    emitted_name = name_map[source_name_key]
                    if is_initializer and emitted_name != base_name:
                        field_source = _rename_field_declaration(field_source, base_name, emitted_name)
                elif not name_map:
                    name_map[source_name_key] = base_name
                else:
                    collision_message = "Distinct source field names normalized to the same C# identifier; stable source-name hash suffixes were added."
                    if len(name_map) == 1:
                        prior_source_name, prior_target = next(iter(name_map.items()))
                        if prior_target == base_name:
                            prior_target = base_name + "_" + sha(prior_source_name.encode("utf-8"))[:8]
                            while any(item["targetMember"] == prior_target and item["sourceName"] != prior_source_name
                                      for item in grouped[bucket]["fields"]):
                                prior_target += "_2"
                            for item in grouped[bucket]["fields"]:
                                if item["targetMember"] == base_name and item["sourceName"] == prior_source_name:
                                    item["targetMember"] = prior_target
                                    item["source"] = _rename_field_declaration(item.get("source"), base_name, prior_target)
                                    for report_row in field_reports:
                                        if report_row.get("fieldId") == item["fieldId"]:
                                            report_row["targetMember"] = prior_target
                                            report_row.setdefault("diagnostics", []).append({
                                                "code": "field_name_normalization_collision", "fieldId": item["fieldId"],
                                                "message": collision_message})
                            name_map[prior_source_name] = prior_target
                    emitted_name = base_name + "_" + sha(source_name_key.encode("utf-8"))[:8]
                    while emitted_name in name_map.values() or any(
                            item["targetMember"] == emitted_name and item["sourceName"] != source_name_key
                            for item in grouped[bucket]["fields"]):
                        emitted_name += "_2"
                    name_map[source_name_key] = emitted_name
                    if is_initializer:
                        field_source = _rename_field_declaration(field_source, base_name, emitted_name)
                    field_diags.append({"code": "field_name_normalization_collision", "fieldId": field.get("id"),
                        "message": collision_message})
                grouped[bucket]["fields"].append({"sourceStart": field.get("sourceBytes", {}).get("start", 0),
                    "fieldId": field.get("id", ""), "targetMember": emitted_name, "context": context,
                    "static": bool(field.get("static", True)), "access": field.get("access", "public"),
                    "sourceName": source_name_key, "source": field_source if is_initializer else None,
                    "status": field_status})
                field_reports.append({"fieldId": field.get("id"), "sourceName": field.get("name"),
                    "classId": field.get("classId"), "ownerAlias": field.get("ownerAlias"),
                    "ownerBindingId": field.get("ownerBindingId"), "static": field.get("static"),
                    "access": field.get("access"),
                    "sourceBytes": field.get("sourceBytes"), "sourceSha256": field.get("sourceSha256"),
                    "targetPath": bucket_paths[bucket], "targetClass": bucket_names[bucket],
                    "targetMember": emitted_name, "initializationContext": context,
                    "initializationPlacement": ("field_initializer" if is_initializer and field_status == "drafted"
                        else "runtime_method" if context == "runtime_write" else "source_only"),
                    "status": field_status, "diagnostics": field_diags,
                    "sourceExecuted": False, "draftOnly": True})
            else:
                unresolved_diag = {"code": "unresolved_field_owner", "fieldId": field.get("id"),
                    "message": "Field owner is not a class or known owner binding; retained in original source only."}
                field_reports.append({"fieldId": field.get("id"), "sourceName": field.get("name"),
                    "classId": field.get("classId"), "ownerAlias": field.get("ownerAlias"),
                    "ownerBindingId": field.get("ownerBindingId"), "static": field.get("static"),
                    "access": field.get("access"), "initializationContext": field.get("initializationContext"),
                    "sourceBytes": field.get("sourceBytes"), "sourceSha256": field.get("sourceSha256"),
                    "status": "unresolved_owner", "targetPath": None, "diagnostics": [unresolved_diag],
                    "sourceExecuted": False, "draftOnly": True})
            continue
        if kind != "function":
            diagnostics.append({"code": "unknown_draft_record", "message": "Unknown static stream record retained in diagnostics"})
            continue
        if header is None:
            fail("CODE_DRAFT_INCOMPLETE", source.name, "Function row appeared before source header")
        method = row.get("method", {})
        method_id = method.get("id")
        parent_function_id = method.get("parentFunctionId", row.get("parentFunctionId"))
        raw_captures = row.get("captures", method.get("captures", []))
        compact = {key: value for key, value in row.items() if key != "ast"}
        function_meta.append(compact)
        if row.get("kind") == "indexed_method":
            indexed_emitted += 1
        else:
            auxiliary_emitted += 1
        if row.get("kind") != "indexed_method" and method_id in inline_registry:
            owner = inline_registry[method_id]
            function_reports.append({"kind": row.get("kind"), "methodId": method_id, "sourceName": method.get("name"),
                "classId": method.get("classId"), "ownerBindingId": method.get("ownerBindingId"),
                "ownerAlias": method.get("ownerAlias"), "parentFunctionId": parent_function_id,
                "sourceBytes": method.get("sourceBytes"), "functionBytes": method.get("functionBytes"),
                "sourceSha256": method.get("sourceSha256"), "parameters": method.get("parameters", []),
                "calls": method.get("calls", []), "capturedBindings": raw_captures,
                "targetPath": owner["targetPath"], "targetClass": owner["targetClass"],
                "targetMethod": owner["targetMethod"], "targetLocationMarker": owner["marker"],
                "status": "embedded_in_owner", "approximateTypes": [], "members": [],
                "diagnostics": [], "sourceExecuted": False, "draftOnly": True})
            auxiliary_embedded += 1
            continue
        bucket = _row_class_id(method, classes, class_by_binding)
        if not bucket:
            owner = method.get("ownerBindingId")
            bucket = owner if isinstance(owner, str) else "function:" + str(method.get("id", "unknown"))
        add_bucket(bucket)
        class_name = bucket_names[bucket]
        source_name = method.get("name") if isinstance(method.get("name"), str) else "Function"
        target_name = (symbol_planner.target_name(method, kind="method") if symbol_planner
                       else _identifier(source_name, "DraftMethod"))
        if not symbol_planner and target_name.casefold() in used_names[bucket]:
            target_name += "_" + sha(str(method.get("id", "")).encode())[:8]
            suffix, base = 2, target_name
            while target_name.casefold() in used_names[bucket]:
                target_name = base + "_" + str(suffix)
                suffix += 1
        used_names[bucket].add(target_name.casefold())
        ast = row.get("ast")
        capture_parameters = (_capture_parameters(row, ast, symbol_planner)
                              if parent_function_id and row.get("kind") != "indexed_method" else [])
        method_input = dict(method, targetName=target_name, captureParameters=capture_parameters)
        if symbol_planner and isinstance(ast, dict):
            ast = symbol_planner.annotate(ast, method_input, captures=capture_parameters)
        render_diagnostics = []
        if ast is None:
            diagnostic = {"code": "ast_fragment_unavailable", "message": row.get("diagnostic", "AST fragment unavailable; retained exact function source")}
            rendered = _fallback(method, raw, class_name, target_name, diagnostic, capture_parameters)
            status = "fallback_original_source_excerpt"
        else:
            try:
                from .code_draft_render import render_method
                rendered = render_method(method_input, ast, raw, class_name=class_name)
                if (not isinstance(rendered, dict) or not isinstance(rendered.get("source"), str)
                        or rendered.get("sourceExecuted") is not False or rendered.get("draftOnly") is not True):
                    raise ValueError("Renderer returned an incomplete/non-draft result")
                seen_embedded_ids = set()
                for embedded in rendered.get("embeddedFunctions", []):
                    if not isinstance(embedded, dict):
                        raise ValueError("Renderer returned an invalid embedded-function record")
                    embedded_id = embedded.get("id") or embedded.get("functionId")
                    marker = embedded.get("marker")
                    if (not isinstance(embedded_id, str) or not embedded_id
                            or not isinstance(marker, str) or not marker
                            or marker not in rendered["source"]):
                        raise ValueError("Embedded-function marker is missing from the owning method source")
                    if embedded_id in seen_embedded_ids:
                        raise ValueError("Renderer reported one embedded function more than once in a method")
                    seen_embedded_ids.add(embedded_id)
                status = "extracted_with_capture_parameters" if capture_parameters else "drafted"
            except Exception as exc:
                diagnostic = {"code": "renderer_exception", "message": "Renderer failed with " + type(exc).__name__ + "; preserved complete original function fragment"}
                rendered = _fallback(method, raw, class_name, target_name, diagnostic, capture_parameters)
                status = "fallback_original_source_excerpt"
        if row.get("kind") != "indexed_method":
            auxiliary_extracted += 1
            if capture_parameters:
                auxiliary_with_captures += 1
        target_method = rendered.get("emittedName", target_name)
        for embedded in rendered.get("embeddedFunctions", []):
            if not isinstance(embedded, dict):
                continue
            embedded_id = embedded.get("id") or embedded.get("functionId")
            if isinstance(embedded_id, str):
                candidate = {"targetPath": bucket_paths[bucket], "targetClass": class_name,
                    "targetMethod": target_method, "marker": embedded["marker"],
                    "sourceBytes": method.get("sourceBytes")}
                current = inline_registry.get(embedded_id)
                if current is None or _embedded_owner_precedence(candidate) < _embedded_owner_precedence(current):
                    inline_registry[embedded_id] = candidate
                    # The auxiliary row can be streamed before a narrower owner
                    # is encountered. Keep its published mapping canonical too.
                    for report_row in function_reports:
                        if report_row.get("status") == "embedded_in_owner" and report_row.get("methodId") == embedded_id:
                            report_row.update({"targetPath": candidate["targetPath"],
                                "targetClass": candidate["targetClass"], "targetMethod": candidate["targetMethod"],
                                "targetLocationMarker": candidate["marker"]})
        text = "\n".join("    " + line if line else "" for line in rendered["source"].splitlines())
        span = method.get("sourceBytes") or {}
        grouped[bucket]["methods"].append((span.get("start", 0), method.get("id", ""), text))
        grouped[bucket]["usings"].update(item for item in rendered.get("usings", []) if isinstance(item, str))
        rendered_diagnostics = [dict(item, methodId=method.get("id"), kind=row.get("kind"))
                                for item in rendered.get("diagnostics", []) if isinstance(item, dict)]
        if capture_parameters:
            rendered_diagnostics.append({"code": "capture_parameter_callsite_unwired", "methodId": method_id,
                "message": "Captured locals are explicit dynamic parameters; source call sites were not rewritten."})
        function_reports.append({"kind": row.get("kind"), "methodId": method.get("id"), "sourceName": source_name,
            "classId": method.get("classId"), "ownerBindingId": method.get("ownerBindingId"),
            "ownerAlias": method.get("ownerAlias"), "sourceBytes": method.get("sourceBytes"),
            "functionBytes": method.get("functionBytes"), "sourceSha256": method.get("sourceSha256"),
            "parameters": method.get("parameters", []), "static": method.get("static"),
            "access": method.get("access"), "async": method.get("async", False),
            "calls": method.get("calls", []), "parentFunctionId": parent_function_id,
            "capturedBindings": raw_captures, "captureParameters": capture_parameters,
            "captureCallSitesRewritten": False if capture_parameters else None,
            "targetPath": bucket_paths[bucket], "targetClass": class_name,
            "targetMethod": target_method, "targetLocationMarker": None, "status": status,
            "approximateTypes": rendered.get("approximateTypes", []), "members": rendered.get("members", []),
            "diagnostics": rendered_diagnostics, "sourceExecuted": False, "draftOnly": True})
        grouped[bucket]["records"].append(compact)

    if header is None or footer is None:
        fail("CODE_DRAFT_INCOMPLETE", source.name, "Static function stream did not provide matching source header/footer")
    if footer.get("sourceExecuted") is not False:
        fail("CODE_DRAFT_SOURCE_EXECUTION", source.name, "Static graph reported source execution")

    if "draftDeclarations" in header:
        declarations = header.get("draftDeclarations")
        if not isinstance(declarations, list):
            fail("CODE_DRAFT_DECLARATIONS", source.name, "draftDeclarations must be an array")
        declared_by_id = {}
        for declaration in declarations:
            if not isinstance(declaration, dict) or not isinstance(declaration.get("id"), str):
                fail("CODE_DRAFT_DECLARATIONS", source.name, "Each declaration needs a source function id")
            if declaration["id"] in declared_by_id:
                fail("CODE_DRAFT_DECLARATIONS", declaration["id"], "Duplicate source function declaration id")
            declared_by_id[declaration["id"]] = declaration
        streamed_by_id = {row["method"].get("id"): row for row in function_meta}
        if len(streamed_by_id) != len(function_meta) or set(streamed_by_id) != set(declared_by_id):
            fail("CODE_DRAFT_DECLARATIONS", source.name, "Header declaration inventory differs from streamed function rows")
        for function_id, declaration in declared_by_id.items():
            streamed = streamed_by_id[function_id]
            method = streamed["method"]
            for key in ("name", "classId", "ownerAlias", "ownerBindingId", "static", "sourceBytes",
                        "sourceSha256", "functionBytes", "parentFunctionId"):
                if declaration.get(key) != method.get(key):
                    fail("CODE_DRAFT_DECLARATIONS", function_id, "Header declaration differs from streamed method field: " + key)
            if declaration.get("kind") != streamed.get("kind"):
                fail("CODE_DRAFT_DECLARATIONS", function_id, "Header declaration kind differs from streamed row")
    if "draftFields" in header:
        declarations = header.get("draftFields")
        if not isinstance(declarations, list):
            fail("CODE_DRAFT_FIELDS", source.name, "draftFields must be an array")
        declared_by_id = {}
        for declaration in declarations:
            if not isinstance(declaration, dict) or not isinstance(declaration.get("id"), str):
                fail("CODE_DRAFT_FIELDS", source.name, "Each field declaration needs a source field id")
            if declaration["id"] in declared_by_id:
                fail("CODE_DRAFT_FIELDS", declaration["id"], "Duplicate source field declaration id")
            declared_by_id[declaration["id"]] = declaration
        # Field metadata is retained in the detailed field reports independently
        # of whether its owner was resolvable or its initializer was renderable.
        streamed_by_id = {row.get("fieldId"): row for row in field_reports}
        if len(streamed_by_id) != len(field_reports) or set(streamed_by_id) != set(declared_by_id):
            fail("CODE_DRAFT_FIELDS", source.name, "Header field inventory differs from streamed field rows")
        for field_id, declaration in declared_by_id.items():
            streamed = streamed_by_id[field_id]
            for key in ("name", "classId", "ownerAlias", "ownerBindingId", "static", "initializationContext",
                        "sourceBytes", "sourceSha256"):
                report_key = "sourceName" if key == "name" else key
                declaration_value = declaration.get(key, "program" if key == "initializationContext" else None)
                if declaration_value != streamed.get(report_key):
                    fail("CODE_DRAFT_FIELDS", field_id, "Header field declaration differs from streamed field field: " + key)

    # Count embedded mappings once by owner path; doing this inside each class
    # report would scan all function rows for every class (O(classes * functions)).
    embedded_counts_by_path = Counter(
        row["targetPath"] for row in function_reports
        if row.get("status") == "embedded_in_owner" and isinstance(row.get("targetPath"), str))
    class_reports = []
    field_declaration_count = 0
    for bucket in sorted(buckets):
        class_row = classes.get(bucket)
        class_name = bucket_names[bucket]
        local_functions = grouped[bucket]["records"]
        indexed_count = sum(row.get("kind") == "indexed_method" for row in local_functions)
        aux_count = len(local_functions) - indexed_count
        body = ["// C# DRAFT ONLY. This directory is outside Assets and excluded from Unity compilation.",
                "// Group directory is a weak lexical candidate label, not proof of SDK/engine/business ownership."]
        if class_row:
            body.extend(["// sourceClassId: " + str(bucket), "// sourceClassName: " + str(class_row.get("name", ""))])
            registration = class_row.get("precedingRegistration")
            if registration:
                body.append("// registrationNeighbor (nearest preceding lexical registration; not proof): " +
                            str(registration.get("identity", "")) + " / " + str(registration.get("name", "")))
            if indexed_count == 0:
                body.extend(["// No indexed static/prototype methods were observed for this class.",
                             "// Available constructor/auxiliary functions are retained; unclassified fields require follow-up."])
        else:
            body.append("// Unresolved owner group: " + str(bucket))
        body.append("using System;")
        for using in sorted(grouped[bucket]["usings"] - {"System"}):
            body.append("using " + using + ";")
        body.extend(["namespace " + namespace + " {", "public partial class " + class_name + " {"])
        fields_by_name = {}
        for field_row in grouped[bucket]["fields"]:
            fields_by_name.setdefault((field_row["targetMember"], field_row["sourceName"]), []).append(field_row)
        total_initializers = sum(row["context"] in ("program", "class_factory", "module")
                                 for row in grouped[bucket]["fields"])
        initializer_blocks = {True: [], False: []}
        for field_identity in sorted(fields_by_name):
            rows = sorted(fields_by_name[field_identity], key=lambda item: (item["sourceStart"], item["fieldId"]))
            initializers = [item for item in rows if item["context"] in ("program", "class_factory", "module")]
            runtime_rows = [item for item in rows if item["context"] == "runtime_write"]
            name = rows[0]["targetMember"]
            if total_initializers == 1 and len(initializers) == 1:
                declaration = initializers[0]["source"]
            elif initializers:
                if initializers[0].get("source"):
                    declaration, separator, _ = initializers[0]["source"].partition(" = ")
                else:
                    separator, declaration = "", ""
                declaration = (declaration + ";") if separator else (
                    f"{initializers[0]['access']} {'static ' if initializers[0]['static'] else ''}dynamic {name};")
                for initializer in initializers:
                    _, separator, expression = initializer["source"].partition(" = ")
                    expression = expression.rsplit(";", 1)[0] if separator else (
                        "((System.Func<dynamic>)(() => { throw new System.NotImplementedException(\"Initializer unavailable\"); }))()")
                    initializer_blocks[initializer["static"]].append((initializer["sourceStart"],
                        f"{name} = {expression};"))
                    report_row = next((item for item in field_reports if item.get("fieldId") == initializer["fieldId"]), None)
                    if report_row and report_row["status"] == "drafted":
                        report_row["status"] = "initialized_in_static_constructor" if initializer["static"] else "initialized_in_constructor"
                    if report_row:
                        report_row["initializationPlacement"] = "static_constructor" if initializer["static"] else "instance_constructor"
            else:
                access = rows[0]["access"] if rows[0]["access"] in ("public", "private", "protected", "internal") else "public"
                declaration = f"{access} {'static ' if rows[0]['static'] else ''}dynamic {name};"
            if runtime_rows:
                body.append("    // Runtime field writes remain in their source methods; they are not promoted.")
            body.append("    " + declaration)
            field_declaration_count += 1
        for is_static in (True, False):
            assignments = sorted(initializer_blocks[is_static], key=lambda item: item[0])
            if assignments:
                constructor = f"static {class_name}()" if is_static else f"{class_name}()"
                body.append("    " + constructor + " {")
                body.extend("        " + statement for _, statement in assignments)
                body.append("    }")
        for _, _, source_text in sorted(grouped[bucket]["methods"], key=lambda item: (item[0], item[1])):
            body.append(source_text)
        if not local_functions:
            body.append("    // No function body was classified into this class; source identity is preserved in SourceRecovery.")
        body.extend(["}", "}", ""])
        path = bucket_paths[bucket]
        files[path] = "\n".join(body).encode("utf-8")
        class_reports.append({"classId": bucket if class_row else None,
            "ownerBindingId": bucket if not class_row and not bucket.startswith("function:") else None,
            "sourceName": class_row.get("name") if class_row else None, "targetClass": class_name,
            "group": bucket_groups[bucket],
            "classificationEvidence": ({"kind": "source_name_and_nearest_registration_lexical_hint_only",
                "nameTokens": _classification_candidate(class_row)[1]} if class_row else {"kind": "owner_unresolved"}),
            "targetPath": path,
            "sourceBytes": class_row.get("sourceBytes") if class_row else None,
            "sourceSha256": class_row.get("sourceSha256") if class_row else None,
            "indexedMethodCount": indexed_count, "auxiliaryFunctionCount": aux_count,
            "embeddedFunctionCount": embedded_counts_by_path.get(path, 0),
            "hasNoIndexedMethods": indexed_count == 0,
            "registrationNeighborIsInferenceOnly": bool(class_row and class_row.get("precedingRegistration"))})

    dependencies = _dependencies(function_meta, classes, class_by_binding, bucket_module_ids)
    requests, owners, code_module_ids = [], {}, []
    for bucket in sorted(buckets):
        path, module_id = bucket_paths[bucket], bucket_module_ids[bucket]
        records = grouped[bucket]["records"]
        mappings = [{"sourceMethodId": item.get("methodId"), "sourceName": item.get("sourceName"),
                    "sourceSha256": item.get("sourceSha256"), "sourceBytes": item.get("sourceBytes"),
                    "kind": item.get("kind"), "targetClass": item.get("targetClass"),
                    "targetPath": item.get("targetPath"), "targetMethod": item.get("targetMethod"),
                    "targetLocationMarker": item.get("targetLocationMarker"), "status": item.get("status"),
                    "capturedBindings": item.get("capturedBindings", [])}
                   for item in function_reports if item.get("targetPath") == path]
        class_row = classes.get(bucket)
        fingerprint = sha(encoded({"sourceSha256": source_sha, "classId": class_row.get("id") if class_row else None,
            "classSha256": class_row.get("sourceSha256") if class_row else None,
            "functions": [{"id": row["method"].get("id"), "sha256": row["method"].get("sourceSha256"), "kind": row.get("kind")} for row in records],
            "targetPath": path, "contentSha256": sha(files[path])}))
        requests.append({"id": module_id, "sourceFingerprint": fingerprint,
                         "dependencies": dependencies.get(module_id, []), "targetPaths": [path],
                         "sourceMethodMappings": mappings})
        owners[path] = module_id
        code_module_ids.append(module_id)

    # An embedded mapping is valid only if its exact marker survived into its
    # owner's final generated file. This catches renderer/writer drift before
    # the report can claim the nested source has an output location.
    for row in function_reports:
        if row.get("status") != "embedded_in_owner":
            continue
        target_path, marker = row.get("targetPath"), row.get("targetLocationMarker")
        target_bytes = files.get(target_path) if isinstance(target_path, str) else None
        if not isinstance(target_bytes, bytes) or not isinstance(marker, str) or not marker:
            fail("CODE_DRAFT_EMBEDDED_MARKER", row.get("methodId", "unknown"),
                 "Embedded function mapping has no owner output or exact marker")
        if marker.encode("utf-8") not in target_bytes:
            fail("CODE_DRAFT_EMBEDDED_MARKER", row.get("methodId", "unknown"),
                 "Embedded function marker is absent from the final owner output")

    indexed_mapping_count = sum(row.get("kind") == "indexed_method" for row in function_reports)
    embedded_mapping_count = sum(row.get("status") == "embedded_in_owner" for row in function_reports)
    if indexed_mapping_count != indexed_emitted:
        fail("CODE_DRAFT_INDEXED_METHOD_COVERAGE", source.name,
             "Indexed source function rows do not match indexed mapping records")
    if embedded_mapping_count != auxiliary_embedded:
        fail("CODE_DRAFT_EMBEDDED_COVERAGE", source.name,
             "Embedded auxiliary count differs from embedded mapping records")

    coverage = {"sourceClasses": len(classes), "functionsEmitted": footer.get("functionsEmitted", len(function_meta)),
        "classFactoriesFlattened": footer.get("classFactoriesFlattened", 0),
        "moduleContainersFlattened": footer.get("moduleContainersFlattened", 0),
        "graphFooterCounts": {key: value for key, value in footer.items() if key not in ("record", "sourceExecuted")},
        "indexedMethodsInSource": footer.get("indexedMethods", header.get("summary", {}).get("methods", 0)),
        "functionRecordsInGraph": footer.get("functionsEmitted", len(function_meta)),
        "functionsEmittedMeaning": "graph function rows; each row has one source mapping, while embedded auxiliary rows point to their owner instead of adding a standalone method",
        "indexedMethodFunctionsEmitted": indexed_emitted, "auxiliaryFunctionsEmitted": auxiliary_emitted,
        "functionsMapped": len(function_reports), "auxiliaryFunctionsExtracted": auxiliary_extracted,
        "auxiliaryFunctionsEmbedded": auxiliary_embedded,
        "auxiliaryFunctionsExtractedWithCaptures": auxiliary_with_captures,
        "classFiles": len(class_reports), "fieldRecords": len(field_reports),
        "fieldDeclarations": field_declaration_count,
        "fieldInitializers": sum(row.get("status") in ("drafted", "initialized_in_static_constructor", "initialized_in_constructor") for row in field_reports),
        "runtimeFieldWrites": sum(row.get("status") == "runtime_write_preserved_in_method" for row in field_reports),
        "fieldsWithInitializers": sum(row.get("status") in ("drafted", "initialized_in_static_constructor", "initialized_in_constructor") for row in field_reports),
        "methodsWithBodies": sum(row["status"] in ("drafted", "extracted_with_capture_parameters", "fallback_original_source_excerpt") for row in function_reports),
        "fallbackFunctionsWithOriginalExcerpt": sum(row["status"] == "fallback_original_source_excerpt" for row in function_reports),
        "embeddedFunctionsMapped": sum(row["status"] == "embedded_in_owner" for row in function_reports),
        "methodsNotEmitted": 0}
    if indexed_emitted != coverage["indexedMethodsInSource"]:
        fail("CODE_DRAFT_INDEXED_METHOD_COVERAGE", source.name, "Streamed indexed function count differs from source method summary")
    if indexed_emitted != header.get("summary", {}).get("methods", indexed_emitted):
        fail("CODE_DRAFT_INDEXED_METHOD_COVERAGE", source.name, "Streamed indexed function count differs from header method summary")
    if indexed_emitted + auxiliary_emitted != coverage["functionsEmitted"]:
        fail("CODE_DRAFT_FUNCTION_COVERAGE", source.name, "Function mapping row count differs from graph footer")
    if len(function_reports) != coverage["functionRecordsInGraph"]:
        fail("CODE_DRAFT_FUNCTION_COVERAGE", source.name, "Not every streamed source function received a mapping record")
    if "staticFields" in footer and len(field_reports) != footer["staticFields"]:
        fail("CODE_DRAFT_FIELD_COVERAGE", source.name, "Streamed field count differs from graph footer")

    # Detailed source mappings and complete diagnostics are stored exactly once
    # in bounded shards. The parent report retains only compact navigation rows.
    detail_rows = ([{"record": "function", **row} for row in function_reports] +
                   [{"record": "field", **row} for row in field_reports])
    if diagnostics:
        detail_rows.append({"record": "pipelineDiagnostics", "diagnostics": diagnostics})
    detail_paths, detail_refs = [], {}
    chunk_size = 512
    for part_index, start in enumerate(range(0, len(detail_rows), chunk_size), 1):
        chunk = detail_rows[start:start + chunk_size]
        part_path = f"Analysis/Code/Drafts/{digest}/Details/Part{part_index:04d}.json"
        part_data = json.dumps({"schemaVersion": 1, "source": {"sha256": source_sha, "bytes": len(raw)},
            "part": part_index, "records": chunk}, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode("utf-8")
        files[part_path] = part_data
        detail_paths.append({"path": part_path, "records": len(chunk)})
        for offset, entry in enumerate(chunk):
            if entry["record"] in ("function", "field"):
                source_key = entry.get("methodId") if entry["record"] == "function" else entry.get("fieldId")
                detail_refs[(entry["record"], source_key)] = {"detailsPath": part_path, "detailsIndex": offset}
    diagnostic_counts, diagnostic_examples = {}, {}
    for entry in detail_rows:
        for diagnostic in entry.get("diagnostics", []):
            code = str(diagnostic.get("code", "unspecified"))
            diagnostic_counts[code] = diagnostic_counts.get(code, 0) + 1
            if code not in diagnostic_examples and len(diagnostic_examples) >= 16:
                continue
            examples = diagnostic_examples.setdefault(code, [])
            if len(examples) < 2:
                example = {key: diagnostic[key] for key in ("methodId", "fieldId", "sourceBytes", "message") if key in diagnostic}
                examples.append(example)
    coverage.update({"detailRecords": len(detail_rows), "detailParts": len(detail_paths),
                     "diagnosticCount": sum(diagnostic_counts.values()),
                     "diagnosticKinds": len(diagnostic_counts)})
    function_index = []
    for row in function_reports:
        function_index.append({key: row.get(key) for key in ("kind", "methodId", "sourceName", "classId",
            "ownerBindingId", "sourceBytes", "functionBytes", "sourceSha256", "targetPath", "targetClass",
            "targetMethod", "targetLocationMarker", "parentFunctionId", "capturedBindings",
            "captureParameters", "captureCallSitesRewritten", "status")} | detail_refs.get(("function", row.get("methodId")), {}))
    field_index = []
    for row in field_reports:
        field_index.append({key: row.get(key) for key in ("fieldId", "sourceName", "classId", "ownerBindingId",
            "ownerAlias", "static", "access", "sourceBytes", "sourceSha256", "targetPath", "targetClass", "targetMember", "initializationContext",
            "initializationPlacement", "status")} |
            detail_refs.get(("field", row.get("fieldId")), {}))
    report = {"schemaVersion": 1, "status": "full_source_csharp_drafts; compile_excluded",
        "source": {"sha256": source_sha, "bytes": len(raw)}, "sourcePath": source_path,
        "draftRoot": draft_root, "reportPath": report_path, "documentationPath": docs_path,
        "namespace": namespace, "sourceExecuted": False, "compilation": "excluded",
        "classification": {"groupCandidates": {group: sum(row["group"] == group for row in class_reports)
                for group in ("EngineCandidate", "SdkCandidate", "FrameworkCandidate", "Unclassified")},
            "evidence": "class and nearest registration names are weak lexical hints only",
            "businessVsSdk": "not_proven_by_candidate_tags", "sdkEngineCodeFiltered": False,
            "registrationNameUse": "nearest lexical neighbor hint only"},
        "coverage": coverage, "classes": class_reports, "fields": field_index,
        "draftSymbols": symbol_planner.summary() if symbol_planner else None,
        "details": detail_paths,
        "modules": [{"id": row["id"], "targetPaths": row["targetPaths"],
            "dependencies": row["dependencies"], "methodIds": [item.get("sourceMethodId") for item in row["sourceMethodMappings"]]}
            for row in requests],
        "functions": sorted(function_index, key=lambda item: (item.get("sourceBytes", {}).get("start", 0), item.get("methodId", ""))),
        "diagnostics": {"count": sum(diagnostic_counts.values()), "countsByCode": diagnostic_counts,
            "examples": diagnostic_examples},
        "validation": {"compiled": "not_run", "behavior": "not_run", "nativeBinding": "not_run"},
        "limitations": ["C# drafts are outside Assets and excluded from compilation.",
            "Dynamic and unsupported semantics are approximate and have source-linked diagnostics.",
            "Business/SDK classification is unknown unless supported by separate evidence.",
            "This output does not execute source code or introduce a JavaScript runtime."]}
    files[report_path] = json.dumps(report, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")
    doc = ("# C# draft continuation\n\n"
        "This source partition contains best-effort C# drafts outside Unity's `Assets` tree. The files are intentionally excluded from compilation; syntax and API errors are repair items, not failed source preservation.\n\n"
        f"- Source: `{source_path}` (SHA-256 `{source_sha}`)\n- C# drafts: `{draft_root}/` (classification candidate subdirectories)\n- Report: `{report_path}`\n"
        f"- Indexed method records: {indexed_emitted}; auxiliary functions: {auxiliary_emitted}; class factories flattened: {coverage['classFactoriesFlattened']}; module containers flattened: {coverage['moduleContainersFlattened']}.\n\n"
        "Source and method mappings are in the report. Engine/SDK/framework labels are lexical candidate hints from class and nearest-registration names only; `Unclassified` is used when evidence is sparse. Every group is exported and no SDK or engine code is filtered. Renderer failures preserve complete function excerpts in fallback method bodies.\n\n"
        "These drafts are not source-equivalent, compiled, behavior-verified, or natively bound.\n").encode("utf-8")
    files[docs_path] = doc
    evidence_id = _module_id(report_path)
    evidence_paths = [source_path, report_path, docs_path, *[row["path"] for row in detail_paths]]
    owners.update({path: evidence_id for path in evidence_paths})
    evidence_fingerprint = sha(encoded({"sourceSha256": source_sha, "reportSha256": sha(files[report_path]),
        "docsSha256": sha(doc), "detailShards": {row["path"]: sha(files[row["path"]]) for row in detail_paths},
        "draftOutputs": {path: sha(files[path]) for path in sorted(bucket_paths.values())}}))
    requests.append({"id": evidence_id, "sourceFingerprint": evidence_fingerprint,
        "dependencies": sorted(code_module_ids), "targetPaths": sorted(evidence_paths), "sourceMethodMappings": []})
    signature = _signature()
    return {"files": files, "owners": owners, "requests": requests, "generatorSignature": signature,
        "report": report, "source": source, "sourcePath": source_path, "draftRoot": draft_root,
        "reportPath": report_path, "documentationPath": docs_path, "sourceSha256": source_sha,
        "sourceBytes": len(raw)}

def emit(source, out, expected_source_sha256=None, *, reuse_from=None, expected_manifest_sha256=None):
    """Write one fresh owned draft candidate, optionally reusing verified files."""
    import copy
    from .output_limits import WHOLE_BYTES, WHOLE_FILES
    prepared = prepare(source, expected_source_sha256)
    if bool(reuse_from) != bool(expected_manifest_sha256):
        fail("CODE_DRAFT_REUSE_IDENTITY", "$", "Reuse requires candidate path and exact manifest SHA-256")
    # Keep source call dependencies in report/manifest for review, but omit them
    # from cache selection: this is a whole-source snapshot, so each module's
    # source fingerprint is bound to the complete source SHA and generator.
    source_dependency_plan = plan_modules(prepared["requests"], prepared["generatorSignature"], whole_input=True)
    cache_requests = copy.deepcopy(prepared["requests"])
    for request in cache_requests:
        request["dependencies"] = []
    if reuse_from:
        reuse = select_reuse(reuse_from, expected_manifest_sha256, cache_requests, prepared["generatorSignature"])
    else:
        reuse = plan_modules(cache_requests, prepared["generatorSignature"], whole_input=True)
    if any(action["action"] == "blocked" for action in reuse["actions"].values()):
        fail("CODE_DRAFT_REUSE_BLOCKED", "$", "Dirty, manual, unknown, or invalid owned candidate content blocks regeneration")
    files = dict(prepared["files"])
    files.update(reuse.get("reusableFiles", {}))
    if len(files) > WHOLE_FILES or sum(len(data) for data in files.values()) > WHOLE_BYTES:
        fail("CODE_DRAFT_OUTPUT_BUDGET", "$", "Full-source draft exceeds whole-input output limits")
    inputs = [prepared["source"]] + ([safe(reuse_from)] if reuse_from else [])
    root = new_output(out, inputs)
    for relative, data in sorted(files.items()):
        if len(data) > FILE_BYTES: fail("CODE_DRAFT_FILE_BUDGET", relative, "Generated draft file exceeds shared file budget")
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    entries = []
    for relative, data in sorted(files.items()):
        entries.append({"path": relative, "sha256": sha(data), "bytes": len(data), "owner": prepared["owners"][relative]})
    manifest = {"schemaVersion": 1, "scopeMode": "whole-input", "candidateKind": "full-source-csharp-drafts",
        "codeGeneratorSignature": prepared["generatorSignature"], "source": prepared["report"]["source"],
        "codeModules": reuse["moduleRecords"], "files": entries,
        "regeneration": {"actions": reuse["actions"], "diagnostics": reuse["diagnostics"]},
        "sourceDependencies": prepared["report"].get("modules", []),
        "sourceDependencyDiagnostics": source_dependency_plan["diagnostics"],
        "validation": {"compiled": "excluded", "behavior": "not_run", "nativeBinding": "not_run"},
        "limits": {"maxOwnedOutputBytes": WHOLE_BYTES, "maxOwnedOutputFiles": WHOLE_FILES, "maxOwnedFileBytes": FILE_BYTES}}
    requests_by_id = {row['id']: row for row in prepared['requests']}
    for record in manifest["codeModules"]:
        request = requests_by_id[record['id']]
        record["sourceMethodMappings"] = request.get("sourceMethodMappings", [])
        # codeModules.files is the canonical path list; byte ownership and hashes
        # live in the manifest-level files inventory.
        record["files"] = list(record["targetPaths"])
    write_json(root / "manifest.json", manifest)
    return {"status": "drafts_emitted", "candidate": str(root), "manifest": str(root / "manifest.json"),
        "source": prepared["report"]["source"], "sourcePath": prepared["sourcePath"],
        "draftRoot": prepared["draftRoot"], "report": str(root / prepared["reportPath"]),
        "documentation": str(root / prepared["documentationPath"]), "coverage": prepared["report"]["coverage"],
        "regeneration": reuse["actions"], "sourceExecuted": False, "compiled": "excluded"}
