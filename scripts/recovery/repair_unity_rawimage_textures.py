"""Rebind missing RawImage textures from a Unity source graph and ASTC cache."""
import argparse
import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path
import re

from PIL import Image
from grea.recovery.normalize import open_texture

BROKEN = re.compile(r"(?m)^  m_Texture: \{fileID: \d+, guid: 0000000deadbeef15deadf00d0000000, type: 2\}$")
DOCUMENT = re.compile(r"(?ms)^--- !u!(\d+) &(-?\d+)\n(.*?)(?=^--- !u!|\Z)")


def destination(project, relative):
    path = (project / relative).resolve()
    if not path.is_relative_to((project / "Assets").resolve()) or path.suffix != ".prefab":
        raise ValueError(f"Expected a project prefab: {relative}")
    return path


def restore(graph, project, cache, roots):
    objects = {o["sourceObjectId"]: o for o in graph["reachableObjects"]}
    nodes = {n["sourceObjectId"]: n for n in graph["gameObjects"]}
    owners = {c["sourceObjectId"]: n for n in nodes.values() for c in n["orderedComponents"]}
    targets = {}
    for rel in roots:
        path = destination(project, rel)
        targets.setdefault(path.stem, []).append(path)
    cache_files = {}
    for path in cache.rglob("*.txt"):
        cache_files.setdefault(path.stem, []).append(path)
    changes = []
    for edge in graph["referenceEdges"]:
        source = edge["sourceObjectId"]
        target = objects.get(edge.get("targetSourceObjectId"))
        if edge["location"] != "$/m_Texture" or source not in owners or not target or target["type"] != "Texture2D":
            continue
        owner = owners[source]
        root = owner
        while root.get("parentSourceObjectId") in nodes:
            root = nodes[root["parentSourceObjectId"]]
        paths = targets.get(root["name"], [])
        if len(paths) != 1:
            continue
        prefab = paths[0]
        yaml = prefab.read_text()
        docs = DOCUMENT.findall(yaml)
        name_line = "  m_Name: " + owner["name"]
        matches = [local for kind, local, body in docs if kind == "1" and name_line in body.splitlines()]
        if len(matches) != 1:
            continue
        pointer = "  m_GameObject: {fileID: " + matches[0] + "}"
        bodies = [body for kind, _, body in docs if kind == "114" and pointer in body.splitlines() and BROKEN.search(body)]
        if len(bodies) != 1:
            continue
        texture = target["data"]
        marker = re.fullmatch(rb".(.+)_\d+###", base64.b64decode(texture.get("image data", {}).get("base64", "")), re.S)
        if not marker:
            continue
        token = marker[1].decode()
        files = cache_files.get(token, [])
        if len(files) != 1:
            continue
        payload = files[0].read_bytes()
        dimensions = (int.from_bytes(payload[7:10], "little"), int.from_bytes(payload[10:13], "little"))
        if payload[:4] != bytes.fromhex("13aba15c") or dimensions != (texture["m_Width"], texture["m_Height"]):
            continue
        digest = hashlib.sha256(payload).hexdigest()
        guid = digest[:32]
        output = project / "Assets/Game/Content/RecoveredTextures" / (guid + ".png")
        output.parent.mkdir(parents=True, exist_ok=True)
        buffer = BytesIO()
        open_texture(payload, ".astc").transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(buffer, format="PNG")
        if output.exists() and output.read_bytes() != buffer.getvalue():
            raise ValueError(f"Conflicting recovered texture: {output}")
        meta = Path(str(output) + ".meta")
        if meta.exists() and f"guid: {guid}" not in meta.read_text().splitlines():
            raise ValueError(f"Conflicting recovered texture GUID: {meta}")
        if not output.exists():
            output.write_bytes(buffer.getvalue())
        if not meta.exists():
            meta.write_text(f"fileFormatVersion: 2\nguid: {guid}\nTextureImporter:\n  serializedVersion: 12\n"
                        "  mipmaps:\n    enableMipMap: 0\n  textureType: 0\n  nPOTScale: 0\n")
        body, = bodies
        fixed = BROKEN.sub(f"  m_Texture: {{fileID: 2800000, guid: {guid}, type: 3}}", body)
        prefab.write_text(yaml.replace(body, fixed, 1))
        changes.append({"prefab": str(prefab.relative_to(project)), "node": owner["name"], "token": token, "sha256": digest})
    return changes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("graph", "project", "cache", "roots", "report"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    rows = restore(json.loads(args.graph.read_bytes()), args.project.resolve(), args.cache, args.roots.read_text().splitlines())
    args.report.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
