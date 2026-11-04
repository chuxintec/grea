"""Source-backed accounting for Creator Label font and i18n bindings.

This module deliberately does not infer a custom font from rendered text,
language, or nearby assets. It records serialized font identities and the
source component's language lifecycle, leaving unresolved native behavior
explicit for target adapters.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from collections import Counter
from pathlib import Path
import platform
import shutil
import struct
import subprocess
from typing import Any, Mapping, Sequence


RULE_VERSION = "monkey-prefab-font-binding/1"
I18N_SOURCE_TYPE = "41ebaVoPpRA4Kp67XEdHfZn"
I18N_SOURCE_SHA256 = "09869990f20feed466cad7518db5f9ab3309decc2860539aa9c0469bbeee6b40"
SOURCE_WRAPPER_SHA256 = "21af08e48846f6ad1a2e0673b0c945358136723b1664f0cd1f6ec9b3df6c5cb5"
COCOS_2415_CC_LABEL_SOURCE = "https://github.com/cocos/cocos-engine/blob/v2.4.15/cocos2d/core/components/CCLabel.js"
COCOS_2415_SYSTEM_FONT_FAMILY = "Arial"
_RF_ID = "41ebaVoPpRA4Kp67XEdHfZn"
_NODE_HELPER = r'''
const fs=require('node:fs');
const acorn=require(process.argv[1]);
const req=JSON.parse(fs.readFileSync(0,'utf8'));
const RF_ID='41ebaVoPpRA4Kp67XEdHfZn';
function parse(s){return acorn.parse(s,{ecmaVersion:'latest',allowHashBang:true});}
function isFn(n){return !!n&&['FunctionExpression','FunctionDeclaration','ArrowFunctionExpression'].includes(n.type);}
function walk(n, ancestors, fn, skipNested=false, root=true){
  if(!n||typeof n!=='object')return;
  fn(n,ancestors);
  if(skipNested&&!root&&isFn(n))return;
  const next=ancestors.concat(n);
  for(const [k,v] of Object.entries(n)){
    if(k==='start'||k==='end'||k==='loc'||k==='range')continue;
    if(Array.isArray(v)){for(const x of v)walk(x,next,fn,skipNested,false);}
    else if(v&&typeof v==='object')walk(v,next,fn,skipNested,false);
  }
}
function fnScopes(path){return path.filter(isFn);}
function patternHasMe(n){
  if(!n)return false;
  if(n.type==='Identifier')return n.name==='Me';
  if(n.type==='RestElement')return patternHasMe(n.argument);
  if(n.type==='AssignmentPattern')return patternHasMe(n.left);
  if(n.type==='ArrayPattern')return n.elements.some(patternHasMe);
  if(n.type==='ObjectPattern')return n.properties.some(p=>patternHasMe(p.value||p.argument));
  return false;
}
function functionBindsMe(fn){
  if((fn.id&&fn.id.name==='Me')||fn.params.some(patternHasMe))return true;
  let found=false;
  walk(fn.body,[],(n)=>{
    if(n.type==='VariableDeclarator'&&patternHasMe(n.id))found=true;
    if((n.type==='FunctionDeclaration'||n.type==='ClassDeclaration')&&n.id&&n.id.name==='Me')found=true;
  },true);
  return found;
}
function findPath(n,target,path=[]){
  if(!n||typeof n!=='object'||n.start>target||n.end<=target)return null;
  const here=path.concat(n);
  for(const [k,v] of Object.entries(n)){
    if(k==='start'||k==='end'||k==='loc'||k==='range')continue;
    if(Array.isArray(v)){for(const x of v){const p=findPath(x,target,here);if(p)return p;}}
    else if(v&&typeof v==='object'){const p=findPath(v,target,here);if(p)return p;}
  }
  return here;
}
function memberName(n){
  if(n&&n.type==='MemberExpression'&&!n.computed&&n.property.type==='Identifier')return n.property.name;
  return null;
}
function staticValue(n){
  if(n&&n.type==='Literal')return n.value;
  if(n&&n.type==='UnaryExpression'&&n.operator==='!'&&n.argument.type==='Literal')return !n.argument.value;
  return undefined;
}
const componentAst=parse(req.component);
const componentMethods=new Set(),componentMeCalls=new Set(),componentDefaults={};
walk(componentAst,[],(n)=>{
  if(n.type==='AssignmentExpression'&&n.left.type==='MemberExpression'){
    const name=memberName(n.left);
    if(name&&n.left.object.type==='MemberExpression'&&n.left.object.object.type==='Identifier'&&n.left.object.object.name==='i'&&n.left.object.property.name==='prototype')componentMethods.add(name);
    if(name==='bitmapEn'||name==='_bmfontUrl'||name==='i18n_string'||name==='_toJson'){
      const v=staticValue(n.right);
      if(v!==undefined)componentDefaults[name]=v;
    }
  }
  if(n.type==='CallExpression'&&n.callee.type==='MemberExpression'&&n.callee.object.type==='Identifier'&&n.callee.object.name==='Me'){
    const name=memberName(n.callee);if(name)componentMeCalls.add(name);
  }
});

const runtimeAst=parse(req.runtime);
const managerDecls=[];
walk(runtimeAst,[],(n,ancestors)=>{
  if(n.type==='VariableDeclarator'&&n.id.type==='Identifier'&&n.id.name==='Me'){
    const scope=fnScopes(ancestors);
    managerDecls.push({node:n,scope});
  }
});
const manager=managerDecls.find(x=>x.scope.length===2&&x.node.init&&x.node.init.type==='CallExpression'&&x.node.init.callee.type==='FunctionExpression');
const rfPos=req.runtime.indexOf('"'+RF_ID+'","i18nLabel"');
const rfPath=rfPos<0?null:findPath(runtimeAst,rfPos);
const sameWrapper=!!manager&&!!rfPath&&JSON.stringify(manager.scope.map(x=>[x.start,x.end]))===JSON.stringify(fnScopes(rfPath).map(x=>[x.start,x.end]));
const managerMethods=new Set();
if(manager){
  walk(manager.node.init.callee,[],(n)=>{
    if(n.type==='AssignmentExpression'&&n.left.type==='MemberExpression'&&n.left.object.type==='Identifier'&&n.left.object.name==='e'){
      const name=memberName(n.left);if(name)managerMethods.add(name);
    }
  },true);
}
const runtimeCalls={};
walk(runtimeAst,[],(n,ancestors)=>{
  if(n.type!=='CallExpression'||n.callee.type!=='MemberExpression'||n.callee.object.type!=='Identifier'||n.callee.object.name!=='Me')return;
  const name=memberName(n.callee), scopes=fnScopes(ancestors);
  const shadowed=manager&&scopes.slice(2).some(functionBindsMe);
  if(name&&manager&&!shadowed&&scopes.length>=2&&JSON.stringify(scopes.slice(0,2).map(x=>[x.start,x.end]))===JSON.stringify(manager.scope.map(x=>[x.start,x.end])))runtimeCalls[name]=(runtimeCalls[name]||0)+1;
});
const result={
  component:{methods:[...componentMethods].sort(),meCalls:[...componentMeCalls].sort(),defaults:componentDefaults},
  runtime:{managerDeclarationCount:managerDecls.length,selectedManagerScope:manager&&manager.scope.map(x=>[x.start,x.end]),moduleSharesWrapper:sameWrapper,managerMethods:[...managerMethods].sort(),calls:runtimeCalls}
};
process.stdout.write(JSON.stringify(result));
'''

_CORETEXT_SWIFT_HELPER = r'''
import Foundation
import CoreText
import CoreFoundation

struct FontRun: Decodable { let id: String; let text: String; let pointSize: Double; let requestedFamily: String? }
struct Request: Decodable { let requestedFamily: String; let runs: [FontRun] }
func familyName(_ font: CTFont) -> String { CTFontCopyFamilyName(font) as String }
func styleName(_ font: CTFont) -> String { (CTFontCopyName(font, kCTFontStyleNameKey) as String?) ?? "" }
func postScriptName(_ font: CTFont) -> String { CTFontCopyPostScriptName(font) as String }
func fileURLPath(_ font: CTFont) -> String {
  guard let value = CTFontCopyAttribute(font, kCTFontURLAttribute), let url = value as? URL, url.isFileURL else { return "" }
  return url.path
}
func variationAxes(_ font: CTFont) -> [String: Double] {
  guard let dictionary = CTFontCopyAttribute(font, kCTFontVariationAttribute) as? NSDictionary else { return [:] }
  var result: [String: Double] = [:]
  for (key, value) in dictionary {
    guard let tagNumber = key as? NSNumber, let axisValue = value as? NSNumber else { continue }
    let tag = tagNumber.uint32Value
    let bytes: [UInt8] = [UInt8((tag >> 24) & 0xff), UInt8((tag >> 16) & 0xff), UInt8((tag >> 8) & 0xff), UInt8(tag & 0xff)]
    result[String(bytes: bytes, encoding: .ascii) ?? String(tag)] = axisValue.doubleValue
  }
  return result
}
let input = FileHandle.standardInput.readDataToEndOfFile()
let request = try JSONDecoder().decode(Request.self, from: input)
var labelResults: [[String: Any]] = []
var coverage: [String: [String: Any]] = [:]
var fallbackFonts: [String: [String: Any]] = [:]
var primaryFonts: [String: [String: Any]] = [:]
for run in request.runs {
  let requestedFamily = run.requestedFamily ?? request.requestedFamily
  let primary = CTFontCreateWithName(requestedFamily as CFString, CGFloat(run.pointSize), nil)
  let primaryFamily = familyName(primary)
  let primaryStyle = styleName(primary)
  let primaryPS = postScriptName(primary)
  let primaryURL = fileURLPath(primary)
  let primaryVariations = variationAxes(primary)
  let primaryKey = requestedFamily + "|" + primaryFamily + "|" + primaryStyle + "|" + primaryPS + "|" + primaryURL + "|" + String(describing: primaryVariations)
  var primaryRecord = primaryFonts[primaryKey] ?? ["family": primaryFamily, "styleName": primaryStyle,
                                                   "postScriptName": primaryPS, "requestedFamily": requestedFamily,
                                                   "systemFontFileUrl": primaryURL, "variationAxes": primaryVariations,
                                                   "pointSizes": [Double]()]
  var primarySizes = primaryRecord["pointSizes"] as! [Double]
  if !primarySizes.contains(run.pointSize) { primarySizes.append(run.pointSize) }
  primaryRecord["pointSizes"] = primarySizes.sorted()
  primaryFonts[primaryKey] = primaryRecord
  let nsText = run.text as NSString
  var utf16Offset = 0
  var characters: [[String: Any]] = []
  var fallbacksForLabel: Set<String> = []
  for scalar in run.text.unicodeScalars {
    let utf16Length = scalar.utf16.count
    let mapped = CTFontCreateForString(primary, nsText as CFString,
                                       CFRange(location: utf16Offset, length: utf16Length))
    let family = familyName(mapped)
    let postScript = postScriptName(mapped)
    let resolvedStyle = styleName(mapped)
    let resolvedURL = fileURLPath(mapped)
    let resolvedVariations = variationAxes(mapped)
    let fallback = family != primaryFamily || postScript != primaryPS
    let characterSet = CTFontCopyCharacterSet(mapped)
    let charSetContains = CFCharacterSetIsLongCharacterMember(characterSet, UInt32(scalar.value))
    var glyphId: UInt16 = 0
    var mapSucceeded: Bool? = nil
    if scalar.value <= 0xFFFF && !(0xD800...0xDFFF).contains(scalar.value) {
      var unit = UniChar(scalar.value)
      mapSucceeded = CTFontGetGlyphsForCharacters(mapped, &unit, &glyphId, 1)
    }
    let glyphCovered = charSetContains && (mapSucceeded ?? true) && (mapSucceeded == nil || glyphId != 0)
    let codepoint = String(format: "U+%04X", scalar.value)
    let row: [String: Any] = [
      "codepoint": codepoint, "scalarValue": Int(scalar.value), "character": String(scalar),
      "family": family, "styleName": resolvedStyle, "postScriptName": postScript,
      "systemFontFileUrl": resolvedURL, "variationAxes": resolvedVariations, "fallback": fallback,
      "characterSetContainsScalar": charSetContains, "glyphMappingChecked": mapSucceeded != nil,
      "glyphMappingSucceeded": mapSucceeded as Any? ?? NSNull(),
      "glyphId": mapSucceeded == nil ? NSNull() : glyphId as Any,
      "glyphCovered": glyphCovered, "requiredForVisualText": scalar.properties.generalCategory != .control,
      "targetLabelId": run.id, "pointSize": run.pointSize
    ]
    characters.append(row)

    var aggregate = coverage[codepoint] ?? [
      "codepoint": codepoint, "scalarValue": Int(scalar.value), "character": String(scalar),
      "requiredForVisualText": scalar.properties.generalCategory != .control,
      "resolutions": [[String: Any]](), "targetLabelIds": [String]()
    ]
    var resolutions = aggregate["resolutions"] as! [[String: Any]]
    let resolutionKey = family + "|" + resolvedStyle + "|" + postScript + "|" + resolvedURL + "|" + String(describing: resolvedVariations)
    if let index = resolutions.firstIndex(where: { ($0["resolutionKey"] as? String) == resolutionKey }) {
      var existing = resolutions[index]
      existing["glyphCovered"] = (existing["glyphCovered"] as? Bool ?? true) && glyphCovered
      existing["glyphMappingChecked"] = (existing["glyphMappingChecked"] as? Bool ?? false) || mapSucceeded != nil
      resolutions[index] = existing
    } else {
      resolutions.append(["resolutionKey": resolutionKey, "family": family, "styleName": resolvedStyle,
                          "postScriptName": postScript, "systemFontFileUrl": resolvedURL,
                          "variationAxes": resolvedVariations, "fallback": fallback,
                          "glyphCovered": glyphCovered, "glyphMappingChecked": mapSucceeded != nil])
    }
    aggregate["resolutions"] = resolutions.sorted { ($0["family"] as? String ?? "") < ($1["family"] as? String ?? "") }
    var labelIds = aggregate["targetLabelIds"] as! [String]
    if !labelIds.contains(run.id) { labelIds.append(run.id) }
    aggregate["targetLabelIds"] = labelIds.sorted()
    coverage[codepoint] = aggregate

    if fallback {
      let resolvedStyle = styleName(mapped)
      let key = family + "|" + resolvedStyle + "|" + postScript + "|" + resolvedURL + "|" + String(describing: resolvedVariations)
      var font = fallbackFonts[key] ?? ["family": family, "styleName": resolvedStyle, "postScriptName": postScript,
                                         "systemFontFileUrl": resolvedURL, "variationAxes": resolvedVariations,
                                         "requestedFamilies": [String](),
                                         "pointSizes": [Double](), "codepoints": [String](),
                                         "characters": [String](), "targetLabelIds": [String]()]
      var requestedFamilies = font["requestedFamilies"] as! [String]
      if !requestedFamilies.contains(requestedFamily) { requestedFamilies.append(requestedFamily) }
      font["requestedFamilies"] = requestedFamilies.sorted()
      var pointSizes = font["pointSizes"] as! [Double]
      if !pointSizes.contains(run.pointSize) { pointSizes.append(run.pointSize) }
      var codepoints = font["codepoints"] as! [String]
      if !codepoints.contains(codepoint) { codepoints.append(codepoint) }
      var chars = font["characters"] as! [String]
      if !chars.contains(String(scalar)) { chars.append(String(scalar)) }
      var labels = font["targetLabelIds"] as! [String]
      if !labels.contains(run.id) { labels.append(run.id) }
      font["pointSizes"] = pointSizes.sorted()
      font["codepoints"] = codepoints.sorted()
      font["characters"] = chars.sorted()
      font["targetLabelIds"] = labels.sorted()
      fallbackFonts[key] = font
      fallbacksForLabel.insert(key)
    }
    utf16Offset += utf16Length
  }
  labelResults.append(["targetLabelId": run.id, "text": run.text, "pointSize": run.pointSize,
                       "requestedFamily": requestedFamily,
                       "resolvedPrimaryFamily": primaryFamily, "resolvedPrimaryStyleName": primaryStyle,
                       "resolvedPrimaryPostScriptName": primaryPS, "resolvedPrimarySystemFontFileUrl": primaryURL,
                       "resolvedPrimaryVariationAxes": primaryVariations,
                       "fallbackFontKeys": fallbacksForLabel.sorted(), "unicodeScalars": characters])
}
let output: [String: Any] = [
  "requestedFamily": request.requestedFamily,
  "resolvedPrimaryFonts": Array(primaryFonts.values).sorted { ($0["family"] as? String ?? "") < ($1["family"] as? String ?? "") },
  "fallbackFonts": Array(fallbackFonts.values).sorted { ($0["family"] as? String ?? "") < ($1["family"] as? String ?? "") },
  "unicodeCoverage": Array(coverage.values).sorted { ($0["scalarValue"] as! Int) < ($1["scalarValue"] as! Int) },
  "labels": labelResults.sorted { ($0["targetLabelId"] as! String) < ($1["targetLabelId"] as! String) }
]
FileHandle.standardOutput.write(try JSONSerialization.data(withJSONObject: output, options: [.sortedKeys]))
'''


def _sfnt_name_records(data: bytes, face_offset: int) -> dict[str, str]:
    """Read the identifying SFNT name records for one TTC/SFNT face."""
    if face_offset < 0 or face_offset + 12 > len(data):
        raise ValueError("font face header is outside the file")
    sfnt = data[face_offset:face_offset + 4]
    if sfnt not in {b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1"}:
        raise ValueError("unsupported SFNT face signature")
    table_count = struct.unpack_from(">H", data, face_offset + 4)[0]
    if table_count > 256 or face_offset + 12 + 16 * table_count > len(data):
        raise ValueError("invalid SFNT table directory")
    name_offset = name_length = None
    for index in range(table_count):
        pos = face_offset + 12 + index * 16
        tag = data[pos:pos + 4]
        offset, length = struct.unpack_from(">II", data, pos + 8)
        if tag == b"name":
            name_offset, name_length = offset, length
            break
    if name_offset is None or name_length is None or name_length < 6 or name_offset + name_length > len(data):
        raise ValueError("SFNT face has no bounded name table")
    table = data[name_offset:name_offset + name_length]
    format_number, count, string_offset = struct.unpack_from(">HHH", table, 0)
    if format_number not in (0, 1) or count > 4096 or 6 + count * 12 > len(table):
        raise ValueError("invalid SFNT name table")
    wanted_ids = {1: "family", 2: "subfamily", 4: "fullName", 6: "postScriptName", 16: "typographicFamily", 17: "typographicSubfamily"}
    candidates: dict[str, list[tuple[int, str]]] = {}
    for index in range(count):
        pos = 6 + index * 12
        platform_id, encoding_id, language_id, name_id, length, offset = struct.unpack_from(">HHHHHH", table, pos)
        key = wanted_ids.get(name_id)
        start = string_offset + offset
        end = start + length
        if key is None or end > len(table):
            continue
        raw = table[start:end]
        try:
            value = raw.decode("utf-16-be" if platform_id in (0, 3) else "mac_roman").strip("\x00\r\n ")
        except (UnicodeDecodeError, LookupError):
            continue
        if value:
            # Unicode/Windows English names are most useful; preserve platform fallbacks.
            score = (10 if platform_id in (0, 3) else 0) + (4 if language_id in (0, 0x0409) else 0) + (2 if encoding_id in (1, 10) else 0)
            candidates.setdefault(key, []).append((score, value))
    result = {key: sorted(values, key=lambda item: (-item[0], item[1]))[0][1]
              for key, values in candidates.items() if values}
    return result


def _font_file_face_evidence(path: str, *, maximum_bytes: int = 256 * 1024 * 1024) -> dict[str, Any]:
    """Hash and inspect an installed font in place; never copies or exports bytes."""
    result: dict[str, Any] = {"path": path, "readOnly": True, "fontBytesCopiedOrExported": False}
    try:
        stat = Path(path).stat()
        if not Path(path).is_file() or stat.st_size <= 0 or stat.st_size > maximum_bytes:
            raise ValueError("font file is absent, empty, or exceeds the bounded size limit")
        data = Path(path).read_bytes()
        result.update({"fileSizeBytes": len(data), "fileSha256": _sha(data)})
        if data.startswith(b"ttcf"):
            if len(data) < 12:
                raise ValueError("truncated TTC header")
            version, count = struct.unpack_from(">II", data, 4)
            if version not in (0x00010000, 0x00020000) or not 0 < count <= 4096 or 12 + 4 * count > len(data):
                raise ValueError("invalid TTC header")
            offsets = list(struct.unpack_from(f">{count}I", data, 12))
            container = "TTC"
        else:
            offsets = [0]
            container = "SFNT"
        faces = []
        for face_index, offset in enumerate(offsets):
            names = _sfnt_name_records(data, offset)
            faces.append({"faceIndex": face_index, **names})
        result.update({"status": "inspected", "container": container, "faceCount": len(faces), "faces": faces})
    except (OSError, ValueError, struct.error) as exc:
        result.update({"status": "needs_action", "reason": str(exc)})
    return result


@dataclass(frozen=True)
class FontBindingReport:
    status: str
    record: dict[str, Any]


def _fail(reason: str, *, diagnostics: Sequence[str] = ()) -> FontBindingReport:
    return FontBindingReport("unsupported", {
        "schema": "monkey-prefab-font-binding/1",
        "ruleVersion": RULE_VERSION,
        "status": "unsupported",
        "reason": reason,
        "diagnostics": list(diagnostics),
    })


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sfnt_physical_faces(raw: bytes) -> list[dict[str, Any]]:
    """Read only SFNT name records needed to map a CoreText face URL to a file face index."""
    def u16(offset: int) -> int:
        if offset < 0 or offset + 2 > len(raw):
            raise ValueError("truncated SFNT uint16")
        return int.from_bytes(raw[offset:offset + 2], "big")

    def u32(offset: int) -> int:
        if offset < 0 or offset + 4 > len(raw):
            raise ValueError("truncated SFNT uint32")
        return int.from_bytes(raw[offset:offset + 4], "big")

    if raw.startswith(b"ttcf"):
        if len(raw) < 12:
            raise ValueError("truncated TTC header")
        count = u32(8)
        if count == 0 or count > 4096 or 12 + 4 * count > len(raw):
            raise ValueError("invalid TTC face count")
        face_offsets = [u32(12 + index * 4) for index in range(count)]
    elif raw[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        face_offsets = [0]
    else:
        raise ValueError("CoreText file URL is not a supported SFNT/TTC font")

    faces = []
    for face_index, face_offset in enumerate(face_offsets):
        table_count = u16(face_offset + 4)
        if table_count == 0 or table_count > 4096 or face_offset + 12 + 16 * table_count > len(raw):
            raise ValueError(f"invalid SFNT table directory at face {face_index}")
        name_table = None
        for table_index in range(table_count):
            record = face_offset + 12 + 16 * table_index
            tag = raw[record:record + 4]
            table_offset = u32(record + 8)
            table_length = u32(record + 12)
            if table_offset + table_length > len(raw):
                raise ValueError(f"SFNT table extends past file at face {face_index}")
            if tag == b"name":
                name_table = (table_offset, table_length)
        fields: dict[int, list[str]] = {1: [], 2: [], 6: []}
        if name_table:
            table_offset, table_length = name_table
            if table_length < 6:
                raise ValueError(f"truncated SFNT name table at face {face_index}")
            format_id = u16(table_offset)
            record_count = u16(table_offset + 2)
            string_offset = table_offset + u16(table_offset + 4)
            if record_count > 65535 or table_offset + 6 + 12 * record_count > table_offset + table_length:
                raise ValueError(f"invalid SFNT name records at face {face_index}")
            for record_index in range(record_count):
                record = table_offset + 6 + 12 * record_index
                platform_id, encoding_id, language_id, name_id, length, offset = (u16(record + i) for i in (0, 2, 4, 6, 8, 10))
                if name_id not in fields or string_offset + offset + length > table_offset + table_length:
                    continue
                value = raw[string_offset + offset:string_offset + offset + length]
                try:
                    decoded = value.decode("utf-16-be") if platform_id in (0, 3) else value.decode("mac_roman") if platform_id == 1 else ""
                except UnicodeDecodeError:
                    decoded = ""
                decoded = decoded.strip("\x00")
                if decoded and decoded not in fields[name_id]:
                    fields[name_id].append(decoded)
        faces.append({
            "faceIndex": face_index,
            "familyNames": sorted(fields[1]),
            "subfamilyNames": sorted(fields[2]),
            "postScriptNames": sorted(fields[6]),
            "nameTableFormat": format_id if name_table else None,
        })
    return faces


def _asset_by_source_id(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(a.get("sourceId")): a for a in manifest.get("assets", []) if a.get("sourceId")}


def _label_config(path: Path) -> tuple[dict[str, str], str]:
    """Read the `label` JsonAsset payload from a frozen Cocos packed resource cache."""
    raw = path.read_bytes()
    packed = json.loads(raw.decode("utf-8"))
    if not isinstance(packed, list) or len(packed) < 6 or not isinstance(packed[5], list):
        raise ValueError("expected frozen Cocos packed resource-cache array")
    candidates: list[dict[str, Any]] = []
    def visit(value: Any) -> None:
        if isinstance(value, list):
            if (len(value) >= 3 and isinstance(value[0], int)
                    and value[1] == "label" and isinstance(value[2], dict)):
                candidates.append(value[2])
                return
            for child in value:
                visit(child)
        elif isinstance(value, dict):
            for child in value.values():
                visit(child)
    visit(packed[5])
    if len(candidates) != 1:
        raise ValueError(f"expected one packed label object, found {len(candidates)}")
    labels = candidates[0]
    if any(not isinstance(k, str) or not isinstance(v, str) for k, v in labels.items()):
        raise ValueError("label JsonAsset contains non-string keys or values")
    return labels, _sha(raw)


def _source_component_records(manifest: Mapping[str, Any], source_type: str,
                              ir: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ir_labels = {c.get("node"): c for c in ir.get("components", []) if c.get("type") == "cc.Label"}
    for asset in manifest.get("assets", []):
        document = asset.get("document")
        if not isinstance(document, dict) or not isinstance(document.get("instances"), list):
            continue
        instances = document["instances"]
        labels_by_node: dict[int, dict[str, Any]] = {}
        for node_index, node in enumerate(instances):
            if not isinstance(node, dict) or node.get("__type__") != "cc.Node":
                continue
            for reference in node.get("_components", []):
                component = reference
                if isinstance(reference, dict) and isinstance(reference.get("__id__"), int):
                    component = instances[reference["__id__"]] if reference["__id__"] < len(instances) else None
                if isinstance(component, dict) and component.get("__type__") == "cc.Label":
                    labels_by_node[node_index] = component
                    break
        for index, instance in enumerate(instances):
            if not isinstance(instance, dict) or instance.get("__type__") != source_type:
                continue
            node_ref = instance.get("node")
            node_index = node_ref.get("__id__") if isinstance(node_ref, dict) else None
            label = labels_by_node.get(node_index) if isinstance(node_index, int) else None
            raw_font = (label or {}).get("_N$file")
            if isinstance(raw_font, dict):
                raw_font = raw_font.get("__uuid__")
            normalized_label = ir_labels.get(f"{asset.get('sourceId')}#{node_index}") if isinstance(node_index, int) else None
            rows.append({
                "prefabSourceId": asset.get("sourceId"),
                "prefabLogicalPath": asset.get("logicalPath"),
                "componentInstanceIndex": index,
                "sourceNodeIndex": node_index,
                "i18nKey": instance.get("i18n_string"),
                "toJson": instance.get("_toJson"),
                "bitmapEn": instance.get("bitmapEn"),
                "bmfontUrl": instance.get("_bmfontUrl"),
                "serializedLabelFontUuid": raw_font,
                "serializedLabelSystemFont": (label or {}).get("_isSystemFontUsed"),
                "serializedLabelString": (label or {}).get("_string"),
                "normalizedLabelSourceId": (normalized_label or {}).get("sourceId"),
                "normalizedLabelFontUuid": (normalized_label or {}).get("font"),
                "normalizedLabelSystemFont": (normalized_label or {}).get("systemFont"),
            })
    return rows


def _run_static_ast(component_source: bytes, runtime_source: bytes) -> dict[str, Any]:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for the vendored Acorn static parse")
    acorn = Path(__file__).with_name("sources") / "acorn.cjs"
    request = json.dumps({
        "component": component_source.decode("utf-8"),
        "runtime": runtime_source.decode("utf-8"),
    }, ensure_ascii=False).encode("utf-8")
    result = subprocess.run([node, "-e", _NODE_HELPER, str(acorn)], input=request,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
                            timeout=90)
    if result.returncode:
        raise RuntimeError("Acorn static parse failed: " + result.stderr.decode("utf-8", "replace")[:600])
    return json.loads(result.stdout.decode("utf-8"))


def analyze_prefab_font_bindings(
    ir: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    i18n_component_source: bytes,
    runtime_wrapper_source: bytes,
    language_cache_paths: Mapping[str, str | Path],
    *,
    expected_component_sha256: str = I18N_SOURCE_SHA256,
    expected_runtime_sha256: str = SOURCE_WRAPPER_SHA256,
) -> FontBindingReport:
    """Return an evidence-pinned binding declaration and unresolved gaps.

    The function accounts for existing bindings, maps frozen i18n keys through
    caller-supplied raw language cache closures, and checks font glyph coverage.
    It never assigns an inferred font to a source system-font Label.
    """
    if _sha(i18n_component_source) != expected_component_sha256:
        return _fail("i18n component source hash does not match the frozen source")
    if _sha(runtime_wrapper_source) != expected_runtime_sha256:
        return _fail("runtime wrapper source hash does not match the frozen source")
    if not isinstance(ir.get("components"), list) or not isinstance(source_manifest.get("assets"), list):
        return _fail("IR or source manifest schema is incomplete")
    try:
        ast = _run_static_ast(i18n_component_source, runtime_wrapper_source)
    except (UnicodeDecodeError, RuntimeError, json.JSONDecodeError) as exc:
        return _fail(str(exc))
    component_ast = ast.get("component", {})
    manager_ast = ast.get("runtime", {})
    required_calls = {"addOrDelLabel", "getLabel", "i18nLabel"}
    if not required_calls.issubset(set(component_ast.get("meCalls", []))):
        return _fail("source i18n component does not match the frozen Me call contract")
    if not manager_ast.get("moduleSharesWrapper"):
        return _fail("could not prove the i18n component and Me manager share the exact wrapper scope")
    manager_methods = set(manager_ast.get("managerMethods", []))
    if not {"initialize", "setLanguage", "getLabel", "getBitmapFont", "i18nBmFont", "reloadLabel"}.issubset(manager_methods):
        return _fail("source Me manager method AST is incomplete")

    labels = [c for c in ir["components"] if c.get("type") == "cc.Label"]
    i18n_components = [c for c in ir["components"] if c.get("type") == I18N_SOURCE_TYPE]
    system_labels = [c for c in labels if c.get("systemFont") is True and c.get("font") is None]
    existing_font_groups: dict[str, dict[str, Any]] = {}
    for label in labels:
        font = label.get("font")
        if not isinstance(font, str):
            continue
        group = existing_font_groups.setdefault(font, {"sourceFontId": font, "count": 0, "targets": []})
        group["count"] += 1
        group["targets"].append(label.get("sourceId"))

    assets_by_source = _asset_by_source_id(source_manifest)
    ir_aliases = ir.get("aliases") if isinstance(ir.get("aliases"), dict) else {}
    bitmap_fonts = {f.get("sourceId"): f for f in ir.get("bitmapFonts", []) if f.get("sourceId")}
    native_asset_records = []
    for font_id, group in sorted(existing_font_groups.items()):
        aliased_id = ir_aliases.get(font_id, font_id)
        source_asset = assets_by_source.get(font_id) or assets_by_source.get(aliased_id)
        source_redirect = source_asset
        target_id = source_asset.get("redirectTarget") if source_asset and source_asset.get("kind") == "redirect" else None
        if target_id:
            source_asset = assets_by_source.get(target_id, source_asset)
        bmfont = bitmap_fonts.get(font_id) or bitmap_fonts.get(aliased_id)
        record = {
            **group,
            "resolvedAlias": aliased_id if aliased_id != font_id else None,
            "sourceAssetKind": source_asset.get("kind") if source_asset else None,
            "sourceAssetBundle": source_asset.get("bundle") if source_asset else None,
            "sourceAssetLogicalPath": source_asset.get("logicalPath") if source_asset else None,
            "serializedSourceBundle": source_redirect.get("bundle") if source_redirect else None,
            "serializedSourceLogicalPath": source_redirect.get("logicalPath") if source_redirect else None,
            "resolvedSourceId": target_id,
            "bitmapFontSourceId": bmfont.get("sourceId") if bmfont else None,
            "bitmapGlyphCount": len(bmfont.get("glyphs", [])) if bmfont else None,
            "bitmapUnicodeCoverage": sorted({g.get("unicode") for g in bmfont.get("glyphs", []) if isinstance(g.get("unicode"), int)}) if bmfont else None,
            "bitmapAtlasRef": bmfont.get("atlasRef") if bmfont else None,
            "bitmapAtlasImage": bmfont.get("atlasImage") if bmfont else None,
            "bitmapAtlasSize": bmfont.get("atlasSize") if bmfont else None,
            "bitmapPointSize": bmfont.get("pointSize") if bmfont else None,
            "bitmapLineHeight": bmfont.get("lineHeight") if bmfont else None,
            "bitmapBaselineConvention": bmfont.get("baselineConvention") if bmfont else None,
        }
        native_asset_records.append(record)

    source_i18n_records = _source_component_records(source_manifest, I18N_SOURCE_TYPE, ir)
    config_results: dict[str, dict[str, Any]] = {}
    diagnostics: list[str] = []
    for locale, path_value in sorted(language_cache_paths.items()):
        path = Path(path_value)
        try:
            labels_data, digest = _label_config(path)
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            diagnostics.append(f"{locale}: {exc}")
            continue
        config_results[locale] = {"path": str(path), "sha256": digest, "keys": labels_data}

    glyph_sets = {font_id: set(record.get("bitmapUnicodeCoverage") or [])
                  for font_id, record in ((r["sourceFontId"], r) for r in native_asset_records)
                  if record.get("bitmapGlyphCount") is not None}
    system_label_texts = [c.get("text", "") for c in system_labels if isinstance(c.get("text", ""), str)]
    static_font_coverage = {}
    for font_id, glyphs in glyph_sets.items():
        missing_counter: Counter[str] = Counter()
        fully_covered = 0
        for value in system_label_texts:
            missing = set(map(ord, value)) - glyphs
            if missing:
                missing_counter.update(chr(code) for code in missing)
            else:
                fully_covered += 1
        static_font_coverage[font_id] = {
            "systemFontLabelCount": len(system_label_texts),
            "fullyCoveredSourceTextCount": fully_covered,
            "sourceTextsWithMissingGlyphs": len(system_label_texts) - fully_covered,
            "distinctMissingCharacters": len(missing_counter),
            "mostFrequentMissingCharacters": [
                {"character": char, "sourceLabelCount": count}
                for char, count in missing_counter.most_common(32)
            ],
        }
    localized_components = []
    for source_row in source_i18n_records:
        key = source_row.get("i18nKey")
        translations = {locale: data["keys"][key] for locale, data in config_results.items() if key in data["keys"]} if isinstance(key, str) else {}
        coverage = {}
        for font_id, glyphs in glyph_sets.items():
            coverage[font_id] = {locale: {"missingCodepoints": sorted(set(map(ord, value)) - glyphs),
                                          "missingCharacters": "".join(chr(code) for code in sorted(set(map(ord, value)) - glyphs))}
                                 for locale, value in translations.items()}
        localized_components.append({**source_row, "translations": translations,
                                     "coverageAgainstExistingSerializedBitmapFonts": coverage,
                                     "translationStatus": "found" if translations else ("key_not_serialized" if not key else "key_missing_from_supplied_raw_configs")})

    font_uuid_bindings = {
        "sourceSerializedCustomFonts": native_asset_records,
        "systemFontLabels": {
            "count": len(system_labels),
            "normalizedSourceState": "font=null and systemFont=true",
            "fontAssetUuid": None,
            "bindingDeclaration": "preserve-source-system-font; no custom font assignment is source-proven",
        },
    }
    record = {
        "schema": "monkey-prefab-font-binding/1",
        "ruleVersion": RULE_VERSION,
        "status": "source_bound_with_explicit_gaps",
        "sourceProvenance": {
            "i18nComponentSourceSha256": _sha(i18n_component_source),
            "runtimeWrapperSourceSha256": _sha(runtime_wrapper_source),
            "i18nSourceType": I18N_SOURCE_TYPE,
            "staticParser": "vendored Acorn; source bytes parsed, never executed",
        },
        "inventory": {
            "labels": len(labels),
            "systemFontUnboundLabels": len(system_labels),
            "labelsWithSerializedFontUuid": sum(1 for c in labels if c.get("font") is not None),
            "i18nComponents": len(i18n_components),
            "rawSerializedI18nComponents": len(source_i18n_records),
        },
        "bindingDeclarations": font_uuid_bindings,
        "glyphMetadataAudit": {
            "staticSystemLabelTextCoverageAgainstExistingSerializedBitmapFonts": static_font_coverage,
            "coverageScope": "source-serialized Label text only; dynamic values are not inferred",
        },
        "i18nLifecycleContract": {
            "componentMethods": component_ast.get("methods", []),
            "componentMeCalls": component_ast.get("meCalls", []),
            "serializedDefaults": component_ast.get("defaults", {}),
            "managerMethods": manager_ast.get("managerMethods", []),
            "managerCallSites": manager_ast.get("calls", {}),
            "managerAndComponentShareExactWrapper": manager_ast.get("moduleSharesWrapper"),
            "translationFlow": "onLoad registers with Me; updateString calls Me.getLabel; reloadLabel loads Config/label for selected language and resets registered labels",
            "fontFlow": "i18nLabel.init is empty; Me.i18nBmFont is empty; Me.getBitmapFont is defined but has no same-wrapper call site",
            "fontReplacementStatus": "not_source_proven",
        },
        "localizedSourceComponents": localized_components,
        "suppliedRawLanguageConfigs": {locale: {"path": data["path"], "sha256": data["sha256"]} for locale, data in config_results.items()},
        "diagnostics": diagnostics,
        "gaps": [
            "The 113 Labels normalize to font=null and systemFont=true; no source-backed custom-font mutation rule or native cross-target fallback identity was found.",
            "The declared Font_GYM bitmap font has insufficient glyph coverage for the supplied Chinese i18n strings and cannot be used as a blanket replacement.",
            "Only supplied raw zh label config values were resolved; zh-tw, en, jp, and kr raw locale values remain unverified.",
        ],
    }
    return FontBindingReport("source_bound_with_explicit_gaps", record)


def analyze_prefab_font_binding_files(
    ir_path: str | Path,
    source_manifest_path: str | Path,
    i18n_component_path: str | Path,
    runtime_wrapper_path: str | Path,
    language_cache_paths: Mapping[str, str | Path],
) -> FontBindingReport:
    """File-backed adapter for frozen private evidence inputs."""
    try:
        ir = json.loads(Path(ir_path).read_text(encoding="utf-8"))
        manifest = json.loads(Path(source_manifest_path).read_text(encoding="utf-8"))
        component = Path(i18n_component_path).read_bytes()
        runtime = Path(runtime_wrapper_path).read_bytes()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _fail(f"cannot read frozen font-binding evidence: {exc}")
    report = analyze_prefab_font_bindings(ir, manifest, component, runtime, language_cache_paths)
    if report.status != "unsupported":
        report.record["frozenInputs"] = {
            "ir": {"path": str(Path(ir_path).resolve()), "sha256": _sha(Path(ir_path).read_bytes())},
            "sourceManifest": {"path": str(Path(source_manifest_path).resolve()),
                               "sha256": _sha(Path(source_manifest_path).read_bytes())},
            "i18nComponent": {"path": str(Path(i18n_component_path).resolve()), "sha256": _sha(component)},
            "runtimeWrapper": {"path": str(Path(runtime_wrapper_path).resolve()), "sha256": _sha(runtime)},
            "rawLanguageCaches": {
                locale: {"path": str(Path(path).resolve()), "sha256": _sha(Path(path).read_bytes())}
                for locale, path in sorted(language_cache_paths.items())
            },
        }
    return report


def _needs_action(reason: str) -> FontBindingReport:
    return FontBindingReport("needs_action", {
        "schema": "monkey-macos-system-font-resolution/1",
        "status": "needs_action",
        "reason": reason,
        "visualEquivalent": False,
    })


def resolve_macos_system_font_runs(
    runs: Sequence[Mapping[str, Any]],
    requested_family: str = COCOS_2415_SYSTEM_FONT_FAMILY,
) -> FontBindingReport:
    """Resolve installed macOS font family and CoreText fallback for label text.

    The resolver only queries the current target macOS font registry. It never
    registers, copies, downloads, or exports fonts. Source-OS identity is not
    inferred from this target-side result.
    """
    if platform.system() != "Darwin":
        return _needs_action("CoreText system-font resolution is supported only on macOS")
    if not isinstance(requested_family, str) or not requested_family.strip() or len(requested_family) > 256:
        return _needs_action("requested font family must be a non-empty bounded string")
    if not runs or len(runs) > 1000:
        return _needs_action("font resolution requires 1 to 1000 bounded label text runs")
    normalized_runs: list[dict[str, Any]] = []
    total_chars = 0
    seen_ids: set[str] = set()
    try:
        for index, run in enumerate(runs):
            label_id = run.get("id")
            text = run.get("text")
            point_size = run.get("pointSize", 12.0)
            run_family = run.get("requestedFamily", requested_family)
            if not isinstance(label_id, str) or not label_id or label_id in seen_ids:
                return _needs_action(f"label run {index} has a missing or duplicate id")
            if not isinstance(run_family, str) or not run_family.strip() or len(run_family) > 256:
                return _needs_action(f"label run {label_id} has an invalid requested family")
            if not isinstance(text, str):
                return _needs_action(f"label run {label_id} does not have source text")
            if isinstance(point_size, bool) or not isinstance(point_size, (int, float)) or not 0 < point_size <= 512:
                return _needs_action(f"label run {label_id} has an invalid point size")
            seen_ids.add(label_id)
            total_chars += len(text)
            normalized_runs.append({"id": label_id, "text": text, "pointSize": float(point_size),
                                    "requestedFamily": run_family})
    except (AttributeError, TypeError):
        return _needs_action("font resolution input must contain label run mappings")
    if total_chars > 250_000:
        return _needs_action("font resolution text input exceeds the bounded character budget")
    swift = shutil.which("swift")
    if not swift:
        return _needs_action("Swift runtime is unavailable for native CoreText queries")
    request = json.dumps({"requestedFamily": requested_family, "runs": normalized_runs}, ensure_ascii=False).encode("utf-8")
    try:
        result = subprocess.run([swift, "-e", _CORETEXT_SWIFT_HELPER], input=request,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180,
                                check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _needs_action(f"native CoreText resolver could not run: {exc}")
    if result.returncode:
        return _needs_action("native CoreText resolver failed: " + result.stderr.decode("utf-8", "replace")[:800])
    try:
        native = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _needs_action(f"native CoreText resolver returned invalid evidence: {exc}")
    if not native.get("resolvedPrimaryFonts") or len(native.get("labels", [])) != len(normalized_runs):
        return _needs_action("CoreText did not resolve every requested label run")
    all_resolved_fonts = list(native.get("resolvedPrimaryFonts", [])) + list(native.get("fallbackFonts", []))
    if any(not isinstance(font.get("styleName"), str) or not font.get("styleName") for font in all_resolved_fonts):
        return _needs_action("CoreText did not return an exact style name for every resolved family")

    # CoreText can resolve a variable-font instance or family alias which is not
    # represented by an identical named face in the underlying TTC. Record the
    # physical face table separately so consumers cannot mistake a descriptor
    # ordinal or a nearby family/style for a Unity faceIndex.
    resolved_rows = []
    for font in all_resolved_fonts:
        path = font.get("systemFontFileUrl")
        if isinstance(path, str) and path and not any(row.get("path") == path for row in resolved_rows):
            resolved_rows.append(_font_file_face_evidence(path))
    file_by_path = {row.get("path"): row for row in resolved_rows}
    coretext_to_physical_faces = []
    for font in all_resolved_fonts:
        path = font.get("systemFontFileUrl")
        file_evidence = file_by_path.get(path, {})
        faces = file_evidence.get("faces", []) if file_evidence.get("status") == "inspected" else []
        ps = font.get("postScriptName")
        exact_ps = [face for face in faces if face.get("postScriptName") == ps]
        exact_family_style = [face for face in faces
                              if face.get("family") == font.get("family")
                              and face.get("subfamily") == font.get("styleName")]
        coretext_to_physical_faces.append({
            "family": font.get("family"), "styleName": font.get("styleName"),
            "postScriptName": ps, "systemFontFileUrl": path,
            "variationAxes": font.get("variationAxes", {}),
            "exactPostScriptFaceCount": len(exact_ps),
            "exactPostScriptFaces": exact_ps,
            "exactFamilyStyleFaceCount": len(exact_family_style),
            "exactFamilyStyleFaces": exact_family_style,
            "unityFontEngineFaceIndexProven": len(exact_ps) == 1,
        })

    missing: list[dict[str, Any]] = []
    required_occurrences = 0
    covered_occurrences = 0
    for label in native["labels"]:
        for scalar in label.get("unicodeScalars", []):
            if not scalar.get("requiredForVisualText"):
                continue
            required_occurrences += 1
            if scalar.get("glyphCovered"):
                covered_occurrences += 1
            else:
                missing.append({k: scalar.get(k) for k in ("targetLabelId", "pointSize", "character", "codepoint", "family", "postScriptName")})
    version = platform.mac_ver()[0] or platform.release()
    try:
        build = subprocess.run(["/usr/bin/sw_vers", "-buildVersion"], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, timeout=5, check=False).stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        build = None
    requested_families = sorted({run["requestedFamily"] for run in normalized_runs})
    record = {
        "schema": "monkey-macos-system-font-resolution/1",
        "status": "resolved" if not missing else "partial",
        "targetOS": "macOS",
        "targetOSVersion": version,
        "targetOSBuild": build,
        "requestedFamily": requested_families[0] if len(requested_families) == 1 else "per-label",
        "requestedFamilies": requested_families,
        "resolvedPrimaryFonts": native["resolvedPrimaryFonts"],
        "fallbackFonts": native.get("fallbackFonts", []),
        "resolvedFontFiles": resolved_rows,
        "coreTextToPhysicalFaceEvidence": coretext_to_physical_faces,
        "glyphCoverage": {
            "requiredUnicodeOccurrences": required_occurrences,
            "coveredUnicodeOccurrences": covered_occurrences,
            "missingUnicodeOccurrences": len(missing),
            "missing": missing,
            "perUnicodeScalar": native.get("unicodeCoverage", []),
        },
        "labels": native["labels"],
        "sourceDefaultEvidence": {
            "sourceProfile": "cocos-2.4.15-bundle",
            "sourceVersion": "2.4.15",
            "sourceFontFamilyDefault": COCOS_2415_SYSTEM_FONT_FAMILY,
            "sourceSystemFontDefault": True,
            "officialSource": COCOS_2415_CC_LABEL_SOURCE + "#L274-L280",
            "systemFontDefaultSource": COCOS_2415_CC_LABEL_SOURCE + "#L371-L372",
            "evidence": "CCLabel.js fontFamily property defaults to Arial; _isSystemFontUsed defaults to true; fontFamily applies only when system font is used.",
            "sourceOSIdentityVerified": False,
        },
        "resolver": {
            "framework": "CoreText",
            "apis": ["CTFontCreateWithName", "CTFontCopyFamilyName", "CTFontCopyName", "kCTFontStyleNameKey", "CTFontCopyPostScriptName",
                     "CTFontCopyAttribute", "kCTFontURLAttribute", "kCTFontVariationAttribute",
                     "CTFontCreateForString", "CTFontCopyCharacterSet", "CFCharacterSetIsLongCharacterMember",
                     "CTFontGetGlyphsForCharacters"],
            "operation": "read-only lookup of fonts already available to the current macOS process",
            "fontRegistrationOrCopy": False,
            "installedFontFileInspection": "read-only hash and SFNT name-table inspection at CoreText-returned URL; no font file is copied or exported",
            "officialDocumentation": [
                "https://developer.apple.com/documentation/coretext/ctfontcreatewithname(_:_:_:)",
                "https://developer.apple.com/documentation/coretext/ctfontcreateforstring(_:_:_:)",
                "https://developer.apple.com/documentation/coretext/ctfontgetglyphsforcharacters(_:_:_:_:)",
                "https://developer.apple.com/documentation/coretext/ctfontcopycharacterset(_:)",
                "https://developer.apple.com/documentation/corefoundation/cfcharactersetislongcharactermember(_:_:)",
                "https://developer.apple.com/documentation/coretext/ctfontcopyname(_:_:)",
                "https://developer.apple.com/documentation/coretext/kctfontstylenamekey",
                "https://developer.apple.com/documentation/coretext/ctfontcopyattribute(_:_:)",
                "https://developer.apple.com/documentation/coretext/kctfonturlattribute",
            ],
        },
        "visualEquivalent": False,
        "limitations": [
            "This records the current macOS target's CoreText selection; it does not identify the source runtime's operating system or installed fonts.",
            "Glyph coverage is a character-to-glyph check and does not establish shaping, line metrics, rasterization, or visual equivalence.",
        ],
    }
    return FontBindingReport(record["status"], record)


def resolve_ir_macos_system_fonts(
    ir: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    *,
    source_manifest_sha256: str | None = None,
) -> FontBindingReport:
    """Resolve normalized source system-font Labels using serialized/default family per Label."""
    source_version = source_manifest.get("sourceVersion")
    source_profile = source_manifest.get("sourceProfile")
    if source_version != "2.4.15" or source_profile != "cocos-2.4.15-bundle":
        return _needs_action("source evidence does not declare the pinned Cocos 2.4.15 profile")
    labels = [c for c in ir.get("components", [])
              if c.get("type") == "cc.Label" and c.get("systemFont") is True and c.get("font") is None]
    if not labels:
        return _needs_action("IR contains no normalized system-font Label samples")
    runs = []
    family_bindings = []
    for index, component in enumerate(labels):
        explicit_family = component.get("fontFamily")
        if explicit_family is None or explicit_family == "":
            requested_family = COCOS_2415_SYSTEM_FONT_FAMILY
            family_source = component.get("fontFamilyDefaultSource") or "official-source-default"
        elif isinstance(explicit_family, str):
            requested_family = explicit_family
            family_source = (component.get("fontFamilyEvidence") or component.get("fontFamilySource")
                             or component.get("fontFamilyDefaultSource")
                             or "normalized-value-source-unverified")
        else:
            return _needs_action(f"Label {component.get('sourceId', index)} has a non-string fontFamily value")
        label_id = str(component.get("sourceId") or f"label-{index}")
        point_size = component.get("fontSize", 12)
        runs.append({"id": label_id, "text": component.get("text", ""), "pointSize": point_size,
                     "requestedFamily": requested_family})
        family_bindings.append({"sourceLabelId": label_id, "requestedFamily": requested_family,
                                "familyBindingSource": family_source, "fontSize": point_size})
    report = resolve_macos_system_font_runs(runs, COCOS_2415_SYSTEM_FONT_FAMILY)
    if report.status in {"unsupported", "needs_action"}:
        return report
    report.record["sourceSample"] = {
        "name": "normalized-IR-sample",
        "sourceVersion": source_version,
        "sourceProfile": source_profile,
        "normalizedSystemFontLabelCount": len(labels),
        "sourceStaticTextLabelCount": sum(bool(run["text"]) for run in runs),
        "sourceOSIdentityVerified": False,
        "sourceManifestSha256": source_manifest_sha256 or source_manifest.get("sourceManifestSha256"),
        "sourceFamilyBindings": family_bindings,
    }
    return report


def resolve_ir_macos_system_font_files(
    ir_path: str | Path,
    source_manifest_path: str | Path,
) -> FontBindingReport:
    """Resolve system-font Labels in a frozen IR, pinning the exact inspect source manifest."""
    try:
        ir_raw = Path(ir_path).read_bytes()
        manifest_raw = Path(source_manifest_path).read_bytes()
        ir = json.loads(ir_raw.decode("utf-8"))
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _needs_action(f"cannot read IR system-font evidence inputs: {exc}")
    source_manifest_sha256 = _sha(manifest_raw)
    ir_source_manifest_sha256 = ir.get("sourceManifestSha256")
    if ir_source_manifest_sha256 != source_manifest_sha256:
        return _needs_action("IR sourceManifestSha256 does not match the supplied inspect source-manifest bytes")
    report = resolve_ir_macos_system_fonts(ir, manifest, source_manifest_sha256=source_manifest_sha256)
    if report.status not in {"unsupported", "needs_action"}:
        report.record["sourceSample"]["name"] = Path(ir_path).parent.parent.name
        report.record["sourceSample"]["frozenInputs"] = {
            "ir": {"path": str(Path(ir_path).resolve()), "sha256": _sha(ir_raw)},
            "sourceManifest": {"path": str(Path(source_manifest_path).resolve()),
                               "sha256": source_manifest_sha256},
        }
    return report


def resolve_pure02_macos_system_fonts(
    ir: Mapping[str, Any], source_manifest: Mapping[str, Any],
) -> FontBindingReport:
    """Compatibility alias for the earlier Pure02-named function."""
    report = resolve_ir_macos_system_fonts(ir, source_manifest)
    if report.status not in {"unsupported", "needs_action"}:
        report.record["sourceSample"]["name"] = "Pure02"
    return report


def resolve_pure02_macos_system_font_files(
    ir_path: str | Path, source_manifest_path: str | Path,
) -> FontBindingReport:
    """Compatibility alias for resolve_ir_macos_system_font_files."""
    return resolve_ir_macos_system_font_files(ir_path, source_manifest_path)
