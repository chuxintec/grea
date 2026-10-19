#!/usr/bin/env python3
"""Version-gated complete native plugins and resumable GitHub releases (Python 3.11+)."""
import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from audit_public_tree import inspect

ROOT = Path(__file__).resolve().parents[1]
TAG = re.compile(r'v(\d+\.\d+\.\d+)(?:-rc([1-9]\d*))?')


def version(tag):
    match = TAG.fullmatch(tag)
    if not match:
        raise ValueError('Use vX.Y.Z or vX.Y.Z-rcN (N >= 1).')
    base = '.'.join(str(int(n)) for n in match[1].split('.'))
    return base + ('rc' + match[2] if match[2] else ''), bool(match[2])


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def identity(tag, require_tag=False):
    package, prerelease = version(tag)
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    tree = ast.parse((ROOT / 'src/grea/__init__.py').read_text(encoding='utf-8'))
    runtime = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == '__version__' for t in n.targets))
    locked = next(p['version'] for p in tomllib.loads((ROOT / 'uv.lock').read_text(encoding='utf-8'))['package'] if p['name'] == 'grea')
    if {project['version'], runtime, locked} != {package}:
        raise ValueError('Tag, pyproject.toml, runtime and uv.lock versions must agree.')
    if git('status', '--porcelain', '--untracked-files=no').strip():
        raise ValueError('Tracked source must be clean before release.')
    sha = git('rev-parse', 'HEAD').decode().strip()
    if require_tag and git('rev-parse', f'refs/tags/{tag}^{{commit}}').decode().strip() != sha:
        raise ValueError('Tag does not point to the checked-out commit.')
    return package, prerelease, sha, project['requires-python']


def source_files():
    files = {}
    for entry in git('ls-tree', '-rz', '--full-tree', 'HEAD').split(b'\0'):
        if not entry:
            continue
        info, raw = entry.split(b'\t', 1)
        mode, kind, oid = info.decode().split()
        name = raw.decode('utf-8')
        if kind != 'blob' or mode not in ('100644', '100755'):
            raise ValueError('Only regular source files may be released: ' + name)
        data = git('cat-file', 'blob', oid)
        issues = inspect(name, data, mode)
        if issues:
            raise ValueError('Public source check failed: ' + name + ' ' + str(issues))
        files[name] = (data, int(mode, 8))
    return files


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


TARGETS = ('macos-arm64', 'windows-x64')


def asset_names(manifest):
    from plugin_targets import archive_name, report_name
    names = ['release-manifest.json']
    for target in manifest['plugin_targets']:
        names.extend((archive_name(target), report_name(target), 'client-acceptance-'+target+'.json'))
    return names


def write_manifest(out, manifest):
    (out/'release-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'SHA256SUMS').write_text(''.join(sha256(out/n)+'  '+n+'\n' for n in asset_names(manifest)),encoding='utf-8')


def prepare(tag, out, require_tag=False):
    package, prerelease, sha, python = identity(tag, require_tag)
    files=source_files()  # Public audit remains a gate even though GitHub supplies source downloads.
    changes=files.get(f"validation/release-notes/{tag}.md",(b"",0))[0].decode("utf-8")
    out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema_version':2,'product':'grea','release_version':tag,
                'package_version':package,'prerelease':prerelease,'source_revision':sha,
                'source_dirty':False,'plugin_targets':[],'artifacts':[],
                'validation':{'plugin_acceptances':{},'client_acceptances':{},
                              'workflow':'.github/workflows/release.yml',
                              'workflow_run':('https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID']) if all(os.environ.get(k) for k in ('GITHUB_REPOSITORY','GITHUB_RUN_ID')) else None,
                              'windows_desktop_unity_player_performance':'not_run: excluded by user scope'}}
    write_manifest(out,manifest)
    (out/'release-notes.md').write_text(
        f'grea {tag}\n\n'+('预发行版本。' if prerelease else '正式版本。')+
        f'版本 `{package}`，源码提交 `{sha}`。\n\n'+
        changes+'\n\n完整插件自带 Python、MCP、'+str(sum(n.startswith('plugin/skills/') and n.endswith('/SKILL.md') for n in files))+' 个技能、参考和许可证。源码由 Git/GitHub 自动下载提供。\n\n'+
        'Windows x64 通过 Windows Server 原生 CI、隔离工具执行、重复构建及临时 Codex 安装发现验证。'
        'Windows 11 桌面、Unity Editor/Player、图形性能和人工输入未实机验收（本轮范围明确排除）。'
        '可选第三方供应方仍需独立安装及验证。\n\n'
        '解压对应平台插件，进入 grea 目录后运行 `codex plugin marketplace add .`、'
        '`codex plugin add grea@grea-local`，重启客户端后调用 session 核对安装路径。'
        '完整用法见包内 docs/安装与平台.md；自有代码 MIT，第三方许可见 THIRD_PARTY.md。\n',encoding='utf-8')
    return manifest


