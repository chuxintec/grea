import json
from pathlib import Path

import pytest

from monkey.io import sha
from monkey.sources.compiled import ParseError
from monkey import native_selection as selection


def _put(root, path, data):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data if isinstance(data, bytes) else data.encode())
    return target.read_bytes()


def _fixture(tmp_path, monkeypatch):
    root = tmp_path / "candidate"
    root.mkdir()
    script_names = set(selection._CURRENT_TEMPLATE_DEPENDENCIES)
    script_names.update(profile[0] for profile in selection._LEGACY_TEMPLATE_PROFILES.values())
    paths = [
        "Assets/Selected.prefab", "Assets/Selected.prefab.meta",
        "Assets/Game.meta", "Packages/manifest.json", "Packages/packages-lock.json",
        "ProjectSettings/ProjectVersion.txt",
    ] + [f"Assets/Scripts/{name}" for name in sorted(script_names)]
    guid = 1
    for path in list(paths):
        if path.startswith("Assets/") and (path.endswith(".prefab") or path.endswith(".cs")):
            meta = path + ".meta"
            paths.append(meta)
    paths = list(dict.fromkeys(paths))
    rows = []
    guid_by_path = {}
    for path in paths:
        if path.endswith(".meta"):
            value = f"{guid:032x}"
            guid += 1
            data = f"fileFormatVersion: 2\nguid: {value}\n".encode()
            guid_by_path[path[:-5]] = value
        elif path == "Assets/Selected.prefab":
            data = (f"--- !u!114 &1\nMonoBehaviour:\n  m_Script: {{fileID: 11500000, guid: {guid_by_path.get('Assets/Scripts/NativeStaticSortQueueProxyPresenter.cs', 'f'*32)}, type: 3}}\n").encode()
        elif path == "Packages/manifest.json":
            data = b'{"dependencies":{"com.unity.ugui":"2.0.0"}}\n'
        elif path == "Packages/packages-lock.json":
            data = b'{"dependencies":{"com.unity.ugui":{"version":"2.0.0"}}}\n'
        elif path == "ProjectSettings/ProjectVersion.txt":
            data = b"m_EditorVersion: 6000.6.2f1\n"
        elif path.endswith(".cs"):
            data = (Path(__file__).parents[1] / "src/monkey/targets" / Path(path).name).read_bytes()
        else:
            data = b""
        _put(root, path, data)
        rows.append(dict(path=path, sha256=sha(data), bytes=len(data), owner="generated"))
    # Put the script reference GUID into the prefab now that meta GUIDs exist.
    presenter_path = "Assets/Scripts/NativeStaticSortQueueProxyPresenter.cs"
    prefab = (f"--- !u!114 &1\nMonoBehaviour:\n  m_Script: {{fileID: 11500000, guid: {guid_by_path[presenter_path]}, type: 3}}\n").encode()
    _put(root, "Assets/Selected.prefab", prefab)
    for row in rows:
        if row["path"] == "Assets/Selected.prefab":
            row.update(sha256=sha(prefab), bytes=len(prefab))
    manifest = dict(schemaVersion=1, targetProfile="unity-6000.6.2f1-ugui", namespace="fixture", files=rows)
    manifest_raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    _put(root, "manifest.json", manifest_raw)
    native_rows = []
    for path in ("Assets/Selected.prefab", "Assets/Selected.prefab.meta"):
        data = (root / path).read_bytes()
        native_rows.append(dict(path=path, sha256=sha(data)))
    rb = dict(unityVersion="6000.6.2f1", status="partial", missingScripts=0,
              nativeScope="saved-source-node-subset", sourceGraphVerification="saved-source-node-subset",
              editableRoundtrip=True, sceneReopened=True, nativeFiles=native_rows)
    rb_raw = json.dumps(rb).encode()
    _put(root, "Analysis/Readback/editor-readback.json", rb_raw)
    verify = dict(candidateManifestSha256=sha(manifest_raw), staticValidation="pass",
                  nativeStaticValidation="pass", editorValidation="partial", diagnostics=[])
    monkeypatch.setattr(selection, "_native_verification", lambda *args: (rb, rb_raw, verify))
    return root, sha(manifest_raw), sha(rb_raw)


def test_freeze_copies_selected_prefab_and_declared_code_closure(tmp_path, monkeypatch):
    root, manifest_sha, readback_sha = _fixture(tmp_path, monkeypatch)
    output = tmp_path / "frozen"
    result = selection.freeze(root, ["Assets/Selected.prefab"], output, manifest_sha, readback_sha)
    assert result["selection"]["prefabs"] == ["Assets/Selected.prefab"]
    assert result["adoptionDependencies"]["schemaVersion"] == 1
    assert result["adoptionDependencies"]["coverage"] == "producer-declared"
    assert (output / "Assets/Selected.prefab").read_bytes() == (root / "Assets/Selected.prefab").read_bytes()
    assert all((output / row["path"]).is_file() for row in result["files"])
    assert not (output / "Analysis/Readback/editor-readback.json").exists()


