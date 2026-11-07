"""Command ownership for the research feature."""

HELPERS = ("research_report",)
OPERATIONS = ("inspect_target",)
RECOVERY = "grea.features.research.recovery"
DEVELOPMENT = None


def declared_commands():
    from grea.features.adapters import core_commands, helper_commands, stage_commands

    yield from core_commands("research", OPERATIONS)
    yield from helper_commands("research", HELPERS)
    if RECOVERY:
        yield from stage_commands("research", RECOVERY, "recovery")
    if DEVELOPMENT:
        yield from stage_commands("research", DEVELOPMENT, "development")
