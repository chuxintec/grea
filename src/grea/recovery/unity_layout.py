"""Unity-source relocation into monkey-project/2.0.0 (PROJECT-SPEC 4.2, 4.6, 10). Files move with their .meta, so GUIDs never change.

The provider export arrives as AssetRipper type roots plus source container folders. Each file is classified by its real
Unity type, then placed through the LayoutPlanner. Exceptions that keep runtime identity: Resources keys keep their exact
relative path under Content/<Type>/Resources/, Spine closures keep their file names, game script assemblies keep their
names under Scripts/, and Plugins/TextMesh Pro stay where Unity expects them. Unreferenced raw .bytes tables leave Assets.
"""
import re
import shutil
from pathlib import Path,PurePosixPath
from .io import read,load,write_json
from .layout import LayoutPlanner,casing,standard

TYPE_ROOTS={'texture2d','sprite','material','monobehaviour','textasset','animationclip','animatorcontroller','animatoroverridecontroller','shader',
    'font','mesh','audioclip','physicmaterial','physicsmaterial2d','cubemap','rendertexture','spriteatlas','videoclip','avatar','prefabinstance',
    'gameobject','lightingdatasset','lightingsettings','terraindata','audiomixercontroller','shadervariantcollection','computeshader','flare'}
KEEP_ROOTS=('Assets/Plugins/','Assets/textmesh pro/','Assets/TextMesh Pro/','Assets/Game/')
YAML_SUFFIXES={'.prefab','.unity','.asset','.mat','.controller','.overridecontroller','.anim','.spriteatlas','.mixer','.lighting','.physicsmaterial2d','.shadervariants','.playable'}
CLASS_KINDS={'213':'sprite','43':'model','48':'shader','49':'data','687078895':'atlas','74':'animation','91':'controller','221':'controller','134':'data','62':'data'}
# Package runtime files found by Resources name (TextMesh Pro); never treated as game tables.
PACKAGE_RESOURCES={'tmp settings','linebreaking leading characters','linebreaking following characters'}
SPINE_TAILS=('_SkeletonData.asset','_Atlas.asset','.skel.bytes','.skel','.json','.atlas.txt','.atlas.bytes','.atlas','_Material.mat','_Controller.controller')
_GUID=re.compile(rb'guid: ([0-9a-f]{32})')


def _class(path):
    with open(path,'rb') as stream:head=stream.read(512)
    found=re.search(rb'--- !u!(\d+) &',head)
    return found.group(1).decode() if found else None


def _meta_guid(path):
    meta=Path(str(path)+'.meta')
    if not meta.is_file():return None
    found=re.search(r'^guid: ([0-9a-f]{32})',meta.read_text(encoding='utf-8-sig',errors='replace'),re.M)
    return found.group(1) if found else None


def _texture_type(path):
    meta=Path(str(path)+'.meta')
    found=re.search(r'^\s*textureType: (\d+)',meta.read_text(encoding='utf-8-sig',errors='replace'),re.M) if meta.is_file() else None
    return int(found.group(1)) if found else None


def referenced_guids(assets):
    """Every GUID named by a serialized YAML asset; such files are dependencies and must stay importable."""
    found=set()
    for path in assets.rglob('*'):
        if path.is_file() and path.suffix.lower() in YAML_SUFFIXES:
            raw=read(path,max_bytes=1024*1024*1024)
            if raw.startswith(b'%YAML'):found.update(m.decode() for m in _GUID.findall(raw))
    return found


def kind_of(path,relative):
    suffix=path.suffix.lower();name=path.name
    if suffix=='.unity':return 'scene'
    if suffix=='.prefab':
        raw=read(path,max_bytes=1024*1024*1024)
        return 'effect' if b'--- !u!198 ' in raw or b'ParticleSystem:' in raw else 'prefab'
    if suffix in ('.png','.jpg','.jpeg','.tga','.psd','.exr','.bmp'):return 'sprite' if _texture_type(path)==8 else 'texture'
    if suffix=='.mat':return 'material'
    if suffix in ('.shader','.cginc','.hlsl','.shadergraph','.compute'):return 'shader'
    if suffix=='.anim':return 'animation'
    if suffix in ('.controller','.overridecontroller'):return 'controller'
    if suffix in ('.ttf','.otf','.fontsettings'):return 'font'
    if suffix in ('.mp3','.ogg','.wav','.aif','.aiff'):return 'native'
    if suffix in ('.mp4','.webm','.mov'):return 'video'
    if suffix in ('.fbx','.obj','.dae'):return 'model'
    if suffix=='.spriteatlas' or suffix=='.spriteatlasv2':return 'atlas'
    if suffix=='.asset':
        cls=_class(path)
        if cls=='114':
            return 'font-asset' if ' SDF' in name or name.endswith('_SDF.asset') or 'SDF' in name.split('_') else 'data'
        return CLASS_KINDS.get(cls,'data')
    return 'data'


def _spine_groups(files):
    """Stem -> member paths for closures rooted at an X_SkeletonData.asset (same folder or AssetRipper type roots)."""
    by_dir={};groups={}
    for relative in files:
        parent,_,name=relative.rpartition('/');by_dir.setdefault(parent,[]).append(name)
    roots=[r for r in files if r.endswith('_SkeletonData.asset')]
    for root in roots:
        parent,_,name=root.rpartition('/');stem=name[:-len('_SkeletonData.asset')]
        folders={parent}|{d for d in by_dir if d.count('/')==1 and d.split('/')[1].lower() in TYPE_ROOTS}
        members=[]
        for folder in sorted(folders):
            for other in by_dir.get(folder,[]):
                tail=other[len(stem):] if other.startswith(stem) else None
                if tail is None:continue
                if tail in SPINE_TAILS or re.fullmatch(r'(_?\d*)\.png',tail):members.append(folder+'/'+other)
        groups[root]=dict(stem=stem,members=sorted(set(members)))
    return groups


