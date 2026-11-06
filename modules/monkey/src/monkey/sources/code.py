"""Static source recovery via vendored, pinned AST parser. Never execute input JS."""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from ..io import sha


def modules(raw, source_path=None):
    node = shutil.which('node')
    if not node:
        return [], dict(code='DEPENDENCY_MISSING',message='Node is required for static module AST recovery')
    adapter = 'system-register-v1' if b'System.register' in raw else 'define-browserify-v1' if b'define(' in raw else 'browserify-table-v1'
    env = {k:v for k,v in os.environ.items() if k not in ('NODE_OPTIONS','NODE_PATH')}
    parser = Path(__file__).with_name('index-modules.cjs')
    attempts=[adapter]
    if adapter=='define-browserify-v1': attempts+=['define-factory-candidates-v1','define-multi-factory-candidates-v1']
    if b'cc._RF.push' in raw: attempts+=['rf-regions-v1']
    for attempt in attempts:
        try:
            # A regular stdin file avoids host Node pipe-read failures on large inputs.
            with open(source_path,'rb') if source_path else tempfile.TemporaryFile() as stream:
                if not source_path: stream.write(raw);stream.seek(0)
                run = subprocess.run([node,'--max-old-space-size=512',str(parser),attempt],stdin=stream,
                                     capture_output=True,timeout=30,env=env)
            if not run.stdout:
                oom=b'heap out of memory' in run.stderr
                return [],dict(code='AST_MEMORY_BUDGET' if oom else 'AST_PROCESS_FAILED',
                               message='Static parser exceeded the 512 MiB heap budget' if oom else 'Static parser exited without JSON',returncode=run.returncode)
            report = json.loads(run.stdout)
        except (OSError,ValueError,subprocess.TimeoutExpired) as error:
            return [],dict(code='AST_UNAVAILABLE',message=str(error))
        if 'error' in report:
            if report['error']['code'] in ('UNSUPPORTED_WRAPPER','EMPTY_INPUT','AMBIGUOUS_WRAPPER'): continue
            return [],report['error']
        if run.returncode:
            return [],dict(code='AST_FAILED',message='Static parser exited without a usable result')
        for module in report['modules']:
            start,end=module['source_bytes']['start'],module['source_bytes']['end']
            if not 0<=start<end<=len(raw) or sha(raw[start:end])!=module['sha256']:
                return [],dict(code='SOURCE_IDENTITY_MISMATCH',message='AST module byte-range/hash mismatch')
        partial = report.get('issues') or any(m.get('unresolved') for m in report['modules'])
        return report['modules'], (dict(code='MODULE_RECOVERY_PARTIAL',
            message='Static candidates require enclosing context/module identity recovery',
            issues=report.get('issues',[]),sourceFormat=report.get('source_format')) if partial else None)
    return [],dict(code='UNSUPPORTED_WRAPPER',message='No supported literal module table; complete source retained')


def drafts(module, module_id, namespace='Game.Gameplay.Unclassified'):
    """Named source members for AI editing; no fabricated unified Invoke API."""
    import re
    token='M'+sha(module_id.encode())[:20]
    from ..layout.code import class_name
    name=class_name(dict(module,sourceId=module_id))
    members=module.get('syntax',{}).get('members',{})
    methods=members.get('methods',[]);fields=members.get('fields',[])
    if not methods:methods=[dict(f,static=True,ownerAlias=None)for f in members.get('functions',[])]
    from ..unity_code_model import CS_KEYWORDS
    def identifier(value):
        if not isinstance(value,str)or not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',value):return None
        return '@'+value if value in CS_KEYWORDS else value
    header=['// Named source declaration draft; outside Assets and not compiled.',
            '// TODO: recover source ownership/types/behavior from exact original module. No methods are marked implemented.',
            '// Source module: '+json.dumps(module_id),
            '// Source module SHA256: '+str(module.get('sha256','unknown'))]
    cs=header+['namespace '+namespace+' {', '  public partial class '+identifier(name)+' {']
    ts=header+['export class '+name+' {']
    known_fields=set()
    for f in fields:
        member=identifier(f.get('name'))
        if not member or f['name']in known_fields:continue
        known_fields.add(f['name']);span=f.get('sourceBytes',{})
        comment='    // TODO source field type; owner '+str(f.get('ownerAlias'))+'; bytes '+str(span.get('start'))+'..'+str(span.get('end'))
        cs += [comment,'    public object '+member+';'];ts += [comment,'  '+f['name']+': unknown;']
    seen=set()
    for m in methods:
        member=identifier(m.get('name'));params=m.get('parameters',[])
        param_names=[identifier(p.get('name'))or('arg'+str(i))for i,p in enumerate(params)]
        if len(set(param_names))!=len(param_names):param_names=['arg'+str(i)for i in range(len(params))]
        key=(m.get('name'),len(params));span=m.get('sourceBytes',{})
        comment='    // TODO source body/types; owner '+str(m.get('ownerAlias'))+'; bytes '+str(span.get('start'))+'..'+str(span.get('end'))+'; SHA256 '+str(m.get('sourceSha256','unknown'))
        cs.append(comment);ts.append(comment)
        if not member or key in seen:
            cs.append('    // Unresolved/duplicate original member signature: '+json.dumps(m.get('name'))+'('+', '.join(p.get('sourceBinding',p.get('name')or'?')for p in params)+')')
            ts.append('    // Ambiguous source member retained in method index; no duplicate placeholder emitted.')
            continue
        seen.add(key);stat='static 'if m.get('static')else''
        cs += ['    public '+stat+'object '+member+'('+', '.join('object '+p for p in param_names)+') {',
               '      throw new System.NotImplementedException("TODO: restore '+str(m.get('name')).replace('"','')+' from original source");','    }']
        ts += ['  '+stat+json.dumps(m['name'])+'('+', '.join(p.removeprefix('@')+': unknown'for p in param_names)+'): unknown {',
               '    throw new Error("TODO: restore original source method");','  }']
    if not methods and not fields:
        cs=header+['// No proven member declarations; original source retained. No empty class fabricated.']
        ts=header+['// No proven member declarations; original source retained.']
    else:cs+=['  }','}'];ts+=['}']
    return token,'\n'.join(cs)+'\n','\n'.join(ts)+'\n'
