"""Generate the public command index from the same parsers that execute it."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from grea.commands.interface import inventory


def display_parameter(field):
    flags = field["flags"]
    flag = next((s for s in flags if s.startswith("--")), field["name"])
    suffix = "…" if field["repeatable"] or field["nargs"] in ("+", "*") else ""
    return f"`{flag}{suffix}`"


def generate(root=ROOT):
    data = inventory()
    lines = [
        "# 功能模块和命令参数",
        "",
        "此表由实际执行用的参数解析器生成。运行 `grea commands 模块 动作` 查看类型、默认值、可选值和互斥要求，追加 `--json` 可读取结构化清单。",
        "",
        "命令格式为 `grea 模块 动作 [参数]`。也可用 `grea --request 参数文件 模块 动作`，文件内容是一个 JSON 对象，键为去掉前导短横线的参数名；重复参数用数组，开关用布尔值。文件名 `-` 表示标准输入。同一调用选择一种输入方式。",
        "",
        "标准回执含 product、version、command、status、exit_code、result 和 diagnostics。result 保留操作自己的材料和原生验证结果。0 表示本次调用成功，1 表示部分完成或有检查发现，2 表示错误，3 表示阻塞；外层退出码继承实际操作。",
        "",
    ]
    for name, description in data["modules"].items():
        rows = [c for c in data["commands"] if c["module"] == name]
        lines += [f"## {name} · {description}", "", "| 动作 | 必需参数 | 可选参数 |",
                  "|---|---|---|"]
        for row in rows:
            params = row["parameters"]
            required = " ".join(display_parameter(p) for p in params if p["required"])
            optional = " ".join(display_parameter(p) for p in params if not p["required"])
            groups = []
            for g in row["exclusiveGroups"]:
                if g["required"]:
                    groups.append(" / ".join(display_parameter(p) for p in params if p["dest"] in g["options"]))
            if groups:
                required += " " + "；".join("任选一项 "+s for s in groups)
            lines.append(f"| `{row['action']}` | {required.strip() or '—'} | {optional or '—'} |")
        lines.append("")
    return {
        root/"schemas/commands.json": json.dumps(data, ensure_ascii=False, indent=2)+"\n",
        root/"plugin/skills/grea/references/功能模块和命令参数.md": "\n".join(lines),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    drift = []
    for path, content in generate().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                drift.append(path.relative_to(ROOT).as_posix())
        else:
            path.write_text(content, encoding="utf-8")
    print(json.dumps({"ok":not drift, "drift":drift}))
    return int(bool(drift))


if __name__ == "__main__":
    sys.exit(main())
