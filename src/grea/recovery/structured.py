"""Bridge whole-input snapshots to the existing source reader and shared IR."""
from pathlib import Path
from collections import Counter
from .io import read,load,write_json,sha,stage_document,stage_bytes,stage_manifest,finish
from .sources import bundle,project
from .normalize import normalize,quarantine_graphs
from .targets import unity,cocos


def validated_ir(stage):
    import os,shutil
    original=stage/'normalize';ir=stage_document(original/'ir.json')
    if not quarantine_graphs(ir):return original,ir
    derived=stage/'validated-ir'
    if derived.exists():
        existing=stage_document(derived/'ir.json')
        if existing.get('parentIrSha256')!=sha(stage_bytes(original/'ir.json')):raise ValueError('Validated IR parent changed')
        return derived,existing
    derived.mkdir();ir['parentIrSha256']=sha(stage_bytes(original/'ir.json'))
    for f in stage_manifest(original)['files']:
        if f['path']=='ir.json':continue
        from .sources.containers import fingerprint
        if fingerprint(original/f['path'])!=f['sha256']:raise ValueError('Normalized resource changed: '+f['path'])
        dest=derived/f['path'];dest.parent.mkdir(parents=True,exist_ok=True)
        try:os.link(original/f['path'],dest)
        except OSError:shutil.copyfile(original/f['path'],dest)
    write_json(derived/'ir.json',ir);finish(derived,ir)
    return derived,ir