def verify(tag, out, complete=True):
    package, prerelease, revision, _ = identity(tag)
    manifest=json.loads((out/'release-manifest.json').read_text(encoding='utf-8'))
    if (manifest.get('schema_version'),manifest.get('release_version'),manifest.get('source_revision'),
        manifest.get('prerelease'),manifest.get('package_version'),manifest.get('source_dirty')) != (2,tag,revision,prerelease,package,False):
        raise ValueError('Manifest identity mismatch')
    targets=manifest['plugin_targets']
    if len(targets)!=len(set(targets)) or any(t not in TARGETS for t in targets):raise ValueError('Invalid target set')
    if complete and set(targets)!=set(TARGETS):raise ValueError('Both native plugin targets required')
    if len(manifest['artifacts'])!=len(targets):raise ValueError('Unexpected installation artifacts')
    from plugin_targets import archive_name,report_name
    from plugin_release import validate, validate_client
    source=source_files()
    for index,target in enumerate(targets):
        row,report=validate(out/archive_name(target),out/report_name(target),source,package,revision)
        client=validate_client(out/('client-acceptance-'+target+'.json'),out/archive_name(target),target,package)
        if (manifest['artifacts'][index]!=row or manifest['validation']['plugin_acceptances'].get(target)!=report
                or manifest['validation']['client_acceptances'].get(target)!=client):raise ValueError('Acceptance identity mismatch')
    names=asset_names(manifest)
    if (out/'SHA256SUMS').read_text(encoding='utf-8')!=''.join(sha256(out/n)+'  '+n+'\n' for n in names):raise ValueError('Checksum mismatch')
    actual={p.name for p in out.iterdir()}
    if actual!=set(names+['SHA256SUMS','release-notes.md']):raise ValueError('Unexpected or missing release files')
    return names+['SHA256SUMS']


