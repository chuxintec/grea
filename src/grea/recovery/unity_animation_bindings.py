"""Restore only source-proven CRC names and MonoScript pointers in provider clip derivatives."""
import re
import json
import zlib

_ATTRIBUTE = re.compile(rb'(?m)^(    attribute: )script_0x([0-9A-Fa-f]+)_\w+\r?$')
_PATH = re.compile(rb'(?m)^(    path: )path_0x([0-9A-Fa-f]+)_\w+\r?$')
_NULL_CURVE = re.compile(rb'(?m)^(    classID: 114\r?\n    script: )\{fileID: 0\}(\r?)$')
_SENTINEL = re.compile(rb'(?m)^( {4,6}script: )\{fileID: 0, guid: 0000000deadbeef15deadf00d0000000, type: 2\}(\r?)$')


def restore(raw, *, script=None, properties=None, paths=None):
    """Input maps must come from the original component types and actual source hierarchy."""
    def validate(items):
        for code, value in items.items():
            if zlib.crc32(value.encode()) != code or any(c in value for c in '\r\n'):
                raise ValueError('Binding name does not match original CRC')
        return items
    properties, paths = validate(properties or {}), validate(paths or {})
    edits = []
    def rename(match, mapping, kind):
        code = int(match[2],16)
        if code not in mapping:
            return match[0]
        value = mapping[code]
        quoted = value if re.fullmatch(r'[A-Za-z0-9_ ./-]+', value) else json.dumps(value,ensure_ascii=False)
        edits.append(dict(kind=kind, hash=code, name=value))
        return match[1] + quoted.encode()
    result = _ATTRIBUTE.sub(lambda m: rename(m,properties,'property'),raw)
    result = _PATH.sub(lambda m: rename(m,paths,'path'),result)
    if script is not None:
        guid, local = script
        if not re.fullmatch(r'[a-f0-9]{32}',guid) or local==0:
            raise ValueError('Exact target MonoScript identity required')
        def replace(m):
            edits.append(dict(kind='script',guid=guid,local=local))
            return m[1] + ('{fileID: %d, guid: %s, type: 3}'%(local,guid)).encode() + m[2]
        result = _NULL_CURVE.sub(replace,result)
        result = _SENTINEL.sub(replace,result)
    return result, edits


def restore_script_slots(raw, bindings):
    """Bind each float/generic slot by its original (path CRC, property CRC)."""
    def checksum(value):
        text = value.decode().strip()
        if text.startswith('"'):
            text = json.loads(text)
        synthetic = re.fullmatch(r'(?:script|path)_0x([a-fA-F0-9]+)_\w+',text)
        if synthetic:
            return int(synthetic[1],16)
        return zlib.crc32(text.encode()) if text else 0
    edits = []
    def replace(m):
        prefix = raw[:m.start()]
        path = list(re.finditer(rb'(?m)^ {4,6}path:([^\r\n]*)$',prefix))
        prop = list(re.finditer(rb'(?m)^ {4,6}attribute:([^\r\n]*)$',prefix))
        if not path or not prop:
            raise ValueError('Missing animation slot identity')
        numeric = m[1].startswith(b'      script:')
        p = int(path[-1][1]) if numeric else checksum(path[-1][1])
        a = int(prop[-1][1]) if numeric else checksum(prop[-1][1])
        target = bindings.get((p,a))
        if target is None:
            return m[0]
        guid,local=target
        if not re.fullmatch('[a-f0-9]{32}',guid) or local==0:
            raise ValueError('Invalid target script slot')
        edits.append(dict(pathHash=p,attributeHash=a,guid=guid,local=local))
        return m[1]+('{fileID: %d, guid: %s, type: 3}'%(local,guid)).encode()+m[2]
    pattern=re.compile(rb'(?m)^( {4,6}script: )\{fileID: 0(?:, guid: 0000000deadbeef15deadf00d0000000, type: 2)?\}(\r?)$')
    return pattern.sub(replace,raw),edits
