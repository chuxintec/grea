"""Neutral command model and parser inspection, independent of feature implementations."""

import argparse
import json
from collections.abc import Callable
from dataclasses import dataclass

from .result import CommandResult


def nonfinite(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def json_value(text):
    return json.loads(text, parse_constant=nonfinite)


def core_parser(operation, description, schema):
    p = argparse.ArgumentParser(description=description)
    for key, field in schema["properties"].items():
        kind = field.get("type")
        options = dict(
            dest=key,
            required=key in schema.get("required", []),
            default=argparse.SUPPRESS,
            help=field.get("description"),
        )
        if kind == "boolean":
            options["action"] = argparse.BooleanOptionalAction
        elif kind in ("integer", "number"):
            options["type"] = int if kind == "integer" else float
        elif kind == "array" and field.get("items", {}).get("type") == "string":
            options["action"] = "append"
        elif kind not in ("string",):
            options["type"] = json_value
        if "enum" in field:
            options["choices"] = field["enum"]
        p.add_argument("--" + key.replace("_", "-"), **options)
    return p


def leaves(parser, path=(), defaults=None, help_text=""):
    defaults = {} if defaults is None else defaults
    sub = next((a for a in parser._actions if isinstance(a, argparse._SubParsersAction)), None)
    if sub is None:
        yield path, defaults, parser, (parser.description or help_text or "").strip()
        return
    descriptions = {a.dest: a.help for a in sub._choices_actions}
    for name, child in sub.choices.items():
        values = {**defaults, sub.dest: name}
        yield from leaves(child, (*path, name), values, descriptions.get(name, ""))


def public_flags(action, parser):
    flags = action.option_strings
    if "--out" in flags and "--output" not in parser._option_string_actions:
        return ["--output", *flags]
    return list(flags)


def parameters(parser):
    rows = []
    for a in parser._actions:
        if isinstance(a, argparse._HelpAction):
            continue
        flags = public_flags(a, parser)
        name = next((f[2:] for f in flags if f.startswith("--")), a.dest)
        kind = (
            "boolean"
            if isinstance(a, (argparse.BooleanOptionalAction, argparse._StoreTrueAction, argparse._StoreFalseAction))
            else getattr(a.type, "__name__", "str")
        )
        if kind == "json_value":
            kind = "json"
        field = dict(
            name=name,
            flags=flags,
            dest=a.dest,
            type=kind,
            required=a.required,
            nargs=a.nargs,
            repeatable=isinstance(a, argparse._AppendAction),
        )
        if a.choices is not None:
            field["choices"] = list(a.choices)
        if a.default != argparse.SUPPRESS:
            field["default"] = a.default
        if a.help:
            field["help"] = a.help
        rows.append(field)
    return rows


@dataclass
class Command:
    module: str
    name: str
    path: tuple
    parser: argparse.ArgumentParser
    defaults: dict
    description: str
    handler: Callable[[argparse.Namespace, list[str], argparse.ArgumentParser], CommandResult]
    schema: dict | None = None

    def __post_init__(self):
        self.parser.prog = f"grea {self.module} {self.name}"
        # Register the standard spelling on this parser only. Old stage
        # parsers are constructed separately and retain their original flags.
        if "--out" in self.parser._option_string_actions and "--output" not in self.parser._option_string_actions:
            action = self.parser._option_string_actions["--out"]
            self.parser._option_string_actions["--output"] = action
            action.option_strings.insert(0, "--output")
        self.parser.allow_abbrev = False

    def describe(self):
        groups = [
            dict(required=g.required, options=[a.dest for a in g._group_actions])
            for g in self.parser._mutually_exclusive_groups
        ]
        # Terminal width affects normal --help, never the versioned interface description.
        formatter = argparse.HelpFormatter(self.parser.prog, width=100)
        formatter.add_usage(
            self.parser.usage, self.parser._actions, self.parser._mutually_exclusive_groups, prefix="usage: "
        )
        row = dict(
            module=self.module,
            action=self.name,
            usage=" ".join(formatter.format_help().split()),
            description=self.description,
            parameters=parameters(self.parser),
            exclusiveGroups=groups,
        )
        if self.schema is not None:
            row["requestSchema"] = self.schema
        return row
