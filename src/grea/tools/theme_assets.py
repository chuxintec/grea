"""Read-only PNG mapping validation/preview and immutable incremental bundles.

Only a separately invoked Unity Editor companion may apply or roll back assets.
No Unity serialization, source/game logic, skeleton or image generation is performed.
"""
import argparse,json,shutil,math
from jsonschema.exceptions import ValidationError
from grea.common import GreaError
from grea.host.paths import Path
from grea.safe_paths import canonical_path,relative_name,unique_paths,disjoint
from grea.common import digest
from grea.change_contracts import validate as change_contract, validate_ledger
from ._artifact_common import digest as file_sha
from ._image_alpha import inspect_image  # private copy; the image_alpha_audit tool runs in beaver

MAX_BYTES=128*1024*1024

def read_json(path):
    path=Path(path)
    if path.stat().st_size>1024*1024:raise ValueError('JSON exceeds 1 MiB')
    return json.loads(path.read_text(encoding='utf-8'),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))

def member(root,name):
    p=root/relative_name(name)
    if any(x.is_symlink() for x in (p,*p.parents)) or not p.is_file():raise ValueError('Missing or linked input: '+name)
    return p

def inspect(project,replacements,manifest):
    project=canonical_path(project);replacements=canonical_path(replacements);manifest=canonical_path(manifest)
    v=read_json(manifest)
    if set(v)!={'schema_version','change_contract','assets'} or v['schema_version']!=1:raise ValueError('Expected versioned theme mapping')
    from jsonschema import Draft202012Validator
    from grea.change_contracts import theme_documents
    Draft202012Validator(theme_documents()['theme-map.schema.json']).validate(v)
    change_contract(v['change_contract'])
    ledger=None;ledger_path=None
    production=v['change_contract'].get('art_production')
    if production:
        declaration=production['ledger']
        ledger_path=member(manifest.parent,declaration['reference'])
        if ledger_path.stat().st_size>1024*1024:raise ValueError('Art ledger exceeds 1 MiB')
        if file_sha(ledger_path)!=declaration['sha256']:raise ValueError('Stale art ledger digest')
        ledger=read_json(ledger_path);ledger_summary=validate_ledger(ledger)
        record_index={r['id']:r for r in ledger['records']}
    assets=v['assets']
    if not isinstance(assets,list) or not 1<=len(assets)<=256:raise ValueError('Select 1..256 PNG mappings')
    unique_paths([a['asset'] for a in assets])
    if len({a['guid'] for a in assets})!=len(assets):raise ValueError('Mapped targets must have unique GUIDs')
    rows=[];total=0;pixels=0
    for row in assets:
        if set(row)-{'ledger_record'}!={'usage','alpha_required','asset','replacement','source_sha256','replacement_sha256','meta_sha256','guid','sprite'}:raise ValueError('Unknown or missing mapping fields')
        if 'ledger_record' in row:
            record=record_index.get(row['ledger_record']) if ledger else None
            if not record or record['kind'] not in ('interface','icon') or record.get('spine',{}).get('state','not_required')!='not_required' or row['asset'] not in record['targets']:
                raise ValueError('PNG mapping must name an existing UI/icon ledger record with this target; Spine is not an automatic PNG replacement')
        if not row['asset'].startswith('Assets/') or not row['asset'].endswith('.png') or not row['replacement'].endswith('.png'):raise ValueError('Only existing native PNG assets supported')
        import re
        if not re.fullmatch('[0-9a-f]{32}',row['guid']):raise ValueError('Expected declared existing GUID')
        for key in ('source_sha256','replacement_sha256','meta_sha256'):
            if not re.fullmatch('[0-9a-f]{64}',row[key]):raise ValueError('Invalid digest')
        source=member(project,row['asset']);new=member(replacements,row['replacement']);meta=member(project,row['asset']+'.meta')
        total+=source.stat().st_size+new.stat().st_size+meta.stat().st_size
        if total>MAX_BYTES:raise ValueError('Mapping byte budget exceeded')
        for file,key in ((source,'source_sha256'),(new,'replacement_sha256'),(meta,'meta_sha256')):
            if file_sha(file)!=row[key]:raise ValueError('Stale '+key+': '+row['asset'])
        before,after=inspect_image(source),inspect_image(new)
        pixels+=before['width']*before['height']+after['width']*after['height']
        if pixels>64000000 or before['format']!='PNG' or after['format']!='PNG':raise ValueError('PNG/pixel budget exceeded')
        spec=row['sprite']
        if set(spec)!={'width','height','pivot','border','pixels_per_unit','file_id','mode'} or spec['mode']!='single':raise ValueError('Only observed single-Sprite contracts supported')
        if (spec['width'],spec['height'])!=(before['width'],before['height']) or (after['width'],after['height'])!=(before['width'],before['height']):raise ValueError('Canvas change requires a separate Editor migration')
        pivot,border=spec['pivot'],spec['border']
        if not isinstance(pivot,list) or len(pivot)!=2 or not all(type(x) in (int,float) and math.isfinite(x) and 0<=x<=1 for x in pivot):raise ValueError('Invalid pivot')
        if not isinstance(border,list) or len(border)!=4 or not all(type(x) in (int,float) and math.isfinite(x) and x>=0 for x in border) or border[0]+border[2]>before['width'] or border[1]+border[3]>before['height']:raise ValueError('Invalid nine-slice border')
        if type(spec['file_id']) is not int or type(spec['pixels_per_unit']) not in (int,float) or not math.isfinite(spec['pixels_per_unit']) or not spec['pixels_per_unit']>0:raise ValueError('Invalid Sprite identity/PPU')
        if after['visible_bbox'] is None:raise ValueError('Fully transparent replacement')
        if row['alpha_required'] and not after['transparent_pixels']:raise ValueError('Cutout requires transparent pixels')
        rows.append(dict(row,changed=row['source_sha256']!=row['replacement_sha256'],before=before,after=after))
    result=dict(schema_version=1,tool='theme_assets',implementation_version='0.1.0',status='validated_declared_mapping',change_contract=v['change_contract'],assets=rows,
                limits=['Approval/invariants/baseline are caller declarations; selected images/meta and an optional bound ledger are read; referenced media are not opened.','GUID/fileID/importer fields are declarations until Editor readback.','No pixel approval, input/gameplay or skeleton/event validation.'])
    result['plan_id']=digest({'manifest':v,'assets':[{k:x[k] for k in ('asset','source_sha256','replacement_sha256','meta_sha256')} for x in rows]})
    if ledger:
        result['art_ledger']=ledger_summary
        if file_sha(ledger_path)!=production['ledger']['sha256']:raise ValueError('Art ledger changed during inspection')
    # Cooperative local writers only; recheck all explicit input identities before returning.
    for row in rows:
        for file,key in ((member(project,row['asset']),'source_sha256'),(member(replacements,row['replacement']),'replacement_sha256'),(member(project,row['asset']+'.meta'),'meta_sha256')):
            if file_sha(file)!=row[key]:raise ValueError('Input changed during mapping inspection')
    return result

