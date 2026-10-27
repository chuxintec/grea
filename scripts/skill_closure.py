#!/usr/bin/env python3
"""Make every GREA skill standalone: documents a skill links to are copied into its
references/shared/ folder, generated from one canonical owner and recorded in SOURCES.json.

- Links to another skill's SKILL.md become routing text naming that skill.
- Links to non-Markdown repository files become install-path mentions.
- Links inside a copy that point at documents the skill does not copy become text naming
  their owner, so no link ever leaves the skill directory.
`--check` regenerates in memory and reports drift without writing.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT/'plugin/skills'
SHARED = 'shared'
LINK = re.compile(r'(?<!!)\[([^\]]+)\]\((<[^>]+>|[^)\s]+)\)')
FENCE = re.compile(r'^(`{3,}|~{3,})[^\n]*\n.*?^\1\s*$', re.M | re.S)
HEADER = '<!-- 生成副本，勿直接编辑。权威来源：{source}；由 scripts/skill_closure.py 维护。 -->\n\n'


def rel(path):
    return path.relative_to(ROOT).as_posix()


def is_shared(path, skill):
    return path.parent == skill/'references'/SHARED


def canonical_docs(skill):
    return sorted(p for p in skill.rglob('*.md') if not is_shared(p, skill))


def split(target):
    path, _, frag = target.strip('<>').partition('#')
    return path, frag


def owner_label(path):
    """Human pointer for a document that is not part of this skill."""
    if path.is_relative_to(SKILLS):
        skill = path.relative_to(SKILLS).parts[0]
        return f'`{skill}` 技能' + ('' if path.name == 'SKILL.md' else f'《{path.stem}》')
    return f'GREA 安装目录 `{rel(path)}`'


def route_text(label, skill_md):
    """A skill is entered through the router, not copied: name it instead of linking."""
    skill = skill_md.relative_to(SKILLS).parts[0]
    return f'`{skill}` 技能' if label.strip('`') == skill else f'{label}（`{skill}` 技能）'


def map_links(text, base, resolve):
    """Rewrite links outside fenced code; resolve(dest, frag, label) -> replacement or None."""
    out, pos = [], 0
    for fence in list(FENCE.finditer(text)) + [None]:
        end = fence.start() if fence else len(text)
        chunk = text[pos:end]

        def repl(m):
            label, target = m[1], m[2]
            path, frag = split(target)
            if re.match(r'^[a-zA-Z][\w+.-]*:', target) or not path:
                return m[0]
            dest = (base/path).resolve()
            new = resolve(dest, frag, label)
            return m[0] if new is None else new
        out.append(LINK.sub(repl, chunk))
        if fence:
            out.append(fence.group(0)); pos = fence.end()
    return ''.join(out)


def plan_skill(skill, sources_on_disk):
    """Return {path: text} for canonical rewrites and shared copies of one skill."""
    shared_dir = skill/'references'/SHARED
    # Shared links already in canonical files resolve back to their recorded sources.
    back = {shared_dir/name: (ROOT/src).resolve() for name, src in sources_on_disk.items()}
    copies = {}  # source -> local name

    def local_name(source):
        if source in copies: return copies[source]
        name = source.name
        taken = set(copies.values())
        if name in taken or name == 'SOURCES.json':
            name = source.parent.name + '-' + name
        copies[source] = name
        return name

    def canonical_target(dest):
        return back.get(dest, dest)

    results = {}
    for doc in canonical_docs(skill):
        text = doc.read_text(encoding='utf-8')

        def resolve(dest, frag, label, doc=doc):
            dest = canonical_target(dest)
            anchor = '#' + frag if frag else ''
            if dest.is_relative_to(skill) and not is_shared(dest, skill):
                return f'[{label}]({os.path.relpath(dest, doc.parent).replace(os.sep, "/")}{anchor})'
            if not dest.exists():
                return None
            if dest.name == 'SKILL.md' and dest.is_relative_to(SKILLS):
                return route_text(label, dest)
            if dest.suffix != '.md':
                return f'{label}（{owner_label(dest)}）'
            name = local_name(dest)
            return f'[{label}]({os.path.relpath(shared_dir/name, doc.parent).replace(os.sep, "/")}{anchor})'
        results[doc] = map_links(text, doc.parent, resolve)

    sources = {}
    for source, name in sorted(copies.items(), key=lambda x: x[1]):
        text = source.read_text(encoding='utf-8')
        text = re.sub(r'^<!-- 生成副本.*?-->\n\n', '', text, flags=re.S)

        def resolve(dest, frag, label, source=source):
            anchor = '#' + frag if frag else ''
            if dest == source:
                return f'[{label}]({anchor or "#"})'
            if dest in copies:
                return f'[{label}]({copies[dest]}{anchor})'
            if dest.is_relative_to(skill) and not is_shared(dest, skill):
                return f'[{label}]({os.path.relpath(dest, shared_dir).replace(os.sep, "/")}{anchor})'
            if not dest.exists():
                return f'{label}'
            if dest.name == 'SKILL.md' and dest.is_relative_to(SKILLS):
                return route_text(label, dest)
            return f'{label}（{owner_label(dest)}）'
        results[shared_dir/name] = HEADER.format(source=rel(source)) + map_links(text, source.parent, resolve)
        sources[name] = rel(source)
    results[shared_dir/'SOURCES.json'] = json.dumps({'schemaVersion': 1, 'generator': 'scripts/skill_closure.py',
                                                     'sources': sources}, ensure_ascii=False, indent=2) + '\n'
    return results


def run(check=False):
    drift = []
    for skill in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        shared_dir = skill/'references'/SHARED
        manifest = shared_dir/'SOURCES.json'
        recorded = json.loads(manifest.read_text(encoding='utf-8'))['sources'] if manifest.is_file() else {}
        # Two passes: canonical rewrites can introduce shared targets that then need sources.
        planned = plan_skill(skill, recorded)
        expected = {p: t for p, t in planned.items()}
        existing = {p for p in shared_dir.glob('*')} if shared_dir.is_dir() else set()
        for path, text in expected.items():
            current = path.read_text(encoding='utf-8') if path.is_file() else None
            if current != text:
                drift.append(rel(path))
                if not check:
                    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding='utf-8')
        for stale in existing - set(expected):
            drift.append(rel(stale))
            if not check: stale.unlink()
    return drift


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Report drift without writing (default when --write is absent)')
    parser.add_argument('--write', action='store_true', help='Regenerate shared copies and rewrite outward links')
    args = parser.parse_args()
    args.check = not args.write
    drift = run(args.check)
    if not args.check and drift:
        # Copies may themselves have changed canonical sources; settle to a fixed point.
        for _ in range(3):
            if not run(False): break
        drift = run(True)
        print(json.dumps({'ok': not drift, 'written': True, 'drift_after_write': drift}, ensure_ascii=False))
        return 0 if not drift else 1
    print(json.dumps({'ok': not drift, 'drift': drift}, ensure_ascii=False))
    return 0 if not drift else 1


if __name__ == '__main__':
    sys.exit(main())
