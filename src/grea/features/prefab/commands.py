"""Public prefab actions with module-owned parameter declarations."""

import argparse
from grea.commands.model import Command
from grea.commands.result import structured
from grea.development.result import development_result


class OutputDirectory(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        previous = getattr(namespace, self.dest, None)
        if previous is not None and previous != value:
            parser.error("Conflicting output directories")
        setattr(namespace, self.dest, value)


def intake_plan_parameters(parser, *, public=False):
    for name in ("candidate", "target", "spec", "out"):
        action = OutputDirectory if public and name == "out" else "store"
        parser.add_argument("--" + name, required=True, action=action)
    parser.add_argument("--package-evidence")
    parser.add_argument("--expected-package-evidence")


def plan_result(args):
    from grea.development.intake import plan_from_args

    return development_result(args, operation=plan_from_args)


def direct_commands():
    parser = argparse.ArgumentParser()
    intake_plan_parameters(parser, public=True)
    return (
        Command(
            "prefab",
            "intake-plan",
            ("intake", "plan"),
            parser,
            {"command": "intake", "action": "plan"},
            "",
            structured(plan_result),
        ),
    )


HELPERS = ("verify_static_set",)
OPERATIONS = ()
RECOVERY = "grea.features.prefab.recovery"
DEVELOPMENT = "grea.features.prefab.development"


def declared_commands():
    from grea.features.adapters import core_commands, helper_commands, stage_commands

    yield from core_commands("prefab", OPERATIONS)
    yield from helper_commands("prefab", HELPERS)
    if RECOVERY:
        yield from stage_commands("prefab", RECOVERY, "recovery")
    if DEVELOPMENT:
        yield from stage_commands("prefab", DEVELOPMENT, "development")
    yield from direct_commands()
