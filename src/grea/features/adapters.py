"""Boundary adapters for core operations and existing command families.

Public commands always return CommandResult. Only print-based standalone helpers
use stdout capture; recovery and development operations return values directly.
No source algorithm, adoption policy or process execution is implemented here.
"""

import argparse
import contextlib
import json
import tempfile
from importlib import import_module

from grea.commands.model import Command, core_parser, leaves
from grea.commands.result import CommandResult


class DevelopmentParser(argparse.ArgumentParser):
    def error(self, message):
        from grea.development.errors import fail

        fail("CLI_USAGE", "arguments", message)


def development_result(arguments, operation):
    from grea.development.result import development_result as receipt

    return CommandResult(*receipt(arguments, operation=operation))


def recovery_result(arguments, operation, parser):
    from grea.recovery.sources.compiled import ParseError

    try:
        return CommandResult(*operation(arguments, usage_parser=parser))
    except (ParseError, OSError, ValueError, KeyError, TypeError, IndexError, RecursionError) as error:
        diagnostic = dict(status="error", code=getattr(error, "code", "INPUT_ERROR"), message=str(error))
        if hasattr(error, "byte_budget"):
            diagnostic["byteBudget"] = error.byte_budget
        return CommandResult(exit_code=2, diagnostics=json.dumps(diagnostic, ensure_ascii=False))


def stage_commands(module, implementation, stage):
    """Build fresh public parsers from the owning module's parameter declarations."""
    if stage not in ("development", "recovery"):
        raise ValueError(f"Unknown command stage: {stage}")
    impl = import_module(implementation)
    parser_type = DevelopmentParser if stage == "development" else argparse.ArgumentParser
    tree = parser_type(prog=f"grea {stage}")
    impl.register(tree.add_subparsers(dest="command", required=True), include_intake_plan=False)
    for path, defaults, parser, description in leaves(tree):
        prefix = impl.ROUTES[path[0]]
        if prefix is None:
            continue
        name = "-".join(p for p in (prefix, *path[1:]) if p)
        if stage == "development":

            def execute(args, raw, usage_parser, operation=impl.dispatch):
                return development_result(args, operation)
        else:

            def execute(args, raw, usage_parser, operation=impl.dispatch):
                return recovery_result(args, operation, usage_parser)

        yield Command(module, name, path, parser, defaults, description, execute)


def core_commands(module, operations):
    from grea.contracts import CONTRACTS

    for operation in operations:
        description, schema, _ = CONTRACTS[operation]

        def execute(args, raw, parser, operation=operation):
            from grea.application import dispatch

            value = dispatch(operation, vars(args))
            return CommandResult(value, {"ok": 0, "partial": 1, "error": 2}[value["status"]])

        yield Command(
            module,
            operation.replace("_", "-"),
            (operation,),
            core_parser(operation, description, schema),
            {},
            description,
            execute,
            schema,
        )


def helper_arguments(parser, raw):
    """Translate the public output alias only before a literal argv separator."""
    alias = "--out" in parser._option_string_actions and (
        parser._option_string_actions["--out"] is parser._option_string_actions.get("--output")
    )
    result = []
    options = True
    for word in raw:
        if word == "--":
            options = False
        if options and alias and (word == "--output" or word.startswith("--output=")):
            word = "--out" + word[len("--output") :]
        result.append(word)
    return result


def printed_result(operation):
    """Quarantine legacy helper printing without loading large receipts into RAM."""
    with tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+", encoding="utf-8") as output:
        diagnostic = ""
        try:
            with contextlib.redirect_stdout(output):
                code = operation() or 0
        except SystemExit as error:
            code = error.code if isinstance(error.code, int) else int(error.code is not None)
            diagnostic = error.code if isinstance(error.code, str) else ""
        except (OSError, ValueError, RuntimeError) as error:
            code, diagnostic = 2, str(error)
        output.seek(0)
        body = output.read()
    try:
        value = json.loads(body) if body.strip() else None
    except ValueError:
        value = body
    return CommandResult(value, code, diagnostic)


def helper_commands(module, tools):
    for tool in tools:
        impl = import_module(f"grea.features.{module}.{tool}")
        for path, defaults, parser, description in leaves(impl.build_parser()):

            def execute(args, raw, usage_parser, main=impl.main, path=path):
                return printed_result(lambda: main([*path, *helper_arguments(usage_parser, raw)]))

            yield Command(
                module,
                "-".join((tool.replace("_", "-"), *path)),
                (tool, *path),
                parser,
                defaults,
                description or impl.__doc__ or "",
                execute,
            )


def binding_commands():
    from grea.recovery import static_code_bindings as impl

    for path, defaults, parser, description in leaves(impl.parser()):

        def execute(args, raw, parser):
            def call():
                value = impl.execute(args)
                return int(any(value.get("counts", {}).get(k, 0) for k in ("partial", "blocked", "not_executed")))

            return printed_result(call)

        yield Command(
            "code", "bindings-" + path[0], ("static-code-bindings", *path), parser, defaults, description, execute
        )
