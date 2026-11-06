import hashlib
import json

import pytest

from monkey.unity_prefab_sdk import SDKBindingError, plan_sdk_script_bindings


def _pin(root, files):
    pins = {}
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode() if isinstance(content, str) else content)
        pins[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pins


def _sdk(tmp_path, source="namespace UnityEngine.UI { public class NeutralRenamed {} }"):
    files = {
        "Runtime/UnityEngine.UI.asmdef": json.dumps({"name": "UnityEngine.UI"}),
        "Runtime/NeutralRenamed.cs": source,
        "Runtime/NeutralRenamed.cs.meta": "fileFormatVersion: 2\nguid: 0123456789abcdef0123456789abcdef\n",
    }
    return _pin(tmp_path, files)


def _script(class_name="NeutralRenamed", *, assembly="UnityEngine.UI.dll", guid="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", file_id=11500000):
    return {
        "identity": {"assembly": assembly, "namespace": "UnityEngine.UI", "class": class_name},
        "sourceTuple": {"guid": guid, "fileID": file_id, "type": 3},
    }


def test_maps_exact_type_using_declaration_not_filename_and_preserves_source_tuple(tmp_path):
    pins = _sdk(tmp_path, "namespace UnityEngine.UI { public class NeutralRenamed {} }")
    original = _script("NeutralRenamed")
    result = plan_sdk_script_bindings([original], sdk_root=tmp_path, pinned_files=pins)
    binding = result["bindings"][0]
    assert binding["status"] == "planned_sdk_binding"
    assert binding["sourceTuple"] == original["sourceTuple"]
    assert binding["expectedTuple"] == {
        "guid": "0123456789abcdef0123456789abcdef", "fileID": 11500000, "type": 3,
    }
    assert result["nativeGetClassVerified"] is False
    assert "NeutralRenamed.cs" in binding["targetSource"]["path"]


def test_monoscript_identity_does_not_require_unrelated_nested_generic_event_schema(tmp_path):
    pins = _sdk(tmp_path, "namespace UnityEngine.UI { public class NeutralRenamed { public class Event : UnityEvent<int> {} } }")
    result = plan_sdk_script_bindings([_script()], sdk_root=tmp_path, pinned_files=pins)
    assert result['declarationCount'] == 1
    assert result['bindings'][0]['targetSource']['path'] == 'Runtime/NeutralRenamed.cs'


def test_target_tuple_uses_cs_monoscript_convention_not_source_dll_local_id(tmp_path):
    pins = _sdk(tmp_path)
    original = _script(file_id=987654321)
    original["sourceTuple"]["type"] = 2
    preserved = dict(original["sourceTuple"])
    binding = plan_sdk_script_bindings([original], sdk_root=tmp_path, pinned_files=pins)["bindings"][0]
    assert binding["sourceTuple"] == preserved
    assert binding["expectedTuple"] == {
        "guid": "0123456789abcdef0123456789abcdef", "fileID": 11500000, "type": 3,
    }
    assert binding["expectedTuple"] != binding["sourceTuple"]


def test_exact_native_type_is_recorded_separately_without_sdk_guid(tmp_path):
    pins = _sdk(tmp_path, "namespace UnityEngine { public class Canvas {} }")
    script = _script("Canvas", assembly="UnityEngine.CoreModule.dll")
    result = plan_sdk_script_bindings(
        [script], sdk_root=tmp_path, pinned_files=pins,
        native_types=[script["identity"]],
    )
    assert result["bindings"][0]["status"] == "native_exact"
    assert result["bindings"][0]["expectedTuple"] is None
    assert result["bindings"][0]["sourceTuple"] == script["sourceTuple"]


def test_refuses_changed_pin_and_missing_target_type(tmp_path):
    pins = _sdk(tmp_path)
    (tmp_path / "Runtime/NeutralRenamed.cs").write_text("namespace UnityEngine.UI { public class Sprite {} }")
    with pytest.raises(SDKBindingError, match="pinned file changed"):
        plan_sdk_script_bindings([_script()], sdk_root=tmp_path, pinned_files=pins)

    pins = _sdk(tmp_path)
    with pytest.raises(SDKBindingError, match="no declaration"):
        plan_sdk_script_bindings([_script("Sprite")], sdk_root=tmp_path, pinned_files=pins)


def test_rejects_wrong_assembly_and_duplicate_target_declarations(tmp_path):
    pins = _sdk(tmp_path)
    with pytest.raises(SDKBindingError, match="different assembly"):
        plan_sdk_script_bindings([_script(assembly="Wrong.UI.dll")], sdk_root=tmp_path, pinned_files=pins)

    files = {
        "Runtime/UnityEngine.UI.asmdef": json.dumps({"name": "UnityEngine.UI"}),
        "Runtime/Image.cs": "namespace UnityEngine.UI { public partial class Image {} public partial class Image {} }",
        "Runtime/Image.cs.meta": "guid: 11111111111111111111111111111111\n",
    }
    pins = _pin(tmp_path, files)
    with pytest.raises(SDKBindingError, match="duplicate target"):
        plan_sdk_script_bindings([_script("Image")], sdk_root=tmp_path, pinned_files=pins)


def test_rejects_duplicate_target_guid_and_does_not_treat_secondary_type_as_monoscript(tmp_path):
    files = {
        "Runtime/UnityEngine.UI.asmdef": json.dumps({"name": "UnityEngine.UI"}),
        "Runtime/Image.cs": "namespace UnityEngine.UI { public class Image {} public class SpriteAlias {} }",
        "Runtime/Image.cs.meta": "guid: 11111111111111111111111111111111\n",
        "Runtime/Other.cs": "namespace UnityEngine.UI { public class Other {} }",
        "Runtime/Other.cs.meta": "guid: 11111111111111111111111111111111\n",
    }
    pins = _pin(tmp_path, files)
    with pytest.raises(SDKBindingError, match="duplicate target MonoScript GUID"):
        plan_sdk_script_bindings([_script()], sdk_root=tmp_path, pinned_files=pins)

    files["Runtime/Other.cs.meta"] = "guid: 22222222222222222222222222222222\n"
    pins = _pin(tmp_path, files)
    with pytest.raises(SDKBindingError, match="no declaration"):
        plan_sdk_script_bindings([_script("SpriteAlias")], sdk_root=tmp_path, pinned_files=pins)


def test_rejects_duplicate_source_tuple_and_unpinned_meta(tmp_path):
    pins = _sdk(tmp_path)
    with pytest.raises(SDKBindingError, match="duplicate source"):
        plan_sdk_script_bindings([_script(), _script()], sdk_root=tmp_path, pinned_files=pins)
    pins.pop("Runtime/NeutralRenamed.cs.meta")
    with pytest.raises(SDKBindingError, match="matching pinned .meta"):
        plan_sdk_script_bindings([_script()], sdk_root=tmp_path, pinned_files=pins)


def test_nearest_actual_asmdef_must_be_pinned_and_asmref_is_rejected(tmp_path):
    files = {
        "Runtime/UnityEngine.UI.asmdef": json.dumps({"name": "UnityEngine.UI"}),
        "Runtime/UI/NeutralRenamed.cs": "namespace UnityEngine.UI { public class NeutralRenamed {} }",
        "Runtime/UI/NeutralRenamed.cs.meta": "guid: 0123456789abcdef0123456789abcdef\n",
        "Runtime/UI/Local.asmdef": json.dumps({"name": "Local.UI"}),
    }
    pins = _pin(tmp_path, files)
    pins.pop("Runtime/UI/Local.asmdef")
    with pytest.raises(SDKBindingError, match="nearest asmdef is not pinned"):
        plan_sdk_script_bindings([_script()], sdk_root=tmp_path, pinned_files=pins)

    (tmp_path / "Runtime/UI/Local.asmdef").unlink()
    (tmp_path / "Runtime/UI/Scope.asmref").write_text('{"reference":"GUID:abc"}')
    pins = _pin(tmp_path, {k: v for k, v in files.items() if not k.endswith("Local.asmdef")})
    with pytest.raises(SDKBindingError, match="asmref assembly scope is unsupported"):
        plan_sdk_script_bindings([_script()], sdk_root=tmp_path, pinned_files=pins)


def test_rejects_multiple_nearest_asmdefs_and_never_looks_above_sdk_root(tmp_path):
    files = {
        "Runtime/UnityEngine.UI.asmdef": json.dumps({"name": "UnityEngine.UI"}),
        "Runtime/Other.asmdef": json.dumps({"name": "Other"}),
        "Runtime/NeutralRenamed.cs": "namespace UnityEngine.UI { public class NeutralRenamed {} }",
        "Runtime/NeutralRenamed.cs.meta": "guid: 0123456789abcdef0123456789abcdef\n",
    }
    pins = _pin(tmp_path, files)
    with pytest.raises(SDKBindingError, match="multiple asmdefs"):
        plan_sdk_script_bindings([_script()], sdk_root=tmp_path, pinned_files=pins)

    nested = tmp_path / "isolated-sdk"
    nested.mkdir()
    (tmp_path / "UnityEngine.UI.asmdef").write_text(json.dumps({"name": "UnityEngine.UI"}))
    pins = _pin(nested, {
        "Runtime/NeutralRenamed.cs": "namespace UnityEngine.UI { public class NeutralRenamed {} }",
        "Runtime/NeutralRenamed.cs.meta": "guid: 0123456789abcdef0123456789abcdef\n",
    })
    with pytest.raises(SDKBindingError, match="no actual parent asmdef"):
        plan_sdk_script_bindings([_script()], sdk_root=nested, pinned_files=pins)


def test_pinned_file_count_and_byte_budgets_are_enforced(tmp_path):
    too_many = {f"missing-{index}.txt": "0" * 64 for index in range(257)}
    with pytest.raises(SDKBindingError, match="file count exceeds budget"):
        plan_sdk_script_bindings([], sdk_root=tmp_path, pinned_files=too_many)

    large = b"x" * (4 * 1024 * 1024 + 1)
    (tmp_path / "large.bin").write_bytes(large)
    pins = {"large.bin": hashlib.sha256(large).hexdigest()}
    with pytest.raises(SDKBindingError, match="exceeds byte budget"):
        plan_sdk_script_bindings([], sdk_root=tmp_path, pinned_files=pins)
