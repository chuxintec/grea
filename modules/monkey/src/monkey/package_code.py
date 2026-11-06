"""Source-bound code emission and typed component projection for package conversion."""
import shutil
from .io import safe,read,load,sha,write_json,new_output,stage_manifest,stage_document,inside,finish,diagnostic
from .sources.compiled import fail
from .layout.standard import find_analysis,analysis_out


def declaration(path, language='ts'):
    path=safe(path);raw=read(path);data=load(raw)
    if data.get('schemaVersion')!=1 or data.get('kind')not in ('numeric-call-subdomain-v1','static-number-methods-v1'):
        fail('PACKAGE_CODE_CONTRACT',str(path),'Expected a supported explicit numeric code schema 1')
    if language not in ('ts','js'):fail('PACKAGE_CODE_LANGUAGE',str(language),'Expected ts or js')
    if data['kind']=='static-number-methods-v1':
        expected={'schemaVersion','kind','moduleName','moduleSha256','helperModuleName','helperModuleSha256','methods'}
        if set(data)!=expected or any(not isinstance(data[k],str)or not data[k]for k in expected-{'schemaVersion','methods'}):fail('PACKAGE_CODE_CONTRACT',str(path),'Unknown/missing static numeric module fields')
        if not isinstance(data['methods'],list)or not 1<=len(data['methods'])<=32 or any(not isinstance(m,str)or not m for m in data['methods']):fail('PACKAGE_CODE_CONTRACT',str(path),'Expected bounded explicit method names')
        return dict(path=str(path),sha256=sha(raw),data=data,language=language)
    if set(data)!={'schemaVersion','kind','moduleName','registrationId','moduleSha256','numericField'}:
        fail('PACKAGE_CODE_CONTRACT',str(path),'Unknown or missing contract fields')
    if any(not isinstance(data[k],str)or not data[k]for k in ('moduleName','registrationId','moduleSha256','numericField')):
        fail('PACKAGE_CODE_CONTRACT',str(path),'Expected explicit nonempty source identity and field')
    return dict(path=str(path),sha256=sha(raw),data=data,language=language)


def prepare(recovered, spec, namespace, output, root_namespace='Game'):
    from .code_model import inspect
    from .code_emit import emit
    data=spec['data']
    if data['kind']=='static-number-methods-v1':
        from .code_math import prepare as prepare_math
        return prepare_math(recovered,spec,namespace,output,root_namespace)
    matches=[m for m in recovered if m.get('name')==data['moduleName'] and any(r.get('identity')==data['registrationId'] for r in m.get('rf',[]))]
    if len(matches)!=1:fail('PACKAGE_CODE_MODULE',data['moduleName'],'Expected one exact original RF module; duplicates are ambiguous')
    module=matches[0];raw=module['source'].encode()
    if sha(raw)!=module.get('sha256') or sha(raw)!=data['moduleSha256']:
        fail('PACKAGE_CODE_SOURCE_CHANGED',module['sourceId'],'Source module differs from numeric contract')
    declaration_raw=read(safe(spec['path']))
    if sha(declaration_raw)!=spec['sha256']:fail('PACKAGE_CODE_CONTRACT_CHANGED',spec['path'],'Declaration changed before emission')
    out=new_output(output);source=out/'OriginalModule.js';source.write_bytes(raw);(out/'OriginalContract.json').write_bytes(declaration_raw)
    inspect(source,out/'Model',data['moduleName'])
    emit(source,out/'Model/code-model.json',out/'Emitted',[data['numericField']],spec.get('language','ts'),namespace,root_namespace)
    contract=load(read(out/'Emitted/Analysis/Code/code-contract.json'))
    if contract['presentation']['kind']!='label-adapter' or contract['presentation']['sourceRegistration']['identity']!=data['registrationId']:
        fail('PACKAGE_CODE_BASE',module['sourceId'],'Only source-proven native Label adapters currently bind automatically')
    methods=contract['methods'];setters=[m['name']for m in methods if m['semantic']['kind']=='write-instance-field'];getters=[m['name']for m in methods if m['semantic']['kind']=='read-instance-field']
    if len(setters)!=1 or len(getters)!=1:
        fail('PACKAGE_CODE_METHOD_PAIR',module['sourceId'],'Native numeric exercise requires one evidenced setter and getter')
    report=dict(schemaVersion=1,sourceModule=module['sourceId'],sourceModuleSha256=sha(raw),declarationSha256=spec['sha256'],
                contractSha256=sha(read(out/'Emitted/Analysis/Code/code-contract.json')),numericMethods=dict(setter=setters[0],getter=getters[0]),
                implementedMethods=contract['implementedMethods'],pendingMethods=len(contract['pendingMethods']),binding='not_run',sourceExecuted=False)
    write_json(out/'package-code.json',report)
    return out


