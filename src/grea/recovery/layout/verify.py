"""Static production-area check (PROJECT-SPEC 8): source traces never enter Assets/ or assets/."""
import re
from pathlib import PurePosixPath
from ..io import diagnostic
from . import semantic,standard

TRACE_DIRS=semantic.TRACE_WORDS
SOURCE_DIRS=semantic.SOURCE_ONLY_WORDS
LOCALE_DIRS=set(semantic.LOCALES)-{'zh-hans','zh-hant'}
# Font family folders may legitimately be named like a locale (an 'En' font), so fonts are not a bundle-as-folder position.
TYPE_DIRS={v.rsplit('/',1)[-1].lower() for v in [*standard.UNITY_TYPES.values(),*standard.CREATOR_TYPES.values()]}-{'fonts'}
EXEMPT=('assets/game/editor/conversion/','assets/plugins/','assets/thirdparty/','assets/textmesh pro/','assets/game/scripts/')
_HEX=re.compile(r'[0-9a-f]{32}')
_HASHED_CODE=re.compile(r'-[0-9a-f]{6,}\.(cs|ts|js)$')
_CLASS=re.compile(r'\b(class|namespace)\s+(Original|Source|Recovered|Monkey|Generated)[A-Z_.]',re.M)


def scan(paths,texts=None):
    """Diagnostics for production paths; texts optionally maps .cs/.ts paths to source for class-name checks."""
    gaps=[]
    for path in sorted(paths):
        if not path.startswith(('Assets/','assets/')) or path.endswith('.meta') or path.casefold().startswith(EXEMPT):continue
        parts=path.split('/');folders=parts[1:-1];name=parts[-1]
        for i,folder in enumerate(folders):
            low=folder.lower()
            parent=folders[i-1].lower() if i else ''
            if folder=='Resources':break  # Preserve existing Unity Resources.Load keys.
            if parent=='audio' and low in ('music','sfx','voice'):continue
            # A shader closure's final folder is an asset name, not a source
            # type container (e.g. the actual effect named MovieClip).
            if (i==len(folders)-1 and 'shaders' in [p.lower() for p in folders[:i]]
                    and low in SOURCE_DIRS and low not in TRACE_DIRS
                    and (name=='EffectDescription.json' or re.fullmatch(r'program\d+_glsl[134]\.(vert|frag)\.glsl',name))):continue
            if low in TRACE_DIRS or low in SOURCE_DIRS:
                gaps.append(diagnostic('LAYOUT_FORBIDDEN_NAME',path,'Source trace folder in production area: '+folder));break
        stem=PurePosixPath(name).stem
        if _HEX.search(stem.lower()):gaps.append(diagnostic('LAYOUT_FORBIDDEN_NAME',path,'GUID-shaped file name'))
        if _HASHED_CODE.search(name):gaps.append(diagnostic('LAYOUT_FORBIDDEN_NAME',path,'Hash-suffixed code file'))
        if name.endswith(('.animationclip.anim','.original.png')) or name.startswith('unknown--'):gaps.append(diagnostic('LAYOUT_FORBIDDEN_NAME',path,'Legacy derived/unknown name'))
        if path.startswith('Assets/') and name.endswith('.js'):gaps.append(diagnostic('LAYOUT_FORBIDDEN_NAME',path,'Source script in Unity production area'))
        text=(texts or {}).get(path)
        if text and _CLASS.search(text):gaps.append(diagnostic('LAYOUT_FORBIDDEN_NAME',path,'Source-trace class or namespace prefix'))
    return gaps
