"""One source graph per native Prefab, with explicit graph and reference boundaries."""
from collections import defaultdict
from ..io import diagnostic
from ..sources.compiled import fail


def plan_prefabs(ir,components):
    groups=defaultdict(list)
    for node in ir['nodes']:groups[node['sourceId'].split('#')[0]].append(node)
    plans=[];gaps=[]
    for source,nodes in sorted(groups.items()):
        if any(n.get('sourceType')=='cc.Scene' for n in nodes):continue
        ids={n['sourceId'] for n in nodes};roots=[n for n in nodes if n['parent'] is None]
        if len(roots)!=1 or any(n['parent'] and n['parent'] not in ids for n in nodes):
            gaps.append(diagnostic('PREFAB_ROOT_BOUNDARY',source,'Source graph must have exactly one internal root',source));continue
        crossing=[c['sourceId'] for c in components if c.get('node') in ids and
                  any(c.get(k) and c[k] not in ids for k in ('target','content'))]
        if crossing:
            gaps.append(diagnostic('PREFAB_EXTERNAL_NODE_REFERENCE',source,'Native node references cross source graph: '+','.join(crossing),source));continue
        plans.append(dict(sourceId=source,root=roots[0]['sourceId'],nodes=sorted(ids),nodeCount=len(ids),
                          path=None,
                          nativeValidation='not_run'))
    return plans,gaps


def native_relationships(ir,prefabs,components=None):
    """Validate exact template/node correspondence and order assets before owners."""
    specs={p['sourceId']:p for p in prefabs};nodes={n['sourceId']:n for n in ir['nodes']};instances=[];seen=set()
    source_components={c['sourceId']:c for c in ir['components']};emitted={c['sourceId']:c for c in components}if components is not None else None
    if len(ir.get('prefabInstances',[]))>4096:fail('PREFAB_NATIVE_INSTANCE_BUDGET','$','At most4096 native instance relations per candidate')
    for link in ir.get('prefabInstances',[]):
        root=link['root'];template=link['template'];owner=root.split('#')[0]
        if root not in nodes or template not in specs:fail('PREFAB_NATIVE_TEMPLATE_MISSING',root,'Resolved template/root not available to native planner')
        if root in seen:fail('PREFAB_INSTANCE_ROOT_DUPLICATE',root,'Two instances claim the same root')
        seen.add(root)
        pairs=[dict(instanceObject=p['instanceObject'],templateObject=p['templateObject'])for p in link['objects']if p['templateObject']in specs[template]['nodes']]
        targets=[p['instanceObject']for p in pairs];source=[p['templateObject']for p in pairs]
        if (len(source)!=len(set(source))or set(source)!=set(specs[template]['nodes'])or len(targets)!=len(set(targets))or
                any(t not in nodes or t.split('#')[0]!=owner for t in targets)):
            fail('PREFAB_NATIVE_NODE_MAPPING',root,'Every template node needs one isolated instance node')
        mapping={p['templateObject']:p['instanceObject']for p in pairs}
        if mapping[specs[template]['root']]!=root:fail('PREFAB_NATIVE_ROOT_MAPPING',root,'Template root correspondence differs')
        children=[];mounted_nodes=set();additions=defaultdict(list)
        for group in link.get('mountedChildren',[]):
            parent=group['parent'];roots=list(group['roots']);members=[]
            if parent not in set(targets)|mounted_nodes or len(roots)!=len(set(roots)):fail('PREFAB_MOUNTED_CHILD_MAPPING',root,'Mounted parent/roots differ from the instance')
            def visit_child(sid):
                if sid not in nodes or sid in set(targets)|mounted_nodes or sid.split('#')[0]!=owner:fail('PREFAB_MOUNTED_CHILD_MAPPING',root,'Mounted subtree overlaps a template/another subtree or escapes its owner')
                mounted_nodes.add(sid);members.append(sid)
                for child in nodes[sid]['children']:
                    if nodes.get(child,{}).get('parent')!=sid:fail('PREFAB_MOUNTED_CHILD_MAPPING',root,'Mounted child/parent relation differs')
                    visit_child(child)
            for child in roots:
                if nodes.get(child,{}).get('parent')!=parent:fail('PREFAB_MOUNTED_CHILD_MAPPING',root,'Mounted root has another parent')
                visit_child(child)
            additions[parent].extend(roots);children.append(dict(parent=parent,roots=roots,nodes=members))
        mounted_components=[];mounted_ids=set()
        for item in link.get('mountedComponents',[]):
            sid=item['component'];component=source_components.get(sid)
            if sid in mounted_ids or not component or component.get('node')!=item['node']or item['node']not in set(targets)|mounted_nodes:
                fail('PREFAB_MOUNTED_COMPONENT_MAPPING',root,'Mounted component has no isolated source owner')
            projected=emitted.get(sid)if emitted is not None else None
            if emitted is not None and(not projected or not projected.get('convertible')):fail('PREFAB_MOUNTED_COMPONENT_UNSUPPORTED',sid,'Mounted source component needs a real target adapter')
            mounted_ids.add(sid);mounted_components.append(dict(node=item['node'],component=sid,sourceType=component['type'],nativeType=projected.get('nativeType')if projected else None))
        for p in pairs:
            original=nodes[p['templateObject']];instance=nodes[p['instanceObject']]
            if instance['children']!=[mapping[c]for c in original['children']]+additions[p['instanceObject']]:fail('PREFAB_NATIVE_TOPOLOGY',root,'Instance children differ from the template plus declared appended mounts')
            if original['parent']and instance['parent']!=mapping[original['parent']]:fail('PREFAB_NATIVE_TOPOLOGY',root,'Template parent correspondence differs')
        instances.append(dict(owner=owner,root=root,template=template,nodes=pairs,sourceInstanceFileId=link['sourceInstanceFileId'],mountedChildren=children,mountedComponents=mounted_components))
    roots={x['root']for x in instances}
    for item in instances:
        parent=nodes[item['root']]['parent'];item['outermost']=True
        while parent is not None:
            if parent in roots:item['outermost']=False;break
            parent=nodes[parent]['parent']
    dependencies={sid:sorted({x['template']for x in instances if x['owner']==sid})for sid in specs};ordered=[];active=set();done=set()
    def visit(sid):
        if sid in active:fail('PREFAB_NATIVE_CYCLE',sid,'Native asset dependency cycle')
        if sid in done:return
        if len(active)>=32:fail('PREFAB_NATIVE_DEPTH',sid,'Native template dependency depth exceeds32')
        active.add(sid)
        for dep in dependencies[sid]:visit(dep)
        active.remove(sid);done.add(sid);ordered.append(specs[sid])
    for sid in specs:visit(sid)
    return ordered,instances


