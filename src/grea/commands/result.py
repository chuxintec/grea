"""Transport-neutral command results; serialization belongs to the entry point."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CommandResult:
    value: Any = None
    exit_code: int = 0
    diagnostics: str = ""


def structured(operation):
    """Adapt an existing (value, exit code) operation without serializing it."""

    def execute(arguments, argv, parser):
        value, code = operation(arguments)
        return CommandResult(value, code)

    return execute
