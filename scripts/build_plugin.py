#!/usr/bin/env python3
"""Build the complete macOS arm64 plugin. Downloads occur only at build time."""
import argparse
import base64
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.request

from plugin_bundle import encoded, extract_runtime, inventory, read_source, sha256, verify_archive, write_archive
from grea.brand_assets import validate_interface

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = 'grea-plugin-macos-arm64.zip'


def write_product(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    for name, (data, mode) in sorted(source.items()):
        # Preserve the audited public resource closure, including linked docs and fixtures.
        if name.endswith('.gitignore'): continue
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data); path.chmod(mode & 0o777)
    # Client manifests live at the installed package root; skills keep their source layout.
    for client in ('.codex-plugin', '.claude-plugin'):
        value = json.loads(source[f'plugin/{client}/plugin.json'][0])
        value['skills'] = './plugin/skills/'
        if client=='.codex-plugin':
            for key in ('composerIcon','logo','logoDark'):
                if key in value.get('interface',{}):
                    original=value['interface'][key]
                    if not original.startswith('./assets/'):raise ValueError('Unexpected source icon path')
                    value['interface'][key]='./plugin/'+original[2:]
            validate_interface(value,lambda path:(destination/path).read_bytes())
        path = destination / client / 'plugin.json'
        path.parent.mkdir(parents=True)
        path.write_bytes(encoded(value))
    (destination / '.mcp.json').write_bytes(source['plugin/.mcp.json'][0])
    marketplace = destination/'.agents/plugins/marketplace.json'
    marketplace.parent.mkdir(parents=True)
    marketplace.write_bytes(encoded({'name':'grea-local','description':'Portable grea skills and local MCP runtime.','plugins':[{
        'name':'grea','source':{'source':'local','path':'./'},
        'policy':{'installation':'AVAILABLE','authentication':'ON_USE'},'category':'Developer Tools'}]}))
    (destination/'.claude-plugin/marketplace.json').write_bytes(encoded({
        'name':'grea-local','description':'Portable grea skills and local MCP runtime.',
        'owner':{'name':'grea contributors'},'plugins':[{'name':'grea','source':'./'}]}))
    required = ['registry.json', 'launch.py', 'launch_tool.py', 'src/grea/cli.py',
                'plugin/version.json', 'plugin/launcher/grea', 'plugin/launcher/start.py',
                'schemas/operations.json', 'schemas/unity-project.schema.json']
    for name in required:
        if not (destination/name).is_file(): raise ValueError('Missing product resource: ' + name)


def download_python(lock, cache):
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / (lock['sha256'] + ('.tar.zst' if lock['url'].endswith('.tar.zst') else '.tar.gz'))
    if archive.is_file():
        if sha256(archive) != lock['sha256']: raise ValueError('Cached Python checksum mismatch')
        return archive
    with tempfile.NamedTemporaryFile(dir=cache, suffix='.download', delete=False) as output:
        temporary = Path(output.name)
        try:
            request = urllib.request.Request(lock['url'], headers={'User-Agent': 'grea-plugin-builder'})
            with urllib.request.urlopen(request, timeout=60) as response:
                shutil.copyfileobj(response, output)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    if temporary.stat().st_size != lock['bytes'] or sha256(temporary) != lock['sha256']:
        temporary.unlink()
        raise ValueError('Downloaded Python identity mismatch')
    temporary.replace(archive)
    return archive


