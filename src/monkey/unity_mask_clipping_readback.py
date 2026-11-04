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
METHOD = 'unity-ui-mask-stencil-rendertexture-v1'
_TRUE = ('supported', 'sourceGeometryVerified', 'sourceGeometryPreserved', 'sourceStatePreserved',
         'probeHostOwned', 'probeObjectsDestroyed', 'probeSceneCreated', 'probeSceneClosed',
         'renderCompleted', 'pixelReadbackVerified', 'insidePixelVerified', 'outsidePixelVerified',
         'maskInsidePointAccepted', 'childGraphicInsideAccepted',
         'probeMaskActiveInHierarchy', 'probeChildActiveInHierarchy', 'verified')


def _file(root, relative):
    if not isinstance(relative, str) or not relative.startswith(PREFIX):
        raise ValueError('probe file is outside its owned directory')
    path = root / relative
    if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
        raise ValueError('probe file escapes candidate')
    if any(parent.is_symlink() for parent in path.parents if parent != root and parent.is_relative_to(root)):
        raise ValueError('probe file has a symlink ancestor')
    return path


def _pair(value, numeric=False):
    return isinstance(value, list) and len(value) == 2 and all(
        (type(x) in (int, float) and math.isfinite(x)) if numeric else type(x) is int for x in value)


def _close(a, b):
    return type(a) in (int, float) and math.isfinite(a) and abs(a-b) <= .001


def verify(instruction, readback, candidate_root):
    """Return blocking diagnostics only for the explicitly opted-in Mask contract."""
    contract = instruction.get('staticMasks') or {}
    if contract.get('contract') != CONTRACT:
        return []
    gaps = []
    def gap(message, source_id=None):
        gaps.append(diagnostic('STATIC_MASK_CLIPPING_UNVERIFIED', source_id or PREFIX, message, source_id))
    root = Path(candidate_root).resolve()
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
            if probe.get('sourceId') != sid or probe.get('node') != spec['node'] or probe.get('method') != METHOD:
                raise ValueError('probe identity/method differs')
            if probe.get('stimulus') != 'temporary-white-child-image-on-transparent-world-space-canvas':
                raise ValueError('controlled stimulus is absent')
            if any(probe.get(key) is not True for key in _TRUE) or probe.get('diagnostics'):
                raise ValueError('probe has incomplete execution/cleanup checks')
            if probe.get('sourceAppFrame') is not False or probe.get('sourceVisualParityClaimed') is not False:
                raise ValueError('controlled probe incorrectly claims source visual parity')
            if (probe.get('sourceMaskEnabled') is not spec['enabled'] or
                probe.get('sourceNodeActiveSelf') is not spec['sourceActiveSelf'] or
                probe.get('sourceNodeActiveInHierarchy') is not spec['sourceActive']):
                raise ValueError('source activity or mask state differs from contract')
            if spec['maskType'] != 0 or spec['inverted']:
                raise ValueError('mask semantics are outside the stencil probe profile')
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
            for key, value in (('insideLocalPoint', inside), ('outsideLocalPoint', outside)):
                if not _pair(probe.get(key), True) or not all(_close(x,y) for x,y in zip(probe[key],value)):
                    raise ValueError('sample local point differs from frozen source geometry')
            png = read(_file(root, png_path), max_bytes=8*1024*1024)
            if hashlib.sha256(png).hexdigest() != probe.get('imageSha256'):
                raise ValueError('PNG SHA differs from probe')
            with Image.open(io.BytesIO(png)) as image:
                if image.format != 'PNG' or image.size != (256,256) or (probe.get('imageWidth'),probe.get('imageHeight')) != image.size:
                    raise ValueError('probe PNG dimensions/format differ')
                rgba = image.convert('RGBA')
                for label in ('inside', 'outside'):
                    point = probe.get(label+'Pixel'); viewport = probe.get(label+'ViewportPoint')
                    if (not _pair(point) or not all(0 <= x < 256 for x in point) or not isinstance(viewport,list) or
                        len(viewport)!=3 or any(type(x) not in (int,float) or not math.isfinite(x) for x in viewport) or
                        viewport[2]<=0 or point != [math.floor(viewport[0]*256),math.floor(viewport[1]*256)]):
                        raise ValueError('sample pixel is outside the image or differs from viewport projection')
                    pixel = list(rgba.getpixel((point[0],255-point[1])))
                    if pixel != probe.get(label+'Rgba'): raise ValueError('sample RGBA differs from PNG')
                    white = pixel[3]>=245 and all(x>=230 for x in pixel[:3])
                    if not (pixel[3]<=12 if label=='outside' and enabled else white):
                        raise ValueError('actual PNG pixels fail inside/outside stencil expectation')
        except (ValueError, KeyError, TypeError, OSError) as error:
            gap(str(error), sid)
    if set(pinned) != used:
        gap('Probe descriptor set differs from the exact source Mask evidence set')
    directory = root / PREFIX
    if directory.is_dir() and {p.relative_to(root).as_posix() for p in directory.iterdir() if p.suffix in ('.json','.png')} != set(pinned):
        gap('Unpinned probe files exist')
    return gaps
