"""Static inherited-field profile for Unity uGUI InputField/Selectable.

The profile supplies type-tree-backed inherited field mappings to the existing
Unity Prefab declaration planner. It does not recover or invoke source methods.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


PROFILE_ID = "unity-ugui-inputfield-selectable-static-profile/1"

INPUTFIELD = "UnityEngine.UI.InputField"
SELECTABLE = "UnityEngine.UI.Selectable"
UI_BEHAVIOUR = "UnityEngine.EventSystems.UIBehaviour"
MONOBEHAVIOUR = "UnityEngine.MonoBehaviour"

# Values fit the maps consumed by unity_prefab_types.py. InputField receives
# the complete inherited tree because its serialized object includes both its
# own fields and the fields declared by Selectable.
NATIVE_BASES = {
    SELECTABLE: SELECTABLE,
    INPUTFIELD: INPUTFIELD,
    UI_BEHAVIOUR: UI_BEHAVIOUR,
}

BASE_INHERITANCE = {
    SELECTABLE: [SELECTABLE, UI_BEHAVIOUR, MONOBEHAVIOUR],
    INPUTFIELD: [INPUTFIELD, SELECTABLE, UI_BEHAVIOUR, MONOBEHAVIOUR],
    UI_BEHAVIOUR: [UI_BEHAVIOUR, MONOBEHAVIOUR],
}

BASE_PARENTS = {
    SELECTABLE: UI_BEHAVIOUR,
    INPUTFIELD: SELECTABLE,
    UI_BEHAVIOUR: MONOBEHAVIOUR,
}

# Each row is (source TypeTree type, exact target C# field type). Field owners
# are retained separately so source/target declaration checks can detect drift.
_SELECTABLE_FIELDS = {
    "m_Navigation": ("Navigation", "UnityEngine.UI.Navigation"),
    "m_Transition": ("int", "UnityEngine.UI.Selectable.Transition"),
    "m_Colors": ("ColorBlock", "UnityEngine.UI.ColorBlock"),
    "m_SpriteState": ("SpriteState", "UnityEngine.UI.SpriteState"),
    "m_AnimationTriggers": ("AnimationTriggers", "UnityEngine.UI.AnimationTriggers"),
    "m_Interactable": ("UInt8", "bool"),
    "m_TargetGraphic": ("PPtr<$Graphic>", "UnityEngine.UI.Graphic"),
}

_INPUTFIELD_FIELDS = {
    "m_TextComponent": ("PPtr<$Text>", "UnityEngine.UI.Text"),
    "m_Placeholder": ("PPtr<$Graphic>", "UnityEngine.UI.Graphic"),
    "m_ContentType": ("int", "UnityEngine.UI.InputField.ContentType"),
    "m_InputType": ("int", "UnityEngine.UI.InputField.InputType"),
    "m_AsteriskChar": ("UInt16", "char"),
    "m_KeyboardType": ("int", "UnityEngine.TouchScreenKeyboardType"),
    "m_LineType": ("int", "UnityEngine.UI.InputField.LineType"),
    "m_HideMobileInput": ("UInt8", "bool"),
    "m_CharacterValidation": ("int", "UnityEngine.UI.InputField.CharacterValidation"),
    "m_CharacterLimit": ("int", "int"),
    "m_OnSubmit": ("SubmitEvent", "UnityEngine.UI.InputField.SubmitEvent"),
    "m_OnDidEndEdit": ("EndEditEvent", "UnityEngine.UI.InputField.EndEditEvent"),
    "m_OnValueChanged": ("OnChangeEvent", "UnityEngine.UI.InputField.OnChangeEvent"),
    "m_CaretColor": ("ColorRGBA", "UnityEngine.Color"),
    "m_CustomCaretColor": ("UInt8", "bool"),
    "m_SelectionColor": ("ColorRGBA", "UnityEngine.Color"),
    "m_Text": ("string", "string"),
    "m_CaretBlinkRate": ("float", "float"),
    "m_CaretWidth": ("int", "int"),
    "m_ReadOnly": ("UInt8", "bool"),
    "m_ShouldActivateOnSelect": ("UInt8", "bool"),
}

UI_INHERITED_FIELDS = {
    SELECTABLE: dict(_SELECTABLE_FIELDS),
    INPUTFIELD: {**_SELECTABLE_FIELDS, **_INPUTFIELD_FIELDS},
}

FIELD_OWNERS = {
    SELECTABLE: {name: SELECTABLE for name in _SELECTABLE_FIELDS},
    INPUTFIELD: {
        **{name: SELECTABLE for name in _SELECTABLE_FIELDS},
        **{name: INPUTFIELD for name in _INPUTFIELD_FIELDS},
    },
}

NATIVE_COMPONENT_CHAINS = BASE_INHERITANCE


class InputFieldProfileError(ValueError):
    """The supplied base declaration or TypeTree does not match the profile."""


def merge_inputfield_native_profile(
    native_bases: Mapping[str, str],
    base_inheritance: Mapping[str, list[str]],
    ui_inherited_fields: Mapping[str, Mapping[str, tuple[str, str]]],
) -> dict[str, dict[str, Any]]:
    """Return copied type maps with this profile overlaid; conflicting entries fail."""
    if not all(isinstance(value, Mapping) for value in (native_bases, base_inheritance, ui_inherited_fields)):
        raise InputFieldProfileError("All destination type maps must be mappings")
    bases = dict(native_bases)
    chains = {key: list(value) for key, value in base_inheritance.items()}
    inherited = {key: dict(value) for key, value in ui_inherited_fields.items()}
    for key, value in NATIVE_BASES.items():
        if key in bases and bases[key] != value:
            raise InputFieldProfileError("Conflicting native base identity: " + key)
        bases[key] = value
    for key, value in BASE_INHERITANCE.items():
        if key in chains and chains[key] != value:
            raise InputFieldProfileError("Conflicting native base chain: " + key)
        chains[key] = list(value)
    for base, field_rows in UI_INHERITED_FIELDS.items():
        target = inherited.setdefault(base, {})
        for field_name, field_type in field_rows.items():
            if field_name in target and target[field_name] != field_type:
                raise InputFieldProfileError("Conflicting inherited field profile: " + base + "." + field_name)
            target[field_name] = field_type
    return {"nativeBases": bases, "baseInheritance": chains,
            "nativeComponentChains": chains, "uiInheritedFields": inherited}


def validate_inputfield_type_tree(typed_schema: Mapping[str, Any],
                                  declared_source_fields: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Require the complete inherited TypeTree field set and source-declared extras."""
    if not isinstance(typed_schema, Mapping) or not isinstance(typed_schema.get("children"), list):
        raise InputFieldProfileError("Typed schema has no direct child list")
    children = typed_schema["children"]
    observed: dict[str, str] = {}
    for child in children:
        if not isinstance(child, Mapping) or not isinstance(child.get("name"), str) or not isinstance(child.get("type"), str):
            raise InputFieldProfileError("Malformed direct TypeTree child")
        name = child["name"]
        if name in observed:
            raise InputFieldProfileError("Duplicate direct TypeTree field: " + name)
        observed[name] = child["type"]
    core = {"m_GameObject", "m_Enabled", "m_Script", "m_Name"}
    missing_core = sorted(core - set(observed))
    if missing_core:
        raise InputFieldProfileError("InputField TypeTree is missing Unity core fields: " + repr(missing_core))
    non_core = {name: value for name, value in observed.items() if name not in core}
    expected = {name: value[0] for name, value in UI_INHERITED_FIELDS[INPUTFIELD].items()}
    source_extra_fields = {}
    if declared_source_fields is not None:
        for field in declared_source_fields:
            if not isinstance(field, Mapping) or not isinstance(field.get("name"), str):
                raise InputFieldProfileError("Malformed parsed source field declaration")
            if field.get("unitySerializedCandidate"):
                name = field["name"]
                if name in expected:
                    raise InputFieldProfileError("Source class redeclares a native inherited field: " + name)
                source_extra_fields[name] = field.get("type")
    expected_names = set(expected) | set(source_extra_fields)
    changed = sorted(name for name in set(expected) & set(non_core) if expected[name] != non_core[name])
    if set(non_core) != expected_names or changed:
        missing = sorted(set(expected) - set(non_core))
        extra = sorted(set(non_core) - set(expected_names))
        undeclared = sorted(set(source_extra_fields) - set(non_core))
        raise InputFieldProfileError(
            "InputField TypeTree differs from profile schema; missing=" + repr(missing) +
            "; extra=" + repr(extra) + "; undeclaredSourceFields=" + repr(undeclared) +
            "; changed=" + repr(changed)
        )
    return {
        "status": "matched",
        "directChildCount": len(children),
        "coreFieldCount": len(children) - len(non_core),
        "serializedFieldCount": len(non_core),
        "additionalSourceFields": [
            {"name": name, "declarationType": declared_type, "typeTreeType": non_core[name]}
            for name, declared_type in sorted(source_extra_fields.items())
        ],
        "fields": [
            {"name": name, "typeTreeType": type_tree_type,
             "csType": UI_INHERITED_FIELDS[INPUTFIELD][name][1] if name in expected else source_extra_fields[name],
             "owner": FIELD_OWNERS[INPUTFIELD][name] if name in expected else "source-derived-type-requires-existing-planner"}
            for name, type_tree_type in sorted(non_core.items())
        ],
    }


