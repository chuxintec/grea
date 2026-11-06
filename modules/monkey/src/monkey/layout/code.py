"""Recovered code placement (PROJECT-SPEC 4.6): layer, module and namespace from evidence; unknown stays Unclassified."""
import re
from ..io import sha
from . import casing,standard

LAYER_SUFFIXES=(
    ('Presentation',('Window','View','Panel','Hud','HUD','Item','Cell','Button','Btn','Comp','Component','Dialog','Popup','Page','Widget','Render','Renderer','Effect','Anim')),
    ('Services',('Net','Http','Socket','Sdk','SDK','Storage','Platform','Ad','Ads','Api','Service','Loader','Request')),
    ('Domain',('Config','Cfg','Data','Model','Info','Vo','Def','Const','Enum','Type','Table','State')),
    ('Gameplay',('Manager','Mgr','System','Controller','Ctrl','Logic','Proxy','Handler')),
)
UNCLASSIFIED='Unclassified'


def class_name(module):
    """The draft's type identifier, matching sources.code.drafts."""
    logical=module.get('name') or next((r.get('class_name') for r in module.get('rf',[]) if r.get('class_name')),None)
    name=re.sub(r'[^A-Za-z0-9_]','_',casing.romanize(logical) if logical else ('UnknownModule_'+'M'+sha(module['sourceId'].encode())[:20]))
    return 'Module_'+name if not name or name[0].isdigit() else name


class CodeLayout:
    def __init__(self,engine,overrides=None,known_modules=()):
        self.engine=engine;self.overrides=overrides or {};self.root=self.overrides.get('rootNamespace') or 'Game'
        self.known=sorted({m for m in known_modules if len(m)>=3},key=lambda m:(-len(m),m))
        self.records=[];self._claims={}

    def classify(self,name,bound_module=None):
        """(layer, module parts, reasons). Prefab binding beats name evidence; overrides beat both."""
        override=(self.overrides.get('code') or {}).get(name)
        if override:
            module=[casing.pascal(p) for p in override.get('module',UNCLASSIFIED).split('/')]
            return override['layer'],module,['layout-override']
        if bound_module:return 'Presentation',list(bound_module),['component-binding']
        words=casing.words(name);last=words[-1] if words else ''
        layer=next((layer for layer,tails in LAYER_SUFFIXES if last in tails),None)
        module=next(([m] for m in self.known if name.startswith(m) and name!=m),None)
        reasons=(['name-suffix'] if layer else [])+(['module-prefix'] if module else [])
        return layer or 'Gameplay',module or [UNCLASSIFIED],reasons or ['no-evidence']

    def namespace(self,layer,module):
        return '.'.join([self.root,layer,*[casing.pascal(p) for p in module]])

    def _claim(self,path,sid):
        key=path.casefold()
        if key in self._claims and self._claims[key]!=sid:
            stem,dot,ext=path.rpartition('.');path=stem+'_'+sha(sid.encode())[:6]+dot+ext;key=path.casefold()
        self._claims[key]=sid;return path

    def place(self,sid,name,bound_module=None,language='cs'):
        """Paths for the module slice and its draft; the draft mirrors its future production location."""
        layer,module,reasons=self.classify(name,bound_module)
        creator=language=='ts' or language=='js'
        folders=[casing.pascal(p) for p in module]
        draft_root=standard.RECOVERY['drafts']+('/TypeScript/'+layer if language=='ts' else '/JavaScript/'+layer if language=='js' else '/CSharp/'+layer)
        draft=self._claim('/'.join([draft_root,*folders,name])+'.'+language,sid)
        source=self._claim('/'.join([standard.RECOVERY['modules'],*[casing.pascal(p) for p in module],name])+'.js',sid)
        record=dict(sourceId=sid,className=name,layer=layer,module='/'.join(module),namespace=self.namespace(layer,module),
                    draft=draft,sourceEvidence=source,reasons=reasons)
        self.records.append(record);return record

    def report(self):
        from collections import Counter
        return dict(schemaVersion=1,layout=standard.VERSION,rootNamespace=self.root,modules=len(self.records),
            layers=dict(Counter(r['layer'] for r in self.records)),unclassified=sum(r['module']==UNCLASSIFIED for r in self.records),records=self.records)
