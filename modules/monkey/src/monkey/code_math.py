"""Source-bound static binary64 expression methods; no source helper executes."""
from pathlib import Path
import tempfile
import re
import os
import subprocess
import shutil
from .io import safe,read,load,sha,new_output,write_json
from .sources.compiled import fail
from .code_emit import name
from .layout.standard import find_analysis

# Reviewed literal createClass / defineProperty table implementation. Other
# helpers need their own source proof; a method-table shape alone is insufficient.
HELPER_PROFILES={'1868b5ac170af89a19b39bb47eb12a961ee7e903da127a44fea68cb7a3c7b80c':dict(profile='babel-createClass-static-descriptors-v1',freeAlias='e',typeOfModule='@babel/runtime/helpers/typeof.js',typeOfSha256='537d17dd369a0b62f68efe94c21de2d7db9e5c3b2170c69027151e79ab4edff4')}
KIND='static-number-methods-v1'
OPS={'+':'add','-':'sub','*':'mul','/':'div'}


def render(expression,language,depth=0):
    if depth>32:fail('CODE_MATH_EXPRESSION','$','Expression depth exceeded')
    kind=expression['kind']
    if kind=='parameter':return name(expression['name'])
    if kind=='literal':
        n=expression['value']
        if type(n)not in(int,float):fail('CODE_MATH_EXPRESSION','$','Expected numeric literal')
        return format(float(n),'.17g')+('D'if language=='cs'else'')
    if kind=='math-pi':return 'global::System.Math.PI'if language=='cs'else'Math.PI'
    if kind=='unary':
        value=render(expression['operand'],language,depth+1)
        if expression['operator']=='+':return '('+value+')'
        if expression['operator']=='-':return '_monkey_neg('+value+')'if language=='cs'else'(-'+value+')'
    if kind=='binary'and expression['operator']in OPS:
        left=render(expression['left'],language,depth+1);right=render(expression['right'],language,depth+1);op=expression['operator']
        return '_monkey_'+OPS[op]+'('+left+', '+right+')'if language=='cs'else'('+left+' '+op+' '+right+')'
    fail('CODE_MATH_EXPRESSION',str(kind),'Unsupported expression; no raw source interpolation')


