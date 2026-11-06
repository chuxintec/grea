import copy
import unittest
from monkey.sources.cocos38_prefabs import Resolver
from monkey.sources.compiled import ParseError


def ref(index):return {'__id__':index}
def target(*path):return dict(__type__='cc.TargetInfo',localID=list(path))
def patch(path,value,*local):return dict(__type__='CCPropertyOverrideInfo',targetInfo=target(*local),propertyPath=path,value=value)
def value(kind,*items):return dict(__value_type__=kind,values=list(items))
def info(file_id,instance=None,asset=None):
    return dict(__type__='cc.PrefabInfo',fileId=file_id,instance=instance,asset=asset or ref(0))
def instance(name,overrides):return dict(__type__='cc.PrefabInstance',fileId=name,propertyOverrides=overrides)
def prefab(key,nodes):return dict(key=key,sourceId='main:'+key,kind='cc.Prefab',document=dict(root=0,instances=[dict(__type__='cc.Prefab',data=ref(1)),*nodes]))
def leaf():
    return prefab('leaf',[
        dict(__type__='cc.Node',_name='Template',_prefab=info('root'),_children=[ref(2)],_lpos=value(1,0,0,0),_components=[
            dict(__type__='DomainState',node=ref(1),__prefab=dict(__type__='cc.CompPrefabInfo',fileId='state'),items=[1,2,3],selected=ref(2))]),
        dict(__type__='cc.Node',_name='Child',_parent=ref(1),_prefab=info('child'),_children=[])] )
def placeholder(parent,name,template,patches):
    return dict(__type__='cc.Node',_parent=ref(parent),_prefab=info('placeholder-'+name,instance(name,patches),{'__uuid__':template}))
def host():
    return prefab('host',[
        dict(__type__='cc.Node',_name='Host',_prefab=info('host-root'),_children=[ref(2),ref(3)]),
        placeholder(1,'left','leaf',[patch(['_name'],'Left','root'),patch(['items','length'],2,'state'),patch(['items','1'],9,'state')]),
        placeholder(1,'right','leaf',[patch(['_lpos'],value(1,20,0,0),'root')])])