def create(project,replacements,manifest,out,preview=False):
    report=inspect(project,replacements,manifest);out=disjoint(out,project,replacements,manifest)
    if out.exists() or not out.parent.is_dir():raise ValueError('Use a new output under an existing parent')
    out.mkdir()
    if preview:
        from PIL import Image,ImageDraw
        count=len(report['assets']);canvas=Image.new('RGB',(512,160*count),'#aaaaaa');draw=ImageDraw.Draw(canvas)
        for i,row in enumerate(report['assets']):
            draw.text((4,160*i),row['asset'],fill='black')
            for column,file in enumerate((member(canonical_path(project),row['asset']),member(canonical_path(replacements),row['replacement']))):
                with Image.open(file) as source:
                    thumb=source.convert('RGBA');thumb.thumbnail((240,128));canvas.paste(thumb,(8+column*256,22+160*i),thumb)
        canvas.save(out/'preview.png');report['preview_sha256']=file_sha(out/'preview.png')
    else:
        bundle=[]
        for i,row in enumerate(report['assets']):
            if not row['changed']:continue
            before=f'before/{i}.png';after=f'after/{i}.png'
            for name,source in ((before,member(canonical_path(project),row['asset'])),(after,member(canonical_path(replacements),row['replacement']))):
                target=out/name;target.parent.mkdir(exist_ok=True);shutil.copyfile(source,target)
                expected=row['source_sha256' if name==before else 'replacement_sha256']
                if file_sha(target)!=expected:raise ValueError('Copy changed; partial output retained')
            bundle.append({**{k:row[k] for k in ('usage','alpha_required','asset','source_sha256','replacement_sha256','meta_sha256','guid','sprite','ledger_record') if k in row},'before':before,'after':after})
        report['bundle']=bundle
        report['status']='incremental_bundle_prepared_not_applied'
    if inspect(project,replacements,manifest)['plan_id']!=report['plan_id']:raise ValueError('Input changed while producing output; partial output retained')
    (out/'theme-plan.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['validate','preview','prepare','validate-ledger'])
    for name in ('project','replacements','manifest','output'):parser.add_argument('--'+name,type=Path,required=name in ('manifest','output'))
    a=parser.parse_args()
    try:
        if a.action=='validate-ledger':
            manifest=canonical_path(a.manifest);result=validate_ledger(read_json(manifest))
            out=disjoint(a.output,manifest)
            with out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
        elif a.project is None or a.replacements is None:
            raise ValueError('PNG actions require --project and --replacements')
        elif a.action=='validate':
            result=inspect(a.project,a.replacements,a.manifest);out=disjoint(a.output,a.project,a.replacements,a.manifest)
            with out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
        else:result=create(a.project,a.replacements,a.manifest,a.output,a.action=='preview')
        print(json.dumps({'status':result['status'],**({'plan_id':result['plan_id']} if 'plan_id' in result else {})}));return 0
    except (OSError,ValueError,KeyError,TypeError,GreaError,ValidationError) as error:
        print(str(error));return 2

if __name__=='__main__':raise SystemExit(main())
