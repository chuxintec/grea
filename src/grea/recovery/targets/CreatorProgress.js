'use strict';
const cc=require('cc');
function sprite(spec,nodes) {
    if(spec.presentationPolicy!=='native-horizontal-tiled-progress-v1')throw Error('Unsupported progress policy');
    const node=nodes.get(spec.barNode),items=node&&node.getComponents(cc.Sprite);
    if(!items||items.length!==1)throw Error('Progress Sprite identity is absent or ambiguous');
    return items[0];
}
function bind(component,spec,nodes) {
    component.mode=cc.ProgressBar.Mode.HORIZONTAL;
    component.reverse=false;
    component.barSprite=sprite(spec,nodes);
    component.totalLength=spec.totalLength;
    component.progress=spec.progress;
}
function read(component,spec,nodes) {
    if(component.barSprite!==sprite(spec,nodes)||component.mode!==cc.ProgressBar.Mode.HORIZONTAL||
       component.reverse!==false||component.enabled!==spec.enabled||
       Math.abs(component.totalLength-spec.totalLength)>1e-6||Math.abs(component.progress-spec.progress)>1e-6)
        throw Error('Saved native progress fields or Sprite reference differ: '+spec.sourceId);
    const ui=component.barSprite.node.getComponent(cc.UITransform);
    if(!ui||Math.abs(ui.width-spec.totalLength*spec.progress)>.001)
        throw Error('Saved native progress width differs: '+spec.sourceId);
}
module.exports={bind,read};