def match_inputfield_derived_type(parsed: Mapping[str, Any], identity: Mapping[str, str],
                                  typed_schema: Mapping[str, Any]) -> dict[str, Any]:
    """Match one exact parsed source class directly deriving from native InputField.

    The existing declaration planner remains responsible for custom fields,
    arrays and enum values. This profile verifies the native inherited portion.
    """
    wanted = (identity.get("assembly"), identity.get("namespace", ""), identity.get("name"))
    declarations = parsed.get("declarations") if isinstance(parsed, Mapping) else None
    if not isinstance(declarations, list):
        return {"status": "gap", "reason": "source declarations are missing"}
    matches = [row for row in declarations if isinstance(row, Mapping) and isinstance(row.get("identity"), Mapping) and
               (row["identity"].get("assembly"), row["identity"].get("namespace", ""), row["identity"].get("name")) == wanted]
    if len(matches) != 1:
        return {"status": "gap", "reason": "exact source assembly/namespace/type declaration is missing or duplicated"}
    declaration = matches[0]
    if declaration.get("kind") != "class":
        return {"status": "gap", "identity": dict(assembly=wanted[0], namespace=wanted[1], name=wanted[2]),
                "reason": "source type is not a class"}
    if not _resolves_to_inputfield(declaration, declarations):
        return {"status": "gap", "identity": dict(assembly=wanted[0], namespace=wanted[1], name=wanted[2]),
                "reason": "source class does not unambiguously derive from UnityEngine.UI.InputField"}
    try:
        tree = validate_inputfield_type_tree(typed_schema, declaration.get("fields", []))
    except InputFieldProfileError as error:
        return {"status": "gap", "identity": dict(assembly=wanted[0], namespace=wanted[1], name=wanted[2]),
                "reason": str(error)}
    return {
        "status": "disabled_schema_carrier",
        "identity": dict(assembly=wanted[0], namespace=wanted[1], name=wanted[2]),
        "declaredSourceBase": declaration.get("base"),
        "nativeSourceBase": INPUTFIELD,
        "candidateTargetBase": INPUTFIELD,
        "sourceBaseChain": list(BASE_INHERITANCE[INPUTFIELD]),
        "nativeInheritedTypeTree": tree,
        "sourceDeclaredFields": list(declaration.get("fields", [])),
        "sourceMethods": "not_recovered_from-static-declarations",
        "componentEnabled": False,
        "behaviorDisposition": "disabled-required; do not emit empty source overrides",
        "targetBaseType": INPUTFIELD,
        "targetSdkIdentity": "caller-supplied pinned SDK declaration; not inferred by this profile",
        "schemaProposalMustUseExistingPlanner": True,
    }


def _resolves_to_inputfield(declaration: Mapping[str, Any], declarations: list[Any]) -> bool:
    raw = declaration.get("base")
    if raw == INPUTFIELD:
        return True
    if raw != "InputField":
        return False
    namespace = declaration.get("identity", {}).get("namespace", "")
    imports = declaration.get("imports", [])
    candidates = []
    local_full = (namespace + "." if namespace else "") + "InputField"
    if any(isinstance(row, Mapping) and isinstance(row.get("identity"), Mapping) and
           row["identity"].get("assembly") == declaration.get("identity", {}).get("assembly") and
           row["identity"].get("namespace", "") + "." + row["identity"].get("name", "").split("+")[-1] == local_full
           for row in declarations):
        candidates.append("custom:" + local_full)
    if INPUTFIELD.rsplit(".", 1)[0] in imports:
        candidates.append("native:" + INPUTFIELD)
    return candidates == ["native:" + INPUTFIELD]