def attach_plugin(tag, out, plugin_dir, target='macos-arm64'):
    from plugin_release import validate,validate_client
    from plugin_targets import archive_name,report_name
    verify(tag,out,complete=False)
    if target not in TARGETS:raise ValueError('Unknown plugin target')
    package,_,revision,_=identity(tag)
    manifest=json.loads((out/'release-manifest.json').read_text(encoding='utf-8'))
    if target in manifest['plugin_targets']:raise ValueError('Target already attached')
    archive=archive_name(target);report=report_name(target);client='client-acceptance-'+target+'.json'
    row,report_row=validate(plugin_dir/archive,plugin_dir/'plugin-acceptance.json',source_files(),package,revision)
    if row['target']!=target:raise ValueError('Wrong target supplied')
    client_row=validate_client(plugin_dir/'client-acceptance.json',plugin_dir/archive,target,package,name=client)
    for source_name,dest in [(archive,archive),('plugin-acceptance.json',report),('client-acceptance.json',client)]:
        if (out/dest).exists():raise FileExistsError(out/dest)
        shutil.copyfile(plugin_dir/source_name,out/dest)
    manifest['plugin_targets'].append(target);manifest['artifacts'].append(row)
    manifest['validation']['plugin_acceptances'][target]=report_row
    manifest['validation']['client_acceptances'][target]=client_row
    write_manifest(out,manifest)
    verify(tag,out,complete=False)
    return manifest


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def api(repo, endpoint, method='GET', data=None):
    args = ['gh', 'api', f'repos/{repo}/{endpoint}', '--method', method]
    if data is not None:
        args += ['--input', '-']
    result = subprocess.run(args, input=json.dumps(data) if data is not None else None,
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def release_state(repo, tag):
    pages = json.loads(gh('api', '--paginate', '--slurp', f'repos/{repo}/releases?per_page=100'))
    return next((r for page in pages for r in page if r['tag_name'] == tag), None)


def compare_remote(repo, release, out, names):
    assets = release['assets']
    actual = {a['name'] for a in assets}
    if not actual <= set(names) or len(actual) != len(assets):
        raise ValueError('Unexpected or duplicate remote assets; refusing overwrite.')
    with tempfile.TemporaryDirectory() as tmp:
        for asset in assets:
            name = asset['name']
            if asset['state'] != 'uploaded' or asset['size'] != (out / name).stat().st_size:
                raise ValueError('Remote asset incomplete or different: ' + name)
            gh('release', 'download', release['tag_name'], '--repo', repo, '--pattern', name, '--dir', tmp)
            if (Path(tmp) / name).read_bytes() != (out / name).read_bytes():
                raise ValueError('Remote asset bytes differ: ' + name)
    return actual


def publish(tag, out, repo):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('Invalid repository.')
    names = verify(tag, out)
    _, prerelease, sha, _ = identity(tag, require_tag=True)
    if api(repo, 'commits/' + tag)['sha'] != sha:
        raise ValueError('Remote tag moved; refusing release.')
    release = release_state(repo, tag)
    if release is None:
        release = api(repo, 'releases', 'POST', {
            'tag_name': tag, 'target_commitish': sha, 'name': 'grea ' + tag,
            'body': (out / 'release-notes.md').read_text(encoding='utf-8'), 'draft': True, 'prerelease': prerelease})
    if release['prerelease'] != prerelease:
        raise ValueError('Existing release type differs; refusing overwrite.')
    existing = compare_remote(repo, release, out, names)
    if not release['draft']:
        if existing != set(names):
            raise ValueError('Published release is incomplete; refusing mutation.')
        return release['html_url']
    for name in names:
        if name not in existing:
            gh('release', 'upload', tag, str(out / name), '--repo', repo)
    release = api(repo, f"releases/{release['id']}")
    if compare_remote(repo, release, out, names) != set(names):
        raise ValueError('Upload incomplete; draft preserved.')
    # Recheck after upload, just before making the release public.
    if api(repo, 'commits/' + tag)['sha'] != sha:
        raise ValueError('Remote tag changed during upload; draft preserved.')
    release = api(repo, f"releases/{release['id']}", 'PATCH',
                  {'draft': False, 'prerelease': prerelease, 'make_latest': 'false' if prerelease else 'legacy'})
    final = api(repo, f"releases/{release['id']}")
    if final['draft'] or final['prerelease'] != prerelease or compare_remote(repo, final, out, names) != set(names):
        raise ValueError('Published release readback failed; inspect existing release before retry.')
    return final['html_url']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'verify', 'attach-plugin', 'publish'])
    parser.add_argument('--tag', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--require-tag', action='store_true')
    parser.add_argument('--partial', action='store_true', help='Verify staging only; never publish partial targets')
    parser.add_argument('--repo')
    parser.add_argument('--plugin-dir', type=Path)
    parser.add_argument('--target',choices=('macos-arm64','windows-x64'),default='macos-arm64')
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.tag, args.out, args.require_tag)
    elif args.action == 'verify':
        result = verify(args.tag, args.out, complete=not args.partial)
    elif args.action == 'attach-plugin':
        if not args.plugin_dir: parser.error('--plugin-dir required')
        result = attach_plugin(args.tag, args.out, args.plugin_dir,args.target)
    else:
        if not args.repo:
            parser.error('--repo required for publish')
        result = publish(args.tag, args.out, args.repo)
    print(json.dumps(result, ensure_ascii=False))
