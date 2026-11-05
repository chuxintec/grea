"""Independent verification of controlled native stencil probes, not source frames."""
from __future__ import annotations

import hashlib
import io
import math
from pathlib import Path

from PIL import Image

from .io import diagnostic, load, read
from .prefab_static_mask_continuation import CONTRACT

PREFIX = 'Analysis/Readback/MaskClipping/'
RECT_METHOD = 'unity-ui-mask-stencil-rendertexture-v2'
IMAGE_METHOD = 'unity-ui-mask-alpha-stencil-rendertexture-v1'
METHOD = RECT_METHOD
_TRUE = ('supported', 'sourceGeometryVerified', 'sourceGeometryPreserved', 'sourceStatePreserved',
         'probeHostOwned', 'probeObjectsDestroyed', 'probeSceneCreated', 'probeSceneClosed',
         'renderCompleted', 'pixelReadbackVerified', 'insidePixelVerified', 'outsidePixelVerified',
         'maskInsidePointAccepted', 'childGraphicInsideAccepted',
         'probeMaskActiveInHierarchy', 'probeChildActiveInHierarchy', 'stimulusSpriteVerified',
         'stimulusObjectsDestroyed', 'verified')


def _file(root, relative):
    if not isinstance(relative, str) or not relative.startswith(PREFIX):
        raise ValueError('probe file is outside its owned directory')
    path = root / relative
    if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
        raise ValueError('probe file escapes candidate')
    if any(parent.is_symlink() for parent in path.parents if parent != root and parent.is_relative_to(root)):
        raise ValueError('probe file has a symlink ancestor')
    return path


def _project_file(root, relative):
    if (not isinstance(relative, str) or not relative.startswith('Assets/') or '\\' in relative or
            any(part in ('', '.', '..') for part in relative.split('/'))):
        raise ValueError('source texture path is unsafe')
    path = root / relative
    if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
        raise ValueError('source texture escapes candidate')
    if any(parent.is_symlink() for parent in path.parents if parent != root and parent.is_relative_to(root)):
        raise ValueError('source texture has a symlink ancestor')
    return path


def _pair(value, numeric=False):
    return isinstance(value, list) and len(value) == 2 and all(
        (type(x) in (int, float) and math.isfinite(x)) if numeric else type(x) is int for x in value)


def _close(a, b):
    return type(a) in (int, float) and math.isfinite(a) and abs(a-b) <= .001


def _texture_owner_row(owned_files, texture_path):
    if not isinstance(owned_files, dict):
        return None
    row = owned_files.get(texture_path)
    return row if isinstance(row, dict) else None


def _canonical_texture_id(source_id, sprite_frame_id):
    if not isinstance(source_id, str) or ':' not in source_id:
        raise ValueError('source Mask ID has no bundle namespace')
    bundle = source_id.split(':',1)[0]
    if not bundle or not isinstance(sprite_frame_id, str) or not sprite_frame_id:
        raise ValueError('source SpriteFrame identity is malformed')
    if sprite_frame_id.startswith(bundle + ':'):
        return sprite_frame_id
    if ':' in sprite_frame_id:
        raise ValueError('SpriteFrame bundle differs from its source Mask bundle')
    return bundle + ':' + sprite_frame_id


def _viewport_pixel(probe, prefix, width, height):
    pixel = probe.get(prefix + 'Pixel')
    viewport = probe.get(prefix + 'ViewportPoint')
    if (not _pair(pixel) or not all(0 <= x < width for x in pixel) or not isinstance(viewport, list) or
            len(viewport) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) for x in viewport) or
            viewport[2] <= 0 or pixel != [math.floor(viewport[0]*width), math.floor(viewport[1]*height)]):
        raise ValueError('sample pixel is outside the image or differs from viewport projection')
    return pixel