def verify_native_relationships(expected,prefabs,actual,scope,template_guids=None,identity_kind='guid'):
    if not expected and not actual:return []
    rows=actual if isinstance(actual,list)else[];found={r.get('root'):r for r in rows};specs={p['sourceId']:p for p in prefabs};gaps=[]
    if len(found)!=len(rows)or set(found)!={x['root']for x in expected}:
        gaps.append(diagnostic('NATIVE_PREFAB_INSTANCE_SET',scope,'Saved native instance set differs from the source plan'))
    for instance in expected:
        row=found.get(instance['root'],{});template=specs[instance['template']]
        identity_key='templateUuid' if identity_kind=='uuid'else'templateGuid'
        root_id=row.get('templateRootFileId')
        valid_root=bool(root_id)and(type(root_id)is str if identity_kind=='uuid'else type(root_id)is int)
        if (row.get('nativeInstance')is not True or row.get('correspondingSourceVerified')is not True or row.get('nodeCorrespondenceVerified')is not True or row.get('templateUnchanged')is not True or
                row.get('templateSourceId')!=instance['template']or row.get('templatePath')!=template['path']or
                not row.get(identity_key)or not valid_root or row.get('nodeCount')!=len(instance['nodes'])):
            gaps.append(diagnostic('NATIVE_PREFAB_RELATION_NOT_VERIFIED',instance['root'],'Native source correspondence/shared template/save-reopen proof missing in '+scope))
        elif template_guids is not None and row[identity_key]!=template_guids.get(instance['template']):
            gaps.append(diagnostic('NATIVE_PREFAB_TEMPLATE_GUID',instance['root'],'Saved instance template GUID differs from the actual native asset'))
        mounts=instance.get('mountedChildren',[]);components=instance.get('mountedComponents',[])
        if mounts and(row.get('mountedChildrenVerified')is not True or row.get('mountedRootCount')!=sum(len(g['roots'])for g in mounts)or row.get('mountedNodeCount')!=sum(len(g['nodes'])for g in mounts)):
            gaps.append(diagnostic('NATIVE_PREFAB_MOUNTED_CHILDREN_NOT_VERIFIED',instance['root'],'Saved native added-node relationships are missing or differ'))
        if components and(row.get('mountedComponentsVerified')is not True or row.get('mountedComponentCount')!=len(components)):
            gaps.append(diagnostic('NATIVE_PREFAB_MOUNTED_COMPONENTS_NOT_VERIFIED',instance['root'],'Saved native added-component relationships are missing or differ'))
    return gaps
