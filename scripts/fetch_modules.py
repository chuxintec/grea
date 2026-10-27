#!/usr/bin/env python3
"""Download the monkey/beaver wheels pinned in modules.lock.json into a directory (build/CI helper)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from grea.modules import fetch  # noqa: E402

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(fetch(args.out), ensure_ascii=False))