def _alpha_source_point(sample, image, node, threshold, enabled):
    texel = sample.get('sourceTexturePixel')
    if not _pair(texel) or not (0 <= texel[0] < image.width and 0 <= texel[1] < image.height):
        raise ValueError('source alpha texel is outside the pinned image')
    alpha_byte = image.convert('RGBA').getpixel((texel[0], image.height-1-texel[1]))[3]
    if type(sample.get('sourceAlphaByte')) is not int or sample['sourceAlphaByte'] != alpha_byte:
        raise ValueError('source alpha byte differs from the manifest-owned PNG')
    if not _close(sample.get('sourceAlpha'), alpha_byte/255.0):
        raise ValueError('normalized source alpha differs from the manifest-owned PNG')
    alpha_pass = alpha_byte/255.0 >= threshold
    if sample.get('sourceAlphaPass') is not alpha_pass:
        raise ValueError('source alpha comparison differs from the pinned threshold')
    expected_visible = (enabled is False) or alpha_pass
    if sample.get('expectedVisible') is not expected_visible:
        raise ValueError('source alpha expected visibility differs from the enabled/threshold contract')
    size, anchor = node.get('size'), node.get('anchor')
    if not _pair(size, True) or not _pair(anchor, True):
        raise ValueError('source node size or pivot is unavailable for alpha sample mapping')
    expected_local = [(texel[0]+.5)/image.width*size[0]-anchor[0]*size[0],
                      (texel[1]+.5)/image.height*size[1]-anchor[1]*size[1]]
    local = sample.get('localPoint')
    if not _pair(local, True) or not all(_close(x, y) for x, y in zip(local, expected_local)):
        raise ValueError('alpha sample local point differs from source texture and node geometry')
    return alpha_byte


