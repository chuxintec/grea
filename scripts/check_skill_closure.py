#!/usr/bin/env python3
"""Check the document closure of an entire GREA Skill set without a product checkout.

This is a document check, not provider, Editor or gameplay validation.
"""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


def without_fences(text):
    return re.sub(r'^(`{3,}|~{3,})[^\n]*\n.*?^\1\s*$', '', text,
                  flags=re.MULTILINE | re.DOTALL)


def local_links(text):
    body = without_fences(text)
    # Inline links/images and reference definitions; fenced examples are data.
    yield from re.findall(r'!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)\)', body)
    yield from re.findall(r'^\s{0,3}\[[^\]]+\]:\s*(<[^>]+>|\S+)', body, re.MULTILINE)


def check(skills_root):
    root = Path(skills_root).resolve()
    errors, graph, links = [], {}, 0
    entries = sorted(root.glob('*/SKILL.md'))
    layout = root / 'grea/assets/skill-layout.json'
    if layout.is_file():
        declared = json.loads(layout.read_text(encoding='utf-8'))['canonical_skills']
        if len(declared) != len(set(declared)) or set(declared) != {p.parent.name for p in entries}:
            errors.append({'code': 'skill_layout_drift', 'expected': declared,
                           'actual': [p.parent.name for p in entries]})
    if not (root / 'grea/SKILL.md').is_file():
        errors.append({'code': 'missing_router'})
    docs = sorted(root.rglob('*.md'))
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            errors.append({'code': 'symlink_not_portable', 'file': str(path.relative_to(root))})
    for path in docs:
        name = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            continue
        text = path.read_text(encoding='utf-8')
        graph[path] = set()
        # Catch prose/code-path references too: changing a link to literal text
        # must not hide a required repository document from the closure check.
        if re.search(r'(?<![\w/])docs/(?:providers/|tools/|examples/|README\.md|[^\s`<>)]*\.md)',
                     re.sub(r'https?://[^\s<>)]*', '', text)):
            errors.append({'code': 'repository_document_reference', 'file': name})
        for raw in local_links(text):
            target = raw.strip('<>')
            url = urlsplit(target)
            if url.scheme in ('http', 'https', 'mailto') or url.netloc:
                continue
            links += 1
            item = {'file': name, 'target': target}
            if url.scheme or Path(unquote(url.path)).is_absolute():
                errors.append(dict(item, code='nonportable_local_link'))
                continue
            dest = (path.parent / unquote(url.path)).resolve() if url.path else path
            if not dest.is_relative_to(root):
                errors.append(dict(item, code='link_outside_skills'))
            elif not dest.exists():
                errors.append(dict(item, code='missing_target'))
            elif dest.suffix == '.md':
                graph[path].add(dest)
    reached, pending = set(), list(entries)
    while pending:
        path = pending.pop()
        if path in reached:
            continue
        reached.add(path)
        pending.extend(graph.get(path, ()))
    for path in docs:
        if 'references' in path.relative_to(root).parts and path not in reached:
            errors.append({'code': 'unreachable_reference', 'file': str(path.relative_to(root))})
    return {'ok': not errors, 'skills': len(entries), 'markdown_files': len(docs),
            'local_links': links, 'errors': errors,
            'scope': 'Skill-set document/resource closure only; runtime tools remain separate dependencies.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-root', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'plugin/skills')
    args = parser.parse_args()
    result = check(args.skills_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ok'] else 1)
