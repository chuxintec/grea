"""Command ownership for the project feature."""

HELPERS = ("unity_pilot", "unity_reference", "cocos_project")
OPERATIONS = (
    "validate_unity_project",
    "plan_unity_project",
    "plan_unity_generation",
    "generate_unity_project",
    "recover_unity_generation",
)
RECOVERY = "grea.features.project.recovery"
DEVELOPMENT = "grea.features.project.development"


def declared_commands():
    from grea.features.adapters import core_commands, helper_commands, stage_commands

    yield from core_commands("project", OPERATIONS)
    yield from helper_commands("project", HELPERS)
    if RECOVERY:
        yield from stage_commands("project", RECOVERY, "recovery")
    if DEVELOPMENT:
        yield from stage_commands("project", DEVELOPMENT, "development")
