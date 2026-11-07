"""Command ownership for the workflow feature."""

HELPERS = ()
OPERATIONS = ("plan_workflow", "init_case", "start_case_revision", "case_status")
RECOVERY = None
DEVELOPMENT = None


def declared_commands():
    from grea.features.adapters import core_commands, helper_commands, stage_commands

    yield from core_commands("workflow", OPERATIONS)
    yield from helper_commands("workflow", HELPERS)
    if RECOVERY:
        yield from stage_commands("workflow", RECOVERY, "recovery")
    if DEVELOPMENT:
        yield from stage_commands("workflow", DEVELOPMENT, "development")
