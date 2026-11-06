"""LayoutPlanner: the only allocator of generated asset paths (PROJECT-SPEC 4-5). Identity GUIDs stay path-independent."""
import re
import unicodedata
from collections import Counter
from ..io import sha
from . import casing,classify,semantic,standard

PASCAL_TYPES={'prefab','scene','config','strings','data','atlas','controller','font-asset'}
VARIANTS={'original':'untrimmed','atlas':'page0'}
MAX_PATH_BYTES=180
_HASHED=re.compile(r'[0-9a-f]{32}|[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}')


def _fold(path):return unicodedata.normalize('NFC',path).casefold()


class LayoutPlanner:
    def __init__(self,engine,metadata=None,overrides=None):
        if engine not in ('unity','creator'):raise ValueError('Unknown layout engine')
        self.engine=engine;self.metadata=metadata or {};self.overrides=overrides or {}
        self.default_locale=self.overrides.get('defaultLocale') or 'zh-Hans'
        self.types=standard.UNITY_TYPES if engine=='unity' else standard.CREATOR_TYPES
        self.roots=standard.ROOTS[engine]
        self.records=[];self.replay=[];self._claims={};self._allocated={};self._dirs={};self._pending={};self._by_key={}
        # A module has one spelling across resource types and both targets.
        # Prefer evidenced CamelCase (CupMerge) over a flattened alias (cupmerge).
        self._minigame_names={}
        for meta in self.metadata.values():
            game=semantic.derive(meta,self.overrides)['minigame']
            if not game:continue
            name=casing.pascal(game);key=name.casefold();prior=self._minigame_names.get(key)
            rank=lambda value:(-sum(c.isupper() for c in value),value)
            if prior is None or rank(name)<rank(prior):self._minigame_names[key]=name

    # -- naming -------------------------------------------------------------------------------------------
    def _meta(self,sid,metadata):
        base=sid;variant=''
        if metadata is None and base not in self.metadata:
            for ending in ('@original','@atlas'):
                if base.endswith(ending):base=base[:-len(ending)];variant=ending[1:];break
        return base,variant,dict(metadata if metadata is not None else self.metadata.get(base,{}))

    def _stem(self,typ,stem):
        return casing.pascal(stem) if typ in PASCAL_TYPES else casing.snake(stem)

    def _folders(self,parts):
        return [casing.folder(p,self.engine) for p in parts]

    def describe(self,sid,kind,suffix,variant='',metadata=None,root=None):
        """Base (uncollided) target and its naming evidence."""
        base,implicit,meta=self._meta(sid,metadata);variant=variant or implicit
        d=semantic.derive(meta,self.overrides);folders=list(d['folders']);stem=d['stem'];reasons=list(d['reasons'])
        rename=(self.overrides.get('renames') or {}).get(base)
        if isinstance(rename,str) and rename:stem=rename;reasons.append('layout-rename')
        typ=classify.target_type(kind,suffix)
        if typ=='audio':typ,folders=classify.audio_category(folders,stem)
        if typ=='json':typ='strings' if classify.is_strings(stem,d['locale']) else 'config'
        if kind=='controller':typ='controller'
        if kind=='font-asset':typ='font-asset'
        if stem is None or d['provenance'] in ('unknown','input-relative-path'):
            stem=(typ.replace('-','_'))+'_'+sha(base.encode())[:6];folders=[self.roots['unsorted']];reasons.append('no-safe-source-name')
            raw_folders=folders
        else:raw_folders=None
        if _HASHED.search(stem.lower()):
            # A content hash is not a name (PROJECT-SPEC 5.5): keep any readable remainder and the module, else name by type.
            stem=re.sub(r'[0-9a-fA-F]{32,}','',stem).strip('_-. ') if not _HASHED.fullmatch(stem.lower()) else ''
            stem=stem or (typ.replace('-','_'))+'_'+sha(base.encode())[:6];reasons.append('hash-source-name')
        name=self._stem(typ,stem)
        if any(casing.HAN.search(str(v)) for v in [stem,*folders]):reasons.append('han-to-pinyin')
        if typ=='config':
            lowered=name.lower()
            for tail in ('table','config','conf','cfg','data'):
                if lowered.endswith(tail) and len(name)>len(tail):name=name[:-len(tail)]+'Table';reasons.append('config-table-name');break
        if variant:name+='_'+VARIANTS.get(variant,casing.snake(variant));reasons.append('derived-'+VARIANTS.get(variant,variant))
        root=root or self.roots['content']
        type_dir={'controller':self.types['animation'],'font-asset':self.types['font']}.get(typ,self.types.get(typ))
        module=raw_folders if raw_folders is not None else (folders or ['Common'])
        if typ in ('font','font-asset'):
            module=[casing.folder(stem,self.engine)]
        if d['minigame']:
            game=casing.pascal(d['minigame']);module=['MiniGames',self._minigame_names.get(game.casefold(),game),*module]
        if d['locale']:module=[d['locale'],*module]
        if typ=='strings':
            module=[d['locale'] or self.default_locale]
            parts=[root,self.types['strings'],*self._folders(module)]
        elif typ=='scene':
            scenes=root+'/Scenes'
            test='test' in stem.lower().replace('-','_').split('_') or stem.lower().endswith('test')
            module=['Tests'] if test else (folders or ['Common'])
            parts=[scenes,*self._folders(module)]
        else:
            parts=[root]
            parts+=[type_dir]+self._folders(module)
        ext=('.unity' if self.engine=='unity' else '.scene') if typ=='scene' and not suffix else suffix
        filename=self._filename(name,ext or '')
        target='/'.join(parts)+'/'+filename
        if len(target[len(root):].encode())>MAX_PATH_BYTES-max(len(r['content'].encode()) for r in standard.ROOTS.values()):
            keep=root+'/'+(type_dir or 'Scenes')+'/Unsorted'
            token=sha((sid+'|'+kind+'|'+variant).encode())[:6]
            target=keep+'/'+self._filename(name+'_'+token,ext or '');reasons.append('long-path')
        cased=self._folders(module)
        record=dict(sourceId=meta.get('sourceId',base),identity=sid,kind=kind,type=typ,bundle=d['bundle'],originalPath=meta.get('logicalPath'),
            sourceName=meta.get('sourceName'),provenance=d['provenance'],locale=d['locale'],minigame=d['minigame'],
            module=cased,stem=stem,reasons=reasons)
        return target,record

    @staticmethod
    def _filename(stem,extension):
        limit=casing.SEGMENT_BYTES-len(extension.encode())
        if len(stem.encode())>limit:
            stem=stem.encode()[:limit-7].decode('utf-8',errors='ignore').rstrip('_-')+'_'+sha(stem.encode())[:6]
        return stem+extension

    def derived_path(self,sid,base_path,tail,extension):
        """Allocate Editor-created derivatives with the same full-filename budget."""
        key=(sid,'animation',extension,tail)
        if key in self._allocated:return self._allocated[key]
        parent,_,filename=base_path.rpartition('/');stem=filename.rsplit('.',1)[0]
        owner=next((r for r in self.records if r['target']==base_path),None)
        if owner is None:raise ValueError('Derived asset requires an allocated owner path')
        self.replay.append(dict(operation='derived',args=[sid,owner['identity'],owner['kind'],'.'+filename.rsplit('.',1)[-1],tail,extension]))
        record=dict(owner,identity=sid,kind='animation',type='animation',stem=stem+tail,
                    reasons=sorted(set(owner['reasons'])|{'derived-asset'}))
        target=parent+'/'+self._filename(stem+tail,extension)
        return self._allocate(key,target,record,None)

    def module_of(self,sid,kind='prefab',metadata=None):
        """Cased module folders an object would live under, e.g. the prefab module that binds a script."""
        return self.describe(sid,kind,'.prefab' if kind=='prefab' else '',metadata=metadata)[1]['module']

    # -- allocation ---------------------------------------------------------------------------------------
    def claim(self,path,owner='existing'):
        """Mark a path written by another stage so later allocations never reuse it."""
        self.replay.append(dict(operation="claim",path=path,owner=owner))
        self._claims.setdefault(_fold(path),owner)

    def _canonical_dirs(self,target):
        parts=target.split('/');out=[]
        for part in parts[:-1]:
            key=_fold('/'.join(out+[part]))
            spelled=self._dirs.setdefault(key,'/'.join(out+[part]))
            out=spelled.split('/')
        return '/'.join(out+[parts[-1]])

    def _suffixed(self,target,token):
        slash=target.rfind('/');dot=target.find('.',slash+1)
        dot=len(target) if dot<0 else dot
        return target[:slash+1]+self._filename(target[slash+1:dot]+'_'+token,target[dot:])

    def reserve(self,requests):
        """requests: [(identity,kind,suffix,variant,metadata,qualifier)]. Collision winners are the smallest identities."""
        requests=list(requests)
        self.replay.append(dict(operation="reserve",requests=requests))
        described=[]
        for sid,kind,suffix,variant,metadata,qualifier in requests:
            key=(sid,kind,suffix,variant)
            if key in self._allocated or key in self._pending:continue
            target,record=self.describe(sid,kind,suffix,variant,metadata)
            self._pending[key]=(target,record,qualifier);described.append(key)
        groups={}
        for key in described:groups.setdefault(_fold(self._pending[key][0]),[]).append(key)
        for folded,keys in sorted(groups.items()):
            for index,key in enumerate(sorted(keys,key=lambda k:(k[0],k[1],k[2],k[3]))):
                target,record,qualifier=self._pending.pop(key)
                self._allocate(key,target,record,qualifier,winner=index==0)

    def _allocate(self,key,target,record,qualifier,winner=True):
        target=self._canonical_dirs(target)
        if not winner or _fold(target) in self._claims:
            alternatives=([self._suffixed(target,casing.snake(qualifier))] if qualifier else [])+[self._suffixed(target,sha(key[0].encode())[:6])]
            for alternative in alternatives:
                if _fold(alternative) not in self._claims:target=alternative;break
            else:raise ValueError('Unresolved deterministic name collision: '+target)
            record['reasons']=sorted(set(record['reasons'])|{'name-collision'})
        self._claims[_fold(target)]=key;self._allocated[key]=target
        record['target']=target;self.records.append(record);self._by_key[key]=record
        return target

    def record(self,sid,kind,suffix,variant=''):
        return self._by_key.get((sid,kind,suffix,variant))

    def path(self,sid,kind,suffix,variant='',metadata=None,qualifier=None):
        key=(sid,kind,suffix,variant)
        if key in self._allocated:return self._allocated[key]
        self.replay.append(dict(operation='path',args=[sid,kind,suffix,variant,metadata,qualifier]))
        target,record=self.describe(sid,kind,suffix,variant,metadata)
        return self._allocate(key,target,record,qualifier)

    def folder(self,sid,kind='spine',metadata=None,root=None):
        """A closure folder (Spine skeleton): canonical folder, file names inside are kept by the caller."""
        key=(sid,kind,'','folder')
        if key in self._allocated:return self._allocated[key]
        self.replay.append(dict(operation='folder',args=[sid,kind,metadata,root]))
        target,record=self.describe(sid,kind,'','',metadata,root=root)
        slash=target.rfind('/');target=target[:slash]+'/'+casing.folder(target[slash+1:],self.engine)
        return self._allocate(key,target,record,None)

    def report(self):
        logical={r['sourceId']:r['provenance'] for r in self.records}
        return dict(schemaVersion=2,layout=standard.VERSION,engine=self.engine,replay=dict(schemaVersion=1,operations=self.replay),logicalAssets=len(logical),targetPaths=len(self.records),
            logicalProvenance=dict(Counter(logical.values())),types=dict(Counter(r['type'] for r in self.records)),
            collisionPaths=sum('name-collision' in r['reasons'] for r in self.records),
            overriddenPaths=sum(any(x.startswith('layout-') for x in r['reasons']) for r in self.records),
            unsortedPaths=sum('no-safe-source-name' in r['reasons'] for r in self.records),records=self.records)
