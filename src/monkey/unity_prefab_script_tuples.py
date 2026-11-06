"""Replace only exact MonoScript PPtrs in text-serialized Unity objects."""
import re

_SCRIPT = re.compile(rb"^(  m_Script: )\{fileID: (-?\d+), guid: ([0-9a-f]{32}), type: (\d+)\}(\r?)$", re.M)


_CURVE_SCRIPT = re.compile(rb"^( {4,6}script: )\{fileID: (-?\d+), guid: ([0-9a-f]{32}), type: (\d+)\}(\r?)$", re.M)


def rebind(data, bindings):
    if not data.startswith(b"%YAML"):
        return data
    def replace(match):
        source = (match[3].decode(), int(match[2]), int(match[4]))
        target = bindings.get(source)
        if target is None:
            return match[0]
        guid, local_id, kind = target
        if not re.fullmatch(r"[0-9a-f]{32}", guid) or not local_id or kind != 3:
            raise ValueError("Invalid target MonoScript tuple")
        return match[1] + f"{{fileID: {local_id}, guid: {guid}, type: {kind}}}".encode() + match[5]
    if re.search(rb"^--- !u!74 &-?\d+\r?\nAnimationClip:", data, re.M):
        data = _CURVE_SCRIPT.sub(replace, data)
    return _SCRIPT.sub(replace, data)
