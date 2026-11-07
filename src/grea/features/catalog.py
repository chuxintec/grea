"""Feature discovery shared by public commands and historical stage adapters."""

from importlib import import_module

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


def feature_modules():
    for name in MODULES:
        yield name, import_module(f"grea.features.{name}.commands")


def stage_modules(stage):
    if stage not in ("recovery", "development"):
        raise ValueError(f"Unknown stage: {stage}")
    for _, feature in feature_modules():
        path = getattr(feature, stage.upper())
        if path:
            yield import_module(path)


def stage_owner(stage, command):
    matches = [module for module in stage_modules(stage) if command in module.ROUTES]
    if len(matches) != 1:
        raise ValueError(f"Unknown or duplicate {stage} command: {command}")
    return matches[0]


def helper_owners():
    return _owners("HELPERS")


def core_owners():
    return _owners("OPERATIONS")


def _owners(field):
    result = {}
    for module, feature in feature_modules():
        for name in getattr(feature, field):
            if name in result:
                raise ValueError(f"Duplicate {field} owner: {name}")
            result[name] = module
    return result
