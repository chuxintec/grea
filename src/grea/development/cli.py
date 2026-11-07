"""Historical development CLI, backed by the public feature declarations."""

import json
import sys

from grea.features.adapters import DevelopmentParser as Parser
from grea.features.catalog import stage_modules, stage_owner
from .implementation import identity as implementation_identity
from .reporting import _p0_report, _p0_summary
from .result import development_result


def capabilities():
    from grea.features.system.development import capabilities as describe

    return describe()


def parser(prog="grea develop", *, include_intake_plan=True):
    result = Parser(prog=prog)
    sub = result.add_subparsers(dest="command", required=True)
    for module in stage_modules("development"):
        module.register(sub, include_intake_plan=include_intake_plan)
    return result


def dispatch(arguments):
    return stage_owner("development", arguments.command).dispatch(arguments)


def main(argv=None, *, arguments=None):
    prog = "grea develop"
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv == ["--version"]:
        argv = ["version"]
    if argv[:1] == ["tool"]:
        from grea.features import DEVELOPMENT_TOOLS, run_tool

        return run_tool(argv[1:], DEVELOPMENT_TOOLS, prog)
    base, code = development_result(arguments, operation=dispatch, parse=lambda: parser(prog).parse_args(argv))
    print(json.dumps(base, ensure_ascii=False, allow_nan=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
