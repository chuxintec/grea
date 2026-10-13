#!/usr/bin/env python3
"""Audit staged bytes, without printing secret values or reading ignored files."""
import argparse
import ipaddress
import json
import re
import subprocess
from pathlib import PurePosixPath


FORBIDDEN_PARTS = {'.private', '.git', '.venv', 'node_modules', '__pycache__',
                   '.cache', '.pytest_cache', 'snapshots', 'vendor', 'PackageCache'}
FORBIDDEN_SUFFIXES = {'.zip', '.tgz', '.gz', '.xz', '.dll', '.exe', '.dylib',
                      '.pdb', '.log', '.pyc', '.pfx', '.p12', '.key', '.keystore'}
RULES = {
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    'access_token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9_-]{30,})'),
    'credential_url': re.compile(r'https?://[^\s/:]+:[^\s/@]+@'),
    'local_home': re.compile(r'(?:/Users|/home)/[A-Za-z0-9._-]+/|[A-Za-z]:\\Users\\[A-Za-z0-9._-]+\\'),
    'application_identity': re.compile(r'\bwx[0-9a-f]{16}\b|\bproject-\d{2}\b'),
    'lfs_pointer': re.compile(r'^version https://git-lfs.github.com/spec/v1$', re.M),
}


def inspect(path, data, mode='100644'):
    """Return categories/line numbers, never matched bytes."""
    name = PurePosixPath(path)
    issues = []
    if mode in {'120000', '160000'}:
        issues.append({'code': 'symlink_or_submodule'})
    if (set(name.parts) & FORBIDDEN_PARTS or name.suffix.lower() in FORBIDDEN_SUFFIXES
            or name.name == '.env' or name.name.startswith('.env.') and name.name != '.env.example'):
        issues.append({'code': 'private_or_generated_path'})
    if len(data) > 2 * 1024 * 1024:
        issues.append({'code': 'oversized_source'})
    try:
        text = data.decode('utf-8')
        if '\0' in text:
            raise UnicodeError('binary')
    except UnicodeError:
        return issues + [{'code': 'binary_not_allowed'}]
    for code, pattern in RULES.items():
        for match in pattern.finditer(text):
            issues.append({'code': code, 'line': text.count('\n', 0, match.start()) + 1})
    # Only RFC1918 addresses, not version numbers or loopback examples.
    for match in re.finditer(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])', text):
        try:
            address = ipaddress.IPv4Address(match[0])
        except ipaddress.AddressValueError:
            continue
        if any(address in ipaddress.ip_network(n) for n in ((167772160, 8), (2886729728, 12), (3232235520, 16))):
            issues.append({'code': 'private_network', 'line': text.count('\n', 0, match.start()) + 1})
    return issues


def audit(root):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args])
    entries = git('ls-files', '--stage', '-z').split(b'\0')
    findings, total, size = [], 0, 0
    for entry in filter(None, entries):
        info, rawpath = entry.split(b'\t', 1)
        mode, oid, stage = info.decode().split()
        path = rawpath.decode('utf-8')
        if stage != '0':
            findings.append({'file': path, 'code': 'unmerged_index'})
            continue
        if mode == '160000':
            findings.append({'file': path, 'code': 'symlink_or_submodule'})
            continue
        data = git('cat-file', 'blob', oid)
        total += 1
        size += len(data)
        findings.extend(dict(file=path, **issue) for issue in inspect(path, data, mode))
    return {'ok': not findings, 'scope': 'Git index bytes', 'files': total,
            'bytes': size, 'findings': findings,
            'limits': 'Pattern-based source gate, not proof that every secret or license issue is absent.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    result = audit(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ok'] else 1)
