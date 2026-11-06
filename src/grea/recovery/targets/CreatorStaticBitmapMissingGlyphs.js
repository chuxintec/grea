'use strict';

const ownedUndo=require('./owned-import-undo.js');

const POLICY = 'cocos24-bitmap-missing-glyph-skip-v1';
const SOURCE_EVIDENCE = 'cocos2d/core/renderer/utils/label/bmfont.js:235';
const NON_GLYPH_CONTROLS = new Set([10]);

function markerClass(cc) {
    const type = cc && cc.js && cc.js.getClassByName('MonkeyStaticBitmapMissingGlyphs');
    if (!type) throw new Error('BITMAP_MISSING_GLYPH_TYPED_MARKER_CLASS_UNAVAILABLE');
    return type;
}
function fontDefinitions(font, sourceFontId) {
    const dictionary = font && font.fntConfig && font.fntConfig.fontDefDictionary;
    if (!dictionary || typeof dictionary !== 'object' || Array.isArray(dictionary))
        throw new Error(`BITMAP_MISSING_GLYPH_FONT_DEFINITION_UNAVAILABLE:${sourceFontId}`);
    const entries = Object.keys(dictionary).map(key => {
        const value = Number(key);
        if (!Number.isInteger(value) || value < 0 || value > 0x10ffff)
            throw new Error(`BITMAP_MISSING_GLYPH_FONT_CODE_UNIT_INVALID:${sourceFontId}:${key}`);
        return value;
    }).sort((a,b)=>a-b);
    return { dictionary, codeUnits: entries };
}
function displayFor(sourceText, codeUnits) {
    const glyphs = new Set(codeUnits), shown = [], missing = [];
    for (let index=0; index<sourceText.length; index++) {
        const unit = sourceText.charCodeAt(index); // Creator 2.4 String.charAt/charCodeAt behavior.
        if (unit === 13) continue; // Source records the placeholder but does not render it.
        if (glyphs.has(unit) || NON_GLYPH_CONTROLS.has(unit)) shown.push(sourceText.charAt(index));
        else missing.push(unit);
    }
    return { displayText: shown.join(''), missingGlyphUnicode: [...new Set(missing)].sort((a,b)=>a-b) };
}
function labelsOn(node, cc, sourceComponentId) {
    const labels = node && node.getComponents(cc.Label) || [];
    if (labels.length !== 1) throw new Error(`BITMAP_MISSING_GLYPH_LABEL_COMPONENT_AMBIGUOUS:${sourceComponentId}:${labels.length}`);
    return labels[0];
}
function expectedFields(spec, label, font, marker) {
    const fontInfo = fontDefinitions(font, spec.sourceFontId);
    const filtered = displayFor(spec.sourceText, fontInfo.codeUnits);
    if (!same(fontInfo.codeUnits, spec.sourceGlyphUnicode) || !same(filtered.missingGlyphUnicode, spec.missingGlyphUnicode) ||
        filtered.displayText !== spec.displayText)
        throw new Error(`BITMAP_MISSING_GLYPH_SOURCE_COVERAGE_DIFFERS:${spec.sourceComponentId}`);
    if (label.string !== spec.sourceText || label.enabled !== spec.sourceEnabled || label.font !== font ||
        marker.sourceComponentId !== spec.sourceComponentId || marker.sourceNodeId !== spec.sourceNodeId ||
        marker.sourceFontId !== spec.sourceFontId || marker.sourceText !== spec.sourceText ||
        marker.displayText !== spec.displayText || marker.sourceEnabled !== spec.sourceEnabled ||
        marker.policy !== spec.policy || marker.sourceCodeEvidence !== spec.sourceCodeEvidence ||
        marker.missingGlyphsAreVisibleTextRecovered !== false ||
        !same(marker.sourceGlyphUnicode, spec.sourceGlyphUnicode) ||
        !same(marker.missingGlyphUnicode, spec.missingGlyphUnicode) ||
        marker.targetLabel !== label || marker.targetFont !== font)
        throw new Error(`BITMAP_MISSING_GLYPH_TYPED_FIELDS_OR_REFERENCE_DIFFERS:${spec.sourceComponentId}`);
    return fontInfo;
}
function attach(contract, nodes, fonts, cc) {
    validateContract(contract);
    if(!(contract.components||[]).length)return {status:'not_applicable',sourceTextMutated:false,nativeFontSubstituted:false};
    if (!(nodes instanceof Map) || !(fonts instanceof Map)) throw new Error('BITMAP_MISSING_GLYPH_NODE_AND_FONT_MAPS_REQUIRED');
    if(!(contract.components||[]).some(spec=>nodes.has(spec.sourceNodeId)))
        return {status:'not_applicable',sourceTextMutated:false,nativeFontSubstituted:false};
    const Marker = markerClass(cc);
    for (const spec of contract.components || []) {
        if (!nodes.has(spec.sourceNodeId)) continue;
        const node=nodes.get(spec.sourceNodeId), label=labelsOn(node,cc,spec.sourceComponentId), font=fonts.get(spec.sourceFontId);
        if (!font || !(font instanceof cc.BitmapFont)) throw new Error(`BITMAP_MISSING_GLYPH_NATIVE_FONT_MISSING:${spec.sourceFontId}`);
        if (label.font !== font || label.string !== spec.sourceText || label.enabled !== spec.sourceEnabled)
            throw new Error(`BITMAP_MISSING_GLYPH_LABEL_REFERENCE_OR_TEXT_DIFFERS:${spec.sourceComponentId}`);
        const info=fontDefinitions(font,spec.sourceFontId), filtered=displayFor(spec.sourceText,info.codeUnits);
        if (!same(info.codeUnits,spec.sourceGlyphUnicode)||!same(filtered.missingGlyphUnicode,spec.missingGlyphUnicode)||filtered.displayText!==spec.displayText)
            throw new Error(`BITMAP_MISSING_GLYPH_SOURCE_COVERAGE_DIFFERS:${spec.sourceComponentId}`);
        if(node.getComponent(Marker))throw new Error(`BITMAP_MISSING_GLYPH_MARKER_ALREADY_PRESENT:${spec.sourceComponentId}`);
        const marker=node.addComponent(Marker);
        marker.sourceComponentId=spec.sourceComponentId;marker.sourceNodeId=spec.sourceNodeId;
        marker.sourceFontId=spec.sourceFontId;marker.sourceText=spec.sourceText;marker.displayText=spec.displayText;
        marker.sourceEnabled=spec.sourceEnabled;marker.sourceGlyphUnicode=[...spec.sourceGlyphUnicode];
        marker.missingGlyphUnicode=[...spec.missingGlyphUnicode];marker.policy=spec.policy;
        marker.sourceCodeEvidence=spec.sourceCodeEvidence;marker.missingGlyphsAreVisibleTextRecovered=false;
        marker.targetLabel=label;marker.targetFont=font;
        expectedFields(spec,label,font,marker);
    }
    return { status:'attached', sourceTextMutated:false, nativeFontSubstituted:false };
}

