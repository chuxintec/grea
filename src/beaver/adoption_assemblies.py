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
    match=re.search(r'^  platformData:\s*\n(.*?)(?=^  [A-Za-z][A-Za-z0-9]*:\s|\Z)',text,re.M|re.S)
    if not match:return None
    body=match.group(1);entries={}
    if re.search(r'^  - first:',body,re.M):
        blocks=re.split(r'^  - first:\s*\n',body,flags=re.M)[1:]
        if not blocks:return None
        for b in blocks:
            m=re.match(r"      ([A-Za-z][A-Za-z0-9]*):[^\n]*\n    second:\s*\n      enabled: ([01])\s*\n(.*)\Z",b,re.S)
            if not m or m[1] in entries:return None
            entries[m[1]]=(int(m[2]),m[3])
    else:
        # Unity 6000 can serialize platformData as a keyed map.
        headers=list(re.finditer(r'^    ([A-Za-z][A-Za-z0-9]*):[^\n]*\n',body,re.M))
        if not headers:return None
        if ''.join(body[h.start():headers[i+1].start() if i+1<len(headers) else len(body)] for i,h in enumerate(headers))!=body:return None
        for i,h in enumerate(headers):
            section=body[h.end():headers[i+1].start() if i+1<len(headers) else len(body)]
            enabled=re.search(r'^      enabled: ([01])\s*$',section,re.M)
            if not enabled or h[1] in entries:return None
            entries[h[1]]=(int(enabled[1]),re.sub(r'^\s*enabled:\s*[01]\s*$','',section,flags=re.M))
    if not {'Any','Editor'}<=set(entries):return None
    # Additional serialized platforms are allowed only when explicitly disabled;
    # an active unmodeled platform can never be silently treated as Player.
    if any(enabled for key,(enabled,_settings) in entries.items() if key not in ('Any','Editor')):return None
    any_on,any_settings=entries['Any'];editor_on,editor_settings=entries['Editor']
    # Recognize only default CPU/OS settings; architecture and platform-limited
    # imports cannot be summarized as a generic Editor/Player role.
    allowed_settings={'CPU':{'AnyCPU'},'OS':{'AnyOS'},'DefaultValueInitialized':{'true','false'},'Exclude Editor':{'0','1'}}
    for settings in (any_settings,editor_settings):
        settings=re.sub(r'^\s*settings:\s*(?:\{\})?\s*$','',settings,flags=re.M)
        seen={}
        for key,value in re.findall(r'^\s+([^:\n]+):\s*(\S+)\s*$',settings,re.M):
            key=key.strip();value=value.strip()
            if key not in allowed_settings or value not in allowed_settings[key] or key in seen:return None
            seen[key]=value
    exclusions=re.findall(r'^\s+Exclude ([^:]+):\s*([01])\s*$',any_settings,re.M)
    if any(k!='Editor' for k,v in exclusions) or len(exclusions)>1:return None
    editor=bool(editor_on) if not any_on else not (exclusions and exclusions[0][1]=='1')
    if any_on and bool(editor_on)!=editor:return None
    roles=[]
    if editor:roles.append('editor')
    if any_on:roles.append('player')
    return roles


def _policy(manifest, sdk_migration=None):
    policy=manifest.get('managedAssemblyPolicy')
    pins={};strategy='reject-ambiguous-sdk'
    if policy is not None:
        if not isinstance(policy,dict) or set(policy)!={'schemaVersion','strategy','assemblies'} or type(policy['schemaVersion']) is not int or policy['schemaVersion']!=1 or policy['strategy']!='explicit-disjoint-role-pairs' or not isinstance(policy['assemblies'],list):
            fail('ADOPT_ASSEMBLY_POLICY','managedAssemblyPolicy','Expected exact schema1 explicit-disjoint-role-pairs policy')
        strategy=policy['strategy']
        for row in policy['assemblies']:
            if not isinstance(row,dict) or set(row)!={'path','guid','sha256','metaSha256','role'}:fail('ADOPT_ASSEMBLY_POLICY','assemblies','Invalid assembly pin')
            p=row['path']
            if not isinstance(p,str) or not p.startswith('Assets/') or not p.endswith('.dll') or any(x in ('','.','..') for x in p.split('/')) or '\\' in p or ':' in p:fail('ADOPT_ASSEMBLY_POLICY',str(p),'Expected canonical Assets DLL path')
            if p in pins or row['role'] not in ('editor-only','player-only') or not re.fullmatch('[a-f0-9]{32}',str(row['guid'])) or any(not re.fullmatch('[a-f0-9]{64}',str(row[k])) for k in ('sha256','metaSha256')):fail('ADOPT_ASSEMBLY_POLICY',p,'Duplicate/invalid immutable role pin')
            pins[p]=dict(row)
    if sdk_migration:
        for pair in sdk_migration['assemblies']:
            for variant in pair['variants']:
                p=variant['path'];row=dict(path=p,guid=variant['after']['guid'],sha256=variant['after']['sha256'],metaSha256=variant['after']['metaSha256'],role='editor-only' if variant['domain']=='editor' else 'player-only',pairRole=pair['role'])
                if p in pins and any(pins[p].get(k)!=row[k] for k in ('guid','sha256','metaSha256','role')):
                    fail('ADOPT_ASSEMBLY_POLICY',p,'Producer pin disagrees with consumer-authorized SDK migration')
                pins[p]=row
        strategy='consumer-explicit-canonical-role-migration'
    return pins,strategy


