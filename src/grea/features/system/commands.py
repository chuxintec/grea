"""Command ownership for the system feature."""

HELPERS = ("registry_doctor", "check_skill", "toolchain_check")
OPERATIONS = ("command_catalog", "session", "list_tools", "describe_tool", "doctor", "run_tool")
RECOVERY = "grea.features.system.recovery"
DEVELOPMENT = "grea.features.system.development"


def declared_commands():
    from grea.features.adapters import core_commands, helper_commands, stage_commands

    yield from core_commands("system", OPERATIONS)
    yield from helper_commands("system", HELPERS)
    if RECOVERY:
        yield from stage_commands("system", RECOVERY, "recovery")
    if DEVELOPMENT:
        yield from stage_commands("system", DEVELOPMENT, "development")
