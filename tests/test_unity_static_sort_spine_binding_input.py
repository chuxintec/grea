import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from monkey.targets.unity import _static_sort_spine_bindings


def test_binding_map_requires_exact_frozen_file_pin():
    with TemporaryDirectory() as folder:
        root = Path(folder)
        payload = {"schemaVersion": 1, "components": [{"sourceId": "skeleton-owner"}]}
        raw = json.dumps(payload).encode()
        path = root / "Assets" / "bindings.json"
        path.parent.mkdir()
        path.write_bytes(raw)
        stage = {"nativeBindingPlanPath": "Assets/bindings.json",
                 "nativeBindingPlanSha256": hashlib.sha256(raw).hexdigest()}
        plan = {"spineNativeStage": stage}
        assert _static_sort_spine_bindings(plan, root) == raw
        path.write_bytes(raw + b" ")
        assert _static_sort_spine_bindings(plan, root) is None
        path.unlink()
        assert _static_sort_spine_bindings(plan, root) is None


def test_binding_map_cannot_escape_candidate_or_use_readback_claims():
    with TemporaryDirectory() as folder:
        root = Path(folder) / "candidate"
        root.mkdir()
        outside = Path(folder) / "bindings.json"
        raw = b'{"components": []}'
        outside.write_bytes(raw)
        for relative in ("../bindings.json", str(outside)):
            assert _static_sort_spine_bindings({"spineNativeStage": {
                "nativeBindingPlanPath": relative,
                "nativeBindingPlanSha256": hashlib.sha256(raw).hexdigest(),
                "components": [{"sourceId": "untrusted-summary-only"}],
            }}, root) is None
        assert _static_sort_spine_bindings({}, root) is None