def inspect_compatibility(incoming,target,manifest,desired,current,operations,profile,sdk_migration=None):
    if not profile.startswith('unity-'):return dict(status='not-applicable',assemblies=[],conflicts=[])
    pins,strategy=_policy(manifest,sdk_migration)
    retained_block=(sdk_migration or {}).get('retainedInactiveAssemblies')
    retained_rows=(retained_block or {}).get('assemblies',[])
    retained_pins={row['path']:row for row in retained_rows}
    if retained_block and retained_block.get('policy')!='preserve-exact-disabled-target-assemblies':
        fail('ADOPT_ASSEMBLY_POLICY','retainedInactiveAssemblies','Unknown explicit inactive retention policy')
    dll=lambda u:u['path'].lower().endswith('.dll')
    relevant={u['path'] for u in desired.values() if dll(u)}
    if not relevant:
        if pins:fail('ADOPT_ASSEMBLY_POLICY','assemblies','Unused assembly pins')
        return dict(status='not-applicable',assemblies=[],conflicts=[])
    post={u['path']:(u,target) for u in current.values() if dll(u)}
    touched=set();conflicts=[]
    sdk_variants={v['path']:v for pair in (sdk_migration or {}).get('assemblies',[]) for v in pair['variants']}
    def conflict(reason,paths,detail):conflicts.append(dict(identity='managed-sdk:'+','.join(paths),reason=reason,current=paths,desired=detail))
    for op in operations:
        if not dll(op['after']):continue
        touched.add(op['target'])
        if op.get('before'):
            approved=sdk_variants.get(op['target'])
            authorized_replace=approved and approved['action']=='replace-preserve-guid' and op.get('sdkMigrationRole')==approved['pairRole'] and op.get('sdkDomain')==approved['domain']
            if (op['before']['file']['sha256']!=op['after']['file']['sha256'] or op['before'].get('meta')!=op['after'].get('meta')) and not authorized_replace:
                conflict('managed-sdk-existing-replacement-needs-native-migration',[op['source'],op['target']],'Existing compiler/importer bytes cannot be replaced by this policy')
            post.pop(op['source'],None)
        post[op['target']]=(op['after'],incoming)
    relevant|=touched
    if len(post)>128:fail('ADOPT_ASSEMBLY_BUDGET','Assets','At most 128 managed DLLs may be checked in one adoption')
    rows=[];used=set();used_retained=set()
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
            inactive=retained_pins.get(path)
            if inactive:
                used_retained.add(path)
                row['explicitInactivePin']=(root==target and path not in touched and
                    all(row[k]==inactive[k] for k in ('path','guid','sha256','metaSha256','moduleVersionId','roles')) and
                    row.get('name','').casefold()==inactive['assemblyName'].casefold())
                if not row['explicitInactivePin']:
                    conflict('managed-sdk-retained-inactive-pin-mismatch',[path],'Retained inactive DLL is changed, touched, or not fully disabled')
            rows.append(row)
    if used!=set(pins):fail('ADOPT_ASSEMBLY_POLICY','assemblies','Pins must name actual post-adoption assemblies')
    if used_retained!=set(retained_pins):fail('ADOPT_ASSEMBLY_POLICY','retainedInactiveAssemblies','Pins must name actual unchanged target assemblies')
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
            if a.get('explicitInactivePin') or b.get('explicitInactivePin'):
                both_inactive=a.get('explicitInactivePin') and b.get('explicitInactivePin')
                inactive=a if a.get('explicitInactivePin') else b
                active=b if inactive is a else a
                paired_active=active['path'] in sdk_variants and active.get('explicitRolePin')
                if both_inactive or paired_active:
                    continue
            # Even disjoint compilation domains do not prove that historical
            # serialized MonoScript GUID/localIDs still resolve. Installing a
            # new counterpart alongside any retained SDK requires native proof
            # and migration, which this static policy cannot authorize.
            if (a['path'] in touched)!=(b['path'] in touched):
                left_role=pins.get(a['path'],{}).get('pairRole');right_role=pins.get(b['path'],{}).get('pairRole')
                paired=bool(left_role) and left_role==right_role and a.get('explicitRolePin') and b.get('explicitRolePin')
                inactive_pair=(a.get('explicitInactivePin') and b['path'] in sdk_variants and b.get('explicitRolePin')) or (b.get('explicitInactivePin') and a['path'] in sdk_variants and a.get('explicitRolePin'))
                if not paired and not inactive_pair:
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
