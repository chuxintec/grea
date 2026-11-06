"""Source-binding names for full drafts; no textual search/replace or runtime inference."""
from __future__ import annotations
import hashlib
import re
from collections import Counter, defaultdict


def _hash(value):return hashlib.sha256(str(value).encode()).hexdigest()[:8]


class DraftSymbols:
    def __init__(self, header, class_names, identifier_normalizer):
        self.normalize=identifier_normalizer
        self.classes={r['id']:r for r in header.get('classes',[]) if isinstance(r,dict) and isinstance(r.get('id'),str)}
        self.class_names=dict(class_names);self.by_binding={}
        for cid,row in self.classes.items():
            for key in ('bindingId','constructorBindingId'):
                if isinstance(row.get(key),str):self.by_binding[row[key]]=cid
        self.mutated=set(header.get('draftMutatedBindings',[]))
        self.targets={};self.symbols=defaultdict(list);self.stats=Counter();self.declarations=[]
        rows=[('method',r)for r in header.get('draftDeclarations',[])]+[('field',r)for r in header.get('draftFields',[])]
        owners={r.get('ownerBindingId') for _,r in rows if r.get('ownerBindingId')}
        self.owner_classes={bid:self.class_name(self.by_binding.get(bid,bid))for bid in owners|set(self.by_binding)}
        used=defaultdict(set);field_targets={}
        for kind,row in sorted(rows,key=lambda pair:((pair[1].get('sourceBytes')or{}).get('start',0),pair[0],pair[1].get('id',''))):
            sid=row.get('id');name=row.get('name');bucket=self.bucket(row)
            if not isinstance(sid,str) or not isinstance(name,str):continue
            key=(bucket,name,bool(row.get('static',True)))
            if kind=='field' and key in field_targets:
                target=field_targets[key]
            else:
                target=self.normalize(name,'DraftMethod'if kind=='method'else'DraftField')
                if target.casefold()==self.class_name(bucket).casefold():target+='_DraftMethod'if kind=='method'else'_DraftField'
                if target.casefold() in used[bucket]:
                    target+='_'+_hash(sid if kind=='method'else name)
                    suffix=2;base=target
                    while target.casefold()in used[bucket]:target=base+'_'+str(suffix);suffix+=1
                used[bucket].add(target.casefold())
                if kind=='field':field_targets[key]=target
            self.targets[(kind,sid)]=target
            record=dict(kind=kind,id=sid,sourceName=name,bucket=bucket,targetClass=self.class_name(bucket),targetName=target,static=bool(row.get('static',True)))
            self.declarations.append(record)
            if kind=='field' or row.get('kind')=='indexed_method':
                # Static aliases of a constructor share one semantic source owner.
                symbol=(bucket,name,bool(row.get('static',True)))
                candidate=dict(record)
                if kind=='field':candidate['id']='field:'+name
                if not any(x['kind']==candidate['kind'] and x['id']==candidate['id']for x in self.symbols[symbol]):self.symbols[symbol].append(candidate)
        self.stats['plannedDeclarations']=len(self.declarations)
        self.stats['uniqueFields']=len(field_targets)
        self.stats['ambiguousMemberKeys']=sum(len(v)>1 for v in self.symbols.values())

    def bucket(self,row):
        cid=row.get('classId')
        if cid in self.classes:return cid
        owner=row.get('ownerBindingId')
        return self.by_binding.get(owner,owner) if isinstance(owner,str) else 'function:'+str(row.get('id','unknown'))

    def class_name(self,bucket):
        if bucket in self.class_names:return self.class_names[bucket]
        prefix='Function_'if str(bucket).startswith('function:')else'Unresolved_'
        return prefix+hashlib.sha256(str(bucket).encode()).hexdigest()[:10]

    def target_name(self,row,kind='method'):
        return self.targets.get((kind,row.get('id')),self.normalize(row.get('name'),'DraftMethod'if kind=='method'else'DraftField'))

    def capture_parameters(self,method):
        result=[];seen=set()
        for row in method.get('captures',[]):
            bid=row.get('bindingId')
            if not isinstance(bid,str) or bid in seen:continue
            if bid in self.owner_classes and bid not in self.mutated:continue
            seen.add(bid)
            name=re.sub(r'[^A-Za-z0-9_]','_',str(row.get('name')or'captured'))
            result.append(dict(bindingId=bid,sourceName=row.get('name'),targetName='__capture_'+name+'_'+_hash(bid)))
        return result

    def annotate(self,ast,method,captures=None):
        """Annotate source AST using exact binding/owner identities only.

        Ordinary function ``this`` remains dynamic. Worker marks lexical arrow
        ``this`` and known method owners; unknown or mutated bindings stay visible.
        """
        if not isinstance(ast,dict):return ast
        if captures is None:captures=method.get('captureParameters',[])
        capture_names={r['bindingId']:r['targetName']for r in captures or [] if isinstance(r,dict)and isinstance(r.get('bindingId'),str)and isinstance(r.get('targetName'),str)}
        todo=[ast]
        while todo:
            node=todo.pop()
            if not isinstance(node,dict):continue
            if node.get('type')=='Identifier':
                bid=node.get('bindingId')
                if bid in capture_names:node['_draftIdentifierTarget']=capture_names[bid]
                elif bid in self.owner_classes and bid not in self.mutated:node['_draftIdentifierTarget']=self.owner_classes[bid]
            elif node.get('type')=='MemberExpression':
                obj=node.get('object')or{};prop=node.get('property')or{}
                name=prop.get('value')if node.get('computed')and prop.get('type')=='Literal'else prop.get('name')if not node.get('computed')else None
                this=obj.get('type')=='ThisExpression'
                bid=obj.get('thisOwnerBindingId')if this else obj.get('bindingId')if obj.get('type')=='Identifier'else None
                static=bool(obj.get('thisStatic'))if this else True
                bucket=self.by_binding.get(bid,bid)
                values=self.symbols.get((bucket,name,static),[])if isinstance(name,str)else []
                if bid in self.owner_classes and bid not in self.mutated and len(values)==1:
                    item=values[0];node['_draftMember']=dict(name=item['targetName'],ownerClass=self.owner_classes[bid],receiver='static_owner'if static else'source',sourceDeclarationId=item['id'])
                    self.stats['mappedMemberReferences']+=1
                elif (obj.get('type') == 'Identifier' and obj.get('name') in ('Math', 'cc')
                      and obj.get('bindingId') is None and not obj.get('bindingAmbiguous')):
                    # Known renderer adapters retain their own conservative API diagnostics.
                    pass
                else:
                    if this and static and bid in self.owner_classes and bid not in self.mutated:
                        # Receiver identity is proven even when a getter/member is not indexed.
                        obj['_draftStaticThisOwner'] = self.owner_classes[bid]
                    reason=('mutated_owner_binding'if bid in self.mutated else'ambiguous_source_member'if len(values)>1 else'unknown_owner_member'if bid in self.owner_classes else'unknown_receiver_type')
                    node['_draftUnresolvedMember']=dict(reason=reason,sourceName=name,bindingId=bid)
                    self.stats['unresolvedMemberReferences']+=1
            for key,value in tuple(node.items()):
                if key.startswith('_draft'):continue
                if isinstance(value,dict):todo.append(value)
                elif isinstance(value,list):todo.extend(x for x in value if isinstance(x,dict))
        return ast

    def summary(self):
        return dict(schemaVersion=1,strategy='source-binding-owner-and-exact-member-identity',counts=dict(self.stats),mutatedOwnerBindings=sorted(self.mutated&set(self.owner_classes)),ambiguousMembers=[dict(owner=key[0],sourceName=key[1],static=key[2],declarations=[v['id']for v in values])for key,values in self.symbols.items()if len(values)>1])
