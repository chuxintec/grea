#!/usr/bin/env python3
"""Build a prepared synthetic sample in a NEW working copy; never build in source Assets."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET


def fingerprint(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def build(source, work, output, timeout=600, execute=subprocess.run, run_tests=False):
    source, work, output = (Path(p).absolute() for p in (source, work, output))
    for path in (source, work, output):
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('Symlink paths are not supported')
    source, work, output = (p.resolve() for p in (source, work, output))
    sample = (source / 'grea-framework-sample.marker').read_text().strip()
    if sample not in ('numeric-combat', 'grid-puzzle') or not (source / 'sample-seeded.json').is_file():
        raise ValueError('Expected a prepared and Editor-seeded grea sample')
    if work.exists() or output.exists() or source == work or source in work.parents or work in source.parents:
        raise ValueError('Working copy and output must be new, outside source')
    if source in output.parents or work == output or work in output.parents:
        raise ValueError('Build output must be outside source and working copy')
    roots = [source / name for name in ('Assets', 'Packages', 'ProjectSettings')]
    if any(p.is_symlink() for root in roots for p in (root, *root.rglob('*'))):
        raise ValueError('Source must be self-contained, without links')
    before = fingerprint(source / 'Assets')
    work.mkdir(parents=True)
    for root in roots:
        shutil.copytree(root, work / root.name)
    for name in ('sample-seeded.json', 'grea-framework-sample.marker'):
        shutil.copyfile(source / name, work / name)
    namespace = 'Numeric' if sample == 'numeric-combat' else 'Puzzle'
    command = ['unity', 'build', str(work), '--target', 'StandaloneOSX', '--execute-method',
               namespace + '.Editor.SampleBuilder.Build', '--output-path', str(output),
               '--timeout', str(timeout), '--format', 'json', '--no-tail', '--log-file', str(work / 'build.log')]
    try:
        if run_tests:
            for mode in ('EditMode', 'PlayMode'):
                report = work / (mode.lower() + '.xml')
                test_command = ['unity', 'test', str(work), '--mode', mode, '--output', str(report), '--timeout',
                                str(timeout), '--format', 'json', '--', '-nographics', '-logFile', str(work / (mode.lower() + '.log'))]
                tested = execute(test_command, capture_output=True, text=True)
                (work / (mode.lower() + '-command.json')).write_text(tested.stdout)
                if tested.returncode != 0 or not report.exists():
                    raise RuntimeError(mode + ' failed; test evidence preserved')
                result = ET.parse(report).getroot()
                if result.get('result') != 'Passed' or int(result.get('passed', '0')) <= 0 or int(result.get('skipped', '0')):
                    raise RuntimeError(mode + ' did not pass every discovered test')
        completed = execute(command, capture_output=True, text=True)
        (work / 'build-command.json').write_text(completed.stdout)
        (work / 'build-stderr.txt').write_text(completed.stderr)
        if completed.returncode != 0:
            raise RuntimeError('Unity build failed; preserved working copy contains command and Editor logs')
        if not output.is_dir():
            raise RuntimeError('Unity exited without the expected Player')
        if fingerprint(source / 'Assets') != before:
            raise RuntimeError('SOURCE_ASSETS_CHANGED')
        receipt = dict(sample=sample, sourceAssetsSha256=hashlib.sha256(json.dumps(before, sort_keys=True,
                       separators=(',', ':')).encode()).hexdigest(), sourceAssetsUnchanged=True,
                       workMayContainUnityBuildCaches=True, sourceFiles=len(before))
        (work / 'source-preservation.json').write_text(json.dumps(receipt, indent=2) + '\n')
        return receipt
    finally:
        # Never overwrite source to disguise changes. Retain evidence and fail if any source byte changed.
        if fingerprint(source / 'Assets') != before:
            raise RuntimeError('SOURCE_ASSETS_CHANGED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--work', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--test', action='store_true', help='Run EditMode and PlayMode in the working copy before building')
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.work, args.output, args.timeout, run_tests=args.test), indent=2))
