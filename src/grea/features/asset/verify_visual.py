"""Verify persistent types and references of an explicitly listed native visual subset."""
import json
import os
import subprocess
from pathlib import Path

from grea.development.io import safe, new_output


def verify(args):
    project, editor, paths = safe(args.project), safe(args.unity_editor), safe(args.paths)
    if not (project / 'ProjectSettings/ProjectVersion.txt').is_file() or not editor.is_file():
        raise ValueError('Installed Unity Editor and project required')
    if (project / 'Temp/UnityLockfile').exists():
        raise ValueError('Close the project before native visual verification')
    if not 30 <= args.budget_seconds <= 7200:
        raise ValueError('Native Editor budget must be 30..7200 seconds')
    selected = paths.read_text(encoding='utf-8').splitlines()
    if not selected or len(selected) != len(set(selected)):
        raise ValueError('A nonempty unique asset path list is required')
    for path in selected:
        target = (project / path).resolve()
        if not path.startswith('Assets/') or not target.is_relative_to(project / 'Assets') or not target.is_file():
            raise ValueError(f'Invalid native asset path: {path}')
    out = new_output(args.output, [project, editor, paths])
    (out / 'new-paths.txt').write_text('\n'.join(selected) + '\n', encoding='utf-8')
    probe = project / 'Assets/Game/Editor/Validators/GreaVisualAssetReadback.cs'
    source = Path(__file__).with_name('VisualAssetReadback.cs.txt').read_bytes().replace(
        b'namespace Grea.VisualRecovery {', b'namespace Grea.VisualReadbackProbe {')
    if probe.exists() or Path(str(probe) + '.meta').exists():
        raise ValueError('Temporary visual probe path is occupied')
    created = []
    parent = probe.parent
    while not parent.exists():
        if Path(str(parent) + '.meta').exists():
            raise ValueError('Orphan folder metadata occupies temporary probe path')
        created.append(parent)
        parent = parent.parent
    owned = False
    try:
        for folder in reversed(created):
            folder.mkdir()
        with probe.open('xb') as stream:
            stream.write(source)
        owned = True
        report = out / 'native.tsv'
        run = subprocess.run([str(editor), '-batchmode', '-nographics', '-quit', '-projectPath', str(project),
                              '-executeMethod', 'Grea.VisualReadbackProbe.AssetReadback.Inspect',
                              '-logFile', str(out / 'unity.log')],
                             env=dict(os.environ, GREA_VISUAL_RUN=str(out), GREA_VISUAL_PHASE='read',
                                      GREA_VISUAL_REPORT=report.name), timeout=args.budget_seconds)
        if run.returncode:
            raise ValueError(f'Unity exited {run.returncode}; inspect {out / "unity.log"}')
        rows = [line.split('\t') for line in report.read_text().splitlines()]
        if [row[0] for row in rows] != selected or any(len(row) != 7 for row in rows):
            raise ValueError('Incomplete or malformed native readback')
        errors = [{'path': row[0], 'error': row[-1]} for row in rows if row[-1]]
        result = dict(status='partial' if errors else 'ok', assets=len(rows), errors=errors,
                      nativeReadback='visual-assets-and-references', report=str(report),
                      objectIdentities=str(out / 'object-identities.tsv'),
                      objectFingerprints=str(out / 'object-fingerprints.tsv'),
                      editorCacheReferences=str(out / 'editor-cache.tsv'), fingerprintVersion=2,
                      verificationScope='Persistent identity and references; not visual or gameplay equivalence')
        (out / 'result.json').write_text(json.dumps(result, indent=2))
        return result
    except subprocess.TimeoutExpired as error:
        raise ValueError(f'Unity readback timed out; inspect {out / "unity.log"}') from error
    finally:
        if owned and probe.exists() and probe.read_bytes() == source:
            probe.unlink()
            Path(str(probe) + '.meta').unlink(missing_ok=True)
        for folder in created:
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
                Path(str(folder) + '.meta').unlink(missing_ok=True)
