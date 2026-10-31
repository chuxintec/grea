"""Hash-bound, project-scoped macOS Unity QA runtime materialization.

This module prepares isolated app copies and persistent QA profiles. Preparing
never launches a process; launch and collection are explicit operations.
"""
from __future__ import annotations

import hashlib
import ctypes
import fcntl
import json
import os
import plistlib
import re
import shutil
import stat
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .errors import BeaverError, fail
from .io import encoded, inside, load, read, safe, sha
from .output_limits import digest_file
from .payload import RootReader, stream_identity, verify_manifest, manifest as payload_manifest, promote

SCHEMA_VERSION = 1
CONTRACT = "beaver-unity-qa/1"
MAX_SPEC = 4 * 1024 * 1024
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SHA = re.compile(r"^[a-f0-9]{64}$")
CONTROL_ENV = {"BEAVER_NATIVE_JOB", "BEAVER_ADOPT_JOB", "MONKEY_ADOPT_JOB"}
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
SAFE_FLAGS = re.compile(r"^-(?:screen-(?:fullscreen|width|height)|force-metal|force-d3d11|development|qa-[a-z0-9-]{1,40})$")
SAFE_VALUES = re.compile(r"^(?:0|[1-9][0-9]{0,3}|true|false)$")


def _id(value, field):
    if not isinstance(value, str) or not ID.fullmatch(value) or value in (".", ".."):
        fail("QA_SPEC_ID", field, "Expected a safe stable identifier")
    return value


def _hash(value, field):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        fail("QA_SPEC_HASH", field, "Expected lowercase SHA256")
    return value


def _load_spec(spec_path, expected_spec_sha256):
    path = safe(spec_path)
    raw = read(path, MAX_SPEC)
    digest = sha(raw)
    if digest != _hash(expected_spec_sha256, "expectedSpecSha256"):
        fail("QA_SPEC_DRIFT", str(path), "Explicit expected spec SHA256 does not match")
    doc = load(raw, max_nodes=50000)
    required = {"schemaVersion", "contract", "projectId", "buildId", "artifactManifest", "artifactManifestSha256", "profileId", "profileSeed", "configInputs", "environmentBindings", "testMode", "arguments"}
    if not isinstance(doc, dict) or set(doc) != required or type(doc.get("schemaVersion")) is not int or doc.get("schemaVersion") != SCHEMA_VERSION or doc.get("contract") != CONTRACT:
        fail("QA_SPEC", str(path), "Expected the closed beaver-unity-qa/1 specification")
    _id(doc["projectId"], "projectId"); _id(doc["buildId"], "buildId"); _id(doc["profileId"], "profileId")
    _hash(doc["artifactManifestSha256"], "artifactManifestSha256")
    if doc["testMode"] not in ("normal", "denyDocuments"):
        fail("QA_TEST_MODE", "testMode", "Only normal or closed denyDocuments mode is supported")
    if not isinstance(doc["configInputs"], dict) or not isinstance(doc["environmentBindings"], dict):
        fail("QA_SPEC", str(path), "configInputs and environmentBindings must be objects")
    seed = doc["profileSeed"]
    if seed is not None:
        if not isinstance(seed, dict) or set(seed) != {"root", "manifest", "manifestSha256"}:
            fail("QA_PROFILE_SEED", "profileSeed", "Expected null or a manifest-pinned directory inventory")
        _hash(seed["manifestSha256"], "profileSeed.manifestSha256")
    for key, row in doc["configInputs"].items():
        _id(key, "configInputs key")
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            fail("QA_CONFIG_INPUT", key, "Expected explicit path and SHA256")
        _hash(row["sha256"], f"configInputs.{key}.sha256")
    for env_name, binding in doc["environmentBindings"].items():
        if (not isinstance(env_name, str) or not ENV_NAME.fullmatch(env_name) or env_name in CONTROL_ENV
                or env_name in {"HOME", "PATH", "TMPDIR", "LANG"}
                or env_name.startswith(("LC_", "DYLD_", "LD_", "BEAVER_", "MONKEY_"))):
            fail("QA_ENV_NAME", str(env_name), "Unsafe or reserved environment binding")
        if not isinstance(binding, dict) or set(binding) != {"kind", "id"} or binding["kind"] not in ("config", "profile"):
            fail("QA_ENV_BINDING", env_name, "Expected a config/profile binding with declared id")
        if binding["kind"] == "config":
            if binding["id"] not in doc["configInputs"]: fail("QA_ENV_BINDING", env_name, "Config id is not declared")
        elif binding["id"] != "root":
            fail("QA_ENV_BINDING", env_name, "Profile binding id must be root")
    if not any(binding.get("kind") == "profile" for binding in doc["environmentBindings"].values()):
        fail("QA_PROFILE_BINDING_REQUIRED", "environmentBindings", "At least one explicit profile-directory binding is required")
    args = doc["arguments"]
    if not isinstance(args, list) or len(args) > 32:
        fail("QA_ARGUMENTS", "arguments", "Expected at most 32 explicitly approved literal arguments")
    for token in args:
        if not isinstance(token, str) or not (SAFE_FLAGS.fullmatch(token) or SAFE_VALUES.fullmatch(token)) or any(ord(c) < 32 for c in token) or any(c in token for c in "$`\\;|&<>\n\r"):
            fail("QA_ARGUMENTS", repr(token), "Argument is outside the closed literal allowlist")
    return path, doc, digest


def _home_root():
    return Path.home() / "Library" / "Application Support" / "beaver" / "unity-qa"


def failure_receipt(error):
    """Return a persisted prepare receipt path attached to an implementation failure, if any."""
    return getattr(error, "qa_failure_receipt", None)


