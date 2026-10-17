"""Launch the one grea implementation from a read-only, relocatable plugin."""
import os
from pathlib import Path
import sys

for stream in (sys.stdin,sys.stdout,sys.stderr):
    if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')

ROOT = Path(__file__).absolute().parents[2]
os.environ['GREA_HOME'] = str(ROOT)
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['PYTHONNOUSERSITE'] = '1'
os.environ['PYTHONUTF8'] = '1'
for key in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV'):
    os.environ.pop(key, None)
sys.path.insert(0, str(ROOT / 'src'))

from grea.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
