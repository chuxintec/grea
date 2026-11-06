"""Developer demo with synthetic fixtures. Creates a fresh, isolated candidate."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from fixtures import fixture
from monkey.io import new_output
from monkey.sources.bundle import inspect
from monkey.normalize import normalize
from monkey.targets.unity import plan, export, verify, handoff

p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--ui',action='store_true')
a=p.parse_args();out=new_output(a.out)
config=fixture(out/'source')
inspect(config,[2 if a.ui else 0],out/'inspect')
normalize(out/'inspect/source-manifest.json',out/'normalized')
plan(out/'normalized/ir.json','synthetic-demo',out/'plan')
result=export(out/'plan/plan.json',out/'unity')
verify(out/'unity',out/'static')
handoff(out/'unity',out/'handoff')
print('Candidate:',out/'unity','status:',result['status'],'Editor/visual/business: not_run')
