"""Group by the subject of an operation, independently of the implementing stage."""

MODULES = {
    "system": "版本、能力、工具发现和环境诊断",
    "workflow": "工作流、案例和验收范围",
    "research": "原版调研和来源证据",
    "source": "包体、资源清单、转换和交接",
    "project": "工程上下文、采用、工作区和原生事务",
    "prefab": "Prefab 恢复、脚本挂载、采用和冷读",
    "asset": "图片、字体、着色器、资源引用和纹理",
    "code": "C#、WASM、程序集和方法恢复",
    "config": "配置、表结构和生成",
    "ui": "界面、布局、节点和事件",
    "server": "Go 服务、协议和迁移",
    "qa": "Player 实测、调试、输入与性能",
    "build": "构建、备份、制品和封装",
    "evidence": "证据、画面、对照和验证回执",
}

# Entries within each line are the names in the recovery parser. Unclassified
# commands fail catalog construction, so a newly added action cannot disappear.
RECOVERY_GROUPS = {
    "system": "capabilities diagnose doctor space-preview",
    "source": """convert hydrate-unity index-unity inspect-unity export-unity prepare-unity-bulk
        export-unity-bulk inspect catalog normalize plan export verify preflight handoff
        freeze-unity-handoff freeze-handoff diff research-matrix""",
    "project": """project-model layout-migration shard-unity-plan restore-unity-plan native-import
        native-finish-plan native-finish recover-native-execution freeze-native-selection
        upgrade-native-runtime""",
    "prefab": """select-prefab-presentation audit-prefab-presentation continue-static-prefabs
        prefab-static-fields prefab-behavior-ir recover-unity-prefabs inspect-unity-prefab-schemas
        rebuild-unity-prefab-texture-material-assets rebuild-unity-prefab-assets verify-unity-prefabs
        freeze-unity-prefabs prepare-unity-runtime-hosts""",
    "asset": """resource-probe acquire-resources inspect-aliases acquire-unity-textures
        export-unity-textures classify-unity-shaders freeze-resource-candidate repair-unity-visuals
        refresh-static-spine-helpers complete-static-spine-defaults prepare-button-material-retry
        prepare-source-system-fonts generate-source-system-fonts complete-native-font stage-native-font finish-native-font""",
    "config": "query-tables",
    "code": """query-methods inventory-unity-methods apply-unity-method-overlay unity-field-plan unity-code-model
        lower-cocos-local-methods unity-code-source unity-code-candidate wasm-code-source wasm-code-candidate
        audit-native-code-dependencies static-code-bindings""",
    "ui": """layout-preview native-layout-audit native-layout-prepare native-layout-patch native-layout-finish
        native-layout-bundle prepare-source-text-reference capture-source-text-reference prepare-context-preview""",
}
RECOVERY_MODULE = {name: module for module, names in RECOVERY_GROUPS.items() for name in names.split()}
RECOVERY_MODULE["research-matrix"] = "research"
# These still have callers with old transaction formats. They are available
# only via the documented stage compatibility route.
LEGACY_RECOVERY = {"adopt", "adopt-recover", "register", "apply"}
RENAMED_RECOVERY = {
    "capabilities": "recovery-capabilities", "doctor": "recovery-doctor",
    "recover-unity-prefabs": "recover", "verify-unity-prefabs": "verify", "freeze-unity-prefabs": "freeze",
    "inspect-unity-prefab-schemas": "inspect-schemas", "rebuild-unity-prefab-assets": "rebuild-assets",
    "rebuild-unity-prefab-texture-material-assets": "rebuild-texture-materials",
    "select-prefab-presentation": "select-presentation", "audit-prefab-presentation": "audit-presentation",
    "prefab-static-fields": "static-fields", "prefab-behavior-ir": "behavior-ir",
    "prepare-unity-runtime-hosts": "prepare-hosts", "research-matrix": "matrix",
}

# (module, operation prefix). Preserve distinctions between planning an
# additive intake, whole-project adoption and build/source transactions.
DEVELOPMENT_GROUPS = {
    "version": ("system", "version"), "capabilities": ("system", "development-capabilities"),
    "doctor": ("system", "development-doctor"), "project": ("project", ""), "adopt": ("project", "adopt"),
    "intake": ("prefab", "intake"), "image": ("asset", "image"), "resource": ("asset", "resource"),
    "config": ("config", ""), "config3": ("config", "schema"), "code": ("code", ""),
    "csharp": ("code", "csharp"), "unity": ("project", "unity"), "batch": ("project", "batch"),
    "workspace": ("project", "workspace"), "production": ("project", "production"), "server": ("server", ""),
    "references": ("asset", "references"), "debug": ("qa", "debug"), "player": ("qa", "player"),
    "qa": ("qa", ""), "payload": ("build", "payload"), "ui": ("ui", ""), "wiring": ("ui", "wiring"),
    "diagnostics": ("system", "diagnostics"), "structure": ("project", "structure"),
    "native": ("project", "native"), "build-filter": ("build", "filter"),
}
HELPER_GROUPS = {
    "prefab": "verify_static_set",
    "source": "unpack_xapk unpack_wxapkg decrypt_v1mmwx_wxapkg laya_contract_audit cocos_modules cocos_convert",
    "research": "research_report", "project": "unity_pilot unity_reference cocos_project",
    "asset": "unity_asset_ledger unity_dependency_audit static_asset_copy unity_native_assets shader_probe image_alpha_audit image_contact_sheet audit_numeric_texture cocos_assets",
    "code": "read_elf_values", "config": "export_config_tables unity_config_candidate config_preflight operations_preview compatibility_plan",
    "build": "package_backup package_windows_portable verify_payload_tree",
    "qa": "unity_native_exit performance_compare unity_player_audit",
    "evidence": "evidence_manifest compare_events compare_traces video_manifest video_sheet",
    "ui": "presentation_audit theme_assets", "server": "server_go_project",
    "system": "registry_doctor check_skill toolchain_check",
}
HELPER_MODULE = {name: module for module, names in HELPER_GROUPS.items() for name in names.split()}
CORE_GROUPS = {
    "system": "command_catalog session list_tools describe_tool doctor run_tool",
    "research": "inspect_target", "workflow": "plan_workflow init_case start_case_revision case_status",
    "evidence": "add_evidence record_verification compare_gameplay_traces",
    "asset": "audit_unity_dependencies snapshot_unity_assets inspect_numeric_texture",
    "project": "validate_unity_project plan_unity_project plan_unity_generation generate_unity_project recover_unity_generation",
}
CORE_MODULE = {name: module for module, names in CORE_GROUPS.items() for name in names.split()}


def recovery_route(path):
    name = path[0]
    if name.startswith("code-"):
        return "code", name.removeprefix("code-")
    if name == "static-code-bindings":
        return "code", "bindings-" + path[1]
    return RECOVERY_MODULE[name], RENAMED_RECOVERY.get(name, name)


def development_route(path):
    module, prefix = DEVELOPMENT_GROUPS[path[0]]
    return module, "-".join(p for p in (prefix, *path[1:]) if p)
