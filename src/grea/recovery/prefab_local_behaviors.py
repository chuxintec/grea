"""Source-bound lowering for a deliberately small set of local UI behaviours.

The rules are tied to frozen module bytes and semantic markers. A matching
component name or serialized type id alone never enables generated behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Any


RULE_VERSION = "monkey-prefab-local-behaviors/1"
SOURCES = {
    "BaseEffect": {
        "source_type": "83480cm2GpLdL42N1n2aVd0",
        "sha256": "bc53e83d3df6a7b55c46fdbcda52350df3d71aa7ccaa42baa3f1b0144001ed3d",
        "markers": (b"t.delay=0,t.tweenTime=.3", b"i.prototype.show=", b"i.prototype.reset=", b"this.node.stopAllActions()"),
    },
    "ScaleBackEffect": {
        "source_type": "d08bdTxpX1NbJhf6/sTgRao",
        "sha256": "ab661a87764aba785f3039b2767301d8b854031b1b57f813a559bf5a09e6c924",
        "markers": (b"i.prototype.show=", b"e.prototype.show.call(this,t)", b"this.tweenHide?", b"kt(1e3*this.tweenTime)", b"}(Se)"),
    },
    "BreathEffect": {
        "source_type": "5f4dd/aSmJBa6/sLQlXJEBS",
        "sha256": "a44e4524015e193da241958bfe2b47901a6232ac89e0e063b59a9a362da94617",
        "markers": (b"t.delay=.3", b"t.tweenTime=.7", b"t.offset=.1", b"this.startValue=this.node.scale", b"this.node.stopAllActions()", b"easing:\"quadInOut\"", b"this.playEffect.bind(this)"),
    },
    "AutoScaleComp": {
        "source_type": "86fdf0LcnRPjKXp4EJh0Q2V",
        "sha256": "31bc40b8ef0497c3f7c172bb3b054be5e280b8581a627fc2a0a66fbb1d8b9067",
        "markers": (b"this.initialY=this.node.y", b"S.statusNotchHeight", b"cc.view.getVisibleSize()", b"this.node.setScale(l)"),
    },
}
SUPPORTED_FIELDS = {
    "BreathEffect": {"delay": ("float", 0.3), "tweenTime": ("float", 0.7), "offset": ("float", 0.1)},
    "ScaleBackEffect": {"delay": ("float", 0.0), "tweenTime": ("float", 0.3), "tweenHide": ("bool", False), "scaleFrom": ("float", 0.7)},
    "AutoScaleComp": {},
}
UNSUPPORTED: dict[str, str] = {}
_PARTIAL_BEHAVIORS = {
    "BreathEffect": ("source stopAllActions cancels every action on the node; native adapters cancel only their own tween",),
    "ScaleBackEffect": (
        "BaseEffect.reset stops every source node action; native adapter stops only owned recovered tweens",
    ),
}
_SCALE_BACK_SCOPE_PROOF = {
    "sourceBundleSha256": "21af08e48846f6ad1a2e0673b0c945358136723b1664f0cd1f6ec9b3df6c5cb5",
    "parser": "acorn-8.15.0",
    "astScope": {"id": "function-expression:1304-7060866", "utf16Range": [1304, 7060866]},
    "bindings": {"BaseEffect.Se": "function-expression:1304-7060866", "ScaleBackEffect.Se": "function-expression:1304-7060866", "kt": "function-expression:1304-7060866"},
    "byteRanges": {"BaseEffect": [72326, 73504], "ScaleBackEffect": [3564927, 3566140], "kt": [110906, 111081]},
    "moduleSha256": {"BaseEffect": "bc53e83d3df6a7b55c46fdbcda52350df3d71aa7ccaa42baa3f1b0144001ed3d", "ScaleBackEffect": "ab661a87764aba785f3039b2767301d8b854031b1b57f813a559bf5a09e6c924", "kt": "4ddc9e7e4b7ad6332ac71b96354d72a0d8f0fece64020d7684cc5301b4e73ed3"},
    "ktSemantics": "returns a Promise resolved by setTimeout(resolve, milliseconds)",
    "aliasResolution": "BaseEffect declares Se; ScaleBackEffect passes the same-scope Se to its class factory; other Se declarations are in non-enclosing function scopes",
}
_TEMPLATE_DIR = Path(__file__).with_name("targets") / "behaviors"


@dataclass(frozen=True)
class Lowering:
    status: str
    component: str
    target: str
    source_sha256: str | None
    rule_version: str
    applied_fields: tuple[str, ...]
    unsupported_behaviors: tuple[str, ...]
    script_path: str | None = None
    script: str | None = None
    reason: str | None = None
    field_values: dict[str, Any] | None = None
    source_evidence: dict[str, Any] | None = None
    required_providers: tuple[str, ...] = ()

    def plan(self) -> dict[str, Any]:
        script_filename = self.script_path.rsplit("/", 1)[-1] if self.script_path else None
        if self.component == "BreathEffect":
            native_type = "Monkey.Recovered.Behaviors.BreathEffect" if self.target.lower() == "unity" else "MonkeyRecoveredBreathEffect"
        elif self.component == "ScaleBackEffect":
            native_type = "Monkey.Recovered.Behaviors.ScaleBackEffect" if self.target.lower() == "unity" else "MonkeyRecoveredScaleBackEffect"
        elif self.component == "AutoScaleComp":
            native_type = "Monkey.Recovered.Behaviors.AutoScaleComp" if self.target.lower() == "unity" else "MonkeyRecoveredAutoScaleComp"
        else:
            native_type = None
        return {
            "status": self.status,
            "component": self.component,
            "target": self.target,
            "originalSourceSha256": self.source_sha256,
            "scriptPath": self.script_path,
            "scriptFilename": script_filename,
            "className": self.component if script_filename else None,
            "nativeType": native_type if script_filename else None,
            "appliedFields": list(self.applied_fields),
            "serializedValues": self.field_values or {},
            "requiredProviders": list(self.required_providers),
            "unsupportedBehaviors": list(self.unsupported_behaviors),
            "reason": self.reason,
            "sourceEvidence": self.source_evidence or {},
        }

    def record(self) -> dict[str, Any]:
        return {"schema": "monkey-prefab-behavior-lowering/1", "ruleVersion": self.rule_version, **self.plan()}


def _reject(component: str, target: str, digest: str | None, reason: str) -> Lowering:
    return Lowering("unsupported", component, target, digest, RULE_VERSION, (), (reason,), reason=reason)


def lower_behavior(
    component: str,
    source_type: str,
    source_bytes: bytes,
    target: str,
    serialized_fields: dict[str, Any] | None = None,
    *,
    base_source_bytes: bytes | None = None,
    source_bundle_bytes: bytes | None = None,
    scope_proof: dict[str, Any] | None = None,
    native_context: dict[str, Any] | None = None,
) -> Lowering:
    """Lower only exact frozen source modules with their proven local semantics.

    `serialized_fields` uses Creator serialized property names. Unknown fields,
    malformed values, source variants, and mismatched identities fail closed.
    """
    target_key = target.lower()
    if target_key not in {"unity", "creator", "creator3.8", "creator-3.8"}:
        return _reject(component, target, hashlib.sha256(source_bytes).hexdigest(), "unsupported target")
    spec = SOURCES.get(component)
    digest = hashlib.sha256(source_bytes).hexdigest()
    if spec is None:
        return _reject(component, target, digest, "no source-bound rule")
    if source_type != spec["source_type"]:
        return _reject(component, target, digest, "source component type identity mismatch")
    if digest != spec["sha256"]:
        return _reject(component, target, digest, "frozen source module hash mismatch")
    if not all(marker in source_bytes for marker in spec["markers"]):
        return _reject(component, target, digest, "source semantic fingerprint mismatch")
    source_evidence: dict[str, Any] = {}
    if component == "ScaleBackEffect":
        base_spec = SOURCES["BaseEffect"]
        if base_source_bytes is None or hashlib.sha256(base_source_bytes).hexdigest() != base_spec["sha256"]:
            return _reject(component, target, digest, "BaseEffect frozen source module is missing or mismatched")
        if not all(marker in base_source_bytes for marker in base_spec["markers"]):
            return _reject(component, target, digest, "BaseEffect semantic fingerprint mismatch")
        if source_bundle_bytes is None:
            reason = ("caller-supplied scope proof is not source verification" if scope_proof is not None
                      else "complete frozen source bundle bytes are required for BaseEffect/kt scope verification")
            return _reject(component, target, digest, reason)
        if hashlib.sha256(source_bundle_bytes).hexdigest() != _SCALE_BACK_SCOPE_PROOF["sourceBundleSha256"]:
            return _reject(component, target, digest, "source bundle hash does not match the frozen AST scope proof")
        proof = _SCALE_BACK_SCOPE_PROOF
        for module, candidate in (("BaseEffect", base_source_bytes), ("ScaleBackEffect", source_bytes)):
            start, end = proof["byteRanges"][module]
            if source_bundle_bytes[start:end] != candidate or hashlib.sha256(candidate).hexdigest() != proof["moduleSha256"][module]:
                return _reject(component, target, digest, f"{module} byte range/hash disagrees with the source bundle proof")
        start, end = proof["byteRanges"]["kt"]
        if hashlib.sha256(source_bundle_bytes[start:end]).hexdigest() != proof["moduleSha256"]["kt"]:
            return _reject(component, target, digest, "kt byte range/hash disagrees with the source bundle proof")
        source_evidence = {
            "baseSourceType": base_spec["source_type"],
            "baseSourceSha256": base_spec["sha256"],
            "scopeProof": dict(proof, verification="whole_bundle_bytes_and_ranges_verified"),
            "inheritedFields": ["delay", "tweenTime"],
            "showOrder": ["await BaseEffect.show/reset", "set scaleFrom", "start backOut tween", "await kt(1000*tweenTime)"],
            "hideOrder": ["if tweenHide start backIn tween and await kt(1000*tweenTime)", "set scale zero"],
        }
        context = native_context or {}
        component_types = context.get("sameNodeComponentTypes")
        if not isinstance(component_types, list):
            return _reject(component, target, digest, "same-node component inventory is required for inherited BaseEffect behavior")
        has_widget = "cc.Widget" in component_types or "Widget" in component_types
        if has_widget and target_key == "unity" and context.get("widgetAlignmentProvider") != "monkey.widget-alignment/1":
            return _reject(component, target, digest, "BaseEffect Widget.updateAlignment requires a bound native widget-alignment provider")
        source_evidence["sameNodeComponentTypes"] = list(component_types)
        source_evidence["baseEffectWidget"] = "updateAlignment called" if has_widget else "absent on source node"
        if has_widget and target_key == "unity":
            source_evidence["widgetAlignmentProvider"] = context["widgetAlignmentProvider"]
    elif component == "AutoScaleComp":
        context = native_context or {}
        component_types = context.get("sameNodeComponentTypes")
        if context.get("viewportProvider") != "monkey.viewport-notch/1":
            return _reject(component, target, digest, "explicit viewport/notch provider binding is required")
        if not isinstance(component_types, list):
            return _reject(component, target, digest, "same-node component inventory is required")
        if "cc.Widget" in component_types or "Widget" in component_types:
            return _reject(component, target, digest, "blocked: source cc.Widget shares the node and conflicts with AutoScaleComp layout writes")
        source_evidence = {
            "viewportProviderContract": context["viewportProvider"],
            "viewportMetrics": ["visibleSize.width", "visibleSize.height", "statusNotchHeight"],
            "sameNodeComponentTypes": list(component_types),
            "widgetConflict": "checked and absent",
        }
    if component in UNSUPPORTED:
        return _reject(component, target, digest, UNSUPPORTED[component])

    fields = serialized_fields or {}
    allowed = SUPPORTED_FIELDS[component]
    unknown = sorted(set(fields) - set(allowed))
    if unknown:
        return _reject(component, target, digest, "unsupported serialized fields: " + ", ".join(unknown))
    for name, value in fields.items():
        expected_type, _default = allowed[name]
        if expected_type == "bool" and not isinstance(value, bool):
            return _reject(component, target, digest, f"invalid serialized field {name}")
        if expected_type == "float" and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
            return _reject(component, target, digest, f"invalid serialized field {name}")
    if target_key == "unity":
        filename = component + ".cs"
        path = "Assets/Monkey/Behaviors/" + filename
    else:
        filename = component + ".ts"
        path = "assets/scripts/monkey/behaviors/" + filename
    template = (_TEMPLATE_DIR / filename).read_text(encoding="utf-8")
    values = {name: fields.get(name, allowed[name][1]) for name in allowed}
    gaps = _PARTIAL_BEHAVIORS.get(component, ())
    required_providers: list[str] = []
    if component == "AutoScaleComp":
        required_providers.append("monkey.viewport-notch/1")
    if component == "ScaleBackEffect" and source_evidence.get("baseEffectWidget") == "updateAlignment called" and target_key == "unity":
        required_providers.append("monkey.widget-alignment/1")
    return Lowering("lowered_with_gaps" if gaps else "lowered", component, target, digest, RULE_VERSION,
                    tuple(sorted(allowed)), gaps, path, template, field_values=values,
                    source_evidence=source_evidence, required_providers=tuple(required_providers))


def lower_component(component_ir: dict[str, Any], source_type: str, source_bytes: bytes,
                    target: str, serialized_fields: dict[str, Any] | None = None, **evidence: Any) -> Lowering:
    """Convenience adapter for normalized component IR records."""
    return lower_behavior(str(component_ir.get("type", "")), source_type, source_bytes,
                          target, serialized_fields, **evidence)


def quad_in_out(progress: float) -> float:
    """Cocos quadInOut scalar used by BreathEffect's native timing contract."""
    t = min(1.0, max(0.0, progress))
    return 2.0 * t * t if t < 0.5 else 1.0 - ((-2.0 * t + 2.0) ** 2) * 0.5


