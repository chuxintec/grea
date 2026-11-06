"""Predict the single serialized field Unity derives from a renamed Prefab file, without editing it."""
import hashlib
import json
import re
from pathlib import Path

from grea.features.prefab.verify_static_set import HEADER


def root_alias(raw, source, target):
    before, after = Path(source).stem, Path(target).stem
    if before == after:
        return None
    heads = list(HEADER.finditer(raw))
    docs = {int(h[2]):(int(h[1]), h.end(), heads[i+1].start() if i+1<len(heads) else len(raw))
            for i,h in enumerate(heads) if not h[0].rstrip().endswith(b'stripped')}
    transforms = [raw[lo:hi] for kind,lo,hi in docs.values() if kind in (4,224)
                  and re.search(rb'^  m_Father: \{fileID: 0\}\r?$', raw[lo:hi], re.M)]
    owner = re.search(rb'^  m_GameObject: \{fileID: (-?\d+)\}', transforms[0], re.M) if len(transforms)==1 else None
    if not owner or int(owner[1]) not in docs:
        raise ValueError('Renaming this Prefab requires a direct serialized root: ' + source)
    kind, lo, hi = docs[int(owner[1])]
    name = re.search(rb'^  m_Name: ([^\r\n]*)', raw[lo:hi], re.M)
    if kind != 1 or not name or not re.fullmatch(r'[A-Za-z0-9_]+', after):
        raise ValueError('Cannot pin serialized Prefab root name: ' + source)
    source_name = name[1].decode('utf-8')
    if source_name.startswith('"'):
        source_name = json.loads(source_name)
    if source_name != before:
        raise ValueError('Serialized root name differs from the source filename: ' + source)
    start, end = lo+name.start(1), lo+name.end(1)
    digest = hashlib.sha256()
    for part in (raw[:start], after.encode(), raw[end:]):
        digest.update(part)
    return dict(sourceName=before, targetName=after, rootLocalId=int(owner[1]), savedSha256=digest.hexdigest())
