"""Controlled, offline source-side Cocos Creator 2.4.15 Label references.

The browser runner loads a pinned Cocos runtime and creates only the requested
Label/LabelOutline objects. It never loads project JavaScript or game business
code. Browser measurements describe the declared capture environment; they do
not claim the original device's OS font selection or raster output.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import math
import os
import platform
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import quote, unquote

from . import io
from . import prefab_static_text_continuation as static_text
from .prefab_static_text_continuation import (
    SCHEMA as TEXT_SCHEMA,
    SOURCE_PROFILE,
    SOURCE_VERSION,
    StaticTextContinuationError,
    _source_engine_pins,
)


SCHEMA = "monkey-cocos-source-text-reference/1"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_MAX_REQUEST_BYTES = 8 * 1024 * 1024
_MAX_DOC_BYTES = 128 * 1024 * 1024
_MAX_RUNTIME_BYTES = 256 * 1024 * 1024
_MAX_FONT_BYTES = 64 * 1024 * 1024
_MAX_CASES = 256
_MAX_TEXT_BYTES = 64 * 1024


class SourceTextReferenceError(ValueError):
    pass


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _css_string(value: str) -> str:
    escaped = (value.replace("\\", "\\\\").replace('"', '\\"')
               .replace("\r", "\\d ").replace("\n", "\\a ").replace("<", "\\3C "))
    return '"' + escaped + '"'


def _load_json(raw: bytes, name: str) -> dict:
    try:
        value = io.load(raw, max_nodes=2_000_000)
    except Exception as error:
        raise SourceTextReferenceError(f"{name} is not strict JSON: {error}") from error
    if not isinstance(value, dict):
        raise SourceTextReferenceError(f"{name} must be a JSON object")
    return value


def _pinned_file(spec: object, name: str, *, max_bytes: int, required_keys=("path", "sha256")):
    if not isinstance(spec, dict) or set(spec) != set(required_keys):
        raise SourceTextReferenceError(f"{name} must contain exactly {', '.join(required_keys)}")
    path_text, digest = spec.get("path"), spec.get("sha256")
    if not isinstance(path_text, str) or not Path(path_text).is_absolute():
        raise SourceTextReferenceError(f"{name}.path must be absolute")
    if not isinstance(digest, str) or not _SHA.fullmatch(digest):
        raise SourceTextReferenceError(f"{name}.sha256 must be lowercase SHA-256")
    path = io.safe(path_text)
    raw = io.read(path, max_bytes=max_bytes)
    if _digest(raw) != digest:
        raise SourceTextReferenceError(f"{name} bytes differ from SHA-256")
    if "bytes" in required_keys and (type(spec.get("bytes")) is not int or spec["bytes"] != len(raw)):
        raise SourceTextReferenceError(f"{name}.bytes differs from file length")
    return path, raw


def _read_plan_inputs(request: dict):
    plan_path, plan_raw = _pinned_file(request.get("sourcePlan"), "sourcePlan", max_bytes=_MAX_DOC_BYTES)
    ir_path, ir_raw = _pinned_file(request.get("sourceIr"), "sourceIr", max_bytes=_MAX_DOC_BYTES)
    manifest_path, manifest_raw = _pinned_file(request.get("sourceManifest"), "sourceManifest", max_bytes=_MAX_DOC_BYTES)
    evidence_path, evidence_raw = _pinned_file(request.get("sourceEngineEvidence"), "sourceEngineEvidence", max_bytes=4 * 1024 * 1024)
    plan, ir, manifest, evidence = (
        _load_json(plan_raw, "sourcePlan"), _load_json(ir_raw, "sourceIr"),
        _load_json(manifest_raw, "sourceManifest"), _load_json(evidence_raw, "sourceEngineEvidence"),
    )
    if manifest.get("sourceVersion") != SOURCE_VERSION or manifest.get("sourceProfile") != SOURCE_PROFILE:
        raise SourceTextReferenceError("SOURCE_MANIFEST_PROFILE_OR_VERSION_MISMATCH")
    manifest_sha = _digest(manifest_raw)
    if plan.get("sourceManifestSha256") != manifest_sha or ir.get("sourceManifestSha256") != manifest_sha:
        raise SourceTextReferenceError("SOURCE_PLAN_IR_MANIFEST_PIN_MISMATCH")
    if ir.get("sourceProfile") != SOURCE_PROFILE:
        raise SourceTextReferenceError("SOURCE_IR_PROFILE_MISMATCH")
    if plan.get("sourceIrSha256") != _digest(ir_raw):
        raise SourceTextReferenceError("SOURCE_PLAN_IR_PIN_MISMATCH")
    if evidence.get("sourceVersion") != SOURCE_VERSION:
        raise SourceTextReferenceError("SOURCE_ENGINE_EVIDENCE_VERSION_MISMATCH")
    try:
        engine_files = _source_engine_pins(evidence)
    except StaticTextContinuationError as error:
        raise SourceTextReferenceError(str(error)) from error
    return {
        "planPath": plan_path, "planRaw": plan_raw, "plan": plan,
        "irPath": ir_path, "irRaw": ir_raw, "ir": ir,
        "manifestPath": manifest_path, "manifestRaw": manifest_raw, "manifest": manifest,
        "evidencePath": evidence_path, "evidenceRaw": evidence_raw,
        "engineFiles": engine_files, "sourceEngineEvidence": evidence,
    }


def _plan_fragment(plan: dict) -> dict:
    value = plan.get("staticTextContinuation")
    if not isinstance(value, dict):
        raw = plan.get("staticTextContinuationJson")
        if isinstance(raw, str):
            try:
                value = json.loads(raw)
            except ValueError as error:
                raise SourceTextReferenceError("SOURCE_TEXT_CONTINUATION_JSON_INVALID") from error
    if (not isinstance(value, dict) or value.get("contract") != TEXT_SCHEMA or
            value.get("schemaVersion") != 1 or not isinstance(value.get("components"), list)):
        raise SourceTextReferenceError("SOURCE_TEXT_CONTINUATION_UNSUPPORTED")
    if value.get("sourceManifestSha256") != plan.get("sourceManifestSha256"):
        raise SourceTextReferenceError("SOURCE_TEXT_CONTINUATION_MANIFEST_PIN_MISMATCH")
    return value


def _font_inputs(request: dict, plan: dict, manifest: dict, groups: list[dict]):
    specs = request.get("sourceFontFiles", [])
    if not isinstance(specs, list):
        raise SourceTextReferenceError("SOURCE_FONT_FILES_INVALID")
    by_id = {}
    copied = []
    for index, spec in enumerate(specs):
        if not isinstance(spec, dict) or set(spec) != {"sourceFontId", "path", "sha256", "bytes", "familyName"}:
            raise SourceTextReferenceError(f"sourceFontFiles[{index}] contract is invalid")
        asset_id, family = spec.get("sourceFontId"), spec.get("familyName")
        if not isinstance(asset_id, str) or not asset_id or asset_id in by_id:
            raise SourceTextReferenceError("SOURCE_FONT_ID_DUPLICATE_OR_MISSING")
        if not isinstance(family, str) or not family.strip() or len(family) > 256:
            raise SourceTextReferenceError("SOURCE_FONT_FAMILY_INVALID")
        path, raw = _pinned_file(spec, f"sourceFontFiles[{index}]", max_bytes=_MAX_FONT_BYTES,
                                 required_keys=("sourceFontId", "path", "sha256", "bytes", "familyName"))
        by_id[asset_id] = {"path": path, "sha256": spec["sha256"], "bytes": len(raw),
                           "familyName": family, "raw": raw}
    plan_rows = {}
    for row in plan.get("components", []) if isinstance(plan.get("components"), list) else []:
        if isinstance(row, dict) and isinstance(row.get("sourceId"), str):
            plan_rows.setdefault(row["sourceId"], []).append(row)
    component_origins = {}
    sync_bindings = plan.get("syncPrefabBindings", [])
    for sync in sync_bindings if isinstance(sync_bindings, list) else []:
        if not isinstance(sync, dict):
            continue
        for origin in sync.get("componentOrigins", []) if isinstance(sync.get("componentOrigins"), list) else []:
            if isinstance(origin, dict) and isinstance(origin.get("instanceSourceId"), str) and isinstance(origin.get("templateSourceId"), str):
                component_origins.setdefault(origin["instanceSourceId"], set()).add(origin["templateSourceId"])

    def canonical_source(source_id):
        seen = set()
        current = source_id
        while current in component_origins:
            targets = component_origins[current]
            if current in seen or len(targets) != 1:
                return None
            seen.add(current)
            current = next(iter(targets))
        return current
    selected_files = {}
    gaps = []
    cases = []
    for group in groups:
        label_id = group.get("sourceLabelId")
        matches = plan_rows.get(label_id, [])
        if len(matches) != 1:
            gaps.append({"code": "SOURCE_LABEL_PLAN_ID_NOT_UNIQUE", "sourceId": label_id})
            continue
        source = matches[0]
        kind = group.get("fontKind")
        source_font_id = source.get("sourceFont")
        raw_source_id = canonical_source(label_id)
        raw_label, raw_node = (static_text._source_component(manifest, raw_source_id, "cc.Label")
                               if raw_source_id else (None, None))
        if not isinstance(raw_label, dict):
            gaps.append({"code": "SOURCE_LABEL_SERIALIZED_DOCUMENT_UNRESOLVED", "sourceId": label_id})
            continue
        cache_mode = static_text._effective_label_source(raw_label)["cacheMode"]
        if cache_mode != 0:
            gaps.append({"code": "SOURCE_LABEL_CACHE_MODE_NOT_SUPPORTED_BY_TTF_RUNNER",
                         "sourceId": label_id, "cacheMode": cache_mode})
            continue
        if group.get("sourceEnabled") is not True:
            gaps.append({"code": "SOURCE_DISABLED_LABEL_HAS_NO_VISIBLE_RENDER_REFERENCE", "sourceId": label_id})
            continue
        if kind == "bitmap-font":
            gaps.append({"code": "SOURCE_BITMAP_FONT_RUNTIME_ASSET_CONTRACT_MISSING", "sourceId": label_id,
                         "sourceFontId": source_font_id})
            continue
        face = group.get("sourceFontFamily")
        font_asset = None
        if kind == "explicit-ttf":
            font_asset = by_id.get(source_font_id)
            if font_asset is None:
                gaps.append({"code": "SOURCE_TTF_FONT_BYTES_NOT_PINNED", "sourceId": label_id,
                             "sourceFontId": source_font_id})
                continue
            face = font_asset["familyName"]
            selected_files[source_font_id] = font_asset
        elif kind != "system-font":
            gaps.append({"code": "SOURCE_FONT_KIND_UNSUPPORTED", "sourceId": label_id,
                         "fontKind": kind})
            continue
        if not isinstance(face, str) or not face.strip():
            gaps.append({"code": "SOURCE_FONT_FAMILY_MISSING", "sourceId": label_id})
            continue
        source_text = group.get("sourceText")
        if not isinstance(source_text, str) or len(source_text.encode("utf-8")) > _MAX_TEXT_BYTES:
            gaps.append({"code": "SOURCE_TEXT_CASE_INVALID_OR_EXCEEDS_BUDGET", "sourceId": label_id})
            continue
        if (not isinstance(group.get("sourceNodeSize"), list) or len(group["sourceNodeSize"]) != 2 or
                not all(isinstance(value, (int, float)) and math.isfinite(float(value)) and float(value) >= 0 for value in group["sourceNodeSize"]) or
                not isinstance(group.get("sourceNodePivot"), list) or len(group["sourceNodePivot"]) != 2 or
                not isinstance(group.get("sourceNodeColor"), list) or len(group["sourceNodeColor"]) != 4):
            gaps.append({"code": "SOURCE_TEXT_NODE_GEOMETRY_INVALID", "sourceId": label_id})
            continue
        cases.append({
            "sourceLabelId": label_id,
            "sourceOutlineId": group.get("sourceOutlineId"),
            "sourceNodeId": group.get("sourceNodeId"),
            "sourceText": source_text,
            "sourceTextSha256": group.get("sourceTextSha256"),
            "fontKind": kind,
            "sourceFontId": source_font_id,
            "sourceFontFamily": face,
            "sourceFontFamilyEvidence": group.get("sourceFontFamilyEvidence"),
            "sourceSystemFont": kind == "system-font",
            "controlledFontStrategy": "browser-system-font-mapping" if kind == "system-font" else "pinned-ttf-css-face",
            "sourceFontSize": group.get("sourceFontSize"),
            "sourceLineHeight": group.get("sourceLineHeight"),
            "sourceOverflow": group.get("sourceOverflow"),
            "sourceWrap": group.get("sourceWrap"),
            "sourceBold": group.get("sourceBold"),
            "sourceItalic": group.get("sourceItalic"),
            "sourceUnderline": group.get("sourceUnderline"),
            "sourceEnabled": group.get("sourceEnabled"),
            "sourceNodeSize": group.get("sourceNodeSize"),
            "sourceNodePivot": group.get("sourceNodePivot"),
            "sourceNodeColor": group.get("sourceNodeColor"),
            "sourceNodeOpacity": next((node.get("opacity", 255) for node in plan.get("nodes", [])
                                         if isinstance(node, dict) and node.get("sourceId") == group.get("sourceNodeId")), 255),
            "sourceOutlineEnabled": group.get("sourceOutlineEnabled"),
            "sourceOutlineWidth": group.get("sourceOutlineWidth"),
            "sourceOutlineColor": group.get("sourceOutlineColor"),
            "sourceCacheMode": cache_mode,
            "horizontalAlign": source.get("horizontalAlign", 0),
            "verticalAlign": source.get("verticalAlign", 0),
            "fontAssetSha256": font_asset["sha256"] if font_asset else None,
            "fontAssetBytes": font_asset["bytes"] if font_asset else None,
        })
    if len(cases) > _MAX_CASES:
        raise SourceTextReferenceError("SOURCE_TEXT_CASE_BUDGET_EXCEEDED")
    return cases, selected_files, gaps


def _runner_html(cases: list[dict], *, runtime_name: str | None, viewport: dict, source_manifest_sha: str):
    spec = {"sourceVersion": SOURCE_VERSION, "sourceManifestSha256": source_manifest_sha,
            "viewport": viewport, "cases": cases}
    encoded = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    encoded = re.sub(r"</", r"<\/", encoded).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    runtime_tag = (f'<script src="{html.escape(runtime_name, quote=True)}"></script>'
                   if runtime_name else "")
    return f'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<style>html,body,#GameDiv,#Cocos2dGameContainer{{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:transparent}}#source-reference-result{{display:none}}</style></head>
<body><div id="GameDiv"><canvas id="GameCanvas"></canvas></div>
<pre id="source-reference-result"></pre>{runtime_tag}
<script>
(function(){{
 const S={encoded}; const output=document.getElementById('source-reference-result');
 function finish(value){{ output.textContent=JSON.stringify(value); document.body.setAttribute('data-source-reference-result',encodeURIComponent(output.textContent)); }}
 function fail(code,message){{ finish({{contract:'monkey-cocos-source-text-reference-capture/1',status:'failed',sourceVersion:S.sourceVersion,error:{{code,message:String(message||'')}} ,cases:[]}}); }}
 try {{
   if(!window.cc){{fail('COCOS_RUNTIME_NOT_LOADED','Pinned Cocos runtime did not expose window.cc');return;}}
   if(cc.ENGINE_VERSION!==S.sourceVersion){{fail('COCOS_ENGINE_VERSION_MISMATCH',String(cc.ENGINE_VERSION));return;}}
   if(!cc.game||!cc.Label||!cc.Scene||!cc.Node){{fail('COCOS_RUNTIME_API_INCOMPLETE','Required Cocos 2.4 APIs are absent');return;}}
   const sourceCase=S.cases[0], sourceCanvasCalls=new Map();
   function recordContext(context){{
     let record=sourceCanvasCalls.get(context.canvas);
     if(!record){{record={{canvas:context.canvas,measures:[],draws:[]}};sourceCanvasCalls.set(context.canvas,record);}}
     return record;
   }}
   const canvasPrototype=window.CanvasRenderingContext2D&&CanvasRenderingContext2D.prototype;
   if(!canvasPrototype||typeof canvasPrototype.measureText!=='function'){{fail('SOURCE_CANVAS_2D_UNAVAILABLE','CanvasRenderingContext2D.measureText is unavailable');return;}}
   const originalMeasureText=canvasPrototype.measureText;
   canvasPrototype.measureText=function(text){{
     const metrics=originalMeasureText.apply(this,arguments);
     if(String(text)===sourceCase.sourceText){{
       const row=recordContext(this);row.measures.push({{text:String(text),font:this.font,width:metrics.width,
         actualBoundingBoxLeft:metrics.actualBoundingBoxLeft||0,actualBoundingBoxRight:metrics.actualBoundingBoxRight||0,
         actualBoundingBoxAscent:metrics.actualBoundingBoxAscent||0,actualBoundingBoxDescent:metrics.actualBoundingBoxDescent||0}});
     }}
     return metrics;
   }};
   for(const drawName of ['fillText','strokeText']){{
     const originalDraw=canvasPrototype[drawName];
     if(typeof originalDraw==='function')canvasPrototype[drawName]=function(text){{
       const result=originalDraw.apply(this,arguments);
       if(String(text)===sourceCase.sourceText){{const row=recordContext(this);row.draws.push({{method:drawName,text:String(text),font:this.font}});}}
       return result;
     }};
   }}
   const explicitGameConfig={{id:'GameCanvas',frameRate:60,renderMode:1,
     debugMode:0,showFPS:false,width:S.viewport.width,height:S.viewport.height,exposeClassName:false}};
   cc.game.renderType=cc.game.RENDER_TYPE_CANVAS;
   cc.game.onStart=function(){{
     try {{
       cc.view.enableRetina(true);
       cc.view.setDesignResolutionSize(S.viewport.width,S.viewport.height,cc.ResolutionPolicy.SHOW_ALL);
       if(cc.game.renderType!==cc.game.RENDER_TYPE_CANVAS)throw new Error('COCOS_CANVAS_RENDERER_NOT_ACTIVE');
       const scene=new cc.Scene(), rows=[];
       for(const c of S.cases){{
         const node=new cc.Node('source-reference-'+c.sourceLabelId);
         node.setContentSize(c.sourceNodeSize[0],c.sourceNodeSize[1]);
         node.setAnchorPoint(c.sourceNodePivot[0],c.sourceNodePivot[1]);
         node.setPosition(S.viewport.width/2,S.viewport.height/2);
         node.color=cc.color.apply(null,c.sourceNodeColor); node.opacity=c.sourceNodeOpacity;
         const label=node.addComponent(cc.Label);
         label.string=c.sourceText; label.fontSize=c.sourceFontSize; label.lineHeight=c.sourceLineHeight;
         label.overflow=c.sourceOverflow; label.enableWrapText=c.sourceWrap;
         label.enableBold=c.sourceBold; label.enableItalic=c.sourceItalic; label.enableUnderline=c.sourceUnderline;
         label.horizontalAlign=c.horizontalAlign; label.verticalAlign=c.verticalAlign;
         label.cacheMode=cc.Label.CacheMode.NONE; label.useSystemFont=true; label.fontFamily=c.sourceFontFamily;
         label.enabled=c.sourceEnabled;
         if(c.sourceOutlineId){{
           const outline=node.addComponent(cc.LabelOutline); outline.width=c.sourceOutlineWidth;
           outline.color=cc.color.apply(null,c.sourceOutlineColor||[255,255,255,255]); outline.enabled=c.sourceOutlineEnabled;
         }}
         scene.addChild(node); rows.push({{case:c,node:node,label:label}});
       }}
       cc.director.runScene(scene);
       let frames=0;
       function collect(){{
         if(++frames<4){{window.setTimeout(collect,50);return;}}
         try {{
           const canvas=document.getElementById('GameCanvas');
           const captured=rows.map(item=>{{
             const c=item.case,label=item.label;
             const calls=Array.from(sourceCanvasCalls.values()).filter(row=>row.measures.length||row.draws.length);
             const sourceCalls=calls.flatMap(row=>row.measures).filter(row=>row.text===c.sourceText);
             if(!sourceCalls.length)throw new Error('SOURCE_CANVAS_MEASURETEXT_NOT_OBSERVED:'+c.sourceLabelId);
             if(!calls.some(row=>row.draws.length))throw new Error('SOURCE_CANVAS_TEXT_RASTER_NOT_OBSERVED:'+c.sourceLabelId);
             const metrics=sourceCalls[sourceCalls.length-1];
             const lines=String(c.sourceText).split('\\n').map(text=>{{
               const rows=calls.flatMap(row=>row.measures).filter(row=>row.text===text);
               const m=rows.length?rows[rows.length-1]:metrics;
               return {{text:text,width:m.width,actualBoundingBoxLeft:m.actualBoundingBoxLeft,
                 actualBoundingBoxRight:m.actualBoundingBoxRight,actualBoundingBoxAscent:m.actualBoundingBoxAscent,
                 actualBoundingBoxDescent:m.actualBoundingBoxDescent}};
             }});
             const canvasRows=calls.filter(row=>row.draws.length).map(row=>({{width:row.canvas.width,height:row.canvas.height,
               draws:row.draws,measureCount:row.measures.length,png:row.canvas.toDataURL?row.canvas.toDataURL('image/png'):null}}));
             let pixels=canvasRows.length?canvasRows[0].png:null;
             if(pixels&&pixels.length>33554432)pixels=null;
             return {{sourceLabelId:c.sourceLabelId,sourceOutlineId:c.sourceOutlineId,sourceNodeId:c.sourceNodeId,
               sourceText:c.sourceText,sourceTextSha256:c.sourceTextSha256,fontKind:c.fontKind,sourceFontId:c.sourceFontId,
               sourceSystemFont:c.sourceSystemFont,engineUseSystemFont:true,controlledFontStrategy:c.controlledFontStrategy,
               fontAssetSha256:c.fontAssetSha256,fontAssetBytes:c.fontAssetBytes,
               requestedFontFamily:c.sourceFontFamily,contextFont:metrics.font,fontAvailable:document.fonts?document.fonts.check(metrics.font,c.sourceText):null,
               sourceFontSize:c.sourceFontSize,actualFontSize:label.actualFontSize,lineHeight:c.sourceLineHeight,
               overflow:c.sourceOverflow,wrap:c.sourceWrap,bold:c.sourceBold,italic:c.sourceItalic,underline:c.sourceUnderline,
               sourceOutlineEnabled:c.sourceOutlineEnabled,outlineWidth:c.sourceOutlineWidth,outlineColor:c.sourceOutlineColor,
               nodeWidth:item.node.width,nodeHeight:item.node.height,nodeAnchor:[item.node.anchorX,item.node.anchorY],
               actualCanvasWidth:canvasRows.length?canvasRows[0].width:0,actualCanvasHeight:canvasRows.length?canvasRows[0].height:0,
               sourceCanvasMeasureCount:sourceCalls.length,sourceCanvasDraws:canvasRows.map(row=>row.draws),
               measureText:{{width:metrics.width,actualBoundingBoxLeft:metrics.actualBoundingBoxLeft,actualBoundingBoxRight:metrics.actualBoundingBoxRight,
                 actualBoundingBoxAscent:metrics.actualBoundingBoxAscent,actualBoundingBoxDescent:metrics.actualBoundingBoxDescent}},lines:lines,rasterDataUrl:pixels}};
           }});
           finish({{contract:'monkey-cocos-source-text-reference-capture/1',status:'captured',sourceVersion:cc.ENGINE_VERSION,
             sourceManifestSha256:S.sourceManifestSha256,browser:{{userAgent:navigator.userAgent,platform:navigator.platform,language:navigator.language,
               devicePixelRatio:window.devicePixelRatio,innerWidth:window.innerWidth,innerHeight:window.innerHeight,
               screenWidth:screen.width,screenHeight:screen.height,fontSetStatus:document.fonts?document.fonts.status:'unsupported'}},
             renderMode:'cocos-label-ttf-canvas-assembler',actualRendererType:cc.game.renderType===cc.game.RENDER_TYPE_CANVAS?'canvas':'other',cases:captured}});
         }} catch(error){{fail('SOURCE_LABEL_CAPTURE_FAILED',error&&error.message||error);}}
       }}
     window.setTimeout(collect,250);
     }} catch(error){{fail('COCOS_GAME_START_FAILED',error&&error.message||error);}}
   }};
   const fontLoads=Promise.all(S.cases.map(c=>document.fonts&&document.fonts.load?document.fonts.load(
     (c.sourceBold?'bold ':'')+(c.sourceItalic?'italic ':'')+c.sourceFontSize+'px "'+c.sourceFontFamily+'"',c.sourceText):Promise.resolve()));
   fontLoads.then(()=>cc.game.run(explicitGameConfig,cc.game.onStart)).catch(error=>fail('SOURCE_FONT_LOAD_FAILED',error&&error.message||error));
 }} catch(error){{fail('SOURCE_REFERENCE_BOOTSTRAP_FAILED',error&&error.message||error);}}
}})();
</script></body></html>'''


def prepare(request_path: str | Path, expected_request_sha256: str, output: str | Path) -> dict:
    """Stage a pinned Cocos runtime and controlled source-only Label runner."""
    request_path = io.safe(request_path)
    request_raw = io.read(request_path, max_bytes=_MAX_REQUEST_BYTES)
    if not isinstance(expected_request_sha256, str) or not _SHA.fullmatch(expected_request_sha256) or _digest(request_raw) != expected_request_sha256:
        raise SourceTextReferenceError("SOURCE_TEXT_REFERENCE_REQUEST_SHA_MISMATCH")
    request = _load_json(request_raw, "request")
    required = {"schemaVersion", "contract", "sourceVersion", "sourcePlan", "sourceIr", "sourceManifest",
                "sourceEngineEvidence", "cocosRuntime", "viewport", "sourceIds"}
    allowed = required | {"sourceFontFiles"}
    if not required.issubset(request) or set(request) - allowed:
        raise SourceTextReferenceError("SOURCE_TEXT_REFERENCE_REQUEST_FIELDS_INVALID")
    if request.get("schemaVersion") != 1 or request.get("contract") != SCHEMA or request.get("sourceVersion") != SOURCE_VERSION:
        raise SourceTextReferenceError("SOURCE_TEXT_REFERENCE_REQUEST_CONTRACT_UNSUPPORTED")
    viewport = request.get("viewport")
    if (not isinstance(viewport, dict) or set(viewport) != {"width", "height", "devicePixelRatio"} or
            type(viewport.get("width")) is not int or type(viewport.get("height")) is not int or
            not 64 <= viewport["width"] <= 4096 or not 64 <= viewport["height"] <= 4096 or
            type(viewport.get("devicePixelRatio")) not in (int, float) or
            not math.isfinite(float(viewport["devicePixelRatio"])) or not 0.5 <= float(viewport["devicePixelRatio"]) <= 4.0):
        raise SourceTextReferenceError("SOURCE_TEXT_REFERENCE_VIEWPORT_INVALID")

    inputs = _read_plan_inputs(request)
    fragment = _plan_fragment(inputs["plan"])
    groups = fragment["components"]
    requested_ids = request.get("sourceIds")
    if (not isinstance(requested_ids, list) or len(requested_ids) != 1 or
            any(not isinstance(sid, str) or not sid for sid in requested_ids) or len(set(requested_ids)) != 1):
        raise SourceTextReferenceError("SOURCE_TEXT_REFERENCE_REQUIRES_ONE_EXPLICIT_SOURCE_ID")
    by_id = {row.get("sourceLabelId"): row for row in groups if isinstance(row, dict)}
    missing = [sid for sid in requested_ids if sid not in by_id]
    if missing:
        raise SourceTextReferenceError("SOURCE_TEXT_REFERENCE_SOURCE_ID_NOT_IN_PLAN:" + ",".join(missing))
    groups = [by_id[sid] for sid in requested_ids]

    cases, font_files, gaps = _font_inputs(request, inputs["plan"], inputs["manifest"], groups)
    runtime_spec = request.get("cocosRuntime")
    if (not isinstance(runtime_spec, dict) or set(runtime_spec) != {"path", "sha256", "bytes", "engineVersion"} or
            runtime_spec.get("engineVersion") != SOURCE_VERSION or type(runtime_spec.get("bytes")) is not int or
            runtime_spec["bytes"] <= 0 or runtime_spec["bytes"] > _MAX_RUNTIME_BYTES):
        raise SourceTextReferenceError("SOURCE_COCOS_RUNTIME_PIN_REQUIRED")
    runtime_path, runtime_raw = _pinned_file(runtime_spec, "cocosRuntime", max_bytes=_MAX_RUNTIME_BYTES,
        required_keys=("path", "sha256", "bytes", "engineVersion"))
    if len(runtime_raw) != runtime_spec["bytes"]:
        raise SourceTextReferenceError("SOURCE_COCOS_RUNTIME_SIZE_MISMATCH")
    runtime_version = runtime_spec["engineVersion"]
    if not cases:
        gaps.append({"code": "SOURCE_TEXT_REFERENCE_NO_SUPPORTED_GROUPS"})

    # Recompute the static text groups from the pinned source inputs. This
    # validates every captured source field and exact dynamic-origin join,
    # instead of trusting a hand-edited continuation fragment.
    recompute_plan = json.loads(json.dumps(inputs["plan"]))
    for key in ("staticTextContinuation", "staticTextContinuationJson", "staticTextContinuationSummary"):
        recompute_plan.pop(key, None)
    try:
        recomputed = static_text.prepare(recompute_plan, inputs["ir"], inputs["manifest"],
                                         inputs["planPath"].parent,
                                         source_evidence=inputs["sourceEngineEvidence"])["continuation"]
    except StaticTextContinuationError as error:
        raise SourceTextReferenceError("SOURCE_TEXT_GROUP_RECOMPUTE_FAILED:" + str(error)) from error
    recomputed_by_id = {row.get("sourceLabelId"): row for row in recomputed.get("components", []) if isinstance(row, dict)}
    if (fragment.get("sourceEngineFiles") != recomputed.get("sourceEngineFiles") or
            any(_canonical(group) != _canonical(recomputed_by_id.get(group.get("sourceLabelId"))) for group in groups)):
        raise SourceTextReferenceError("SOURCE_TEXT_CONTINUATION_DIFFERS_FROM_PINNED_SOURCE_INPUTS")

    output = Path(output).absolute()
    output = io.new_output(output, [request_path, inputs["planPath"], inputs["irPath"], inputs["manifestPath"],
                                    inputs["evidencePath"], runtime_path,
                                    *[row["path"] for row in font_files.values()]])
    runtime_rel = "runtime/cocos2d-runtime.js"
    runtime_out = io.inside(output, runtime_rel)
    runtime_out.parent.mkdir(parents=True, exist_ok=True)
    runtime_out.write_bytes(runtime_raw)
    font_evidence = []
    font_css = []
    for index, (asset_id, row) in enumerate(sorted(font_files.items())):
        suffix = row["path"].suffix.lower()
        if suffix not in (".ttf", ".otf"):
            raise SourceTextReferenceError("SOURCE_TTF_FONT_EXTENSION_UNSUPPORTED:" + suffix)
        rel = f"fonts/source-{index}{suffix}"
        path = io.inside(output, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(row["raw"])
        font_css.append(f"@font-face{{font-family:{_css_string(row['familyName'])};src:url('{rel}') format('{ 'truetype' if suffix == '.ttf' else 'opentype' }');font-weight:400;font-style:normal;font-display:block;}}")
        font_evidence.append({"sourceFontId": asset_id, "path": rel, "sha256": row["sha256"],
                              "bytes": row["bytes"], "familyName": row["familyName"]})
    if font_css:
        # Insert CSS before runtime initialization to guarantee font-face availability at capture.
        base_html = _runner_html(cases, runtime_name=Path(runtime_rel).as_posix(), viewport=viewport,
                                 source_manifest_sha=_digest(inputs["manifestRaw"]))
        base_html = base_html.replace("</head>", "<style>" + "".join(font_css) + "</style></head>")
    else:
        base_html = _runner_html(cases, runtime_name=Path(runtime_rel).as_posix(), viewport=viewport,
                                 source_manifest_sha=_digest(inputs["manifestRaw"]))
    runner_path = output / "source-reference.html"
    runner_path.write_text(base_html, encoding="utf-8")
    record = {
        "schemaVersion": 1, "contract": SCHEMA, "status": "prepared" if cases else "partial",
        "sourceVersion": SOURCE_VERSION, "sourceProfile": SOURCE_PROFILE,
        "requestSha256": expected_request_sha256,
        "sourcePlanSha256": _digest(inputs["planRaw"]), "sourceIrSha256": _digest(inputs["irRaw"]),
        "sourceManifestSha256": _digest(inputs["manifestRaw"]),
        "sourceEngineFiles": inputs["engineFiles"],
        "cocosRuntime": {"path": runtime_rel, "sha256": _digest(runtime_raw), "bytes": len(runtime_raw),
                         "declaredEngineVersion": runtime_version},
        "viewport": {"width": viewport["width"], "height": viewport["height"],
                      "devicePixelRatio": float(viewport["devicePixelRatio"])},
        "cases": cases, "sourceFontFiles": font_evidence, "gaps": gaps,
        "browser": {"captureMode": "headless-local-file-offline", "executable": "required-at-capture"},
        "sourceReference": "controlled-capture-under-reported-browser-and-font-environment",
        "originalDeviceEquivalence": "not-claimed",
        "artifacts": [{"path": "source-reference.html", "sha256": _digest(runner_path.read_bytes()),
                       "bytes": runner_path.stat().st_size},
                      {"path": runtime_rel, "sha256": _digest(runtime_raw), "bytes": len(runtime_raw)},
                      *[{"path": row["path"], "sha256": row["sha256"], "bytes": row["bytes"]}
                        for row in font_evidence]],
    }
    io.write_json(output / "preparation.json", record)
    return {"status": record["status"], "preparation": str(output / "preparation.json"),
            "preparationSha256": _digest((output / "preparation.json").read_bytes()),
            "runner": str(runner_path), "sourceCaseCount": len(cases), "gapCount": len(gaps),
            "gaps": gaps, "nativeCapture": "not_run"}


def capture(preparation_path: str | Path, expected_preparation_sha256: str,
            browser_executable: str | Path, output: str | Path, *, timeout_seconds: int = 90) -> dict:
    """Run the local pinned Cocos runtime in headless Chromium and retain metrics/raster."""
    prep_path = io.safe(preparation_path)
    prep_raw = io.read(prep_path, max_bytes=16 * 1024 * 1024)
    if not isinstance(expected_preparation_sha256, str) or not _SHA.fullmatch(expected_preparation_sha256) or _digest(prep_raw) != expected_preparation_sha256:
        raise SourceTextReferenceError("SOURCE_TEXT_REFERENCE_PREPARATION_SHA_MISMATCH")
    prep = _load_json(prep_raw, "preparation")
    if prep.get("contract") != SCHEMA or prep.get("status") != "prepared":
        raise SourceTextReferenceError("SOURCE_TEXT_REFERENCE_PREPARATION_NOT_RUNNABLE")
    if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 180:
        raise SourceTextReferenceError("SOURCE_TEXT_REFERENCE_TIMEOUT_INVALID")
    stage = prep_path.parent
    artifacts = prep.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise SourceTextReferenceError("SOURCE_TEXT_REFERENCE_ARTIFACT_INVENTORY_MISSING")
    expected_artifacts = {}
    for artifact in artifacts:
        if (not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str) or
                artifact["path"] in expected_artifacts or not isinstance(artifact.get("sha256"), str) or
                not _SHA.fullmatch(artifact["sha256"]) or type(artifact.get("bytes")) is not int):
            raise SourceTextReferenceError("SOURCE_TEXT_REFERENCE_ARTIFACT_INVENTORY_INVALID")
        artifact_path = io.inside(stage, artifact["path"])
        artifact_raw = io.read(artifact_path, max_bytes=_MAX_RUNTIME_BYTES)
        if len(artifact_raw) != artifact["bytes"] or _digest(artifact_raw) != artifact["sha256"]:
            raise SourceTextReferenceError("SOURCE_TEXT_REFERENCE_ARTIFACT_CHANGED:" + artifact["path"])
        expected_artifacts[artifact["path"]] = artifact
    actual_artifacts = {path.relative_to(stage).as_posix() for path in stage.rglob("*")
                        if path.is_file() and path != prep_path}
    if actual_artifacts != set(expected_artifacts):
        raise SourceTextReferenceError("SOURCE_TEXT_REFERENCE_ARTIFACT_SET_CHANGED")
    runtime = prep.get("cocosRuntime")
    if not isinstance(runtime, dict):
        raise SourceTextReferenceError("SOURCE_COCOS_RUNTIME_PIN_REQUIRED")
    runtime_path = io.inside(stage, runtime.get("path"))
    runtime_raw = io.read(runtime_path, max_bytes=_MAX_RUNTIME_BYTES)
    if len(runtime_raw) != runtime.get("bytes") or _digest(runtime_raw) != runtime.get("sha256"):
        raise SourceTextReferenceError("SOURCE_COCOS_RUNTIME_CHANGED")
    runner = io.inside(stage, "source-reference.html")
    if not runner.is_file():
        raise SourceTextReferenceError("SOURCE_TEXT_REFERENCE_RUNNER_MISSING")
    browser_path = io.safe(browser_executable)
    if not browser_path.is_file() or not browser_path.stat().st_mode & 0o111:
        raise SourceTextReferenceError("SOURCE_REFERENCE_BROWSER_NOT_EXECUTABLE")
    output = io.new_output(Path(output).absolute(), [prep_path, runner, runtime_path, browser_path])
    version = subprocess.run([str(browser_path), "--version"], check=False, capture_output=True,
                             text=True, timeout=10)
    if version.returncode != 0:
        raise SourceTextReferenceError("SOURCE_REFERENCE_BROWSER_VERSION_QUERY_FAILED")
    browser_version = (version.stdout or version.stderr).strip()
    screenshot = output / "browser-reference.png"
    viewport = prep["viewport"]
    base_flags = [str(browser_path), "--headless", "--disable-background-networking", "--disable-sync",
                  "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-translate",
                  "--hide-scrollbars", "--allow-file-access-from-files",
                  "--host-resolver-rules=MAP * ~NOTFOUND,EXCLUDE localhost",
                  f"--force-device-scale-factor={viewport['devicePixelRatio']}"]
    calibration_html = ('<!doctype html><meta charset="utf-8"><body><script>document.body.setAttribute('
                        '"data-source-reference-viewport",window.innerWidth+","+window.innerHeight)</script>')
    calibration_url = "data:text/html," + quote(calibration_html, safe="")
    calibration_args = [*base_flags, f"--user-data-dir={output / 'chrome-calibration-profile'}",
                        f"--window-size={viewport['width']},{viewport['height']}", "--dump-dom", calibration_url]
    try:
        calibration_result = subprocess.run(calibration_args, check=False, capture_output=True, text=True,
                                            timeout=15, env=os.environ.copy())
    except subprocess.TimeoutExpired:
        calibration_result = None
    calibration_match = (re.search(r'data-source-reference-viewport="(\d+),(\d+)"', calibration_result.stdout)
                         if calibration_result is not None and calibration_result.returncode == 0 else None)
    if calibration_match:
        observed_window_width, observed_window_height = map(int, calibration_match.groups())
        adjusted_window_width = max(64, min(8192, viewport["width"] + viewport["width"] - observed_window_width))
        adjusted_window_height = max(64, min(8192, viewport["height"] + viewport["height"] - observed_window_height))
        calibration = {"requestedCssViewport": {"width": viewport["width"], "height": viewport["height"]},
                       "initialWindowSize": {"width": viewport["width"], "height": viewport["height"]},
                       "observedCssViewport": {"width": observed_window_width, "height": observed_window_height},
                       "adjustedWindowSize": {"width": adjusted_window_width, "height": adjusted_window_height},
                       "status": "measured-and-adjusted"}
    else:
        adjusted_window_width, adjusted_window_height = viewport["width"], viewport["height"]
        calibration = {"requestedCssViewport": {"width": viewport["width"], "height": viewport["height"]},
                       "status": "unavailable-no-adjustment"}
    args = [*base_flags, f"--user-data-dir={output / 'chrome-capture-profile'}",
            f"--window-size={adjusted_window_width},{adjusted_window_height}",
            "--virtual-time-budget=5000", "--run-all-compositor-stages-before-draw",
            f"--screenshot={screenshot}", "--dump-dom", runner.as_uri()]
    try:
        result = subprocess.run(args, check=False, capture_output=True, text=True,
                                timeout=timeout_seconds, env=os.environ.copy())
    except subprocess.TimeoutExpired as error:
        raise SourceTextReferenceError("SOURCE_REFERENCE_BROWSER_TIMEOUT") from error
    if result.returncode != 0:
        (output / "browser-stderr.txt").write_text(result.stderr[-20000:], encoding="utf-8")
        raise SourceTextReferenceError(f"SOURCE_REFERENCE_BROWSER_FAILED:{result.returncode}")
    match = re.search(r'data-source-reference-result="([^"]*)"', result.stdout)
    if not match:
        (output / "browser-dom.txt").write_text(result.stdout[-200000:], encoding="utf-8")
        (output / "browser-stderr.txt").write_text(result.stderr[-20000:], encoding="utf-8")
        raise SourceTextReferenceError("SOURCE_REFERENCE_BROWSER_RESULT_MISSING")
    try:
        payload = json.loads(unquote(html.unescape(match.group(1))))
    except ValueError as error:
        raise SourceTextReferenceError("SOURCE_REFERENCE_BROWSER_RESULT_INVALID") from error
    if not isinstance(payload, dict):
        raise SourceTextReferenceError("SOURCE_REFERENCE_BROWSER_RESULT_INVALID")
    if payload.get("status") != "captured" or payload.get("sourceVersion") != SOURCE_VERSION:
        io.write_json(output / "capture.json", {"status": "partial", "preparationSha256": expected_preparation_sha256,
                                                "browserVersion": browser_version, "browserError": payload,
                                                "diagnostics": [{"code": "SOURCE_REFERENCE_CAPTURE_NOT_COMPLETE"}]})
        return {"status": "partial", "capture": str(output / "capture.json"), "browserVersion": browser_version,
                "diagnostics": [{"code": "SOURCE_REFERENCE_CAPTURE_NOT_COMPLETE"}]}
    expected_ids = [row["sourceLabelId"] for row in prep.get("cases", [])]
    actual_rows = payload.get("cases") if isinstance(payload.get("cases"), list) else []
    actual_ids = [row.get("sourceLabelId") for row in actual_rows if isinstance(row, dict)]
    diagnostics = []
    if len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != set(expected_ids):
        diagnostics.append({"code": "SOURCE_REFERENCE_CASE_SET_MISMATCH", "expected": expected_ids, "actual": actual_ids})
    if payload.get("sourceManifestSha256") != prep.get("sourceManifestSha256"):
        diagnostics.append({"code": "SOURCE_REFERENCE_MANIFEST_PIN_MISMATCH"})
    if payload.get("actualRendererType") != "canvas":
        diagnostics.append({"code": "SOURCE_REFERENCE_ENGINE_CANVAS_RENDERER_NOT_ACTIVE"})
    browser_info = payload.get("browser") if isinstance(payload.get("browser"), dict) else {}
    declared = prep.get("viewport", {})
    if (browser_info.get("innerWidth") != declared.get("width") or
            browser_info.get("innerHeight") != declared.get("height") or
            not isinstance(browser_info.get("devicePixelRatio"), (int, float)) or
            abs(float(browser_info.get("devicePixelRatio", 0)) - float(declared.get("devicePixelRatio", -1))) > 0.001):
        diagnostics.append({"code": "SOURCE_REFERENCE_BROWSER_ENVIRONMENT_DIFFERS_DECLARED"})
    for row in actual_rows:
        if isinstance(row, dict) and row.get("fontAvailable") is False:
            diagnostics.append({"code": "SOURCE_FONT_FAMILY_UNAVAILABLE_IN_CAPTURE_ENV",
                                "sourceId": row.get("sourceLabelId"),
                                "requestedFamily": row.get("requestedFontFamily"),
                                "actualContextFont": row.get("contextFont")})
    raster_rows = []
    for row in actual_rows:
        if not isinstance(row, dict):
            continue
        data_url = row.pop("rasterDataUrl", None)
        if isinstance(data_url, str) and data_url.startswith("data:image/png;base64,"):
            try:
                raster_raw = base64.b64decode(data_url.split(",", 1)[1], validate=True)
            except ValueError:
                diagnostics.append({"code": "SOURCE_REFERENCE_LABEL_RASTER_INVALID", "sourceId": row.get("sourceLabelId")})
            else:
                raster_path = output / ("label-" + _digest(row["sourceLabelId"].encode())[:20] + ".png")
                raster_path.write_bytes(raster_raw)
                raster_rows.append({"sourceLabelId": row.get("sourceLabelId"), "path": raster_path.name,
                                    "sha256": _digest(raster_raw), "bytes": len(raster_raw)})
    if len(raster_rows) != len(actual_rows):
        diagnostics.append({"code": "SOURCE_REFERENCE_LABEL_TEXTURE_RASTER_MISSING"})
    if not screenshot.is_file():
        diagnostics.append({"code": "SOURCE_REFERENCE_SCREENSHOT_MISSING"})
        screenshot_row = None
    else:
        raw = screenshot.read_bytes()
        screenshot_row = {"path": screenshot.name, "sha256": _digest(raw), "bytes": len(raw)}
    report = {
        "schemaVersion": 1, "contract": "monkey-cocos-source-text-reference-capture/1",
        "status": "captured" if not diagnostics else "partial", "preparationSha256": expected_preparation_sha256,
        "sourceVersion": payload.get("sourceVersion"), "sourceManifestSha256": payload.get("sourceManifestSha256"),
        "browser": payload.get("browser"), "browserExecutable": str(browser_path), "browserVersion": browser_version,
        "captureHost": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "declaredViewport": prep.get("viewport"), "browserWindowCalibration": calibration, "cases": actual_rows,
        "labelRasterFiles": raster_rows, "viewportRaster": screenshot_row,
        "sourceReferenceScope": "controlled-browser-device-font-and-viewport",
        "originalDeviceEquivalence": "not-claimed", "diagnostics": diagnostics,
    }
    io.write_json(output / "capture.json", report)
    return {"status": report["status"], "capture": str(output / "capture.json"),
            "caseCount": len(actual_rows), "rasterCount": len(raster_rows),
            "browserVersion": browser_version, "diagnostics": diagnostics}
