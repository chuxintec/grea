"""Strict equivalence checks for Unity-generated saved .meta bytes."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass


SCHEMA = "monkey-unity-saved-meta/1"
_GUID = re.compile(r"^[0-9a-fA-F]{32}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_EMPTY_OMISSIONS = {"userData", "assetBundleName", "assetBundleVariant"}


class SavedMetaVerificationError(ValueError):
    """A bounded failure code suitable for the Unity verifier diagnostic."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _Line:
    number: int
    indent: int
    text: str


def _fail(code: str):
    raise SavedMetaVerificationError(code)


def _strip_comment(value: str) -> str:
    quote = None
    escaped = False
    depth = 0
    for i, ch in enumerate(value):
        if quote == '"':
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quote = None
            continue
        if quote == "'":
            if ch == "'":
                quote = None
            continue
        if ch in ('"', "'"):
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == "#" and depth == 0 and (i == 0 or value[i - 1].isspace()):
            return value[:i].rstrip()
    return value.rstrip()


def _split_top_level(value: str, delimiter: str) -> list[str]:
    result=[]; quote=None; escaped=False; depth=0; start=0
    for i,ch in enumerate(value):
        if quote == '"':
            if escaped: escaped=False
            elif ch == "\\": escaped=True
            elif ch == '"': quote=None
            continue
        if quote == "'":
            if ch == "'":
                if i + 1 < len(value) and value[i + 1] == "'":
                    continue
                quote=None
            continue
        if ch in ('"',"'"):
            quote=ch
        elif ch in "[{": depth+=1
        elif ch in "]}": depth-=1
        elif ch == delimiter and depth == 0:
            result.append(value[start:i].strip());start=i+1
    result.append(value[start:].strip())
    return result


def _mapping_pair(value: str) -> tuple[str, str] | None:
    quote=None;escaped=False;depth=0
    for i,ch in enumerate(value):
        if quote == '"':
            if escaped: escaped=False
            elif ch == "\\": escaped=True
            elif ch == '"': quote=None
            continue
        if quote == "'":
            if ch == "'":
                if i + 1 < len(value) and value[i + 1] == "'":
                    continue
                quote=None
            continue
        if ch in ('"',"'"):quote=ch
        elif ch in "[{":depth+=1
        elif ch in "]}":depth-=1
        elif ch == ":" and depth == 0 and (i+1 == len(value) or value[i+1].isspace()):
            key=value[:i].strip()
            if not key:return None
            return key,value[i+1:].strip()
    return None


def _key(raw: str):
    parsed=_scalar(raw)
    if not isinstance(parsed,str) or not parsed:
        _fail("SAVED_META_YAML_INVALID_KEY")
    return parsed


def _scalar(raw: str):
    raw=raw.strip()
    if raw == "": return None
    if raw.startswith("{"):
        if not raw.endswith("}"):_fail("SAVED_META_YAML_UNSUPPORTED_FLOW_MAP")
        inner=raw[1:-1].strip(); result={}
        if not inner:return result
        for item in _split_top_level(inner,","):
            pair=_mapping_pair(item)
            if pair is None:_fail("SAVED_META_YAML_INVALID_FLOW_MAP")
            key=_key(pair[0])
            if key in result:_fail("SAVED_META_DUPLICATE_KEY")
            result[key]=_scalar(pair[1])
        return result
    if raw.startswith("["):
        if not raw.endswith("]"):_fail("SAVED_META_YAML_UNSUPPORTED_FLOW_LIST")
        inner=raw[1:-1].strip()
        return [] if not inner else [_scalar(part) for part in _split_top_level(inner,",")]
    if raw.startswith('"'):
        try:
            value=json.loads(raw)
        except (json.JSONDecodeError,ValueError):
            _fail("SAVED_META_YAML_INVALID_QUOTED_SCALAR")
        if not isinstance(value,str):_fail("SAVED_META_YAML_INVALID_QUOTED_SCALAR")
        return value
    if raw.startswith("'"):
        if not raw.endswith("'") or len(raw)<2:_fail("SAVED_META_YAML_INVALID_QUOTED_SCALAR")
        return raw[1:-1].replace("''","'")
    if raw.startswith(("&","*","!")) or raw in ("|",">"):
        _fail("SAVED_META_YAML_UNSUPPORTED_SCALAR")
    low=raw.lower()
    if low in ("null","~"):return None
    if low in ("true","false"):return low=="true"
    number=raw.replace("_","")
    if re.fullmatch(r"[-+]?(?:0|[1-9][0-9]*)",number):
        try:return int(number,10)
        except ValueError:pass
    if re.fullmatch(r"[-+]?0[xX][0-9a-fA-F]+",number):
        return int(number,16)
    if re.fullmatch(r"[-+]?(?:(?:[0-9]+\.[0-9]*|\.[0-9]+)(?:[eE][-+]?[0-9]+)?|[0-9]+[eE][-+]?[0-9]+)",number):
        return float(number)
    return raw


