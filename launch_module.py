#!/usr/bin/env python3
"""Run a tool from a monkey/beaver wheel bundled with this GREA install: `launch_module.py <module> tool <id> [args]`.

Used only when no module installation is bound or discovered. The wheel must match
modules.lock.json byte for byte; it is imported in place (pure-Python wheel) on the GREA
interpreter, whose runtime already provides the modules' shared libraries.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).absolute().parent


def main(argv):
    if len(argv) < 2 or argv[1] != 'tool':
        print('usage: launch_module.py <monkey|beaver> tool <id> [args...]', file=sys.stderr)
        return 2
    name = argv[0]
    lock = json.loads((ROOT/'modules.lock.json').read_text(encoding='utf-8'))
    entry = next((m for m in lock['modules'] if m['name'] == name), None)
    if entry is None:
        print('unknown GREA module: ' + name, file=sys.stderr)
        return 2
    wheel = ROOT/'modules'/'wheels'/entry['wheel']['file']
    if not wheel.is_file():
        print('bundled module wheel missing: ' + str(wheel), file=sys.stderr)
        return 2
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    if digest != entry['wheel']['sha256']:
        print('bundled module wheel differs from modules.lock.json: ' + name, file=sys.stderr)
        return 2
    sys.path.insert(0, str(wheel))
    runner = __import__(entry['import'] + '.toolkit.runner', fromlist=['main'])
    return runner.main(argv[2:])


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
