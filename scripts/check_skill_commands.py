"""Check documented GREA commands and shell examples without executing their effects."""
import contextlib
import io
import json
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from grea.commands.catalog import commands
from grea.commands.groups import MODULES
from grea.contracts import CONTRACTS
from jsonschema import Draft202012Validator, ValidationError

ENTRY = r'(?:["\']?\$GREA_ROOT/bin/grea["\']?|(?:\./)?(?:bin/)?grea)'
SHELL = re.compile(ENTRY + r'\s+(.*)')


def command_lines(source):
    shell = False
    lines = iter(enumerate(source.splitlines(), 1))
    for number, line in lines:
        if line.startswith("```"):
            shell = line.strip() in ("```sh", "```bash", "```shell", "```zsh")
        elif shell:
            while line.endswith("\\"):
                _, continuation = next(lines, (number, ""))
                line = line[:-1] + " " + continuation.strip()
            match = SHELL.fullmatch(line.strip())
            if match:
                yield number, match[1], True
        else:
            for fragment in re.findall(r'`([^`\n]+)`', line):
                match = SHELL.fullmatch(fragment)
                if match:
                    yield number, match[1], False



def validate(args, complete, request=None):
    if not args:
        return
    if args[:1] == ["--request"]:
        if len(args) < 4:
            raise ValueError("Expected a request file, module and action")
        args = args[2:]
    if args[0] == "commands":
        if len(args)>1 and args[1].isascii() and args[1] != "--json" and not args[1].startswith("<"):
            if args[1] not in MODULES:
                raise ValueError(f"Unknown module: {args[1]}")
            if len(args)>2 and args[2] != "--json" and (args[1],args[2]) not in commands():
                raise ValueError(f"Unknown action: {' '.join(args[1:3])}")
        return
    if args[0] in {"mcp", "--help", "--version"} or args[0].startswith("<") or not args[0].isascii():
        return
    if args[0] in MODULES:
        if len(args) < 2:
            return
        command = commands().get(tuple(args[:2]))
        if command is None:
            raise ValueError(f"Unknown command: {' '.join(args[:2])}")
        if request is not None:
            if command.schema:
                Draft202012Validator(command.schema).validate(request)
            if command.path == ("run_tool",) and request["tool_id"] in MODULES:
                validate([request["tool_id"], *request["arguments"]], True)
            return
        params = args[2:]
        if "--help" in params or "-h" in params or not params and not complete:
            return
        if complete:
            with contextlib.redirect_stderr(io.StringIO()):
                try:
                    command.parser.parse_args(params)
                except SystemExit:
                    raise ValueError(f"Arguments do not match {command.parser.prog}: {params}") from None
        else:
            unknown = [p for p in params if p.startswith("--") and p.split("=")[0] not in command.parser._option_string_actions]
            if unknown:
                raise ValueError(f"Unknown options for {command.parser.prog}: {unknown}")
        return
    # Frozen JSON core-call examples stay executable through the old entry.
    if args[0].replace("-", "_") not in CONTRACTS:
        raise ValueError(f"Unknown entry: {args[0]}")


def check(root):
    files = sorted(Path(root).rglob("*.md"))
    errors = []
    count = 0
    for path in files:
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        for number, text, complete in command_lines(source):
            count += 1
            try:
                args = shlex.split(text)
                request = None
                if "<<JSON" in args:
                    mark = args.index("<<JSON")
                    request = json.loads("\n".join(lines[number:lines.index("JSON",number)]))
                    args = args[:mark]
                validate(args, complete, request)
            except (ValueError, KeyError, IndexError, FileNotFoundError, ValidationError) as error:
                errors.append(dict(file=str(path.relative_to(root)), line=number, message=str(error)))
    return dict(ok=not errors, markdown_files=len(files), examples=count, errors=errors)


if __name__ == "__main__":
    result = check(ROOT/"plugin/skills")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(int(not result["ok"]))