function read(contract, persistentNodes, loadedCloneNodes, fonts, cc) {
    validateContract(contract);
    if(!(contract.components||[]).length)return [];
    if (!(persistentNodes instanceof Map)||!(loadedCloneNodes instanceof Map)||!(fonts instanceof Map))
        throw new Error('BITMAP_MISSING_GLYPH_READ_MAPS_REQUIRED');
    const persistentValues=new Set(persistentNodes.values());
    if([...loadedCloneNodes.values()].some(node=>persistentValues.has(node)))
        throw new Error('BITMAP_MISSING_GLYPH_PROBE_REQUIRES_DISPOSABLE_CLONE');
    const scoped=(contract.components||[]).filter(spec=>persistentNodes.has(spec.sourceNodeId));
    if(!scoped.length)return [];
    const Marker=markerClass(cc), rows=[];
    for(const spec of scoped){
        const savedNode=persistentNodes.get(spec.sourceNodeId), savedLabel=labelsOn(savedNode,cc,spec.sourceComponentId);
        const font=fonts.get(spec.sourceFontId), savedMarker=savedNode.getComponent(Marker);
        if(!font||!(font instanceof cc.BitmapFont)||!savedMarker)throw new Error(`BITMAP_MISSING_GLYPH_SAVED_NATIVE_COMPONENT_MISSING:${spec.sourceComponentId}`);
        if(savedMarker.targetLabel!==savedLabel||savedMarker.targetFont!==font||savedLabel.font!==font||savedLabel.string!==spec.sourceText)
            throw new Error(`BITMAP_MISSING_GLYPH_SAVED_LABEL_REFERENCE_OR_TEXT_DIFFERS:${spec.sourceComponentId}`);
        const savedFontInfo=expectedFields(spec,savedLabel,font,savedMarker);

        const loadedNode=loadedCloneNodes.get(spec.sourceNodeId);
        if(!loadedNode)throw new Error(`BITMAP_MISSING_GLYPH_DISPOSABLE_NODE_MISSING:${spec.sourceNodeId}`);
        const loadedLabel=labelsOn(loadedNode,cc,spec.sourceComponentId), loadedMarker=loadedNode.getComponent(Marker);
        if(!loadedMarker)throw new Error(`BITMAP_MISSING_GLYPH_DISPOSABLE_MARKER_MISSING:${spec.sourceComponentId}`);
        const loadedFont=fonts.get(spec.sourceFontId);
        if(loadedLabel.font!==loadedFont||loadedLabel.string!==spec.sourceText)
            throw new Error(`BITMAP_MISSING_GLYPH_DISPOSABLE_LABEL_REFERENCE_OR_TEXT_DIFFERS:${spec.sourceComponentId}`);
        const loadedFontInfo=expectedFields(spec,loadedLabel,loadedFont,loadedMarker);
        rows.push({spec,savedLabel,savedFontInfo,loadedNode,loadedLabel,loadedFontInfo});
    }
    const render=renderProbe(rows,loadedCloneNodes,cc);
    return rows.map(({spec,savedLabel,savedFontInfo,loadedLabel,loadedFontInfo})=>{
        const measured=render.get(spec.sourceComponentId);
        return {
            sourceComponentId:spec.sourceComponentId,sourceNodeId:spec.sourceNodeId,sourceEnabled:savedLabel.enabled,
            sourceFontId:spec.sourceFontId,sourceText:spec.sourceText,targetText:savedLabel.string,
            displayText:measured.displayText,policy:spec.policy,sourceCodeEvidence:spec.sourceCodeEvidence,
            sourceGlyphUnicode:[...savedFontInfo.codeUnits],missingGlyphUnicode:[...spec.missingGlyphUnicode],
            targetSourceComponentId:spec.sourceComponentId,
            targetFontSourceId:savedLabel.font===fonts.get(spec.sourceFontId)?spec.sourceFontId:null,
            targetReferenceVerified:true,targetFontReferenceVerified:true,rendererInstalled:true,
            targetGuid:savedLabel.uuid||null,targetFontGuid:savedLabel.font._uuid||null,
            persistedTargetReferenceVerified:true,persistedFontReferenceVerified:true,
            fontUuid:savedLabel.font._uuid||null,bitmapRenderDataInitialized:measured.initialized,
            vertexCount:measured.vertexCount,indexCount:measured.indexCount,zeroVisibleVertices:measured.vertexCount===0,
            missingGlyphsAreVisibleTextRecovered:false,
        };
    });
}

