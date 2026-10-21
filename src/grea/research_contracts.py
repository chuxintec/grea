"""Finite evidence normalization input; semantic judgments remain analyst supplied."""
KINDS=['prefab','scene','eui','spine','character','level','config_row','system']
STAGES=['declared','acquired','parsed','reference_closed','runtime']
def documents():
    text={'type':'string','minLength':1,'maxLength':2048}
    arr=lambda x:{'type':'array','maxItems':100000,'items':x}
    obj=lambda p,req:{'type':'object','additionalProperties':False,'properties':p,'required':req}
    source=obj(dict(id=text,path=text,sha256={'type':'string','pattern':'^[0-9a-f]{64}$'}),['id','path','sha256'])
    item=obj(dict(id=text,kind={'enum':KINDS},stage={'enum':STAGES},source_id=text,version=text),['id','kind','stage','source_id'])
    proto=obj(dict(name=text,direction={'enum':['client_to_server','server_to_client','internal']},kind={'enum':['rpc','message','field']},source_id=text),['name','direction','kind','source_id'])
    judgment=obj(dict(topic=text,type={'enum':['fact','inference','hypothesis','experience','unknown']},text=text,source_ids=arr(text)),['topic','type','text','source_ids'])
    interval={'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':0}}
    estimate=obj(dict(role=text,active_hours=interval,collaboration_days=interval,backend_included={'type':'boolean'},assumptions=arr(text),confidence={'enum':['low','medium','high']}),['role','active_hours','collaboration_days','backend_included','assumptions','confidence'])
    media=obj(dict(kind={'enum':['screenshot','video']},source_id=text,timecode=text),['kind','source_id'])
    coverage=obj(dict(area={'enum':['core_loop','tutorial','progression','ui_comparison']},system=text,status={'enum':['played','observed','partial','locked','blocked','static_only','not_run','not_applicable']},identity=text,operator=text,entry=text,actions=text,result=text,understanding=text,next_step=text,media=arr(media)),['area','system','status','identity','operator','entry','actions','result','understanding','next_step','media'])
    return {'research-input.schema.json':dict(obj(dict(schema_version={'const':1},game=text,sources=arr(source),items=arr(item),protocols=arr(proto),complete_kinds={'type':'array','uniqueItems':True,'items':{'enum':KINDS}},judgments=arr(judgment),estimates=arr(estimate),play_coverage=arr(coverage)),['schema_version','game','sources','items','protocols']),**{'$schema':'https://json-schema.org/draft/2020-12/schema'})}
