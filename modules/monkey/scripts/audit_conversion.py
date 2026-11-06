#!/usr/bin/env python3
"""Join a prior source audit to whole-input output ledgers; never claim native success."""
import argparse
from pathlib import Path
from collections import Counter
from monkey.io import safe, read, load, new_output, write_json, sha, stage_document


def audit(candidate, source_audit, output):
    root=safe(candidate);out=new_output(output,[root,source_audit])
    source=load(read(source_audit,max_bytes=128*1024*1024),max_nodes=8_000_000)
    expected={f['inputPath']:f for f in source['files'] if f['route']=='conversion'}
    report=load(read(root/'conversion-result.json'));issues=[];projects=[]
    for project in report['projects']:
        base=root/project['path'];manifest=load(read(base/'manifest.json',max_bytes=128*1024*1024),max_nodes=8_000_000)
        owned={f['path']:f for f in manifest['files']}
        ledger=load(read(base/'Analysis/resource-ledger.json',max_bytes=128*1024*1024),max_nodes=8_000_000)
        actual={f['path']:f for f in ledger['files']}
        for path in sorted(set(expected)|set(actual)):
            if path not in actual:issues.append(dict(code='INPUT_UNACCOUNTED',project=base.name,path=path));continue
            if path not in expected:issues.append(dict(code='UNDECLARED_INPUT',project=base.name,path=path));continue
            src=expected[path];row=actual[path];target=owned.get(row['target'])
            if row['sha256']!=src['sha256'] or row['bytes']!=src['bytes']:
                issues.append(dict(code='INPUT_IDENTITY_MISMATCH',project=base.name,path=path))
            if not target or target['sha256']!=src['sha256'] or target['bytes']!=src['bytes']:
                issues.append(dict(code='RETAINED_CONTENT_MISMATCH',project=base.name,path=path))
        redirects=set()
        for row in ledger['files']:
            if row['category']=='Bundle':
                config=load(read(base/row['target']))
                redirects.update((config['name'],i) for i in config.get('redirect',[])[::2])
        indexed=load(read(base/'Analysis/cocos-assets.json',max_bytes=128*1024*1024),max_nodes=8_000_000)['assets']
        missing=[a for a in indexed if a['status']=='missing_reference']
        reference_accounting=dict(logicalEntries=len(indexed),unlocatedByFilename=len(missing),
            redirectsWithoutOwnFile=sum((a['bundle'],a['index']) in redirects for a in missing),
            unlocatedNonRedirect=[a['sourceId'] for a in missing if (a['bundle'],a['index']) not in redirects])
        spine=load(read(base/'Analysis/spine-closures.json',max_bytes=128*1024*1024))
        code=load(read(base/'Analysis/code-index.json',max_bytes=128*1024*1024),max_nodes=8_000_000)
        item=dict(path=str(base),manifestSha256=sha(read(base/'manifest.json',max_bytes=128*1024*1024)),
                  accountedFiles=len(actual),accountedBytes=sum(f['bytes'] for f in actual.values()),
                  dispositions=dict(Counter(f['disposition'] for f in actual.values())),
                  categories=dict(Counter(f['category'] for f in actual.values())),
                  referenceAccounting=reference_accounting,
                  spine=dict(closed=spine['closed'],unresolved=spine['unresolved'],
                      reasons=dict(Counter(a.get('reason') for a in spine['skeletons'] if a['status']!='closure_recovered'))),
                  code=dict(moduleCandidates=sum(m.get('entryType')=='module_candidate' for m in code['modules']),
                      unresolvedSources=sum(m.get('entryType')=='unresolved_source' for m in code['modules']),business='not_implemented'),
                  native=manifest.get('validation'),targetPlan='not_available')
        planpath=root/'Structured'/(base.name+'-plan')/'plan.json'
        if planpath.exists() and (planpath.parent/'manifest.json').exists():
            plan=stage_document(planpath)
            item['targetPlan']=dict(nodes=len(plan['nodes']),components=len(plan['components']),
                convertibleComponents=sum(c['convertible'] for c in plan['components']),
                sourcePrefabs=len(plan.get('sourcePrefabs',[])),bitmapFonts=len(plan.get('bitmapFonts',[])),assets=dict(Counter(a['kind'] for a in plan['assets'])))
        projects.append(item)
    result=dict(schemaVersion=1,status='pass' if not issues else 'failed',
        scope='source routing and retained bytes bound to generated manifests; disk verification and native execution are separate',
        sourceSummary=source['summary'],projects=projects,issues=issues)
    write_json(out/'audit.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--source-audit',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();result=audit(a.candidate,a.source_audit,a.out)
    print({'status':result['status'],'issues':len(result['issues']),'projects':len(result['projects']),'report':str(Path(a.out)/'audit.json')})
    raise SystemExit(0 if result['status']=='pass' else 1)
