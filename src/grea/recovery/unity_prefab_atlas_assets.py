"""Plan texture-only repairs for source-proven packed uGUI atlas Sprites.

The planner never edits provider assets or Unity YAML. It binds an exact source
Sprite to its same-bundle SpriteAtlas render-data entry and selected, hydrated
Texture2D, then records immutable target asset preconditions for an Editor owner.
"""
from pathlib import Path
import re

from .layout.standard import VERSION, V2_LAYOUT
from .io import inside, load, read, sha, write_json
from .sources.compiled import fail
from .unity_sprite import atlas_settings, rectangle_atlas_geometry

CONTRACT = "monkey-unity-prefab-atlas-rebind-plan/1"
MAX_SPRITES = 64
MAX_GRAPH = 64 * 1024 * 1024
MAX_ASSET = 16 * 1024 * 1024
GUID_RE = re.compile(rb"(?m)^guid: ([0-9a-f]{32})\s*$")
MAIN_ID_RE = re.compile(rb"(?m)^--- !u!213 &(-?[0-9]+)\s*$")


def _need(ok, code, loc, message):
    if not ok:
        fail(code, str(loc), message)


def _pin_file(path, expected, maximum=MAX_GRAPH):
    raw = read(path, max_bytes=maximum)
    _need(sha(raw) == expected, "ATLAS_ASSET_PIN_DRIFT", path, "Pinned input bytes changed")
    return raw


def _candidate_owned(manifest, relative_path, raw):
    rows = [row for row in manifest.get("files", []) if row.get("path") == relative_path]
    _need(len(rows) == 1 and rows[0].get("sha256") == sha(raw) and rows[0].get("bytes") == len(raw),
          "ATLAS_ASSET_CANDIDATE_PIN", relative_path, "Candidate manifest does not own these exact evidence bytes")


def _f32_array(data):
    """Return little-endian source index bytes from the parser's byte array."""
    _need(isinstance(data, list) and all(type(x) is int and 0 <= x <= 255 for x in data),
          "ATLAS_ASSET_SOURCE_GEOMETRY", "$", "Exact inline source index bytes required")
    return bytes(data).hex()


def _yaml_vector(raw, field):
    # A bounded value reader for known Unity native Sprite fields, not a YAML parser.
    text = raw.decode("utf-8", "strict")
    match = re.search(r"(?m)^\s*" + re.escape(field) + r":\s*\{([^}\n]+)\}", text)
    _need(match is not None, "ATLAS_ASSET_TARGET_SHAPE", field, "Expected inline Unity vector field")
    values = {}
    for pair in match.group(1).split(","):
        m = re.fullmatch(r"\s*([xyzw]):\s*(-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)\s*", pair)
        _need(m is not None, "ATLAS_ASSET_TARGET_SHAPE", field, "Unsupported vector serialization")
        values[m.group(1)] = float(m.group(2))
    return values


def _yaml_rect(raw, field):
    text = raw.decode("utf-8", "strict")
    inline = re.search(r"(?m)^\s*" + re.escape(field) + r":\s*\{([^}\n]+)\}", text)
    if inline:
        got = _yaml_vector(raw, field)
        if set(got) == {"x", "y", "z", "w"}:
            return dict(x=got["x"], y=got["y"], width=got["z"], height=got["w"])
        return got
    block = re.search(r"(?m)^\s*" + re.escape(field) + r":\s*\n((?:[ \t]+[^\n]*\n){1,8})", text)
    _need(block is not None, "ATLAS_ASSET_TARGET_SHAPE", field, "Expected bounded Unity Rect block")
    values = {}
    for line in block.group(1).splitlines():
        m = re.fullmatch(r"\s*(x|y|width|height):\s*(-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)\s*", line)
        if m:
            _need(m.group(1) not in values, "ATLAS_ASSET_TARGET_SHAPE", field, "Duplicate Rect coordinate")
            values[m.group(1)] = float(m.group(2))
    _need(set(values) == {"x", "y", "width", "height"}, "ATLAS_ASSET_TARGET_SHAPE", field,
          "Unity Rect must have exact x/y/width/height")
    return values


