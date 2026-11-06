"""Native source-bound numeric adapter evidence; counts alone never prove bindings."""
import re
from .io import diagnostic


def _id(value):
    return isinstance(value,str)and bool(re.fullmatch(r'-?[1-9][0-9]{0,18}',value))and -(1<<63)<=int(value)<(1<<63)


def numeric(specs,rows,engine,scope,exercise=None):
    expected={c['sourceId']:c for c in specs if c.get('convertible')and c.get('codeClassName')}
    if not expected:return []
    def table(values):
        if not isinstance(values,list)or any(not isinstance(v,dict)for v in values):return None
        data={v.get('sourceId'):v for v in values}
        return data if len(data)==len(values)and set(data)==set(expected)else None
    actual=table(rows);errors=[]
    if actual is None:return [diagnostic('NUMERIC_CODE_BINDING_READBACK',scope,'Missing/duplicate/foreign numeric source-component bindings')]
    for source_id,spec in expected.items():
        row=actual[source_id];valid=isinstance(spec.get('sourceScriptIdentity'),str)and bool(spec['sourceScriptIdentity'])and row.get('sourceScriptIdentity')==spec['sourceScriptIdentity']and row.get('uninitialized')is True
        if engine=='unity':
            valid=valid and isinstance(spec.get('codeScriptGuid'),str)and bool(re.fullmatch('[0-9a-f]{32}',spec['codeScriptGuid']))and row.get('scriptGuid')==spec['codeScriptGuid']and row.get('bound')is True and _id(row.get('componentFileId'))and _id(row.get('labelFileId'))and row.get('fileIdOwner')in ('persistent-asset','saved-prefab-source')
        else:
            valid=valid and row.get('className')==spec['codeClassName']and all(isinstance(row.get(k),str)and row[k]for k in ('classId','componentUuid','nodeUuid'))
            if spec.get('codeScriptUuid'):
                from .identities import creator_script_class_id
                valid=valid and row.get('classId')==creator_script_class_id(spec['codeScriptUuid'])
        if not valid:errors.append(diagnostic('NUMERIC_CODE_BINDING_READBACK',scope+'/'+source_id,'Saved numeric class/script/reference/identity/state differs',source_id))
    if exercise is not None:
        trials=table(exercise)
        if trials is None or any(not all(trials[sid].get(k)is True for k in ('numberBoundaries','instancesIndependent','textUnchanged'))for sid in expected):
            errors.append(diagnostic('NUMERIC_CODE_SEMANTICS_READBACK',scope,'Numeric boundaries, independent instances and presentation-preserving state writes must be exercised'))
    return errors