def project_ir(ir_path, inspected, emission, output):
    from .code_presentation import label_components
    if load(read(emission/'package-code.json')).get('kind')=='static-number-methods-v1':return ir_path,stage_document(ir_path/'ir.json')
    ir=stage_document(ir_path/'ir.json');contract=load(read(emission/'Emitted/Analysis/Code/code-contract.json'));report=load(read(emission/'package-code.json'))
    identity=contract['presentation']['sourceRegistration']['identity']
    expected={c['sourceId'] for c in ir['components']if c['type']==identity}
    if not expected:fail('PACKAGE_CODE_BINDINGS',identity,'No matching serialized original components in supplied object graphs')
    asset_ids={sid.split('#')[0]for sid in expected};replacements={}
    for asset in inspected['assets']:
        sid=asset.get('sourceId',asset.get('id'))
        if sid not in asset_ids:continue
        for c in label_components(asset['document'],sid,contract):
            if c['sourceId']in replacements:fail('PACKAGE_CODE_BINDINGS',c['sourceId'],'Repeated source component')
            c.update(codeClassName=contract['className'],codeNamespace=contract['codeNamespace'],codeScriptGuid=contract['nativeIdentity']['unityScriptGuid'],codeScriptUuid=contract['nativeIdentity']['creatorScriptUuid'],numericMethods=report['numericMethods'])
            replacements[c['sourceId']]=c
    if set(replacements)!=expected:fail('PACKAGE_CODE_BINDINGS',identity,'Projection must cover every original matching component exactly once')
    out=new_output(output,[ir_path,emission])
    for row in stage_manifest(ir_path)['files']:
        if row['path']=='ir.json':continue
        raw=read(inside(ir_path,row['path']),max_bytes=128*1024*1024)
        if sha(raw)!=row['sha256']:fail('PACKAGE_CODE_IR_CHANGED',row['path'],'Normalized resource identity differs')
        dest=inside(out,row['path']);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    ir['components']=[replacements.get(c['sourceId'],c)for c in ir['components']]
    ir['diagnostics']=[d for d in ir['diagnostics']if not(d['code']=='UNSUPPORTED_COMPONENT_SEMANTIC'and d.get('sourceId')in expected)]
    ir['diagnostics'].extend(diagnostic('CODE_NUMERIC_SUBDOMAIN_HANDOFF',sid,'Only explicit Number setter/getter calls and static Label presentation; original pending methods remain unavailable',sid)for sid in sorted(expected))
    ir['codeProjection']=dict(report,sourceIrSha256=sha(read(ir_path/'ir.json',max_bytes=128*1024*1024)),sourceBindings=sorted(expected),binding='planned_native_import')
    write_json(out/'ir.json',ir);finish(out,ir)
    return out,ir


def install(emission, project, profile, manifest, plan):
    from .targets import unity
    contract_path=emission/'Emitted/Analysis/Code/code-contract.json';contract=load(read(contract_path));prefix='Unity/'if profile==unity.PROFILE else'Cocos/'
    script=None
    for row in contract['files']:
        original=row['path'].startswith('SourceRecovery/Code/Source/Emission/')
        if not row['path'].startswith(prefix)and not original:continue
        source=emission/'Emitted'/row['path'];raw=read(source)
        if sha(raw)!=row['sha256']:fail('PACKAGE_CODE_EMIT_CHANGED',str(source),'Generated source/meta differs')
        rel=row['path']if original else row['path'].removeprefix(prefix);dest=inside(project,rel)
        if dest.exists():fail('PACKAGE_CODE_COLLISION',rel,'Refuse to replace an existing generated asset')
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        if not original and rel.endswith(('.cs','.ts','.js')):
            if script is not None:fail('PACKAGE_CODE_TARGET',rel,'Expected one target script')
            script=rel
    shutil.copy2(contract_path,analysis_out(project,'code-contract.json'))
    binding_report=load(read(emission/'package-code.json'))
    binding_report['sourceBindings']=[dict(sourceId=c['sourceId'],node=c['node'],state='planned_native_import'if c['convertible']else'blocked_presentation_adapter')for c in plan['components']if c.get('codeClassName')==contract['className']]
    write_json(find_analysis(project,'package-code.json'),binding_report)
    shutil.copy2(emission/'OriginalContract.json',analysis_out(project,'numeric-code-declaration.json'))
    manifest['codeEmission']=dict(kind=contract.get('kind','numeric-call-subdomain-v1'),binding=contract['binding'],language='csharp'if profile==unity.PROFILE else contract.get('cocosCodeLanguage','ts'),sourceContractSha256=sha(read(contract_path)),
        scriptPath=script,scriptGuid=contract['nativeIdentity']['unityScriptGuid']if profile==unity.PROFILE else None,
        scriptUuid=contract['nativeIdentity']['creatorScriptUuid']if profile!=unity.PROFILE else None,sourceRegistration=contract['presentation']['sourceRegistration'])