def verify(instruction, readback, candidate_root=None, *, candidate=None, owned_files=None):
    """Return blocking diagnostics only for the explicitly opted-in Mask contract."""
    contract = instruction.get('staticMasks') or {}
    if contract.get('contract') != CONTRACT:
        return []
    gaps = []
    def gap(message, source_id=None):
        gaps.append(diagnostic('STATIC_MASK_CLIPPING_UNVERIFIED', source_id or PREFIX, message, source_id))
    selected_root = candidate if candidate is not None else candidate_root
    if selected_root is None:
        gap('Candidate root is required to verify pinned Mask probe outputs')
        return gaps
    root = Path(selected_root).resolve()
    specs = contract.get('masks')
    if not isinstance(specs, list) or any(not isinstance(x, dict) or not x.get('sourceId') for x in specs):
        gap('Source Mask contract rows are invalid'); return gaps
    expected = {x['sourceId']: x for x in specs}
    source = {x['sourceId']: x for x in instruction.get('components', []) if x.get('type') == 'cc.Mask'}
    if len(expected) != len(specs) or set(expected) != set(source):
        gap('Source Mask component denominator differs'); return gaps
    rows = [x for prefab in readback.get('sourcePrefabs', []) for x in (prefab.get('staticMaskFields') or [])]
    actual = {x.get('sourceId'): x for x in rows if isinstance(x, dict)}
    prefab_guids = {x.get('sourceId'): prefab.get('guid') for prefab in readback.get('sourcePrefabs', [])
                    for x in (prefab.get('staticMaskFields') or []) if isinstance(x, dict)}
    if len(actual) != len(rows) or set(actual) != set(expected):
        gap('Saved native Mask denominator differs'); return gaps
    descriptors = readback.get('staticMaskReadbackFiles')
    if not isinstance(descriptors, list) or any(not isinstance(x, dict) for x in descriptors):
        gap('Main readback does not pin the probe files'); return gaps
    pinned = {x.get('path'): x.get('sha256') for x in descriptors}
    if len(pinned) != len(descriptors):
        gap('Probe descriptor paths repeat'); return gaps
    used = set()
    nodes = {x['sourceId']: x for x in instruction.get('nodes', [])}
    for sid, spec in expected.items():
        try:
            row = actual[sid]
            if (row.get('verified') is not True or row.get('clipProbeVerified') is not True or
                row.get('persistentIdentityVerified') is not True or not row.get('persistentIdentityGuid') or
                type(row.get('persistentIdentityLocalFileId')) is not int or not row['persistentIdentityLocalFileId']):
                raise ValueError('saved Mask fields, persistent identity or probe result are absent')
            if row['persistentIdentityGuid'] != prefab_guids.get(sid):
                raise ValueError('persistent Mask identity belongs to a different prefab')
            probe = row.get('clipProbe')
            if not isinstance(probe, dict): raise ValueError('probe is absent')
            token = hashlib.sha256(sid.encode()).hexdigest()[:20]
            json_path = PREFIX + 'maskclip-' + token + '.json'
            png_path = PREFIX + 'maskclip-' + token + '.png'
            if probe.get('evidencePath') != json_path or probe.get('imagePath') != png_path:
                raise ValueError('probe paths are not bound to the exact source ID')
            for relative in (json_path, png_path):
                raw = read(_file(root, relative), max_bytes=8*1024*1024)
                if hashlib.sha256(raw).hexdigest() != pinned.get(relative):
                    raise ValueError('probe file SHA differs from main readback')
                used.add(relative)
            evidence = load(read(_file(root, json_path)), max_nodes=10000)
            if evidence != probe: raise ValueError('embedded probe differs from pinned JSON')
            expected_method = RECT_METHOD if spec.get('maskType') == 0 else IMAGE_METHOD if spec.get('maskType') == 2 else None
            if (expected_method is None or probe.get('sourceId') != sid or probe.get('node') != spec['node'] or
                    probe.get('method') != expected_method):
                raise ValueError('probe identity/method differs')
            if probe.get('stimulus') != 'owned-white-sprite-child-on-transparent-world-space-canvas':
                raise ValueError('controlled stimulus is absent')
            if any(probe.get(key) is not True for key in _TRUE) or probe.get('diagnostics'):
                raise ValueError('probe has incomplete execution/cleanup checks')
            if probe.get('sourceAppFrame') is not False or probe.get('sourceVisualParityClaimed') is not False:
                raise ValueError('controlled probe incorrectly claims source visual parity')
            if (probe.get('sourceMaskEnabled') is not spec['enabled'] or
                probe.get('sourceNodeActiveSelf') is not spec['sourceActiveSelf'] or
                probe.get('sourceNodeActiveInHierarchy') is not spec['sourceActive']):
                raise ValueError('source activity or mask state differs from contract')
            if spec['maskType'] not in (0, 2) or spec['inverted']:
                raise ValueError('mask semantics are outside the verified rect/image stencil profiles')
            expected_profile = 'rect' if spec['maskType'] == 0 else 'sprite-alpha-threshold'
            if probe.get('probeProfile') != expected_profile:
                raise ValueError('probe profile differs from mask type')
            enabled = spec['enabled']
            if (probe.get('status') != ('native-stencil-clipping-verified' if enabled else 'disabled-mask-no-clip-verified') or
                probe.get('stencilClipVerified') is not enabled or probe.get('disabledNoClipVerified') is not (not enabled) or
                probe.get('maskOutsidePointRejected') is not enabled or
                probe.get('childGraphicOutsideRejected') is not enabled or
                probe.get('disabledChildGraphicOutsideAccepted') is not (not enabled)):
                raise ValueError('enabled/disabled clipping semantics differ')
            node = nodes[spec['node']]; width, height = node['size']; px, py = node['anchor']
            inside = [(0.5-px)*width, (0.5-py)*height]
            outside = [(1.25-px)*width, inside[1]]
            if spec['maskType'] == 0:
                expected_inside_local = inside
            else:
                expected_inside_local = None
            for key, value in ((('insideLocalPoint', expected_inside_local), ('outsideLocalPoint', outside))):
                if value is None:
                    continue
                if not _pair(probe.get(key), True) or not all(_close(x,y) for x,y in zip(probe[key],value)):
                    raise ValueError('sample local point differs from frozen source geometry')
            png = read(_file(root, png_path), max_bytes=8*1024*1024)
            if hashlib.sha256(png).hexdigest() != probe.get('imageSha256'):
                raise ValueError('PNG SHA differs from probe')
            with Image.open(io.BytesIO(png)) as image:
                expected_probe_size = (256,256) if spec['maskType'] == 0 else (512,512)
                if image.format != 'PNG' or image.size != expected_probe_size or (probe.get('imageWidth'),probe.get('imageHeight')) != image.size:
                    raise ValueError('probe PNG dimensions/format differ')
                rgba = image.convert('RGBA')
                for label in ('inside', 'outside'):
                    point = _viewport_pixel(probe,label,image.width,image.height)
                    pixel = list(rgba.getpixel((point[0],image.height-1-point[1])))
                    if pixel != probe.get(label+'Rgba'): raise ValueError('sample RGBA differs from PNG')
                    white = pixel[3]>=245 and all(x>=230 for x in pixel[:3])
                    if not (pixel[3]<=12 if label=='outside' and enabled else white):
                        raise ValueError('actual PNG pixels fail inside/outside stencil expectation')
                if spec['maskType'] == 2:
                    expected_texture_id = _canonical_texture_id(sid,spec.get('spriteFrameUuid'))
                    texture = [row for row in instruction.get('textures', [])
                               if isinstance(row, dict) and row.get('id') == expected_texture_id]
                    if len(texture) != 1:
                        raise ValueError('image Mask source Sprite does not resolve to one planned TextureSpec')
                    texture_spec = texture[0]
                    texture_path = texture_spec.get('path')
                    if (not isinstance(texture_path, str) or texture_spec.get('id') != expected_texture_id or
                            probe.get('sourceTextureId') != texture_spec.get('id') or
                            probe.get('sourceTexturePath') != texture_path or probe.get('sourceSpriteFrameId') != spec.get('spriteFrameUuid')):
                        raise ValueError('image Mask source texture identity differs from the frozen TextureSpec')
                    owner_row = _texture_owner_row(owned_files, texture_path)
                    if (not isinstance(owner_row, dict) or owner_row.get('path') != texture_path or
                            owner_row.get('owner') != 'generated' or type(owner_row.get('bytes')) is not int or
                            not isinstance(owner_row.get('sha256'), str) or len(owner_row['sha256']) != 64):
                        raise ValueError('image Mask source texture lacks a generated-owned manifest row')
                    source_png = read(_project_file(root, texture_path), max_bytes=64*1024*1024)
                    source_sha = hashlib.sha256(source_png).hexdigest()
                    if (len(source_png) != owner_row['bytes'] or source_sha != owner_row['sha256'] or
                            source_sha != probe.get('sourceTextureSha256')):
                        raise ValueError('source texture PNG differs from its owned manifest and probe hash')
                    with Image.open(io.BytesIO(source_png)) as source_image:
                        if (source_image.format != 'PNG' or
                                source_image.size != tuple(int(v) for v in texture_spec.get('size', []))):
                            raise ValueError('source texture PNG dimensions differ from the TextureSpec')
                        if source_image.size != (probe.get('sourceTextureWidth'),probe.get('sourceTextureHeight')):
                            raise ValueError('source texture dimensions differ from the probe')
                        if (probe.get('sourceTextureFormat') != 'RGBA32' or
                                probe.get('sourceTextureImportMode') != 'Single' or
                                probe.get('sourceTextureMeshType') != 'FullRect' or
                                probe.get('sourceTextureCompression') != 'Uncompressed' or
                                probe.get('sourceTextureAlphaSource') != 'FromInput' or
                                probe.get('sourceTextureAlphaVerified') is not True or
                                probe.get('sourceMaskMaterialVerified') is not True or
                                probe.get('sourceMaterialGuid') != spec.get('unityMaskMaterialGuid') or
                                probe.get('sourceMaterialShaderPath') != spec.get('unityMaskShaderPath') or
                                probe.get('sourceMaterialShaderSha256') != spec.get('unityMaskShaderSha256') or
                                probe.get('sourceAlphaThreshold') != spec.get('alphaThreshold') or
                                probe.get('alphaDiscardPolicy') != 'discard-if-source-alpha-less-than-threshold' or
                                probe.get('alphaSamplesVerified') is not True):
                            raise ValueError('image Mask import, material, threshold or alpha-proof profile differs')
                        sprite_rows = [row for row in readback.get('sprites', []) if isinstance(row, dict) and
                                       row.get('id') == texture_spec.get('id')]
                        if (len(sprite_rows) != 1 or sprite_rows[0].get('guid') != probe.get('sourceTextureGuid') or
                                sprite_rows[0].get('guid') != probe.get('sourceSpriteGuid') or
                                sprite_rows[0].get('fileId') != probe.get('sourceSpriteLocalFileId') or
                                probe.get('sourceSpriteFrameId') != spec.get('spriteFrameUuid')):
                            raise ValueError('source Sprite persistent identity differs from saved sprite readback')
                        alpha_samples = probe.get('sourceAlphaSamples')
                        if not isinstance(alpha_samples, list) or len(alpha_samples) < 2:
                            raise ValueError('image Mask alpha threshold has no independent source-pixel sample set')
                        kinds = [row.get('kind') if isinstance(row, dict) else None for row in alpha_samples]
                        if len(kinds) != len(set(kinds)) or not {'opaque','transparent-zero'} <= set(kinds):
                            raise ValueError('image Mask alpha samples omit opaque/transparent source contrast')
                        for sample in alpha_samples:
                            alpha_byte=_alpha_source_point(sample,source_image,node,spec['alphaThreshold'],enabled)
                            if sample.get('kind')=='opaque' and alpha_byte!=255:
                                raise ValueError('opaque sample is not source alpha 255')
                            if sample.get('kind')=='transparent-zero' and alpha_byte!=0:
                                raise ValueError('transparent sample is not source alpha zero')
                            point = sample.get('pixel')
                            viewport = sample.get('viewportPoint')
                            if (not _pair(point) or not all(0 <= x < image.width for x in point) or
                                    not isinstance(viewport,list) or len(viewport)!=3 or
                                    any(type(x) not in (int,float) or not math.isfinite(x) for x in viewport) or
                                    viewport[2]<=0 or point != [math.floor(viewport[0]*image.width),math.floor(viewport[1]*image.height)]):
                                raise ValueError('source alpha sample output pixel differs from the probe projection')
                            actual_pixel=list(rgba.getpixel((point[0],image.height-1-point[1])))
                            if actual_pixel != sample.get('rgba'):
                                raise ValueError('source alpha sample RGBA differs from the probe PNG')
                            expected_visible=sample.get('expectedVisible')
                            if not (actual_pixel[3]>=245 and all(value>=230 for value in actual_pixel[:3]) if expected_visible
                                    else actual_pixel[3]<=12):
                                raise ValueError('native stencil output contradicts the independent source alpha threshold')
                        opaque_sample=next(row for row in alpha_samples if row.get('kind')=='opaque')
                        if any(not _close(a,b) for a,b in zip(probe.get('insideLocalPoint',[]),opaque_sample.get('localPoint',[]))) or \
                                probe.get('insidePixel') != opaque_sample.get('pixel') or probe.get('insideRgba') != opaque_sample.get('rgba'):
                            raise ValueError('primary inside pixel is not the independently proven opaque source sample')
        except (ValueError, KeyError, TypeError, OSError) as error:
            gap(str(error), sid)
    if set(pinned) != used:
        gap('Probe descriptor set differs from the exact source Mask evidence set')
    directory = root / PREFIX
    if directory.is_dir() and {p.relative_to(root).as_posix() for p in directory.iterdir() if p.suffix in ('.json','.png')} != set(pinned):
        gap('Unpinned probe files exist')
    return gaps