def _parse_yaml(raw: bytes, code: str) -> dict:
    try:text=raw.decode("utf-8-sig")
    except UnicodeDecodeError:_fail(code)
    lines=[]
    for number,line in enumerate(text.splitlines(),1):
        if "\t" in line[:len(line)-len(line.lstrip())]:_fail("SAVED_META_YAML_TAB_INDENT")
        stripped=_strip_comment(line)
        if not stripped.strip():continue
        content=stripped.lstrip(" ");indent=len(stripped)-len(content)
        if content.startswith("%YAML ") or content.startswith("%TAG ") or content in ("---","..."):
            continue
        if content.startswith("---") or content.startswith("..."):_fail("SAVED_META_YAML_MULTIDOCUMENT")
        lines.append(_Line(number,indent,content))
    if not lines or lines[0].indent != 0:_fail(code)

    def parse_block(index:int,indent:int):
        if index>=len(lines) or lines[index].indent!=indent:_fail(code)
        sequence=lines[index].text=="-" or lines[index].text.startswith("- ")
        value=[] if sequence else {}
        while index<len(lines) and lines[index].indent==indent:
            line=lines[index]
            is_item=line.text=="-" or line.text.startswith("- ")
            if is_item != sequence:
                if sequence:break
                _fail("SAVED_META_YAML_MIXED_BLOCK")
            if sequence:
                rest=line.text[1:].strip();index+=1
                if not rest:
                    if index>=len(lines) or lines[index].indent<=indent:
                        value.append(None)
                    else:
                        child,index=parse_block(index,lines[index].indent);value.append(child)
                    continue
                pair=_mapping_pair(rest)
                if pair is None:
                    value.append(_scalar(rest))
                    if index<len(lines) and lines[index].indent>indent:_fail("SAVED_META_YAML_UNSUPPORTED_SEQUENCE_NESTING")
                    continue
                key=_key(pair[0]);map_value={}
                if pair[1]:map_value[key]=_scalar(pair[1])
                elif index<len(lines) and lines[index].indent>indent:
                    child,index=parse_block(index,lines[index].indent);map_value[key]=child
                else:map_value[key]=None
                if index<len(lines) and lines[index].indent>indent:
                    continuation_indent=lines[index].indent
                    extra,index=parse_block(index,continuation_indent)
                    if not isinstance(extra,dict):_fail("SAVED_META_YAML_INVALID_SEQUENCE_MAP")
                    if key in extra:_fail("SAVED_META_DUPLICATE_KEY")
                    map_value.update(extra)
                value.append(map_value)
            else:
                pair=_mapping_pair(line.text)
                if pair is None:_fail(code)
                key=_key(pair[0])
                if key in value:_fail("SAVED_META_DUPLICATE_KEY")
                index+=1
                if pair[1]:value[key]=_scalar(pair[1])
                elif index<len(lines) and (lines[index].indent>indent or
                        lines[index].indent==indent and (lines[index].text=="-" or lines[index].text.startswith("- "))):
                    child,index=parse_block(index,lines[index].indent);value[key]=child
                else:value[key]=None
                if index<len(lines) and lines[index].indent>indent:
                    _fail("SAVED_META_YAML_INDENT_INVALID")
        return value,index

    result,end=parse_block(0,0)
    if end!=len(lines) or not isinstance(result,dict):_fail(code)
    return result


def _meta_identity(document: dict, code: str):
    guid=document.get("guid")
    if not isinstance(guid,str) or not _GUID.fullmatch(guid):_fail("SAVED_META_GUID_MISSING_OR_INVALID")
    importer_types=[key for key,value in document.items() if key.endswith("Importer") and isinstance(value,dict)]
    if len(importer_types)!=1:_fail("SAVED_META_IMPORTER_TYPE_MISSING_OR_AMBIGUOUS")
    importer=importer_types[0]
    return guid.lower(),importer


def _is_empty(value) -> bool:
    return value is None or value == ""


