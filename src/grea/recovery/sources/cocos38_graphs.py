"""Version-proven Creator 3.8.7 static node/UI geometry, never a runtime shim.

Omitted defaults follow cocos-engine v3.8.7 Node/UITransform/UIOpacity/UIRenderer/
Label/Sprite. Nested Prefab instances/overrides require a separate adapter.
"""
import copy
from .compiled import fail

PROFILE='cocos-3.8.7-node-ui-v1'
BASELINE='https://github.com/cocos/cocos-engine/tree/v3.8.7/cocos'


def graph(asset,*,profile=PROFILE,version='3.8.7'):
    return _graph(asset,False,profile=profile,version=version)


def resolved_graph(asset,resolver,*,profile=PROFILE,version='3.8.7'):
    resolved=resolver.resolve(asset)
    nodes,components,gaps=_graph(resolved,True,profile=profile,version=version)
    namespace=asset['sourceId'];identities=resolved['objectIdentities']
    def source_id(value):
        if value is None or not value.startswith(namespace+'#'):return value
        index,separator,tail=value[len(namespace)+1:].partition('/')
        if index not in identities:fail('PREFAB_NORMALIZED_IDENTITY',value,'Resolved source object identity unavailable')
        return identities[index]+(separator+tail if separator else '')
    for node in nodes:
        for key in ('sourceId','parent'):node[key]=source_id(node[key])
        for key in ('children','components','sourceGeometryComponents'):node[key]=[source_id(x)for x in node[key]]
    for component in components:
        for key in ('sourceId','node','target','content'):
            if key in component:component[key]=source_id(component[key])
    for gap in gaps:gap['sourceId']=source_id(gap['sourceId'])
    live={n['sourceId']for n in nodes}
    resolved['prefabInstances']=[link for link in resolved['prefabInstances']if link['root']in live]
    return nodes,components,gaps,resolved


