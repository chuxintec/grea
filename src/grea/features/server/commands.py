"""Command ownership for the server feature."""

HELPERS = ("server_go_project",)
OPERATIONS = ()
RECOVERY = None
DEVELOPMENT = "grea.features.server.development"


def declared_commands():
    from grea.features.adapters import core_commands, helper_commands, stage_commands

    yield from core_commands("server", OPERATIONS)
    yield from helper_commands("server", HELPERS)
    if RECOVERY:
        yield from stage_commands("server", RECOVERY, "recovery")
    if DEVELOPMENT:
        yield from stage_commands("server", DEVELOPMENT, "development")