def emit(source,model_path,helper,dependencies,output,selected,language='ts',namespace='monkey-project',context=None,typeof_source=None,root_namespace='Game'):
    from .code_model import inspect
    from .targets.unity import guid
    from .targets.cocos import identity,meta
    source=safe(source);helper=safe(helper);raw=read(source);helper_raw=read(helper);model_raw=read(safe(model_path));model=load(model_raw)
    if model.get('source')!={'sha256':sha(raw),'bytes':len(raw)} or model.get('sourceExecuted')is not False:fail('CODE_EMIT_SOURCE_CHANGED',str(source),'Source differs from model')
    if not isinstance(namespace,str)or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',namespace):fail('CODE_NAMESPACE',str(namespace),'Expected bounded identity namespace')
    if sha(helper_raw)not in HELPER_PROFILES:fail('CODE_MATH_HELPER_UNVERIFIED',str(helper),'Literal method table does not prove helper semantics; exact reviewed helper required')
    profile=HELPER_PROFILES[sha(helper_raw)]
    if context is None or typeof_source is None or context.get('sourceExecuted')is not False or context.get('helperSha256')!=sha(helper_raw) or context.get('callbackSha256')!=profile['typeOfSha256']or context.get('resolvedModule')!=profile['typeOfModule']or sha(typeof_source)!=profile['typeOfSha256']:
        fail('CODE_MATH_CONTEXT_REQUIRED',str(helper),'Exact lexical typeof dependency proof is required before emission')
    if language not in ('ts','js'):fail('CODE_LANGUAGE',language,'Expected ts or js')
    with tempfile.TemporaryDirectory()as t:
        verified=Path(t).resolve()/'facts';inspect(source,verified,model['moduleName'])
        if load(read(verified/'code-model.json'))!=model:fail('CODE_EMIT_MODEL_CHANGED',str(model_path),'Recomputed static facts differ')
    classes=model.get('descriptorClasses',[])
    if len(classes)!=1:fail('CODE_MATH_CLASS','$','One exact declared source class is required')
    cls=classes[0];class_name=name(cls['exportedName'])
    if class_name=='Math' or not cls.get('literalModuleShape') or not cls.get('descriptorTablesSafe'):
        fail('CODE_MATH_CLASS',class_name,'Unsupported module setup, descriptor shape or intrinsic shadow')
    deps={str(r['key']):r['module']for r in dependencies}
    binding=cls['importBinding']
    if binding['imported']!='createClass' or deps.get(str(binding['setterIndex']))!='./rollupPluginModLoBabelHelpers.js':
        fail('CODE_MATH_IMPORT',class_name,'Original literal dependency does not match the reviewed helper import')
    registrations=[r for r in model['registrations']if r['name']==class_name and r.get('declarationKind')=='creator3-cclegacy-import-candidate']
    if len(registrations)!=1 or deps.get(str(registrations[0]['importBinding']['setterIndex']))!='cc':
        fail('CODE_MATH_REGISTRATION',class_name,'Expected exact cclegacy source registration and original cc import')
    if not 1<=len(selected)<=32 or len(set(selected))!=len(selected):fail('CODE_MATH_SELECTION','$','Expected1..32 exact unique methods')
    picked=[]
    for requested in selected:
        name(requested)
        matches=[m for m in model['methods']if m['name']==requested]
        if len(matches)!=1:fail('CODE_MATH_SELECTION',requested,'Ambiguous or missing original method')
        m=matches[0]
        if m.get('scopeBytes')!=cls['scopeBytes']or m.get('ownerAlias')!=cls['constructorAlias']or m.get('semantic',{}).get('kind')!='pure-number-expression-candidate' or m.get('static')is not True:
            fail('CODE_MATH_METHOD',requested,'Only verified static numeric-return expressions supported')
        if requested==class_name or requested.startswith('_monkey_'):fail('CODE_MEMBER_CONFLICT',requested,'Target helper/class collision')
        for parameter in m['parameters']:
            name(parameter['name'])
            if parameter['name'].startswith('_monkey_'):fail('CODE_MEMBER_CONFLICT',parameter['name'],'Target helper collision')
        picked.append(m)
    if sha(read(source))!=sha(raw)or sha(read(helper))!=sha(helper_raw):fail('CODE_EMIT_SOURCE_CHANGED',str(source),'Source/helper changed before emission')
    out=new_output(output,[source,model_path,helper]);cs=['// Generated static Number-call subset. Source helpers never execute.','namespace '+root_namespace+'.Domain.Math {',f'public static class {class_name} {{']
    attr='[global::System.Runtime.CompilerServices.MethodImpl(global::System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]'
    # One separately rounded binary64 operation per call; prevent fused mul-add
    # contraction across original JavaScript operator boundaries.
    for op,label in OPS.items():cs += ['    '+attr,f'    private static double _monkey_{label}(double x, double y) {{ return x {op} y; }}']
    cs += ['    '+attr,'    private static double _monkey_neg(double x) { return -x; }']
    target=[f'export class {class_name} {{'if language=='ts'else f'class {class_name} {{']
    for method in picked:
        params=[p['name']for p in method['parameters']];member=method['name'];expression=method['semantic']['expression']
        cs.append(f'    public static double {member}('+', '.join('double '+p for p in params)+') { return '+render(expression,'cs')+'; }')
        parameters=', '.join(p+(': number'if language=='ts'else'')for p in params)
        target.append(f'    static {member}({parameters})'+(': number'if language=='ts'else'')+' { return '+render(expression,language)+'; }')
    cs += ['}','}'];target += ['}']
    if language=='js':target += [f'export {{ {class_name} }};']
    source_id=registrations[0]['identity'];script_guid=guid(namespace,'code/'+source_id+'/'+class_name);script_uuid=identity(namespace,'code/'+source_id+'/'+class_name)
    files={f'Unity/Assets/Game/Domain/Math/{class_name}.cs':'\n'.join(cs)+'\n',f'Cocos/assets/Game/Domain/Math/{class_name}.{language}':'\n'.join(target)+'\n',
           f'Unity/Assets/Game/Domain/Math/{class_name}.cs.meta':'fileFormatVersion: 2\nguid: '+script_guid+'\n',
           f'Cocos/assets/Game/Domain/Math/{class_name}.{language}.meta':__import__('json').dumps(meta(script_uuid,'typescript'if language=='ts'else'javascript','4.0.24'),indent=2)+'\n',
           'SourceRecovery/Code/Source/Emission/'+class_name+'.js':raw,'SourceRecovery/Code/Source/Emission/ReviewedBabelHelpers.js':helper_raw,'SourceRecovery/Code/Source/Emission/ReviewedTypeofHelper.js':typeof_source}
    if language=='js':files['Cocos/assets/package.json']='{"type":"module"}\n'
    for path,body in files.items():
        dest=out/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(body if isinstance(body,bytes)else body.encode())
    pending=[m for m in model['methods']if m not in picked]
    contract=dict(schemaVersion=1,kind=KIND,status='partial',source=model['source'],codeModelSha256=sha(model_raw),className=class_name,codeNamespace=root_namespace+'.Domain.Math',sourceMethods=len(model['methods']),implementedMethods=len(picked),
                  methods=picked,pendingMethods=pending,namespace=namespace,cocosCodeLanguage=language,sourceExecuted=False,
                  helper=dict(sha256=sha(helper_raw),profile=profile['profile'],context=context,executed=False),sourceClass=cls,
                  callDomain=dict(kind='explicit-static-number-calls-v1',accepted='Explicit JavaScript Number/C# double arguments including signed zero, NaN and infinities; unmodified methods and Math.PI',
                                  excluded='Non-number/omitted arguments, constructors, helper side effects, mutable global intrinsics, vector/object methods',rounding='one binary64 operation per source operator; no fused contraction'),
                  presentation=dict(kind='static-utility',sourceRegistration=registrations[0]),nativeIdentity=dict(unityScriptGuid=script_guid,creatorScriptUuid=script_uuid),
                  binding='static-calls-only-no-component-binding',compiled='not_run',business='not_run',files=[dict(path=p,sha256=sha(v if isinstance(v,bytes)else v.encode()))for p,v in files.items()])
    (out/'Analysis').mkdir();write_json(find_analysis(out,'code-contract.json'),contract)
    return contract


