"""Walk UnityPy serialized object pointers from explicitly selected source roots."""
import argparse
from collections import defaultdict
from functools import lru_cache
import json
from pathlib import Path


def pointer(file, ref):
    if not ref or not ref['m_PathID']:
        return None
    index = ref['m_FileID']
    if not 0 <= index <= len(file.externals):
        raise ValueError(f'Invalid external file index {index} in {file.name}')
    cab = file.externals[index - 1].path if index else file.name
    return Path(cab).name.lower(), ref['m_PathID']


def positive_pointers(file, tree):
    pending = [tree]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if 'm_PathID' in value and 'm_FileID' in value:
                key = pointer(file, value)
                if key:
                    yield key
            else:
                pending.extend(value.values())
        elif isinstance(value, (list, tuple)):
            # Maps such as Material.m_SavedProperties.m_TexEnvs contain (name, value) pairs.
            pending.extend(item for item in value if isinstance(item, (dict, tuple, list)))


def closure(manifest):
    import UnityPy
    paths = {}
    for name in manifest['bundles']:
        path = Path(name)
        for file in UnityPy.load(path.read_bytes()).assets:
            key = file.name.lower()
            if key in paths and paths[key] != path:
                raise ValueError(f'Duplicate serialized file: {key}')
            paths[key] = path

    @lru_cache(maxsize=12)
    def load_file(key):
        return next(file for file in UnityPy.load(paths[key].read_bytes()).assets if file.name.lower() == key)

    queue = [(row['cab'].lower(), int(row['pathId'])) for row in manifest['roots']]
    seen = defaultdict(set)
    external = defaultdict(set)
    missing = defaultdict(set)
    while queue:
        cab, pid = queue.pop()
        if pid in seen[cab]:
            continue
        seen[cab].add(pid)
        if cab not in paths:
            external[cab].add(pid)
            continue
        file = load_file(cab)
        obj = file.objects.get(pid)
        if obj is None:
            missing[cab].add(pid)
            continue
        queue.extend(positive_pointers(file, obj.read_typetree()))
    def sorted_map(mapping):
        return {cab: sorted(ids) for cab, ids in sorted(mapping.items())}
    return dict(objects=sorted_map({k:v for k,v in seen.items() if k in paths}),
                external=sorted_map(external), missing=sorted_map(missing))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = closure(json.loads(args.sources.read_text()))
    args.output.write_text(json.dumps(result, sort_keys=True))
    return int(bool(result['missing']))


if __name__ == '__main__':
    raise SystemExit(main())
