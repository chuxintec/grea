"""Read-only dynamic Research denominator. Hints never stand in for parser evidence."""
import re
import unicodedata
from collections import Counter
from pathlib import Path
from .io import safe, read, load, sha, new_output, write_json
from .sources.compiled import fail

MAX_CASES=500


def _hint(engine):
    if not isinstance(engine,str) or not engine.strip():
        return dict(family='unknown',version=None,backend=None,confidence='unknown')
    lowered=engine.lower()
    family=('cocos' if 'cocos' in lowered else 'tuanjie' if '团结' in engine or 'tuanjie' in lowered
            else 'unity' if 'unity' in lowered else 'laya' if 'laya' in lowered
            else 'egret' if 'egret' in lowered else 'unknown')
    match=re.search(r'\b(?:20\d{2}|6000)\.\d+\.\d+[a-z]\d+(?:[a-z]\d+)?|\b\d+\.\d+\.\d+\b',engine)
    backend='wasm' if 'wasm' in lowered else 'mono' if 'mono' in lowered else None
    return dict(family=family,version=match.group() if match else None,backend=backend,
                lua='lua' in lowered,confidence='metadata_hint_only')


def discover(root,output):
    root=safe(root)
    if not root.is_dir():fail('RESEARCH_ROOT',str(root),'Expected explicit Research games directory')
    # Reserve output first, never traverse/write a source subtree as a generated case.
    out=new_output(output,[root]);folders=sorted(p for p in root.iterdir() if p.is_symlink() or p.is_dir())
    folders=[p for p in folders if not p.name.startswith(('_','.'))]
    if len(folders)>MAX_CASES:fail('RESEARCH_CASE_BUDGET',str(root),'Too many game directories')
    cases=[];seen=set()
    for folder in folders:
        key=unicodedata.normalize('NFC',folder.name).casefold()
        if key in seen:fail('RESEARCH_NAME_COLLISION',folder.name,'Case/Unicode-equivalent game directory')
        seen.add(key)
        case=dict(caseId=sha(unicodedata.normalize('NFC',folder.name).encode())[:24],name=folder.name,
                  relativeRoot=folder.name,sourceRevision=None,engineHint=_hint(None),
                  stages=dict(identity='not_run',read='not_run',export='not_run',native='not_run',business='not_run'),
                  sourceEvidence=[],diagnostics=[],targets=['unity6'],conversion='not_run')
        if folder.is_symlink():
            case['diagnostics'].append(dict(code='RESEARCH_LINK_NOT_FOLLOWED',message='Explicit source registration required'))
            case['availability']='blocked_source';cases.append(case);continue
        metadata=folder/'RESEARCH.json'
        data={}
        if metadata.is_file():
            try:
                raw=read(metadata);data=load(raw)
                if not isinstance(data,dict) or not isinstance(data.get('identity',{}),dict):
                    raise ValueError('Expected identity object')
                identity=data.get('identity',{})
                case.update(metadataSha256=sha(raw),sourceRevision=identity.get('observedSourceVersion'),
                            engineHint=_hint(identity.get('sourceEngine')))
                # Record declared external references; never follow or enumerate them here.
                pointer=identity.get('originalSource')
                if isinstance(pointer,str) and pointer:
                    case['declaredSourceReference']=pointer
                case['sourceEvidence'].append(dict(path='RESEARCH.json',kind='identity_metadata',sha256=sha(raw),parsedBody=False))
            except (ValueError,UnicodeError,RecursionError,KeyError) as error:
                case['diagnostics'].append(dict(code='RESEARCH_METADATA_INVALID',message=type(error).__name__))
        else:case['diagnostics'].append(dict(code='RESEARCH_METADATA_MISSING',message='Game remains in denominator'))
        sources=folder/'Evidence/source'
        if sources.is_dir() and not sources.is_symlink():
            # Only the explicit source-manifest layout, not arbitrary recursive game/cache scans.
            manifests=[sources/'manifest.json',*[p/'manifest.json' for p in sorted(sources.iterdir()) if p.is_dir() and not p.is_symlink()]]
            if len(manifests)>MAX_CASES:fail('RESEARCH_MANIFEST_BUDGET',folder.name,'Too many declared source groups')
            for manifest in manifests:
                if manifest.is_file():
                    raw=read(manifest)
                    case['sourceEvidence'].append(dict(path=manifest.relative_to(folder).as_posix(),kind='source_manifest',
                                                       sha256=sha(raw),bytes=len(raw),parsedBody=False))
        for parent in ['Analysis','Evidence']:
            base=folder/parent
            if base.is_dir() and not base.is_symlink():
                children=list(base.iterdir())
                if len(children)>1000:fail('RESEARCH_ENTRY_BUDGET',folder.name,'Too many direct analysis entries')
                for p in sorted(children):
                    if p.is_dir() and not p.is_symlink() and p.name.startswith(('extraction-','source-work-','static-','source')):
                        case['sourceEvidence'].append(dict(path=p.relative_to(folder).as_posix(),kind='declared_analysis_directory',parsedBody=False))
        if case['engineHint']['family']=='cocos':case['targets']=['unity6','cocos38']
        body_evidence=[x for x in case['sourceEvidence'] if x['kind']!='identity_metadata']
        case['availability']='inspectable_evidence' if body_evidence else 'declared_reference_only' if case.get('declaredSourceReference') else 'blocked_source'
        if case['engineHint']['family']=='unknown':case['diagnostics'].append(dict(code='SOURCE_PROFILE_UNKNOWN',message='Source body must be inspected; no fallback reader'))
        cases.append(case)
    content=dict(schemaVersion=1,root=str(root),denominator=len(cases),excludedPrefix=['.','_'],cases=cases,
                 summary=dict(availability=dict(Counter(c['availability'] for c in cases)),families=dict(Counter(c['engineHint']['family'] for c in cases))),
                 conversionExecuted=False,sourceBodiesParsed=False,externalSourceReferencesFollowed=False)
    write_json(out/'cases.json',content)
    write_json(out/'discovery.json',dict(schemaVersion=1,caseManifestSha256=sha(read(out/'cases.json')),
                                        denominator=len(cases),status='discovered',conversion='not_run',summary=content['summary']))
    lines=['# Research source coverage','',f'Dynamic denominator: {len(cases)} games. Metadata hints only; conversion not run.','',
           '| Game | Family hint | Version hint | Source evidence | Export |','| --- | --- | --- | --- | --- |']
    for c in cases:
        clean=lambda s:str(s or 'unknown').replace('|','\\|').replace('\n',' ')
        lines.append('| '+' | '.join(clean(v) for v in [c['name'],c['engineHint']['family'],c['engineHint']['version'],c['availability'],'not_run'])+' |')
    (out/'coverage.md').write_text('\n'.join(lines)+'\n')
    return dict(status='discovered',denominator=len(cases),conversion='not_run',summary=content['summary'],report=str(out/'cases.json'))
