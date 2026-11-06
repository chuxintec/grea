"""Public prefab actions with module-owned parameter declarations."""
import argparse

from grea.commands.catalog import Command
from grea.development.result import development_result
from grea.development.intake import plan_from_args


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
    return development_result(args, operation=plan_from_args)


def declared_commands():
    parser = argparse.ArgumentParser()
    intake_plan_parameters(parser, public=True)
    return (Command("prefab", "intake-plan", "structured", ("intake", "plan"), parser,
                    {"command": "intake", "action": "plan"}, "", plan_result),)
