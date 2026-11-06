# Adapted from GREA cocos_assets.py; MIT notice in monkey/licenses/GREA-MIT.txt.
"""Bounded offline Cocos 2.4 compiled-v1 evidence reader; never a game runtime.

Implementation derives from observed serialized protocol and independently authored examples.
Only the explicitly selected adapter is accepted. References remain data, never live objects.
"""
import base64
import copy
import hashlib
import json
import math
import re

VERSION = '0.1.0'
ADAPTERS = ('cocos-2.4-compiled-v1', 'cocos-2.4-pack-v1', 'cocos-2.4-texture-pack-v1')
_SAFE_DECLARED_SOURCE_ID = re.compile(r'^[A-Za-z0-9_-]{1,128}(?:@[0-9a-f]{5})?$')


class ParseError(ValueError):
    def __init__(self, code, location, message):
        super().__init__(f'{code} at {location}: {message}')
        self.code, self.location, self.message = code, location, message

    def as_dict(self):
        return dict(code=self.code, location=self.location, message=self.message)


def fail(code, location, message):
    raise ParseError(code, location, message)


def array(value, location):
    if not isinstance(value, list): fail('INVALID_SHAPE', location, 'Expected an array')
    return value


def integer(value, location):
    if type(value) is not int: fail('INVALID_SHAPE', location, 'Expected an integer, not a boolean')
    return value


def at(table, index, location):
    integer(index, location)
    if index < 0 or index >= len(table): fail('INDEX_OUT_OF_RANGE', location, 'Table index outside declared bounds')
    return table[index]


def uuid_full(value, location):
    if not isinstance(value, str): fail('INVALID_UUID', location, 'Expected a UUID string')
    if re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', value): return value.lower()
    if re.fullmatch(r'[0-9a-fA-F]{2}[A-Za-z0-9+/]{20}', value):
        raw = value[:2] + base64.b64decode(value[2:], validate=True).hex()
        return f'{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}'
    fail('INVALID_UUID', location, 'Unsupported UUID encoding')


def budget(document, max_depth=96, max_nodes=500000):
    pending=[(document,0)]; count=0
    while pending:
        value,depth=pending.pop(); count+=1
        if isinstance(value,float) and not math.isfinite(value): fail('INVALID_NUMBER','$','Non-finite numeric value')
        if isinstance(value,str):
            try: value.encode('utf-8')
            except UnicodeError: fail('INVALID_UNICODE','$','Unpaired Unicode surrogate is unsupported')
        if depth>max_depth or count>max_nodes: fail('BUDGET_EXCEEDED','$','Depth or value budget exceeded')
        if isinstance(value,list): pending.extend((x,depth+1) for x in value)
        elif isinstance(value,dict): pending.extend((x,depth+1) for pair in value.items() for x in pair)


