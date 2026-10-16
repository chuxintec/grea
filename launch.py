#!/usr/bin/env python3
"""Portable source-workspace launcher. No global install or implicit dependency download."""
import os,subprocess,sys
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent
    portable=root/'runtime/bin/python3'
    if portable.is_file() and (root/'plugin/launcher/start.py').is_file():
        command=[str(portable),'-I','-B',str(root/'plugin/launcher/start.py'),*sys.argv[1:]]
        if os.name=='nt':return subprocess.call(command)
        os.execv(str(portable),command)
    python=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.is_file():
        print(f'grea runtime missing. Run: uv sync --project "{root}" --frozen',file=sys.stderr)
        return 2
    env=dict(os.environ,GREA_HOME=str(root),PYTHONUTF8='1')
    command=[str(python),'-m','grea.cli',*sys.argv[1:]]
    if os.name=='nt':return subprocess.call(command,env=env)
    os.execve(str(python),command,env)
if __name__=='__main__':raise SystemExit(main())