def test_freeze_rejects_unresolved_guid(tmp_path, monkeypatch):
    root, manifest_sha, readback_sha = _fixture(tmp_path, monkeypatch)
    path = root / "Assets/Selected.prefab"
    path.write_text("--- !u!114 &1\nMonoBehaviour:\n  reference: {fileID: 1, guid: " + "f" * 32 + ", type: 3}\n")
    manifest = json.loads((root / "manifest.json").read_text())
    data = path.read_bytes()
    row = next(x for x in manifest["files"] if x["path"] == "Assets/Selected.prefab")
    row.update(sha256=sha(data), bytes=len(data))
    raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    _put(root, "manifest.json", raw)
    rb = json.loads((root / "Analysis/Readback/editor-readback.json").read_text())
    rb["nativeFiles"][0]["sha256"] = sha(data)
    rb_raw = json.dumps(rb).encode()
    _put(root, "Analysis/Readback/editor-readback.json", rb_raw)
    monkeypatch.setattr(selection, "_native_verification", lambda *args: (rb, rb_raw, dict(
        candidateManifestSha256=sha(raw), staticValidation="pass", nativeStaticValidation="pass",
        editorValidation="partial", diagnostics=[])))
    with pytest.raises(ParseError, match="UNRESOLVED_GUID"):
        selection.freeze(root, ["Assets/Selected.prefab"], tmp_path / "out", sha(raw), sha(rb_raw))


def test_freeze_rejects_manifest_sha_drift(tmp_path, monkeypatch):
    root, _, readback_sha = _fixture(tmp_path, monkeypatch)
    with pytest.raises(ParseError, match="CANDIDATE_SHA_MISMATCH"):
        selection.freeze(root, ["Assets/Selected.prefab"], tmp_path / "out", "0" * 64, readback_sha)


def test_freeze_rejects_missing_declared_template_dependency(tmp_path, monkeypatch):
    root, manifest_sha, readback_sha = _fixture(tmp_path, monkeypatch)
    manifest = json.loads((root / "manifest.json").read_text())
    removed = "Assets/Scripts/NativeInputBlocker.cs"
    manifest["files"] = [row for row in manifest["files"] if row["path"] not in (removed, removed + ".meta")]
    (root / removed).unlink()
    (root / (removed + ".meta")).unlink()
    raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    _put(root, "manifest.json", raw)
    rb = json.loads((root / "Analysis/Readback/editor-readback.json").read_text())
    rb_raw = json.dumps(rb).encode()
    _put(root, "Analysis/Readback/editor-readback.json", rb_raw)
    monkeypatch.setattr(selection, "_native_verification", lambda *args: (rb, rb_raw, dict(
        candidateManifestSha256=sha(raw), staticValidation="pass", nativeStaticValidation="pass",
        editorValidation="partial", diagnostics=[])))
    with pytest.raises(ParseError, match="DECLARED_CODE_DEPENDENCY_MISSING"):
        selection.freeze(root, ["Assets/Selected.prefab"], tmp_path / "out", sha(raw), sha(rb_raw))


def test_freeze_registers_unowned_package_lock_as_exact_supplemental_authority(tmp_path, monkeypatch):
    root, _, readback_sha = _fixture(tmp_path, monkeypatch)
    manifest = json.loads((root / "manifest.json").read_text())
    lock_path = "Packages/packages-lock.json"
    manifest["files"] = [row for row in manifest["files"] if row["path"] != lock_path]
    raw = (json.dumps(manifest, sort_keys=True) + "\n").encode()
    _put(root, "manifest.json", raw)
    rb = json.loads((root / "Analysis/Readback/editor-readback.json").read_text())
    rb_raw = json.dumps(rb).encode()
    _put(root, "Analysis/Readback/editor-readback.json", rb_raw)
    monkeypatch.setattr(selection, "_native_verification", lambda *args: (rb, rb_raw, dict(
        candidateManifestSha256=sha(raw), staticValidation="pass", nativeStaticValidation="pass",
        editorValidation="partial", diagnostics=[])))
    output = tmp_path / "out"
    result = selection.freeze(root, ["Assets/Selected.prefab"], output, sha(raw), sha(rb_raw))
    authority = result["supplementalFileAuthorities"][lock_path]
    file_row = next(row for row in result["files"] if row["path"] == lock_path)
    assert authority["authority"] == "package-lock"
    assert file_row["owner"] == "retained"
    assert file_row["sha256"] == sha((root / lock_path).read_bytes())


def test_freeze_records_normalized_unity_editor_revision(tmp_path, monkeypatch):
    root, manifest_sha, _ = _fixture(tmp_path, monkeypatch)
    path = "ProjectSettings/ProjectVersion.txt"
    saved = b"m_EditorVersion: 6000.6.2f1\nm_EditorVersionWithRevision: 6000.6.2f1 (0123456789ab)\n"
    _put(root, path, saved)
    rb = json.loads((root / "Analysis/Readback/editor-readback.json").read_text())
    rb_raw = json.dumps(rb).encode()
    _put(root, "Analysis/Readback/editor-readback.json", rb_raw)
    monkeypatch.setattr(selection, "_native_verification", lambda *args: (rb, rb_raw, dict(
        candidateManifestSha256=manifest_sha, staticValidation="pass", nativeStaticValidation="pass",
        editorValidation="partial", diagnostics=[])))
    result = selection.freeze(root, ["Assets/Selected.prefab"], tmp_path / "out", manifest_sha, sha(rb_raw))
    record = next(row for row in result["normalizedNativeFiles"] if row["path"] == path)
    copied = next(row for row in result["files"] if row["path"] == path)
    assert record["savedSha256"] == sha(saved)
    assert copied["sha256"] == sha(saved)
