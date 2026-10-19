"""Declared UI/UX change boundaries; never authorization or gameplay attestation."""
from jsonschema import Draft202012Validator
from .common import GreaError, digest

INVARIANTS = ['combat_rules','progression','damage_hit_timing','rng_choices','costs_rewards_eligibility','persistence_semantics','animation_events_cancel']

def documents():
    text={'type':'string','minLength':1,'maxLength':1024}
    return {'change-contract.schema.json':{'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object','additionalProperties':False,
        'required':['schema_version','scope','baseline_sha256','product_id','baseline_product_id','save_namespace','baseline_save_namespace','design','allowed_changes','invariants'],
        'properties':{'schema_version':{'const':1},'scope':{'const':'ui_ux'},'baseline_sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'},
        'product_id':text,'baseline_product_id':text,'save_namespace':text,'baseline_save_namespace':text,
        'design':{'type':'object','additionalProperties':False,'required':['state','reference','sha256'],'properties':{'state':{'enum':['candidate','approved']},'reference':text,'sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'}}},
        'allowed_changes':{'type':'array','minItems':1,'maxItems':5,'uniqueItems':True,'items':{'enum':['visual_style','layout','navigation','feedback','readability']}},
        'invariants':{'type':'array','minItems':len(INVARIANTS),'maxItems':len(INVARIANTS),'uniqueItems':True,'items':{'enum':INVARIANTS}},
        'ui_ux_budget':text}}}

def validate(value, baseline_sha256=None):
    schema=documents()['change-contract.schema.json']
    errors=list(Draft202012Validator(schema).iter_errors(value))
    if errors:raise GreaError('INVALID_CHANGE_CONTRACT',errors[0].message)
    for name in ('product_id','save_namespace'):
        if value[name].strip().casefold()==value['baseline_'+name].strip().casefold():
            raise GreaError('CHANGE_IDENTITY_COLLISION','Derived product and save namespace must be explicitly isolated.')
    if baseline_sha256 is not None and value['baseline_sha256']!=baseline_sha256:
        raise GreaError('CHANGE_BASELINE_MISMATCH','Contract must bind the selected baseline artifact digest.')
    return dict(value)

def fingerprint(value):return digest(validate(value))

def theme_documents():
    text={'type':'string','minLength':1,'maxLength':4096}
    sha={'type':'string','pattern':'^[0-9a-f]{64}$'}
    vector=lambda size: {'type':'array','minItems':size,'maxItems':size,'items':{'type':'number'}}
    sprite={'type':'object','additionalProperties':False,'required':['mode','width','height','pivot','border','pixels_per_unit','file_id'],
        'properties':{'mode':{'const':'single'},'width':{'type':'integer','minimum':1},'height':{'type':'integer','minimum':1},'pivot':vector(2),'border':vector(4),'pixels_per_unit':{'type':'number','exclusiveMinimum':0},'file_id':{'type':'integer'}}}
    props={'usage':{'const':'ui_sprite'},'alpha_required':{'type':'boolean'},'asset':text,'replacement':text,'source_sha256':sha,'replacement_sha256':sha,'meta_sha256':sha,'guid':{'type':'string','pattern':'^[0-9a-f]{32}$'},'sprite':sprite}
    return {'theme-map.schema.json':{'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object','additionalProperties':False,'required':['schema_version','change_contract','assets'],
        'properties':{'schema_version':{'const':1},'change_contract':documents()['change-contract.schema.json'],'assets':{'type':'array','minItems':1,'maxItems':256,'items':{'type':'object','additionalProperties':False,'required':list(props),'properties':props}}}}}
