"""Complete-source lexical evidence, separate from executable code recovery."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from .io import safe,read,load,sha,write_json,new_output,finish
from .sources.compiled import fail


def facts(source,expected_sha256=None,selected=()):
    source=safe(source);raw=read(source)
    if expected_sha256 is not None and sha(raw)!=expected_sha256:fail('CODE_GRAPH_SOURCE_IDENTITY',str(source),'Exact source SHA256 required')
    node=shutil.which('node')
    if not node:fail('DEPENDENCY_MISSING','Node','Pinned static Acorn parser requires the installed Node runtime')
    env={k:v for k,v in os.environ.items()if k not in ('NODE_OPTIONS','NODE_PATH')}
    with tempfile.TemporaryDirectory(prefix='monkey-code-graph-')as temp:
        args=[node,'--max-old-space-size=768',str(Path(__file__).with_name('code-graph.cjs'))]
        if selected:
            request=Path(temp)/'selected.json';write_json(request,list(selected));args+=['methods',str(request)]
        with source.open('rb')as stream:
            try:r=subprocess.run(args,stdin=stream,capture_output=True,timeout=120,env=env)
            except subprocess.TimeoutExpired:fail('CODE_GRAPH_TIME_BUDGET',str(source),'Static graph exceeded 120 seconds; source was not executed')
    if r.returncode:
        # Never reproduce source text or environment from parser stderr.
        fail('CODE_GRAPH_PARSE_FAILED',str(source),'Static graph failed within the fixed parser/heap/node budgets')
    if len(r.stdout)>128*1024*1024:fail('CODE_GRAPH_OUTPUT_BUDGET',str(source),'Use a bounded source slice; graph exceeds128MiB')
    report=load(r.stdout,max_nodes=8_000_000)
    if report.get('source')!={'sha256':sha(raw),'bytes':len(raw)}or report.get('sourceExecuted')is not False:
        fail('CODE_GRAPH_SOURCE_IDENTITY',str(source),'Worker evidence differs from input')
    for row in [*report['methods'],*report['classes'],*report.get('methodInventory',[])]:
        span=row['sourceBytes'];a,b=span['start'],span['end']
        if type(a)is not int or type(b)is not int or not 0<=a<b<=len(raw)or sha(raw[a:b])!=row['sourceSha256']:
            fail('CODE_GRAPH_SPAN_IDENTITY',row['id'],'Original byte span/hash differs')
    if sha(read(source))!=sha(raw):fail('SOURCE_CHANGED',str(source),'Source changed while indexing')
    return report


def inspect(source,output,expected_sha256=None,selected=()):
    report=facts(source,expected_sha256,selected);out=new_output(output,[safe(source)])
    report.update(status='source_indexed; methods_not_yet_recovered',compiled='not_run',behavior='not_run',nativeBinding='not_run')
    write_json(out/'code-graph.json',report);finish(out,dict(schemaVersion=1,scopeMode='code-source-index',diagnostics=[]))
    return dict(status='source_indexed',source=report['source'],summary=report['summary'],report=str(out/'code-graph.json'),sourceExecuted=False)


def draft_records(source):
    """Parse complete input once and stream every source function as bounded AST data.

    Class factory wrappers are flattened into their classes/methods. Indexed
    methods and other functions have separate coverage denominators. The worker
    never executes source; JSONL is a temporary static bridge, not a runtime IR.
    """
    source=safe(source);raw=read(source);identity=dict(sha256=sha(raw),bytes=len(raw))
    node=shutil.which('node')
    if not node:fail('DEPENDENCY_MISSING','Node','Static full-source parser requires existing Node')
    env={k:v for k,v in os.environ.items()if k not in ('NODE_OPTIONS','NODE_PATH')}
    with tempfile.TemporaryDirectory(prefix='monkey-draft-ast-') as tmp:
        spool=Path(tmp)/'functions.jsonl'
        with source.open('rb') as src,spool.open('wb') as dst:
            try:
                result=subprocess.run([node,'--max-old-space-size=768',str(Path(__file__).with_name('code-graph.cjs')),'draft-stream'],stdin=src,stdout=dst,stderr=subprocess.DEVNULL,timeout=240,env=env)
            except subprocess.TimeoutExpired:fail('CODE_DRAFT_PARSE_TIMEOUT',source.name,'Static draft stream exceeded240 seconds')
        if result.returncode:fail('CODE_DRAFT_PARSE_FAILED',source.name,'Static parser could not finish; no source program executed')
        if spool.stat().st_size>1024*1024**2:fail('CODE_DRAFT_AST_BUDGET',source.name,'Static AST bridge exceeds1GiB')
        if sha(read(source))!=identity['sha256']:fail('SOURCE_CHANGED',source.name,'Source changed while parsing drafts')
        with spool.open('rb') as stream:
            first=True;finished=False
            while line:=stream.readline(64*1024**2+1):
                if len(line)>64*1024**2:fail('CODE_DRAFT_AST_LINE_BUDGET',source.name,'AST record exceeds64MiB')
                try:
                    row=load(line,max_nodes=3_000_000,max_depth=600)
                except (RecursionError,ValueError):
                    marker=b',"ast":';metadata,found,_=line.partition(marker)
                    if not found:fail('CODE_DRAFT_AST_RECORD',source.name,'Source AST record could not be decoded')
                    row=load(metadata+b'}',max_nodes=500_000,max_depth=96)
                    row['ast']=None;row['diagnostic']='AST decode failed locally; exact source span retained for repair'

                if first:
                    if row.get('record')!='header' or row.get('source')!=identity or row.get('sourceExecuted')is not False:fail('CODE_DRAFT_SOURCE_IDENTITY',source.name,'Draft source identity differs')
                    first=False
                if row.get('record')in ('function','field'):
                    m=row['method'] if row['record']=='function' else row['field'];a,b=m['sourceBytes']['start'],m['sourceBytes']['end']
                    if not 0<=a<b<=len(raw) or sha(raw[a:b])!=m['sourceSha256']:fail('CODE_DRAFT_METHOD_IDENTITY',m['id'],'Source method range/hash differs')
                if row.get('record')=='footer':finished=True
                yield row
            if not finished:fail('CODE_DRAFT_INCOMPLETE',source.name,'Static stream did not complete')