def _guard_root(path):
    """Reject symlink ancestors and roots with an unexpected ownership marker."""
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink():
            fail("QA_SYMLINK_ROOT", str(part), "QA runtime roots cannot contain symbolic links")
    return path


def _write_control_json(path, value, create=False):
    flags = os.O_WRONLY | os.O_NOFOLLOW
    if create: flags |= os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            fail("QA_CONTROL_FILE", str(path), "Expected an independent regular control file")
        os.fchmod(fd, 0o600)
        if not create: os.ftruncate(fd, 0)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(encoded(value)); stream.flush(); os.fsync(fd)
    finally:
        os.close(fd)


def _open_control_lock(path):
    try: fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError as error: fail("QA_CONTROL_FILE", str(path), f"Lock path cannot be opened without following links ({type(error).__name__})")
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(fd)
        fail("QA_CONTROL_FILE", str(path), "Expected an independent regular lock file")
    os.fchmod(fd, 0o600)
    return os.fdopen(fd, "r+b")


def _write_control_text(path, text, create=False):
    flags = os.O_WRONLY | os.O_NOFOLLOW
    if create: flags |= os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            fail("QA_CONTROL_FILE", str(path), "Expected an independent regular control file")
        os.fchmod(fd, 0o600)
        if not create: os.ftruncate(fd, 0)
        with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as stream:
            stream.write(text); stream.flush(); os.fsync(fd)
    finally: os.close(fd)


def _read_control_json(path, max_bytes):
    _guard_root(path)
    try: fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as error: fail("QA_CONTROL_FILE", str(path), f"Control file cannot be opened without following links ({type(error).__name__})")
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1: fail("QA_CONTROL_FILE", str(path), "Expected an independent regular control file")
        with os.fdopen(fd, "rb", closefd=False) as stream: raw = stream.read(max_bytes + 1)
    finally: os.close(fd)
    if len(raw) > max_bytes: fail("QA_CONTROL_FILE", str(path), "Control file exceeds its byte budget")
    return load(raw)


def _owned(path, identity):
    path = _guard_root(path)
    marker = path / "owner.json"
    if not path.exists():
        return False
    if not path.is_dir() or marker.is_symlink() or not marker.is_file():
        fail("QA_UNKNOWN_OWNERSHIP", str(path), "Existing runtime root has no trustworthy owner record")
    try: old = _read_control_json(marker, 64 * 1024)
    except (OSError, ValueError): fail("QA_UNKNOWN_OWNERSHIP", str(path), "Owner record is unreadable")
    if old != identity:
        fail("QA_OWNER_DRIFT", str(marker), "Stable ownership identity differs from the requested runtime")
    return True


def _write_owner(path, identity):
    if path.exists():
        marker = path / "owner.json"
        if marker.exists():
            old = _read_control_json(marker, 64 * 1024)
            if old != identity: fail("QA_OWNER_DRIFT", str(marker), "Owner record changed")
            return
    path.mkdir(parents=True, exist_ok=True)
    _write_control_json(path / "owner.json", identity, create=True)


def _signature(app):
    """Read existing code-signing identity; never signs or modifies the bundle."""
    try:
        detail = subprocess.run(["/usr/bin/codesign", "-dv", "--verbose=4", str(app)], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unknown", "reason": type(exc).__name__}
    output = detail.stdout + detail.stderr
    if detail.returncode != 0:
        if "code object is not signed" in output.lower() or "not signed at all" in output.lower():
            return {"status": "unsigned"}
        return {"status": "unknown", "returnCode": detail.returncode}
    verified = subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)], capture_output=True, text=True, timeout=20)
    fields = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if key in ("Identifier", "TeamIdentifier", "CDHash", "Authority"):
                fields[key] = value
    return {"status": "valid" if verified.returncode == 0 else "invalid", "identity": fields, "verifyReturnCode": verified.returncode}


def _copy_app(root, rows, source_app, app_dest):
    # Copy only the manifest-verified player subtree; use O_EXCL and never follow links.
    root = Path(root)
    app_dest.mkdir(parents=True, exist_ok=False)
    prefix = "player/" + source_app.name + "/"
    if any(not p.startswith(prefix) for p in rows):
        fail("QA_APP_SCOPE", str(source_app), "Artifact manifest contains files outside its single app bundle")
    paths = sorted(rows, key=lambda p: (p.count("/"), p))
    with RootReader(root) as reader:
        for rel in paths:
            local = rel[len(prefix):]
            if not local: continue
            row = rows[rel]; dest = inside(app_dest, local)
            if "symlink" in row:
                target = row["symlink"]
                if Path(target).is_absolute(): fail("QA_EXTERNAL_LINK", rel, "Absolute app symlinks are not portable and are rejected")
                link = Path(local).parent / target
                resolved = (app_dest / link).resolve(strict=False)
                if not resolved.is_relative_to(app_dest): fail("QA_EXTERNAL_LINK", rel, "App symlink escapes the copied bundle")
                dest.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(target, dest)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with reader.open(rel) as src, dest.open("xb") as out:
                digest, size, _ = stream_identity(src, rel, output=out)
            if (digest, size) != (row["sha256"], row["bytes"]): fail("QA_COPY_DRIFT", rel, "Copied bytes differ from manifest identity")
            os.chmod(dest, stat.S_IMODE(os.stat(root / rel, follow_symlinks=False).st_mode))


def _app_executable(app):
    try: info = plistlib.loads(read(app / "Contents" / "Info.plist", 2 * 1024 * 1024))
    except Exception: fail("QA_APP_INFO", str(app), "Bundle Info.plist is invalid")
    name = info.get("CFBundleExecutable") if isinstance(info, dict) else None
    if not isinstance(name, str) or not name or Path(name).name != name:
        fail("QA_APP_EXECUTABLE", str(app), "CFBundleExecutable must be a basename")
    executable = app / "Contents" / "MacOS" / name
    if executable.is_symlink() or not executable.is_file() or not os.access(executable, os.X_OK):
        fail("QA_APP_EXECUTABLE", str(executable), "Expected owned executable file in bundle")
    return executable


