"""Host-native absolute paths for contract-only fixtures; creates no files."""
from pathlib import Path


def fixture_path(name=''):
    return str(Path(__file__).resolve().parent / 'synthetic-fixture' / name)
