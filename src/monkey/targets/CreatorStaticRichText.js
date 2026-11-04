/* Apply a validated serialized static cc.RichText projection. No script lookup,
 * event registration, image resolution, or source behavior execution occurs. */
'use strict';

const SCHEMA = 'monkey-static-richtext/1';

function apply(component, spec) {
    if (!component || !spec || spec.schema !== SCHEMA || spec.staticOnly !== true ||
        spec.convertible !== true || spec.renderReady !== true || spec.richText !== true) {
        throw new Error('RichText is not a validated static projection: ' +
            (spec && spec.sourceId || '<missing>'));
    }
    if (!(spec.fontSize > 0) || !(spec.lineHeight > 0) || !(spec.maxWidth >= 0) ||
        !Number.isInteger(spec.horizontalAlign) || spec.horizontalAlign < 0 || spec.horizontalAlign > 2 ||
        !Number.isInteger(spec.verticalAlign) || spec.verticalAlign < 0 || spec.verticalAlign > 2) {
        throw new Error('Static RichText metrics are outside the supported contract: ' + spec.sourceId);
    }
    if (!spec.fontBinding || !spec.fontBinding.nativeFontAssetId ||
        !Array.isArray(spec.fontBinding.nativeFallbackAssetIds)) {
        throw new Error('An explicit source-backed font/fallback binding is required before static RichText: ' + spec.sourceId);
    }
    if (!component.font && (!spec.fontBinding.targetSystemFontFamily ||
        component.fontFamily !== spec.fontBinding.targetSystemFontFamily)) {
        throw new Error('No mapped Creator font or evidenced target system family is assigned: ' + spec.sourceId);
    }
    component.string = spec.creatorMarkup;
    component.fontSize = spec.fontSize;
    component.lineHeight = spec.lineHeight;
    component.maxWidth = spec.maxWidth;
    component.horizontalAlign = spec.horizontalAlign;
    component.verticalAlign = spec.verticalAlign;
    // Preserve the font and fallback chain assigned by the plan. The source
    // default family is provenance, not permission to choose host Arial.
    component.handleTouchEvent = false;
    component.enabled = spec.componentEnabled !== false;
    return component;
}

function sourceChildren(node){
    const cc=require('cc');
    const withoutSortProxy=node.children.filter(child=>!isGeneratedSortProxyRoot(child));
    if(!node.getComponent(cc.RichText))return withoutSortProxy;
    // Creator 3.8.8 rich-text.ts creates these hidden, nonserialized segments.
    return withoutSortProxy.filter(c=>!((c.name==='RICHTEXT_CHILD'||c.name==='RICHTEXT_Image_CHILD')&&c.hideFlags));
}
function isGeneratedSortProxyRoot(node){
    const cc=require('cc');
    const markerType=cc.js&&cc.js.getClassByName&&cc.js.getClassByName('MonkeyStaticSortQueueProxyMarker');
    const marker=markerType&&node?node.getComponent(markerType):null;
    if(!marker||marker.kind!=='root')return false;
    const api=cc.js&&cc.js.getClassByName&&cc.js.getClassByName('MonkeyStaticSortQueueProxyApi');
    if(!api||typeof api.isGeneratedProxyRoot!=='function')throw Error('Static sort proxy API is not registered while source hierarchy contains a generated root');
    return !!api.isGeneratedProxyRoot(node);
}
module.exports = { schema: SCHEMA, apply, sourceChildren, isGeneratedSortProxyRoot };
