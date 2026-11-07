"""Persistent PPtr storage types for source-to-native visual asset handoff."""
from pathlib import PurePosixPath


_NATIVE = {'.asset', '.mat', '.anim', '.controller', '.overridecontroller', '.spriteatlas', '.shadervariants', '.unity'}
_IMPORTED = {'.shader', '.png', '.tga', '.jpg', '.jpeg', '.exr', '.hdr', '.ttf', '.otf', '.fbx', '.cs', '.dll', '.prefab'}


def reference_type(target_path):
    """A recovered Shader.asset and its editable ShaderLab have different PPtr types.

    The caller must supply the verified destination path, not the old extension.
    Unknown importers are rejected instead of inheriting a stale provider type.
    """
    if target_path in ('Resources/unity_builtin_extra', 'Library/unity default resources'):
        return 0
    suffix = PurePosixPath(target_path).suffix.lower()
    if suffix in _NATIVE:
        return 2
    if suffix in _IMPORTED:
        return 3
    raise ValueError(f'Unknown native reference storage: {target_path}')


def remap_pointers(raw, targets):
    """Replace provider main-object references with verified native object identities.

    targets maps provider GUID to (provider main fileID, native GUID, native
    local fileID, native asset path). Unknown GUIDs are left for the caller's
    dependency gate; known same-file subobjects retain their original local ID.
    """
    import re
    pattern = re.compile(rb'\{fileID: (-?\d+), guid: ([a-f0-9]{32}), type: (\d+)\}')

    def remap(match):
        target = targets.get(match[2].decode())
        if target is None:
            return match[0]
        original, guid, local, path = target
        if not re.fullmatch('[a-f0-9]{32}', guid) or not local:
            raise ValueError('Native GUID/local ID required for reference remapping')
        file_id = local if int(match[1]) == original else int(match[1])
        return f'{{fileID: {file_id}, guid: {guid}, type: {reference_type(path)}}}'.encode()

    return pattern.sub(remap, raw)
