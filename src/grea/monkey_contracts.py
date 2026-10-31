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
        'title':'Pinned monkey finite pipeline request; path/identity checks are runtime requirements','oneOf':variants},
        'monkey-shader-handoff.schema.json':SHADER_HANDOFF_SCHEMA}


# Frozen producer-owned handoff schema, not a second Shader classifier.
SHADER_HANDOFF_SCHEMA = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
 'title': 'monkey-shader-handoff/1',
 'type': 'object',
 'additionalProperties': False,
 'required': ['schema', 'items'],
 'properties': {'schema': {'const': 'monkey-shader-handoff/1'},
                'items': {'type': 'array', 'maxItems': 5000, 'items': {'$ref': '#/$defs/item'}}},
 '$defs': {'item': {'type': 'object',
                    'additionalProperties': False,
                    'required': ['path',
                                 'bytes',
                                 'sha256',
                                 'classification',
                                 'source',
                                 'target',
                                 'dialect',
                                 'platformEvidence',
                                 'nativeCompilation',
                                 'runtimeDisposition',
                                 'evidenceId'],
                    'properties': {'path': {'type': 'string', 'pattern': '^Assets/'},
                                   'bytes': {'type': 'integer', 'minimum': 0, 'maximum': 16777216},
                                   'sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
                                   'classification': {'enum': ['source-text',
                                                               'platform-compiled',
                                                               'recovered-binary',
                                                               'unknown',
                                                               'unsupported']},
                                   'source': {'type': 'object'},
                                   'target': {'oneOf': [{'type': 'null'},
                                                        {'type': 'object',
                                                         'additionalProperties': False,
                                                         'required': ['guid', 'localFileID'],
                                                         'properties': {'guid': {'type': 'string',
                                                                                 'pattern': '^[0-9a-f]{32}$'},
                                                                        'localFileID': {'type': 'integer',
                                                                                        'minimum': -9223372036854775808,
                                                                                        'maximum': 9223372036854775807,
                                                                                        'not': {'const': 0}}}}]},
                                   'dialect': {'type': ['string', 'null']},
                                   'platformEvidence': {'type': 'array'},
                                   'nativeCompilation': {'const': 'not_run'},
                                   'runtimeDisposition': {'enum': ['source-review',
                                                                   'evidence-only',
                                                                   'blocked']},
                                   'evidenceId': {'type': 'string', 'minLength': 1}}}}}