function renderProbe(rows,nodes,cc) {
    const scene=new cc.Scene('BitmapMissingGlyphProbeScene');ownedUndo.registerRoot(scene);
    const context=new cc.Node('BitmapMissingGlyphProbeRoot');ownedUndo.registerRoot(context);
    scene.active=true;context.active=true;
    let activated=false;
    const mapped=new Set(nodes.values());
    const roots=[...mapped].filter(node=>!node.parent||!mapped.has(node.parent));
    const result=new Map();
    try {
        if(typeof cc.UITransform==='function')context.addComponent(cc.UITransform);
        context.parent=scene;
        for(const root of roots)root.parent=context;
        for(const row of rows){
            for(let current=row.loadedNode;current&&mapped.has(current);current=current.parent)current.active=true;
        }
        scene._load();scene._activate(true);activated=true;
        // Claim the attached disposable tree, including all supplied clone roots.
        ownedUndo.registerRoot(scene);
        for(const row of rows){
            const {spec,loadedNode,loadedLabel,loadedFontInfo}=row;
            if(loadedNode.activeInHierarchy!==true)throw new Error(`BITMAP_MISSING_GLYPH_PROBE_NODE_NOT_ACTIVE:${spec.sourceNodeId}`);
            const data=initializeLabelMesh(loadedLabel,spec.sourceComponentId);
            const display=displayFor(spec.sourceText,loadedFontInfo.codeUnits);
            const expectedVertices=expectedVisibleVertices(display.displayText,loadedFontInfo.dictionary);
            if(data.vertexCount!==expectedVertices)
                throw new Error(`BITMAP_MISSING_GLYPH_NATIVE_VERTEX_COUNT_DIFFERS:${spec.sourceComponentId}:${data.vertexCount}/${expectedVertices}`);
            if(display.displayText===''&&data.vertexCount!==0)
                throw new Error(`BITMAP_MISSING_GLYPH_EMPTY_SOURCE_TEXT_RENDERED_VERTICES:${spec.sourceComponentId}`);
            result.set(spec.sourceComponentId,{displayText:display.displayText,initialized:true,
                vertexCount:data.vertexCount,indexCount:data.indexCount});
        }
    } finally {
        if(activated)scene._activate(false);
        for(const root of roots)if(root.parent)root.parent=null;
        if(typeof scene.destroy==='function')scene.destroy();
    }
    return result;
}

