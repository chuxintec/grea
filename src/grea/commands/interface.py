"""The domain-oriented CLI. Compatibility commands keep their own receipt formats."""
import argparse
import contextlib
import json
import math
import sys
import tempfile
from pathlib import Path

from grea import __version__
from .catalog import commands, nonfinite, parameters
from .groups import MODULES


def inventory(module=None, action=None):
    if action and not module:
        raise ValueError("Select a module before an action")
    if module and module not in MODULES:
        raise ValueError(f"Unknown module: {module}")
    selected = [v for (m, a), v in sorted(commands().items())
                if (not module or m == module) and (not action or a == action)]
    if action and not selected:
        raise ValueError(f"Unknown command: {module} {action}")
    return dict(version=__version__, modules={k: v for k, v in MODULES.items() if not module or k == module},
                commands=[c.describe() for c in selected])


def show_commands(argv):
    parser = argparse.ArgumentParser(prog="grea commands", description="List commands, or inspect one command and its parameters.")
    parser.add_argument("module", choices=sorted(MODULES), nargs="?")
    parser.add_argument("action", nargs="?")
    parser.add_argument("--json", action="store_true", help="Print machine-readable parameter descriptions")
    args = parser.parse_args(argv)
    try:
        data = inventory(args.module, args.action)
    except ValueError as error:
        parser.error(str(error))
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action:
        print(commands()[args.module, args.action].parser.format_help(), end="")
    elif args.module:
        print(f"usage: grea {args.module} ACTION [parameters]")
        for item in data["commands"]:
            print(f"grea {item['module']} {item['action']}")
    else:
        for module, label in MODULES.items():
            total = sum(c["module"] == module for c in data["commands"])
            print(f"{module:10} {total:3}  {label}")
    return 0


def read_request(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate request field: {key}")
            result[key] = value
        return result
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    request = json.loads(text, object_pairs_hook=unique, parse_constant=nonfinite)
    if not isinstance(request, dict):
        raise ValueError("Expected a JSON object")
    return request


def as_text(value, field):
    if field["type"] == "json":
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    kind = field["type"]
    if kind == "int":
        valid = type(value) is int
    elif kind == "float":
        valid = type(value) is int or type(value) is float and math.isfinite(value)
    elif kind == "integer_literal":
        valid = isinstance(value, str) or type(value) is int
    else:
        valid = isinstance(value, str)
    if not valid:
        raise ValueError(f"{field['name']}: expected {kind}")
    return str(value)


def request_args(command, request):
    options = []
    positional = []
    consumed = set()
    for field in parameters(command.parser):
        keys = {field["name"], field["dest"], *(f[2:] for f in field["flags"] if f.startswith("--"))}
        matches = keys & request.keys()
        if not matches:
            continue
        if len(matches) != 1:
            raise ValueError(f"Multiple spellings of {field['name']} in one request")
        key = matches.pop()
        consumed.add(key)
        value = request[key]
        flags = field["flags"]
        if flags and field["type"] == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"{key}: expected a boolean")
            if key == field["dest"] or "--"+key not in flags:
                flag = flags[0]
            else:
                flag = "--"+key
            if value:
                options.append(flag)
            elif len(flags) == 2 and flags[1].startswith("--no-"):
                options.append(flags[0] if flag == flags[1] else flags[1])
            continue
        flag = flags[0] if flags else None
        repeated = field["repeatable"]
        groups = value if repeated and isinstance(value, list) else [value]
        for group in groups:
            if field["type"] != "json" and isinstance(group, list):
                if field["nargs"] not in ("+", "*") and not isinstance(field["nargs"], int):
                    raise ValueError(f"{key}: expected one value")
                values = [as_text(item, field) for item in group]
            else:
                values = [as_text(group, field)]
            if flag:
                if len(values)==1 and field["nargs"] is None:
                    options.append(flag+"="+values[0])
                else:
                    options.extend([flag, *values])
            else:
                positional.extend(values)
    unknown = sorted(request.keys() - consumed)
    if unknown:
        raise ValueError("Unknown request fields: " + ", ".join(unknown))
    return options + (["--", *positional] if positional else [])