def _bundle_identifier(app):
    info = plistlib.loads(read(app / "Contents" / "Info.plist", 2 * 1024 * 1024))
    value = info.get("CFBundleIdentifier") if isinstance(info, dict) else None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", value):
        fail("QA_BUNDLE_IDENTIFIER", str(app), "Expected a stable reverse-DNS CFBundleIdentifier")
    return value


def _copy_input(source, destination, expected, label):
    source = safe(source)
    if not source.is_file() or source.is_symlink(): fail("QA_INPUT_PATH", str(source), "Input must be a regular non-symlink file")
    before = digest_file(source)
    if before != expected: fail("QA_INPUT_DRIFT", label, "Input differs from its explicit SHA256")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as src, destination.open("xb") as out:
        h, size, _ = stream_identity(src, label, output=out)
    if h != expected: fail("QA_INPUT_DRIFT", label, "Input changed while it was copied")
    os.chmod(destination, 0o600)
    return {"sha256": h, "bytes": size, "sourceBeforeSha256": before, "sourceAfterSha256": digest_file(source)}


def _reject_documents_file_references(path):
    try: value = load(read(path, 16 * 1024 * 1024), max_nodes=200000)
    except (ValueError, UnicodeError) as exc: fail("QA_CONFIG_JSON", str(path), "Config input must be valid bounded UTF-8 JSON")
    docs = (Path.home() / "Documents").resolve()
    pending = [(None, value)]
    while pending:
        key, node = pending.pop()
        if isinstance(node, dict): pending.extend((k, v) for k, v in node.items())
        elif isinstance(node, list): pending.extend((key, item) for item in node)
        elif isinstance(node, str) and isinstance(key, str) and any(token in key.lower() for token in ("file", "path", "directory", "dir")):
            candidate = Path(os.path.expanduser(node))
            if not candidate.is_absolute(): continue
            resolved = candidate.resolve(strict=False)
            if resolved == docs or resolved.is_relative_to(docs):
                fail("QA_CONFIG_DOCUMENTS_REFERENCE", key, "Config file/path field points into Documents")


def _profile_owner_path(project_root, profile_id):
    return project_root / "data" / "profile-owners" / (profile_id + ".json")


def _profile_owned(project_root, profile_root, profile_identity):
    _guard_root(profile_root)
    owner_path = _guard_root(_profile_owner_path(project_root, profile_identity["profileId"]))
    if not profile_root.exists() and not owner_path.exists(): return False
    if not profile_root.is_dir() or not owner_path.is_file():
        fail("QA_UNKNOWN_OWNERSHIP", str(profile_root), "Profile or external owner record is missing")
    owner = _read_control_json(owner_path, 64 * 1024)
    if owner != profile_identity: fail("QA_OWNER_DRIFT", str(owner_path), "Stable profile owner identity differs")
    return True


def _copy_seed(seed, destination):
    destination.mkdir(parents=True, exist_ok=False)
    if seed is None:
        return {"status": "empty-profile", "seedApplied": False, "treeSha256": _hash_tree(destination)}
    root = safe(seed["root"]); manifest_path = safe(seed["manifest"])
    if digest_file(manifest_path) != seed["manifestSha256"]:
        fail("QA_PROFILE_SEED_DRIFT", str(manifest_path), "Seed inventory manifest SHA256 differs")
    verified = verify_manifest(root, manifest_path)
    _, files, _ = payload_manifest(manifest_path)
    with RootReader(root) as reader:
        for rel, row in files.items():
            target = inside(destination, rel); target.parent.mkdir(parents=True, exist_ok=True)
            if "symlink" in row:
                if Path(row["symlink"]).is_absolute(): fail("QA_PROFILE_SEED_LINK", rel, "Absolute seed symlinks are rejected")
                target_candidate = (target.parent / row["symlink"]).resolve(strict=False)
                if not target_candidate.is_relative_to(destination): fail("QA_PROFILE_SEED_LINK", rel, "Seed symbolic link escapes profile")
                os.symlink(row["symlink"], target)
            else:
                with reader.open(rel) as src, target.open("xb") as out:
                    digest,size,_=stream_identity(src, rel, output=out)
                if (digest,size)!=(row['sha256'],row['bytes']):
                    fail('QA_PROFILE_SEED_DRIFT',rel,'Seed bytes changed after inventory verification')
                os.chmod(target, stat.S_IMODE(os.stat(root / rel, follow_symlinks=False).st_mode))
    if digest_file(manifest_path) != seed["manifestSha256"]: fail("QA_PROFILE_SEED_DRIFT", str(manifest_path), "Seed manifest changed during copy")
    after=verify_manifest(root,manifest_path)
    return {"status": "seeded", "seedApplied": True, "manifestSha256": seed["manifestSha256"], "verification": verified, "verificationAfter":after, "treeSha256": _hash_tree(destination)}


