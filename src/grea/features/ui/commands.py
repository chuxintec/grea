"""Command ownership for the ui feature."""

HELPERS = ("presentation_audit", "theme_assets")
OPERATIONS = ()
RECOVERY = "grea.features.ui.recovery"
DEVELOPMENT = "grea.features.ui.development"


def declared_commands():
    from grea.features.adapters import core_commands, helper_commands, stage_commands

    yield from core_commands("ui", OPERATIONS)
    yield from helper_commands("ui", HELPERS)
    if RECOVERY:
        yield from stage_commands("ui", RECOVERY, "recovery")
    if DEVELOPMENT:
        yield from stage_commands("ui", DEVELOPMENT, "development")