class CompiledV1:
    def __init__(self, document, declared_source_ids=()):
        d=array(document,'$')
        if not d or type(d[0]) is not int or d[0]!=1: fail('UNSUPPORTED_VERSION','$[0]','Only compiled serialization header 1 is supported')
        if len(d)!=11: fail('INVALID_SHAPE','$','Compiled-v1 requires eleven sections')
        self.uuids,self.strings,self.classes,self.masks,self.values,self.types,self.refs,self.owners,self.keys,self.deps = [
            [] if type(v) is int and v==0 else array(v,f'$[{i}]') for i,v in enumerate(d[1:],1)]
        if (not isinstance(declared_source_ids, (list, tuple, set, frozenset))
                or len(declared_source_ids) > 50000
                or any(not isinstance(value, str) or not _SAFE_DECLARED_SOURCE_ID.fullmatch(value)
                       for value in declared_source_ids)):
            fail('INVALID_DECLARED_SOURCE_IDS', '$.declaredSourceIds', 'Expected at most 50,000 safe opaque source IDs')
        self.declared_source_ids = frozenset(declared_source_ids)
        if not all(isinstance(v,str) for v in self.strings): fail('INVALID_SHAPE','$[2]','String table must contain strings')
        if len(self.owners)!=len(self.keys) or len(self.owners)!=len(self.deps): fail('INVALID_SHAPE','$[8:11]','Dependency tables have different lengths')
        self.ref_owners={}; self.dep_owners={}; self.instances=[]; self.total=0

    def class_name(self,index,loc):
        value=at(self.classes,index,loc)
        name=value[0] if isinstance(value,list) and value else value
        if not isinstance(name,str): fail('INVALID_SHAPE',loc,'Class name must be a string')
        return name

    def assign(self,owner,key,value,loc):
        if isinstance(owner,dict) and isinstance(key,str): owner[key]=value
        elif isinstance(owner,list) and type(key) is int:
            at(owner,key,loc); owner[key]=value
        else: fail('INVALID_REFERENCE',loc,'Expected object/string key or array/integer key')

    def reference_key(self,key,loc):
        if type(key) is int: return at(self.strings,key,loc) if key>=0 else ~key
        if isinstance(key,str): return key
        fail('INVALID_REFERENCE',loc,'Invalid reference key')

    def object(self,values,loc,depth):
        array(values,loc)
        if not values: fail('INVALID_SHAPE',loc,'Missing object mask')
        mask=array(at(self.masks,values[0],loc+'.mask'),loc+'.mask')
        if len(mask)<2: fail('INVALID_SHAPE',loc+'.mask','Mask lacks class or boundary')
        cls=array(at(self.classes,mask[0],loc+'.class'),loc+'.class')
        if len(cls)<3 or not isinstance(cls[0],str): fail('INVALID_SHAPE',loc+'.class','Invalid property class')
        keys=array(cls[1],loc+'.class.keys'); offset=integer(cls[2],loc+'.class.offset')
        boundary=integer(mask[-1],loc+'.mask.boundary')
        if len(values)!=len(mask)-1 or not 1<=boundary<=len(values): fail('INVALID_SHAPE',loc,'Mask and object lengths/boundary disagree')
        result={'__type__':cls[0]}; seen=set()
        for i in range(1,len(values)):
            prop=mask[i]; key=at(keys,prop,loc+f'.property[{i}]')
            if not isinstance(key,str) or key in seen or key=='__type__': fail('INVALID_SHAPE',loc,'Invalid or duplicate property key')
            seen.add(key)
            kind=0 if i<boundary else at(cls,prop+offset,loc+'.kind')
            self.field(result,key,values[i],kind,loc+'.'+key,depth+1)
        return result

    def field(self,owner,key,value,kind,loc,depth):
        if depth>96: fail('BUDGET_EXCEEDED',loc,'Decoded nesting budget exceeded')
        integer(kind,loc+'.kind')
        if kind==0 or kind==7: result=copy.deepcopy(value)
        elif kind==1:
            integer(value,loc)
            if value>=0:
                if value>=self.total: fail('INDEX_OUT_OF_RANGE',loc,'Instance reference outside declared instances')
                result={'__id__':value}
            else:
                index=(~value)*3
                if index>=max(0,len(self.refs)-1) or index in self.ref_owners: fail('INVALID_REFERENCE',loc,'Invalid or reused deferred reference')
                self.ref_owners[index]=owner; result=None
        elif kind in (2,3,9):
            result=[None]*len(array(value,loc))
            for i,v in enumerate(value): self.field(result,i,v,{2:1,3:6,9:4}[kind],f'{loc}[{i}]',depth+1)
        elif kind==4: result=self.object(value,loc,depth+1)
        elif kind in (5,8):
            array(value,loc)
            if not value: fail('INVALID_SHAPE',loc,'Inline value type lacks identity')
            result={'__value_type__':integer(value[0],loc),'values':copy.deepcopy(value[1:])}
        elif kind==6:
            at(self.deps,value,loc)
            if value in self.dep_owners: fail('INVALID_REFERENCE',loc,'Dependency slot has multiple owners')
            self.dep_owners[value]=owner; result=None
        elif kind==10:
            if len(array(value,loc))!=2: fail('INVALID_SHAPE',loc,'Custom value must contain class and payload')
            result={'__type__':self.class_name(value[0],loc),'data':copy.deepcopy(value[1])}
        elif kind==11:
            array(value,loc)
            if not value or not isinstance(value[0],dict) or (len(value)-1)%3: fail('INVALID_SHAPE',loc,'Invalid dictionary encoding')
            result=copy.deepcopy(value[0])
            for i in range(1,len(value),3): self.field(result,value[i],value[i+2],value[i+1],f'{loc}[{i}]',depth+1)
        elif kind==12:
            array(value,loc)
            if not value: fail('INVALID_SHAPE',loc,'Missing typed array values')
            result=copy.deepcopy(array(value[0],loc))
            if len(result)!=len(value)-1: fail('INVALID_SHAPE',loc,'Typed array length mismatch')
            for i,v in enumerate(list(result)): self.field(result,i,v,value[i+1],f'{loc}[{i}]',depth+1)
        else: fail('UNSUPPORTED_KIND',loc+'.kind',f'Unsupported field kind {kind}')
        self.assign(owner,key,result,loc)

    def decode(self):
        values=list(self.values); root=0
        if values and type(values[-1]) is int: root=values.pop()
        self.total=len(values)
        if not values or len(self.types)>self.total: fail('INVALID_SHAPE','$[5]','No instances or more custom types than instances')
        normal=self.total-len(self.types)
        for i,value in enumerate(values):
            loc=f'$[5][{i}]'
            if i<normal: result=self.object(value,loc,0)
            else:
                kind=integer(self.types[i-normal],loc+'.type')
                if kind>=0: result={'__type__':self.class_name(kind,loc),'data':copy.deepcopy(value)}
                else:
                    holder=[None]; self.field(holder,0,value,~kind,loc,0); result=holder[0]
            self.instances.append(result)
        root=root if root>=0 else ~root; at(self.instances,root,'$.root')
        if self.refs:
            if (len(self.refs)-1)%3: fail('INVALID_SHAPE','$[7]','Invalid reference triples')
            embedded=integer(self.refs[-1],'$[7][-1]')*3
            if embedded<0 or embedded>len(self.refs)-1: fail('INVALID_REFERENCE','$[7]','Invalid embedded reference count')
            for i in range(0,len(self.refs)-1,3):
                owner=self.ref_owners.get(i) if i<embedded else at(self.instances,self.refs[i],f'$[7][{i}]')
                target=self.refs[i+2]; at(self.instances,target,f'$[7][{i+2}]')
                self.assign(owner,self.reference_key(self.refs[i+1],f'$[7][{i+1}]'),{'__id__':target},f'$[7][{i}]')
        for i,(owner,key,uid) in enumerate(zip(self.owners,self.keys,self.deps)):
            owner=self.dep_owners.get(i) if i in self.dep_owners else at(self.instances,owner,f'$[8][{i}]')
            uid=at(self.uuids,uid,f'$[10][{i}]') if type(uid) is int else uid
            self.assign(owner,self.reference_key(key,f'$[9][{i}]'),
                        {'__uuid__':source_asset_key(uid,f'$[10][{i}]',self.declared_source_ids)},
                        f'$.dependency[{i}]')
        return dict(root=root,instances=self.instances)


