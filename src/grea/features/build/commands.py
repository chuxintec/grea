"""Command ownership for the build feature."""

HELPERS = ("package_backup", "package_windows_portable", "verify_payload_tree")
OPERATIONS = ()
RECOVERY = None
DEVELOPMENT = "grea.features.build.development"


def declared_commands():
    from grea.features.adapters import core_commands, helper_commands, stage_commands

    yield from core_commands("build", OPERATIONS)
    yield from helper_commands("build", HELPERS)
    if RECOVERY:
        yield from stage_commands("build", RECOVERY, "recovery")
    if DEVELOPMENT:
        yield from stage_commands("build", DEVELOPMENT, "development")
