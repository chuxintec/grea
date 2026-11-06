"""Run the engineering provider shipped with monkey, including source checkouts."""
import sys
from importlib.util import find_spec
from pathlib import Path

from . import __version__


def main(argv):
    package_dir = Path(__file__).resolve().parent
    provider_root = package_dir.parent
    if provider_root.name == "src":
        checkout_provider = provider_root.parent / "engineering" / "src"
        if (checkout_provider / "beaver" / "cli.py").is_file():
            provider_root = checkout_provider

    # Editable checkouts use two source roots. Wheels install both as siblings.
    expected = provider_root / "beaver" / "__init__.py"
    if not expected.is_file():
        raise RuntimeError("The monkey installation is missing its bundled engineering provider")
    sys.path.insert(0, str(provider_root))
    try:
        spec = find_spec("beaver")
        if spec is None or spec.origin is None or Path(spec.origin).resolve() != expected.resolve():
            raise RuntimeError("A different engineering provider is already loaded")
        from beaver.cli import main as run_development
        return run_development(argv, prog="monkey develop", producer="monkey", version=__version__)
    finally:
        sys.path.remove(str(provider_root))
