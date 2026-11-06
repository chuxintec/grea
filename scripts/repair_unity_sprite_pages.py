"""Repair missing sprite atlas pointers from a matching, intact Unity export."""
import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


MISSING = "texture: {fileID: 2800000, guid: 0000000deadbeef15deadf00d0000000, type: 2}"
POINTER = re.compile(r"texture: \{fileID: 2800000, guid: ([a-f0-9]{32}), type: 3\}")
EMPTY_SHAPES = "    m_BlendShapes:\n      vertices: []\n      shapes: []\n      channels: []\n      fullWeights: []\n"


def sprites(folder):
    for path in folder.rglob("*.asset"):
        with path.open("rb") as stream:
            if b"--- !u!213 " not in stream.read(110):
                continue
        data = path.read_text()
        key = re.search(r"m_RenderDataKey:\s*([a-f0-9]{32}: -?\d+)", data)
        render = data.partition("  m_RD:\n")[2].partition("  m_AtlasRD:")[0]
        pointer, separator, geometry = render.partition("    alphaTexture:")
        if key and separator:
            yield path, data, (key[1], geometry.replace(EMPTY_SHAPES, "")), pointer


def restore(project, donor):
    images = defaultdict(list)
    for path in donor.rglob("*.png.meta"):
        guid = re.search(r"^guid: ([a-f0-9]{32})$", path.read_text(), re.M)
        if guid and path.with_suffix("").is_file():
            images[guid[1]].append(path.with_suffix(""))
    matches = defaultdict(set)
    for _, _, key, pointer in sprites(donor):
        ref = POINTER.search(pointer)
        if ref:
            matches[key].update(images[ref[1]])
    log = []
    for path, data, key, pointer in sprites(project / "Assets"):
        if MISSING not in pointer or len(matches[key]) != 1:
            continue
        source, = matches[key]
        pixels = source.read_bytes()
        meta = Path(str(source) + ".meta").read_text()
        digest = hashlib.sha256(b"monkey:sprite-page\0" + pixels + meta.encode()).hexdigest()
        target = project / "Assets/Game/Content/RecoveredAtlases" / (digest[:32] + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        new_meta = re.sub(r"^guid: [a-f0-9]{32}$", "guid: " + digest[:32], meta, count=1, flags=re.M)
        for output, content in ((target, pixels), (Path(str(target) + ".meta"), new_meta.encode())):
            if output.exists() and output.read_bytes() != content:
                raise ValueError(f"Conflicting recovered page: {output}")
            if not output.exists():
                output.write_bytes(content)
        repaired = pointer.replace(MISSING, f"texture: {{fileID: 2800000, guid: {digest[:32]}, type: 3}}", 1)
        path.write_text(data.replace("  m_RD:\n" + pointer, "  m_RD:\n" + repaired, 1))
        log.append({"sprite": str(path.relative_to(project)), "source": str(source), "page": str(target.relative_to(project))})
    return log


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("project", "donor", "report"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    args.report.write_text(json.dumps(restore(args.project, args.donor), indent=2))
