"""Source path -> module path (PROJECT-SPEC 7.1). Packaging, type words and locales become metadata, not folders."""
import fnmatch
from pathlib import PurePosixPath

PACKAGING={'main','resources','internal','start-scene','gameasset','remoteasset','spineasset','subpackages','assets','import','native','raw-assets','res'}
TYPE_WORDS={'texture','textures','image','images','prefab','prefabs','anim','anims','animation','animations','animationclip','spine','spinecook','uispine',
    'audio','audios','sound','sounds','music','font','fonts','config','configs','data','material','materials','shader','shaders','movieclip',
    'uiraw','sprite','sprites','scene','scenes','model','models'}
SUBASSET_TAILS={'spriteframe','texture','sprite-frame'}
LOCALES={'en':'en','zh':'zh-Hans','zh-cn':'zh-Hans','zh-hans':'zh-Hans','cn':'zh-Hans','zh-tw':'zh-Hant','tw':'zh-Hant','zh-hk':'zh-Hant',
    'zh-hant':'zh-Hant','jp':'ja','ja':'ja','kr':'ko','ko':'ko','fr':'fr','de':'de','es':'es','pt':'pt','ru':'ru','th':'th','vi':'vi'}
MINIGAME_BUNDLES={'minigameres','minigame','minigames'}
# Never valid production folders (PROJECT-SPEC 8): source traces and source-only type/package words.
TRACE_WORDS={'original','recovered','recovery','source','sources','generated','monkey','manual','bulkinitial','imported','sourcemedia','unformatted'}
SOURCE_ONLY_WORDS={'texture','image','images','prefab','anim','anims','animationclip','spinecook','uispine','sound','sounds','music','font',
    'configs','material','shader','movieclip','uiraw','sprite','gameasset','remoteasset','spineasset','subpackages','raw-assets','minigameres',
    'texture2d','monobehaviour','textasset','animatorcontroller','audioclip','mesh'}
KNOWN_SUFFIXES={'.png','.jpg','.jpeg','.webp','.ttf','.otf','.fnt','.prefab','.fire','.scene','.unity','.json','.bin','.skel','.atlas',
    '.mp3','.ogg','.wav','.m4a','.anim','.mat','.controller','.asset','.txt','.bytes','.mp4','.shader','.fbx','.tga','.psd',
    '.overridecontroller','.spriteatlas','.mixer','.lighting','.shadervariants','.physicsmaterial2d','.cginc','.hlsl','.shadergraph','.exr','.ttf','.otf'}


def split_logical(meta):
    """(segments, stem, provenance) from typed source metadata; input-relative paths are not semantic."""
    logical=meta.get('logicalPath');name=meta.get('sourceName')
    provenance=meta.get('nameProvenance') or ('config.paths' if isinstance(logical,str) and logical else 'source-name' if isinstance(name,str) and name else 'unknown')
    if provenance=='input-relative-path':return [],None,provenance
    raw=logical if isinstance(logical,str) and logical else name if isinstance(name,str) and name else None
    if raw is None or raw.startswith(('/','\\','~')) or '\\' in raw or (len(raw)>1 and raw[1]==':'):return [],None,'unknown'
    parts=[p for p in raw.split('/') if p]
    if any(p in ('.','..') for p in parts):return [],None,'unknown'
    if len(parts)>1 and parts[-1].lower() in SUBASSET_TAILS:parts=parts[:-1]
    stem=parts[-1];suffix=PurePosixPath(stem).suffix.lower()
    if suffix in KNOWN_SUFFIXES:stem=stem[:-len(suffix)]
    return parts[:-1],stem or None,provenance


def bundle_role(bundle,overrides):
    declared=(overrides.get('bundles') or {}).get(bundle) or {}
    role=declared.get('role')
    if role=='locale':return 'locale',declared.get('locale') or LOCALES.get(str(bundle).lower(),str(bundle))
    if role in ('minigame','packaging'):return role,None
    key=str(bundle or '').lower()
    if key in LOCALES:return 'locale',LOCALES[key]
    if key in MINIGAME_BUNDLES:return 'minigame',None
    return 'packaging',None


def strip_leading(folders,extra):
    words=TYPE_WORDS|PACKAGING|{w.lower() for w in extra}
    index=0
    while index<len(folders) and folders[index].lower() in words:index+=1
    return folders[index:]


def _match(pattern,folders):
    """Segment-wise glob over leading folders; a trailing ** only means 'and below'. Returns (#matched, captures)."""
    parts=[p for p in pattern.split('/') if p]
    if parts and parts[-1]=='**':parts=parts[:-1]
    if not parts or len(parts)>len(folders):return None
    captures=[]
    for want,have in zip(parts,folders):
        if not fnmatch.fnmatchcase(have.lower(),want.lower()):return None
        if '*' in want:
            prefix,_,suffix=want.partition('*')
            captures.append(have[len(prefix):len(have)-len(suffix) if suffix else None])
    return len(parts),captures


def apply_modules(rules,bundle,folders):
    """First matching layout.json module rule replaces the matched leading folders."""
    for rule in rules or []:
        for candidate,offset in ((folders,0),([str(bundle)]+folders,1)):
            found=_match(rule['match'],candidate)
            if not found:continue
            count,captures=found
            target=rule['module']
            for i,value in enumerate(captures,1):target=target.replace('{'+str(i)+'}',value)
            return [p for p in target.split('/') if p]+candidate[count:],rule['match']
    return None,None


def derive(meta,overrides=None):
    """Raw (uncased) folders below the type folder, stem, locale and minigame name for one source object."""
    overrides=overrides or {};bundle=meta.get('bundle') or ''
    folders,stem,provenance=split_logical(meta)
    role,locale=bundle_role(bundle,overrides);minigame=None;reasons=[]
    replaced,rule=apply_modules(overrides.get('modules'),bundle,folders)
    if replaced is not None:
        folders=replaced;reasons.append('layout-override:'+rule)
    else:
        folders=strip_leading(folders,overrides.get('stripSegments') or [])
    # The target is type-first, so type-grouping and trace folders anywhere in the source path are redundant.
    dropped={w for w in TYPE_WORDS|TRACE_WORDS|SOURCE_ONLY_WORDS}
    if any(f.lower() in dropped for f in folders):folders=[f for f in folders if f.lower() not in dropped];reasons.append('type-or-trace-segment-dropped')
    if role=='minigame' and folders:
        minigame=folders[0];folders=strip_leading(folders[1:],overrides.get('stripSegments') or [])
    elif role=='minigame':
        minigame='Common'
    return dict(folders=folders,stem=stem,locale=locale,minigame=minigame,provenance=provenance,bundle=bundle,bundleRole=role,reasons=reasons)
