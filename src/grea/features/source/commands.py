"""Command ownership for the source feature."""

HELPERS = (
    "unpack_xapk",
    "unpack_wxapkg",
    "decrypt_v1mmwx_wxapkg",
    "laya_contract_audit",
    "cocos_modules",
    "cocos_convert",
)
OPERATIONS = ()
RECOVERY = "grea.features.source.recovery"
DEVELOPMENT = None


def declared_commands():
    from grea.features.adapters import core_commands, helper_commands, stage_commands

    yield from core_commands("source", OPERATIONS)
    yield from helper_commands("source", HELPERS)
    if RECOVERY:
        yield from stage_commands("source", RECOVERY, "recovery")
    if DEVELOPMENT:
        yield from stage_commands("source", DEVELOPMENT, "development")
