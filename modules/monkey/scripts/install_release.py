#!/usr/bin/env python3
"""Install a SHA-pinned release wheel and atomically select one user CLI."""
import argparse
import email
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import venv
import zipfile


def install(wheel, digest, prefix, bin_dir):
    wheel = wheel.resolve(strict=True)
    if not re.fullmatch(r'[0-9a-f]{64}', digest) or hashlib.sha256(wheel.read_bytes()).hexdigest() != digest:
        raise ValueError('Release wheel SHA256 mismatch')
    with zipfile.ZipFile(wheel) as archive:
        metadata = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
        if len(metadata) != 1:
            raise ValueError('Expected one wheel distribution')
        meta = email.message_from_bytes(archive.read(metadata[0]))
    version = meta['Version']
    if meta['Name'] != 'monkey-native' or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:\.dev[0-9]+)?', version or ''):
        raise ValueError('Expected a versioned monkey-native wheel')
    prefix, bin_dir = prefix.absolute(), bin_dir.absolute()
    prefix.mkdir(parents=True, exist_ok=True)
    lock = prefix / '.install.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        current = prefix / 'current'
        entry = bin_dir / 'monkey'
        target = current / 'bin/monkey'
        if current.exists() and not current.is_symlink():
            raise ValueError('Refusing to replace an unmanaged current directory')
        if os.path.lexists(entry) and (not entry.is_symlink() or os.readlink(entry) != str(target)):
            raise ValueError('Refusing to replace an unmanaged monkey command')
        release = prefix / 'releases' / version
        receipt = release / 'release-install.json'
        identity = dict(version=version, wheel=wheel.name, sha256=digest)
        if release.exists():
            if not receipt.is_file() or json.loads(receipt.read_text()) != identity:
                raise ValueError('Existing version has a different or incomplete installation; inspect it before retrying')
        else:
            venv.EnvBuilder(with_pip=True).create(release)
            subprocess.run([str(release / 'bin/python'), '-I', '-m', 'pip', 'install',
                            '--index-url', 'https://pypi.org/simple', str(wheel) + '[astc]'], check=True)
            receipt.write_text(json.dumps(identity, indent=2) + '\n')
        python = str(release / 'bin/python')
        subprocess.run([python, '-I', '-m', 'pip', 'check'], check=True)
        subprocess.run([python, '-I', '-c',
                        'import monkey,sys; from pathlib import Path; '
                        'assert monkey.__version__ == sys.argv[1]; '
                        'assert Path(monkey.__file__).is_relative_to(Path(sys.prefix)); '
                        'print(monkey.__file__)', version], check=True)
        subprocess.run([str(release / 'bin/monkey'), '--version'], check=True)
        # Old version directories remain available; selection changes only after verification.
        temp = prefix / ('.current-' + str(os.getpid()))
        temp.symlink_to(release, target_is_directory=True)
        os.replace(temp, current)
        bin_dir.mkdir(parents=True, exist_ok=True)
        if not os.path.lexists(entry):
            entry.symlink_to(target)
        print(json.dumps(dict(identity, command=str(entry), environment=str(release))))
    finally:
        lock.unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--prefix', type=Path, default=Path.home() / '.local/share/monkey')
    parser.add_argument('--bin-dir', type=Path, default=Path.home() / '.local/bin')
    args = parser.parse_args()
    install(args.wheel, args.sha256, args.prefix, args.bin_dir)
