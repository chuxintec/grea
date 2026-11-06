"""Run the engineering provider shipped with monkey, including source checkouts."""
import sys
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
    source = provider_root / "beaver" / "cli.py"
    if not source.is_file():
        raise RuntimeError("The monkey installation is missing its bundled engineering provider")
    if str(provider_root) not in sys.path[:1]:
        sys.path.insert(0, str(provider_root))
    from beaver import cli
    if Path(cli.__file__).resolve() != source.resolve():
        raise RuntimeError("A different engineering provider is already loaded")
    return cli.main(argv, prog="monkey develop", producer="monkey", version=__version__)
