"""Exact read-only resource and official UGUI dependency declarations."""
from .io import inside, read, load
from .output_limits import digest_file
from .errors import fail


def assets(spec, incoming, files, before, existing_guids, get_guid):
    rows = spec.get('externalAssets', [])
    for row in rows:
        src, dest = row['source'], row['target']
        if src not in files or src+'.meta' not in files:
            fail('INTAKE_EXTERNAL_SOURCE', src, 'Candidate asset/meta pair required')
        if get_guid(read(inside(incoming, src+'.meta')), src) != row['guid'] or existing_guids.get(row['guid']) != [dest]:
            fail('INTAKE_EXTERNAL_IDENTITY', dest, 'Exact same GUID and unique retained path required')
        for suffix, key in [('', 'sha256'), ('.meta', 'metaSha256')]:
            if files[src+suffix]['sha256'] != row[key] or before.get(dest+suffix, {}).get('sha256') != row[key]:
                fail('INTAKE_EXTERNAL_BYTES', dest+suffix, 'Candidate and retained asset/meta must both match exact reviewed bytes')
    return rows


def package_scripts(spec, target, existing_guids, *, requirements=None):
    rows = []
    for row in spec.get('packageScripts', []):
        name = row['packageName']
        manifest = load(read(inside(target, 'Packages/manifest.json')))
        lock = load(read(inside(target, 'Packages/packages-lock.json')))
        declaration = lock.get('dependencies', {}).get(name, {})
        resolved = (requirements or {}).get('resolvedPackages', {}).get(name, {})
        proven_builtin = (resolved.get('resolvedVersion') == row['packageVersion'] and resolved.get('source') == 'builtin'
                          and resolved.get('requestedTarget') == manifest.get('dependencies', {}).get(name)
                          and resolved.get('targetRoot') and row['packageSource'] == 'builtin')
        if ((manifest.get('dependencies', {}).get(name) != row['packageVersion'] and not proven_builtin)
                or declaration.get('version') != row['packageVersion'] or declaration.get('source') != row['packageSource']
                or row['packageSource'] == 'registry' and declaration.get('url') != 'https://packages.unity.com'):
            fail('INTAKE_PACKAGE_SOURCE', name, 'Exact direct official Unity registry/builtin package and locked version required')
        if row['guid'] in existing_guids:
            fail('INTAKE_PACKAGE_GUID', row['guid'], 'Package script GUID is also owned under Assets')
        # Only the project-resolved UPM cache is eligible; no caller-provided filesystem root.
        cache = inside(target, 'Library/PackageCache')
        matches = []
        if cache.is_dir():
            for path in cache.glob(name+'@*/package.json'):
                path = inside(target, path.relative_to(target).as_posix())
                info = load(read(path))
                if info.get('name') == name and info.get('version') == row['packageVersion']:
                    matches.append(path.parent)
        if len(matches) != 1:
            fail('INTAKE_PACKAGE_RESOLUTION', name, 'One exact cached official package required; do not install or choose a stale copy')
        root = matches[0]
        if proven_builtin and (str(root)!=resolved.get('targetRoot') or row['packageJsonSha256']!=resolved.get('packageJsonSha256')):
            fail('INTAKE_PACKAGE_RESOLUTION', name, 'Proven builtin cache root/package identity differs')
        relative = row['target'].removeprefix('Packages/'+name+'/')
        pins = [('package.json', row['packageJsonSha256']), (relative, row['sha256']), (relative+'.meta', row['metaSha256'])]
        for path, expected in pins:
            path = inside(root, path)
            if not path.is_file() or digest_file(path) != expected:
                fail('INTAKE_PACKAGE_BYTES', str(path), 'Exact cached package/source/meta pin differs')
        from .intake import guid
        if guid(read(inside(root, relative+'.meta')), row['target']) != row['guid']:
            fail('INTAKE_PACKAGE_GUID', row['target'], 'Package MonoScript metadata GUID differs')
        rows.append(dict(row, resolvedRoot=str(root)))
    return rows


def recheck_packages(plan):
    """Guard package cache contents on success and before any rollback mutation."""
    if not plan.get('packageScripts'):
        return
    from .io import safe
    current = package_scripts(plan['spec'], safe(plan['targetRoot']), {}, requirements=plan.get('projectRequirements'))
    if current != plan['packageScripts']:
        fail('INTAKE_PACKAGE_DRIFT', plan['targetRoot'], 'Retained package resolution changed')
    if package_inputs(current) != plan['packageInputs']:
        fail('INTAKE_PACKAGE_DRIFT', plan['targetRoot'], 'Pinned package source tree changed')


def package_inputs(rows):
    result = {}
    for row in rows:
        root = row['resolvedRoot']
        if root in result:
            continue
        from .io import safe
        directory = safe(root)
        entries = {}
        for path in directory.rglob('*'):
            if len(entries) > 20000:
                fail('INTAKE_PACKAGE_BUDGET', root, 'Package file budget exceeded')
            path = inside(directory, path.relative_to(directory).as_posix())
            if path.is_file():
                entries[path.relative_to(directory).as_posix()] = digest_file(path)
        result[root] = entries
    return result
