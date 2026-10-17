#!/usr/bin/env python3
"""Version-gated source bundles and resumable GitHub releases (Python 3.11+)."""
import argparse
import ast
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from audit_public_tree import inspect
import build_skill

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


def prepare(tag, out, require_tag=False):
    package, prerelease, sha, python = identity(tag, require_tag)
    files = source_files()
    skill_files = build_skill.render(files, package, sha)
    timestamp = datetime.fromtimestamp(int(git('show', '-s', '--format=%ct', 'HEAD')), timezone.utc)
    out.mkdir(parents=True, exist_ok=False)
    archive = out / f'grea-{tag}.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, (data, mode) in sorted(files.items()):
            info = zipfile.ZipInfo(f'grea-{tag}/{name}', timestamp.timetuple()[:6])
            info.create_system = 3
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    skill_archive = out / f'grea-skill-{tag}.zip'
    build_skill.write_archive(skill_archive, skill_files, timestamp)
    manifest = {
        'schema_version': 1, 'product': 'grea', 'release_version': tag,
        'package_version': package, 'prerelease': prerelease, 'source_revision': sha,
        'source_dirty': False, 'source_timestamp': timestamp.isoformat(),
        'requirements': {'python_declared': python, 'install': 'uv sync --frozen',
                         'uv_lock_sha256': hashlib.sha256(files['uv.lock'][0]).hexdigest()},
        'artifacts': [{'name': archive.name, 'bytes': archive.stat().st_size,
                       'sha256': sha256(archive), 'files': len(files), 'root_directory': f'grea-{tag}'},
                      {'name': skill_archive.name, 'kind': 'skill', 'version': package,
                       'bytes': skill_archive.stat().st_size, 'sha256': sha256(skill_archive),
                       'files': len(skill_files), 'root_directory': 'grea'}],
        'validation': {'workflow': '.github/workflows/release.yml',
                       'publication_gates': ['source audit', 'core tests and stdio MCP', 'contract and skill checks',
                                             'fresh extracted bundle install and tests', 'uploaded asset download comparison'],
                       'windows_native': 'not_run', 'game_and_unity_runtime': 'not_run'},
        'distribution': 'Public source only; optional third-party providers installed separately. See THIRD_PARTY.md.',
    }
    (out / 'release-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'SHA256SUMS').write_text(''.join(sha256(p) + '  ' + p.name + '\n' for p in (archive, skill_archive, out / 'release-manifest.json')), encoding='utf-8')
    (out / 'release-notes.md').write_text(
        f'grea {tag}\n\n' + ('预发行版本。' if prerelease else '正式版本。') +
        f'完整源码使用包，Python/CLI 版本 `{package}`。\n\n'
        f'附件：完整 ZIP、独立 Skill ZIP（版本 {package}）、release-manifest.json、SHA256SUMS。\n\n'
        f'解压并进入 `grea-{tag}`，运行 `uv sync --frozen`，再运行 `./bin/grea session`；'
        'Windows 入口为 `bin\\grea.cmd session`。macOS 可用系统 Archive Utility 或 ditto 解压中文文件名。\n\n'
        '源码与纯文档包不包含第三方程序、Unity 包快照、Spine vendor、虚拟环境或项目材料。'
        '来源与许可证见 THIRD_PARTY.md，自有代码采用 MIT。\n\n'
        '发布由测试、契约/技能检查及解压包安装验证把关；Windows 原生运行、Unity Editor 和游戏验收未执行。'
        '平台限制见 docs/安装与平台.md。\n\n'
        f'源码提交：`{sha}`。\n', encoding='utf-8')
    return manifest


def verify(tag, out, extract=None, extract_skill=None):
    package, prerelease, sha, _ = identity(tag)
    manifest = json.loads((out / 'release-manifest.json').read_text(encoding='utf-8'))
    if (manifest['release_version'], manifest['source_revision'], manifest['prerelease'], manifest['package_version']) != (tag, sha, prerelease, package):
        raise ValueError('Manifest identity mismatch.')
    names = [f'grea-{tag}.zip', f'grea-skill-{tag}.zip', 'release-manifest.json']
    from plugin_targets import TARGETS, archive_name, report_name
    targets=manifest.get('plugin_targets',['macos-arm64'] if len(manifest['artifacts'])==3 else [])
    if len(targets)!=len(set(targets)) or any(t not in TARGETS for t in targets):raise ValueError('Invalid target set')
    for target in targets:names += [archive_name(target),report_name(target)]
    checksums = ''.join(sha256(out / n) + '  ' + n + '\n' for n in names)
    if (out / 'SHA256SUMS').read_text(encoding='utf-8') != checksums:
        raise ValueError('Checksum mismatch.')
    archive = out / names[0]
    row = manifest['artifacts'][0]
    if (row['name'], row['bytes'], row['sha256']) != (names[0], archive.stat().st_size, sha256(archive)):
        raise ValueError('Archive identity mismatch.')
    files = source_files()
    if len(manifest['artifacts']) != 2+len(targets) or row['files'] != len(files) or row['root_directory'] != f'grea-{tag}':
        raise ValueError('Manifest file inventory mismatch.')
    for index,target in enumerate(targets):
        from plugin_release import validate
        plugin_row, report_row = validate(out/archive_name(target),out/report_name(target),files,package,sha)
        report=manifest['validation'].get('plugin_acceptances',{}).get(target,manifest['validation'].get('plugin_acceptance') if target=='macos-arm64' else None)
        if manifest['artifacts'][index+2] != plugin_row or report!=report_row:
            raise ValueError('Portable plugin release identity mismatch')
    skill_files = build_skill.render(files, package, sha)
    skill_row = manifest['artifacts'][1]
    expected_skill_row = {'name': names[1], 'kind': 'skill', 'version': package,
                          'bytes': (out/names[1]).stat().st_size, 'sha256': sha256(out/names[1]),
                          'files': len(skill_files), 'root_directory': 'grea'}
    if skill_row != expected_skill_row:
        raise ValueError('Skill manifest identity mismatch')
    build_skill.verify_archive(out/names[1], skill_files)
    with zipfile.ZipFile(archive) as z:
        expected = {f'grea-{tag}/{p}' for p in files}
        if set(z.namelist()) != expected or len(z.namelist()) != len(expected):
            raise ValueError('Archive file set differs from committed source.')
        for name, (data, mode) in files.items():
            info = z.getinfo(f'grea-{tag}/{name}')
            if z.read(info) != data or info.external_attr >> 16 != mode:
                raise ValueError('Archive file bytes or mode mismatch: ' + name)
        if extract:
            extract.mkdir(parents=True, exist_ok=False)
            for info in z.infolist():
                path = PurePosixPath(info.filename)
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('Unsafe archive path.')
                dest = extract.joinpath(*path.parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(info))
                dest.chmod((info.external_attr >> 16) & 0o777)
    if extract_skill is not None:
        build_skill.verify_archive(out/names[1], skill_files, extract_skill)
    return names + ['SHA256SUMS']


def attach_plugin(tag, out, plugin_dir, target="macos-arm64"):
    """Merge a separately built and accepted platform artifact before publishing."""
    from plugin_release import validate
    from plugin_targets import archive_name,report_name,TARGETS
    if target not in TARGETS:raise ValueError('Unknown plugin target')
    ARCHIVE,REPORT=archive_name(target),report_name(target)
    verify(tag,out)
    package,_,revision,_=identity(tag)
    manifest_path=out/'release-manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    targets=manifest.get('plugin_targets',['macos-arm64'] if len(manifest['artifacts'])==3 else [])
    if target in targets:raise ValueError('Target already attached; do not overwrite')
    plugin_row,report_row=validate(plugin_dir/ARCHIVE,plugin_dir/'plugin-acceptance.json',source_files(),package,revision)
    if plugin_row['target']!=target:raise ValueError('Wrong target supplied')
    for name in (ARCHIVE,REPORT):
        if (out/name).exists():raise FileExistsError(out/name)
    shutil.copyfile(plugin_dir/ARCHIVE,out/ARCHIVE);shutil.copyfile(plugin_dir/'plugin-acceptance.json',out/REPORT)
    manifest['artifacts'].append(plugin_row);manifest['plugin_targets']=[*targets,target]
    manifest['validation'].setdefault('plugin_acceptances',{})[target]=report_row
    if target=='macos-arm64':manifest['validation']['plugin_acceptance']=report_row
    manifest['validation']['publication_gates'].append(target+' native portable plugin isolated acceptance')
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    names=[f'grea-{tag}.zip',f'grea-skill-{tag}.zip','release-manifest.json']
    for item in manifest['plugin_targets']:names.extend((archive_name(item),report_name(item)))
    (out/'SHA256SUMS').write_text(''.join(sha256(out/name)+'  '+name+'\n' for name in names),encoding='utf-8')
    with (out/'release-notes.md').open('a',encoding='utf-8') as stream:
        stream.write('\n完整 '+target+' 插件：`'+ARCHIVE+'`，包含独立 Python、锁定依赖与本地 stdio MCP；支持 Codex 和 Claude Code 的插件配置。Unity 与可选外部工具独立安装。隔离验收见 `'+REPORT+'`。\n')
        stream.write('\n解压插件后进入其中的 `grea/`：\n\n'
                     '```sh\n# Codex\ncodex plugin marketplace add .\ncodex plugin add grea@grea-local\n'
                     '# Claude Code\nclaude plugin marketplace add ./\nclaude plugin install grea@grea-local\n```\n'
                     '\n保留解压目录作为本地安装来源；已有源码版 MCP 注册时先核对并停用同名旧入口，重启客户端后在新会话调用 `session` 核对 `package_root` 为插件安装目录。\n')
    verify(tag, out)
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
    parser.add_argument('--extract', type=Path)
    parser.add_argument('--extract-skill', type=Path)
    parser.add_argument('--repo')
    parser.add_argument('--plugin-dir', type=Path)
    parser.add_argument('--target',choices=('macos-arm64','windows-x64'),default='macos-arm64')
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare(args.tag, args.out, args.require_tag)
    elif args.action == 'verify':
        result = verify(args.tag, args.out, args.extract, args.extract_skill)
    elif args.action == 'attach-plugin':
        if not args.plugin_dir: parser.error('--plugin-dir required')
        result = attach_plugin(args.tag, args.out, args.plugin_dir,args.target)
    else:
        if not args.repo:
            parser.error('--repo required for publish')
        result = publish(args.tag, args.out, args.repo)
    print(json.dumps(result, ensure_ascii=False))
