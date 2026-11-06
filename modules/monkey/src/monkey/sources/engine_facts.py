"""Bounded source-version declarations from a static AST, never source execution."""
import os,shutil,subprocess
from pathlib import Path
from ..io import safe,read,sha,load
from .compiled import fail


def inspect(source,include_settings=False):
    source=safe(source);raw=read(source);node=shutil.which('node')
    if not node:fail('DEPENDENCY_MISSING','Node','Static source version parser required')
    env={k:v for k,v in os.environ.items()if k not in ('NODE_OPTIONS','NODE_PATH')}
    with source.open('rb')as stream:
        run=subprocess.run([node,'--max-old-space-size=256',str(Path(__file__).with_name('engine-facts.cjs')),*(['--settings']if include_settings else [])],stdin=stream,capture_output=True,timeout=30,env=env)
    if run.returncode:fail('SOURCE_ENGINE_AST_FAILED',str(source),'Version assignment could not be statically parsed')
    result=load(run.stdout)
    if result.get('source')!={'sha256':sha(raw),'bytes':len(raw)}or result.get('sourceCodeExecuted')is not False:
        fail('SOURCE_ENGINE_IDENTITY',str(source),'Static input identity differs')
    for fact in [*result['facts'],*result.get('settings',[])]:
        start,end=fact['sourceBytes']['start'],fact['sourceBytes']['end']
        if not 0<=start<end<=len(raw)or sha(raw[start:end])!=fact['sha256']:fail('SOURCE_ENGINE_IDENTITY',str(source),'Version span differs')
    return result
