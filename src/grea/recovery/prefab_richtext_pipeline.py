"""Source-pinned static RichText enrichment and explicit font-backed planning."""
from pathlib import Path
from copy import deepcopy
from typing import Sequence
from . import io
from .output_limits import copy_verified
from .sources.compiled import fail
from .prefab_static_richtext import convert_static_richtext

def enrich(ir):
    rows=[c for c in ir['components']if c['type']=='cc.RichText']
    if not rows:return
    path=ir.get('sourceManifestPath')
    if not path:fail('RICHTEXT_SOURCE_MISSING','manifest','Frozen source manifest required')
    raw=io.stage_bytes(Path(path))
    if io.sha(raw)!=ir['sourceManifestSha256']:fail('RICHTEXT_SOURCE_CHANGED',path,'Source hash differs')
    assets={a['sourceId']:a for a in io.load(raw,max_nodes=8_000_000)['assets']}
    for c in rows:
        asset,suffix=c['sourceId'].split('#',1);parts=suffix.split('/')
        obj=assets[asset]['document']['instances'][int(parts[0])]
        for i in range(1,len(parts),2):
            key='_components'if parts[i]=='components'else parts[i]
            obj=obj[key][int(parts[i+1])]
            if isinstance(obj,dict)and '__id__'in obj:obj=assets[asset]['document']['instances'][obj['__id__']]
        if obj.get('__type__')!='cc.RichText':fail('RICHTEXT_SOURCE_TYPE',c['sourceId'],'Source type differs')
        c['sourceRichText']=deepcopy(obj)
        spec=convert_static_richtext(obj,source_id=c['sourceId'],node_id=c['node'])
        for key in ('text','fontSize','lineHeight','maxWidth','horizontalAlign','verticalAlign','wrap'):
            c[key]=obj.get('_N$string','')if key=='text'else spec[key]

def _selected_richtext_components(plan, source_ids):
    rows=[c for c in plan.get('components',[]) if c.get('type')=='cc.RichText']
    if source_ids is None:return rows
    if not isinstance(source_ids,(list,tuple)) or any(not isinstance(x,str) or not x for x in source_ids):
        raise ValueError('source_ids must be a list of nonempty RichText source IDs')
    if len(set(source_ids))!=len(source_ids):raise ValueError('source_ids must not contain duplicates')
    by_id={c.get('sourceId'):c for c in rows}
    absent=[x for x in source_ids if x not in by_id]
    if absent:raise ValueError('source_ids include non-RichText or absent components: '+','.join(absent))
    return [by_id[x] for x in source_ids]

def bind(plan_path, receipt_path, expected_receipt, output, *, source_ids: Sequence[str] | None = None):
    plan_path,receipt_path=io.safe(plan_path),io.safe(receipt_path)
    plan=io.stage_document(plan_path);receipt_raw=io.read(receipt_path)
    if io.sha(receipt_raw)!=expected_receipt:fail('RICHTEXT_FONT_RECEIPT_CHANGED','receipt','Hash differs')
    receipt=io.load(receipt_raw);metrics_path=io.safe(receipt['metricsPath']);metrics_raw=io.read(metrics_path)
    if io.sha(metrics_raw)!=receipt['metricsSha256']:fail('RICHTEXT_METRICS_CHANGED','metrics','Hash differs')
    metrics=io.load(metrics_raw);covered=[g['unicode']for g in metrics['glyphs']]
    coverage=dict(metricsPath=str(metrics_path),metricsSha256=io.sha(metrics_raw),receiptPath=str(receipt_path),receiptSha256=expected_receipt)
    unity=plan['targetProfile'].startswith('unity');primary=None;fallback=None
    try: selected=_selected_richtext_components(plan,source_ids)
    except ValueError as exc: fail('RICHTEXT_SOURCE_SELECTION_INVALID','sourceIds',str(exc))
    if unity:
        fs=plan['systemFontBinding']['systemFonts']['fonts']
        fallback=next(f for f in fs if f['populationMode']=='StaticSDFRequired')
        primary=next(f for f in fs if f['role']=='primary'and fallback['assetId']in f.get('fallbackAssetIds',[]))
        if not set(covered)<=set(fallback['requiredUnicode']):fail('RICHTEXT_FONT_NOT_STAGED','font','Glyph supplement must precede binding')
    for c in selected:
        source=c.get('sourceRichText')
        if not source:fail('RICHTEXT_SOURCE_NOT_ENRICHED',c['sourceId'],'Replan from the frozen IR')
        binding=dict(nativeFontAssetId=primary['assetId']if unity else 'system:'+metrics['postScriptName'],nativeFallbackAssetIds=[fallback['assetId']]if unity else [],coveredUnicode=covered,coverageEvidence=coverage,targetSystemFontFamily=metrics['family'])
        spec=convert_static_richtext(source,source_id=c['sourceId'],node_id=c['node'],font_binding=binding)
        c['staticRichText']=spec;c['convertible']=spec['renderReady'];c['supported']=spec['renderReady']
        if unity:c['font']=primary['assetId']
        else:c.update(nativeType='cc.RichText',nativeSystemFont=True,fontFamily=metrics['family'])
        if not c['convertible']:fail('RICHTEXT_CONTENT_UNSUPPORTED',c['sourceId'],str(spec['gaps']))
    out=io.new_output(output,[plan_path.parent,receipt_path.parent])
    for f in io.stage_manifest(plan_path.parent)['files']:
        if f['path']!='plan.json':copy_verified(io.inside(plan_path.parent,f['path']),io.inside(out,f['path']),f['sha256'],f['bytes'])
    plan['staticRichTextCoverage']=dict(coverage,sourceIds=[c['sourceId'] for c in selected],selectionMode='explicit' if source_ids is not None else 'all')
    io.write_json(out/'plan.json',plan);return io.finish(out,plan)