def prepare(spec_path, expected_spec_sha256, out=None):
    """Serialize preparation by project, then materialize without launching."""
    spec_path, doc, spec_digest = _load_spec(spec_path, expected_spec_sha256)
    manifest_path = safe(doc["artifactManifest"])
    if digest_file(manifest_path) != doc["artifactManifestSha256"]: fail("QA_MANIFEST_DRIFT", str(manifest_path), "Artifact manifest SHA256 differs from spec")
    apps = list((manifest_path.parent / "player").glob("*.app"))
    if len(apps) != 1: fail("QA_APP_COUNT", str(manifest_path.parent), "Artifact must contain exactly one player/*.app bundle")
    bundle_id = _bundle_identifier(apps[0])
    project_root = _guard_root(_home_root()) / doc["projectId"]
    _owned(project_root, {"schemaVersion": 1, "contract": "beaver-unity-qa-project/1", "projectId": doc["projectId"], "bundleIdentifier": bundle_id})
    lock_root = _guard_root(_home_root() / ".locks")
    lock_root.mkdir(parents=True, exist_ok=True); os.chmod(lock_root, 0o700)
    lock_path = _guard_root(lock_root / (doc["projectId"] + ".prepare.lock"))
    with _open_control_lock(lock_path) as lock:
        try: fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        except OSError: fail("QA_PROJECT_LOCK", str(lock_path), "Unable to acquire project preparation lock")
        return _prepare_locked(spec_path, expected_spec_sha256, out)