def _source_edge(graph, sid, location):
    rows = [e for e in graph.get("referenceEdges", []) if e.get("sourceObjectId") == sid and e.get("location") == location]
    _need(len(rows) == 1, "ATLAS_ASSET_SOURCE_EDGE", sid, "Expected one exact source reference edge")
    return rows[0]


def _target_identity(asset_path, meta_path):
    asset = read(asset_path, max_bytes=MAX_ASSET)
    meta = read(meta_path, max_bytes=1024 * 1024)
    guids = GUID_RE.findall(meta)
    ids = MAIN_ID_RE.findall(asset)
    _need(len(guids) == 1 and len(ids) == 1, "ATLAS_ASSET_TARGET_IDENTITY", asset_path,
          "Unique native Sprite GUID and local fileID required")
    return asset, meta, guids[0].decode("ascii"), int(ids[0])


def _verify_target_shape(asset, source, atlas_row, geometry):
    """Verify source identity against the existing native Sprite before pinning it."""
    rect = atlas_row["textureRect"]
    target_rect = _yaml_rect(asset, "m_Rect")
    def same_float32(left, right):
        import struct
        return set(left) == set(right) and all(struct.pack('<f', left[k]) == struct.pack('<f', right[k]) for k in left)
    _need(same_float32(target_rect, rect), "ATLAS_ASSET_TARGET_RECT", source["sourceObjectId"],
          "Existing target Sprite rect differs from exact atlas region")
    target_rd_rect = _yaml_rect(asset, "textureRect")
    _need(same_float32(target_rd_rect, rect), "ATLAS_ASSET_TARGET_RENDER_RECT", source["sourceObjectId"],
          "Existing target render rect differs from atlas render-data entry")
    _need(re.search(rb"(?m)^\s*settingsRaw:\s*67\s*$", asset) is not None,
          "ATLAS_ASSET_TARGET_SETTINGS", source["sourceObjectId"], "Target native Sprite is not the expected rectangle atlas record")
    # Source/target packed mesh bytes are retained by the prescribed texture-only edit.
    source_rd = source["data"]["m_RD"]
    source_indices = _f32_array(source_rd["m_IndexBuffer"])
    target_indices = re.findall(rb"(?m)^\s*m_IndexBuffer:\s*([0-9a-f]+)\s*$", asset)
    _need(target_indices and source_indices.encode() in target_indices, "ATLAS_ASSET_TARGET_MESH", source["sourceObjectId"],
          "Existing target index buffer differs from source Sprite mesh")
    source_vertex = source_rd["m_VertexData"]["m_DataSize"]["base64"]
    import base64
    source_vertex_hex = base64.b64decode(source_vertex, validate=True).hex().encode("ascii")
    vertex_rows = re.findall(rb"(?m)^\s*_typelessdata:\s*([0-9a-f]*)\s*$", asset)
    _need(vertex_rows and source_vertex_hex in vertex_rows, "ATLAS_ASSET_TARGET_MESH", source["sourceObjectId"],
          "Existing target vertex buffer differs from source Sprite mesh")
    return dict(targetRect=target_rect, targetMeshPreserved=True, sourceGeometrySha256=geometry["geometrySha256"])


