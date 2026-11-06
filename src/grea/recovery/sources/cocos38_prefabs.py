"""Development-time Cocos 3.4.1/3.8.7 Prefab graph resolution with native links.

This module never runs in a Player. Expanded documents are validation/planning
material; native emitters must retain template instances rather than flatten them.
"""
import copy
from .compiled import fail,ParseError

MAX_OBJECTS=200_000
MAX_DEPTH=32


def pointer(value,objects,kind=None):
    if isinstance(value,dict)and set(value)=={'__id__'}and type(value['__id__'])is int:
        index=value['__id__']
        if not 0<=index<len(objects):fail('PREFAB_OBJECT_REFERENCE',str(index),'Object index outside source document')
        value=objects[index]
    if not isinstance(value,dict)or kind and value.get('__type__')!=kind:fail('PREFAB_OBJECT_TYPE',str(kind),'Expected exact source object type')
    return value


def root_index(asset,objects):
    root=asset['document']['root']
    if type(root)is not int or not 0<=root<len(objects)or not isinstance(objects[root],dict):fail('PREFAB_ROOT',asset['sourceId'],'Original root index/type is invalid')
    obj=objects[root]
    if obj.get('__type__')in ('cc.Prefab','cc.SceneAsset'):
        value=obj.get('data'if obj['__type__']=='cc.Prefab'else'scene')
        if not isinstance(value,dict)or set(value)!={'__id__'}:fail('PREFAB_ROOT',asset['sourceId'],'Expected original root object reference')
        root=value['__id__']
    if type(root)is not int or not 0<=root<len(objects)or objects[root].get('__type__')not in ('cc.Node','cc.Scene'):fail('PREFAB_ROOT',asset['sourceId'],'Root is not a source Node/Scene')
    return root


