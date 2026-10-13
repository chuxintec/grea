#!/usr/bin/env python3
"""Copy M2 package sources into a NEW isolated Unity test project. Never opens Unity."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / 'tools/unity/framework/packages'
SAMPLE = ROOT / 'tools/unity/templates/counter-composition/Assets'


def prepare(destination, include_sample=True):
    destination = Path(destination).absolute()
    if any(p.is_symlink() for p in (destination, *destination.parents)):
        raise ValueError('Symlink output is not supported')
    if destination.exists():
        raise ValueError('Output must be a new directory; existing projects are never modified')
    sources = [p for base in ((PACKAGES, SAMPLE) if include_sample else (PACKAGES,)) for p in base.rglob('*')]
    if any(p.is_symlink() or (not p.is_file() and not p.is_dir()) for p in sources):
        raise ValueError('Only regular source files/directories are supported')
    snapshot = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sources if p.is_file()}
    destination.mkdir(parents=True)
    shutil.copytree(PACKAGES, destination / 'Packages')
    if include_sample:
        shutil.copytree(SAMPLE, destination / 'Assets')
    else:
        (destination / 'Assets').mkdir()
    dependencies = {'com.unity.render-pipelines.universal': '17.6.0', 'com.unity.ugui': '2.6.0',
                    'com.unity.test-framework': '1.8.0', 'com.unity.modules.audio': '1.0.0'}
    manifest = {'dependencies': dependencies, 'testables': sorted(p.name for p in PACKAGES.iterdir() if p.is_dir())}
    (destination / 'Packages/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    lock = ROOT / 'tools/unity/framework/test-packages-lock.json'
    if lock.exists():
        shutil.copyfile(lock, destination / 'Packages/packages-lock.json')
    (destination / 'ProjectSettings').mkdir()
    (destination / 'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.6.2f1\n')
    (destination / 'grea-m2-inputs.json').write_text(json.dumps(snapshot, indent=2) + '\n')
    return {'project': str(destination), 'sourceFiles': len(snapshot), 'editor': '6000.6.2f1',
            'unityExecuted': False, 'includesSample': include_sample}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--packages-only', action='store_true', help='Compile packages without any Game assemblies')
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, not args.packages_only), indent=2))