class PrefabResolutionTests(unittest.TestCase):
    def test_341_inline_child_has_stable_identity_and_does_not_mutate_source(self):
        from monkey.sources.cocos34_graphs import resolved_graph
        a=prefab('inline',[dict(__type__='cc.Node',_name='Parent',_children=[dict(__type__='cc.Node',_name='Inline',_parent=ref(1),_prefab=info('inline'))])]);before=copy.deepcopy(a)
        ns,_,_,result=resolved_graph(a,Resolver([a],'cocos-3.4.1-bundle'))
        child=next(n for n in ns if n['name']=='Inline');self.assertEqual(child['sourceId'],'main:inline#1/children/0');self.assertEqual(child['parent'],'main:inline#1');self.assertEqual(a,before)

    def test_341_duplicate_component_id_uses_source_sdk_last_write_order(self):
        template=leaf();template['document']['instances'][1]['_components'].append(dict(__type__='DomainState',node=ref(1),__prefab=dict(__type__='cc.CompPrefabInfo',fileId='state'),items=[30,40,50],selected=ref(2)))
        parent=host();r=Resolver([template,parent],'cocos-3.4.1-bundle').resolve(parent);o=r['document']['instances'];left=o[2];first,second=[o[x['__id__']]for x in left['_components']]
        self.assertEqual(first['items'],[1,2,3]);self.assertEqual(second['items'],[30,9]);self.assertTrue(r['prefabResolution']['localIdShadowing'])
        with self.assertRaisesRegex(ParseError,'TARGET_DUPLICATE'):Resolver([template,parent]).resolve(parent)

    def test_mounted_widget_and_child_are_isolated_and_child_override_runs_after_mount(self):
        from monkey.sources.cocos34_graphs import resolved_graph
        from monkey.targets.prefabs import plan_prefabs,native_relationships,verify_native_relationships
        template=leaf();parent=host();child=dict(__type__='cc.Node',_name='Before',_parent=ref(2),_prefab=info('added-child'),_children=[],_components=[])
        parent['document']['instances'].append(child);record=parent['document']['instances'][2]['_prefab']['instance']
        record['mountedChildren']=[dict(__type__='cc.MountedChildrenInfo',targetInfo=target('root'),nodes=[ref(4)])]
        record['mountedComponents']=[dict(__type__='cc.MountedComponentsInfo',targetInfo=target('root'),components=[dict(__type__='cc.Widget',node=ref(2),_alignFlags=33,_right=12,_top=25,__prefab=dict(__type__='cc.CompPrefabInfo',fileId='added-widget'))])]
        record['propertyOverrides'].append(patch(['_name'],'After mount','added-child'));before=copy.deepcopy([template,parent])
        resolver=Resolver([template,parent],'cocos-3.4.1-bundle');result=resolver.resolve(parent);objects=result['document']['instances']
        self.assertEqual(objects[4]['_name'],'After mount');self.assertEqual(objects[4]['_parent'],ref(2));self.assertEqual(len(objects[2]['_children']),2);self.assertEqual(len(objects[3]['_children']),1)
        self.assertEqual(len(objects[2]['_components']),2);self.assertEqual(len(objects[3]['_components']),1);self.assertEqual([template,parent],before)
        left=next(x for x in result['prefabInstances']if x['root']=='main:host#2');self.assertEqual(left['mountedChildren'][0]['roots'],['main:host#4']);self.assertEqual(left['mountedComponents'][0]['sourceType'],'cc.Widget')
        nodes=[];components=[];links=[]
        for source in [template,parent]:
            ns,cs,gaps,resolved=resolved_graph(source,resolver);nodes+=ns;components+=cs;links+=resolved['prefabInstances']
        ir=dict(nodes=nodes,components=components,prefabInstances=links);plans,_=plan_prefabs(ir,components);ordered,instances=native_relationships(ir,plans)
        mounted=next(x for x in instances if x['root']=='main:host#2');self.assertEqual(mounted['mountedChildren'][0]['nodes'],['main:host#4']);self.assertEqual(len(mounted['mountedComponents']),1)
        proof=[dict(root=x['root'],templateSourceId=x['template'],templatePath=next(p['path']for p in plans if p['sourceId']==x['template']),templateGuid='g',templateRootFileId=1,nodeCount=len(x['nodes']),nativeInstance=True,correspondingSourceVerified=True,nodeCorrespondenceVerified=True,templateUnchanged=True)for x in instances]
        self.assertTrue(any(g['code']=='NATIVE_PREFAB_MOUNTED_CHILDREN_NOT_VERIFIED'for g in verify_native_relationships(instances,plans,proof,'saved')))
        for row in proof:row.update(mountedChildrenVerified=True,mountedComponentsVerified=True,mountedRootCount=int(row['root']=='main:host#2'),mountedNodeCount=int(row['root']=='main:host#2'),mountedComponentCount=int(row['root']=='main:host#2'))
        self.assertEqual(verify_native_relationships(instances,plans,proof,'saved'),[])

    def test_two_instances_keep_template_identity_isolation_and_internal_references(self):
        template=leaf();parent=host();before=copy.deepcopy([template,parent]);resolver=Resolver([template,parent]);result=resolver.resolve(parent)
        links=result['prefabInstances'];self.assertEqual(len(links),2)
        self.assertEqual({x['template']for x in links},{'main:leaf'})
        self.assertEqual(result['prefabResolution']['nativeInstancesRequired'],True)
        objects=result['document']['instances'];self.assertEqual(objects[2]['_name'],'Left');self.assertEqual(objects[3]['_name'],'Template')
        left_state=objects[objects[2]['_components'][0]['__id__']];right_state=objects[objects[3]['_components'][0]['__id__']]
        self.assertEqual(left_state['items'],[1,9]);self.assertEqual(right_state['items'],[1,2,3])
        self.assertEqual(left_state['selected'],objects[2]['_children'][0]);self.assertEqual(right_state['selected'],objects[3]['_children'][0]);self.assertNotEqual(left_state['selected'],right_state['selected'])
        self.assertEqual([template,parent],before)
        objects[2]['_name']='Manually changed validation';self.assertEqual(resolver.resolve(parent)['document']['instances'][2]['_name'],'Left')
        self.assertTrue(all(x['nativeRelationship']=='required_not_emitted'for x in links))

    def test_nested_local_id_scope_and_outer_target_override_redirect(self):
        template=leaf();middle=prefab('middle',[dict(__type__='cc.Node',_name='Middle',_prefab=info('middle-root'),_children=[ref(2)]),placeholder(1,'nested','leaf',[])])
        outer=prefab('outer',[dict(__type__='cc.Node',_name='Outer',_prefab=info('outer-root'),_children=[ref(2)],_components=[dict(__type__='DomainState',node=ref(1),selected=None)]),
            placeholder(1,'middle-instance','middle',[patch(['_name'],'Scoped Child','nested','child')])])
        outer['document']['instances'][1]['_prefab']['targetOverrides']=[dict(__type__='cc.TargetOverrideInfo',source=ref(1),target=ref(2),targetInfo=target('nested','child'),propertyPath=['selected'])]
        result=Resolver([template,middle,outer]).resolve(outer);objects=result['document']['instances'];dest=objects[1]['selected']['__id__']
        self.assertEqual(objects[dest]['_name'],'Scoped Child');self.assertEqual(len(result['prefabInstances']),2)
        self.assertEqual(len({x['root']for x in result['prefabInstances']}),2)

    def test_variant_root_keeps_outer_parent_and_overrides_without_self_dependency(self):
        template=leaf();variant=prefab('variant',[placeholder(0,'variant-instance','leaf',[patch(['_name'],'Variant','root')])]);variant['document']['instances'][1]['_parent']=None
        result=Resolver([template,variant]).resolve(variant)
        self.assertEqual(result['document']['instances'][1]['_name'],'Variant');self.assertIsNone(result['document']['instances'][1]['_parent']);self.assertEqual(result['prefabInstances'][0]['root'],'main:variant#1')

    def test_valuetype_field_patch_and_typed_normalized_ids_do_not_rewrite_text(self):
        from monkey.sources.cocos38_graphs import resolved_graph
        a=host();a['document']['instances'][2]['_prefab']['instance']['propertyOverrides'].extend([patch(['_lpos','x'],12,'root'),patch(['_name'],'main:leaf#1','child')])
        resolver=Resolver([leaf(),a]);nodes,components,gaps,resolved=resolved_graph(a,resolver)
        root=next(n for n in nodes if n['sourceId']=='main:host#2');self.assertEqual(root['position'],[12,0,0])
        child=next(n for n in nodes if n['parent']==root['sourceId']);self.assertEqual(child['name'],'main:leaf#1')
        self.assertTrue(child['sourceId'].startswith('main:host#2/instance/left/'))
        self.assertEqual(resolved['prefabInstances'][0]['objects'][0]['templateObject'],'main:leaf#0')

    def test_missing_cycle_duplicate_scope_and_mounted_changes_fail_explicitly(self):
        a=host()
        with self.assertRaisesRegex(ParseError,'TEMPLATE_MISSING'):Resolver([a]).resolve(a)
        b=prefab('cycle',[placeholder(0,'self','cycle',[])])
        with self.assertRaisesRegex(ParseError,'DEPENDENCY_CYCLE'):Resolver([b]).resolve(b)
        a=host();a['document']['instances'][2]['_prefab']['instance']['mountedChildren']=[ref(1)]
        with self.assertRaisesRegex(ParseError,'PREFAB_OBJECT_TYPE'):Resolver([leaf(),a]).resolve(a)
        a=host();a['document']['instances'][2]['_prefab']['instance']['propertyOverrides']=[patch(['_name'],'Unknown','missing')]
        with self.assertRaisesRegex(ParseError,'TARGET_MISSING'):Resolver([leaf(),a]).resolve(a)

    def test_unknown_constructor_owner_and_missing_reference_endpoint_are_recorded(self):
        a=host();a['document']['instances'][2]['_prefab']['instance']['propertyOverrides'].append(patch(['unavailable','length'],2,'state'))
        a['document']['instances'][1]['_prefab']['targetOverrides']=[dict(__type__='cc.TargetOverrideInfo',source=ref(1),targetInfo=target('root'),propertyPath=['external'])]
        result=Resolver([leaf(),a]).resolve(a)
        self.assertEqual({x['kind']for x in result['pendingPrefabOverrides']},{'constructor-default-owner-unavailable','source-target-override-skipped-missing-endpoint'})

    def test_native_plan_keeps_exact_pairs_and_rejects_missing_or_forged_proof(self):
        from monkey.sources.cocos38_graphs import resolved_graph
        from monkey.targets.prefabs import plan_prefabs,native_relationships,verify_native_relationships
        assets=[leaf(),host()];resolver=Resolver(assets);ir=dict(nodes=[],components=[],prefabInstances=[])
        for a in assets:
            nodes,components,_,resolved=resolved_graph(a,resolver)
            ir['nodes'].extend(nodes);ir['components'].extend(components);ir['prefabInstances'].extend(resolved['prefabInstances'])
        plans,_=plan_prefabs(ir,ir['components']);ordered,instances=native_relationships(ir,plans)
        self.assertEqual([p['sourceId']for p in ordered],['main:leaf','main:host']);self.assertEqual(len(instances),2)
        self.assertTrue(all(x['outermost']for x in instances))
        damaged=copy.deepcopy(ir);damaged['prefabInstances'][0]['objects']=[p for p in damaged['prefabInstances'][0]['objects']if p['templateObject']!='main:leaf#2']
        with self.assertRaisesRegex(ParseError,'NODE_MAPPING'):native_relationships(damaged,plans)
        self.assertTrue(verify_native_relationships(instances,plans,[],'scene'))
        spec=next(p for p in plans if p['sourceId']=='main:leaf');proof=[dict(root=x['root'],templateSourceId=x['template'],templatePath=spec['path'],templateGuid='native-guid',nativeInstance=True,correspondingSourceVerified=True,nodeCorrespondenceVerified=True,templateUnchanged=True,templateRootFileId=1,nodeCount=len(x['nodes']))for x in instances]
        self.assertEqual(verify_native_relationships(instances,plans,proof,'scene',{'main:leaf':'native-guid'}),[])
        proof[0]['templateGuid']='wrong-template'
        self.assertTrue(any(g['code']=='NATIVE_PREFAB_TEMPLATE_GUID'for g in verify_native_relationships(instances,plans,proof,'scene',{'main:leaf':'native-guid'})))
        proof[0]['templateGuid']='native-guid';proof[0]['templateUnchanged']=False
        self.assertTrue(any(g['code']=='NATIVE_PREFAB_RELATION_NOT_VERIFIED'for g in verify_native_relationships(instances,plans,proof,'scene')))
        for row in proof:
            row.update(templateUuid='native-uuid',templateRootFileId='creator-scoped-file-id',templateUnchanged=True)
            row.pop('templateGuid')
        self.assertEqual(verify_native_relationships(instances,plans,proof,'CreatorScene',{'main:leaf':'native-uuid'},'uuid'),[])
        proof[0]['templateUuid']='other-asset'
        self.assertTrue(verify_native_relationships(instances,plans,proof,'CreatorScene',{'main:leaf':'native-uuid'},'uuid'))


if __name__=='__main__':unittest.main()
