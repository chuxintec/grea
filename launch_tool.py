#!/usr/bin/env python3
"""Run a bundled module in the interpreter selected by registry.json.

This bootstrap also supports optional provider environments where grea itself is
not installed. CLI/MCP still own selection, budgets and execution receipts.
"""
import re
import runpy
import sys
import traceback
from pathlib import Path

if len(sys.argv) < 2 or not re.fullmatch(r'[a-z][a-z0-9_]*', sys.argv[1]):
    raise SystemExit('Expected a registered bundled module name')
module = sys.argv.pop(1)
sys.path.insert(0, str(Path(__file__).absolute().parent / 'src'))
try:
    from grea.commands.groups import HELPER_MODULE
    prefix = ('grea.features.' + HELPER_MODULE[module]) if module in HELPER_MODULE else 'grea.tools'
    runpy.run_module(prefix + '.' + module, run_name='__main__')
except Exception:
    # Exit 1 is reserved for a tool's intentional findings. An uncaught failure,
    # including import errors in optional provider environments, is always 2.
    traceback.print_exc()
    raise SystemExit(2)
