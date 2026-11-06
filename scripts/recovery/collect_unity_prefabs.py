"""Collect saved Unity prefabs by original source ID across ordered batch retries.

The selection may include canonicalId for bundle redirects. A successful later
batch supersedes an earlier one. Projects remain separate because each Unity
project owns its font atlases, material assets, local IDs and GUIDs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile


def load(path):
    return json.loads(path.read_bytes())


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify(project, receipt):
    row = load(receipt)
    asset = (project / row['path']).resolve(strict=True)
    if not asset.is_relative_to(project / 'Assets') or asset.suffix != '.prefab':
        raise ValueError(f'Unexpected prefab path in {receipt}')
    meta = Path(str(asset) + '.meta')
    guid = re.search(r'^guid: ([\da-f]{32})$', meta.read_text(), re.M)
    if not (row['savedReloaded'] and row['referencesVerified'] and row['missingScripts'] == 0
            and guid and guid[1] == row['guid'] and digest(asset) == row['prefabSha256']):
        raise ValueError(f'Failed native readback or prefab identity mismatch: {receipt}')
    return dict(project=str(project), prefab=str(asset), receipt=str(receipt),
                assetPath=row['path'], guid=row['guid'], sha256=row['prefabSha256'])


def collect(selection, batches):
    rows = {s['sourceId']: s for s in selection}
    if len(rows) != len(selection):
        raise ValueError('Duplicate source IDs in selection')
    found = {}
    for batch in batches:
        reports = load(batch / 'native-results.json')
        conversions = {j['name']: j for j in load(batch / 'conversion-results-v2.json')}
        for report in reports:
            if report.get('processExitCode') != 0:
                continue
            project = Path(report['project']).resolve(strict=True)
            receipts = {load(f)['sourceId']: f for f in (project / 'Analysis/Readback/Prefabs').glob('*.json')}
            job = conversions[report['name']]
            for source_id in report['sourceIds']:
                if source_id not in rows:
                    continue
                canonical = rows[source_id].get('canonicalId') or source_id
                if canonical != source_id:
                    ir_path = Path(job['basePlan']).parents[1] / 'normalize/ir.json'
                    if (digest(ir_path) != load(Path(job['basePlan']))['sourceIrSha256']
                            or load(ir_path)['aliases'].get(source_id) != canonical):
                        raise ValueError(f'Unverified redirect: {source_id} -> {canonical}')
                receipt = receipts.get(canonical)
                if receipt:
                    found[source_id] = dict(rows[source_id], **verify(project, receipt),
                                            conversionPlan=job['plan'], batchName=report['name'],
                                            batchDirectory=str(batch))
    missing = rows.keys() - found.keys()
    if missing:
        raise ValueError(f'{len(missing)} sources lack verified prefabs: {sorted(missing)}')
    for source_id, row in found.items():
        canonical = row.get('canonicalId', source_id)
        if canonical != source_id and canonical in found:
            for key in ('project', 'prefab', 'receipt', 'assetPath', 'guid', 'sha256', 'conversionPlan', 'batchName', 'batchDirectory'):
                row[key] = found[canonical][key]
        row['previousStatus'] = row.pop('status', None)
        row['status'] = 'verified-save-reopen'
    return [found[s['sourceId']] for s in selection]


def write_archive(path, rows):
    projects = sorted({r['project'] for r in rows})
    folders = {project: f'Projects/{i:03d}' for i, project in enumerate(projects, 1)}
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        portable = []
        for row in rows:
            folder = folders[row['project']]
            portable.append({k: row[k] for k in ('sourceId', 'canonicalId', 'path', 'guid', 'sha256') if k in row}
                            | dict(project=folder, prefab=folder + '/' + row['assetPath']))
        archive.writestr('prefabs.json', json.dumps(portable, indent=2, ensure_ascii=False))
        for project, folder in folders.items():
            root = Path(project)
            for name in ('Assets', 'Packages', 'ProjectSettings'):
                tree = root / name
                if not tree.is_dir():
                    raise ValueError(f'Missing Unity project directory: {tree}')
                for file in sorted(tree.rglob('*')):
                    if file.is_file():
                        archive.write(file, f'{folder}/{file.relative_to(root).as_posix()}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', required=True, type=Path)
    parser.add_argument('--batch', action='append', required=True, type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--archive', action='store_true')
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Choose a fresh output directory')
    rows = collect(load(args.selection), [p.resolve() for p in args.batch])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.out.parent) as temp:
        staging = Path(temp) / 'delivery'
        staging.mkdir()
        (staging / 'prefabs.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False))
        if args.archive:
            write_archive(staging / 'UnityProjects.zip', rows)
        os.rename(staging, args.out)
    print(f'Collected {len(rows)} source entries from {len({r["project"] for r in rows})} Unity projects')


if __name__ == '__main__':
    main()
