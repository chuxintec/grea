#!/usr/bin/env python3
"""Install the authoritative skill, rebasing local Markdown links; --check is read-only."""
import argparse
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

LINK = re.compile(r"(\]\()(<[^>]+>|[^\s)]+)(\))")
ROOT = Path(__file__).resolve().parents[1]


def render(source: Path, destination: Path) -> dict[Path, bytes]:
    result = {}
    for file in sorted(source.rglob('*')):
        if file.is_symlink():
            raise ValueError(f'Source symlink is unsupported: {file}')
        if not file.is_file() or any(p.startswith('.') or p == '__pycache__' for p in file.relative_to(source).parts):
            continue
        relative = file.relative_to(source)
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
                try:
                    mapped = destination / linked.relative_to(source)
                except ValueError:
                    mapped = linked
                rebased = Path(os.path.relpath(mapped, (destination / relative).parent)).as_posix()
                suffix = target[len(parsed.path):]
                rewritten = rebased + suffix
                if raw.startswith('<') or ' ' in rewritten:
                    rewritten = '<' + rewritten + '>'
                return match[1] + rewritten + match[3]
            data = LINK.sub(replace, data.decode('utf-8')).encode('utf-8')
        result[relative] = data
    return result


def synchronize(source: Path, destination: Path, check: bool = False) -> list[str]:
    source, destination = source.resolve(), destination.absolute()
    if destination.name != 'grea' or destination.is_symlink():
        raise ValueError('Destination must be a real directory named grea')
    destination = destination.resolve()
    if source == destination.resolve() or source in destination.resolve().parents or destination.resolve() in source.parents:
        raise ValueError('Source and destination must not overlap')
    if destination.exists() and not (destination / 'SKILL.md').is_file():
        raise ValueError('Existing destination must contain SKILL.md')
    for item in destination.rglob('*') if destination.exists() else []:
        if item.is_symlink():
            raise ValueError(f'Destination symlink is unsupported: {item}')
    expected = render(source, destination)
    actual = {p.relative_to(destination): p for p in destination.rglob('*') if p.is_file()}
    differences = [str(p) for p, data in expected.items() if p not in actual or actual[p].read_bytes() != data]
    extras = sorted(actual.keys() - expected.keys())
    differences += ['extra: ' + str(p) for p in extras]
    if not check:
        for relative, data in expected.items():
            path = destination / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_bytes() != data:
                path.write_bytes(data)
        for relative in extras:
            actual[relative].unlink()
        for directory in sorted(destination.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
    return differences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=ROOT.parent / '.agents/skills/grea')
    parser.add_argument('--check', action='store_true', help='Report drift without writing')
    args = parser.parse_args()
    try:
        differences = synchronize(ROOT / 'skill', args.destination, args.check)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.check and differences:
        print('Skill differs:\n' + '\n'.join(differences))
        return 1
    print('Skill is consistent' if args.check else f'Skill synchronized ({len(differences)} changed files)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