def _graph(asset,instances_resolved,*,profile=PROFILE,version='3.8.7'):
    from ..normalize import expand_nodes,ref,vector,node_ir,component_ir
    namespace=asset['sourceId']
    objects=asset['document']['instances']
    pending=list(objects)
    while pending:
        value=pending.pop()
        if isinstance(value,list):pending.extend(value)
        elif isinstance(value,dict):
            pending.extend(value.values())
            if not instances_resolved and (value.get('__type__')=='cc.PrefabInstance' or (value.get('__type__')=='cc.PrefabInfo' and any(value.get(k) for k in ('instance','targetOverrides','nestedPrefabInstanceRoots')))):
                fail('COCOS3_PREFAB_INSTANCE_PENDING',namespace,'Original nested Prefab instances/overrides are not flattened or guessed')
    entries=list(expand_nodes(objects,namespace))
    by_id={str(index):obj for index,obj in entries if isinstance(obj,dict)}
    node_components={}
    inline=[]
    gaps=[]
    def gap(index,message):gaps.append(dict(sourceId=namespace+'#'+str(index),message=message))
    def source_vector(value,kind,keys,default,field):
        if value is not None:
            if not isinstance(value,dict):fail('COCOS3_VALUE_TYPE',namespace,'Expected source vector for '+field)
            if '__value_type__'in value:
                if value['__value_type__']!=kind:fail('COCOS3_VALUE_TYPE',namespace,'Wrong tagged vector type for '+field)
            elif not all(k in value for k in keys):fail('COCOS3_VALUE_TYPE',namespace,'Incomplete named vector for '+field)
        return vector(value,keys,default)

    for index,obj in entries:
        if not isinstance(obj,dict)or obj.get('__type__')not in ('cc.Node','cc.Scene'):continue
        refs=[]
        for ordinal,value in enumerate(obj.get('_components',[])):
            if value is None:gap(index,'Null original component');continue
            if isinstance(value,dict)and '__type__'in value:
                cid=str(index)+'/components/'+str(ordinal);inline.append((cid,value));by_id[cid]=value
            elif isinstance(value,dict)and set(value)=={'__id__'}and type(value['__id__'])is int:
                cid=str(value['__id__'])
            else:fail('COCOS3_COMPONENT_REFERENCE',namespace,'Unsupported original component reference')
            if cid not in by_id:fail('COCOS3_COMPONENT_REFERENCE',namespace,'Component object unavailable')
            refs.append(cid)
        node_components[str(index)]=refs
    entries+=inline
    nodes=[];components=[];consumed=set()
    for index,obj in entries:
        if not isinstance(obj,dict)or obj.get('__type__')not in ('cc.Node','cc.Scene'):continue
        index=str(index);refs=node_components[index]
        values=[(cid,by_id[cid])for cid in refs]
        for cid,value in values:
            if ref(value.get('node'),namespace)!=namespace+'#'+index:
                fail('COCOS3_COMPONENT_OWNER',namespace,'Component owner differs from original node list')
        ui=[(cid,value)for cid,value in values if value.get('__type__')=='cc.UITransform']
        opacity=[(cid,value)for cid,value in values if value.get('__type__')=='cc.UIOpacity']
        renderers=[(cid,value)for cid,value in values if value.get('__type__')in ('cc.Sprite','cc.Label')]
        if len(ui)>1 or len(opacity)>1 or len(renderers)>1:
            fail('COCOS3_UI_COMPONENT_AMBIGUOUS',namespace,'One UITransform/UIOpacity/renderer per node is supported')
        def vec(field,kind,keys,default):return source_vector(obj.get(field),kind,keys,default,field)
        position=vec('_lpos',1,['x','y','z'],[0,0,0]);rotation=vec('_lrot',3,['x','y','z','w'],[0,0,0,1]);scale=vec('_lscale',1,['x','y','z'],[1,1,1])
        if abs(sum(v*v for v in rotation)-1)>.0001:fail('COCOS3_ROTATION',namespace,'Unnormalized source quaternion')
        size=[0,0];anchor=[.5,.5];alpha=255
        geometry=[]
        for cid,value in ui:
            if value.get('_enabled',True) is not True and version!='3.4.1':fail('COCOS3_UI_TRANSFORM_DISABLED',namespace,'Disabled source UITransform needs a separate lifecycle profile')
            if type(value.get('_enabled',True))is not bool:fail('COCOS3_UI_TRANSFORM_DISABLED',namespace,'Expected boolean source UITransform state')
            size=source_vector(value.get('_contentSize'),5,['width','height'],[100,100],'_contentSize');anchor=source_vector(value.get('_anchorPoint'),0,['x','y'],[.5,.5],'_anchorPoint')
            consumed.add(cid);geometry.append(namespace+'#'+cid)
            for key in value:
                if key not in ('__type__','_name','_objFlags','__prefab','_id','_enabled','node','_contentSize','_anchorPoint'):
                    gap(cid,'Unsupported UITransform field: '+key)
        for cid,value in opacity:
            alpha=value.get('_opacity',255) if value.get('_enabled',True) else 255
            if type(alpha)not in (int,float)or not 0<=alpha<=255:fail('COCOS3_OPACITY',namespace,'Opacity outside source range')
            consumed.add(cid);geometry.append(namespace+'#'+cid)
        color=source_vector(renderers[0][1].get('_color')if renderers else None,4,['r','g','b','a'],[255]*4,'_color')
        if any(type(v)not in(int,float)or not 0<=v<=255 for v in color):fail('COCOS3_COLOR',namespace,'Renderer color outside source range')
        layer=obj.get('_layer',1<<30)
        if type(layer)is not int or not 0<=layer<=0xffffffff:fail('COCOS3_LAYER',namespace,'Expected source uint32 layer bits')
        known={'__type__','_name','_objFlags','_parent','_children','_active','_components','_prefab','_lpos','_lrot','_lscale','_mobility','_layer','_euler','_id','__editorExtras__','_globals','autoReleaseAssets','_autoReleaseAssets'}
        for key in obj:
            if key not in known:gap(index,'Unsupported node field: '+key)
        projected=dict(__type__=obj['__type__'],_name=obj.get('_name','New Node'),_parent=obj.get('_parent'),_children=obj.get('_children',[]),_active=obj.get('_active',True),
                       _trs=position+rotation+scale,_contentSize=dict(width=size[0],height=size[1]),_anchorPoint=dict(x=anchor[0],y=anchor[1]),
                       _color=dict(zip(['r','g','b','a'],color)),_opacity=alpha,_components=[{'__sourceId__':namespace+'#'+cid}for cid in refs if cid not in consumed])
        node,_=node_ir(namespace,index,projected)
        if obj['__type__']=='cc.Scene':node['sourceType']='cc.Scene';gap(index,'Source Scene globals/cameras remain pending; static hierarchy only')
        node.update(sourceGeometryProfile=profile,sourceLayer=layer,sourceGeometryComponents=geometry)
        if ui and not ui[0][1].get('_enabled',True):node['sourceUITransformEnabled']=False
        nodes.append(node)
    metadata={'cc.Prefab','cc.SceneAsset','cc.Node','cc.Scene','cc.PrefabInfo','cc.CompPrefabInfo','cc.TargetInfo','cc.PrefabInstance','CCPropertyOverrideInfo','cc.TargetOverrideInfo','cc.MountedChildrenInfo','cc.MountedComponentsInfo'}
    for index,obj in entries:
        index=str(index)
        if not isinstance(obj,dict)or obj.get('__type__')in metadata or index in consumed:continue
        typ=obj.get('__type__')
        if not typ:continue
        sid=namespace+'#'+index
        if typ not in ('cc.Sprite','cc.Label','cc.Widget','cc.Layout'):
            components.append(dict(sourceId=sid,type=typ,node=ref(obj.get('node'),namespace),enabled=obj.get('_enabled',True),materials=[],supported=False,sourceData=copy.deepcopy(obj)))
            gap(index,'Creator '+version+' component requires a separate semantic adapter: '+typ);continue
        value=copy.deepcopy(obj)
        value.pop('__prefab',None);value.pop('_color',None)
        value['_materials']=[obj['_customMaterial']]if obj.get('_customMaterial')else []
        value.pop('_customMaterial',None)
        if typ=='cc.Label':
            value['_N$file']=value.pop('_font',None)
            value['_string']=value.get('_string','label')
            value['_horizontalAlign']=value.get('_horizontalAlign',1);value['_verticalAlign']=value.get('_verticalAlign',1)
            value['_styleFlags']=sum(bit for field,bit in (('_isBold',1),('_isItalic',2),('_isUnderline',4))if value.pop(field,False))
            for field in ('_actualFontSize','_enableOutline','_outlineWidth','_outlineColor','_underlineHeight'):
                value.pop(field,None)
            if obj.get('_enableShadow'):gap(index,'Label shadow requires a separate adapter')
            for field in ('_enableShadow','_shadowColor','_shadowOffset','_shadowBlur'):value.pop(field,None)
        elif typ=='cc.Sprite':
            value['_sizeMode']=value.get('_sizeMode',1)
            if obj.get('_useGrayscale'):gap(index,'Sprite grayscale shader requires a separate adapter')
            value.pop('_useGrayscale',None)
        elif typ=='cc.Widget':
            value.pop('_materials',None)
            value['alignMode']=value.pop('_alignMode',1)
            value.pop('_lockFlags',None)
        elif typ=='cc.Layout':
            value.pop('_materials',None)
            aliases={'_layoutType':'_N$layoutType','_resizeMode':'_resize'}
            aliases.update({name:'_N$'+name[1:]for name in ('_spacingX','_spacingY','_paddingLeft','_paddingBottom','_paddingRight','_paddingTop','_horizontalDirection','_verticalDirection','_startAxis')})
            for src,dest in aliases.items():
                if src in value:value[dest]=value.pop(src)
            value.setdefault('_N$verticalDirection',1)
            value.setdefault('_resize',0)
            value['_cellSize']=dict(zip(['width','height'],source_vector(value.get('_cellSize'),5,['width','height'],[40,40],'Layout._cellSize')))
        component,missing=component_ir(namespace,index,value)
        component['sourceGeometryProfile']=profile
        if obj.get('_enableShadow') or obj.get('_useGrayscale'):component['supported']=False
        components.append(component)
        for message in missing:gap(index,message)
        if typ=='cc.Label'and obj.get('_enableOutline',False):
            outline=dict(__type__='cc.LabelOutline',node=obj.get('node'),_enabled=obj.get('_enabled',True),_width=obj.get('_outlineWidth',2),_color=obj.get('_outlineColor',dict(r=0,g=0,b=0,a=255)))
            effect,missing=component_ir(namespace,index+'/outline',outline);components.append(effect)
            for message in missing:gap(index,message)
    # Prefab.data / SceneAsset.scene is the live hierarchy. Compiled object
    # tables may also retain detached records (including stale _parent links);
    # instantiating the asset does not attach those records to its tree.
    definition=objects[0]if objects and isinstance(objects[0],dict)else{}
    root=definition.get('data')if definition.get('__type__')=='cc.Prefab'else definition.get('scene')if definition.get('__type__')=='cc.SceneAsset'else None
    if isinstance(root,dict)and set(root)=={'__id__'}:
        root_id=ref(root,namespace);by_node={n['sourceId']:n for n in nodes};live=set();pending=[root_id]
        if root_id not in by_node:fail('COCOS3_ROOT_NODE_MISSING',namespace,'Asset root does not identify an available source Node/Scene')
        while pending:
            sid=pending.pop()
            if sid in live:continue
            live.add(sid)
            if sid in by_node:pending.extend(by_node[sid]['children'])
        for n in nodes:
            if n['sourceId']not in live:gaps.append(dict(sourceId=n['sourceId'],message='Detached serialized node is outside the asset root hierarchy; original record retained in source evidence'))
        nodes=[n for n in nodes if n['sourceId']in live]
        components=[c for c in components if c.get('node')in live]
    return nodes,components,gaps