def install_dependencies(tree, cache, lock):
    upstream_files = inventory(tree/'runtime')
    uv = shutil.which('uv')
    if not uv: raise ValueError('Building requires uv; installing/using the artifact does not')
    uv_version = subprocess.check_output([uv, '--version'], text=True).split()[1]
    if uv_version != lock['buildUvVersion']:
        raise ValueError('Use the locked build uv version: ' + lock['buildUvVersion'])
    env = dict(os.environ, UV_CACHE_DIR=str(cache/'uv'), UV_NO_PROGRESS='1', UV_PYTHON_DOWNLOADS='never')
    for key in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV'):
        env.pop(key, None)
    command = [uv, 'export', '--project', str(tree), '--frozen', '--no-header', '--no-dev', '--no-editable',
               '--no-emit-project', '--format', 'requirements-txt']
    requirements = subprocess.check_output(command, env=env)
    (tree/'runtime-requirements.txt').write_bytes(requirements)
    python = tree/'runtime/bin/python3'
    site = tree/f"runtime/lib/python{lock['pythonMinor']}/site-packages"
    subprocess.run([uv, 'pip', 'install', '--python', str(python), '--target', str(site),
                    '--require-hashes', '--only-binary', ':all:', '--no-deps',
                    '-r', str(tree/'runtime-requirements.txt')], env=env, check=True, stdout=sys.stderr)
    # Console wrappers embed build paths. grea uses modules and the bundled interpreter.
    shutil.rmtree(site/'bin', ignore_errors=True)
    for path in sorted((tree/'runtime').rglob('*'), reverse=True):
        if path.is_file() and (path.suffix == '.pyc' or path.name == 'uv_cache.json'):
            path.unlink()
        elif path.is_dir() and path.name == '__pycache__':
            shutil.rmtree(path)
    for path in (tree/'runtime/bin').iterdir():
        if path.name not in ('python3', 'python' + lock['pythonMinor']):
            if path.is_dir(): shutil.rmtree(path)
            else: path.unlink()
    normalization = normalize_records(site, tree/'runtime', upstream_files=upstream_files)
    packages = sorted([{'name': d.metadata['Name'], 'version': d.version,
                         'license': d.metadata.get('License-Expression') or (d.metadata.get('License') or 'See bundled license files')[:200]}
                        for d in importlib.metadata.distributions(path=[str(site)])], key=lambda x: x['name'].lower())
    return packages, normalization


def normalize_records(site, runtime, upstream_files=None):
    """Keep installed RECORDs truthful after pruning nonportable generated files."""
    site, runtime = Path(site).resolve(), Path(runtime).resolve()
    upstream_files = upstream_files or {}
    preserved = []
    for record in sorted(site.glob('*.dist-info/RECORD')):
        with record.open(newline='') as stream:
            rows = list(csv.reader(stream))
        kept = []
        for row in rows:
            if len(row) != 3: raise ValueError('Invalid wheel RECORD')
            name, checksum, size = row
            path = (site/name).resolve()
            if runtime not in path.parents: raise ValueError('Wheel RECORD escapes runtime')
            if not path.is_file():
                pruned = (site/'bin' in path.parents or runtime/'bin' in path.parents
                          or '__pycache__' in path.parts or path.name == 'uv_cache.json')
                if not pruned: raise ValueError('Missing installed dependency file: ' + name)
                continue
            if checksum:
                algorithm, wanted = checksum.split('=', 1)
                actual = base64.urlsafe_b64encode(hashlib.new(algorithm, path.read_bytes()).digest()).rstrip(b'=').decode()
                if actual != wanted or (size and path.stat().st_size != int(size)):
                    relative = path.relative_to(runtime).as_posix()
                    original = upstream_files.get(relative)
                    if not original or (sha256(path), path.stat().st_size) != (original['sha256'], original['bytes']):
                        raise ValueError('Installed dependency differs from its RECORD: ' + name)
                    preserved.append({'file':relative,'sha256':original['sha256'],
                                      'reason':'Original stripped CPython archive bytes are unchanged; upstream wheel RECORD predates stripping.'})
            kept.append(row)
        with record.open('w', newline='') as stream:
            csv.writer(stream, lineterminator='\n').writerows(sorted(kept))
    return preserved


