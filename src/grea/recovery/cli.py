"""Historical recovery CLI, backed by the public feature declarations."""

import argparse
import json
import sys

from grea.features.adapters import recovery_result
from grea.features.catalog import stage_modules, stage_owner
from . import __version__
from .sources.compiled import ParseError


def parser():
    result = argparse.ArgumentParser(prog="grea recover")
    result.add_argument("--version", action="version", version="%(prog)s " + __version__)
    sub = result.add_subparsers(dest="command", required=True)
    for module in stage_modules("recovery"):
        module.register(sub)
    return result


def main(argv=None):
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw[:1] == ["tool"]:
        from grea.features import RECOVERY_TOOLS, run_tool

        return run_tool(raw[1:], RECOVERY_TOOLS, "grea recover")
    if raw[:1] == ["static-code-bindings"]:
        from .static_code_bindings import main as run_static_code_bindings

        try:
            result = run_static_code_bindings(raw[1:])
            counts = result.get("counts", {})
            return 1 if any(counts.get(key, 0) for key in ("partial", "blocked", "not_executed")) else 0
        except (ParseError, OSError, ValueError, KeyError, TypeError, IndexError, RecursionError) as error:
            print(
                json.dumps(
                    dict(status="error", code=getattr(error, "code", "INPUT_ERROR"), message=str(error)),
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            return 2
    return execute(parser().parse_args(raw))


def execute(args, *, usage_parser=None):
    usage_parser = usage_parser or argparse.ArgumentParser(prog="grea recover " + args.command)
    result = recovery_result(args, stage_owner("recovery", args.command).dispatch, usage_parser)
    if result.value is not None:
        print(json.dumps(result.value, ensure_ascii=False))
    if result.diagnostics:
        print(result.diagnostics, file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
