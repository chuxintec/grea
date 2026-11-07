"""Command ownership for the evidence feature."""

HELPERS = ("evidence_manifest", "compare_events", "compare_traces", "video_manifest", "video_sheet")
OPERATIONS = ("add_evidence", "record_verification", "compare_gameplay_traces")
RECOVERY = None
DEVELOPMENT = None


def declared_commands():
    from grea.features.adapters import core_commands, helper_commands, stage_commands

    yield from core_commands("evidence", OPERATIONS)
    yield from helper_commands("evidence", HELPERS)
    if RECOVERY:
        yield from stage_commands("evidence", RECOVERY, "recovery")
    if DEVELOPMENT:
        yield from stage_commands("evidence", DEVELOPMENT, "development")
