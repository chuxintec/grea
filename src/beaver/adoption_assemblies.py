"""Conservative, non-loading managed SDK compatibility checks before adoption.

No policy grants permission to rewrite an existing DLL, importer or MonoScript.
Only exact, explicit and demonstrably disjoint Editor/Player pairs are accepted.
"""
import re
from .io import sha,encoded
from .errors import fail
from .owned_fs import RootReader
from .managed_metadata import inspect_managed


def importer_roles(raw):
    """Recognize the small serialized PluginImporter subset we can prove.

    Missing/default importers, constraints, override maps and platform-specific
    variants remain unknown; a filename or an Editor directory is not proof.
    """
    text=raw.decode('utf-8')
    if 'PluginImporter:' not in text or re.search(r'^  defineConstraints:\s*(?!\[\])\S',text,re.M):return None
    if re.search(r'^  (?:defineConstraints|externalObjects):\s*$',text,re.M):return None
    if re.search(r'^  externalObjects:\s*(?!\{\})\S',text,re.M):return None
    match=re.search(r'^  platformData:\s*\n(.*?)(?=^  [A-Za-z]|\Z)',text,re.M|re.S)
    if not match:return None
    body=match.group(1);entries={}
    if re.search(r'^  - first:',body,re.M):
        blocks=re.split(r'^  - first:\s*\n',body,flags=re.M)[1:]
        if not blocks:return None
        for b in blocks:
            m=re.match(r"      (Any|Editor):[^\n]*\n    second:\s*\n      enabled: ([01])\s*\n(.*)\Z",b,re.S)
            if not m or m[1] in entries:return None
            entries[m[1]]=(int(m[2]),m[3])
    else:
        # Unity 6000 can serialize platformData as a keyed map.
        blocks=list(re.finditer(r'^    (Any|Editor):\s*\n(.*?)(?=^    \S|\Z)',body,re.M|re.S))
        if not blocks or ''.join(x[0] for x in blocks)!=body:return None
        for m in blocks:
            e=re.search(r'^      enabled: ([01])\s*$',m[2],re.M)
            if not e or m[1] in entries:return None
            entries[m[1]]=(int(e[1]),m[2])
    if set(entries)!={'Any','Editor'}:return None
    any_on,any_settings=entries['Any'];editor_on,editor_settings=entries['Editor']
    # Do not treat CPU/OS constrained Editor imports as all-Editor proof.
    for key,expected in [('CPU','AnyCPU'),('OS','AnyOS')]:
        values=re.findall(r'^\s+'+key+r':\s*(\S+)\s*$',editor_settings,re.M)
        if values and values!=[expected]:return None
    exclusions=re.findall(r'^\s+Exclude ([^:]+):\s*([01])\s*$',any_settings,re.M)
    if any(k!='Editor' for k,v in exclusions) or len(exclusions)>1:return None
    editor=bool(editor_on) if not any_on else not (exclusions and exclusions[0][1]=='1')
    if any_on and bool(editor_on)!=editor:return None
    roles=[]
    if editor:roles.append('editor')
    if any_on:roles.append('player')
    return roles


def _policy(manifest):
    policy=manifest.get('managedAssemblyPolicy')
    if policy is None:return {},'reject-ambiguous-sdk'
    if not isinstance(policy,dict) or set(policy)!={'schemaVersion','strategy','assemblies'} or type(policy['schemaVersion']) is not int or policy['schemaVersion']!=1 or policy['strategy']!='explicit-disjoint-role-pairs' or not isinstance(policy['assemblies'],list):
        fail('ADOPT_ASSEMBLY_POLICY','managedAssemblyPolicy','Expected exact schema1 explicit-disjoint-role-pairs policy')
    pins={}
    for row in policy['assemblies']:
        if not isinstance(row,dict) or set(row)!={'path','guid','sha256','metaSha256','role'}:fail('ADOPT_ASSEMBLY_POLICY','assemblies','Invalid assembly pin')
        p=row['path']
        if not isinstance(p,str) or not p.startswith('Assets/') or not p.endswith('.dll') or any(x in ('','.','..') for x in p.split('/')) or '\\' in p or ':' in p:fail('ADOPT_ASSEMBLY_POLICY',str(p),'Expected canonical Assets DLL path')
        if p in pins or row['role'] not in ('editor-only','player-only') or not re.fullmatch('[a-f0-9]{32}',str(row['guid'])) or any(not re.fullmatch('[a-f0-9]{64}',str(row[k])) for k in ('sha256','metaSha256')):fail('ADOPT_ASSEMBLY_POLICY',p,'Duplicate/invalid immutable role pin')
        pins[p]=row
    return pins,policy['strategy']