def core_request(command, request):
    """Retain JSON types and explicit empty values for native schema validation."""
    properties = command.schema["properties"]
    result = {}
    for key, value in request.items():
        dest = key.replace("-", "_")
        if dest not in properties and key.startswith("no-"):
            positive = key[3:].replace("-", "_")
            if positive in properties and properties[positive].get("type") == "boolean":
                if not isinstance(value, bool):
                    raise ValueError(f"{key}: expected a boolean")
                dest, value = positive, not value
        if dest not in properties:
            raise ValueError(f"Unknown request field: {key}")
        if dest in result:
            raise ValueError(f"Multiple spellings of {dest} in one request")
        result[dest] = value
    return argparse.Namespace(**result)


def invoke(command, args, raw):
    if command.backend == "core":
        from grea.application import dispatch
        result = dispatch(command.path[0], vars(args))
        print(json.dumps(result, ensure_ascii=False))
        return {"ok": 0, "partial": 1, "error": 2}[result["status"]]
    if command.backend == "development":
        return command.handler([], arguments=args)
    if command.backend == "helper":
        # A helper may use its parser for contextual errors after parsing, so
        # retain its own execution path rather than trying to emulate it.
        out_alias = "--out" in command.parser._option_string_actions and (
            command.parser._option_string_actions["--out"] is command.parser._option_string_actions.get("--output"))
        translated = []
        options = True
        for word in raw:
            if word == "--":
                options = False
            if options and out_alias and (word == "--output" or word.startswith("--output=")):
                word = "--out" + word[len("--output"):]
            translated.append(word)
        return command.handler([*command.path[1:], *translated])
    if command.backend == "recovery":
        return command.handler(args, usage_parser=command.parser)
    result = command.handler(args)
    if command.backend == "bindings":
        return int(any(result.get("counts", {}).get(k, 0) for k in ("partial", "blocked", "not_executed")))
    return result


def run_command(module, action, raw, request_file=None):
    command = commands().get((module, action))
    if command is None:
        message = f"Unknown command: {module} {action}. Use grea commands {module}."
        print(json.dumps(dict(product="grea",version=__version__,command=f"{module} {action}",
                              status="error",exit_code=2,result=None,diagnostics=message)))
        return 2
    option_tokens = raw[:raw.index("--")] if "--" in raw else raw
    if "-h" in option_tokens or "--help" in option_tokens:
        print(command.parser.format_help(), end="")
        return 0
    with tempfile.SpooledTemporaryFile(max_size=1024*1024, mode="w+", encoding="utf-8") as output, \
         tempfile.SpooledTemporaryFile(max_size=1024*1024, mode="w+", encoding="utf-8") as errors:
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                if request_file is not None:
                    if raw:
                        raise ValueError("Use either --request FILE or inline parameters")
                    request = read_request(request_file)
                    if command.backend == "core":
                        args = core_request(command, request)
                    else:
                        raw = request_args(command, request)
                        args = command.parser.parse_args(raw)
                else:
                    args = command.parser.parse_args(raw)
                for key, value in command.defaults.items():
                    setattr(args, key, value)
                code = invoke(command, args, raw) or 0
        except SystemExit as error:
            code = error.code if isinstance(error.code, int) else int(error.code is not None)
            if isinstance(error.code, str):
                errors.write(error.code)
        except (OSError, ValueError, RuntimeError) as error:
            errors.write(str(error))
            code = 2
        output.seek(0)
        body = output.read()
        try:
            result = json.loads(body) if body.strip() else None
        except ValueError:
            result = body
        errors.seek(0)
        diagnostics = errors.read().strip()
    status = {0:"ok", 1:"partial", 2:"error", 3:"blocked"}.get(code,"error")
    receipt = dict(product="grea", version=__version__, command=f"{module} {action}", status=status,
                   exit_code=code, result=result, diagnostics=diagnostics)
    print(json.dumps(receipt, ensure_ascii=False, allow_nan=False))
    return code


def route(argv):
    """Return None for a stage compatibility route, otherwise its exit code."""
    args = list(argv)
    request_file = None
    if args and (args[0] == "--request" or args[0].startswith("--request=")):
        if args[0] == "--request":
            if len(args) < 2:
                print("--request requires a JSON file or -", file=sys.stderr)
                return 2
            request_file, args = args[1], args[2:]
        else:
            request_file, args = args[0].split("=", 1)[1], args[1:]
    if args[:1] == ["commands"] and request_file is None:
        return show_commands(args[1:])
    if not args or args[0] not in MODULES:
        if request_file is not None:
            print("--request requires a module and action; see grea commands", file=sys.stderr)
            return 2
        return None
    if len(args) == 1 or args[1] in ("-h", "--help"):
        return show_commands([args[0]])
    return run_command(args[0], args[1], args[2:], request_file)
