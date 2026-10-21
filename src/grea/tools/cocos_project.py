"""Generate a create-only Creator 3.8.8 five-layer Signal Counter project."""
import argparse,json,uuid
from grea.host.paths import Path
from .project_templates import publish,receipt

NAMESPACE=uuid.UUID('ab876bd6-204a-4f41-b3ca-76fe8af94e28')
def identity(name):return str(uuid.uuid5(NAMESPACE,name))
def compressed(value):
    table='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
    h=value.replace('-','');return h[:2]+''.join(table[int(h[i:i+3],16)>>6]+table[int(h[i:i+3],16)&63] for i in range(2,32,3))
def meta(path,kind,identifier):
    return dict(ver={'scene':'1.1.50','prefab':'1.1.50','typescript':'4.0.24'}.get(kind,'1.0.0'),importer=kind,imported=True,uuid=identifier,files=['.json'] if kind in ('scene','prefab') else [],subMetas={},userData={})
def scene(script_uuid,name='Signal'):
    return [dict(__type__='cc.SceneAsset',_name=name,_objFlags=0,_native='',scene={'__id__':1}),dict(__type__='cc.Scene',_name=name,_objFlags=0,_parent=None,_children=[{'__id__':2}],_active=True,_components=[],_prefab=None,_id=identity(name)),dict(__type__='cc.Node',_name='Bootstrap',_parent={'__id__':1},_children=[],_active=True,_components=[{'__id__':3}],_prefab=None,_lpos=dict(__type__='cc.Vec3',x=0,y=0,z=0),_lrot=dict(__type__='cc.Quat',x=0,y=0,z=0,w=1),_lscale=dict(__type__='cc.Vec3',x=1,y=1,z=1),_layer=1073741824),dict(__type__=compressed(script_uuid),_name='',_enabled=True,node={'__id__':2},_id=identity(name+'/boot'))]
def generate(output,name='Signal Counter',width=750,height=1334,creator_version='3.8.8'):
    if creator_version!='3.8.8' or not name.strip() or not 240<=width<=8192 or not 240<=height<=8192:raise ValueError('Supported Creator=3.8.8; valid name and design dimensions required')
    root=publish('cocos',output,{'__WIDTH__':width,'__HEIGHT__':height})
    def write(path,value):
        p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for p in sorted((root/'assets').rglob('*')):
        if p.is_file():write(str(p.relative_to(root))+'.meta',meta(p,'typescript' if p.suffix=='.ts' else 'json',identity(p.relative_to(root).as_posix())))
    script=identity('assets/scripts/bootstrap/SignalBoot.ts');start=identity('assets/scenes/Signal.scene')
    write('assets/scenes/Signal.scene',scene(script));write('assets/scenes/Signal.scene.meta',meta(None,'scene',start))
    write('package.json',dict(name=name,version='0.1.0',creator=dict(version=creator_version),uuid=identity('project/'+name)))
    write('settings/v2/packages/project.json',dict(__version__='1.0.6',general=dict(designResolution=dict(width=width,height=height,fitWidth=True,fitHeight=True))))
    write('grea-cocos.json',dict(schema_version=1,creator=creator_version,design=[width,height],start_scene=start,browser_primary=True,funplay='optional_not_installed'))
    (root/'.gitignore').write_text('library/\ntemp/\nlocal/\nprofiles/\nbuild/\n')
    return receipt(root,'cocos',dict(name=name,creator=creator_version,width=width,height=height))
def audit_layers(project):
    import re
    from grea.safe_paths import canonical_path
    root=canonical_path(project)/'assets/scripts'
    allowed={'domain':{'domain'},'gameplay':{'domain','gameplay'},'presentation':{'domain','gameplay','presentation'},'services':{'domain','gameplay','services'},'bootstrap':{'domain','gameplay','presentation','services','bootstrap'}}
    paths=sorted(root.rglob('*.ts'));issues=[];graph={};total=0
    if len(paths)>1000:raise ValueError('TS file budget exceeded')
    for file in paths:
        if file.is_symlink():raise ValueError('Linked source unsupported')
        total+=file.stat().st_size
        if total>8*1024**2:raise ValueError('TS byte budget exceeded')
        text=file.read_text();layer=file.relative_to(root).parts[0];edges=[]
        if layer not in allowed:issues.append(dict(file=str(file.relative_to(root)),reason='unknown layer'));continue
        # Conservative static screening, not a complete TypeScript parser.
        imports=re.findall(r"(?:from\s*|import\s*|require\s*\(|import\s*\()(['\"])([^'\"]+)\1",text)
        if re.search(r"(?:import|require)\s*\(\s*[^'\"\s]",text):issues.append(dict(file=str(file.relative_to(root)),reason='computed import cannot be statically closed'))
        for _,name in imports:
            if name.startswith('.'):
                dest=(file.parent/name).resolve();dest=dest if dest.suffix=='.ts' else dest.with_suffix('.ts') if dest.with_suffix('.ts').exists() else dest/'index.ts'
                if not dest.is_relative_to(root) or not dest.is_file():issues.append(dict(file=str(file.relative_to(root)),reason='unclosed/escaping import',dependency=name));continue
                target=dest.relative_to(root).parts[0];edges.append(dest)
                if target not in allowed[layer]:issues.append(dict(file=str(file.relative_to(root)),reason='forbidden layer dependency',dependency=name))
            elif layer in ('domain','gameplay') or name!='cc':issues.append(dict(file=str(file.relative_to(root)),reason='external dependency requires explicit review',dependency=name))
        graph[file]=edges
    visiting=set();done=set()
    def visit(file):
        if file in visiting:raise ValueError('Cyclic TypeScript dependency')
        if file in done:return
        visiting.add(file)
        for edge in graph.get(file,[]):visit(edge)
        visiting.remove(file);done.add(file)
    for file in graph:visit(file)
    return dict(status='findings' if issues else 'static_layer_screen_pass',files=len(paths),findings=issues,limitations=['Conservative literal import/export/dynamic-import screening; not a TypeScript compiler or proof against reflection/global service locators.'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--name',default='Signal Counter');p.add_argument('--width',type=int,default=750);p.add_argument('--height',type=int,default=1334);p.add_argument('--creator-version',default='3.8.8');p.add_argument('--audit-project',type=Path);a=p.parse_args()
    try:
        if a.audit_project:
            from grea.safe_paths import disjoint
            r=audit_layers(a.audit_project);output=disjoint(a.output,a.audit_project)
            with output.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2)
            print(json.dumps(dict(status=r['status'],findings=len(r['findings']))));return 1 if r['findings'] else 0
        r=generate(a.output,a.name,a.width,a.height,a.creator_version);print(json.dumps(dict(status=r['status'],files=len(r['files']))));return 0
    except (ValueError,OSError) as e:print(str(e));return 2
if __name__=='__main__':raise SystemExit(main())
