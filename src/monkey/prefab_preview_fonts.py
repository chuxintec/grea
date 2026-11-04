"""Bind an explicitly generated glyph supplement to a fixed preview state."""
from . import io
from .output_limits import copy_verified
from .prefab_system_fonts import prepare_static_inputs
from .sources.compiled import fail


def augment(plan_path, receipt_path, expected_receipt, output):
    plan_path,receipt_path=io.safe(plan_path),io.safe(receipt_path)
    plan=io.stage_document(plan_path);raw=io.read(receipt_path)
    if io.sha(raw)!=expected_receipt:fail('PREVIEW_FONT_RECEIPT_CHANGED',str(receipt_path),'Receipt hash differs')
    receipt=io.load(raw);state=plan.get('previewState')
    if not state or receipt.get('previewStateSha256')!=state['stateSha256']:
        fail('PREVIEW_FONT_STATE_MISMATCH','previewState','Glyph receipt belongs to another state')
    prior=plan.get('staticFontInputs')or{}
    if receipt.get('derivedFromOriginalGenerationReceiptSha256')!=prior.get('sourceGenerationReceiptSha256'):
        fail('PREVIEW_FONT_PARENT_MISMATCH','receipt','Original glyph receipt differs')
    metrics_path=io.safe(receipt['metricsPath']);metrics_raw=io.read(metrics_path)
    if io.sha(metrics_raw)!=receipt.get('metricsSha256'):fail('PREVIEW_FONT_METRICS_CHANGED','metrics','Metrics hash differs')
    metrics=io.load(metrics_raw)
    fonts=[f for f in plan['systemFontBinding']['systemFonts']['fonts']if f['populationMode']=='StaticSDFRequired']
    if len(fonts)!=1:fail('PREVIEW_FONT_FACE_AMBIGUOUS','fonts','Explicit one-face supplement required')
    font=fonts[0];before=set(font['requiredUnicode']);after={g['unicode']for g in metrics['glyphs']}
    states=plan.get('previewStates')or[state]
    requested={ord(c)for st in states for op in st['operations']if op['kind']=='label.text'for c in op['stringValue']}
    requested.update(ord(c)for st in states for batch in st.get('cloneBatches',[])for row in batch['instances']for op in row['previewState']['operations']if op['kind']=='label.text'for c in op['stringValue'])
    requested.update(ord(c)for component in plan['components']if component['type']=='cc.RichText'for c in component.get('text',''))
    if not before<=after or not (after-before)<=requested or not after-before:
        fail('PREVIEW_FONT_GLYPH_SCOPE','glyphs','Supplement must preserve original glyphs and only add preview text glyphs')
    font['requiredUnicode']=sorted(after);font['requiredGlyphs']=[dict(unicode=n,codepoint=f'U+{n:04X}',character=chr(n))for n in sorted(after)]
    out=io.new_output(output,[plan_path.parent,receipt_path.parent]);skip={f['relativePath']for f in prior.get('copies',[])}|{'plan.json'}
    for f in io.stage_manifest(plan_path.parent)['files']:
        if f['path']in skip:continue
        copy_verified(io.inside(plan_path.parent,f['path']),io.inside(out,f['path']),f['sha256'],f['bytes'])
    staged=prepare_static_inputs(receipt_path,expected_receipt,plan['systemFontBinding'],out)
    if staged.status!='staged':fail('PREVIEW_FONT_STAGING','fonts',str(staged.record))
    plan['staticFontInputs']=staged.record
    plan['previewGlyphAugmentation']=dict(stateSha256=state['stateSha256'],sourceReceiptSha256=expected_receipt,originalGlyphCount=len(before),glyphCount=len(after),addedUnicode=sorted(after-before),sourceLabelIdsUnchanged=True)
    io.write_json(out/'plan.json',plan);return io.finish(out,plan)
