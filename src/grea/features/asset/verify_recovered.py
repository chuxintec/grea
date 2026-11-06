"""Verify the complete staged file set after importing it into Unity."""
from pathlib import Path
import json

from grea.development.io import safe, new_output, write_json
from grea.development.output_limits import digest_file
from .recovered_layout import active_files, inventory, asset_path, META_GUID


def verify(args):
    project = safe(args.project)
    records = {}
    with safe(args.ledger).open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            guid = row['guid']
            if guid in records:
                raise ValueError('Duplicate ledger GUID: ' + guid)
            asset_path(row['target'])
            records[guid] = row
    before, after = inventory(args.before), inventory(args.inventory)
    if not records or records.keys() != before.keys() or records.keys() != after.keys():
        raise ValueError('Asset identity set differs between ledger and native inventories')
    if active_files(project) != {str(p) for p, _, _ in after.values()}:
        raise ValueError('On-disk assets differ from the imported inventory')
    for guid, row in records.items():
        src, typ, deps = before[guid]
        dst, actual, current = after[guid]
        if (str(src), str(dst), typ, actual) != (row['source'], row['target'], row['importedType'], row['importedType']) or set(deps) != set(current):
            raise ValueError('Native path, type or direct dependencies changed: ' + guid)
        path = project/dst
        meta = Path(str(path) + '.meta')
        ident = META_GUID.search(meta.read_bytes())
        expected = {row['sha256']}
        if 'prefabRootAlias' in row:
            expected.add(row['prefabRootAlias']['savedSha256'])
        if not ident or ident[1].decode() != guid or digest_file(path) not in expected or digest_file(meta) != row['metaSha256']:
            raise ValueError('Imported file or metadata differs from ledger: ' + str(dst))
    out = new_output(args.output, [project, args.before, args.inventory, args.ledger])
    result = dict(assets=len(records), nativeReadback='matched-imported-paths-types-dependencies',
                  contentAndMetaFiles=2*len(records))
    write_json(out/'verification.json', result)
    return dict(result, report=str(out/'verification.json'))
