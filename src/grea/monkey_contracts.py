"""Generated request schema for the versioned monkey pipeline."""
from .integrations.monkey.pipeline import OPERATIONS


def documents():
    variants=[]
    for operation,spec in OPERATIONS.items():
        properties={key:{'type':'string','minLength':1} for key in spec.get('paths',())}
        properties.update({key:{'type':'string','enum':list(values)} for key,values in spec.get('values',{}).items()})
        properties.update({key:{'type':'integer','minimum':bounds[0],'maximum':bounds[1]} for key,bounds in spec.get('integers',{}).items()})
        properties.update({key:{'type':'boolean'} for key in spec.get('flags',())})
        properties.update({key:{'type':'string','format':'date-time'} for key in spec.get('text',())})
        variants.append({'type':'object','additionalProperties':False,
            'required':['schema_version','operation','options','input_roots','timeout_seconds'],
            'properties':{'schema_version':{'const':1},'operation':{'const':operation},
                'options':{'type':'object','additionalProperties':False,'required':sorted(spec['required']),
                           'properties':dict(sorted(properties.items()))},
                'input_roots':{'type':'array','minItems':1,'maxItems':64,'items':{'type':'string','minLength':1}},
                'timeout_seconds':{'type':'integer','minimum':1,'maximum':1800}}})
    return {'monkey-pipeline.schema.json':{'$schema':'https://json-schema.org/draft/2020-12/schema',
        'title':'Pinned monkey 0.4.0 pipeline request; path/identity checks are runtime requirements','oneOf':variants}}