function initializeLabelMesh(label,sourceComponentId) {
    if(typeof label._flushAssembler==='function'&&!label.renderData)label._flushAssembler();
    const data=label.renderData||label._renderData;
    if(!data)throw new Error(`BITMAP_MISSING_GLYPH_RENDER_DATA_MISSING:${sourceComponentId}`);
    data.vertDirty=true;
    if(label._assembler&&typeof label._assembler.updateRenderData==='function')label._assembler.updateRenderData(label);
    else if(typeof label.updateRenderData==='function')label.updateRenderData(true);
    else throw new Error(`BITMAP_MISSING_GLYPH_NATIVE_ASSEMBLER_MISSING:${sourceComponentId}`);
    const ready=label.renderData||label._renderData;
    if(!ready||!Number.isInteger(ready.vertexCount)||!Number.isInteger(ready.indexCount))
        throw new Error(`BITMAP_MISSING_GLYPH_RENDER_DATA_UNINITIALIZED:${sourceComponentId}`);
    return {vertexCount:ready.vertexCount,indexCount:ready.indexCount};
}
function expectedVisibleVertices(displayText,dictionary) {
    let count=0;
    for(let index=0;index<displayText.length;index++){
        const glyph=dictionary[String(displayText.charCodeAt(index))];
        if(glyph&&glyph.rect&&glyph.rect.width>0&&glyph.rect.height>0)count++;
    }
    return count*4;
}
function validateContract(contract) {
    if(!contract||contract.schema!=='monkey-prefab-bitmap-missing-glyphs/1'||contract.policy!==POLICY||
        contract.sourceCodeEvidence!==SOURCE_EVIDENCE||contract.missingGlyphsAreVisibleTextRecovered!==false||
        (contract.components||[]).some(spec=>!spec||spec.policy!==POLICY||spec.sourceCodeEvidence!==SOURCE_EVIDENCE||
            spec.missingGlyphsAreVisibleTextRecovered!==false||!Array.isArray(spec.sourceGlyphUnicode)||!Array.isArray(spec.missingGlyphUnicode)))
        throw new Error('BITMAP_MISSING_GLYPH_CONTRACT_INVALID');
}
function same(a,b) {
    return Array.isArray(a)&&Array.isArray(b)&&a.length===b.length&&a.every((value,index)=>value===b[index]);
}
module.exports={attach,read,displayFor,fontDefinitions,initializeLabelMesh};