def recover(tree, roots, configs, source_profile, out, profiles, namespace, code_emission=None, layout=None, system_fonts=False):
    from . import __version__
    stage=out/'Structured';stage.mkdir(exist_ok=True)
    result=dict(schemaVersion=1,status='pending',sourceProfile=source_profile,stages=[],projects={})
    if not source_profile:
        result.update(status='needs_action',reason='SOURCE_PROFILE_REQUIRED')
        write_json(stage/'recovery.json',result);return result
    try:
        from .signatures import phase_signatures
        from .stage_contracts import compatible
        signatures=phase_signatures();signature_path=stage/'stage-signatures.json'
        previous_signatures=load(read(signature_path)) if signature_path.exists() else {}
        def check_signature(name):
            if not compatible(previous_signatures,signatures,name):
                from .sources.compiled import fail
                fail('STAGE_ALGORITHM_CHANGED',name,'Checkpoint algorithm signature differs or is absent; use a fresh output, keep existing candidates')
        if not previous_signatures:
            if any(stage.glob('*/manifest.json')):
                from .sources.compiled import fail
                fail('STAGE_ALGORITHM_UNKNOWN',str(stage),'Existing checkpoints predate algorithm signatures; create a fresh output')
            write_json(signature_path,signatures)
        result['stageSignatures']={k:v['sha256'] for k,v in signatures.items()}
        existing=stage/'inspect/source-manifest.json'
        if (stage/'inspect/manifest.json').exists():
            check_signature('inspect')
            inspected=stage_document(existing)
            if inspected.get('sourceProfile')!=source_profile:
                raise ValueError('Source stage tool/profile mismatch')
            for name,root in inspected['sourceRoots'].items():
                if not Path(root).is_relative_to(tree):raise ValueError('Source stage escaped the immutable input snapshot')
            result.setdefault('reused',[]).append(dict(stage='inspect',sha256=sha(stage_bytes(existing))))
        elif source_profile=='cocos-2.1.2-resource':
            from .sources.cocos_legacy import inspect as inspect_legacy
            inspected=inspect_legacy(tree,stage/'inspect')
        elif source_profile==project.PROFILE:
            root=tree/roots[0]['id'];parsed=project.Project(root)
            inspected=project.inspect(root,list(range(len(parsed.keys))),stage/'inspect',max_assets=50000,whole_input=True)
        else:
            # Whole-input inventories can include byte-equivalent cached bundle indexes.
            # Retain every original in the ledger, but inspect one proven-equivalent index.
            from .io import encoded
            grouped={}
            for config in configs:
                grouped.setdefault(config['data']['name'],[]).append(config)
            paths=[];result['bundleIndexAliases']=[]
            for name,choices in sorted(grouped.items()):
                if len({sha(encoded(c['data'])) for c in choices})!=1:
                    from .sources.compiled import fail
                    fail('BUNDLE_IDENTITY_CONFLICT',name,'Different bundle indexes cannot be merged')
                def supplied_payloads(c):
                    parent=(tree/c['path']).parent
                    return sum(1 for folder in ('import','native') for p in (parent/folder).rglob('*') if p.is_file())
                selected=sorted(choices,key=lambda c:(-supplied_payloads(c),c['path']))[0]
                paths.append(tree/selected['path'])
                for alternate in choices:
                    if alternate is not selected:
                        result['bundleIndexAliases'].append(dict(bundle=name,path=alternate['path'],selected=selected['path'],
                            configSha256=sha(encoded(selected['data'])),reason='equivalent index; prefer supplied import/native payload tree'))
            if not paths:
                result.update(status='needs_action',reason='BUNDLE_CONFIG_NOT_PROVIDED');write_json(stage/'recovery.json',result);return result
            primary=bundle.Bundle(paths[0],source_profile)
            supplied=dict(source_tree=tree,provided_roots=[tree/r['id']for r in roots])if source_profile=='cocos-3.4.1-bundle'else{}
            inspected=bundle.inspect(paths[0],list(range(len(primary.keys))),stage/'inspect',paths[1:],
                    include_all_bundles=True,max_assets=50000,max_bytes=1024*1024*1024,resolve_provided=True,source_profile=source_profile,**supplied)
        result['stages'].append(dict(stage='inspect',status=stage_manifest(stage/'inspect')['status'],assets=len(inspected['assets'])))
        if (stage/'normalize/manifest.json').exists():
            check_signature('normalize')
            ir=stage_document(stage/'normalize/ir.json')
            if ir['sourceManifestSha256']!=sha(stage_bytes(existing)):
                raise ValueError('Normalized stage source/tool changed')
            result.setdefault('reused',[]).append(dict(stage='normalize',sha256=sha(stage_bytes(stage/'normalize/ir.json'))))
        else:ir=normalize(stage/'inspect/source-manifest.json',stage/'normalize')
        ir_path,ir=validated_ir(stage)
        if code_emission:
            from .package_code import project_ir
            ir_path,ir=project_ir(ir_path,inspected,code_emission,stage/'code-ir')
        result['stages'].append(dict(stage='normalize',status=stage_manifest(ir_path)['status'],nodes=len(ir['nodes']),components=len(ir['components'])))
        if 'missingDeclaredAssets'in inspected:result['declaredAssetsNotProvided']=len(inspected['missingDeclaredAssets']);result['declaredAssets']=inspected.get('declaredAssets')
        result['objectTypes']=dict(Counter(a.get('kind') or 'unknown' for a in inspected['assets']))
        result['normalized']=dict(spriteFrames=len(ir['spriteFrames']),fonts=sum(a['kind']=='cc.TTFFont' for a in ir['assets']),
                                  jsonAssets=sum(a['kind']=='cc.JsonAsset' for a in ir['assets']),nodes=len(ir['nodes']),components=len(ir['components']))
        result['resolutionReasons']=dict(Counter(d.get('resolutionReason') or
            ('unsupported_format' if any(s in d['code'] for s in ('UNSUPPORTED','INVALID','PACK_')) else
             'provided_file_resolver_unmatched' if 'AMBIGUOUS_FILE' in d['code'] else
             'input_not_provided' if 'MISSING' in d['code'] or 'UNRESOLVED' in d['code'] else 'semantic_gap')
            for d in inspected['diagnostics']))
        for profile in profiles:
            adapter=unity if profile==unity.PROFILE else cocos;key='UnityProject' if profile==unity.PROFILE else 'CocosProject'
            plan_path=stage/(key+'-plan')/'plan.json'
            if (plan_path.parent/'manifest.json').exists():
                check_signature(key+'-plan')
                plan=stage_document(plan_path)
                from .layout import VERSION
                if plan.get('sourceIrSha256')!=sha(stage_bytes(ir_path/'ir.json')) or plan.get('namespace')!=namespace:
                    raise ValueError('Target plan input/namespace changed; retained without overwrite')
                if plan.get('projectLayout')!=VERSION or plan.get('layoutOverridesSha256')!=(layout or ({},None))[1]:
                    raise ValueError('Target plan layout or layout.json changed; retained without overwrite')
                result.setdefault('reused',[]).append(dict(stage=key+'-plan',sha256=sha(stage_bytes(plan_path))))
            else:
                font_inputs = {}
                if system_fonts:
                    from .source_system_font_preparation import conversion_plan_inputs
                    font_inputs = conversion_plan_inputs(ir_path/'ir.json', stage/'inspect/source-manifest.json', stage/'SystemFonts')
                plan=adapter.plan(ir_path/'ir.json',namespace,plan_path.parent,layout=layout,**font_inputs)
            temporary=stage/'Emitted'/key
            if temporary.exists():
                import uuid
                temporary=stage/'Emitted'/(key+'-'+str(uuid.uuid4()))
            manifest=adapter.export(stage/(key+'-plan')/'plan.json',temporary)
            if code_emission:
                from .package_code import install
                install(code_emission,temporary,profile,manifest,plan)
            manifest['format']=dict(profile='none',applied=False)
            finish(temporary,manifest)
            temporary.rename(out/key)
            result['projects'][profile]=dict(path=key,plan=str((stage/(key+'-plan')/'plan.json').relative_to(out)),
                       sourceObjects=len(inspected['assets']),nodes=len(ir['nodes']),components=len(plan['components']),
                       convertibleComponents=sum(c['convertible'] for c in plan['components']),
                       nativeValidation='not_run',layout=plan.get('projectLayout'),formatProfile='none',namespace=namespace)
        result['status']='partial'
    except (ValueError,OSError,KeyError,TypeError,IndexError) as error:
        result.update(status='failed',reason=getattr(error,'code','STRUCTURED_RECOVERY_FAILED'),message=str(error))
    write_json(stage/'recovery.json',result)
    return result