def prepare(recovered,spec,namespace,output,root_namespace='Game'):
    """Called with fresh static module-index records from the explicit input set."""
    from .code_model import inspect
    data=spec['data']
    def exact(module_name,digest):
        matches=[r for r in recovered if r.get('name')==module_name]
        if len(matches)!=1:fail('PACKAGE_CODE_MODULE',module_name,'One exact declared source module required')
        row=matches[0];raw=row['source'].encode()
        if sha(raw)!=digest or row['sha256']!=digest:fail('PACKAGE_CODE_SOURCE_CHANGED',module_name,'Source module differs from explicit contract')
        return row,raw
    module,raw=exact(data['moduleName'],data['moduleSha256'])
    helper,helper_raw=exact(data['helperModuleName'],data['helperModuleSha256'])
    if data['helperModuleName']!=data['moduleName'].rsplit('/',1)[0]+'/rollupPluginModLoBabelHelpers.js':
        fail('CODE_MATH_IMPORT',data['helperModuleName'],'Declared sibling helper differs from original dependency profile')
    declaration_raw=read(safe(spec['path']))
    if sha(declaration_raw)!=spec['sha256']:fail('PACKAGE_CODE_CONTRACT_CHANGED',spec['path'],'Declaration changed')
    out=new_output(output)
    source=out/'OriginalModule.js';source.write_bytes(raw)
    helper_source=out/'OriginalHelper.js';helper_source.write_bytes(helper_raw)
    (out/'OriginalContract.json').write_bytes(declaration_raw)
    # Source export binding supplies the class name. The module URL is kept
    # separately and never sanitized into a different source identity.
    context,typeof_raw=helper_context(Path(output).parent/'InputTree',helper,helper_raw)
    write_json(out/'helper-context.json',context)
    inspect(source,out/'Model',data['moduleName'])
    contract=emit(source,out/'Model/code-model.json',helper_source,module['dependencies'],out/'Emitted',data['methods'],spec.get('language','ts'),namespace,context,typeof_raw,root_namespace)
    report=dict(schemaVersion=1,kind=KIND,sourceModule=module['sourceId'],sourceModuleSha256=sha(raw),helperModule=helper['sourceId'],helperModuleSha256=sha(helper_raw),
                declarationSha256=spec['sha256'],contractSha256=sha(read(out/'Emitted/Analysis/Code/code-contract.json')),implementedMethods=contract['implementedMethods'],pendingMethods=len(contract['pendingMethods']),
                binding='static-calls-only-no-component-binding',sourceExecuted=False)
    write_json(out/'package-code.json',report)
    return out