def _prepare_locked(spec_path, expected_spec_sha256, out=None):
    """Prepare hash-bound app/config/profile roots. This function never launches."""
    spec_path, doc, spec_sha = _load_spec(spec_path, expected_spec_sha256)
    manifest_path = safe(doc["artifactManifest"])
    if digest_file(manifest_path) != doc["artifactManifestSha256"]:
        fail("QA_MANIFEST_DRIFT", str(manifest_path), "Artifact manifest SHA256 differs from spec")
    manifest_root = manifest_path.parent
    verified = verify_manifest(manifest_root, manifest_path, scope="player", allow_links=True, artifact=True)
    artifact_doc = load(read(manifest_path, 128 * 1024 * 1024), max_nodes=8_000_000)
    rows = {row["path"]: row for row in artifact_doc["files"]}
    apps = list((manifest_root / "player").glob("*.app"))
    if len(apps) != 1: fail("QA_APP_COUNT", str(manifest_root), "Artifact must contain exactly one player/*.app bundle")
    source_app = apps[0]
    executable = _app_executable(source_app)
    bundle_identifier = _bundle_identifier(source_app)
    if executable.relative_to(manifest_root).as_posix() not in rows:
        fail("QA_APP_EXECUTABLE", str(executable), "Executable is not declared by artifact manifest")
    root = _guard_root(_home_root())
    project_root = root / doc["projectId"]
    build_root = project_root / "builds" / doc["buildId"]
    data_root = project_root / "data"
    profile_root = data_root / "profiles" / doc["profileId"]
    identity = {"schemaVersion": 1, "contract": "beaver-unity-qa-owner/1", "projectId": doc["projectId"], "buildId": doc["buildId"], "profileId": doc["profileId"], "bundleIdentifier": bundle_identifier, "specSha256": spec_sha, "artifactManifestSha256": doc["artifactManifestSha256"], "sourceSha256": artifact_doc["sourceSha256"]}
    project_owner = {"schemaVersion": 1, "contract": "beaver-unity-qa-project/1", "projectId": doc["projectId"], "bundleIdentifier": bundle_identifier}
    _owned(project_root, project_owner)
    if build_root.exists(): fail("QA_BUILD_EXISTS", str(build_root), "A build identity is immutable and cannot be overwritten")
    # Profile owner deliberately excludes buildId, allowing a stable profile across builds.
    profile_identity = {"schemaVersion": 1, "contract": "beaver-unity-qa-profile/1", "projectId": doc["projectId"], "profileId": doc["profileId"]}
    profile_exists = _profile_owned(project_root, profile_root, profile_identity)
    profile_owner_path = _profile_owner_path(project_root, doc["profileId"])
    configs_final = data_root / "configs" / doc["buildId"]
    if configs_final.exists(): fail("QA_CONFIG_EXISTS", str(configs_final), "Build config identity already exists")
    # Validate every input before creating roots, owner records, or profile data.
    source_before = verify_manifest(manifest_root, manifest_path, scope="player", allow_links=True, artifact=True)
    seed_preflight = None
    if doc["profileSeed"] is not None:
        seed_preflight = safe(doc["profileSeed"]["manifest"])
        if digest_file(seed_preflight) != doc["profileSeed"]["manifestSha256"]: fail("QA_PROFILE_SEED_DRIFT", str(seed_preflight), "Seed inventory manifest SHA256 differs")
        verify_manifest(doc["profileSeed"]["root"], seed_preflight)
    for key, item in doc["configInputs"].items():
        if digest_file(item["path"]) != item["sha256"]: fail("QA_INPUT_DRIFT", key, "Config source differs from explicit SHA256")
        _reject_documents_file_references(item["path"])
    prep_run_id = uuid.uuid4().hex
    receipt_root = data_root / "receipts"
    receipt_path = receipt_root / ("prepare-" + prep_run_id + ".json")
    report_dir = safe(out) if out is not None else None
    if report_dir is not None:
        if report_dir.exists(): fail("QA_OUTPUT_EXISTS", str(report_dir), "Report output directory must be fresh")
        report_path = report_dir / "qa-prepare.json"
    else: report_path = receipt_root / ("prepare-report-" + prep_run_id + ".json")
    if report_path.exists() or receipt_path.exists(): fail("QA_OUTPUT_EXISTS", str(report_path), "Receipt/report output must be fresh")
    # All mutable content is staged first; the durable receipt identifies stages for safe recovery.
    for parent in (root, project_root, build_root.parent, receipt_root, configs_final.parent, data_root):
        _guard_root(parent); parent.mkdir(parents=True, exist_ok=True)
    os.chmod(data_root, 0o700)
    if profile_exists and (not profile_root.is_dir() or not profile_owner_path.is_file()): fail("QA_UNKNOWN_OWNERSHIP", str(profile_root), "Existing profile ownership is incomplete")
    stage = build_root.parent / ("." + doc["buildId"] + ".stage-" + uuid.uuid4().hex)
    config_stage = configs_final.parent / ("." + doc["buildId"] + ".stage-" + uuid.uuid4().hex)
    profile_stage = None if profile_exists else profile_root.parent / ("." + doc["profileId"] + ".stage-" + uuid.uuid4().hex)
    receipt = {"schemaVersion": 1, "contract": "beaver-unity-qa-prepare-receipt/1", "runId": prep_run_id, "projectId": doc["projectId"], "buildId": doc["buildId"], "profileId": doc["profileId"], "status": "staging", "stagePaths": [str(stage), str(config_stage), *([str(profile_stage)] if profile_stage else [])], "committed": []}
    _write_control_json(receipt_path, receipt, create=True)
    try:
        if not (project_root / "owner.json").exists(): _write_owner(project_root, project_owner)
        stage.mkdir(mode=0o700); config_stage.mkdir(mode=0o700)
        _copy_app(manifest_root, rows, source_app, stage / "App.app")
        _app_executable(stage / "App.app")
        source_signature = _signature(source_app); copied_signature = _signature(stage / "App.app")
        if source_signature["status"] in ("valid", "invalid") and copied_signature != source_signature:
            fail("QA_SIGNATURE_DRIFT", str(stage / "App.app"), "Read-only source and copied signing identities/verification differ")
        if source_signature["status"] == "unsigned" and copied_signature["status"] != "unsigned": fail("QA_SIGNATURE_DRIFT", str(stage / "App.app"), "Copied signature state differs from unsigned source")
        config_records = {}
        for key, item in doc["configInputs"].items():
            dest = config_stage / (key + ".json")
            _guard_root(dest)
            config_records[key] = dict(_copy_input(item["path"], dest, item["sha256"], "config:" + key), path=str(configs_final / (key + ".json")), storage="data")
        if profile_stage is not None:
            seed_record = _copy_seed(doc["profileSeed"], profile_stage)
            os.chmod(profile_stage, 0o700)
        else:
            seed_record = {"status": "existing-profile-preserved", "seedApplied": False}
        bundle_identity = _hash_tree(stage / "App.app")
        bundle_record = {"path": str(build_root / "App.app"), "treeSha256": bundle_identity, "sourceManifestSha256": source_before["manifestSha256"]}
        source_after = verify_manifest(manifest_root, manifest_path, scope="player", allow_links=True, artifact=True)
        if source_before["manifestSha256"] != source_after["manifestSha256"]: fail("QA_SOURCE_AFTER_DRIFT", str(manifest_path), "Source manifest changed during prepare")
        for key, item in doc["configInputs"].items():
            if digest_file(item["path"]) != item["sha256"]: fail("QA_INPUT_AFTER_DRIFT", key, "Config source changed after copy")
        if profile_stage is not None:
            profile_root.parent.mkdir(parents=True, exist_ok=True)
            promote(profile_stage, profile_root); receipt["committed"].append("profileData"); _write_control_json(receipt_path, receipt)
            profile_owner_path.parent.mkdir(parents=True, exist_ok=True); _write_control_json(profile_owner_path, profile_identity, create=True)
            os.chmod(profile_owner_path, 0o600); receipt["committed"].append("profileOwner"); _write_control_json(receipt_path, receipt)
        promote(config_stage, configs_final); receipt["committed"].append("configs"); _write_control_json(receipt_path, receipt)
        owner = {**identity, "environmentBindings": doc["environmentBindings"], "arguments": doc["arguments"], "testMode": doc["testMode"], "bundle": bundle_record, "configInputs": config_records, "profileSeed": seed_record, "signature": {"source": source_signature, "copy": copied_signature}, "declaredProfileBinding": True}
        owner_sha = sha(encoded(owner)); _write_control_json(stage / "qa-owner.json", owner, create=True)
        promote(stage, build_root); receipt["committed"].append("bundle"); _write_control_json(receipt_path, receipt)
    except BaseException as error:
        shutil.rmtree(stage, ignore_errors=True)
        shutil.rmtree(config_stage, ignore_errors=True)
        if profile_stage is not None: shutil.rmtree(profile_stage, ignore_errors=True)
        receipt["status"] = "failed-or-recovery-required"; _write_control_json(receipt_path, receipt)
        try: error.qa_failure_receipt = str(receipt_path)
        except Exception: pass
        raise
    receipt.update(status="prepared", sourceVerificationBefore=source_before, sourceVerificationAfter=source_after, ownerSha256=owner_sha, committed=["profileData", "profileOwner", "configs", "bundle"])
    _write_control_json(receipt_path, receipt)
    report = {"schemaVersion": 1, "contract": "beaver-unity-qa-prepare/1", "status": "prepared", "runId": prep_run_id, "projectId": doc["projectId"], "buildId": doc["buildId"], "profileId": doc["profileId"], "ownerSha256": owner_sha, "specPath": str(spec_path), "specSha256": spec_sha, "artifactManifest": str(manifest_path), "artifactManifestSha256": doc["artifactManifestSha256"], "sourceSha256": artifact_doc["sourceSha256"], "sourceVerificationBefore": source_before, "sourceVerificationAfter": source_after, "bundle": bundle_record, "signature": {"source": source_signature, "copy": copied_signature}, "profileRoot": str(profile_root), "profileOwner": profile_identity, "profileSeed": seed_record, "configInputs": config_records, "testMode": doc["testMode"], "launchPerformed": False, "profileIsolation": "only explicitly declared profile-directory environment bindings; HOME and Unity persistentDataPath are unchanged and not claimed isolated", "limitations": ["No app process launched; no runtime file-access syscall evidence produced", "Existing signature was read-only verified; no signing operation performed", "The consuming app must use a declared profile binding for save isolation; Unity PlayerPrefs and ordinary AppData are not redirected"]}
    report["prepareReceipt"] = str(receipt_path)
    if report_dir is not None: report_dir.mkdir(parents=True, exist_ok=False)
    _write_control_json(report_path, report, create=True)
    return dict(status="prepared", runId=report["runId"], projectId=doc["projectId"], buildId=doc["buildId"], profileId=doc["profileId"], report=str(report_path), receipt=str(receipt_path), owner=owner, ownerSha256=owner_sha, bundle=bundle_record, profileRoot=str(profile_root), configInputs=config_records, sourceVerificationBefore=source_before, sourceVerificationAfter=source_after)