def _meta(relative):
    """Planner metadata for a provider export path: container folders are semantic, AssetRipper type roots are not."""
    parts=relative.split('/')[1:]
    if len(parts)>1 and parts[0].lower() in TYPE_ROOTS:
        return dict(bundle='',logicalPath=standard.ROOTS['unity']['unsorted']+'/'+parts[-1],nameProvenance='source-name')
    return dict(bundle='',logicalPath='/'.join(parts))


def plan(project,overrides=None):
    """Moves for the provider export. Pure: reads files, writes nothing."""
    project=Path(project);assets=project/'Assets'
    files=sorted(p.relative_to(project).as_posix() for p in assets.rglob('*') if p.is_file() and p.suffix!='.meta')
    referenced=referenced_guids(assets);planner=LayoutPlanner('unity',overrides=overrides or {})
    moves=[];claimed=set();content=standard.ROOTS['unity']['content']
    for relative in files:
        if relative.startswith(KEEP_ROOTS):planner.claim(relative)
    def move(old,new,kind,reason):
        if old!=new:moves.append(dict(source=old,target=new,guid=_meta_guid(project/old),kind=kind,reason=reason))
        claimed.add(old);planner.claim(new)
    for root,group in _spine_groups(files).items():
        meta=_meta(root);meta['logicalPath']=meta['logicalPath'].rsplit('/',1)[0]+'/'+group['stem']
        folder=planner.folder(root,'spine',metadata=meta)
        for member in group['members']:
            if member not in claimed and not member.startswith(KEEP_ROOTS):move(member,folder+'/'+member.rsplit('/',1)[1],'spine','spine-closure-names-kept')
    requests=[]
    for relative in files:
        if relative in claimed or relative.startswith(KEEP_ROOTS):continue
        path=project/relative;parts=relative.split('/')
        if parts[1]=='Scenes':
            move(relative,standard.ROOTS['unity']['scenes']+'/'+'/'.join(parts[2:]),'scene','scene-and-owned-settings');continue
        if len(parts)>2 and parts[1]=='Scripts':
            move(relative,standard.ROOTS['unity']['scripts']+'/'+'/'.join(parts[2:]),'script','assembly-type-identity-kept');continue
        if parts[1]=='Editor':
            move(relative,standard.RECOVERY['source']+'/Provider/'+'/'.join(parts[1:]),'evidence','provider-editor-code');continue
        kind=kind_of(path,relative);guid=_meta_guid(path)
        if path.suffix.lower()=='.bytes' and guid not in referenced and path.stem.lower() not in PACKAGE_RESOURCES:
            section=standard.RECOVERY['source']+'/Provider' if path.stem.lower().endswith('.dll') else standard.RECOVERY['config']
            move(relative,section+'/'+casing.safe_path('/'.join(parts[1:])),'evidence','unreferenced-raw-table');continue
        lowered=[p.lower() for p in parts]
        if 'resources' in lowered[1:-1]:
            # Resources.Load keys survive: exact relative key below a typed Resources folder (GREA STR rule).
            at=lowered.index('resources',1);key='/'.join(parts[at+1:])
            typ=planner.types.get({'native':'sfx','font-asset':'font','controller':'animation','scene':'data'}.get(kind,kind)) or planner.types['data']
            move(relative,content+'/'+typ+'/Resources/'+key,kind,'resources-key-kept');continue
        requests.append((relative,kind,path.suffix,'',_meta(relative),None))
    planner.reserve(requests)
    for relative,kind,suffix,variant,metadata,_ in requests:
        move(relative,planner.path(relative,kind,suffix,metadata=metadata),kind,'typed-content')
    return dict(schemaVersion=1,layout=standard.VERSION,moves=moves,names=planner.report(),referencedGuids=len(referenced))


def apply(project,planned):
    """Execute moves with their .meta files; remove emptied provider folders and their folder metas."""
    project=Path(project);targets={}
    for row in planned['moves']:
        key=row['target'].casefold()
        if key in targets or (project/row['target']).exists():raise ValueError('Relocation target collision: '+row['target'])
        targets[key]=row['source']
    for row in planned['moves']:
        source=project/row['source'];dest=project/row['target'];dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.move(source,dest)
        meta=Path(str(source)+'.meta')
        if meta.exists():shutil.move(meta,Path(str(dest)+'.meta'))
    for folder in sorted((p for p in (project/'Assets').rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir();meta=Path(str(folder)+'.meta')
            if meta.exists():meta.unlink()
    update_receipts(project,planned['moves'])
    return len(planned['moves'])


def update_receipts(project,moves):
    """Keep executable field-code locations usable while retaining their provider provenance."""
    receipt=standard.find_analysis(project,'unity-code-quarantine.json')
    if not receipt.is_file():return 0
    body=load(read(receipt));mapping={r['source']:r['target'] for r in moves};changed=0
    for row in body.get('schemaApplied',[]):
        previous=row['path'];target=mapping.get(previous,previous)
        if previous!=target:
            row.setdefault('providerPath',previous);row['path']=target;changed+=1
    if changed:write_json(receipt,body)
    return changed


def relocate(project,overrides=None):
    planned=plan(project,overrides);moved=apply(project,planned)
    write_json(Path(project)/standard.analysis('unity-relocation.json'),dict(planned,moved=moved))
    return dict(moved=moved,layout=standard.VERSION,report='Analysis/Mappings/unity-relocation.json')