class Resolver:
    def __init__(self,assets,source_profile='cocos-3.8.7-bundle'):
        if source_profile not in ('cocos-3.4.1-bundle','cocos-3.8.7-bundle'):fail('PREFAB_SOURCE_PROFILE',source_profile,'Explicit audited source serialization required')
        self.source_profile=source_profile
        self.templates={};self.cache={};self.active=[]
        for asset in assets:
            if asset.get('kind')!='cc.Prefab'or not asset.get('document'):continue
            key=asset['key']
            if key in self.templates and self.templates[key]['document']!=asset['document']:fail('PREFAB_TEMPLATE_CONFLICT',key,'Conflicting source templates')
            self.templates.setdefault(key,asset)

    def resolve(self,asset):
        sid=asset['sourceId']
        if sid in self.cache:return copy.deepcopy(self.cache[sid])
        if sid in self.active:fail('PREFAB_DEPENDENCY_CYCLE',sid,'Source template dependency cycle')
        if len(self.active)>=MAX_DEPTH:fail('PREFAB_DEPTH',sid,'Template nesting exceeds limit')
        self.active.append(sid)
        try:result=self._resolve(asset);self.cache[sid]=copy.deepcopy(result);return result
        finally:self.active.pop()

    def _resolve(self,asset):
        objects=copy.deepcopy(asset['document']['instances']);original_count=len(objects)
        if len(objects)>MAX_OBJECTS:fail('PREFAB_OBJECT_BUDGET',asset['sourceId'],'Source object count exceeds limit')
        root=root_index(asset,objects);links=[];pending=[];identities={i:asset['sourceId']+'#'+str(i)for i in range(original_count)};expanded=set()
        inline_components={};shadowing=[]
        def intern_component(value,identity,reuse=False):
            if isinstance(value,dict)and set(value)=={'__id__'}:
                index=value['__id__']
                if type(index)is not int or not 0<=index<len(objects):fail('PREFAB_OBJECT_REFERENCE',asset['sourceId'],'Mounted component reference outside source document')
                return index
            if not isinstance(value,dict)or not isinstance(value.get('__type__'),str):fail('PREFAB_MOUNTED_COMPONENT',asset['sourceId'],'Expected a typed mounted component')
            owner=value.get('node');meta=value.get('__prefab');file_id=pointer(meta,objects,'cc.CompPrefabInfo').get('fileId')if meta else None
            key=(owner.get('__id__'),file_id)if isinstance(owner,dict)and set(owner)=={'__id__'}and file_id else ('inline-object',id(value))
            if reuse and key in inline_components:
                matches=[i for i in inline_components[key]if objects[i]==value]
                if len(matches)!=1:fail('PREFAB_MOUNTED_COMPONENT_CONFLICT',asset['sourceId'],'Mounted component payload does not identify one original component')
                return matches[0]
            index=len(objects);objects.append(value);identities[index]=identity;inline_components.setdefault(key,[]).append(index)
            if len(objects)>MAX_OBJECTS:fail('PREFAB_OBJECT_BUDGET',asset['sourceId'],'Mounted/inline component count exceeds limit')
            return index
        # Compiled 3.x graphs may embed components directly in _components.
        # Give those development objects stable source identities before cloning.
        i=-1
        while i+1<len(objects):
            i+=1
            obj=objects[i]
            if not isinstance(obj,dict)or obj.get('__type__')not in ('cc.Node','cc.Scene'):continue
            if self.source_profile=='cocos-3.4.1-bundle':
                for ordinal,value in enumerate(obj.get('_children',[])):
                    if isinstance(value,dict)and value.get('__type__')=='cc.Node':
                        dest=len(objects);objects.append(value);identities[dest]=identities[i]+'/children/'+str(ordinal)
                        obj['_children'][ordinal]={'__id__':dest}
                        if len(objects)>MAX_OBJECTS:fail('PREFAB_OBJECT_BUDGET',asset['sourceId'],'Inline child count exceeds limit')
            for ordinal,value in enumerate(obj.get('_components',[])):
                if isinstance(value,dict)and '__type__'in value:
                    dest=intern_component(value,asset['sourceId']+'#'+str(i)+'/components/'+str(ordinal))
                    obj['_components'][ordinal]={'__id__':dest}
        if len(objects)>MAX_OBJECTS:fail('PREFAB_OBJECT_BUDGET',asset['sourceId'],'Inline component count exceeds limit')
        def ref_index(value):
            if not isinstance(value,dict)or set(value)!={'__id__'}or type(value['__id__'])is not int or not 0<=value['__id__']<len(objects):fail('PREFAB_OBJECT_REFERENCE',asset['sourceId'],'Expected exact object reference')
            return value['__id__']
        def info(node):
            value=objects[node].get('_prefab')
            return pointer(value,objects,'cc.PrefabInfo')if value else None
        def local_id(value):
            target=pointer(value,objects,'cc.TargetInfo');path=target.get('localID')
            if not isinstance(path,list)or not path or len(path)>MAX_DEPTH or any(not isinstance(x,str)or not x for x in path):fail('PREFAB_TARGET_ID',asset['sourceId'],'Invalid source localID path')
            return path
        def target_map(node):
            mapping={};seen=set()
            def store(scope,key,value):
                if key in scope:
                    if self.source_profile!='cocos-3.4.1-bundle':fail('PREFAB_TARGET_DUPLICATE',key,'Ambiguous source localID')
                    # v3.4.1 generateTargetMap assigns in node/component/child
                    # traversal order. Preserve its last-write semantics while
                    # retaining every object and recording the collision.
                    row=dict(localID=key,replacement=identities.get(value)if type(value)is int else 'instance-scope')
                    if row not in shadowing:shadowing.append(row)
                scope[key]=value
            def walk(index,scope,is_root):
                if index in seen:fail('PREFAB_NODE_CYCLE',str(index),'Repeated/cyclic source child')
                seen.add(index);obj=objects[index];prefab=info(index)
                if prefab:
                    instance=pointer(prefab['instance'],objects,'cc.PrefabInstance')if prefab.get('instance')else None
                    if not is_root and instance:
                        name=instance.get('fileId')
                        if not isinstance(name,str)or not name:fail('PREFAB_TARGET_DUPLICATE',str(name),'Empty nested instance localID')
                        store(scope,name,{});scope=scope[name]
                    key=prefab.get('fileId')
                    if key:
                        store(scope,key,index)
                for value in obj.get('_components',[]):
                    component=ref_index(value);meta=objects[component].get('__prefab')
                    if meta:
                        key=pointer(meta,objects,'cc.CompPrefabInfo').get('fileId')
                        if key:
                            store(scope,key,component)
                for child in obj.get('_children',[]):walk(ref_index(child),scope,False)
            walk(node,mapping,True);return mapping
        def target(path,mapping):
            found=mapping
            for key in path:
                if not isinstance(found,dict)or key not in found:fail('PREFAB_TARGET_MISSING','/'.join(path),'Exact source localID unavailable')
                found=found[key]
            if type(found)is not int:fail('PREFAB_TARGET_TYPE','/'.join(path),'Target is an instance scope rather than object')
            return found
        def property_owner(index,path):
            if not isinstance(path,list)or not path or any(not isinstance(k,str)or not k or k in ('__proto__','prototype','constructor')for k in path):fail('PREFAB_PROPERTY_PATH',str(path),'Unsafe/empty source property path')
            owner=objects[index]
            for key in path[:-1]:
                if isinstance(owner,dict):owner=owner.get(key)
                elif isinstance(owner,list)and key.isdecimal()and int(key)<len(owner):owner=owner[int(key)]
                else:owner=None
                if owner is None:return None,path[-1]
            return owner,path[-1]
        def assign(index,path,value,origin):
            owner,key=property_owner(index,path)
            if owner is None:
                pending.append(dict(kind='constructor-default-owner-unavailable',target=identities[index],propertyPath=path,source=origin));return False
            if isinstance(owner,list):
                if key=='length':
                    if type(value)is not int or not 0<=value<=100000:fail('PREFAB_ARRAY_LENGTH',str(value),'Array length exceeds explicit integer subset')
                    del owner[value:];owner.extend([None]*(value-len(owner)))
                elif key.isdecimal()and int(key)<len(owner):owner[int(key)]=copy.deepcopy(value)
                else:fail('PREFAB_ARRAY_SLOT',key,'Source array slot outside defined length')
            elif isinstance(owner,dict)and '__value_type__'in owner:
                fields={0:['x','y'],1:['x','y','z'],2:['x','y','z','w'],3:['x','y','z','w'],4:['r','g','b','a'],5:['width','height']}.get(owner['__value_type__'])
                values=owner.get('values')
                if fields is None or key not in fields or not isinstance(values,list):fail('PREFAB_VALUE_PROPERTY',key,'Unsupported source ValueType property')
                if owner['__value_type__']==4 and len(values)==1 and type(values[0])is int:
                    values=[(values[0]>>shift)&255 for shift in (0,8,16,24)];owner['values']=values
                if len(values)!=len(fields):fail('PREFAB_VALUE_PROPERTY',key,'Invalid original ValueType arity')
                values[fields.index(key)]=copy.deepcopy(value)
            elif isinstance(owner,dict):owner[key]=copy.deepcopy(value)
            else:fail('PREFAB_PROPERTY_OWNER',str(path),'Unsupported source owner type')
            return True
        def expand(index,depth=0):
            if depth>MAX_DEPTH:fail('PREFAB_DEPTH',asset['sourceId'],'Node nesting exceeds limit')
            if index in expanded:return
            expanded.add(index);prefab=info(index);obj=objects[index]
            instance=pointer(prefab['instance'],objects,'cc.PrefabInstance')if prefab and prefab.get('instance')else None
            if instance:
                if instance.get('removedComponents'):fail('PREFAB_REMOVED_COMPONENT_DELTA',asset['sourceId'],'Removed components need an evidenced native adapter')
                template_ref=prefab.get('asset');key=template_ref.get('__uuid__')if isinstance(template_ref,dict)else None
                if key not in self.templates:fail('PREFAB_TEMPLATE_MISSING',str(key),'Exact original template not supplied')
                template=self.resolve(self.templates[key]);source=template['document']['instances'];template_root=root_index(template,source)
                if len(objects)+len(source)-1>MAX_OBJECTS:fail('PREFAB_OBJECT_BUDGET',asset['sourceId'],'Expanded validation object budget exceeded')
                mapping={template_root:index}
                for i in range(len(source)):
                    if i!=template_root:mapping[i]=len(objects);objects.append(None)
                path=instance.get('fileId')
                if not isinstance(path,str)or not path:fail('PREFAB_INSTANCE_ID',asset['sourceId'],'Original instance fileId required')
                def remap(value):
                    if isinstance(value,dict):
                        if set(value)=={'__id__'}:
                            if type(value['__id__'])is not int or value['__id__']not in mapping:fail('PREFAB_OBJECT_REFERENCE',str(value),'Invalid template object index')
                            return dict(__id__=mapping[value['__id__']])
                        return {k:remap(v)for k,v in value.items()}
                    if isinstance(value,list):return [remap(v)for v in value]
                    return value
                retained={k:copy.deepcopy(obj.get(k))for k in ('_parent','_id','_objFlags','__editorExtras__')}
                pairs=[]
                for i,record in enumerate(source):
                    dest=mapping[i];objects[dest]=remap(record)
                    if i!=template_root:identities[dest]=identities[index]+'/instance/'+path+'/'+template['objectIdentities'][str(i)]
                    pairs.append(dict(instanceObject=identities[dest],templateObject=template['objectIdentities'][str(i)]))
                objects[index].update(retained)
                cloned_info=info(index)
                if not cloned_info:fail('PREFAB_TEMPLATE_INFO',key,'Template root lacks native source PrefabInfo')
                cloned_info['instance']=copy.deepcopy(instance)
                # The template was fully expanded first, preserving inner delta order.
                for i in mapping.values():
                    if isinstance(objects[i],dict)and objects[i].get('__type__')=='cc.Node':expanded.add(i)
                mapped=target_map(index);mounted_children=[];mounted_components=[]
                # Match the source SDK's ordering: mounted children (including
                # their localID scopes), mounted components, then property deltas.
                for group in instance.get('mountedChildren')or[]:
                    group=pointer(group,objects,'cc.MountedChildrenInfo');where=local_id(group.get('targetInfo'));dest=target(where,mapped)
                    if objects[dest].get('__type__')!='cc.Node':fail('PREFAB_MOUNT_PARENT',asset['sourceId'],'Mounted children require a Node target')
                    children=[]
                    for child in group.get('nodes')or[]:
                        child_index=ref_index(child)
                        if objects[child_index].get('__type__')!='cc.Node'or child_index==dest:fail('PREFAB_MOUNT_CHILD',asset['sourceId'],'Expected a distinct mounted Node')
                        if child in objects[dest].get('_children',[]):fail('PREFAB_MOUNT_CHILD_DUPLICATE',asset['sourceId'],'Mounted child is already attached')
                        objects[dest].setdefault('_children',[]).append(dict(__id__=child_index));objects[child_index]['_parent']=dict(__id__=dest)
                        children.append(identities[child_index]);expand(child_index,depth+1)
                    mounted_children.append(dict(parent=identities[dest],localID=where,roots=children))
                    mapped=target_map(index)
                for group_index,group in enumerate(instance.get('mountedComponents')or[]):
                    group=pointer(group,objects,'cc.MountedComponentsInfo');where=local_id(group.get('targetInfo'));dest=target(where,mapped)
                    if objects[dest].get('__type__')!='cc.Node':fail('PREFAB_MOUNT_PARENT',asset['sourceId'],'Mounted components require a Node target')
                    for ordinal,component in enumerate(group.get('components')or[]):
                        component_index=intern_component(component,identities[index]+'/mounted-components/'+str(group_index)+'/'+str(ordinal),reuse=True)
                        if dict(__id__=component_index)in objects[dest].get('_components',[]):fail('PREFAB_MOUNT_COMPONENT_DUPLICATE',asset['sourceId'],'Mounted component is already attached')
                        objects[component_index]['node']=dict(__id__=dest);objects[dest].setdefault('_components',[]).append(dict(__id__=component_index))
                        mounted_components.append(dict(node=identities[dest],localID=where,component=identities[component_index],sourceType=objects[component_index]['__type__']))
                applied=[]
                for patch in instance.get('propertyOverrides')or[]:
                    override=pointer(patch,objects,'CCPropertyOverrideInfo');where=local_id(override.get('targetInfo'));dest=target(where,mapped);prop=override.get('propertyPath');value=override.get('value')
                    ok=assign(dest,prop,value,'propertyOverrides')
                    applied.append(dict(target=identities[dest],localID=where,propertyPath=prop,value=copy.deepcopy(value),appliedForValidation=ok))
                links.append(dict(root=identities[index],template=self.templates[key]['sourceId'],sourceInstanceFileId=path,objects=pairs,overrides=applied,mountedChildren=mounted_children,mountedComponents=mounted_components,nativeRelationship='required_not_emitted'))
                inverse={template['objectIdentities'][str(i)]:identities[mapping[i]]for i in range(len(source))}
                for nested in template['prefabInstances']:
                    cloned=copy.deepcopy(nested);cloned['root']=inverse[cloned['root']]
                    for pair in cloned['objects']:pair['instanceObject']=inverse[pair['instanceObject']]
                    for patch in cloned['overrides']:
                        patch['target']=inverse[patch['target']];patch['value']=remap(patch['value'])
                    for group in cloned.get('mountedChildren',[]):
                        group['parent']=inverse[group['parent']];group['roots']=[inverse[x]for x in group['roots']]
                    for component in cloned.get('mountedComponents',[]):
                        component['node']=inverse[component['node']];component['component']=inverse[component['component']]
                    links.append(cloned)
                for gap in template['pendingPrefabOverrides']:
                    pending.append(dict(copy.deepcopy(gap),target=inverse[gap['target']]))
            for child in objects[index].get('_children',[]):expand(ref_index(child),depth+1)
        expand(root)
        # TargetOverrideInfo redirects references to objects inside an instance.
        for index,obj in enumerate(objects):
            if not isinstance(obj,dict)or obj.get('__type__')not in ('cc.Node','cc.Scene'):continue
            meta=info(index)
            for item in meta.get('targetOverrides')or[] if meta else []:
                override=pointer(item,objects,'cc.TargetOverrideInfo')
                if not override.get('source')or not override.get('target')or not override.get('targetInfo'):
                    pending.append(dict(kind='source-target-override-skipped-missing-endpoint',target=identities[index],
                                        propertyPath=override.get('propertyPath'),source='targetOverrides'))
                    continue
                source_index=ref_index(override.get('source'))
                if override.get('sourceInfo'):source_index=target(local_id(override['sourceInfo']),target_map(source_index))
                target_root=ref_index(override.get('target'))
                try:dest=target(local_id(override.get('targetInfo')),target_map(target_root))
                except ParseError as error:
                    if error.code!='PREFAB_TARGET_MISSING':raise
                    pending.append(dict(kind='source-target-override-skipped-missing-local-id',target=identities[index],
                                        propertyPath=override.get('propertyPath'),source='targetOverrides'))
                    continue
                assign(source_index,override.get('propertyPath'),dict(__id__=dest),'targetOverrides')
        result=copy.deepcopy(asset);result['document']=dict(root=asset['document']['root'],instances=objects);result['objectIdentities']={str(i):identity for i,identity in identities.items()};result['prefabInstances']=links;result['pendingPrefabOverrides']=pending
        result['prefabResolution']=dict(kind='development-time-source-validation-only',sourceObjectCount=original_count,expandedObjectCount=len(objects),nativeInstancesRequired=bool(links),sourceRuntimeExecuted=False,localIdShadowing=shadowing)
        return result
