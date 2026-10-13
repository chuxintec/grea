#!/usr/bin/env python3
"""Run a bundled module in the interpreter selected by registry.json.

This bootstrap also supports optional provider environments where grea itself is
not installed. CLI/MCP still own selection, budgets and execution receipts.
"""
import re
import runpy
import sys
from pathlib import Path

if len(sys.argv) < 2 or not re.fullmatch(r'[a-z][a-z0-9_]*', sys.argv[1]):
    raise SystemExit('Expected a registered bundled module name')
module = sys.argv.pop(1)
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
runpy.run_module('grea.tools.' + module, run_name='__main__')