def _compare(source,saved,path,omissions):
    if type(source) is not type(saved):_fail("SAVED_META_EFFECTIVE_FIELD_CHANGED:"+(path or "<root>"))
    if isinstance(source,dict):
        for key in sorted(source.keys()|saved.keys()):
            child_path=f"{path}.{key}" if path else key
            if key not in source or key not in saved:
                present=source[key] if key in source else saved[key]
                parts=child_path.split(".")
                allowed_scope=(len(parts)==1 or len(parts)==2 and parts[0].endswith("Importer"))
                if key in source and key not in saved and key in _ALLOWED_EMPTY_OMISSIONS and allowed_scope and _is_empty(present):
                    omissions.append({"path":child_path,"omittedFrom":"saved","value":present})
                    continue
                _fail("SAVED_META_EFFECTIVE_FIELD_MISSING_OR_ADDED:"+child_path)
            _compare(source[key],saved[key],child_path,omissions)
    elif isinstance(source,list):
        if len(source)!=len(saved):_fail("SAVED_META_EFFECTIVE_FIELD_CHANGED:"+(path or "<root>"))
        for index,(left,right) in enumerate(zip(source,saved)):_compare(left,right,f"{path}[{index}]",omissions)
    elif source!=saved:
        _fail("SAVED_META_EFFECTIVE_FIELD_CHANGED:"+(path or "<root>"))


def verify_saved_meta(source_raw: bytes, saved_raw: bytes, expected_saved_sha256: str) -> dict:
    """Verify Unity saved .meta bytes against the pinned readback hash and source semantics.

    This function never writes either byte stream. Its only semantic allowance
    is omission of an empty ``userData``, ``assetBundleName`` or
    ``assetBundleVariant`` field at the root or importer mapping level.
    """
    if not isinstance(source_raw,bytes) or not isinstance(saved_raw,bytes):
        _fail("SAVED_META_BYTES_REQUIRED")
    if not isinstance(expected_saved_sha256,str) or not _SHA256.fullmatch(expected_saved_sha256):
        _fail("SAVED_META_EXPECTED_SHA256_INVALID")
    source_sha=hashlib.sha256(source_raw).hexdigest()
    saved_sha=hashlib.sha256(saved_raw).hexdigest()
    if saved_sha!=expected_saved_sha256:_fail("SAVED_META_READBACK_SHA256_MISMATCH")
    try:source=_parse_yaml(source_raw,"SAVED_META_SOURCE_YAML_INVALID")
    except SavedMetaVerificationError:raise
    try:saved=_parse_yaml(saved_raw,"SAVED_META_SAVED_YAML_INVALID")
    except SavedMetaVerificationError:raise
    source_guid,source_importer=_meta_identity(source,"SAVED_META_SOURCE")
    saved_guid,saved_importer=_meta_identity(saved,"SAVED_META_SAVED")
    if source_guid!=saved_guid:_fail("SAVED_META_GUID_CHANGED")
    if source_importer!=saved_importer:_fail("SAVED_META_IMPORTER_TYPE_CHANGED")
    omissions=[]
    _compare(source,saved,"",omissions)
    # Semantic equality alone would also conceal unrelated comment, layout or
    # scalar spelling edits. Permit precisely the proven empty-field removals;
    # every retained byte must still be identical to the generator output.
    omitted_paths={item['path'] for item in omissions}
    removed=set();kept=[];root_key=None
    empty_field=re.compile(rb"^( *)([A-Za-z_][A-Za-z0-9_]*):[ \t]*(?:\"\"|''|null|~)?[ \t]*(?:\r?\n)?$")
    for line in source_raw.splitlines(keepends=True):
        top=re.match(rb'^([A-Za-z_][A-Za-z0-9_]*):',line)
        if top:root_key=top.group(1).decode('ascii')
        match=empty_field.fullmatch(line)
        path=None
        if match:
            indent=len(match.group(1));key=match.group(2).decode('ascii')
            if indent==0:path=key
            elif indent==2 and root_key==source_importer:path=source_importer+'.'+key
        if path in omitted_paths:
            removed.add(path)
        else:kept.append(line)
    if removed!=omitted_paths or b''.join(kept)!=saved_raw:
        _fail('SAVED_META_UNAPPROVED_BYTE_CHANGE')
    importer=source[source_importer]
    main_id=importer.get("mainObjectFileID")
    return {
        "schema":SCHEMA,
        "verified":True,
        "sourceSha256":source_sha,
        "savedSha256":saved_sha,
        "expectedSavedSha256":expected_saved_sha256,
        "guid":source_guid,
        "importerType":source_importer,
        "mainObjectFileID":main_id,
        "fieldCount":_field_count(source),
        "allowedDiff":omissions,
    }


def _field_count(value) -> int:
    if isinstance(value,dict):return sum(_field_count(child) for child in value.values())+len(value)
    if isinstance(value,list):return sum(_field_count(child) for child in value)+len(value)
    return 1
