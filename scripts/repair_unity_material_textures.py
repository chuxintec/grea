"""Resolve broken Material texture slots from source edges and exact cached ASTC payloads."""
import argparse
import base64
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from PIL import Image
from monkey.normalize import open_texture


def unique_materials(graph):
    by_name = defaultdict(list)
    for obj in graph["reachableObjects"]:
        if obj["type"] == "Material" and obj.get("data"):
            by_name[obj["data"]["m_Name"]].append(obj)
    return {name: items[0] for name, items in by_name.items() if len(items) == 1}


def restore(graph, project, cache):
    objects = {obj["sourceObjectId"]: obj for obj in graph["reachableObjects"]}
    edges = {(edge["sourceObjectId"], edge["location"]): edge.get("targetSourceObjectId")
             for edge in graph["referenceEdges"]}
    materials = unique_materials(graph)
    payloads = defaultdict(list)
    for f in cache.rglob("*.txt"):
        payloads[f.stem].append(f)
    targets = defaultdict(list)
    for path in (project / "Assets").rglob("*.mat"):
        text = path.read_text()
        name = re.search(r"^  m_Name: (.+)$", text, re.M)
        if name:
            targets[name[1]].append((path, text))
    repaired = []
    for name, files in targets.items():
        if len(files) != 1 or name not in materials:
            continue
        path, text = files[0]
        source = materials[name]
        for index, (slot, _) in enumerate(source["data"]["m_SavedProperties"]["m_TexEnvs"]):
            pattern = re.compile(r"(?m)^(\s*(?:- )?" + re.escape(slot) +
                                 r":\n\s*m_Texture: )\{fileID: \d+, guid: 0000000deadbeef15deadf00d0000000, type: 2\}")
            if len(pattern.findall(text)) != 1:
                continue
            sid = edges.get((source["sourceObjectId"], f"$/m_SavedProperties/m_TexEnvs/{index}/1/m_Texture"))
            obj = objects.get(sid)
            if not obj or obj["type"] != "Texture2D":
                continue
            tex = obj["data"]
            marker = re.fullmatch(rb".(.+)_\d+###", base64.b64decode(tex["image data"]["base64"]), re.S)
            if not marker:
                continue
            candidates = payloads.get(marker[1].decode(), [])
            if len(candidates) != 1:
                continue
            raw = candidates[0].read_bytes()
            size = (int.from_bytes(raw[7:10], "little"), int.from_bytes(raw[10:13], "little"))
            if raw[:4] != bytes.fromhex("13aba15c") or size != (tex["m_Width"], tex["m_Height"]):
                continue
            guid = hashlib.sha256(b"monkey:material-texture:" + sid.encode() + raw).hexdigest()[:32]
            image_path = project / "Assets/Game/Content/RecoveredTextures" / (guid + ".png")
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image = open_texture(raw, ".astc").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            image.save(image_path)
            meta = Path(str(image_path) + ".meta")
            meta.write_text(f"fileFormatVersion: 2\nguid: {guid}\nTextureImporter:\n  serializedVersion: 12\n"
                            "  mipmaps:\n    enableMipMap: 0\n  textureType: 0\n  nPOTScale: 0\n")
            text = pattern.sub(lambda m: m[1] + f"{{fileID: 2800000, guid: {guid}, type: 3}}", text)
            path.write_text(text)
            repaired.append(dict(material=str(path.relative_to(project)), slot=slot, sourceTexture=sid,
                                 cacheSha256=hashlib.sha256(raw).hexdigest()))
    return repaired


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("graph", "project", "cache", "report"):
        parser.add_argument("--" + option, type=Path, required=True)
    args = parser.parse_args()
    args.report.write_text(json.dumps(restore(json.loads(args.graph.read_bytes()), args.project, args.cache), indent=2))
