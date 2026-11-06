"""Explicit original textures and recovered shader source, with byte/identity provenance.

Shader code from a different engine remains source, never relabelled as a compiled
target shader. Texture atlases remain complete images alongside derived SpriteFrames.
"""
from pathlib import Path
import shutil,re
from ..io import read,sha,write_json,inside,encoded,load
from ..names import source_names
from ..normalize import open_texture
from ..layout import LayoutPlanner
from ..layout.standard import find_analysis,ROOTS
from ..targets import unity,cocos


def export_catalog(manifest,project,engine,namespace,cache,overrides=None):
    project=Path(project);cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    naming=LayoutPlanner(engine,source_names(manifest),overrides)
    existing={}
    for path in sorted((project/ROOTS[engine]['content']/'Textures').rglob('*.png')):
        relative=path.relative_to(project).as_posix();naming.claim(relative)
        if Path(str(path)+'.meta').is_file():existing.setdefault(sha(read(path,max_bytes=128*1024*1024)),relative)
    inputs={(i.get('bundle',manifest['bundle']),i['path']):i for i in manifest['inputs']}
    textures=[a for a in manifest['assets'] if a.get('kind') in ('cc.Texture2D','cc.ImageAsset') and a.get('native')]
    naming.reserve([(a['sourceId'],'texture','.png','',None,None) for a in textures])
    report=dict(schemaVersion=1,textures=[],shaders=[],shaderCompilation='needs_adapter',textureImport='not_run')
    def metadata(path,sid,kind):
        target=project/(path+'.meta')
        if engine=='unity':target.write_text('fileFormatVersion: 2\nguid: '+unity.guid(namespace,sid)+'\n',encoding='utf-8')
        else:
            importer,ver=('image','1.0.27') if kind=='texture' else ('json','2.0.1') if kind=='json' else ('*','1.0.0')
            write_json(target,cocos.meta(cocos.identity(namespace,sid),importer,ver,dict(type='texture',fixAlphaTransparencyArtifacts=False,hasAlpha=True) if kind=='texture' else None))
    for asset in textures:
        bundle=asset.get('bundle',manifest['bundle']);relative=asset['native'];expected=inputs.get((bundle,relative))
        raw=read(inside(Path(manifest['sourceRoots'][bundle]),relative),max_bytes=128*1024*1024)
        if expected is None or sha(raw)!=expected['sha256']:raise ValueError('Texture differs from source receipt: '+asset['sourceId'])
        target=naming.path(asset['sourceId'],'texture','.png');cached=cache/(sha(raw)+'.png')
        # This cache is create-only inside the current conversion, shared by both target passes.
        if not cached.exists():
            with open_texture(raw,Path(relative).suffix.lower()) as image:
                image.save(cached,format='PNG')
        digest=sha(cached.read_bytes());shared=existing.get(digest)
        if shared:
            allocated=target;target=shared
            record=naming.record(asset['sourceId'],'texture','.png')
            record.update(target=target,allocatedPath=allocated);record['reasons'].append('byte-identical-texture-reuse')
        else:
            dest=project/target;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(cached,dest)
            metadata(target,'original-texture/'+asset['sourceId'],'texture');existing[digest]=target
        meta_raw=read(project/(target+'.meta'))
        native_id=re.search(rb'^guid: ([0-9a-f]{32})',meta_raw,re.M).group(1).decode() if engine=='unity' else load(meta_raw)['uuid']
        report['textures'].append(dict(sourceId=asset['sourceId'],sourcePath=relative,sourceSha256=sha(raw),path=target,sha256=digest,
            targetIdentity=native_id,proposedIdentity=unity.guid(namespace,'original-texture/'+asset['sourceId']) if engine=='unity' else cocos.identity(namespace,'original-texture/'+asset['sourceId']),
            status='shared_existing_texture' if shared else 'full_texture_exported'))
    for asset in manifest['assets']:
        if asset.get('kind')!='cc.EffectAsset':continue
        objects=(asset.get('document') or {}).get('instances',[])
        effect=next((x for x in objects if isinstance(x,dict) and x.get('__type__')=='cc.EffectAsset'),None)
        row=dict(sourceId=asset['sourceId'],status='needs_adapter',files=[],nativeShader=False);report['shaders'].append(row)
        if effect is None:row['reason']='Decoded effect source not available';continue
        folder=naming.folder(asset['sourceId'],'shader')
        payloads={'EffectDescription.json':encoded(effect)}
        for index,shader in enumerate(effect.get('shaders',[])):
            for dialect in ('glsl1','glsl3','glsl4'):
                program=shader.get(dialect,{}) if isinstance(shader,dict) else {}
                if not isinstance(program,dict):continue
                for stage in ('vert','frag'):
                    text=program.get(stage)
                    if isinstance(text,str):payloads[f'program{index}_{dialect}.{stage}.glsl']=text.encode('utf-8')
        for name,raw in payloads.items():
            target=folder+'/'+name;dest=project/target;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
            metadata(target,'shader-source/'+asset['sourceId']+'/'+name,'json' if name.endswith('.json') else 'text')
            row['files'].append(dict(path=target,sha256=sha(raw),bytes=len(raw)))
        row.update(status='source_exported_needs_adapter',reason='Original compiled GLSL stages and effect settings recovered; no automatic GLSL-to-ShaderLab or Creator 2-to-3 compilation is claimed')
        if engine=='unity':
            from ..shader_profiles import export_profile
            native=export_profile(effect,project,namespace,asset['sourceId'],effect_sha256=sha(payloads['EffectDescription.json']),folder=folder)
            row['nativeProfile']=native['profile'];row['nativeValidation']='not_run'
            if native['written']:
                row.update(status='source_exported_with_exact_target_profile',nativeShader=True,
                    reason='Exact pinned source/macro profile generated; material binding, native validation and source variants remain separate gates',
                    nativeFiles=[dict(path=p,sha256=sha(read(project/p)),bytes=(project/p).stat().st_size)for p in native['files']])
    report['naming']=naming.report()
    report['deduplicatedTextures']=sum(r['status']=='shared_existing_texture' for r in report['textures'])
    report['writtenTextures']=len(report['textures'])-report['deduplicatedTextures']
    write_json(find_analysis(project,'resource-catalog.json'),report)
    return report
