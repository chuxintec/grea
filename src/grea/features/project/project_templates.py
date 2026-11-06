"""Create-only template publication shared by finite project generators."""
import hashlib,json,re,shutil,uuid
from grea.host.paths import Path
from grea.common import package_root
from grea.safe_paths import canonical_path

def publish(template,output,replacements=None):
    output=canonical_path(output)
    if output.exists() or not output.parent.is_dir():raise ValueError('Output must be new with an existing parent')
    base=package_root()/'tools'/template/'template'
    files={}
    for p in base.rglob('*'):
        if p.is_symlink():raise ValueError('Linked template')
        if p.is_file():files[p.relative_to(base).as_posix()]=p.read_bytes()
    if not files:raise ValueError('Template missing from product')
    output.mkdir()
    for name,raw in sorted(files.items()):
        if replacements:
            text=raw.decode('utf-8')
            for k,v in replacements.items():text=text.replace(k,str(v))
            raw=text.encode('utf-8')
        p=output/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    return output

def receipt(root,kind,options):
    files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    result=dict(schema_version=1,template=kind,template_version='0.1.0',status='generated_not_runtime_verified',options=options,files=files)
    (root/'grea-generated.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return result
