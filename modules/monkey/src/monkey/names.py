"""Evidence-based display paths. Identity GUIDs/UUIDs are deliberately independent."""
import re
import unicodedata
from pathlib import PurePosixPath
from collections import Counter
from .io import sha
from .layout.casing import romanize

_KNOWN={'.png','.jpg','.jpeg','.ttf','.otf','.fnt','.prefab','.fire','.scene','.unity','.json','.bin','.skel','.atlas','.mp3','.ogg','.wav','.anim'}
_DEVICE=re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)',re.I)


def source_names(manifest):
    result={}
    for asset in manifest['assets']:
        doc=asset.get('document') or {};objects=doc.get('instances',[]);index=doc.get('root',0)
        obj=objects[index] if isinstance(index,int) and 0<=index<len(objects) and isinstance(objects[index],dict) else {}
        result[asset['sourceId']]=dict(bundle=asset.get('bundle',manifest.get('bundle')),logicalPath=asset.get('logicalPath'),
            sourceName=obj.get('_name') or obj.get('name'),sourceType=asset.get('kind'))
    return result


def _trim(value,limit):
    raw=value.encode('utf-8')
    return value if len(raw)<=limit else raw[:limit].decode('utf-8',errors='ignore')


class Names:
    def __init__(self, metadata=None):
        self.metadata=metadata or {};self.records=[];self._claims={};self._allocated={};self._directories={};self._directory_claims={}

    def path(self,sid,suffix,prefix,variant='',metadata=None):
        key=(sid,suffix,prefix,variant)
        if key in self._allocated:return self._allocated[key]
        base=sid
        if base not in self.metadata:
            for ending in ('@original','@atlas'):
                if base.endswith(ending):base=base[:-len(ending)];variant=variant or ending[1:];break
        meta=metadata or self.metadata.get(base,{})
        original=meta.get('logicalPath');name=meta.get('sourceName');reasons=[]
        provenance=meta.get('nameProvenance') or ('config.paths' if isinstance(original,str) and original else 'source-name' if isinstance(name,str) and name else 'unknown')
        relative=original if isinstance(original,str) and original else name if isinstance(name,str) and name else None
        if suffix and not re.fullmatch(r'\.[A-Za-z0-9_-]{1,20}',suffix):suffix='.data';reasons.append('unsafe-extension-normalized')
        if relative and (relative.startswith(('/','\\','~')) or re.match(r'^[A-Za-z]:',relative) or '\\' in relative or any(p in ('','.','..') for p in relative.split('/'))):
            reasons.append('unsafe-source-path-rejected');relative=None;provenance='unknown'
        if relative is None:
            relative='unknown--'+sha(base.encode())[:10];reasons.append('no-safe-source-name')
        parts=[];source_parts=[str(p) for p in [meta.get('bundle') or base.split(':')[0],*relative.split('/')]]
        for part in source_parts:
            clean=romanize(part)
            if clean!=part:reasons.append('han-to-pinyin')
            clean=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',clean).rstrip(' .') or '_unnamed'
            if _DEVICE.match(clean):
                first,dot,last=clean.partition('.');clean=first+'_'+dot+last
            if clean!=part:reasons.append('cross-platform-normalization')
            if len(clean.encode())>80:clean=_trim(clean,64)+'--'+sha(clean.encode())[:8];reasons.append('long-segment')
            parts.append(clean)
        ext=PurePosixPath(parts[-1]).suffix.lower()
        if ext and (ext==suffix or ext in _KNOWN):parts[-1]=parts[-1][:-len(ext)]
        if variant:parts[-1]+='.'+variant;reasons.append('derived-'+variant)
        if len('/'.join(parts).encode())>180:
            parts=[parts[0],_trim(parts[-1],90)+'--'+sha('/'.join(parts).encode())[:8]];reasons.append('long-path')
        parent=prefix.rstrip('/');source_parent=parent
        directory_parts=parts if not suffix else parts[:-1]
        for index,part in enumerate(directory_parts):
            source_parent+='/'+source_parts[index]
            if source_parent in self._directories:
                parent=self._directories[source_parent];continue
            candidate=parent+'/'+part;canonical_dir=unicodedata.normalize('NFC',candidate).casefold()
            if canonical_dir in self._directory_claims and self._directory_claims[canonical_dir]!=source_parent:
                candidate=parent+'/'+part+'--'+sha(source_parent.encode())[:8];reasons.append('folder-name-collision')
            self._directories[source_parent]=candidate;self._directory_claims[unicodedata.normalize('NFC',candidate).casefold()]=source_parent
            parent=candidate
        target=parent if not suffix else parent+'/'+parts[-1]+suffix
        canonical=unicodedata.normalize('NFC',target).casefold()
        if canonical in self._claims and self._claims[canonical]!=key:
            stem=target[:-len(suffix)] if suffix else target
            kind=re.sub('[^a-z0-9_-]','',str(meta.get('sourceType') or '').split('.')[-1].lower())
            alternative=stem+'.'+kind+suffix if kind else stem+'--'+sha(sid.encode())[:10]+suffix
            if unicodedata.normalize('NFC',alternative).casefold() in self._claims:
                alternative=stem+('.'+kind if kind else '')+'--'+sha(sid.encode())[:10]+suffix
            target=alternative;canonical=unicodedata.normalize('NFC',target).casefold();reasons.append('name-collision')
        if canonical in self._claims and self._claims[canonical]!=key:raise ValueError('Unresolved deterministic name collision')
        self._claims[canonical]=key;self._allocated[key]=target
        self.records.append(dict(sourceId=meta.get('sourceId',base),identity=sid,originalPath=original,sourceName=name,provenance=provenance,
            target=target,reasons=sorted(set(reasons))))
        return target

    def report(self):
        logical={r['sourceId']:r['provenance'] for r in self.records}
        return dict(schemaVersion=1,logicalAssets=len(logical),targetPaths=len(self.records),
            logicalProvenance=dict(Counter(logical.values())),collisionPaths=sum(any(x in r['reasons'] for x in ('name-collision','folder-name-collision')) for r in self.records),
            normalizedPaths=sum(any(x in r['reasons'] for x in ('cross-platform-normalization','long-segment','long-path')) for r in self.records),
            records=self.records)
