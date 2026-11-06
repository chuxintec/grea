"""Finite native Label field projection for statically declared Label script adapters."""
from .normalize import component_ir,expand_nodes
from .sources.compiled import fail


def label_components(document,asset_id,contract):
    presentation=contract.get('presentation',{})
    if presentation.get('kind')!='label-adapter' or presentation.get('sourceClassScope',{}).get('baseArgument')!='cc.Label':
        fail('CODE_LABEL_DECLARATION',asset_id,'Expected source-scoped cc.Label adapter declaration')
    registration=presentation.get('sourceRegistration',{});identity=registration.get('identity')
    if not isinstance(identity,str)or not identity or registration.get('name')!=contract.get('className'):
        fail('CODE_LABEL_REGISTRATION',asset_id,'Missing matching original RF declaration')
    result=[]
    def project(index,value):
        if value.get('__type__')!=identity:return
        obj=dict(value,__type__='cc.Label');component,gaps=component_ir(asset_id,index,obj)
        # A custom serialized business field must not disappear into a native Label.
        unknown=[gap for gap in gaps if gap.startswith('unknown component field:')]
        if unknown:fail('CODE_LABEL_CUSTOM_FIELDS',component['sourceId'],'; '.join(unknown))
        component.update(sourceScriptIdentity=identity,sourceScriptName=contract['className'],
                         codeBehavior='numeric-subdomain-only',pendingMethods=len(contract['pendingMethods']))
        result.append(component)
    for index,obj in expand_nodes(document['instances'],asset_id):
        if not isinstance(obj,dict):continue
        if obj.get('__type__')in ('cc.Node','cc.Scene'):
            for ordinal,value in enumerate(obj.get('_components',[])):
                if isinstance(value,dict)and '__type__'in value:project(f'{index}/components/{ordinal}',value)
        else:project(index,obj)
    if not result:fail('CODE_LABEL_SOURCE_BINDINGS',asset_id,'No exact original script components')
    if len({c['sourceId']for c in result})!=len(result):fail('CODE_LABEL_SOURCE_BINDINGS',asset_id,'Repeated original component identity')
    return result