def decode_document(document, adapter=ADAPTERS[0], max_depth=96, *, declared_source_ids=()):
    budget(document,max_depth=max_depth)
    if adapter==ADAPTERS[0]: return CompiledV1(document, declared_source_ids).decode()
    if adapter==ADAPTERS[1]:
        array(document,'$')
        if len(document)!=6: fail('INVALID_SHAPE','$','Pack requires shared header and sections')
        sections=array(document[5],'$[5]')
        if not sections: fail('EMPTY_INPUT','$[5]','Pack contains no sections')
        return {'sections':[dict(pack_section_ordinal=i,document=CompiledV1(
            document[:5]+array(section,f'$[5][{i}]'), declared_source_ids).decode()) for i,section in enumerate(sections)]}
    if adapter==ADAPTERS[2]:
        if not isinstance(document,dict) or set(document)!= {'type','data'} or document['type']!='cc.Texture2D' or not isinstance(document['data'],str): fail('INVALID_SHAPE','$','Expected the explicit Texture2D pack encoding')
        if not document['data'] or any(not x for x in document['data'].split('|')): fail('EMPTY_INPUT','$.data','Empty texture section')
        return {'sections':[dict(pack_section_ordinal=i,type='cc.Texture2D',data=value) for i,value in enumerate(document['data'].split('|'))]}
    fail('UNSUPPORTED_ADAPTER','$',f'Unknown adapter {adapter}')



def asset_key(value, location='$'):
    """Native texture keys may be short hex hashes; never conflate with UUIDs."""
    if isinstance(value,str)and '@'in value:
        match=re.fullmatch(r'([^@]+)@([0-9a-f]{5})',value)
        if not match:fail('INVALID_UUID',location,'Unsupported subasset suffix')
        return asset_key(match[1],location)+'@'+match[2]
    if isinstance(value, str) and re.fullmatch(r'[0-9a-f]{8,16}', value):
        return value
    return uuid_full(value, location)


def source_asset_key(value, location='$', declared_source_ids=()):
    """Preserve a safe opaque ID only when the source bundle declared it."""
    try:
        return asset_key(value, location)
    except ParseError:
        if (value in declared_source_ids and safe_source_asset_identity(value)):
            return value
        fail('INVALID_UUID', location, 'Unsupported UUID encoding and not a safe config-declared opaque source ID')


def safe_source_asset_identity(value):
    """Return whether an opaque config identity is a bounded path-safe token."""
    return isinstance(value, str) and _SAFE_DECLARED_SOURCE_ID.fullmatch(value) is not None


def decode_pack_section(document, ordinal, *, declared_source_ids=(), max_depth=96):
    """Decode one selected packed member without expanding sibling members."""
    d = array(document, '$')
    if len(d) != 6 or type(d[0]) is not int or d[0] != 1:
        fail('INVALID_SHAPE', '$', 'Pack requires version-1 shared header and sections')
    sections = array(d[5], '$[5]')
    integer(ordinal, '$.packSectionOrdinal')
    section = at(sections, ordinal, '$[5].selected')
    selected = d[:5] + array(section, f'$[5][{ordinal}]')
    budget(selected, max_depth=max_depth)
    return CompiledV1(selected, declared_source_ids).decode()
