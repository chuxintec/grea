#!/usr/bin/env python3
"""Install the authoritative grea plugin skills into a skills root, rebasing local Markdown links; --check is read-only.

Layout mapping: plugin/skills/<name>/ -> <dest>/<name>/; legacy plugin/shared/ (when present) and plugin/version.json
are installed inside the router skill (<dest>/grea/). Only directories recorded as managed are
written or pruned, so unrelated skills in the same root are left alone.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

LINK = re.compile(r"(\]\()(<[^>]+>|[^\s)]+)(\))")
ROOT = Path(__file__).resolve().parents[1]
# tools/grea remains a product repo; shared skills belong to the enclosing workspace.
def workspace_root(product_root: Path) -> Path:
    return product_root.parent.parent if product_root.parent.name == 'tools' else product_root.parent


WORKSPACE = workspace_root(ROOT)
ROUTER = 'grea'
RECORD = '.grea-install.json'


def skill_names(source: Path) -> list[str]:
    names = sorted(p.name for p in (source / 'skills').iterdir() if (p / 'SKILL.md').is_file())
    if ROUTER not in names:
        raise ValueError('Plugin must contain the router skill skills/grea/SKILL.md')
    return names


def mapping(source: Path) -> dict[Path, Path]:
    """Source file (relative to plugin) -> installed file (relative to destination root)."""
    result = {}
    for file in sorted(source.rglob('*')):
        if file.is_symlink():
            raise ValueError(f'Source symlink is unsupported: {file}')
        relative = file.relative_to(source)
        if not file.is_file() or any(p.startswith('.') or p == '__pycache__' for p in relative.parts):
            continue
        if relative.parts[0] == 'skills' and len(relative.parts) > 2:
            result[relative] = Path(*relative.parts[1:])
        elif relative.parts[0] == 'shared':
            result[relative] = Path(ROUTER, *relative.parts)
        elif relative == Path('version.json'):
            result[relative] = Path(ROUTER, 'version.json')
    return result


def render(source: Path, destination: Path) -> dict[Path, bytes]:
    files = mapping(source)
    by_source = {(source / k).resolve(): v for k, v in files.items()}
    result = {}
    for relative, installed in files.items():
        file = source / relative
        data = file.read_bytes()
        if file.suffix == '.md':
            def replace(match):
                raw = match[2]
                target = raw.strip('<>')
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith('/'):
                    return match[0]
                linked = (file.parent / unquote(parsed.path)).resolve()
                if not linked.exists():
                    raise ValueError(f'Broken source link: {relative}: {target}')
                mapped = destination / by_source[linked] if linked in by_source else linked
                rebased = Path(os.path.relpath(mapped, (destination / installed).parent)).as_posix()
                rewritten = rebased + target[len(parsed.path):]
                if raw.startswith('<') or ' ' in rewritten:
                    rewritten = '<' + rewritten + '>'
                return match[1] + rewritten + match[3]
            data = LINK.sub(replace, data.decode('utf-8')).encode('utf-8')
        result[installed] = data
    return result


def synchronize(source: Path, destination: Path, check: bool = False) -> list[str]:
    source, destination = source.resolve(), destination.absolute()
    if destination.is_symlink():
        raise ValueError('Destination must be a real skills directory')
    destination = destination.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Source and destination must not overlap')
    names = skill_names(source)
    record_path = destination / ROUTER / RECORD
    previous = json.loads(record_path.read_text(encoding='utf-8'))['skills'] if record_path.is_file() else []
    managed = sorted(set(names) | set(previous))
    for name in managed:
        target = destination / name
        if target.is_symlink():
            raise ValueError(f'Destination symlink is unsupported: {target}')
        if target.exists() and not (target / 'SKILL.md').is_file():
            raise ValueError(f'Existing destination must contain SKILL.md: {target}')
        for item in target.rglob('*') if target.exists() else []:
            if item.is_symlink():
                raise ValueError(f'Destination symlink is unsupported: {item}')
    expected = render(source, destination)
    record = (json.dumps({'source': 'grea plugin', 'skills': names}, indent=2) + '\n').encode()
    actual = {p.relative_to(destination): p for name in managed if (destination / name).exists()
              for p in (destination / name).rglob('*') if p.is_file()}
    actual.pop(Path(ROUTER, RECORD), None)
    differences = [str(p) for p, data in expected.items() if p not in actual or actual[p].read_bytes() != data]
    extras = sorted(actual.keys() - expected.keys())
    differences += ['extra: ' + str(p) for p in extras]
    if not record_path.is_file() or record_path.read_bytes() != record:
        differences.append('record: ' + str(Path(ROUTER, RECORD)))
    if not check:
        for relative, data in expected.items():
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)
        for relative in extras:
            actual[relative].unlink()
        record_path.write_bytes(record)
        for name in managed:
            root = destination / name
            if not root.exists():
                continue
            for directory in sorted(root.rglob('*'), key=lambda p: len(p.parts), reverse=True):
                if directory.is_dir() and not any(directory.iterdir()):
                    directory.rmdir()
            if not any(root.iterdir()):
                root.rmdir()
    return differences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=WORKSPACE / '.agents/skills',
                        help='Skills root that receives one directory per grea skill')
    parser.add_argument('--check', action='store_true', help='Report drift without writing')
    args = parser.parse_args()
    try:
        differences = synchronize(ROOT / 'plugin', args.destination, args.check)
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.check and differences:
        print('Skills differ:\n' + '\n'.join(differences))
        return 1
    print('Skills are consistent' if args.check else f'Skills synchronized ({len(differences)} changed files)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
