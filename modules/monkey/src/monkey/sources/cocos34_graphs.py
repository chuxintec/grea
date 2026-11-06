"""Creator 3.4.1 Node/UI defaults and serialization, audited independently.

Shared projections are used only after checking v3.4.1 Node, UITransform,
UIOpacity, Renderable2D, Sprite, Label, Widget and Layout declarations. This is
not a source version alias. Unknown components remain explicit source data.
"""
from . import cocos38_graphs

PROFILE='cocos-3.4.1-node-ui-v1'
BASELINE='https://github.com/cocos/cocos-engine/tree/v3.4.1/cocos'


def graph(asset):
    return cocos38_graphs.graph(asset,profile=PROFILE,version='3.4.1')


def resolved_graph(asset,resolver):
    return cocos38_graphs.resolved_graph(asset,resolver,profile=PROFILE,version='3.4.1')