def helper_context(tree,helper,helper_raw):
    """Follow the reviewed helper's free alias in its original immutable script."""
    from .io import inside
    import json
    profile=HELPER_PROFILES.get(sha(helper_raw))
    if not profile:fail('CODE_MATH_HELPER_UNVERIFIED',helper['sourceId'],'Exact reviewed helper required')
    path=inside(safe(tree),helper.get('sourceSnapshotPath',helper['sourceFile']));raw=read(path)
    span=helper['source_bytes']
    if any(type(span.get(k))is not int for k in ('start','end'))or not 0<=span['start']<span['end']<=len(raw)or raw[span['start']:span['end']]!=helper_raw:
        fail('CODE_MATH_CONTEXT_CHANGED',str(path),'Helper callback differs from original script span')
    node=shutil.which('node')
    if not node:fail('DEPENDENCY_MISSING','Node','Required static context parser')
    job=dict(source=str(path),start=span['start'],end=span['end'],helperSha256=sha(helper_raw),freeAlias=profile['freeAlias'])
    env={k:v for k,v in os.environ.items()if k not in ('NODE_OPTIONS','NODE_PATH')}
    child=subprocess.Popen([node,'--max-old-space-size=256',str(Path(__file__).with_name('module-context.cjs'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    try:
        stdout,stderr=child.communicate(json.dumps(job).encode(),timeout=30)
    except subprocess.TimeoutExpired:
        child.terminate()
        try:child.communicate(timeout=5)
        except subprocess.TimeoutExpired:fail('CODE_MATH_CONTEXT_CHILD_PENDING',str(path),'Owned context worker did not exit after TERM')
        fail('CODE_MATH_CONTEXT_BUDGET',str(path),'Static context deadline reached')
    if child.returncode:fail('CODE_MATH_CONTEXT_FAILED',str(path),'Static lexical dependency could not be proven; source was not executed')
    context=load(stdout)
    if context.get('sourceSha256')!=sha(raw)or context.get('helperSha256')!=sha(helper_raw)or context.get('sourceExecuted')is not False or context.get('resolvedModule')!=profile['typeOfModule']or context.get('callbackSha256')!=profile['typeOfSha256']:
        fail('CODE_MATH_CONTEXT_UNVERIFIED',str(path),'Original lexical dependency differs from reviewed profile')
    ctx=context['callbackBytes'];body=raw[ctx['start']:ctx['end']]
    if sha(body)!=profile['typeOfSha256']or sha(read(path))!=sha(raw):fail('CODE_MATH_CONTEXT_CHANGED',str(path),'Context changed before evidence capture')
    context.update(sourceFile=helper['sourceFile'],workerSha256=sha(read(Path(__file__).with_name('module-context.cjs'))),processExited=True,exitCode=child.returncode)
    return context,body