def build(out, *, worktree=False, cache=None, tag=None):
    if (platform.system(), platform.machine()) != ('Darwin', 'arm64'):
        raise ValueError('Build and acceptance currently require native macOS arm64')
    out = Path(out).resolve()
    if out.exists(): raise FileExistsError(out)
    source, identity = read_source(ROOT, worktree)
    project = tomllib.loads(source['pyproject.toml'][0].decode())['project']
    version = project['version']
    metadata = json.loads(source['plugin/version.json'][0])
    if metadata['version'] != version or metadata['greaVersion'] != version:
        raise ValueError('Plugin and product versions differ')
    for client in ('.codex-plugin', '.claude-plugin'):
        if json.loads(source[f'plugin/{client}/plugin.json'][0])['version'] != version:
            raise ValueError('Client manifest version differs')
    if tag:
        from release import version as parse_version
        if parse_version(tag)[0] != version: raise ValueError('Release tag version differs')
    lock = json.loads(source['plugin/runtime-lock.json'][0])
    cache = Path(cache or ROOT/'.cache/plugin-runtime').resolve()
    archive = download_python(lock, cache)
    license_archive = download_python(lock['licenseArchive'], cache)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='grea-plugin-build-', dir=out.parent) as temporary:
        tree = Path(temporary)/'grea'
        write_product(source, tree)
        extract_runtime(archive, tree/'runtime', lock['sha256'])
        from runtime_licenses import install_licenses
        licenses = install_licenses(license_archive, tree/'runtime', lock)
        packages, normalization = install_dependencies(tree, cache, lock)
        subprocess.run([str(tree/'runtime/bin/python3'), '-I', '-B', str(tree/'launch_tool.py'),
                        'check_skill', '--workspace-root', str(tree), '--json'],
                       cwd=tree, check=True, stdout=sys.stderr)
        observed = subprocess.check_output([str(tree/'runtime/bin/python3'), '-I', '-B', '-c',
                                            'import platform; print(platform.python_version(), platform.machine())'], text=True).strip()
        if observed != lock['pythonVersion'] + ' arm64': raise ValueError('Runtime architecture/version mismatch')
        runtime_identity = {'python': lock, 'pythonPackages': packages, 'licenses': licenses,
                            'preservedUpstreamRecordDifferences': normalization,
                            'uvLockSha256': hashlib.sha256(source['uv.lock'][0]).hexdigest(),
                            'requirementsSha256': sha256(tree/'runtime-requirements.txt')}
        (tree/'runtime-manifest.json').write_bytes(encoded(runtime_identity))
        manifest = {'schemaVersion': 1, 'name': 'grea', 'kind': 'complete-plugin',
                    'version': version, 'target': 'macos-arm64', **identity,
                    'runtime': runtime_identity, 'files': inventory(tree),
                    'limits': 'Local core MCP is bundled; Unity Editor and optional external providers are separate. No other platform is accepted by this artifact.'}
        (tree/'plugin-manifest.json').write_bytes(encoded(manifest))
        out.mkdir()
        write_archive(tree, out/ARCHIVE, identity['source_timestamp'])
    verify_archive(out/ARCHIVE)
    summary = {k: manifest[k] for k in ('version', 'target', 'source_revision', 'source_dirty', 'source_kind', 'source_tree_sha256')}
    summary.update(archive=ARCHIVE, sha256=sha256(out/ARCHIVE), bytes=(out/ARCHIVE).stat().st_size,
                   files=len(manifest['files']), runtime=runtime_identity)
    (out/'plugin-build.json').write_bytes(encoded(summary))
    (out/'SHA256SUMS').write_text(''.join(sha256(out/name)+'  '+name+'\n' for name in (ARCHIVE, 'plugin-build.json')), encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--worktree', action='store_true', help='Unpublished preview of audited current worktree bytes')
    parser.add_argument('--tag')
    args = parser.parse_args()
    result = build(args.out, worktree=args.worktree, cache=args.cache, tag=args.tag)
    print(json.dumps({k: v for k, v in result.items() if k != 'runtime'}, ensure_ascii=False))
