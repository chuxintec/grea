"""Exact declared built-in PPtr closure; a GUID never authorizes its whole domain."""
import re

from .errors import fail

LEGACY_GUID_REFERENCES = re.compile(rb'\bguid:\s*([a-f0-9]{32})\b')
GUID_TOKENS = re.compile(rb'\bguid:[ \t]*([^ \t\r\n,}]+)')
CANONICAL_GUID = re.compile(rb'[a-f0-9]{32}\Z')
PPTR = re.compile(rb'\{[ \t]*fileID:[ \t]*(-?[0-9]+)[ \t]*,[ \t]*guid:[ \t]*([^ \t\r\n,}]+)[ \t]*,[ \t]*type:[ \t]*([0-9]+)[ \t]*\}')


def declarations(rows, ordinary_guids):
    objects = {(r['guid'], r['localId']): r for r in rows}
    if {r['guid'] for r in rows} & ordinary_guids:
        fail('INTAKE_ENGINE_DOMAIN', 'engineObjects', 'Built-in identities cannot also be imported or externally owned asset GUIDs')
    return objects


def text_references(raw, where, ordinary_guids, objects, *, importer=False, strict=False):
    used = set()
    if not strict:
        # Versions1–3 retain their original GUID scanner and null rules.
        for match in LEGACY_GUID_REFERENCES.finditer(raw):
            guid = match.group(1).decode()
            if guid not in ordinary_guids | {'0' * 32}:
                message = 'Importer reference outside selected closure' if importer else 'Unselected or undeclared serialized GUID reference: ' + guid
                fail('INTAKE_IMPORTER_REFERENCE' if importer else 'INTAKE_DEPENDENCY_CLOSURE', where, message)
        return used
    refs = list(PPTR.finditer(raw))
    for match in GUID_TOKENS.finditer(raw):
        token = match.group(1)
        if not CANONICAL_GUID.fullmatch(token):
            fail('INTAKE_REFERENCE_CANONICAL', where, 'Serialized GUID must be exactly32 lowercase hexadecimal characters')
        guid = token.decode()
        candidates = [p for p in refs if p.start(2) == match.start(1) and p.end(2) == match.end(1)]
        if guid == '0' * 32:
            if len(candidates) == 1 and candidates[0].group(1) == b'0' and candidates[0].group(3) == b'0':
                continue
        elif guid in ordinary_guids:
            continue
        elif not importer and len(candidates) == 1:
            p = candidates[0]; key = (guid, int(p.group(1)))
            if key in objects and p.group(3) == b'0':
                used.add(key)
                continue
        fail('INTAKE_IMPORTER_REFERENCE' if importer else 'INTAKE_DEPENDENCY_CLOSURE', where,
             'Unselected or undeclared exact serialized GUID/localID/type reference: ' + guid)
    return used


def expected_reference(value, where, ordinary_guids, objects):
    if value['guid'] in ordinary_guids | {''}:
        return
    row = objects.get((value['guid'], value['localId']))
    if row is None or (value['type'], value['assembly']) != (row['type'], row['assembly']):
        fail('INTAKE_EXPECTATION_REFERENCE', where, 'Object expectation is outside the declared exact asset/engine identity closure')
