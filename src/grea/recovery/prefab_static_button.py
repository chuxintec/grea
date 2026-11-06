"""Source-pinned static color-button fields; input events are never executed."""
from pathlib import Path
from . import io
from .prefab_static_toggle import _resolve_component,_pick,_color
from .sources.compiled import fail

DEFAULT_SOURCE='https://github.com/cocos/cocos-engine/blob/v2.4.15/cocos2d/core/components/CCButton.js'
DEFAULT_COLORS={'normalColor':[255,255,255,255],'hoverColor':[255,255,255,255],
                'pressedColor':[211,211,211,255],'disabledColor':[124,124,124,255]}

def enrich(ir):
    if ir.get('sourceProfile') not in ('cocos-2.4.15-bundle','cocos-2.4.15-project'):return
    rows=[c for c in ir['components']if c['type']=='cc.Button'and c.get('transition') in (0,1,3)]
    if not rows or not ir.get('sourceManifestPath'):return
    raw=io.stage_bytes(Path(ir['sourceManifestPath']))
    if io.sha(raw)!=ir.get('sourceManifestSha256'):fail('BUTTON_SOURCE_CHANGED',ir['sourceManifestPath'],'Frozen source changed')
    manifest=io.load(raw,max_nodes=8_000_000)
    for c in rows:
        source,node,_=_resolve_component(manifest,c['sourceId'],'cc.Button')
        if node!=c['node']:fail('BUTTON_NODE_CHANGED',c['sourceId'],'Source node differs')
        spec={'sourceId':c['sourceId'],'sourceNodeId':node,'sourceEnabled':c.get('enabled',True),
              'sourceTransition':c['transition'],'sourceZoomScale':c.get('zoomScale',1.2),'sourceFields':source,'defaultsSource':DEFAULT_SOURCE,'behavior':'disabled','eventsBound':False}
        for name,default in DEFAULT_COLORS.items():
            present,value,_=_pick(source,('_N$'+name,name),name)
            if present:
                v=_color(value,name);spec[name]=[v[k]for k in ('r','g','b','a')]
            else:spec[name]=list(default)
        spec['autoGray']=bool(source.get('enableAutoGrayEffect',False))
        # Nondefault disabled grayscale requires separate native material semantics.
        spec['renderReady']=not spec['autoGray']
        c['staticButtonBinding']=spec
