"""Extract source-declared constant component defaults without executing JS."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable


_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def extract_declarations(source_path, expected_sha256: str, source_types: Iterable[str]) -> dict:
    """Extract decorated source-property defaults for uniquely RF-bound types.

    Only fields proven by a property decorator (or an exact decorated accessor
    backing relation) enter ``fields``. Undecorated constructor assignments are
    reported separately as runtime implementation evidence and do not become
    serialized static-field blockers. Decorated fields with unsupported or
    indirect defaults remain gaps. This invokes the pinned local Acorn parser
    and static RF module indexer; source code is never executed.
    """
    try:
        path = Path(source_path)
        if isinstance(source_types, (str, bytes)):
            raise TypeError("source_types must be an iterable of RF identity strings, not a string")
        types = list(source_types)
    except (TypeError, ValueError) as error:
        return {"components": {}, "diagnostics": [{"code": "INVALID_ARGUMENTS", "message": str(error)}]}
    if not _SHA256.fullmatch(expected_sha256 or ""):
        return {"components": {}, "diagnostics": [{"code": "INVALID_EXPECTED_SHA256", "message": "expected_sha256 must be lowercase SHA-256 hex"}]}
    if not types or any(not isinstance(item, str) or not item.strip() for item in types):
        return {"components": {}, "diagnostics": [{"code": "INVALID_SOURCE_TYPES", "message": "source_types must contain non-empty RF identity strings"}]}
    node = shutil.which("node")
    if node is None:
        return {"components": {}, "diagnostics": [{"code": "NODE_UNAVAILABLE", "message": "Node.js is required for the pinned Acorn syntax parser"}]}
    helper = Path(__file__).with_name("static-declarations.cjs")
    try:
        completed = subprocess.run(
            [node, str(helper), str(path), expected_sha256, json.dumps(types, ensure_ascii=False)],
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"components": {}, "diagnostics": [{"code": "STATIC_DECLARATION_PROCESS_FAILED", "message": str(error)}]}
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        message = completed.stderr.strip() or f"static declaration helper exited {completed.returncode} without JSON"
        return {"components": {}, "diagnostics": [{"code": "INVALID_HELPER_OUTPUT", "message": message}]}
    if not isinstance(result, dict) or not isinstance(result.get("components"), dict) or not isinstance(result.get("diagnostics"), list):
        return {"components": {}, "diagnostics": [{"code": "INVALID_HELPER_RESULT", "message": "static declaration helper returned an invalid result shape"}]}
    return {"components": result["components"], "diagnostics": result["diagnostics"]}