def enrich_handoff(project):
    """Describe emitted static calls without pretending they are scene components."""
    path=find_analysis(project,'package-code.json')
    if not path.exists()or load(read(path)).get('kind')!='static-number-methods-v1':return None
    contract=load(read(find_analysis(project,'code-contract.json')));report=load(read(path))
    methods=[dict(name=m['name'],parameters=[p['name']for p in m['parameters']],sourceBytes=m['sourceBytes'],sourceSha256=m['sourceSha256'])for m in contract['methods']]
    task=dict(taskId='static-numeric-utility',module=contract['className'],sourceRefs=[report['sourceModule']],
              codeState='implemented-evidenced-number-subdomain',binding=report['binding'],sourceBindings=[],
              implementedMethods=methods,pendingMethods=[m['name']for m in contract['pendingMethods']],callDomain=contract['callDomain'],
              targetScript='manifest.json#/codeEmission/scriptPath',contract='Analysis/Code/code-contract.json',
              allowedPaths=['Assets/Game/Domain/','assets/Game/Domain/'],
              nextAction='Review static Number-call contract before using these methods; recover vector/object methods separately from exact preserved source',
              verification=['compile generated target script','Number boundary and rounding vectors','target Player/runtime before gameplay integration'],
              validation=dict(compile='not_run',numericCalls='not_run',player='not_run',business='not_run'))
    work=load(read(find_analysis(project,'agent-work.json')));work['tasks'].append(task);write_json(find_analysis(project,'agent-work.json'),work)
    invocation=contract['codeNamespace']+'.'+contract['className'] if (project/'ProjectSettings').exists()else contract['className']
    lines=['# Static numeric utility', '',f'Class: `{invocation}`. Resolve the current script from `manifest.json` → `codeEmission.scriptPath`; this pointer stays valid after formatting.',
           '',f"{len(methods)} source methods emitted, {len(contract['pendingMethods'])} pending. Binding: `{report['binding']}`. No source constructor or helper executes, and no source component is wired by this utility.", '',
           'Implemented calls:',*['- `'+invocation+'.'+m['name']+'('+', '.join(m['parameters'])+')` → number / C# double'for m in methods], '',
           'Accepted calls: '+contract['callDomain']['accepted']+'.', 'Excluded calls: '+contract['callDomain']['excluded']+'.',
           'Rounding: '+contract['callDomain']['rounding']+'. Do not replace unclamped interpolation with an engine clamp or reassociate arithmetic.', '',
           'Pending original methods: '+', '.join('`'+m['name']+'`'for m in contract['pendingMethods'])+'.',
           'Exact source ranges, SHA256, helper context and method mappings: `../Analysis/Code/code-contract.json`. Original module, reviewed helper and typeof dependency: `../SourceRecovery/Original/`.',
           'This generated candidate has no compile, numeric runtime, Player or gameplay acceptance yet. External validation receipts must name this candidate and exact code hashes.','']
    (project/'Docs/STATIC-NUMERIC-UTILITY.md').write_text('\n'.join(lines),encoding='utf-8')
    start=project/'Docs/START-HERE.md';start.write_text(start.read_text(encoding='utf-8')+'\nAn evidenced static utility is available: [calls, domain and pending methods](STATIC-NUMERIC-UTILITY.md). Its generated methods are separate from the uncompiled original code drafts.\n',encoding='utf-8')
    return len(work['tasks'])