def back_ease(progress: float, outgoing: bool) -> float:
    t = min(1.0, max(0.0, progress))
    c1 = 1.70158
    return (1.0 + (c1 + 1.0) * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2
            if outgoing else (c1 + 1.0) * t ** 3 - c1 * t ** 2)


def source_scale_x(scale_xyz: tuple[float, float, float]) -> float:
    """Cocos 2.4 Node.scale reads the scalar X slot."""
    return scale_xyz[0]


def uniform_scale_xyz(value: float) -> tuple[float, float, float]:
    """Cocos 2.4 setScale(number) writes one scalar uniformly to XYZ."""
    return (value, value, value)


def sample_breath_cycle(start: float, offset: float, tween_time: float,
                        delay: float, elapsed: float) -> float:
    """Sample the source loop's scale value; zero durations complete immediately."""
    if tween_time <= 0:
        return start
    cycle = 2.0 * tween_time + max(0.0, delay)
    t = elapsed % cycle if cycle > 0 else 0.0
    if t < tween_time:
        return start + offset * quad_in_out(t / tween_time)
    if t < 2.0 * tween_time:
        return start + offset * (1.0 - quad_in_out((t - tween_time) / tween_time))
    return start


def sample_back_scale(start_xyz: tuple[float, float, float], target: float,
                      progress: float, outgoing: bool) -> tuple[float, float, float]:
    start = source_scale_x(start_xyz)
    eased = back_ease(progress, outgoing)
    return uniform_scale_xyz(start + (target - start) * eased)
