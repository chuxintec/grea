"""Discover and validate module-owned commands; no stage dispatch lives here."""

from functools import lru_cache

from grea.features.catalog import MODULES, feature_modules
from .model import Command, core_parser, json_value, leaves, nonfinite, parameters, public_flags


def collect(providers):
    result = {}
    for module, provider in providers:
        for command in provider.declared_commands():
            key = command.module, command.name
            if command.module != module or module not in MODULES or key in result:
                raise ValueError(f"Invalid or duplicate GREA command: {command.module} {command.name}")
            if not callable(command.handler):
                raise ValueError(f"Missing command handler: {command.module} {command.name}")
            result[key] = command
    return result


@lru_cache(maxsize=1)
def commands():
    return collect(feature_modules())
