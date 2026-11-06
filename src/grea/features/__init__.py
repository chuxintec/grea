"""Tools shared by the public functional modules and stage-compatible calls."""
from importlib import import_module
import sys

from grea.commands.groups import HELPER_MODULE

RECOVERY_TOOLS = ('laya_contract_audit', 'read_elf_values', 'unpack_xapk', 'shader_probe', 'decrypt_v1mmwx_wxapkg', 'unpack_wxapkg', 'export_config_tables')
DEVELOPMENT_TOOLS = ('unity_asset_ledger', 'unity_dependency_audit', 'compare_traces', 'compare_events', 'video_manifest', 'video_sheet', 'verify_payload_tree', 'package_windows_portable', 'audit_numeric_texture', 'image_alpha_audit', 'image_contact_sheet', 'package_backup', 'static_asset_copy', 'unity_native_exit', 'unity_config_candidate', 'unity_native_assets', 'evidence_manifest', 'config_preflight', 'presentation_audit', 'performance_compare', 'compatibility_plan', 'operations_preview', 'unity_pilot')

def helper(name):
    return import_module(f"grea.features.{HELPER_MODULE[name]}.{name}")


def run_tool(argv, names, prog):
    if not argv or argv[0] in ("-h", "--help"):
        print(f"usage: {prog} tool <id> [args...]\n\ntools: " + ", ".join(names))
        return 0 if argv else 2
    name, *arguments = argv
    if name not in names:
        print(f"Unknown tool: {name}", file=sys.stderr)
        return 2
    try:
        return helper(name).main(arguments) or 0
    except (OSError, ValueError, ImportError) as error:
        print(str(error), file=sys.stderr)
        return 2
