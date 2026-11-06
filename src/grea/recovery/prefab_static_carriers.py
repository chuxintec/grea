"""Generate disabled, serializable native carriers for frozen static fields."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from .io import inside, sha, write_json


_PREFIX = {
    "unity": "Assets/Game/Scripts/Presentation/Recovered/StaticFields/",
    "creator": "assets/Game/Scripts/Presentation/Recovered/StaticFields/",
}
_NAMESPACE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NATIVE_SCALARS = {"bool", "float", "string", "node_ref", "component_ref", "asset_ref"}
_CREATOR_PRIMITIVES = {
    "cc.Boolean": ("bool", "CCBoolean"), "Boolean": ("bool", "CCBoolean"), "boolean": ("bool", "CCBoolean"),
    "cc.Float": ("float", "CCFloat"), "Float": ("float", "CCFloat"), "Number": ("float", "CCFloat"), "number": ("float", "CCFloat"),
    "cc.Integer": ("float", "CCInteger"), "Integer": ("float", "CCInteger"), "cc.String": ("string", "CCString"),
    "String": ("string", "CCString"), "string": ("string", "CCString"),
}
_ASSET_TYPES = {"cc.Asset", "cc.SpriteFrame", "cc.Texture2D", "cc.AudioClip", "cc.Prefab",
                "cc.SpriteAtlas", "cc.Font", "cc.Material", "cc.AnimationClip", "cc.JsonAsset",
                "cc.TextAsset", "cc.RenderTexture", "cc.ImageAsset", "cc.BufferAsset", "cc.EffectAsset"}
_COMPONENT_TYPES = {"cc.Component", "cc.RenderComponent", "cc.UIComponent", "cc.Sprite", "cc.Label", "cc.RichText",
                    "cc.Button", "cc.ScrollView", "cc.Layout", "cc.Mask", "cc.Canvas", "cc.Widget",
                    "cc.BlockInputEvents", "cc.Animation", "cc.ProgressBar", "cc.Slider", "cc.Toggle",
                    "cc.ToggleContainer", "cc.EditBox", "cc.Graphics", "cc.AudioSource", "cc.VideoPlayer", "cc.WebView",
                    "sp.Skeleton"}
_CREATOR_REFERENCE_TYPES = {"cc.Node": "Node", "cc.Scene": "Node", "cc.Asset": "Asset",
    "cc.SpriteFrame": "SpriteFrame", "cc.Texture2D": "Texture2D", "cc.AudioClip": "AudioClip",
    "cc.Prefab": "Prefab", "cc.SpriteAtlas": "SpriteAtlas", "cc.Font": "Font", "cc.Material": "Material",
    "cc.AnimationClip": "AnimationClip", "cc.JsonAsset": "JsonAsset", "cc.TextAsset": "TextAsset",
    "cc.RenderTexture": "RenderTexture", "cc.ImageAsset": "ImageAsset", "cc.BufferAsset": "BufferAsset",
    "cc.EffectAsset": "EffectAsset", "cc.Sprite": "Sprite", "cc.Label": "Label", "cc.RichText": "RichText",
    "cc.Button": "Button", "cc.ScrollView": "ScrollView", "cc.Layout": "Layout", "cc.Mask": "Mask",
    "cc.Canvas": "Canvas", "cc.Widget": "Widget", "cc.BlockInputEvents": "BlockInputEvents",
    "cc.Animation": "Animation", "cc.ProgressBar": "ProgressBar", "cc.Slider": "Slider", "cc.Toggle": "Toggle",
    "cc.ToggleContainer": "ToggleContainer", "cc.EditBox": "EditBox", "cc.Graphics": "Graphics",
    "cc.AudioSource": "AudioSource", "cc.VideoPlayer": "VideoPlayer", "cc.WebView": "WebView",
    "cc.Component": "Component", "cc.UIComponent": "Component", "cc.RenderComponent": "Component",
    "sp.Skeleton": "Component"}
_STATIC_TYPE_PREFIX = "__monkey_static_type_v1__:"


class StaticCarrierError(ValueError):
    """Invalid snapshot, schema, or owned generated file."""


def _native_double(value):
    if type(value) not in (int, float):
        return False
    try:
        converted = float(value)
    except OverflowError:
        return False
    return math.isfinite(converted) and (type(value) is not int or int(converted) == value)


def _slug(value):
    value = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_") or "Component"
    if value[0].isdigit():
        value = "T_" + value
    return value[:48]


def _json(value):
    def reject(item):
        if isinstance(item, float) and not math.isfinite(item):
            raise StaticCarrierError("snapshot contains a non-finite number")
        raise TypeError(f"not JSON serializable: {type(item).__name__}")
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), default=reject)
    except (TypeError, ValueError) as error:
        raise StaticCarrierError(f"snapshot value is not finite JSON: {error}") from error


def _reference_kind(source_declared_type):
    if not isinstance(source_declared_type, str):
        return None
    value = source_declared_type.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1].strip()
    if value in _CREATOR_PRIMITIVES or value.startswith("cc.Enum("):
        return None
    if value in {"cc.Node", "cc.Scene"}:
        return "node_ref"
    if value in _ASSET_TYPES:
        return "asset_ref"
    if value in _COMPONENT_TYPES:
        return "component_ref"
    return None


def _creator_reference_type(source_declared_type, reference_kind):
    return _CREATOR_REFERENCE_TYPES.get(source_declared_type.strip() if isinstance(source_declared_type, str) else "") or {
        "node_ref": "Node", "component_ref": "Component", "asset_ref": "Asset"}[reference_kind]


def _declared_array_type(source_declared_type):
    if not isinstance(source_declared_type, str):
        return None
    value = source_declared_type.strip()
    if value.startswith("[") and value.endswith("]") and value[1:-1].strip().startswith(_STATIC_TYPE_PREFIX):
        value = value[1:-1].strip()
    if value.startswith(_STATIC_TYPE_PREFIX):
        try:
            descriptor = json.loads(value[len(_STATIC_TYPE_PREFIX):])
        except json.JSONDecodeError:
            return None
        if isinstance(descriptor, dict) and descriptor.get("kind") == "array":
            element = descriptor.get("element")
            if isinstance(element, dict) and element.get("kind") == "record" and isinstance(element.get("fields"), list):
                return {"kind": "record", "creatorType": "record", "sourceType": descriptor,
                        "record": element}
        return None
    if not (value.startswith("[") and value.endswith("]")):
        return None
    element_type = value[1:-1].strip()
    primitive = _CREATOR_PRIMITIVES.get(element_type)
    if primitive:
        return {"kind": primitive[0], "creatorType": primitive[1], "sourceType": element_type}
    if element_type.startswith("cc.Enum("):
        return {"kind": "float", "creatorType": "CCInteger", "sourceType": element_type}
    reference_kind = _reference_kind(element_type)
    if reference_kind:
        return {"kind": reference_kind, "creatorType": _creator_reference_type(element_type, reference_kind),
            "sourceType": element_type}
    return None


def _native_array_field(result, element_kind, creator_element_type, values):
    storage = {"bool": "bool[]", "float": "double[]", "string": "string[]"}.get(
        element_kind, "UnityEngine.Object[]")
    result.update(storageType=storage, elementKind=element_kind, creatorElementType=creator_element_type)
    value_key = {"bool": "boolValues", "float": "numberValues", "string": "stringValues"}.get(
        element_kind, "refValues")
    result[value_key] = values
    return result


def _native_array_field(result, element_kind, creator_element_type, values):
    storage = {"bool": "bool[]", "float": "double[]", "string": "string[]"}.get(
        element_kind, "UnityEngine.Object[]")
    result.update(storageType=storage, elementKind=element_kind, creatorElementType=creator_element_type)
    value_key = {"bool": "boolValues", "float": "numberValues", "string": "stringValues"}.get(
        element_kind, "refValues")
    result[value_key] = values
    return result


def _field_plan(field, index):
    if not isinstance(field, dict) or not isinstance(field.get("name"), str) or not field["name"]:
        raise StaticCarrierError("field record must have a non-empty source name")
    name, kind, value = field["name"], field.get("kind"), field.get("value")
    declared_type = field.get("sourceDeclaredType")
    if declared_type is not None and not isinstance(declared_type, str):
        raise StaticCarrierError(f"field {name!r} has an invalid sourceDeclaredType")
    declaration_evidence = field.get("declarationEvidence") if isinstance(field.get("declarationEvidence"), dict) else {}
    source_constant = field.get("sourceConstant", "" if field.get("serializedOverride") else declaration_evidence.get("sourceConstant", ""))
    accessor_backing = field.get("accessorBacking", declaration_evidence.get("accessorBacking"))
    field_name = f"__sf_{index:03d}_{_slug(name)}"
    result = {"name": name, "sourceFieldName": name, "fieldName": field_name, "kind": kind,
              "sourceDeclaredType": declared_type or "", "referenceKind": "", "nullExpected": False,
              "creatorType": "", "creatorElementType": "",
              "sourceConstant": source_constant if isinstance(source_constant, str) else "",
              "sourceValueEncoding": "", "sourceValueEncodingJson": "",
              "accessorBacking": accessor_backing if isinstance(accessor_backing, dict) else None,
              "accessorBackingJson": _json(accessor_backing) if isinstance(accessor_backing, dict) else "",
              "dynamicType": "",
              "numberValue": 0.0, "stringValue": "", "boolValue": False, "refValue": "",
              "colorR": 0, "colorG": 0, "colorB": 0, "colorA": 0,
              "numberValues": [], "stringValues": [], "boolValues": [], "refValues": [], "snapshotJson": ""}
    if kind in {"bool", "float", "string"}:
        if declared_type == "cc.Color":
            raise StaticCarrierError(f"cc.Color field {name!r} must be encoded as an object")
        if kind == "bool" and type(value) is not bool:
            raise StaticCarrierError(f"boolean field {name!r} has an invalid value")
        if kind == "float" and not _native_double(value):
            raise StaticCarrierError(f"numeric field {name!r} has an invalid value")
        if kind == "string" and not isinstance(value, str):
            raise StaticCarrierError(f"string field {name!r} has an invalid value")
        result["storageType"] = {"bool": "bool", "float": "double", "string": "string"}[kind]
        result[{"bool": "boolValue", "float": "numberValue", "string": "stringValue"}[kind]] = value
        primitive_hint = None
        if declared_type:
            primitive_hint = _CREATOR_PRIMITIVES.get(declared_type.strip())
            if declared_type.strip().startswith("cc.Enum("):
                primitive_hint = ("float", "CCInteger")
        if primitive_hint and primitive_hint[0] != kind:
            # Preserve the actual serialized/default literal when a source
            # decorator contradicts it; do not coerce Boolean to enum number.
            result["creatorType"] = {"bool": "CCBoolean", "float": "CCFloat", "string": "CCString"}[kind]
            return result, "source_declared_primitive_conflict:" + name
        result["creatorType"] = primitive_hint[1] if primitive_hint else {
            "bool": "CCBoolean", "float": "CCFloat", "string": "CCString"}[kind]
        return result, None
    if kind in {"node_ref", "component_ref", "asset_ref"}:
        if not isinstance(value, str) or not value:
            raise StaticCarrierError(f"reference field {name!r} must contain an exact sourceId")
        result.update(storageType="UnityEngine.Object", refValue=value,
                      creatorType=_creator_reference_type(declared_type, kind))
        return result, None
    if kind == "null":
        if value is not None:
            raise StaticCarrierError(f"null field {name!r} has a non-null value")
        reference_kind = _reference_kind(declared_type) if declared_type else "component_ref"
        if reference_kind is None:
            gap = "null_declared_type_not_native_reference:" + name
            result.update(storageType="string", mode="snapshot-json", snapshotJson="null", stringValue="null")
            return result, gap
        result.update(storageType="UnityEngine.Object", referenceKind=reference_kind, nullExpected=True,
                      creatorType=_creator_reference_type(declared_type, reference_kind))
        if not declared_type:
            result["dynamicType"] = "unverified"
        return result, None
    if kind == "array":
        if not isinstance(value, list):
            raise StaticCarrierError(f"array field {name!r} has a non-array value")
        declared_element = _declared_array_type(declared_type)
        if declared_element:
            expected_kind = declared_element["kind"]
            if expected_kind == "record":
                record = declared_element["record"]
                record_fields = []
                for field_index, schema_field in enumerate(record["fields"]):
                    field, field_gap = _field_plan({"name": schema_field["name"], "kind": schema_field["kind"],
                        "value": schema_field.get("value"), "sourceDeclaredType": schema_field.get("sourceDeclaredType"),
                        "sourceConstant": schema_field.get("sourceConstant"), "accessorBacking": schema_field.get("accessorBacking"),
                        "declarationEvidence": schema_field.get("declarationEvidence")}, field_index)
                    if field_gap:
                        raise StaticCarrierError(f"record field {schema_field['name']!r} has unsupported declaration: {field_gap}")
                    record_fields.append(field)
                record_schema_sha = hashlib.sha256(_json({"name": record["name"], "fields": [
                    {key: item.get(key) for key in ("name", "kind", "storageType", "creatorType", "referenceKind", "nullExpected")}
                    for item in record_fields]}).encode("utf-8")).hexdigest()[:10]
                record_type = "StaticRecord_" + _slug(record["name"]) + "_" + record_schema_sha
                rows = []
                defaults = {field["name"]: field for field in record_fields}
                for row_index, item in enumerate(value):
                    if not isinstance(item, dict) or item.get("kind") != "object" or not isinstance(item.get("value"), dict):
                        raise StaticCarrierError(f"record array {name!r} contains a non-object row")
                    payload = item["value"]
                    type_tag = payload.get("__type__")
                    if isinstance(type_tag, dict): type_tag = type_tag.get("value") if type_tag.get("kind") == "string" else None
                    if type_tag != record["name"]:
                        raise StaticCarrierError(f"record array {name!r} has an unproven item type {type_tag!r}")
                    row_fields = []
                    for schema_field in record["fields"]:
                        field_name = schema_field["name"]
                        actual = payload.get(field_name)
                        if actual is None:
                            actual = {"kind": schema_field["kind"], "value": schema_field.get("value")}
                        if not isinstance(actual, dict) or "kind" not in actual:
                            raise StaticCarrierError(f"record array {name!r}.{field_name} is malformed")
                        expected = defaults[field_name]
                        kind_value = actual.get("kind")
                        compatible = kind_value == expected["kind"] or (expected["kind"] == "null" and kind_value in _NATIVE_SCALARS)
                        if not compatible:
                            raise StaticCarrierError(f"record array {name!r}.{field_name} conflicts with its declared record field")
                        value_value = actual.get("value")
                        if kind_value in {"node_ref", "component_ref", "asset_ref"} and (not isinstance(value_value, str) or not value_value):
                            raise StaticCarrierError(f"record reference {name!r}.{field_name} has no exact sourceId")
                        if kind_value == "float" and not _native_double(value_value):
                            raise StaticCarrierError(f"record number {name!r}.{field_name} is not exact in double")
                        if kind_value == "bool" and type(value_value) is not bool:
                            raise StaticCarrierError(f"record boolean {name!r}.{field_name} is invalid")
                        if kind_value == "string" and not isinstance(value_value, str):
                            raise StaticCarrierError(f"record string {name!r}.{field_name} is invalid")
                        if expected["storageType"] == "Color":
                            if kind_value != "object" or not isinstance(value_value, dict) or set(value_value) != {"r", "g", "b", "a"}:
                                raise StaticCarrierError(f"record Color {name!r}.{field_name} is malformed")
                            color_channels = [value_value[key] for key in ("r", "g", "b", "a")]
                            if any(type(channel) is not int or not 0 <= channel <= 255 for channel in color_channels):
                                raise StaticCarrierError(f"record Color {name!r}.{field_name} is outside [0,255]")
                        else:
                            color_channels = [0, 0, 0, 0]
                        nested_row = {"name": field_name, "sourceFieldName": field_name,
                            "fieldName": expected["fieldName"], "kind": kind_value, "value": value_value,
                            "sourceDeclaredType": expected.get("sourceDeclaredType", ""),
                            "storageType": expected["storageType"], "referenceKind": expected.get("referenceKind", ""),
                            "nullExpected": kind_value == "null", "enumValues": schema_field.get("enumValues", []),
                            "sourceConstant": expected.get("sourceConstant", ""),
                            "colorR": color_channels[0], "colorG": color_channels[1],
                            "colorB": color_channels[2], "colorA": color_channels[3],
                            "numberValue": 0.0, "stringValue": "", "boolValue": False, "refValue": ""}
                        if kind_value == "bool": nested_row["boolValue"] = value_value
                        elif kind_value == "float": nested_row["numberValue"] = value_value
                        elif kind_value == "string": nested_row["stringValue"] = value_value
                        elif kind_value in {"node_ref", "component_ref", "asset_ref"}: nested_row["refValue"] = value_value
                        row_fields.append(nested_row)
                    unknown = sorted(set(payload) - {"__type__", *(field["name"] for field in record["fields"])})
                    if unknown:
                        raise StaticCarrierError(f"record array {name!r} contains undeclared fields: {unknown}")
                    rows.append({"index": row_index, "fields": row_fields})
                result.update(storageType=record_type + "[]", elementKind="record", creatorElementType=record_type,
                    recordTypeName=record_type, recordName=record["name"], recordSchema=record_fields, recordValues=rows)
                return result, None
            if not value:
                native_array = _native_array_field(result, expected_kind, declared_element["creatorType"], [])
                return native_array, None
            encoded_kinds = [item.get("kind") for item in value if isinstance(item, dict) and "kind" in item]
            if len(encoded_kinds) != len(value) or any(item_kind != expected_kind for item_kind in encoded_kinds):
                result.update(storageType="string", mode="snapshot-json", snapshotJson=_json(value), stringValue=_json(value), creatorType="CCString")
                return result, "array_declared_type_mismatch:" + name
        item_kinds = [item.get("kind") for item in value if isinstance(item, dict) and "kind" in item]
        if len(item_kinds) == len(value) and value and len(set(item_kinds)) == 1 and item_kinds[0] in _NATIVE_SCALARS:
            element_kind = item_kinds[0]
            values = [item.get("value") for item in value]
            if element_kind == "bool" and any(type(item) is not bool for item in values):
                raise StaticCarrierError(f"boolean array {name!r} has invalid values")
            if element_kind == "float" and any(not _native_double(item) for item in values):
                result.update(storageType="string", mode="snapshot-json", snapshotJson=_json(value), stringValue=_json(value))
                return result, "array_number_not_exact_in_double:" + name
            if element_kind == "string" and any(not isinstance(item, str) for item in values):
                raise StaticCarrierError(f"string array {name!r} has invalid values")
            if element_kind in {"node_ref", "component_ref", "asset_ref"} and any(not isinstance(item, str) or not item for item in values):
                raise StaticCarrierError(f"reference array {name!r} has invalid sourceIds")
            creator_element_type = ((declared_element or {}).get("creatorType") or {
                "bool": "CCBoolean", "float": "CCFloat", "string": "CCString",
                "node_ref": "Node", "component_ref": "Component", "asset_ref": "Asset"}[element_kind])
            return _native_array_field(result, element_kind, creator_element_type, values), None
        gap = "array_not_native_typed:" + name
        result.update(storageType="string", mode="snapshot-json", snapshotJson=_json(value), stringValue=_json(value), creatorType="CCString")
        return result, gap
    if kind == "object" and declared_type == "cc.Color":
        source_color_value = value
        packed_color = False
        if isinstance(value, dict) and set(value) == {"__value_type__", "values"}:
            tag, payload = value["__value_type__"], value["values"]
            if isinstance(tag, dict) and set(tag) == {"kind", "value"} and tag["kind"] == "float": tag = tag["value"]
            if isinstance(payload, dict) and set(payload) == {"kind", "value"} and payload["kind"] == "array": payload = payload["value"]
            if type(tag) is not int or tag != 4 or not isinstance(payload, list) or len(payload) != 1:
                raise StaticCarrierError(f"cc.Color field {name!r} has invalid packed value type")
            packed = payload[0]
            if isinstance(packed, dict) and set(packed) == {"kind", "value"} and packed["kind"] == "float": packed = packed["value"]
            if type(packed) is not int or not 0 <= packed <= 0xffffffff:
                raise StaticCarrierError(f"cc.Color field {name!r} has invalid packed uint32")
            value = dict(zip(("r", "g", "b", "a"), ((packed >> shift) & 255 for shift in (0, 8, 16, 24))))
            packed_color = True
        if not isinstance(value, dict) or set(value) != {"r", "g", "b", "a"}:
            raise StaticCarrierError(f"cc.Color field {name!r} must contain exactly r/g/b/a channels")
        raw_channels = [value[key] for key in ("r", "g", "b", "a")]
        typed_channels = all(isinstance(channel, dict) and set(channel) == {"kind", "value"} and
                             channel.get("kind") == "float" for channel in raw_channels)
        plain_channels = all(type(channel) is int for channel in raw_channels)
        if not typed_channels and not plain_channels:
            raise StaticCarrierError(f"cc.Color field {name!r} channels must be exact integers or source-encoded float literals")
        channels = [channel["value"] if typed_channels else channel for channel in raw_channels]
        if any(type(channel) is not int or not 0 <= channel <= 255 for channel in channels):
            raise StaticCarrierError(f"cc.Color field {name!r} channels must be exact integers in [0,255]")
        if source_constant not in (None, "") and not isinstance(source_constant, str):
            raise StaticCarrierError(f"cc.Color field {name!r} has invalid sourceConstant")
        if source_constant == "cc.Color.WHITE" and channels != [255, 255, 255, 255]:
            raise StaticCarrierError(f"cc.Color field {name!r} conflicts with sourceConstant cc.Color.WHITE")
        if accessor_backing is not None and (not isinstance(accessor_backing, dict) or
                accessor_backing.get("propertyName") != name or
                not isinstance(accessor_backing.get("backingFieldName"), str)):
            raise StaticCarrierError(f"cc.Color field {name!r} has invalid accessor backing evidence")
        result.update(storageType="Color", creatorType="Color", mode="typed-color",
                      colorR=channels[0], colorG=channels[1], colorB=channels[2], colorA=channels[3],
                      sourceValueEncoding="cocos24_packed_aabbggrr/1" if packed_color else ("nested_static_float_channel_values/1" if typed_channels else "plain_rgba_integer_channels/1"),
                      sourceValueEncodingJson=_json(source_color_value))
        return result, None
    if kind in {"object", "null", "unresolved_ref"}:
        gap = "field_snapshot_json_not_native:" + name
        result.update(storageType="string", mode="snapshot-json", snapshotJson=_json(value), stringValue=_json(value), creatorType="CCString")
        return result, gap
    raise StaticCarrierError(f"unsupported snapshot field kind {kind!r} for {name!r}")


def _schema(type_name, fields):
    return [{key: field.get(key) for key in ("name", "fieldName", "kind", "storageType", "elementKind", "mode",
                                              "sourceDeclaredType", "referenceKind", "nullExpected", "creatorType",
                                              "creatorElementType", "recordTypeName", "recordSchema")}
            for field in fields]


def _cs_literal(value):
    return json.dumps(value, ensure_ascii=True)


def _unity_script(namespace, class_name, fields):
    lines = ["// Generated disabled static-field carrier. No source behavior is implemented.",
             "using System;", "using UnityEngine;", "", f"namespace {namespace}", "{"]
    records = {}
    for field in fields:
        if field.get("recordTypeName"):
            records[field["recordTypeName"]] = field.get("recordSchema", [])
    for record_type, record_fields in sorted(records.items()):
        lines.extend(["    [Serializable]", f"    public sealed class {record_type}", "    {"])
        for record_field in record_fields:
            field_type = record_field["storageType"]
            if field_type == "bool": initial = "false"
            elif field_type == "double": initial = "0d"
            elif field_type == "string": initial = "string.Empty"
            elif field_type == "Color":
                field_type = "Color32"
                initial = f"new Color32({record_field['colorR']}, {record_field['colorG']}, {record_field['colorB']}, {record_field['colorA']})"
            elif field_type == "UnityEngine.Object": initial = "null"
            else: raise StaticCarrierError(f"unsupported Unity record field storage type {field_type}")
            lines.append(f"        [SerializeField] public {field_type} {record_field['fieldName']} = {initial};")
        lines.extend(["    }", ""])
    lines += [f"    public sealed class {class_name} : MonoBehaviour", "    {"]
    lines.append("        [SerializeField, HideInInspector] public string __monkeySourceId = string.Empty;")
    for field in fields:
        field_type = field["storageType"]
        if field_type == "bool":
            initial = "false"
        elif field_type == "double":
            initial = "0d"
        elif field_type == "string":
            initial = "string.Empty"
        elif field_type == "Color":
            field_type = "Color32"
            initial = f"new Color32({field['colorR']}, {field['colorG']}, {field['colorB']}, {field['colorA']})"
        elif field_type == "bool[]":
            initial = "Array.Empty<bool>()"
        elif field_type == "double[]":
            initial = "Array.Empty<double>()"
        elif field_type == "string[]":
            initial = "Array.Empty<string>()"
        elif field_type == "UnityEngine.Object":
            initial = "null"
        elif field_type == "UnityEngine.Object[]":
            initial = "Array.Empty<UnityEngine.Object>()"
        elif field.get("recordTypeName") and field_type == field["recordTypeName"] + "[]":
            initial = f"Array.Empty<{field['recordTypeName']}>()"
        else:
            raise StaticCarrierError(f"unsupported Unity storage type {field_type}")
        lines.append(f"        [SerializeField] public {field_type} {field['fieldName']} = {initial};")
    lines += ["    }", "}", ""]
    return "\n".join(lines)


def _creator_script(namespace, class_name, fields):
    required = {"_decorator", "Component"}
    primitive={"bool":"CCBoolean","double":"CCFloat","string":"CCString"}
    element={"bool":"CCBoolean","float":"CCFloat","string":"CCString","node_ref":"Node","component_ref":"Component","asset_ref":"Asset"}
    for field in fields:
        storage=field.get("storageType","")
        if storage in primitive:required.add(field.get("creatorType")or primitive[storage])
        elif storage == "Color": required.add("Color")
        elif storage.endswith("[]"):required.add(field.get("creatorElementType")or element.get(field.get("elementKind"),""))
        elif storage=="UnityEngine.Object":required.add(field.get("creatorType")or element.get(field.get("referenceKind")or field.get("kind"),""))
        for nested in field.get("recordSchema", []):
            nested_storage=nested.get("storageType","")
            if nested_storage=="bool":required.add(nested.get("creatorType")or "CCBoolean")
            elif nested_storage=="double":required.add(nested.get("creatorType")or "CCFloat")
            elif nested_storage=="Color":required.add("Color")
            elif nested_storage=="string":required.add(nested.get("creatorType")or "CCString")
            elif nested_storage=="UnityEngine.Object":required.add(nested.get("creatorType")or "Asset")
    import_order = ("_decorator", "Asset", "Animation", "AnimationClip", "AudioClip", "AudioSource",
        "BlockInputEvents", "BufferAsset", "Button", "Canvas", "CCBoolean", "CCFloat", "CCInteger",
        "CCString", "Color", "Component", "EditBox", "EffectAsset", "Font", "Graphics", "ImageAsset", "JsonAsset",
        "Label", "Layout", "Mask", "Material", "Node", "Prefab", "ProgressBar", "RenderTexture",
        "RichText", "ScrollView", "Slider", "Sprite", "SpriteAtlas", "SpriteFrame", "TextAsset",
        "Texture2D", "Toggle", "ToggleContainer", "VideoPlayer", "WebView", "Widget")
    imports = ", ".join(item for item in import_order if item in required)
    lines = ["// Generated disabled static-field carrier. No source behavior is implemented.",
             f"import {{ {imports} }} from 'cc';",
             "const { ccclass, property } = _decorator;", ""]
    records = {}
    for field in fields:
        if field.get("recordTypeName"):
            records[field["recordTypeName"]] = field.get("recordSchema", [])
    for record_type, record_fields in sorted(records.items()):
        lines += [f"@ccclass({_cs_literal(namespace + '.' + record_type)})", f"export class {record_type} {{"]
        for nested in record_fields:
            nested_storage=nested["storageType"]
            if nested_storage=="bool": prop,ts_type,initial=nested.get("creatorType")or "CCBoolean","boolean","false"
            elif nested_storage=="double": prop,ts_type,initial=nested.get("creatorType")or "CCFloat","number",str(nested.get("numberValue",0))
            elif nested_storage=="string": prop,ts_type,initial=nested.get("creatorType")or "CCString","string",_cs_literal(nested.get("stringValue",""))
            elif nested_storage=="Color": prop,ts_type,initial="Color","Color",f"new Color({nested['colorR']}, {nested['colorG']}, {nested['colorB']}, {nested['colorA']})"
            elif nested_storage=="UnityEngine.Object":
                prop=nested.get("creatorType")or "Asset";ts_type=f"{prop} | null";initial="null"
            else: raise StaticCarrierError(f"unsupported Creator record field storage type {nested_storage}")
            lines.append(f"    @property({prop}) public {nested['fieldName']}: {ts_type} = {initial};")
        lines += ["}", ""]
    lines += [f"@ccclass({_cs_literal(namespace + '.' + class_name)})",
             f"export class {class_name} extends Component {{"]
    lines.append("    @property({ visible: false }) public __monkeySourceId: string = '';")
    for field in fields:
        storage = field["storageType"]
        if storage == "bool":
            prop, ts_type, initial = field.get("creatorType") or "CCBoolean", "boolean", "false"
        elif storage == "double":
            prop, ts_type, initial = field.get("creatorType") or "CCFloat", "number", "0"
        elif storage == "string":
            prop, ts_type, initial = field.get("creatorType") or "CCString", "string", "''"
        elif storage == "Color":
            prop, ts_type = "Color", "Color"
            initial = f"new Color({field['colorR']}, {field['colorG']}, {field['colorB']}, {field['colorA']})"
        elif storage == "UnityEngine.Object":
            kind = field.get("referenceKind") or field["kind"]
            native = field.get("creatorType") or {"node_ref": "Node", "component_ref": "Component", "asset_ref": "Asset"}[kind]
            prop, ts_type, initial = native, f"{native} | null", "null"
        elif storage.endswith("[]"):
            element = field.get("elementKind")
            native = field.get("creatorElementType") or {"bool": "CCBoolean", "float": "CCFloat", "string": "CCString",
                      "node_ref": "Node", "component_ref": "Component", "asset_ref": "Asset", "record": field.get("recordTypeName")}[element]
            if element == "record":
                prop, ts_type, initial = f"[{native}]", f"{native}[]", "[]"
                lines.append(f"    @property({prop}) public {field['fieldName']}: {ts_type} = {initial};")
                continue
            ts_types = {"CCBoolean": "boolean", "CCFloat": "number", "CCInteger": "number", "CCString": "string",
                        "Node": "Node", "Component": "Component", "Asset": "Asset"}
            ts_element = ts_types.get(native)
            if ts_element is None and native in _CREATOR_REFERENCE_TYPES.values():
                ts_element = native
            if ts_element is None:
                raise StaticCarrierError(f"unsupported Creator array element type {native}")
            prop, ts_type, initial = f"[{native}]", f"{ts_element}[]", "[]"
        else:
            raise StaticCarrierError(f"unsupported Creator storage type {storage}")
        lines.append(f"    @property({prop}) public {field['fieldName']}: {ts_type} = {initial};")
    lines += ["}", ""]
    return "\n".join(lines)


def prepare(components, target, namespace, output):
    """Generate deduplicated target scripts and sourceId-addressed bindings."""
    if target not in _PREFIX:
        raise StaticCarrierError(f"unsupported target {target!r}")
    if not isinstance(namespace, str) or not _NAMESPACE.fullmatch(namespace):
        raise StaticCarrierError("namespace must be a valid dotted identifier")
    if not isinstance(components, list):
        raise StaticCarrierError("components must be an array")
    output = Path(output)
    rows = []
    seen_sources = set()
    diagnostics = []
    for item in components:
        if not isinstance(item, dict):
            raise StaticCarrierError("component row must be an object")
        snapshot = item.get("staticFieldSnapshot", item)
        if not isinstance(snapshot, dict):
            raise StaticCarrierError("staticFieldSnapshot must be an object")
        source_id = item.get("sourceId", snapshot.get("sourceId"))
        source_type = snapshot.get("sourceType")
        node = snapshot.get("node")
        if not isinstance(source_id, str) or not source_id or source_id in seen_sources:
            raise StaticCarrierError(f"invalid or duplicate component sourceId: {source_id!r}")
        if not isinstance(node, str) or not node or not isinstance(source_type, str) or not source_type:
            raise StaticCarrierError(f"component {source_id} has invalid node/sourceType")
        seen_sources.add(source_id)
        source_fields = snapshot.get("fields")
        if not isinstance(source_fields, list):
            raise StaticCarrierError(f"component {source_id} has no serialized fields array")
        fields, generated_gaps = [], []
        names = set()
        for index, source_field in enumerate(source_fields):
            field, gap = _field_plan(source_field, index)
            if field["name"] in names:
                raise StaticCarrierError(f"duplicate field name in {source_id}: {field['name']}")
            names.add(field["name"])
            fields.append(field)
            if gap:
                generated_gaps.append(gap)
        for field in fields:
            if field.get("recordTypeName"):
                record_schema_sha = hashlib.sha256(_json({"sourceType": source_type, "recordSchema": field.get("recordSchema", [])}).encode("utf-8")).hexdigest()[:8]
                record_type = f"StaticRecord_{_slug(source_type)}_{_slug(field.get('recordName', 'Entry'))}_{record_schema_sha}"
                field["recordTypeName"] = record_type
                field["storageType"] = record_type + "[]"
                field["creatorElementType"] = record_type
        gaps = list(snapshot.get("gaps", []))
        if not isinstance(gaps, list) or any(not isinstance(gap, str) for gap in gaps):
            raise StaticCarrierError(f"component {source_id} has malformed gaps")
        gaps.extend(generated_gaps)
        declaration_defaults_verified = (snapshot.get("declarationDefaults") == "verified" and
                                         not any("unverified" in gap for gap in gaps))
        if not declaration_defaults_verified:
            gaps.append("source_declaration_defaults_not_verified")
        gaps = sorted(set(gaps))
        diagnostics.extend({"code": "STATIC_CARRIER_GAP", "sourceId": source_id, "message": gap}
                           for gap in gaps)
        schema = _schema(source_type, fields)
        schema_hash = hashlib.sha256(_json({"sourceType": source_type, "fields": schema}).encode("utf-8")).hexdigest()[:12]
        class_name = f"StaticFields_{_slug(source_type)}_{schema_hash}"
        full_type = namespace + "." + class_name
        extension = ".cs" if target == "unity" else ".ts"
        target_path = _PREFIX[target] + class_name + extension
        identity = _script_identity(target, namespace, target_path)
        spec = {"sourceId": source_id, "node": node, "sourceType": source_type,
                "typeName": full_type, "scriptGuid": identity, "scriptPath": target_path,
                "scriptSha256": None, "fields": fields, "behavior": "disabled", "enabled": False,
                "nativeCreate": "no-callbacks", "fieldsVerified": False, "gaps": gaps,
                "declarationDefaults": "verified" if declaration_defaults_verified else "unverified",
                "declarationDefaultsVerified": declaration_defaults_verified, "dynamicBehaviorComplete": False}
        rows.append((target_path, target_path.rsplit("/", 1)[-1], source_type, class_name, fields, spec))

    by_target = {}
    for target_path, filename, source_type, class_name, fields, spec in rows:
        key = (target_path, _json(_schema(source_type, fields)))
        if key in by_target:
            continue
        code = _unity_script(namespace, class_name, fields) if target == "unity" else _creator_script(namespace, class_name, fields)
        raw = code.encode("utf-8")
        digest = sha(raw)
        spec["scriptSha256"] = digest
        by_target[key] = {"source": "static-field-scripts/" + filename, "target": target_path,
                          "sha256": digest, "identity": spec["scriptGuid"], "_bytes": raw}
    # Set the class digest on every source binding after script de-duplication.
    scripts = []
    target_to_script = {}
    for key, item in by_target.items():
        target_to_script[key[0]] = item
        scripts.append({k: v for k, v in item.items() if k != "_bytes"})
        destination = inside(output, item["source"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = item["_bytes"]
        if destination.exists() and destination.read_bytes() != raw:
            raise StaticCarrierError(f"refusing to overwrite generated script {destination}")
        destination.write_bytes(raw)
    bindings = {}
    for target_path, _filename, _source_type, _class_name, _fields, spec in rows:
        script = target_to_script[target_path]
        spec["scriptSha256"] = script["sha256"]
        bindings[spec["sourceId"]] = spec
    return {"scripts": scripts, "bindings": bindings, "diagnostics": diagnostics}


def _script_identity(target, namespace, path):
    import uuid
    if target == "unity":
        return uuid.uuid5(uuid.NAMESPACE_URL, "monkey/" + namespace + "/prefab-static-field/" + path).hex
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "monkey/" + namespace + "/creator-3.8.8/prefab-static-field/" + path))


def emit(plan, plan_root, target, out):
    """Copy prepared scripts into a candidate and write deterministic metadata."""
    if target not in _PREFIX:
        raise StaticCarrierError(f"unsupported target {target!r}")
    plan_root, out = Path(plan_root), Path(out)
    rows = plan.get("staticFieldScripts", [])
    if not isinstance(rows, list):
        raise StaticCarrierError("plan.staticFieldScripts must be an array")
    emitted = []
    seen_targets = set()
    for item in rows:
        if not isinstance(item, dict) or not item.get("target", "").startswith(_PREFIX[target]):
            raise StaticCarrierError("static field script destination is outside the carrier namespace")
        if item["target"] in seen_targets:
            raise StaticCarrierError("duplicate static field script destination: " + item["target"])
        seen_targets.add(item["target"])
        raw = inside(plan_root, item["source"]).read_bytes()
        if sha(raw) != item.get("sha256"):
            raise StaticCarrierError(f"static field script hash mismatch: {item.get('target')}")
        destination = inside(out, item["target"])
        if destination.exists():
            raise StaticCarrierError(f"refusing to replace target asset: {item['target']}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        metadata = Path(str(destination) + ".meta")
        if metadata.exists():
            destination.unlink()
            raise StaticCarrierError(f"refusing to replace target metadata: {metadata}")
        if target == "unity":
            metadata.write_text("fileFormatVersion: 2\nguid: " + item["identity"] + "\n", encoding="utf-8")
        else:
            write_json(metadata, {"ver": "4.0.24", "uuid": item["identity"], "importer": "typescript",
                                  "imported": False, "files": [], "subMetas": {}, "userData": {}})
        emitted.append(item["target"])
    return emitted
