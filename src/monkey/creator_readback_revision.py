"""Strict selector for additive, Editor-produced Creator readback revisions.

The original editor-readback.json remains immutable. This module validates the
atomic current-revision pointer and its full receipt hash chain before a caller
uses the newer readback for native-file verification.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


POINTER_PATH = "Analysis/Readback/current-revision.json"
REVISION_PATTERN = re.compile(r"^Analysis/Readback/reopened-([1-9][0-9]*)\.json$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MAX_RECEIPT_BYTES = 128 * 1024 * 1024
MAX_CHAIN_LENGTH = 4096


class RevisionError(ValueError):
    """Invalid or mismatched Editor readback revision evidence."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        raise RevisionError(f"CREATOR_READBACK_REVISION_BAD_SHA:{label}")
    return value


def _safe_relative_path(value: Any, label: str, *, allow_original: str | None = None) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise RevisionError(f"CREATOR_READBACK_REVISION_UNSAFE_PATH:{label}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise RevisionError(f"CREATOR_READBACK_REVISION_UNSAFE_PATH:{label}")
    normalized = pure.as_posix()
    if REVISION_PATTERN.fullmatch(normalized) or normalized == POINTER_PATH:
        return normalized
    if allow_original is not None and normalized == allow_original:
        return normalized
    raise RevisionError(f"CREATOR_READBACK_REVISION_PATH_NOT_ALLOWED:{label}")


def _read_candidate_file(root: Path, relative: str) -> bytes:
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise RevisionError(f"CREATOR_READBACK_REVISION_FILE_MISSING:{relative}") from exc
    if not resolved.is_relative_to(resolved_root):
        raise RevisionError(f"CREATOR_READBACK_REVISION_PATH_ESCAPES:{relative}")
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        try:
            if current.is_symlink():
                raise RevisionError(f"CREATOR_READBACK_REVISION_SYMLINK:{relative}")
        except OSError as exc:
            raise RevisionError(f"CREATOR_READBACK_REVISION_FILE_MISSING:{relative}") from exc
    try:
        if candidate.stat().st_size > MAX_RECEIPT_BYTES:
            raise RevisionError(f"CREATOR_READBACK_REVISION_FILE_TOO_LARGE:{relative}")
        return candidate.read_bytes()
    except OSError as exc:
        raise RevisionError(f"CREATOR_READBACK_REVISION_FILE_MISSING:{relative}") from exc


def _json_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RevisionError(f"CREATOR_READBACK_REVISION_JSON_INVALID:{label}") from exc
    if not isinstance(value, dict):
        raise RevisionError(f"CREATOR_READBACK_REVISION_JSON_SHAPE:{label}")
    return value


def _valid_native_files(readback: dict[str, Any]) -> None:
    rows = readback.get("nativeFiles")
    if not isinstance(rows, list) or not rows:
        raise RevisionError("CREATOR_READBACK_REVISION_NATIVE_FILES_MISSING")
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise RevisionError("CREATOR_READBACK_REVISION_NATIVE_FILE_ROW_INVALID")
        path = row.get("path")
        if not isinstance(path, str) or "\\" in path or "\x00" in path:
            raise RevisionError("CREATOR_READBACK_REVISION_NATIVE_FILE_PATH_INVALID")
        pure = PurePosixPath(path)
        if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
            raise RevisionError("CREATOR_READBACK_REVISION_NATIVE_FILE_PATH_UNSAFE")
        if not path.startswith(("assets/", "Analysis/")):
            raise RevisionError("CREATOR_READBACK_REVISION_NATIVE_FILE_PATH_OUTSIDE_ROOTS")
        if path in seen:
            raise RevisionError("CREATOR_READBACK_REVISION_NATIVE_FILE_DUPLICATE")
        seen.add(path)
        _require_sha(row.get("sha256"), f"nativeFiles:{path}")


def _check_identity(readback: dict[str, Any], *, manifest_sha256: str,
                    source_plan_sha256: str | None, project_uuid: str, label: str,
                    scene_uuid: str | None = None) -> None:
    if readback.get("projectUuid") != project_uuid:
        raise RevisionError(f"CREATOR_READBACK_REVISION_PROJECT_MISMATCH:{label}")
    if readback.get("manifestSha256") != manifest_sha256:
        raise RevisionError(f"CREATOR_READBACK_REVISION_MANIFEST_MISMATCH:{label}")
    if source_plan_sha256 is not None and readback.get("sourcePlanSha256") != source_plan_sha256:
        raise RevisionError(f"CREATOR_READBACK_REVISION_PLAN_MISMATCH:{label}")
    if scene_uuid is not None and readback.get("sceneUuid") != scene_uuid:
        raise RevisionError(f"CREATOR_READBACK_REVISION_SCENE_MISMATCH:{label}")


def select_current_revision(candidate: str | Path, manifest_sha256: str, project_uuid: str,
                            source_plan_sha256: str, original_readback_path: str) -> dict[str, Any] | None:
    """Return the verified current revision, or ``None`` when no pointer exists.

    Pointer presence is authoritative: malformed or stale revision evidence is
    an error and never falls back to the original receipt.
    """
    root = Path(candidate)
    pointer_path = root / POINTER_PATH
    if not pointer_path.exists() and not pointer_path.is_symlink():
        return None
    manifest_sha256 = _require_sha(manifest_sha256, "manifest")
    source_plan_sha256 = _require_sha(source_plan_sha256, "sourcePlan")
    if not isinstance(project_uuid, str) or not project_uuid:
        raise RevisionError("CREATOR_READBACK_REVISION_PROJECT_EXPECTED_MISSING")
    if original_readback_path not in ("Analysis/Readback/editor-readback.json", "Analysis/editor-readback.json"):
        raise RevisionError("CREATOR_READBACK_REVISION_ORIGIN_PATH_NOT_ALLOWED")
    original_relative = _safe_relative_path(original_readback_path, "origin", allow_original=original_readback_path)
    pointer_raw = _read_candidate_file(root, POINTER_PATH)
    pointer = _json_bytes(pointer_raw, POINTER_PATH)
    if pointer.get("schemaVersion") != 1 or pointer.get("kind") != "creator-reopen-readback-revision":
        raise RevisionError("CREATOR_READBACK_REVISION_POINTER_SCHEMA_INVALID")
    revision = pointer.get("revision")
    if type(revision) is not int or revision <= 0:
        raise RevisionError("CREATOR_READBACK_REVISION_POINTER_NUMBER_INVALID")
    receipt_path = _safe_relative_path(pointer.get("readbackPath"), "currentReceipt")
    match = REVISION_PATTERN.fullmatch(receipt_path)
    if not match or int(match.group(1)) != revision:
        raise RevisionError("CREATOR_READBACK_REVISION_POINTER_PATH_NUMBER_MISMATCH")

    pointer_manifest = _require_sha(pointer.get("manifestSha256"), "pointer.manifest")
    pointer_plan = _require_sha(pointer.get("sourcePlanSha256"), "pointer.sourcePlan")
    origin_path = _safe_relative_path(pointer.get("originReceiptPath"), "originReceipt", allow_original=original_relative)
    origin_sha = _require_sha(pointer.get("originReceiptSha256"), "originReceipt")
    scene_uuid = pointer.get("sceneUuid")
    if (pointer_manifest != manifest_sha256 or pointer_plan != source_plan_sha256 or
            pointer.get("projectUuid") != project_uuid or not isinstance(scene_uuid, str) or not scene_uuid or
            origin_path != original_relative):
        raise RevisionError("CREATOR_READBACK_REVISION_POINTER_IDENTITY_MISMATCH")

    current_path = receipt_path
    expected_hash = _require_sha(pointer.get("readbackSha256"), "currentReceipt")
    current_revision = revision
    expected_revision_metadata = {
        "revision": revision,
        "previousReceiptPath": pointer.get("previousReceiptPath"),
        "previousReceiptSha256": pointer.get("previousReceiptSha256"),
        "originReceiptPath": origin_path,
        "originReceiptSha256": origin_sha,
        "manifestSha256": manifest_sha256,
        "sourcePlanSha256": source_plan_sha256,
        "projectUuid": project_uuid,
    }
    current_raw = b""
    current_readback: dict[str, Any] = {}
    visited: set[str] = set()
    chain_count = 0
    while True:
        chain_count += 1
        if chain_count > MAX_CHAIN_LENGTH:
            raise RevisionError("CREATOR_READBACK_REVISION_CHAIN_TOO_LONG")
        if current_path in visited:
            raise RevisionError("CREATOR_READBACK_REVISION_CHAIN_CYCLE")
        visited.add(current_path)
        current_raw = _read_candidate_file(root, current_path)
        if _digest(current_raw) != expected_hash:
            raise RevisionError(f"CREATOR_READBACK_REVISION_RECEIPT_HASH_MISMATCH:{current_path}")
        current_readback = _json_bytes(current_raw, current_path)
        _check_identity(current_readback, manifest_sha256=manifest_sha256,
                        source_plan_sha256=source_plan_sha256, project_uuid=project_uuid, label=current_path,
                        scene_uuid=scene_uuid)
        metadata = current_readback.get("readbackRevision")
        if not isinstance(metadata, dict):
            raise RevisionError(f"CREATOR_READBACK_REVISION_METADATA_MISSING:{current_path}")
        if metadata.get("schemaVersion") != 1 or metadata.get("readSavedMethod") != "CreatorScene.readSaved":
            raise RevisionError(f"CREATOR_READBACK_REVISION_METHOD_METADATA_INVALID:{current_path}")
        if current_path == receipt_path:
            for key, value in expected_revision_metadata.items():
                if metadata.get(key) != value:
                    raise RevisionError(f"CREATOR_READBACK_REVISION_POINTER_RECEIPT_MISMATCH:{key}")
        else:
            if metadata.get("revision") != current_revision:
                raise RevisionError(f"CREATOR_READBACK_REVISION_CHAIN_NUMBER_MISMATCH:{current_path}")
            for key, value in (("originReceiptPath", origin_path), ("originReceiptSha256", origin_sha),
                               ("manifestSha256", manifest_sha256), ("sourcePlanSha256", source_plan_sha256),
                               ("projectUuid", project_uuid), ("sceneUuid", scene_uuid)):
                if metadata.get(key) != value:
                    raise RevisionError(f"CREATOR_READBACK_REVISION_CHAIN_IDENTITY_MISMATCH:{key}")

        previous_path = _safe_relative_path(metadata.get("previousReceiptPath"), "previousReceipt",
                                            allow_original=original_relative)
        previous_hash = _require_sha(metadata.get("previousReceiptSha256"), "previousReceipt")
        if previous_path == origin_path:
            if previous_hash != origin_sha:
                raise RevisionError("CREATOR_READBACK_REVISION_ORIGIN_LINK_MISMATCH")
            origin_raw = _read_candidate_file(root, origin_path)
            if _digest(origin_raw) != origin_sha:
                raise RevisionError("CREATOR_READBACK_REVISION_ORIGIN_HASH_MISMATCH")
            origin_readback = _json_bytes(origin_raw, origin_path)
            _check_identity(origin_readback, manifest_sha256=manifest_sha256,
                            source_plan_sha256=None, project_uuid=project_uuid, label=origin_path,
                            scene_uuid=scene_uuid)
            break

        prior_match = REVISION_PATTERN.fullmatch(previous_path)
        if not prior_match:
            raise RevisionError("CREATOR_READBACK_REVISION_PREVIOUS_PATH_INVALID")
        prior_revision = int(prior_match.group(1))
        if prior_revision >= current_revision:
            raise RevisionError("CREATOR_READBACK_REVISION_CHAIN_ORDER_INVALID")
        if metadata.get("revision") != current_revision:
            raise RevisionError("CREATOR_READBACK_REVISION_CHAIN_NUMBER_MISMATCH")
        current_path = previous_path
        expected_hash = previous_hash
        current_revision = prior_revision

    _valid_native_files(current_readback)
    if not isinstance(current_readback.get("sceneUuid"), str) or not current_readback["sceneUuid"]:
        raise RevisionError("CREATOR_READBACK_REVISION_SCENE_IDENTITY_MISSING")
    return {"path": root.joinpath(*PurePosixPath(receipt_path).parts), "relativePath": receipt_path,
            "raw": current_raw, "readback": current_readback, "pointer": pointer,
            "revision": revision, "receiptSha256": expected_hash,
            "chainLength": chain_count, "originReceiptSha256": origin_sha}
