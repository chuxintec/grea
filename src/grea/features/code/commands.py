"""Command ownership for the code feature."""

HELPERS = ("read_elf_values",)
OPERATIONS = ()
RECOVERY = "grea.features.code.recovery"
DEVELOPMENT = "grea.features.code.development"


def declared_commands():
    from grea.features.adapters import core_commands, helper_commands, stage_commands

    yield from core_commands("code", OPERATIONS)
    yield from helper_commands("code", HELPERS)
    if RECOVERY:
        yield from stage_commands("code", RECOVERY, "recovery")
    if DEVELOPMENT:
        yield from stage_commands("code", DEVELOPMENT, "development")
    from grea.features.adapters import binding_commands

    yield from binding_commands()
