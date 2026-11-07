"""Pin engineering sources and the command boundaries that invoke them.

The versioned scope file travels with new runtimes. Historical runtimes without
it keep their original flat inventory, including their exact key spelling.
Reading an inventory never imports or executes the supplied runtime.
"""

from pathlib import Path

from .errors import fail
from .io import encoded, load, read, sha
from .output_limits import digest_file


SCOPE_FILE = "implementation-scope.json"
SCOPE = {"schemaVersion": 1, "areas": ["development", "features", "commands"]}


def inventory(runtime, *, require_scope=False):
    runtime = Path(runtime)
    scope = runtime / SCOPE_FILE
    if runtime.is_symlink() or scope.is_symlink():
        fail("SYMLINK_PATH", str(runtime), "Original runtime inventory cannot contain links")
    if scope.is_file():
        if load(read(scope, max_bytes=4096)) != SCOPE or runtime.name != "development":
            fail("IMPLEMENTATION_SCOPE", str(scope), "Unsupported implementation scope or runtime layout")
        root = runtime.parent
        areas = [root / name for name in SCOPE["areas"]]
        if any(not area.is_dir() for area in areas):
            fail("IMPLEMENTATION_SCOPE", str(root), "Complete development, features and commands runtime required")
    else:
        if require_scope:
            fail("IMPLEMENTATION_SCOPE", str(scope), "Current runtime scope declaration is missing")
        root, areas = runtime, [runtime]
    files = {}
    total = 0
    for area in areas:
        if area.is_symlink():
            fail("SYMLINK_PATH", str(area), "Original runtime inventory cannot contain links")
        for path in sorted(area.rglob("*")):
            if path.is_symlink():
                fail("SYMLINK_PATH", str(path), "Original runtime inventory cannot contain links")
            if not path.is_file() or "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo"):
                continue
            total += path.stat().st_size
            if len(files) >= 1024 or total > 64 * 1024 * 1024:
                fail("INTAKE_BINDING_RUNTIME_BUDGET", str(runtime), "Original runtime exceeds1024 files/64MiB")
            files[path.relative_to(root).as_posix()] = digest_file(path)
    return files


def identity():
    return sha(encoded(inventory(Path(__file__).parent, require_scope=True)))
