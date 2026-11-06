"""Read native types and direct references with a temporary, owned Editor probe."""
import os
import subprocess
from pathlib import Path

from grea.development.io import new_output, safe
from .recovered_layout import inventory


def collect(args):
    project, editor = safe(args.project), safe(args.unity_editor)
    if not (project/'ProjectSettings/ProjectVersion.txt').is_file() or not editor.is_file():
        raise ValueError('Installed Unity Editor and project required')
    if not 30 <= args.budget_seconds <= 7200:
        raise ValueError('Native Editor budget must be 30..7200 seconds')
    if (project/'Temp/UnityLockfile').exists():
        raise ValueError('Close the project before native inventory collection')
    probe = safe(project/'Assets/Game/Editor/Validators/GreaLayoutInventoryProbe.cs')
    template = Path(__file__).with_name('RecoveredAssetInventory.cs.txt').read_bytes()
    out = new_output(args.output, [project, editor])
    directories = []
    parent = probe.parent
    while not parent.exists():
        directories.append(parent)
        parent = parent.parent
    if probe.exists() or Path(str(probe)+'.meta').exists() or any(Path(str(p)+'.meta').exists() for p in directories):
        raise ValueError('Temporary inventory probe path is occupied')
    created = []
    owned_probe = False
    try:
        for folder in reversed(directories):
            folder.mkdir()
            created.append(folder)
        with probe.open('xb') as stream:
            owned_probe = True
            stream.write(template)
        path = out/'inventory.tsv'
        env = dict(os.environ, GREA_ASSET_INVENTORY=str(path),
                   GREA_LAYOUT_HELPER=probe.relative_to(project).as_posix())
        run = subprocess.run([str(editor), '-batchmode', '-nographics', '-quit', '-projectPath', str(project),
                        '-executeMethod', 'Grea.AssetLayout.Inventory.Run', '-logFile', str(out/'unity.log')],
                       env=env, timeout=args.budget_seconds)
        if run.returncode:
            raise ValueError(f"Unity exited {run.returncode}; inspect {out/'unity.log'}")
        count = len(inventory(path))
        return dict(assets=count, nativeReadback='asset-database', report=str(path))
    except subprocess.TimeoutExpired as error:
        raise ValueError(f"Unity inventory timed out; inspect {out/'unity.log'}") from error
    finally:
        if owned_probe and probe.exists() and probe.read_bytes() == template:
            probe.unlink()
            Path(str(probe)+'.meta').unlink(missing_ok=True)
        for folder in reversed(created):
            if folder.exists() and not any(folder.iterdir()):
                folder.rmdir()
                Path(str(folder)+'.meta').unlink(missing_ok=True)