def _hash_tree(root):
    digest = hashlib.sha256()
    for parent, dirs, files in os.walk(root, followlinks=False):
        dirs.sort(); files.sort()
        for name in sorted(dirs + files):
            path = Path(parent) / name; rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                payload = b"L\0" + rel.encode() + b"\0" + os.readlink(path).encode()
            elif path.is_file():
                payload = b"F\0" + rel.encode() + b"\0" + bytes.fromhex(digest_file(path)) + str(stat.S_IMODE(path.stat().st_mode)).encode()
            else: continue
            digest.update(payload)
    return digest.hexdigest()


def _read_owner(project_id, build_id, profile_id, expected_owner_sha256):
    for value, field in ((project_id, "projectId"), (build_id, "buildId"), (profile_id, "profileId")): _id(value, field)
    root = _guard_root(_home_root())
    project_root = root / project_id; build_root = project_root / "builds" / build_id; profile_root = project_root / "data" / "profiles" / profile_id
    profile_identity = {"schemaVersion": 1, "contract": "beaver-unity-qa-profile/1", "projectId": project_id, "profileId": profile_id}
    if not _profile_owned(project_root, profile_root, profile_identity):
        fail("QA_UNKNOWN_OWNERSHIP", str(profile_root), "QA profile owner record is missing")
    _guard_root(build_root)
    marker = build_root / "qa-owner.json"
    if not marker.is_file() or marker.is_symlink(): fail("QA_UNKNOWN_OWNERSHIP", str(build_root), "Build has no stable owner record")
    owner = _read_control_json(marker, 128 * 1024)
    actual = sha(encoded(owner))
    if actual != expected_owner_sha256: fail("QA_OWNER_DRIFT", str(marker), "Expected owner SHA256 does not match")
    if owner.get("projectId") != project_id or owner.get("buildId") != build_id or owner.get("profileId") != profile_id:
        fail("QA_UNKNOWN_OWNERSHIP", str(marker), "Build owner identity does not match requested IDs")
    project_identity = {"schemaVersion": 1, "contract": "beaver-unity-qa-project/1", "projectId": project_id, "bundleIdentifier": owner.get("bundleIdentifier")}
    _owned(project_root, project_identity)
    return build_root, profile_root, owner


def launch(project_id, build_id, profile_id, expected_owner_sha256, duration=60, run_id=None):
    """Launch exactly the owned GUI executable; never attach to or kill foreign processes."""
    if type(duration) is not int or not 1 <= duration <= 3600: fail("QA_DURATION", str(duration), "Expected a 1..3600 second bounded process budget")
    build_root, profile_root, owner = _read_owner(project_id, build_id, profile_id, expected_owner_sha256)
    app = build_root / "App.app"; exe = _app_executable(app)
    if _hash_tree(app) != owner.get("bundle", {}).get("treeSha256"):
        fail("QA_BUNDLE_DRIFT", str(app), "Prepared bundle changed after ownership record")
    run_id = _id(run_id or uuid.uuid4().hex, "runId")
    bindings = owner.get("environmentBindings", {})
    data_root = build_root.parent.parent / "data"
    tmp_path = _guard_root(data_root / "tmp" / profile_id); tmp_path.mkdir(parents=True, exist_ok=True); os.chmod(tmp_path, 0o700)
    env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "HOME": str(Path.home()), "TMPDIR": str(tmp_path), "LANG": "en_US.UTF-8"}
    for name, binding in bindings.items():
        if binding["kind"] == "config":
            config = owner.get("configInputs", {}).get(binding["id"])
            if not isinstance(config, dict) or not isinstance(config.get("path"), str):
                fail("QA_OWNER_CONFIG", name, "Owner record lacks the declared controlled config")
            config_path = _guard_root(config["path"])
            if not config_path.is_file() or digest_file(config_path) != config.get("sha256"):
                fail("QA_CONFIG_DRIFT", binding["id"], "Controlled Data config is missing or changed")
            if config_path.is_relative_to(Path.home() / "Documents"):
                fail("QA_CONFIG_PATH", name, "Runtime config binding cannot point into Documents")
            env[name] = str(config_path)
        else: env[name] = str(profile_root)
    log_path = data_root / "logs" / profile_id / (run_id + ".log")
    _guard_root(log_path.parent); log_path.parent.mkdir(parents=True, exist_ok=True); os.chmod(log_path.parent, 0o700)
    args = [str(exe), *owner.get("arguments", []), "-logFile", str(log_path)]
    mode = owner.get("testMode", "normal")
    sandbox_info = {"requested": mode == "denyDocuments", "profilePath": None, "profileSha256": None, "launchCompleted": False, "enforcementIndependentlyVerified": False}
    if mode == "denyDocuments":
        docs = (Path.home() / "Documents").resolve()
        escaped_docs = str(docs).replace("\\", "\\\\").replace('"', '\\"')
        profile = f'(version 1)\n(allow default)\n(deny file-read* (subpath "{escaped_docs}"))\n(deny file-write* (subpath "{escaped_docs}"))\n'
        sandbox_file = data_root / "receipts" / ("deny-documents-" + run_id + ".sb")
        _guard_root(sandbox_file)
        sandbox_file.parent.mkdir(parents=True, exist_ok=True)
        _write_control_text(sandbox_file, profile, create=True)
        sandbox_info.update(profilePath=str(sandbox_file), profileSha256=digest_file(sandbox_file))
        args = ["/usr/bin/sandbox-exec", "-p", profile, str(exe), *owner.get("arguments", []), "-logFile", str(log_path)]
    started = datetime.now(timezone.utc).isoformat()
    receipt_path = data_root / "runs" / (run_id + ".json")
    _guard_root(receipt_path)
    if os.path.lexists(receipt_path): fail("QA_RUN_EXISTS", str(receipt_path), "runId is immutable and cannot be reused")
    _guard_root(receipt_path.parent); receipt_path.parent.mkdir(parents=True, exist_ok=True); os.chmod(receipt_path.parent, 0o700)
    lock_path = data_root / "locks" / (profile_id + ".lock")
    _guard_root(lock_path); lock_path.parent.mkdir(parents=True, exist_ok=True); os.chmod(lock_path.parent, 0o700)
    with _open_control_lock(lock_path) as lock:
        try: fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: fail("QA_PROFILE_BUSY", str(profile_root), "Another QA launch owns this profile")
        lock.seek(0); lock.truncate(); lock.write(f"{run_id}\n".encode()); lock.flush(); os.fsync(lock.fileno())
        return _launch_owned(exe, args, app, env, log_path, duration, project_id, build_id, profile_id, run_id, receipt_path, mode, started, sandbox_info, expected_owner_sha256)


