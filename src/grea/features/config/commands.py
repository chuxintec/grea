"""Command ownership for the config feature."""

HELPERS = (
    "export_config_tables",
    "unity_config_candidate",
    "config_preflight",
    "operations_preview",
    "compatibility_plan",
)
OPERATIONS = ()
RECOVERY = "grea.features.config.recovery"
DEVELOPMENT = "grea.features.config.development"


def declared_commands():
    from grea.features.adapters import core_commands, helper_commands, stage_commands

    yield from core_commands("config", OPERATIONS)
    yield from helper_commands("config", HELPERS)
    if RECOVERY:
        yield from stage_commands("config", RECOVERY, "recovery")
    if DEVELOPMENT:
        yield from stage_commands("config", DEVELOPMENT, "development")
