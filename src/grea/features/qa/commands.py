"""Command ownership for the qa feature."""

HELPERS = ("unity_native_exit", "performance_compare", "unity_player_audit")
OPERATIONS = ()
RECOVERY = None
DEVELOPMENT = "grea.features.qa.development"


def declared_commands():
    from grea.features.adapters import core_commands, helper_commands, stage_commands

    yield from core_commands("qa", OPERATIONS)
    yield from helper_commands("qa", HELPERS)
    if RECOVERY:
        yield from stage_commands("qa", RECOVERY, "recovery")
    if DEVELOPMENT:
        yield from stage_commands("qa", DEVELOPMENT, "development")