def plan_packed_atlas_rebind(*, candidate_root, expected_manifest_sha256,
                             selected_pixel_manifest, selected_pixel_manifest_sha256,
                             source_sprite_ids, target_assets_root, provider_assets,
                             output_path, allow_trimmed_source_correction=False):
    """Create a pinned plan for exact selected Sprites; no source/target is modified.

    ``provider_assets`` is an explicit ``sourceObjectId -> {assetPath: ...}``
    result from the caller's full AssetBundle logical-path to candidate-relocation
    map. This routine
    validates each path's native GUID/localID, mesh, and atlas region, and never
    searches by basename or Sprite name.
    """
    _need(type(allow_trimmed_source_correction) is bool, 'ATLAS_ASSET_CORRECTION_MODE', '$', 'Explicit Boolean correction mode required')
    candidate = Path(candidate_root).resolve()
    manifest_raw = _pin_file(candidate / "manifest.json", expected_manifest_sha256, 32 * 1024 * 1024)
    manifest = load(manifest_raw)
    _need(manifest.get("contract") == "monkey-unity-prefab-recovery/1",
          "ATLAS_ASSET_CANDIDATE", candidate, "Exact Unity Prefab source candidate required")
    graph_path = candidate / "Analysis/Evidence/source-graph.json"
    graph_raw = read(graph_path, max_bytes=MAX_GRAPH)
    _candidate_owned(manifest, "Analysis/Evidence/source-graph.json", graph_raw)
    graph = load(graph_raw, max_nodes=8_000_000)
    _need(graph.get("contract") == "monkey-unity-prefab-source-graph/1"
          and graph.get("sourceUnityVersions") == ["2021.3.30f1"],
          "ATLAS_ASSET_CANDIDATE", graph_path, "Exact supported Unity 2021.3 source graph required")
    inputs_path = candidate / "Analysis/Evidence/source-inputs.json"
    inputs_raw = read(inputs_path, max_bytes=8 * 1024 * 1024)
    _candidate_owned(manifest, "Analysis/Evidence/source-inputs.json", inputs_raw)
    inputs = load(inputs_raw, max_nodes=200_000)
    relocation_path = candidate / "Analysis/Mappings/unity-relocation.json"
    relocation_raw = read(relocation_path, max_bytes=16 * 1024 * 1024)
    _candidate_owned(manifest, "Analysis/Mappings/unity-relocation.json", relocation_raw)
    relocation = load(relocation_raw, max_nodes=500_000)
    _need(relocation.get("layout") in (VERSION, V2_LAYOUT), "ATLAS_ASSET_RELOCATION", relocation_path,
          "Exact candidate relocation report required")
    objects = {o["sourceObjectId"]: o for o in graph.get("reachableObjects", [])}
    _need(len(objects) == len(graph.get("reachableObjects", [])), "ATLAS_ASSET_GRAPH", graph_path, "Duplicate source object IDs")
    pixels_path = Path(selected_pixel_manifest).resolve()
    pixel_raw = _pin_file(pixels_path, selected_pixel_manifest_sha256, 16 * 1024 * 1024)
    pixels = load(pixel_raw, max_nodes=200_000)
    _need(pixels.get("contract") == "unity-selected-texture-export/1" and pixels.get("status") == "exported"
          and pixels.get("nativeImport") == "not_run", "ATLAS_ASSET_PIXEL_MANIFEST", pixels_path,
          "Pinned selected local pixels manifest required; native import remains untested")
    selected = source_sprite_ids
    _need(isinstance(selected, list) and 1 <= len(selected) <= MAX_SPRITES and len(set(selected)) == len(selected)
          and all(isinstance(s, str) for s in selected), "ATLAS_ASSET_SELECTION", "$", "Select 1..64 unique exact source Sprite IDs")
    _need(isinstance(provider_assets, dict) and set(provider_assets) == set(selected),
          "ATLAS_ASSET_TARGET_SELECTION", "$", "Exact explicit target relocation path required for every selected Sprite")
    root = Path(target_assets_root).resolve()
    _need(root == candidate, "ATLAS_ASSET_TARGET_ROOT", root,
          "Target native assets must resolve inside this exact candidate via its relocation report")
    # Selected pixel rows are unique per full source Texture2D identity.
    pixel_rows = pixels.get("textures", [])
    plan_rows = []
    for sid in selected:
        source = objects.get(sid)
        _need(source is not None and source.get("type") == "Sprite", "ATLAS_ASSET_SOURCE_SPRITE", sid, "Exact source Sprite not in graph")
        ident = source.get("identity", {})
        inputs_match = [row for row in inputs if row.get("sourceSha256") == ident.get("containerSha256")]
        _need(len(inputs_match) == 1, "ATLAS_ASSET_SOURCE_INPUT", sid, "Unique source container full logical input pin required")
        source_input = inputs_match[0]
        _need(isinstance(source_input.get("sourcePath"), str) and source_input["sourcePath"],
              "ATLAS_ASSET_SOURCE_INPUT", sid, "Full source logical path is missing from source-inputs evidence")
        source_raw = read(Path(source_input["sourcePath"]), max_bytes=512 * 1024 * 1024)
        _need(sha(source_raw) == source_input["sourceSha256"], "ATLAS_ASSET_SOURCE_INPUT", sid,
              "Original source container bytes differ from source-inputs pin")
        atlas_edge = _source_edge(graph, sid, "$/m_SpriteAtlas")
        _need(atlas_edge.get("status") == "resolved" and atlas_edge.get("fileId") == "0", "ATLAS_ASSET_ATLAS_EDGE", sid,
              "SpriteAtlas must resolve within the same source serialized file")
        atlas = objects.get(atlas_edge.get("targetSourceObjectId"))
        _need(atlas is not None and atlas.get("type") == "SpriteAtlas" and atlas["identity"]["containerSha256"] == ident["containerSha256"]
              and atlas["identity"]["serializedFile"] == ident["serializedFile"], "ATLAS_ASSET_ATLAS_IDENTITY", sid,
              "Exact same-container SpriteAtlas required")
        packed_edges = [e for e in graph.get("referenceEdges", []) if e.get("sourceObjectId") == atlas["sourceObjectId"]
                        and e.get("targetSourceObjectId") == sid and re.fullmatch(r"\$/m_PackedSprites/[0-9]+", e.get("location", ""))]
        packed_ptrs = [p for p in atlas["data"].get("m_PackedSprites", [])
                       if isinstance(p, dict) and p.get("fileId") == "0" and str(p.get("pathId")) == str(ident.get("pathId"))]
        _need(len(packed_edges) == 1 and len(packed_ptrs) == 1, "ATLAS_ASSET_PACKED_SPRITE", sid,
              "Sprite must be an exact unique member of this source SpriteAtlas")
        key = source["data"].get("m_RenderDataKey")
        entries = [row for row in atlas["data"].get("m_RenderDataMap", []) if row[0] == key]
        _need(len(entries) == 1, "ATLAS_ASSET_RENDER_KEY", sid, "RenderDataKey must identify exactly one SpriteAtlas entry")
        render = entries[0][1]
        settings = atlas_settings(render.get("settingsRaw"))
        _need(settings["packingMode"] == "Rectangle" and settings["packingRotation"] == "None",
              "ATLAS_ASSET_UNSUPPORTED_PACKING", sid, "Only unrotated rectangle atlas regions are supported")
        texptr = render.get("texture", {})
        atlas_idx = atlas["data"]["m_RenderDataMap"].index(entries[0])
        tex_edge = _source_edge(graph, atlas["sourceObjectId"], f"$/m_RenderDataMap/{atlas_idx}/1/texture")
        _need(tex_edge.get("status") == "resolved" and tex_edge.get("fileId") == texptr.get("fileId") == "0",
              "ATLAS_ASSET_TEXTURE_EDGE", sid, "Atlas render data must resolve one exact Texture2D")
        texture = objects.get(tex_edge.get("targetSourceObjectId"))
        _need(texture is not None and texture.get("type") == "Texture2D", "ATLAS_ASSET_TEXTURE_IDENTITY", sid,
              "Exact source Texture2D object required")
        ti = texture["identity"]
        _need(ti["containerSha256"] == ident["containerSha256"] and ti["serializedFile"] == ident["serializedFile"]
              and str(ti["pathId"]) == str(texptr.get("pathId")), "ATLAS_ASSET_TEXTURE_IDENTITY", sid,
              "Render-data Texture2D identity differs from source graph")
        matches = [row for row in pixel_rows if row.get("source", {}).get("file") == ti["serializedFile"]
                   and str(row.get("source", {}).get("pathId")) == str(ti["pathId"])
                   and row.get("source", {}).get("sourceRawSha256") == texture.get("rawSha256")]
        _need(len(matches) == 1, "ATLAS_ASSET_PIXEL_CROSSWALK", sid,
              "Selected pixel manifest must pin this exact source Texture2D tuple and raw bytes")
        pixel = matches[0]
        hydration = pixel.get("hydration", {})
        _need(pixel.get("target", {}).get("nativeGuid") == "not-assigned" and pixel.get("target", {}).get("nativeImport") == "not_run"
              and hydration.get("rgbaRawSha256"), "ATLAS_ASSET_PIXEL_STATUS", sid, "Pixel evidence must remain accurately marked not natively imported")
        width, height = texture["data"].get("m_Width"), texture["data"].get("m_Height")
        _need(pixels.get("inputPins", {}).get("source") == ident["containerSha256"],
              "ATLAS_ASSET_PIXEL_SOURCE_PIN", sid, "Selected pixel manifest is not pinned to the exact source container")
        png_rel = pixel.get("target", {}).get("path")
        _need(isinstance(png_rel, str), "ATLAS_ASSET_PIXEL_PNG", sid, "Selected pixel PNG path is missing")
        png_path = inside(pixels_path.parent, png_rel)
        png_raw = read(png_path, max_bytes=128 * 1024 * 1024)
        _need(sha(png_raw) == pixel.get("target", {}).get("sha256")
              and len(png_raw) == pixel.get("target", {}).get("bytes"),
              "ATLAS_ASSET_PIXEL_PNG", sid, "Selected pixel PNG differs from its pinned manifest")
        region = render['textureRect']
        local = source['data']['m_Rect']
        trimmed = allow_trimmed_source_correction and (render.get('textureRectOffset') != dict(x=0, y=0)
            or local['width'] != region['width'] or local['height'] != region['height'])
        if trimmed:
            from .unity_prefab_trimmed_atlas import trimmed_rectangle_atlas_geometry
            geometry = trimmed_rectangle_atlas_geometry(source['data'], render, width, height)
        else:
            geometry = rectangle_atlas_geometry(source["data"], render, width, height)
            _need(render.get("textureRectOffset") == {"x": 0.0, "y": 0.0}, "ATLAS_ASSET_TRIM", sid,
                  "Trimmed atlas region requires an explicitly authorized correction profile")
        binding = provider_assets[sid]
        _need(isinstance(binding, dict) and set(binding) == {"assetPath"}, "ATLAS_ASSET_TARGET_PATH", sid,
              "Explicit relocation record must contain only assetPath")
        asset_rel = binding["assetPath"]
        _need(isinstance(asset_rel, str) and asset_rel.startswith("Assets/") and asset_rel.endswith(".asset"),
              "ATLAS_ASSET_TARGET_PATH", sid, "Explicit candidate relocation path under Assets required")
        asset_path = inside(root, asset_rel)
        meta_path = inside(root, asset_rel + ".meta")
        asset, meta, guid, local_id = _target_identity(asset_path, meta_path)
        _candidate_owned(manifest, asset_rel, asset)
        _candidate_owned(manifest, asset_rel + ".meta", meta)
        relocation_rows = [row for row in relocation.get("moves", []) if row.get("target") == asset_rel and row.get("kind") == "sprite"]
        _need(len(relocation_rows) == 1 and relocation_rows[0].get("guid") == guid,
              "ATLAS_ASSET_RELOCATION", asset_rel, "Candidate relocation must map this Sprite path/GUID uniquely")
        relocation_row = relocation_rows[0]
        _need(local_id == 21300000, "ATLAS_ASSET_TARGET_FILEID", asset_rel, "Existing native Sprite main localID must be 21300000")
        target_proof = _verify_target_shape(asset, source, render, geometry)
        if trimmed:
            target_proof['providerBeforeGeometry'] = dict(rect=_yaml_rect(asset, 'm_Rect'),
                offset=_yaml_vector(asset, 'm_Offset'), pivot=_yaml_vector(asset, 'm_Pivot'),
                textureRectOffset=_yaml_vector(asset, 'textureRectOffset'))
        _need(b"guid: 0000000deadbeef15deadf00d0000000" in asset,
              "ATLAS_ASSET_TARGET_REBIND", asset_rel, "Expected original known-dead Sprite texture binding before repair")
        plan_rows.append(dict(sourceSpriteId=sid, sourceSpriteIdentity=ident, sourceSpriteRawSha256=source["rawSha256"],
            sourceName=source["data"].get("m_Name"), sourceInputPath=source_input["sourcePath"],
            sourceInputSha256=source_input["sourceSha256"], sourceAtlasId=atlas["sourceObjectId"], sourceRenderDataKey=key,
            sourceTextureIdentity=ti, sourceTextureRawSha256=texture["rawSha256"], sourceTextureLogicalPath=hydration.get("logicalPath"),
            pixelManifestSha256=sha(pixel_raw), pixelPngPath=png_rel, pixelPngSha256=sha(png_raw), pixelPngBytes=len(png_raw),
            textureRgbaRawSha256=hydration["rgbaRawSha256"], textureDimensions=dict(width=width, height=height),
            atlasRenderData=render, geometry=geometry, providerAsset=dict(originalPath=relocation_row["source"], path=asset_rel, guid=guid, localId=local_id,
                assetSha256=sha(asset), assetBytes=len(asset), metaSha256=sha(meta), metaBytes=len(meta), **target_proof),
            candidateRelocation=dict(sourcePath=relocation_row["source"], targetPath=relocation_row["target"],
                guid=relocation_row["guid"], kind=relocation_row["kind"], reason=relocation_row.get("reason")),
            operation=dict(kind="native-source-derived-trim-correction-and-texture-rebind" if trimmed else "native-SerializedObject-render-texture-rebind",
                fields=(["m_Rect", "m_Offset", "m_Pivot", "m_RD.textureRectOffset"] if trimmed else []) + ["m_RD.texture", "m_AtlasRD.texture"],
                preserveAssetGuid=True, preserveLocalId=True, preserveRectBorderPivotPpuMeshAndMeta=True,
                createTextureGuid="Unity-generated", noYamlWrite=True)))
    output = Path(output_path).resolve()
    _need(output != candidate and not output.is_relative_to(candidate) and not candidate.is_relative_to(output),
          "ATLAS_ASSET_OUTPUT_OVERLAP", output, "Output must not overlap its candidate input")
    _need(not output.exists(), "ATLAS_ASSET_OUTPUT_EXISTS", output, "Plan output is immutable; use a fresh path")
    result = dict(schemaVersion=1, contract=CONTRACT, status="planned-not-applied", sourceVersion="2021.3.30f1",
        targetVersion=manifest.get("targetProfile"), candidateManifestSha256=sha(manifest_raw), sourceGraphSha256=sha(graph_raw),
        sourceInputsSha256=sha(inputs_raw), relocationSha256=sha(relocation_raw), selectedPixelManifestSha256=sha(pixel_raw), targetAssetsRoot=str(root),
        profile="unity-2021.3-trimmed-unrotated-rectangle-atlas-v1" if allow_trimmed_source_correction else "unity-2021.3-unrotated-rectangle-atlas-v1", assets=plan_rows,
        nativeEditorApplied=False, nativeAssetDatabaseGetClass="not_applicable", sourceCodeExecuted=False,
        limitation="This is an unapplied source-pinned native resource plan; no Editor import, save, reopen, or visual verification was run.")
    write_json(output, result)
    return result