def _launch_owned(exe, args, app, env, log_path, duration, project_id, build_id, profile_id, run_id, receipt_path, mode, started, sandbox_info, expected_owner_sha256):
    try:
        return _launch_process(exe,args,app,env,log_path,duration,project_id,build_id,profile_id,run_id,receipt_path,mode,started,sandbox_info,expected_owner_sha256)
    except BaseException as error:
        try:error.qa_failure_receipt=str(receipt_path)
        except Exception:pass
        raise


def _launch_process(exe, args, app, env, log_path, duration, project_id, build_id, profile_id, run_id, receipt_path, mode, started, sandbox_info, expected_owner_sha256):
    record_base = {"schemaVersion": 1, "contract": "beaver-unity-qa-process/1", "runId": run_id, "projectId": project_id, "buildId": build_id, "profileId": profile_id, "expectedOwnerSha256": expected_owner_sha256, "executablePath": str(exe), "executableSha256": digest_file(exe), "command": args, "cwd": str(app), "cleanEnvironment": env, "startedUtc": started, "budgetSeconds": duration, "logPath": str(log_path), "mode": mode, "documentsSandbox": sandbox_info}
    _write_control_json(receipt_path, {**record_base, "pid": None, "owned": False, "status": "starting"}, create=True)
    console_path=_guard_root(log_path.with_name(run_id+'.console.log'))
    record_base['consoleLogPath']=str(console_path)
    # Unity owns -logFile; redirect stdout to another file, never the same inode.
    fd=os.open(log_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);os.close(fd)
    with os.fdopen(os.open(console_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as log:
        try: process = subprocess.Popen(args, cwd=app, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as error:
            _write_control_json(receipt_path, {**record_base, "pid": None, "owned": False, "status": "failed", "launchError": type(error).__name__})
            fail("QA_LAUNCH_FAILED", str(exe), f"Owned GUI launch failed ({type(error).__name__}); process receipt retained")
        process_record = {**record_base, "pid": process.pid, "owned": True, "pidIdentity": _pid_identity_snapshot(process.pid, exe, log_path), "status": "running"}
        _write_control_json(receipt_path, process_record)
        try:
            code = process.wait(timeout=duration); status = "exited"
        except subprocess.TimeoutExpired:
            status = "stopped_by_budget"
            process.terminate()
            try: code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                sandbox_info.update(launchCompleted=True, enforcementIndependentlyVerified=False)
                process_record.update(status="recovery_required", stoppedByBudget=True, exitCode=None, documentsSandbox=sandbox_info)
                _write_control_json(receipt_path, process_record)
                fail("QA_STOP_TIMEOUT", str(process.pid), "Owned process did not stop after graceful terminate; it remains recorded and was not killed")
        except BaseException:
            process.terminate()
            try:
                code = process.wait(timeout=10)
                sandbox_info.update(launchCompleted=True, enforcementIndependentlyVerified=False)
                process_record.update(status="interrupted", exitCode=code, exitedUtc=datetime.now(timezone.utc).isoformat(), documentsSandbox=sandbox_info)
            except subprocess.TimeoutExpired:
                sandbox_info.update(launchCompleted=True, enforcementIndependentlyVerified=False)
                process_record.update(status="recovery_required", exitCode=None, documentsSandbox=sandbox_info)
            _write_control_json(receipt_path, process_record)
            raise
    sandbox_info.update(launchCompleted=True, enforcementIndependentlyVerified=False)
    process_record.update(status=("failed" if code != 0 else status), exitCode=code, exitedUtc=datetime.now(timezone.utc).isoformat(), stoppedByBudget=(status == "stopped_by_budget"), documentsSandbox=sandbox_info)
    _write_control_json(receipt_path, process_record)
    return {"status": process_record["status"], "runId": run_id, "pid": process.pid, "exitCode": code, "stoppedByBudget": status == "stopped_by_budget", "logPath": str(log_path), "processRecord": str(receipt_path), "report": process_record, "runtimeFileAccessEvidence": "not measured; no syscall tracing performed"}


def collect(project_id, build_id, profile_id, expected_owner_sha256, run_id=None, out=None):
    build_root, profile_root, owner = _read_owner(project_id, build_id, profile_id, expected_owner_sha256)
    app = build_root / "App.app"; bundle_actual = _hash_tree(app)
    if run_id is None: fail("QA_RUN_REQUIRED", "runId", "Collect requires an explicit runId")
    run_id = _id(run_id, "runId")
    data_root = build_root.parent.parent / "data"
    process_path = _guard_root(data_root / "runs" / (run_id + ".json"))
    process = _read_control_json(process_path, 128 * 1024) if process_path.is_file() else None
    if (not isinstance(process, dict) or process.get("runId") != run_id
            or (process.get("projectId"), process.get("buildId"), process.get("profileId")) != (project_id, build_id, profile_id)):
        fail("QA_RUN_MISSING", str(run_id), "No recorded launch matches the explicit runId")
    log_path = _guard_root(process.get("logPath", ""))
    expected_log = data_root / "logs" / profile_id / (run_id + ".log")
    if log_path != expected_log or not log_path.is_file(): fail("QA_RUN_LOG", str(log_path), "Run log must be the exact controlled path for this profile/run")
    logs = [{"path": str(log_path), "sha256": digest_file(log_path), "bytes": log_path.stat().st_size}]
    console_path=_guard_root(process.get('consoleLogPath',''))
    if console_path!=expected_log.with_name(run_id+'.console.log') or not console_path.is_file():
        fail('QA_RUN_LOG',str(console_path),'Console log must match this exact owned run')
    logs.append(dict(path=str(console_path),sha256=digest_file(console_path),bytes=console_path.stat().st_size))
    bundle_matches = bundle_actual == owner.get("bundle", {}).get("treeSha256")
    if process.get("status") == "running":
        executable_name = plistlib.loads(read(build_root / "App.app" / "Contents" / "Info.plist")).get("CFBundleExecutable")
        executable_path = build_root / "App.app" / "Contents" / "MacOS" / executable_name
        process["presence"] = _verify_running_process(process, executable_path, log_path)
    if not bundle_matches or process.get("status") == "failed": overall_status = "failed"
    elif process.get("status") == "recovery_required" or process.get("status") == "interrupted" or process.get("presence") == "identity_unknown": overall_status = "recovery_required"
    elif process.get("status") == "stopped_by_budget": overall_status = "stopped_by_budget"
    elif process.get("status") == "running" and process.get("presence") == "verified-running": overall_status = "observed_running"
    elif process.get("status") == "exited" and process.get("exitCode") == 0: overall_status = "collected"
    else: overall_status = "failed"
    report = {"schemaVersion": 1, "contract": "beaver-unity-qa-collect/1", "status": overall_status, "runId": run_id, "projectId": project_id, "buildId": build_id, "profileId": profile_id, "ownerSha256": expected_owner_sha256, "sourceSha256": owner.get("sourceSha256"), "artifactManifestSha256": owner.get("artifactManifestSha256"), "bundle": {"expectedTreeSha256": owner.get("bundle", {}).get("treeSha256"), "actualTreeSha256": bundle_actual, "matches": bundle_matches}, "profileRoot": str(profile_root), "process": process, "logs": logs, "runtimeFileAccessEvidence": "not measured; logs do not establish syscall-level access", "profileIsolation": "only explicitly declared profile-directory environment bindings; HOME, Unity persistentDataPath, PlayerPrefs and ordinary AppData are not redirected", "limitations": ["A successful process exit does not prove menu, gameplay, or save-resume behavior", "A clean run may not reveal existing TCC grants unless denyDocuments mode is used; denial is evidence only for paths covered by that closed profile", "The application must actually consume the declared profile binding before profile isolation can be credited"]}
    if out is None: out_path = data_root / "receipts" / ("collect-" + run_id + ".json")
    else:
        out_dir = safe(out)
        if out_dir.exists(): fail("QA_OUTPUT_EXISTS", str(out_dir), "Report output directory must be fresh")
        out_dir.mkdir(parents=True, exist_ok=False)
        out_path = out_dir / "qa-collect.json"
    _guard_root(out_path)
    if os.path.lexists(out_path): fail("QA_OUTPUT_EXISTS", str(out_path), "Collection report path already exists")
    report["report"] = str(out_path)
    _write_control_json(out_path, report, create=True)
    return report


def _verify_running_process(process, executable, log_path):
    pid = process.get("pid")
    if type(pid) is not int or pid <= 0: return "identity_unknown"
    expected_exe = str(executable)
    baseline = process.get("pidIdentity", {})
    current = _pid_identity_snapshot(pid, executable, log_path)
    if (current.get("status") == "verified" and baseline.get("status") == "verified"
            and current.get("executablePath") == baseline.get("executablePath") == expected_exe
            and current.get("startTime") == baseline.get("startTime")
            and current.get("logArgumentMatched") and baseline.get("logArgumentMatched")):
        return "verified-running"
    return "identity_unknown"


def _pid_identity_snapshot(pid, executable, log_path):
    result = {"status": "identity_unknown", "executablePath": None, "startTime": None, "logArgumentMatched": False}
    if os.uname().sysname != "Darwin": return result
    try:
        library = ctypes.CDLL("/usr/lib/libproc.dylib")
        function = library.proc_pidpath
        function.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        function.restype = ctypes.c_int
        buffer = ctypes.create_string_buffer(4096)
        count = function(pid, buffer, len(buffer))
        if count <= 0: return result
        actual_executable = os.fsdecode(buffer.value)
        start = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "lstart="], capture_output=True, text=True, timeout=5)
        command = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True, timeout=5)
        if start.returncode or command.returncode: return result
        start_time = start.stdout.strip()
        log_argument = f"-logFile {log_path}"
        matched = log_argument in command.stdout.strip()
        result.update(executablePath=actual_executable, startTime=start_time, logArgumentMatched=matched)
        if actual_executable == str(executable) and start_time and matched: result["status"] = "verified"
        return result
    except (OSError, AttributeError, subprocess.TimeoutExpired):
        return result
