"""Request schema generated from the same named beaver forwarding table."""
from .integrations.beaver_operations import OPERATIONS, operation_versions, UTC_DEADLINE_PATTERN
from .integrations.beaver import SUPPORTED_VERSIONS


BEAVER_RESULT_SCHEMA = {
    '$schema':'https://json-schema.org/draft/2020-12/schema',
    'title':'beaver-result/1 envelope for pinned implementations; engineering data remains provider-owned',
    'type':'object',
    'required':['schemaVersion','contract','operationId','producer','status','actualChanges','artifacts','diagnostics','limitations','verification'],
    'properties':{
        'schemaVersion':{'const':1},'contract':{'const':'beaver-result/1'},
        'operationId':{'type':'string','minLength':1},
        'producer':{'type':'object','required':['name','version','implementationSha256'],
                    'properties':{'name':{'const':'beaver'},'version':{'type':'string','minLength':1},
                                  'implementationSha256':{'type':'string','pattern':'^[a-f0-9]{64}$'}}},
        'status':{'enum':['ok','partial','blocked','failed','not_run']},'data':{'type':'object'},
        'actualChanges':{'type':'array','items':{'anyOf':[{'type':'object'},{'type':'string','minLength':1}]}},
        'artifacts':{'type':'array','items':{'type':'object','required':['path','sha256'],
                    'properties':{'path':{'type':'string','minLength':1},'sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'}}}},
        'diagnostics':{'type':'array','items':{'type':'object'}},
        'limitations':{'type':'array','items':{'type':'string'}},
        'verification':{'type':'object','required':['native','player','visual','business'],
                        'properties':{'native':{'type':['string','object']},'player':{'type':'string'},
                                      'visual':{'type':'string'},'business':{'type':'string'}}},
    },
    'allOf':[{'if':{'properties':{'status':{'enum':['ok','partial']}}},'then':{'required':['data']}}],
}


def validate_result(value):
    from jsonschema import Draft202012Validator
    error=next(Draft202012Validator(BEAVER_RESULT_SCHEMA).iter_errors(value),None)
    if error is not None:raise ValueError('Invalid beaver-result/1 schema at '+error.json_path+': '+error.message)


def documents():
    variants=[]
    for name,spec in OPERATIONS.items():
        properties={k:{'type':'string','minLength':1}for k in spec.get('paths',())}
        properties.update({k:{'type':'array','minItems':bounds[0],'maxItems':bounds[1],
                              'items':{'type':'string','minLength':1}}
                           for k,bounds in spec.get('path_lists',{}).items()})
        properties.update({k:{'type':'string','pattern':'^[a-f0-9]{64}$'}for k in spec.get('hashes',())})
        properties.update({k:{'type':'integer','minimum':b[0],'maximum':b[1]}for k,b in spec.get('integers',{}).items()})
        properties.update({k:{'type':'string','minLength':1,'maxLength':4096}for k in spec.get('text',())})
        properties.update({k:{'type':'boolean'}for k in spec.get('flags',())})
        for key,values in spec.get('enums',{}).items():properties[key]['enum']=sorted(values)
        if name in ('qa.launch','qa.collect','qa.inspect-instance','qa.bind','qa.virtual-bind'):
            for key in ('project','build','profile','run'):
                if key in properties:properties[key].update(pattern='^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$',maxLength=64)
        options={'type':'object','additionalProperties':False,'required':sorted(spec['required']),'properties':dict(sorted(properties.items()))}
        if name=='image.compress':options['allOf']=[{'if':{'required':['apply'],'properties':{'apply':{'const':True}}},'then':{'required':['expected-source']}}]
        if name=='adoption.plan':options['dependentRequired']={'sdk-migration':['expected-sdk-migration'],'expected-sdk-migration':['sdk-migration']}
        if name=='structure.inspect':options['dependentRequired']={'product-root':['profile'],'profile':['product-root']}
        if name=='debug.start':
            options['dependentRequired']={'width':['height'],'height':['width'],
                'observation-spec':['expected-observation'],'expected-observation':['observation-spec']}
            options['properties']['deadline-utc']['pattern']='^'+UTC_DEADLINE_PATTERN+'$'
        for option,versions in spec.get('option_versions',{}).items():
            options['properties'][option]['x-beaver-versions']=sorted(versions)
        for option,values in spec.get('value_versions',{}).items():
            options['properties'][option]['x-beaver-value-versions']={value:sorted(versions) for value,versions in values.items()}
        variants.append({'type':'object','additionalProperties':False,'required':['schema_version','operation','options','timeout_seconds'],
            **({'x-beaver-budget':{'nativePhases':spec['native_phases'],'overheadSeconds':spec['budget_overhead'],'durationOption':'timeout'}} if 'native_phases' in spec else {}),
            **({'x-beaver-version-budgets':{v:{'nativePhases':b['native_phases'],'overheadSeconds':b['budget_overhead'],
                'maximumTimeout':b['maximum_timeout'],'durationOption':'timeout'} for v,b in spec['version_budgets'].items()}} if 'version_budgets' in spec else {}),
            'x-beaver-versions':sorted(operation_versions(name,spec)),
            'x-beaver-capability':spec.get('capability',name),
            'properties':{'schema_version':{'const':1},'operation':{'const':name},'options':options,
                          'timeout_seconds':{'type':'integer','minimum':1,'maximum':1800}}})
    return {'beaver-operation.schema.json':{'$schema':'https://json-schema.org/draft/2020-12/schema',
        'title':'Finite pinned beaver forwarding; exact version, capability and identity checked at runtime','oneOf':variants},
        'beaver-result.schema.json':BEAVER_RESULT_SCHEMA}
