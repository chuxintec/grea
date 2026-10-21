"""Normalize bounded local evidence and create a new JSON/Markdown research report."""
import argparse,hashlib,json
from jsonschema import Draft202012Validator
from grea.host.paths import Path
from grea.safe_paths import canonical_path,disjoint,relative_name
from grea.research_contracts import documents,KINDS,STAGES

def normalize(source):
    source=canonical_path(source)
    if source.stat().st_size>8*1024**2:raise ValueError('Input exceeds 8 MiB')
    value=json.loads(source.read_text(encoding='utf-8'),parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    Draft202012Validator(documents()['research-input.schema.json']).validate(value)
    sources={};remaining=64*1024**2
    for row in value['sources']:
        if row['id'] in sources:raise ValueError('Duplicate source ID')
        p=source.parent/relative_name(row['path'])
        if any(x.is_symlink() for x in (p,*p.parents)) or not p.is_file():raise ValueError('Missing or linked source')
        if p.stat().st_size>remaining:raise ValueError('Explicit source hash budget exceeded')
        raw=p.read_bytes();remaining-=len(raw)
        if hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('Stale source digest')
        sources[row['id']]=dict(row,bytes=len(raw))
    for row in value['items']+value['protocols']:
        if row['source_id'] not in sources:raise ValueError('Unknown evidence source')
    for j in value.get('judgments',[]):
        if not set(j['source_ids'])<=sources.keys():raise ValueError('Unknown judgment source')
        if j['type']=='fact' and not j['source_ids']:raise ValueError('Fact needs explicit evidence')
    for e in value.get('estimates',[]):
        if any(e[k][0]>e[k][1] for k in ('active_hours','collaboration_days')):raise ValueError('Reversed estimate interval')
    metrics={};gaps=[]
    for kind in KINDS:
        rows=[r for r in value['items'] if r['kind']==kind]
        present={r['stage'] for r in rows}
        metrics[kind]={s:len({r['id'] for r in rows if r['stage']==s}) if s in present else None for s in STAGES}
        metrics[kind]['unique_observed']=len({r['id'] for r in rows}) if rows or kind in value.get('complete_kinds',[]) else None
        if kind not in value.get('complete_kinds',[]):gaps.append(kind+': total coverage not established')
    protocols={direction:{kind:len({r['name'] for r in value['protocols'] if r['direction']==direction and r['kind']==kind}) or None for kind in ('rpc','message','field')} for direction in ('client_to_server','server_to_client','internal')}
    return dict(schema_version=1,status='normalized_evidence_not_development_approval',game=value['game'],input_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),sources=list(sources.values()),metrics=metrics,protocols=protocols,coverage_gaps=gaps,judgments=value.get('judgments',[]),estimates=value.get('estimates',[]),limitations=['Counts are deduplicated caller classifications linked to byte-verified sources; the tool does not parse game semantics or infer missing stages.','Nested fields are not RPCs. Config rows are not gameplay count. Absence is unknown, not zero.','Analyst estimates/judgments are supplied, not a fixed AI speed multiplier or authorization to create a game.'])

def report(source,output):
    source=canonical_path(source);value=normalize(source);output=disjoint(output,source)
    # A report must not overwrite or sit over an explicit source.
    for row in value['sources']:disjoint(output,source.parent/row['path'])
    if output.exists():raise ValueError('Use a new output directory')
    output.mkdir()
    (output/'research.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# '+value['game'],'','状态：证据归一；不自动批准开发。','','## 分析判断']
    lines += [f"- [{j['type']}] {j['topic']}: {j['text']}" for j in value['judgments']] or ['尚无分析者判断；事实指标见JSON，不用统计表替代立项判断。']
    lines += ['','## 成本假设']+[f"- {e['role']}: 主动小时 {e['active_hours']}；协作工作日 {e['collaboration_days']}；后端已包含 {e['backend_included']}；置信度 {e['confidence']}；前提 {'; '.join(e['assumptions'])}" for e in value['estimates']]
    lines += ['','## 证据边界']+['- '+x for x in value['coverage_gaps']+value['limitations']]
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');return value

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:r=report(a.input,a.output);print(json.dumps(dict(status=r['status'],coverage_gaps=len(r['coverage_gaps']))));return 0
    except (OSError,ValueError,KeyError) as e:print(str(e));return 2
if __name__=='__main__':raise SystemExit(main())