def inspect_compatibility(incoming,target,manifest,desired,current,operations,profile):
    if not profile.startswith('unity-'):return dict(status='not-applicable',assemblies=[],conflicts=[])
    pins,strategy=_policy(manifest)
    dll=lambda u:u['path'].lower().endswith('.dll')
    relevant={u['path'] for u in desired.values() if dll(u)}
    if not relevant:
        if pins:fail('ADOPT_ASSEMBLY_POLICY','assemblies','Unused assembly pins')
        return dict(status='not-applicable',assemblies=[],conflicts=[])
    post={u['path']:(u,target) for u in current.values() if dll(u)}
    touched=set();conflicts=[]
    def conflict(reason,paths,detail):conflicts.append(dict(identity='managed-sdk:'+','.join(paths),reason=reason,current=paths,desired=detail))
    for op in operations:
        if not dll(op['after']):continue
        touched.add(op['target'])
        if op.get('before'):
            if op['before']['file']['sha256']!=op['after']['file']['sha256'] or op['before'].get('meta')!=op['after'].get('meta'):
                conflict('managed-sdk-existing-replacement-needs-native-migration',[op['source'],op['target']],'Existing compiler/importer bytes cannot be replaced by this policy')
            post.pop(op['source'],None)
        post[op['target']]=(op['after'],incoming)
    relevant|=touched
    if len(post)>128:fail('ADOPT_ASSEMBLY_BUDGET','Assets','At most 128 managed DLLs may be checked in one adoption')
    rows=[];used=set()
    with RootReader(incoming) as src,RootReader(target) as dst:
        for path,(u,root) in sorted(post.items()):
            view=src if root==incoming else dst
            row=dict(path=path,guid=u['guid'],sha256=u['file']['sha256'],metaSha256=(u.get('meta') or {}).get('sha256'),roles=None)
            try:
                raw=view.read(path,max_bytes=64*1024**2)
                if sha(raw)!=row['sha256']:raise ValueError('DLL changed during preview')
                info=inspect_managed(raw);row.update(info)
                if not u.get('meta'):raise ValueError('Missing importer metadata')
                meta=view.read(path+'.meta')
                if sha(meta)!=row['metaSha256']:raise ValueError('Importer changed during preview')
                row['roles']=importer_roles(meta)
                if row['roles'] is None:row['unknown']='Importer roles are not proven by supported exact serialization'
            except (ValueError,UnicodeError) as e:row['unknown']=str(e)
            pin=pins.get(path)
            if pin:
                used.add(path);role=['editor'] if pin['role']=='editor-only' else ['player']
                row['explicitRolePin']=all(row[k]==pin[k] for k in ('guid','sha256','metaSha256')) and row['roles']==role
                if not row['explicitRolePin']:conflict('managed-sdk-role-pin-mismatch',[path],'Actual bytes/GUID/importer role differ from policy')
            rows.append(row)
    if used!=set(pins):fail('ADOPT_ASSEMBLY_POLICY','assemblies','Pins must name actual post-adoption assemblies')
    if sum(len(r.get('types',[])) for r in rows)>100000 or sum(sum(len(t) for t in r.get('types',[])) for r in rows)>16*1024**2:
        fail('ADOPT_ASSEMBLY_BUDGET','Assets','Managed type inventory exceeds bounded comparison budget')
    active_names={r.get('name','').casefold() for r in rows if r['path'] in relevant}
    for r in rows:
        if 'unknown' in r and (r['path'] in relevant or not r.get('name') or r['name'].casefold() in active_names):
            conflict('managed-sdk-identity-or-role-unknown',[r['path']],r['unknown'])
    for i,a in enumerate(rows):
        for b in rows[i+1:]:
            if not ({a['path'],b['path']}&relevant):continue
            if not a.get('name') or not b.get('name'):continue
            same=a['name'].casefold()==b['name'].casefold()
            overlap=set(a.get('publicTypes',[]))&set(b.get('publicTypes',[]))
            if not same and not overlap:continue
            paths=[a['path'],b['path']]
            # Even disjoint compilation domains do not prove that historical
            # serialized MonoScript GUID/localIDs still resolve. Installing a
            # new counterpart alongside any retained SDK requires native proof
            # and migration, which this static policy cannot authorize.
            if (a['path'] in touched)!=(b['path'] in touched):
                conflict('managed-sdk-existing-identity-needs-native-migration',paths,'Cannot add a second identity alongside a retained SDK, even with disjoint importer roles')
                continue
            if a['roles'] is None or b['roles'] is None or set(a['roles'])&set(b['roles']):
                conflict('managed-sdk-assembly-or-type-scope-collision',paths,dict(assemblyNames=[a['name'],b['name']],overlapTypes=sorted(overlap)[:32]));continue
            if not same or not a.get('explicitRolePin') or not b.get('explicitRolePin'):
                conflict('managed-sdk-explicit-role-pair-required',paths,'Only an exact same-assembly disjoint Editor/Player pair can be explicitly accepted')
    for row in rows:
        types=row.pop('types',[]);row['typeCount']=len(types);row['typeNamesSha256']=sha(encoded(sorted(types)))
        public=row.pop('publicTypes',[]);row['publicTypeCount']=len(public);row['publicTypeNamesSha256']=sha(encoded(sorted(public)))
    return dict(status='blocked' if conflicts else 'preflight-verified',strategy=strategy,assemblies=rows,conflicts=conflicts,boundary='Assets managed DLL metadata/importer proof only; no package-cache inventory, MonoScript localID/GUID migration or native compilation acceptance')
