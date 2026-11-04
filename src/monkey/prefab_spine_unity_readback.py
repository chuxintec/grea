"""Verify saved, per-Prefab Unity Spine static readbacks.

This verifier only compares frozen plans, saved JSON readbacks and Unity meta
identities. It never invokes Unity or executes recovered source behavior.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from .io import diagnostic, inside, read


_STAGE_CONTRACT = 'monkey-spine-native-stage/1'
_BINDING_CONTRACT = 'monkey-spine-native-binding/1'
_PROFILE = 'cocos24-builtin-spine-material-v1'
_UI_SHADER = 'Monkey/SpineSourceGraphicProfile/Colored'
_SDK_INSTRUCTIONS = 'Spine.Unity.SkeletonRendererInstruction'
_TEXTURE_METHOD = 'serialized RawImage.texture identity plus exact Spine callback SetMaterial(material, texture); Unity CanvasRenderer exposes no public texture getter'
_SPINE_BLEND_MODES = {'normal', 'additive', 'multiply', 'screen'}
_RENDERER_TYPES = {
    'SkeletonGraphic': 'Spine.Unity.SkeletonGraphic',
    'SkeletonAnimation': 'Spine.Unity.SkeletonAnimation',
}
_ALLOWED_SOURCE_GAPS = {
    ('playTimes', 'source_only_no_same_component_field'),
    ('caching', 'source_only_runtime_cache_mapping_unresolved'),
}
_GUID = re.compile(r'^[0-9a-fA-F]{32}$')
_SHA = re.compile(r'^[0-9a-f]{64}$')


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _json_file(path: Path):
    try:
        value = json.loads(read(path, max_bytes=128 * 1024 * 1024).decode('utf-8-sig'))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _relative_file(root: Path, relative: str):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
        return None
    try:
        path = inside(root, relative)
    except (OSError, ValueError):
        return None
    return path if path.is_file() else None


def _guid_from_meta(root: Path, asset_path: str):
    if not isinstance(asset_path, str) or not asset_path or Path(asset_path).is_absolute() or '..' in Path(asset_path).parts:
        return None
    meta = _relative_file(root, asset_path + '.meta')
    if meta is None:
        return None
    try:
        matches = [line[6:].strip() for line in read(meta, max_bytes=1024 * 1024).decode('utf-8-sig').splitlines()
                   if line.startswith('guid: ')]
    except (OSError, UnicodeError):
        return None
    if len(matches) != 1 or not _GUID.fullmatch(matches[0]):
        return None
    return matches[0].lower()


def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _close(actual, expected, tolerance=1e-6):
    return _finite_number(actual) and _finite_number(expected) and abs(actual - expected) <= tolerance


def _source_color_matches(actual, expected):
    return (isinstance(actual, list) and len(actual) == 4 and isinstance(expected, list) and len(expected) == 4 and
            all(_close(a, e, 1e-3) for a, e in zip(actual, expected)))


def _meta_error(root: Path, asset_path: str, actual_guid: str, path_label: str):
    if not isinstance(actual_guid, str) or not _GUID.fullmatch(actual_guid):
        return f'{path_label} readback GUID is missing or malformed'
    if _relative_file(root, asset_path) is None:
        return f'{path_label} target asset path is missing: {asset_path}'
    expected_guid = _guid_from_meta(root, asset_path)
    if expected_guid is None or expected_guid != actual_guid.lower():
        return f'{path_label} readback GUID differs from target meta: {asset_path}'
    return None


def _verify_data_asset(root: Path, stage_asset: dict, actual: dict, ui_shader: dict, owner: str):
    failures = []
    source_id = stage_asset.get('sourceAssetId')
    factory = stage_asset.get('factoryInput')
    if not isinstance(factory, dict) or factory.get('sourceAssetId') != source_id:
        return [f'{owner}: malformed frozen Spine data asset spec {source_id}']
    if actual.get('sourceAssetId') != source_id:
        failures.append(f'{owner}: data asset source ID mismatch {source_id}')

    path_pins = (
        ('skeletonDataAssetPath', 'skeletonDataAssetPath', 'skeletonDataAssetGuid', 'skeleton data asset'),
        ('atlasAssetPath', 'atlasAssetPath', 'atlasAssetGuid', 'Spine atlas asset'),
    )
    for expected_key, actual_key, guid_key, label in path_pins:
        expected_path = factory.get(expected_key)
        actual_path = actual.get(actual_key)
        if not isinstance(expected_path, str) or actual_path != expected_path:
            failures.append(f'{owner}: {label} path differs for {source_id}')
        else:
            error = _meta_error(root, expected_path, actual.get(guid_key), label)
            if error:
                failures.append(f'{owner}: {error}')

    for key in ('skeletonSha256', 'atlasSha256', 'expectedSpineVersion'):
        actual_key = 'spineVersion' if key == 'expectedSpineVersion' else key
        if factory.get(key) != actual.get(actual_key):
            failures.append(f'{owner}: Spine data asset {actual_key} differs for {source_id}')
    if not _close(actual.get('scale'), factory.get('scale')) or actual.get('scaleVerified') is not True:
        failures.append(f'{owner}: Spine data asset scale is unverified for {source_id}')
    if actual.get('premultipliedAlpha') is not factory.get('premultipliedAlpha'):
        failures.append(f'{owner}: Spine data asset PMA flag differs for {source_id}')
    if actual.get('sourceMaterialProfile') != _PROFILE:
        failures.append(f'{owner}: source material profile differs for {source_id}')
    if (actual.get('profileShaderName') != factory.get('shaderName') or
            actual.get('profileShaderSha256') != factory.get('shaderSha256')):
        failures.append(f'{owner}: Spine profile shader identity differs for {source_id}')
    if (factory.get('graphicShaderName') != ui_shader.get('shaderName') or
            factory.get('graphicShaderSha256') != ui_shader.get('sha256') or
            factory.get('graphicShaderAssetPath') != ui_shader.get('targetPath') or
            actual.get('uiGraphicShaderName') != ui_shader.get('shaderName') or
            actual.get('uiGraphicShaderSha256') != ui_shader.get('sha256') or
            actual.get('uiGraphicShaderVerified') is not True):
        failures.append(f'{owner}: Spine Unity UI Graphic shader identity/readback differs for {source_id}')
    for flag in ('nativeAssetIdentityVerified', 'savedSourceReferencesVerified',
                 'sourceProfileMaterialsVerified', 'staticDataVerified'):
        if actual.get(flag) is not True:
            failures.append(f'{owner}: data asset {flag} is not verified for {source_id}')
    if actual.get('gaps') != []:
        failures.append(f'{owner}: data asset has readback gaps for {source_id}')
    for key in ('requiredAnimations', 'requiredSkins'):
        required = factory.get(key)
        found = actual.get('animations' if key == 'requiredAnimations' else 'skins')
        if (not isinstance(required, list) or not isinstance(found, list) or
                any(not isinstance(item, str) or item not in found for item in required)):
            failures.append(f'{owner}: required Spine {key} are not present for {source_id}')

    expected_pages = factory.get('pages')
    actual_pages = actual.get('pages')
    if not isinstance(expected_pages, list) or not isinstance(actual_pages, list) or len(expected_pages) != len(actual_pages):
        failures.append(f'{owner}: Spine atlas page count differs for {source_id}')
        return failures
    for index, (expected_page, actual_page) in enumerate(zip(expected_pages, actual_pages)):
        if not isinstance(expected_page, dict) or not isinstance(actual_page, dict):
            failures.append(f'{owner}: malformed Spine atlas page row {source_id}[{index}]')
            continue
        page_label = f'{source_id}[{index}]'
        for expected_key, actual_key in (
            ('sourceAtlasPage', 'sourceAtlasPage'), ('nativeAtlasPage', 'nativeAtlasPage'),
            ('sourceTextureSourceId', 'sourceTextureSourceId'),
        ):
            if expected_page.get(expected_key) != actual_page.get(actual_key):
                failures.append(f'{owner}: Spine atlas page identity differs {page_label}/{expected_key}')
        for path_key, guid_key, label in (
            ('textureAssetPath', 'textureGuid', 'Spine page texture'),
            ('normalMaterialAssetPath', 'normalMaterialGuid', 'Spine page material'),
        ):
            asset_path = expected_page.get(path_key)
            error = _meta_error(root, asset_path, actual_page.get(guid_key), label)
            if error:
                failures.append(f'{owner}: {error} ({page_label})')
        if actual_page.get('referencesVerified') is not True:
            failures.append(f'{owner}: Spine page native references are unverified {page_label}')
        expected_graphic_path = expected_page.get('graphicNormalMaterialAssetPath')
        if actual_page.get('graphicNormalMaterialPath') != expected_graphic_path:
            failures.append(f'{owner}: Spine Graphic normal material path differs {page_label}')
        graphic_normal_guid = _guid_from_meta(root, expected_graphic_path)
        if (graphic_normal_guid is None or actual_page.get('graphicNormalMaterialGuid') != graphic_normal_guid):
            failures.append(f'{owner}: Spine Graphic normal material GUID differs {page_label}')
        variants = expected_page.get('variants')
        if not isinstance(variants, list):
            failures.append(f'{owner}: malformed Spine material variants {page_label}')
            continue
        expected_modes = [variant.get('blendMode') for variant in variants if isinstance(variant, dict)]
        expected_guids = [_guid_from_meta(root, variant.get('materialAssetPath')) for variant in variants
                          if isinstance(variant, dict)]
        expected_graphic_paths = [variant.get('graphicMaterialAssetPath') for variant in variants
                                  if isinstance(variant, dict)]
        expected_graphic_guids = [_guid_from_meta(root, path) for path in expected_graphic_paths]
        if (len(expected_modes) != len(variants) or len(expected_guids) != len(variants) or
                len(expected_graphic_paths) != len(variants) or any(guid is None for guid in expected_guids) or
                any(guid is None for guid in expected_graphic_guids) or
                any(mode not in {'additive', 'multiply', 'screen'} for mode in expected_modes) or
                len(set(expected_modes)) != len(expected_modes)):
            failures.append(f'{owner}: frozen Spine variant material identity is incomplete {page_label}')
        if actual_page.get('variantModes') != expected_modes or actual_page.get('variantMaterialGuids') != expected_guids:
            failures.append(f'{owner}: Spine variant material GUID/order differs {page_label}')
        if (actual_page.get('graphicVariantMaterialPaths') != expected_graphic_paths or
                actual_page.get('graphicVariantMaterialGuids') != expected_graphic_guids):
            failures.append(f'{owner}: Spine Graphic variant material path/GUID order differs {page_label}')
    return failures


def _verify_ui_shader(root: Path, ui_shader: dict):
    failures = []
    if (not isinstance(ui_shader, dict) or ui_shader.get('status') != 'native_ui_shader_source_hash_verified' or
            ui_shader.get('shaderName') != _UI_SHADER or not isinstance(ui_shader.get('sha256'), str) or
            not re.fullmatch(r'[0-9a-f]{64}', ui_shader.get('sha256', ''))):
        return ['Frozen Spine Unity UI shader identity/status is missing or unsupported']
    source_path, target_path = ui_shader.get('sourcePath'), ui_shader.get('targetPath')
    if not isinstance(source_path, str) or not Path(source_path).is_file() or _sha(Path(source_path)) != ui_shader['sha256']:
        failures.append('Frozen Spine Unity UI shader source path/SHA differs')
    target = _relative_file(root, target_path)
    if target is None or _sha(target) != ui_shader['sha256']:
        failures.append('Imported Spine Unity UI shader path/SHA differs')
    return failures


def _reference_pairs(rows):
    if not isinstance(rows, list):
        return None
    pairs = []
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get('name'), str) or not row.get('name') or
                not isinstance(row.get('version'), str) or not row.get('version')):
            return None
        pairs.append((row['name'], row['version']))
    if len(set(pairs)) != len(pairs):
        return None
    return set(pairs)


def _verify_editor_runtime_variant(instruction: dict, root: Path):
    """Verify actual loading of the paired Editor-only Spine assemblies when pinned."""
    stage = instruction.get('spineNativeStage')
    if not isinstance(stage, dict) or 'editorRuntimeVariant' not in stage:
        return []
    failures = []

    def fail(message):
        failures.append(diagnostic('SPINE_EDITOR_RUNTIME_READBACK_INVALID',
                                   'Analysis/Readback/Spine/runtime-assembly-load.json', message,
                                   'spine-editor-runtime'))

    variant = stage.get('editorRuntimeVariant')
    if not isinstance(variant, dict) or variant.get('status') != 'verified_editor_source_build':
        fail('Frozen Editor runtime variant source-build pin is missing or unverified')
        return failures
    manifest_sha = instruction.get('sourceManifestSha256')
    ir_sha = instruction.get('sourceIrSha256')
    manifest_path = instruction.get('sourceManifestPath')
    if (not isinstance(manifest_sha, str) or not _SHA.fullmatch(manifest_sha) or
            not isinstance(ir_sha, str) or not _SHA.fullmatch(ir_sha) or
            not isinstance(manifest_path, str) or not Path(manifest_path).is_file() or
            _sha(Path(manifest_path)) != manifest_sha):
        fail('Unity instruction source manifest/IR pin is missing or source manifest SHA differs')
        return failures
    expected = variant.get('assemblyLoadVerification')
    assemblies = variant.get('assemblies')
    if not isinstance(expected, dict) or not isinstance(assemblies, dict):
        fail('Frozen Editor runtime assembly/path/hash expectation is missing')
        return failures
    if expected.get('status') != 'not_run' or expected.get('expectedUnityEditorReference') is not True:
        fail('Frozen Editor runtime load expectation has an invalid status or Editor-reference policy')
    expected_fields = expected.get('requiredActualFields')
    if (not isinstance(expected_fields, list) or
            not {'typeof(SkeletonGraphic).Assembly.Location', 'assemblySha256',
                 'referencedAssemblies', 'unityEditorReferencePresent'}.issubset(set(expected_fields))):
        fail('Frozen Editor runtime load expectation omits required native actual fields')

    unity = assemblies.get('spine-unity.dll')
    core = assemblies.get('spine-csharp.dll')
    if not isinstance(unity, dict) or not isinstance(core, dict):
        fail('Frozen Editor Spine Unity/core assembly pair is incomplete')
        return failures
    for filename, assembly, expected_path_key, expected_sha_key in (
        ('spine-unity.dll', unity, 'expectedAssemblyPath', 'expectedAssemblySha256'),
        ('spine-csharp.dll', core, 'expectedCoreAssemblyPath', 'expectedCoreAssemblySha256'),
    ):
        path = assembly.get('runtimeImportPath')
        digest = assembly.get('sha256')
        if (path != expected.get(expected_path_key) or not isinstance(path, str) or
                not path.startswith('Assets/Plugins/Spine38/EditorRuntime/') or
                not isinstance(digest, str) or not _SHA.fullmatch(digest) or digest != expected.get(expected_sha_key)):
            fail(f'Frozen Editor assembly path/SHA pin differs for {filename}')
            continue
        asset = _relative_file(root, path)
        if asset is None or _sha(asset) != digest:
            fail(f'Candidate Editor assembly is missing or differs from source SHA: {filename}')
        if (assembly.get('assemblyName') != filename[:-4] or
                not isinstance(assembly.get('assemblyVersion'), str) or not assembly.get('assemblyVersion')):
            fail(f'Frozen Editor assembly name/version is malformed for {filename}')

    unity_refs = _reference_pairs(unity.get('references'))
    core_refs = _reference_pairs(core.get('references'))
    if unity_refs is None or core_refs is None:
        fail('Frozen Editor assembly reference set is malformed or duplicated')
    else:
        if ('UnityEditor.CoreModule', '0.0.0.0') not in unity_refs:
            fail('Frozen spine-unity Editor variant does not reference UnityEditor.CoreModule')
        if ('spine-csharp', core.get('assemblyVersion')) not in unity_refs:
            fail('Frozen spine-unity Editor variant does not reference its paired spine-csharp version')
        if any(name == 'UnityEditor.CoreModule' for name, _ in core_refs):
            fail('Frozen spine-csharp core assembly unexpectedly references UnityEditor')
    evidence_path = variant.get('sourceEvidencePath')
    evidence_sha = variant.get('sourceEvidenceSha256')
    if (not isinstance(evidence_path, str) or not Path(evidence_path).is_file() or
            not isinstance(evidence_sha, str) or not _SHA.fullmatch(evidence_sha) or
            _sha(Path(evidence_path)) != evidence_sha):
        fail('Editor runtime source-build evidence path/SHA differs')
    else:
        try:
            source_evidence = json.loads(read(Path(evidence_path), max_bytes=128 * 1024 * 1024).decode('utf-8-sig'))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            source_evidence = None
        if (not isinstance(source_evidence, dict) or
                source_evidence.get('status') != 'verified_editor_source_build' or
                source_evidence.get('sourceManifestSha256') != variant.get('sourceManifestSha256') or
                source_evidence.get('cocosCompatibilityFallbacksIncluded') is not False):
            fail('Editor runtime source-build evidence content differs from its stage pin')

    report_path = _relative_file(root, 'Analysis/Readback/Spine/runtime-assembly-load.json')
    if report_path is None:
        fail('Required Editor runtime assembly-load readback is missing')
        return failures
    try:
        report = json.loads(read(report_path, max_bytes=16 * 1024 * 1024).decode('utf-8-sig'))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        fail('Editor runtime assembly-load readback is malformed JSON')
        return failures
    if not isinstance(report, dict) or report.get('schemaVersion') != 1:
        fail('Editor runtime assembly-load readback schema is invalid')
        return failures
    if (report.get('status') != 'verified_editor_assembly_loaded' or
            report.get('verified') is not True or report.get('editorVariantRequired') is not True or
            report.get('gaps') != []):
        fail('Editor runtime load status is unverified or contains gaps')
    if (report.get('sourceManifestSha256') != instruction.get('sourceManifestSha256') or
            report.get('normalizedIrSha256') != instruction.get('sourceIrSha256')):
        fail('Editor runtime readback source manifest/IR pins differ from the Unity instruction')
    expected_report_fields = (
        ('expectedSpineUnityPath', expected.get('expectedAssemblyPath')),
        ('expectedSpineUnitySha256', expected.get('expectedAssemblySha256')),
        ('expectedSpineCorePath', expected.get('expectedCoreAssemblyPath')),
        ('expectedSpineCoreSha256', expected.get('expectedCoreAssemblySha256')),
    )
    for key, value in expected_report_fields:
        if report.get(key) != value:
            fail(f'Editor runtime readback frozen expectation differs: {key}')

    for prefix, filename, assembly, path_key, sha_key in (
        ('SpineUnity', 'spine-unity.dll', unity, 'expectedAssemblyPath', 'expectedAssemblySha256'),
        ('SpineCore', 'spine-csharp.dll', core, 'expectedCoreAssemblyPath', 'expectedCoreAssemblySha256'),
    ):
        path = assembly.get('runtimeImportPath')
        target = _relative_file(root, path) if isinstance(path, str) else None
        actual_path = report.get(f'actual{prefix}CandidatePath')
        actual_location = report.get(f'actual{prefix}Location')
        expected_location = str((root / path).resolve()) if isinstance(path, str) else None
        if (actual_path != expected.get(path_key) or not isinstance(actual_location, str) or
                str(Path(actual_location).resolve()) != expected_location):
            fail(f'Loaded Editor assembly path does not point at the paired candidate file: {filename}')
        if (target is None or _sha(target) != expected.get(sha_key) or
                report.get(f'actual{prefix}Sha256') != expected.get(sha_key)):
            fail(f'Loaded Editor assembly SHA differs from the paired candidate file: {filename}')
        if (report.get(f'actual{prefix}AssemblyName') != assembly.get('assemblyName') or
                report.get(f'actual{prefix}AssemblyVersion') != assembly.get('assemblyVersion')):
            fail(f'Loaded Editor assembly name/version differs: {filename}')

    loaded_refs = _reference_pairs(report.get('spineUnityReferences'))
    if loaded_refs is None or unity_refs is None or loaded_refs != unity_refs:
        fail('Loaded spine-unity reference set differs from the frozen Editor assembly')
    if (report.get('unityEditorReferencePresent') is not True or
            expected.get('expectedUnityEditorReference') is not True or
            ('UnityEditor.CoreModule', '0.0.0.0') not in (loaded_refs or set())):
        fail('Loaded spine-unity assembly lacks the required UnityEditor reference')
    if (report.get('spineCoreReferenceVerified') is not True or
            ('spine-csharp', core.get('assemblyVersion')) not in (loaded_refs or set())):
        fail('Loaded spine-unity assembly lacks the exact paired core reference')
    return failures


def _expected_dynamic_gaps(component: dict):
    rows = component.get('fieldGaps')
    if not isinstance(rows, list):
        return None
    result = []
    for row in rows:
        if not isinstance(row, dict) or (row.get('sourceProperty'), row.get('status')) not in _ALLOWED_SOURCE_GAPS:
            return None
        result.append(f"source_field_unmapped:{row['sourceProperty']}:{row['status']}")
    return result


def _pma_value(component: dict):
    rows = component.get('targetFieldBindings')
    if not isinstance(rows, list):
        return None
    found = [row for row in rows if isinstance(row, dict) and
             (row.get('member') == 'pmaVertexColors' or row.get('sourceProperty') == 'premultipliedAlpha')]
    if len(found) != 1 or found[0].get('valueType') != 'bool' or found[0].get('status') not in (
            'explicit', 'resolved_source_engine_default'):
        return None
    return found[0].get('boolValue') if type(found[0].get('boolValue')) is bool else None


def _empty_unbound_graphic_presentation(value):
    """Accept only Unity JsonUtility's exact empty DTO for an unbound Graphic."""
    if not isinstance(value, dict):
        return value is None
    expected = {
        'sourceComponentId': '',
        'sdkInstructionsType': '',
        'instructionCount': 0,
        'canvasRendererCount': 0,
        'sdkEventAttached': False,
        'materialPairsVerified': False,
        'nativeMaterialStatus': '',
        'nativeMaterialVerified': False,
        'textureVerificationMethod': '',
        'pose': {
            'initialized': False,
            'animationStateInitialized': False,
            'sourceDataIdentityVerified': False,
            'dataVersion': '',
            'boneCount': 0,
            'slotCount': 0,
            'activeDrawableAttachmentCount': 0,
            'nonNullAttachmentCount': 0,
            'sourceSkin': '',
            'actualSkin': '',
            'sourceSkinVerified': False,
            'runtimeDefaultSkinName': '',
            'defaultSkinRuntimeNull': False,
            'sourceAnimation': '',
            'actualAnimation': '',
            'trackTime': 0.0,
            'sourceAnimationVerified': False,
            'allSlotsHaveNoDrawableAttachment': False,
            'emptyRendererStateVerified': False,
            'emptyPoseVerified': False,
            'gaps': [],
            'activeDrawableAttachments': [],
        },
        'gaps': [],
        'renderers': [],
    }
    def exact_json(actual, wanted):
        if isinstance(wanted, dict):
            return (isinstance(actual, dict) and actual.keys() == wanted.keys() and
                    all(exact_json(actual[key], item) for key, item in wanted.items()))
        if isinstance(wanted, list):
            return (isinstance(actual, list) and len(actual) == len(wanted) and
                    all(exact_json(a, w) for a, w in zip(actual, wanted)))
        return type(actual) is type(wanted) and actual == wanted

    return exact_json(value, expected)


def _graphic_material_bindings(stage_asset: dict):
    factory = stage_asset.get('factoryInput')
    pages = factory.get('pages') if isinstance(factory, dict) else None
    if not isinstance(pages, list) or not pages:
        return None
    result = {}
    source_asset_id = stage_asset.get('sourceAssetId')
    for page in pages:
        if not isinstance(page, dict):
            return None
        page_name, texture_id = page.get('sourceAtlasPage'), page.get('sourceTextureSourceId')
        texture_path = page.get('textureAssetPath')
        if not all(isinstance(value, str) and value for value in (source_asset_id, page_name, texture_id, texture_path)):
            return None
        normal_path = page.get('graphicNormalMaterialAssetPath')
        if not isinstance(normal_path, str) or not normal_path:
            return None
        normal_id = f'{source_asset_id}/{page_name}/normal'
        result[normal_id] = dict(textureSourceId=texture_id, blendMode='normal',
                                 materialPath=normal_path, texturePath=texture_path)
        variants = page.get('variants')
        if not isinstance(variants, list):
            return None
        for variant in variants:
            if not isinstance(variant, dict):
                return None
            mode, material_path = variant.get('blendMode'), variant.get('graphicMaterialAssetPath')
            if mode not in {'additive', 'multiply', 'screen'} or not isinstance(material_path, str) or not material_path:
                return None
            material_id = f'{source_asset_id}/{page_name}/{mode}'
            if material_id in result:
                return None
            result[material_id] = dict(textureSourceId=texture_id, blendMode=mode,
                                       materialPath=material_path, texturePath=texture_path)
    return result


def _expected_initial_string(component: dict, member: str):
    rows = component.get('targetFieldBindings')
    if not isinstance(rows, list):
        return None
    matches = [row for row in rows if isinstance(row, dict) and row.get('member') == member]
    if (len(matches) != 1 or matches[0].get('valueType') != 'string' or
            matches[0].get('status') not in ('explicit', 'resolved_source_engine_default') or
            not isinstance(matches[0].get('stringValue'), str)):
        return None
    return matches[0]['stringValue']


def _expected_stencil_mask_ancestors(source_node_id: str, nodes: dict, static_masks):
    """Return active serialized source Masks from the Graphic node toward its Canvas."""
    if not isinstance(source_node_id, str) or source_node_id not in nodes or not isinstance(static_masks, list):
        return None
    masks_by_node = {}
    for row in static_masks:
        if not isinstance(row, dict) or not isinstance(row.get('node'), str):
            return None
        if row.get('enabled') is True:
            masks_by_node.setdefault(row['node'], []).append(row.get('sourceId'))
    expected = []
    current = source_node_id
    visited = set()
    while current in nodes:
        if current in visited:
            return None
        visited.add(current)
        node = nodes[current]
        if not isinstance(node, dict) or type(node.get('active')) is not bool:
            return None
        # A child Spine Graphic can be authored inactive while an ancestor
        # Mask remains active. MaskUtilities checks the Mask's own hierarchy,
        # not the child's active state, so evaluate each mask node separately.
        active_in_hierarchy = node['active']
        parent = node.get('parent')
        parent_seen = set()
        while parent not in (None, ''):
            if not isinstance(parent, str) or parent in parent_seen:
                return None
            parent_seen.add(parent)
            parent_node = nodes.get(parent)
            if not isinstance(parent_node, dict) or type(parent_node.get('active')) is not bool:
                return None
            active_in_hierarchy = active_in_hierarchy and parent_node['active']
            parent = parent_node.get('parent')
        if active_in_hierarchy:
            matches = masks_by_node.get(current, [])
            if len(matches) > 1 or any(not isinstance(source_id, str) or not source_id for source_id in matches):
                return None
            expected.extend(matches)
        parent = node.get('parent')
        if parent in (None, ''):
            break
        if not isinstance(parent, str):
            return None
        current = parent
    return expected


def _verify_transient_stencil_variant(row: dict, expected: dict, actual_asset_path: str,
                                     nodes: dict, static_masks, source_node_id: str, root: Path,
                                     source_id: str, index: int, owner: str):
    failures = []
    # Candidate file identities are checked by the caller; this helper validates
    # all per-renderer provenance carried by the saved native readback.
    expected_ancestors = _expected_stencil_mask_ancestors(source_node_id, nodes, static_masks)
    actual_ancestors = row.get('stencilMaskAncestorSourceIds')
    if expected_ancestors is None or actual_ancestors != expected_ancestors:
        failures.append(f'{owner}: Spine renderer stencil-mask ancestry differs {source_id}[{index}]')
    maskable = row.get('rawImageMaskable')
    depth = row.get('stencilDepth')
    if type(maskable) is not bool or type(depth) is not int:
        failures.append(f'{owner}: Spine renderer stencil depth is malformed {source_id}[{index}]')
        expected_depth = -1
    else:
        expected_depth = len(expected_ancestors) if maskable and expected_ancestors is not None else 0
        if depth != expected_depth:
            failures.append(f'{owner}: Spine renderer stencil depth differs from source ancestry {source_id}[{index}]')
    if not isinstance(row.get('stencilRootSortCanvasPath'), str) or not row.get('stencilRootSortCanvasPath'):
        failures.append(f'{owner}: Spine renderer root sort Canvas provenance is missing {source_id}[{index}]')
    if actual_asset_path != '':
        failures.append(f'{owner}: Spine transient stencil renderer unexpectedly reports a persistent material path {source_id}[{index}]')
    stencil_id = (1 << expected_depth) - 1 if 0 < expected_depth < 31 else -1
    wanted_state = {
        'stencilReference': stencil_id,
        'stencilComparison': 3,  # UnityEngine.Rendering.CompareFunction.Equal
        'stencilOperation': 0,  # UnityEngine.Rendering.StencilOp.Keep
        'stencilReadMask': stencil_id,
        'stencilWriteMask': 0,
        'stencilColorMask': 15,  # UnityEngine.Rendering.ColorWriteMask.All
        'stencilUseAlphaClip': 0,
    }
    if stencil_id < 0 or any(row.get(key) != value for key, value in wanted_state.items()):
        failures.append(f'{owner}: Spine renderer stencil material state differs from UGUI ancestry formula {source_id}[{index}]')
    for key in ('baseMaterialPersistentReferenceVerified', 'modifiedMaterialShaderMatchesBase',
                'nonStencilMaterialPropertiesMatch', 'stencilAncestryVerified',
                'stencilConfigurationVerified', 'transientStencilVariantVerified'):
        if row.get(key) is not True:
            failures.append(f'{owner}: Spine renderer {key} is not verified {source_id}[{index}]')
    if (row.get('baseMaterialAssetPath') != expected.get('materialPath') or
            row.get('baseMaterialShader') != _UI_SHADER):
        failures.append(f'{owner}: Spine renderer persistent base material path/shader differs {source_id}[{index}]')
    if row.get('baseMaterialAssetGuid') != _guid_from_meta(root, expected.get('materialPath')):
        failures.append(f'{owner}: Spine renderer persistent base material GUID differs {source_id}[{index}]')
    if (row.get('baseMaterialTextureAssetPath') != expected.get('texturePath') or
            row.get('baseMaterialTextureGuid') != _guid_from_meta(root, expected.get('texturePath'))):
        failures.append(f'{owner}: Spine renderer persistent base texture path/GUID differs {source_id}[{index}]')
    return failures


def _verify_empty_pose(stage_component: dict, pose: dict, data_asset: dict, owner: str):
    failures = []
    source_id = stage_component.get('sourceComponentId')
    if not isinstance(pose, dict):
        return [f'{owner}: verified empty pose readback is missing {source_id}']
    for key in ('initialized', 'animationStateInitialized', 'sourceDataIdentityVerified',
                'sourceSkinVerified', 'sourceAnimationVerified', 'allSlotsHaveNoDrawableAttachment',
                'emptyRendererStateVerified', 'emptyPoseVerified'):
        if pose.get(key) is not True:
            failures.append(f'{owner}: zero drawable pose {key} is not verified {source_id}')
    expected_skin = pose.get('sourceSkin')
    actual_skin = pose.get('actualSkin')
    default_skin = pose.get('runtimeDefaultSkinName')
    default_skin_null = pose.get('defaultSkinRuntimeNull')
    exact_skin_representation = (actual_skin == expected_skin or
        actual_skin in (None, '') and default_skin_null is True and isinstance(expected_skin, str) and
        bool(expected_skin) and default_skin == expected_skin)
    if (not exact_skin_representation or type(default_skin_null) is not bool or
            default_skin_null and (actual_skin not in (None, '') or default_skin != expected_skin)):
        failures.append(f'{owner}: zero drawable pose source/default/runtime skin representation differs {source_id}')
    if pose.get('dataVersion') != data_asset.get('spineVersion'):
        failures.append(f'{owner}: zero drawable pose data version differs {source_id}')
    for key, asset_key in (('boneCount', 'boneCount'), ('slotCount', 'slotCount')):
        value, expected = pose.get(key), data_asset.get(asset_key)
        if type(value) is not int or type(expected) is not int or value != expected:
            failures.append(f'{owner}: zero drawable pose {key} differs from bound data {source_id}')
    active_count = pose.get('activeDrawableAttachmentCount')
    if type(active_count) is not int or active_count != 0:
        failures.append(f'{owner}: zero drawable pose contains drawable attachments {source_id}')
    non_null_count = pose.get('nonNullAttachmentCount')
    if (type(non_null_count) is not int or non_null_count < 0 or
            type(pose.get('slotCount')) is not int or non_null_count > pose['slotCount']):
        failures.append(f'{owner}: zero drawable pose attachment count is malformed {source_id}')
    if pose.get('activeDrawableAttachments') != [] or pose.get('gaps') != []:
        failures.append(f'{owner}: zero drawable pose has active drawable rows or gaps {source_id}')
    expected_skin = _expected_initial_string(stage_component, 'initialSkinName')
    expected_animation = _expected_initial_string(stage_component, 'startingAnimation')
    if expected_skin is None or pose.get('sourceSkin') != expected_skin:
        failures.append(f'{owner}: zero drawable pose source skin is unpinned {source_id}')
    if expected_animation is None or pose.get('sourceAnimation') != expected_animation:
        failures.append(f'{owner}: zero drawable pose source animation is unpinned {source_id}')
    actual_skin = pose.get('actualSkin')
    exact_runtime_skin = (actual_skin in (None, '') if expected_skin == '' else
        actual_skin == expected_skin or actual_skin in (None, '') and pose.get('defaultSkinRuntimeNull') is True and
        pose.get('runtimeDefaultSkinName') == expected_skin)
    if expected_skin is not None and not exact_runtime_skin:
        failures.append(f'{owner}: zero drawable pose actual skin differs {source_id}')
    actual_animation = pose.get('actualAnimation')
    if (expected_animation is not None and
            (actual_animation not in (None, '') if expected_animation == '' else actual_animation != expected_animation)):
        failures.append(f'{owner}: zero drawable pose actual animation differs {source_id}')
    if not _close(pose.get('trackTime'), 0.0):
        failures.append(f'{owner}: zero drawable pose is not at time zero {source_id}')
    return failures


def _verify_graphic_renderer(root: Path, stage_component: dict, actual: dict, data_asset_plan: dict,
                             actual_data_asset: dict, ui_shader: dict, owner: str, nodes: dict,
                             static_masks):
    failures = []
    source_id = stage_component.get('sourceComponentId')
    expected_bindings = _graphic_material_bindings(data_asset_plan)
    if not isinstance(expected_bindings, dict) or not expected_bindings:
        return [f'{owner}: frozen Spine UI material pairs are incomplete {source_id}']
    pages = data_asset_plan.get('factoryInput', {}).get('pages', [])
    first_page = pages[0] if pages else {}
    expected_base_path = first_page.get('graphicNormalMaterialAssetPath')
    expected_base_guid = _guid_from_meta(root, expected_base_path)
    expected_main_texture = first_page.get('textureAssetPath')
    if expected_base_guid is None:
        failures.append(f'{owner}: expected Spine Graphic base material GUID is unavailable {source_id}')
    if (actual.get('rendererMaterialRequired') is not True or actual.get('rendererMaterialVerified') is not True or
            actual.get('allowMultipleCanvasRenderers') is not True or
            actual.get('customMaterialOverrideCount') != 0):
        failures.append(f'{owner}: SkeletonGraphic material adapter is missing, overridden, or unverified {source_id}')
    if (actual.get('rendererBaseMaterialShader') != ui_shader.get('shaderName') or
            actual.get('rendererBaseMaterialAssetPath') != expected_base_path or
            actual.get('rendererBaseMaterialGuid') != expected_base_guid):
        failures.append(f'{owner}: SkeletonGraphic base material path/GUID/shader differs {source_id}')
    if (actual.get('rendererMaterialForRenderingShader') != ui_shader.get('shaderName') or
            actual.get('rendererMainTextureAssetPath') != expected_main_texture):
        failures.append(f'{owner}: SkeletonGraphic rendering shader or main texture differs {source_id}')

    presentation = actual.get('rendererPresentation')
    if not isinstance(presentation, dict):
        return failures + [f'{owner}: saved SkeletonGraphic typed material presentation is missing {source_id}']
    if (presentation.get('sourceComponentId') != source_id or
            presentation.get('sdkInstructionsType') != _SDK_INSTRUCTIONS or
            presentation.get('sdkEventAttached') is not True or
            presentation.get('nativeMaterialVerified') is not True or
            presentation.get('materialPairsVerified') is not True or
            presentation.get('textureVerificationMethod') != _TEXTURE_METHOD or
            presentation.get('gaps') != []):
        failures.append(f'{owner}: saved SkeletonGraphic presentation identity/verification differs {source_id}')
    renderer_rows = presentation.get('renderers')
    instruction_count = presentation.get('instructionCount')
    canvas_count = presentation.get('canvasRendererCount')
    status = presentation.get('nativeMaterialStatus')
    if (not isinstance(renderer_rows, list) or type(instruction_count) is not int or instruction_count < 0 or
            type(canvas_count) is not int or canvas_count < 0):
        failures.append(f'{owner}: saved SkeletonGraphic typed pair denominator is malformed {source_id}')
        renderer_rows = renderer_rows if isinstance(renderer_rows, list) else []
    if status == 'verified_empty_pose_with_persistent_material_pairs':
        if instruction_count != 0 or renderer_rows != []:
            failures.append(f'{owner}: verified empty pose has non-empty renderer rows {source_id}')
        failures.extend(_verify_empty_pose(stage_component, presentation.get('pose'), actual_data_asset, owner))
    elif status == 'verified_active_submesh_materials':
        if instruction_count <= 0 or canvas_count != instruction_count or len(renderer_rows) != instruction_count:
            failures.append(f'{owner}: active SkeletonGraphic submesh denominator differs {source_id}')
    else:
        failures.append(f'{owner}: SkeletonGraphic native material status is unknown or unverified {source_id}')
    if len(renderer_rows) != instruction_count:
        failures.append(f'{owner}: saved SkeletonGraphic typed pair row count differs {source_id}')
    canvas_paths = actual.get('canvasRendererMaterialAssetPaths')
    for index, row in enumerate(renderer_rows):
        if not isinstance(row, dict) or row.get('index') != index:
            failures.append(f'{owner}: malformed SkeletonGraphic renderer row {source_id}[{index}]')
            continue
        pair_id = row.get('sourceMaterialId')
        expected = expected_bindings.get(pair_id)
        if expected is None:
            failures.append(f'{owner}: unknown persisted Spine UI source material pair {source_id}[{index}]')
            continue
        if (row.get('textureSourceId') != expected['textureSourceId'] or
                row.get('blendMode') != expected['blendMode']):
            failures.append(f'{owner}: persisted Spine UI material/texture/blend pair differs {source_id}[{index}]')
        if (row.get('actualMaterialShader') != ui_shader.get('shaderName') or
                not isinstance(row.get('actualMaterialName'), str) or not row.get('actualMaterialName')):
            failures.append(f'{owner}: Spine UI renderer material shader/identity is missing {source_id}[{index}]')
        if row.get('actualTextureName') != Path(expected['texturePath']).stem:
            failures.append(f'{owner}: Spine UI renderer texture differs {source_id}[{index}]')
        for flag in ('rawImageEnabled', 'rawImageMaterialReferenceVerified', 'materialReferenceVerified',
                     'textureReferenceVerified', 'blendVerified'):
            if row.get(flag) is not True:
                failures.append(f'{owner}: Spine UI renderer {flag} is not verified {source_id}[{index}]')
        if type(row.get('rawImageMaskable')) is not bool:
            failures.append(f'{owner}: Spine UI RawImage mask state is malformed {source_id}[{index}]')
        canvas_path = (canvas_paths[index + 1] if isinstance(canvas_paths, list) and
                       len(canvas_paths) == instruction_count + 1 and isinstance(canvas_paths[index + 1], str) else None)
        if canvas_path == '':
            failures.extend(_verify_transient_stencil_variant(row, expected, canvas_path, nodes, static_masks,
                                                               stage_component.get('sourceNodeId'), root,
                                                               source_id, index, owner))

    canvas_shaders = actual.get('canvasRendererMaterialShaders')
    expected_child_paths = []
    for row in renderer_rows:
        expected = expected_bindings.get(row.get('sourceMaterialId')) if isinstance(row, dict) else None
        expected_child_paths.append(expected.get('materialPath') if expected is not None else None)
    if status == 'verified_active_submesh_materials':
        # Unity reports the root CanvasRenderer's empty material slot before
        # the per-submesh renderer materials. Keep validating each child slot;
        # only the root's no-material slot may be blank.
        expected_shaders = [''] + [_UI_SHADER] * instruction_count
        expected_paths = [''] + expected_child_paths
    else:
        # An empty pose has no submesh material slots. The single entry is the
        # root CanvasRenderer with no bound material.
        expected_shaders = ['']
        expected_paths = ['']
    if (not isinstance(canvas_shaders, list) or len(canvas_shaders) != len(expected_shaders) or
            any(actual_value != expected_value for actual_value, expected_value in
                zip(canvas_shaders, expected_shaders))):
        failures.append(f'{owner}: CanvasRenderer material shader set differs {source_id}')
    if (not isinstance(canvas_paths, list) or len(canvas_paths) != len(expected_paths) or
            not canvas_paths or canvas_paths[0] != '' or any(
                actual_path != expected_path and not (actual_path == '' and index > 0 and
                    index - 1 < len(renderer_rows) and isinstance(renderer_rows[index - 1], dict) and
                    renderer_rows[index - 1].get('transientStencilVariantVerified') is True)
                for index, (actual_path, expected_path) in enumerate(zip(canvas_paths, expected_paths)))):
        failures.append(f'{owner}: CanvasRenderer material asset path set differs {source_id}')
    return failures


def _verify_component(stage_component: dict, actual: dict, visual: dict, data_assets: dict,
                      stage_assets: dict, nodes: dict, static_masks, ui_shader: dict, root: Path, owner: str):
    failures = []
    source_id = stage_component.get('sourceComponentId')
    has_data = stage_component.get('sourceHasStaticDataReference') is True
    data_id = stage_component.get('sourceDataAssetId')
    if actual.get('sourceComponentId') != source_id:
        failures.append(f'{owner}: Spine component identity differs {source_id}')
    renderer_kind = actual.get('rendererKind')
    if renderer_kind not in _RENDERER_TYPES or actual.get('nativeComponentType') != _RENDERER_TYPES.get(renderer_kind):
        failures.append(f'{owner}: native Spine renderer type is unknown or mismatched {source_id}')
    renderer_context = stage_component.get('rendererSelection')
    if (not isinstance(renderer_context, dict) or
            renderer_context.get('status') != 'declared_not_native_readback' or
            renderer_context.get('nativeRendererReadback') != 'pending' or
            renderer_context.get('sourceComponentId') != source_id or
            renderer_context.get('rendererKind') not in _RENDERER_TYPES):
        failures.append(f'{owner}: declared source Spine renderer context is missing or malformed {source_id}')
    else:
        expected_renderer = renderer_context['rendererKind']
        expected_transform = 'RectTransform' if expected_renderer == 'SkeletonGraphic' else 'Transform'
        if renderer_context.get('targetNodeTransform') != expected_transform:
            failures.append(f'{owner}: declared renderer context transform differs from renderer kind {source_id}')
        if renderer_kind != expected_renderer:
            failures.append(f'{owner}: native Spine renderer kind differs from declared target context {source_id}')
        if expected_renderer == 'SkeletonGraphic':
            ppu = renderer_context.get('canvasReferencePixelsPerUnit')
            if (not _finite_number(ppu) or float(ppu) <= 0 or
                    not isinstance(renderer_context.get('canvasIdentity'), str) or
                    not renderer_context.get('canvasIdentity')):
                failures.append(f'{owner}: declared SkeletonGraphic context lacks positive finite Canvas PPU {source_id}')
        elif renderer_context.get('canvasReferencePixelsPerUnit') is not None:
            failures.append(f'{owner}: declared SkeletonAnimation context unexpectedly has Canvas PPU {source_id}')
    for key, expected in (
        ('componentTypeVerified', True), ('dataReferenceVerified', True), ('mappedStaticFieldsVerified', True),
        ('enabled', True), ('staticDataBound', has_data), ('sourceDataUnbound', not has_data),
        ('dynamicAssignmentUnverified', not has_data),
    ):
        if actual.get(key) is not expected:
            failures.append(f'{owner}: Spine component {key} differs {source_id}')
    if ((has_data and actual.get('sourceDataAssetId') != data_id) or
            (not has_data and (data_id not in (None, '') or actual.get('sourceDataAssetId') != ''))):
        failures.append(f'{owner}: Spine component source data asset ID differs {source_id}')
    if has_data:
        data_asset = data_assets.get(data_id)
        data_asset_plan = stage_assets.get(data_id)
        if data_asset is None:
            failures.append(f'{owner}: bound Spine data asset is absent {source_id}/{data_id}')
        elif (actual.get('dataAssetContentVerified') is not True or
              actual.get('nativeDataAssetPath') != data_asset.get('skeletonDataAssetPath') or
              actual.get('nativeDataAssetGuid') != data_asset.get('skeletonDataAssetGuid')):
            failures.append(f'{owner}: component data asset path/GUID/content differs {source_id}')
        if renderer_kind == 'SkeletonGraphic' and data_asset is not None and data_asset_plan is not None:
            failures.extend(_verify_graphic_renderer(root, stage_component, actual, data_asset_plan,
                                                     data_asset, ui_shader, owner, nodes, static_masks))
    elif (actual.get('dataAssetContentVerified') is not False or actual.get('nativeDataAssetPath') not in (None, '') or
          actual.get('nativeDataAssetGuid') not in (None, '')):
        failures.append(f'{owner}: source-unbound Spine component has a native data asset {source_id}')

    dynamic_gaps = _expected_dynamic_gaps(stage_component)
    if dynamic_gaps is None:
        failures.append(f'{owner}: unknown or malformed source-only Spine field gap {source_id}')
        dynamic_gaps = []
    if actual.get('sourceOnlyFieldGaps') != dynamic_gaps:
        failures.append(f'{owner}: Spine source-only field gaps differ {source_id}')
    expected_all_gaps = []
    if not has_data:
        expected_all_gaps.append('dynamic_skeleton_data_assignment_unverified')
    expected_all_gaps.extend(dynamic_gaps)
    if actual.get('gaps') != expected_all_gaps:
        failures.append(f'{owner}: Spine component gap set differs {source_id}')
    if actual.get('fieldsVerified') is not (not dynamic_gaps):
        failures.append(f'{owner}: Spine fieldsVerified incorrectly masks source-only gaps {source_id}')
    if actual.get('nativeComplete') is not (has_data and not dynamic_gaps):
        failures.append(f'{owner}: Spine nativeComplete overstates or understates dynamic completeness {source_id}')

    pma = _pma_value(stage_component)
    if renderer_kind == 'SkeletonGraphic':
        if pma is None:
            failures.append(f'{owner}: SkeletonGraphic has no explicit/resolved source PMA field {source_id}')
        if has_data:
            if (actual.get('pmaMaterialProfileRequired') is not True or
                    actual.get('pmaMaterialProfileVerified') is not True or
                    actual.get('pmaMaterialProfileNotApplicable') is not False):
                failures.append(f'{owner}: source-required SkeletonGraphic PMA material profile is unverified {source_id}')
            data_asset = data_assets.get(data_id, {})
            if pma is not None and data_asset.get('premultipliedAlpha') is not pma:
                failures.append(f'{owner}: SkeletonGraphic PMA differs from source and native data asset {source_id}')
        elif (actual.get('pmaMaterialProfileRequired') is not False or
              actual.get('pmaMaterialProfileVerified') is not False or
              actual.get('pmaMaterialProfileNotApplicable') is not True):
            failures.append(f'{owner}: unbound SkeletonGraphic PMA applicability is not explicit {source_id}')
    elif renderer_kind in _RENDERER_TYPES:
        if (actual.get('pmaMaterialProfileRequired') is not False or
                actual.get('pmaMaterialProfileVerified') is not False or
                actual.get('pmaMaterialProfileNotApplicable') is not False):
            failures.append(f'{owner}: non-Graphic Spine renderer has unexpected PMA profile state {source_id}')
        if (actual.get('rendererMaterialRequired') is not False or actual.get('rendererMaterialVerified') is not True or
                actual.get('rendererPresentation') is not None):
            failures.append(f'{owner}: non-Graphic or source-unbound renderer has unexpected UI material binding {source_id}')
        if renderer_kind == 'SkeletonAnimation' and (
                actual.get('allowMultipleCanvasRenderers') is not False or
                actual.get('customMaterialOverrideCount') != 0 or
                actual.get('rendererBaseMaterialShader') not in (None, '') or
                actual.get('rendererBaseMaterialAssetPath') not in (None, '') or
                actual.get('rendererBaseMaterialGuid') not in (None, '') or
                actual.get('rendererMaterialForRenderingShader') not in (None, '') or
                actual.get('canvasRendererMaterialShaders') != [] or
                actual.get('canvasRendererMaterialAssetPaths') != [] or
                actual.get('rendererMainTextureAssetPath') not in (None, '')):
            failures.append(f'{owner}: SkeletonAnimation has unexpected Canvas/UI material state {source_id}')
    if renderer_kind == 'SkeletonGraphic' and not has_data:
        if (actual.get('rendererMaterialRequired') is not False or actual.get('rendererMaterialVerified') is not True or
                not _empty_unbound_graphic_presentation(actual.get('rendererPresentation')) or
                actual.get('allowMultipleCanvasRenderers') is not False or
                actual.get('customMaterialOverrideCount') != 0):
            failures.append(f'{owner}: source-unbound SkeletonGraphic incorrectly claims an applied UI material profile {source_id}')

    if not isinstance(visual, dict) or visual.get('sourceComponentId') != source_id:
        failures.append(f'{owner}: visual identity row is missing or mismatched {source_id}')
        return failures
    expected_time_scale = stage_component.get('sourceTimeScale')
    for key, expected in (
        ('rendererKind', _RENDERER_TYPES.get(renderer_kind)), ('sourceTimeScaleVerified', True),
        ('rendererEnabled', True), ('persistentVisiblePose', True),
    ):
        actual_value = visual.get(key)
        mismatch = actual_value is not expected if isinstance(expected, bool) else actual_value != expected
        if mismatch:
            failures.append(f'{owner}: Spine visible-pose identity {key} differs {source_id}')
    if (stage_component.get('sourceTimeScaleVerified') is not True or
            not _close(visual.get('sourceTimeScale'), expected_time_scale) or
            not _close(visual.get('nativeTimeScale'), 0.0)):
        failures.append(f'{owner}: Spine source/native timeScale proof differs {source_id}')
    node = nodes.get(stage_component.get('sourceNodeId'))
    source_color = node.get('color') if isinstance(node, dict) else None
    if renderer_kind == 'SkeletonGraphic':
        if (not isinstance(source_color, list) or len(source_color) != 4 or
                visual.get('sourceColorVerified') is not True or visual.get('nativeColorVerified') is not True or
                not _source_color_matches(visual.get('sourceColor'), source_color) or
                not _source_color_matches(visual.get('nativeColor'), source_color)):
            failures.append(f'{owner}: SkeletonGraphic source/native color proof differs {source_id}')
    elif renderer_kind == 'SkeletonAnimation':
        if (visual.get('sourceColorVerified') is not False or visual.get('nativeColorVerified') is not False or
                visual.get('sourceColor') != [] or visual.get('nativeColor') != []):
            failures.append(f'{owner}: SkeletonAnimation has unexpected Graphic color proof {source_id}')
    return failures


def verify(plan, projectRoot, editorReadback):
    """Return strict static diagnostics plus explicit dynamic-incomplete warnings.

    ``plan`` is the frozen expanded Unity import plan, ``projectRoot`` is the
    generated Unity candidate, and ``editorReadback`` is its saved native
    editor-readback object. A missing stage is a no-op for non-Spine plans.
    """
    stage_summary = plan.get('spineNativeStage') if isinstance(plan, dict) else None
    if not isinstance(stage_summary, dict):
        return []
    if not stage_summary.get('componentCount') and 'editorRuntimeVariant' not in stage_summary:
        return []

    root = Path(projectRoot).resolve()
    failures = []
    failures.extend(_verify_editor_runtime_variant(plan, root))

    def fail(message, source_id='spine-native-stage'):
        failures.append(diagnostic('SPINE_NATIVE_READBACK_INVALID', 'Analysis/Readback/Spine', message, source_id))

    if stage_summary.get('contract') != _STAGE_CONTRACT:
        fail('Unsupported or missing frozen Spine native stage contract')
        return failures
    if not isinstance(plan.get('sourceManifestSha256'), str) or not isinstance(plan.get('sourceIrSha256'), str):
        fail('Expanded Unity plan is missing source manifest/IR pins')
        return failures
    if stage_summary.get('sourceManifestSha256') != plan.get('sourceManifestSha256') or stage_summary.get('sourceIrSha256') != plan.get('sourceIrSha256'):
        fail('Expanded Unity plan and Spine stage source manifest/IR pins differ')
        return failures

    manifest_path = plan.get('sourceManifestPath')
    if not isinstance(manifest_path, str) or not Path(manifest_path).is_file() or _sha(Path(manifest_path)) != plan['sourceManifestSha256']:
        fail('Frozen source manifest is missing or its SHA-256 differs')
        return failures

    stage_path_relative = stage_summary.get('nativeBindingPlanPath')
    stage_path = _relative_file(root, stage_path_relative)
    if stage_path is None:
        fail('Frozen expanded Spine binding plan is missing')
        return failures
    expected_stage_sha = stage_summary.get('nativeBindingPlanSha256')
    if not isinstance(expected_stage_sha, str) or _sha(stage_path) != expected_stage_sha:
        fail('Frozen expanded Spine binding plan SHA-256 differs')
        return failures
    stage_plan = _json_file(stage_path)
    if not isinstance(stage_plan, dict) or stage_plan.get('schemaVersion') != 1 or stage_plan.get('contract') != _BINDING_CONTRACT:
        fail('Frozen expanded Spine binding plan schema/contract is invalid')
        return failures
    if (stage_plan.get('sourceManifestSha256') != plan['sourceManifestSha256'] or
            stage_plan.get('normalizedIrSha256') != plan['sourceIrSha256'] or
            stage_plan.get('sourceNativeBindingPlanSha256') != stage_summary.get('sourceNativeBindingPlanSha256')):
        fail('Spine binding plan does not match frozen source manifest/normalized-IR/native-plan pins')
        return failures
    ui_shader = stage_plan.get('unityGraphicShader')
    failures.extend(diagnostic('SPINE_NATIVE_READBACK_INVALID', 'Assets/Game/Editor/Conversion/spine-native-binding-plan.json',
                               message, 'spine-native-stage')
                    for message in _verify_ui_shader(root, ui_shader))
    if failures:
        return failures
    stage_components = stage_plan.get('components')
    stage_assets = stage_plan.get('dataAssets')
    if (not isinstance(stage_components, list) or not isinstance(stage_assets, list) or
            len(stage_components) != stage_summary.get('componentCount') or
            len(stage_components) != stage_summary.get('expandedInstanceComponentCount') or
            len(stage_assets) != stage_summary.get('dataAssetCount')):
        fail('Frozen Spine binding plan component/data-asset counts differ from the expanded plan')
        return failures

    component_ids = [row.get('sourceComponentId') if isinstance(row, dict) else None for row in stage_components]
    asset_ids = [row.get('sourceAssetId') if isinstance(row, dict) else None for row in stage_assets]
    if (any(not isinstance(value, str) or not value for value in component_ids + asset_ids) or
            len(set(component_ids)) != len(component_ids) or len(set(asset_ids)) != len(asset_ids)):
        fail('Frozen Spine plan has missing or duplicate component/data-asset identities')
        return failures
    prefab_specs = {row.get('sourceId'): row for row in plan.get('sourcePrefabs', []) if isinstance(row, dict)}
    prefab_ids = set(prefab_specs)
    target_components = {row.get('sourceId'): row for row in plan.get('components', []) if isinstance(row, dict)}
    if any(row.get('sourcePrefabId') not in prefab_ids for row in stage_components):
        fail('Frozen Spine component references an unknown source Prefab owner')
        return failures
    for row in stage_components:
        target_component = target_components.get(row['sourceComponentId'])
        owner_nodes = set(prefab_specs[row['sourcePrefabId']].get('nodes', []))
        origin = row.get('templateOrigin')
        if (target_component is None or target_component.get('type') != 'sp.Skeleton' or
                target_component.get('node') != row.get('sourceNodeId') or row.get('sourceNodeId') not in owner_nodes):
            fail('Frozen Spine component does not match its expanded source component/node owner', row['sourceComponentId'])
        if (not isinstance(origin, dict) or not isinstance(origin.get('componentOriginChain'), list) or
                not origin.get('componentOriginChain') or not isinstance(origin.get('nodeOriginChain'), list) or
                not origin.get('nodeOriginChain') or origin.get('sourceComponentId') != origin['componentOriginChain'][-1] or
                origin.get('sourceNodeId') != origin['nodeOriginChain'][-1] or
                origin.get('sourcePrefabId') not in prefab_ids):
            fail('Frozen Spine template-origin chain is incomplete or mismatched', row['sourceComponentId'])
        has_data = row.get('sourceHasStaticDataReference')
        if (type(has_data) is not bool or
                (has_data and (not isinstance(row.get('sourceDataAssetId'), str) or not row.get('sourceDataAssetId'))) or
                (not has_data and row.get('sourceDataAssetId') not in (None, ''))):
            fail('Frozen Spine component static/unbound data reference state is ambiguous', row['sourceComponentId'])
    referenced_assets = {row.get('sourceDataAssetId') for row in stage_components
                         if row.get('sourceHasStaticDataReference') is True and row.get('sourceDataAssetId')}
    if referenced_assets != set(asset_ids):
        fail('Frozen Spine data-asset set differs from statically referenced component assets')
        return failures
    for row in stage_components:
        renderer_context = row.get('rendererSelection')
        context_valid = (isinstance(renderer_context, dict) and
                         renderer_context.get('status') == 'declared_not_native_readback' and
                         renderer_context.get('nativeRendererReadback') == 'pending' and
                         renderer_context.get('sourceComponentId') == row.get('sourceComponentId') and
                         renderer_context.get('rendererKind') in _RENDERER_TYPES and
                         renderer_context.get('targetNodeTransform') ==
                         ('RectTransform' if renderer_context.get('rendererKind') == 'SkeletonGraphic' else 'Transform'))
        if context_valid and renderer_context['rendererKind'] == 'SkeletonGraphic':
            context_valid = (_finite_number(renderer_context.get('canvasReferencePixelsPerUnit')) and
                             float(renderer_context['canvasReferencePixelsPerUnit']) > 0 and
                             isinstance(renderer_context.get('canvasIdentity'), str) and
                             bool(renderer_context['canvasIdentity']))
        if context_valid and renderer_context['rendererKind'] == 'SkeletonAnimation':
            context_valid = renderer_context.get('canvasReferencePixelsPerUnit') is None
        if (row.get('persistentVisiblePose') is not True or row.get('sourceTimeScaleVerified') is not True or
                not _finite_number(row.get('sourceTimeScale')) or
                row.get('rendererKind') != 'derive_from_target_node_transform' or
                not isinstance(row.get('sourceNodeId'), str) or not row.get('sourceNodeId') or not context_valid):
            fail('Frozen Spine component is missing verified visible-pose/timeScale/node evidence', row.get('sourceComponentId'))
    if failures:
        return failures

    if not isinstance(editorReadback, dict):
        fail('Unity editor readback is missing')
        return failures
    actual_prefabs_rows = editorReadback.get('sourcePrefabs')
    if not isinstance(actual_prefabs_rows, list):
        fail('Unity editor readback has no source Prefab identity rows')
        return failures
    actual_prefabs = {}
    for row in actual_prefabs_rows:
        if not isinstance(row, dict) or not isinstance(row.get('sourceId'), str) or row['sourceId'] in actual_prefabs:
            fail('Unity editor readback has malformed/duplicate source Prefab identities')
            return failures
        actual_prefabs[row['sourceId']] = row

    components_by_prefab = {}
    for row in stage_components:
        components_by_prefab.setdefault(row['sourcePrefabId'], []).append(row)
    assets_by_id = {row['sourceAssetId']: row for row in stage_assets}
    nodes = {row.get('sourceId'): row for row in plan.get('nodes', []) if isinstance(row, dict)}
    static_mask_contract = plan.get('staticMasks')
    static_masks = static_mask_contract.get('masks') if isinstance(static_mask_contract, dict) else None
    warnings = []

    for prefab_id, expected_components in sorted(components_by_prefab.items()):
        prefab_readback = actual_prefabs.get(prefab_id)
        if not isinstance(prefab_readback, dict):
            fail('Spine owner Prefab is absent from native editor readback', prefab_id)
            continue
        guid = prefab_readback.get('guid')
        if not isinstance(guid, str) or not _GUID.fullmatch(guid):
            fail('Spine owner Prefab readback GUID is missing or malformed', prefab_id)
            continue
        expected_prefab = prefab_specs.get(prefab_id, {})
        expected_path = expected_prefab.get('path')
        if not isinstance(expected_path, str) or prefab_readback.get('path') != expected_path:
            fail('Spine owner Prefab path differs from the frozen plan', prefab_id)
        prefab_guid_error = _meta_error(root, expected_path, guid, 'Spine owner Prefab')
        if prefab_guid_error:
            fail(prefab_guid_error, prefab_id)
            continue
        relative = f'Analysis/Readback/Spine/{guid.lower()}.json'
        path = _relative_file(root, relative)
        if path is None:
            fail('Per-Prefab saved Spine readback file is missing: ' + relative, prefab_id)
            continue
        saved = _json_file(path)
        if not isinstance(saved, dict):
            fail('Per-Prefab saved Spine readback is invalid JSON', prefab_id)
            continue
        expected_ids = {row['sourceComponentId'] for row in expected_components}
        expected_owner_assets = {row.get('sourceDataAssetId') for row in expected_components
                                 if row.get('sourceHasStaticDataReference') is True and row.get('sourceDataAssetId')}
        actual_components_rows = saved.get('components')
        actual_assets_rows = saved.get('dataAssets')
        if (saved.get('schemaVersion') != 1 or saved.get('sourcePrefabId') != prefab_id or
                saved.get('sourceManifestSha256') != plan['sourceManifestSha256'] or
                saved.get('normalizedIrSha256') != plan['sourceIrSha256']):
            fail('Per-Prefab Spine readback source identity/manifest/IR pin differs', prefab_id)
        if (saved.get('staticNativeVerified') is not True or saved.get('dynamicBehaviorComplete') is not False or
                saved.get('visualPolicy') != stage_plan.get('visualPolicy')):
            fail('Per-Prefab Spine static/dynamic verification policy flags differ', prefab_id)
        if saved.get('failures') != []:
            fail('Per-Prefab Spine readback records native failures', prefab_id)
        if not isinstance(actual_components_rows, list) or not isinstance(actual_assets_rows, list):
            fail('Per-Prefab Spine component/dataAsset arrays are missing', prefab_id)
            continue
        if (saved.get('componentCount') != len(expected_ids) or
                len(actual_components_rows) != len(expected_ids) or
                saved.get('dataAssetCount') != len(expected_owner_assets) or
                len(actual_assets_rows) != len(expected_owner_assets)):
            fail('Per-Prefab Spine component/data-asset denominator differs', prefab_id)
        actual_components = {}
        for actual in actual_components_rows:
            if not isinstance(actual, dict) or not isinstance(actual.get('sourceComponentId'), str) or actual['sourceComponentId'] in actual_components:
                fail('Per-Prefab Spine component rows have malformed/duplicate identity', prefab_id)
                continue
            actual_components[actual['sourceComponentId']] = actual
        if set(actual_components) != expected_ids:
            fail('Per-Prefab Spine component ID set differs', prefab_id)
        actual_assets = {}
        for actual in actual_assets_rows:
            if not isinstance(actual, dict) or not isinstance(actual.get('sourceAssetId'), str) or actual['sourceAssetId'] in actual_assets:
                fail('Per-Prefab Spine data-asset rows have malformed/duplicate identity', prefab_id)
                continue
            actual_assets[actual['sourceAssetId']] = actual
        if set(actual_assets) != expected_owner_assets:
            fail('Per-Prefab Spine data-asset ID set differs', prefab_id)
        for asset_id in sorted(expected_owner_assets & set(actual_assets)):
            failures.extend(diagnostic('SPINE_NATIVE_READBACK_INVALID', relative, message, prefab_id)
                            for message in _verify_data_asset(root, assets_by_id[asset_id], actual_assets[asset_id],
                                                              ui_shader, prefab_id))

        visual_rows = saved.get('visualComponents')
        if not isinstance(visual_rows, list):
            fail('Per-Prefab Spine visual component rows are missing', prefab_id)
            visual_rows = []
        visual_by_id = {}
        for visual in visual_rows:
            if not isinstance(visual, dict) or not isinstance(visual.get('sourceComponentId'), str) or visual['sourceComponentId'] in visual_by_id:
                fail('Per-Prefab Spine visual rows have malformed/duplicate identity', prefab_id)
                continue
            visual_by_id[visual['sourceComponentId']] = visual
        if set(visual_by_id) != expected_ids:
            fail('Per-Prefab Spine visual component ID set differs', prefab_id)
        for expected in expected_components:
            source_id = expected['sourceComponentId']
            actual = actual_components.get(source_id)
            if actual is None:
                continue
            failures.extend(diagnostic('SPINE_NATIVE_READBACK_INVALID', relative, message, prefab_id)
                            for message in _verify_component(expected, actual, visual_by_id.get(source_id), actual_assets,
                                                             assets_by_id, nodes, static_masks, ui_shader, root, prefab_id))
            dynamic_gaps = _expected_dynamic_gaps(expected)
            if dynamic_gaps is None:
                continue
            if dynamic_gaps or expected.get('sourceHasStaticDataReference') is not True:
                warnings.append(diagnostic('SPINE_DYNAMIC_BEHAVIOR_INCOMPLETE', relative,
                    'Static Spine fields are checked; source-only playTimes/cache and/or unbound runtime assignment remain explicitly unverified: ' + source_id,
                    prefab_id))
        stage_gaps = saved.get('stageGaps')
        if not isinstance(stage_gaps, list):
            fail('Per-Prefab Spine stageGaps array is missing', prefab_id)
        else:
            expected_gap_pairs = set()
            for component in expected_components:
                expected_gap_pairs.update((component['sourceComponentId'], gap)
                                          for gap in (_expected_dynamic_gaps(component) or []))
                if component.get('sourceHasStaticDataReference') is not True:
                    expected_gap_pairs.add((component['sourceComponentId'], 'dynamic_skeleton_data_assignment_unverified'))
            observed_gap_pairs = set()
            for gap in stage_gaps:
                if (not isinstance(gap, dict) or gap.get('code') != 'SPINE_COMPONENT_READBACK_GAP' or
                        not isinstance(gap.get('sourceId'), str) or not isinstance(gap.get('message'), str)):
                    fail('Per-Prefab Spine readback has an unknown stage gap', prefab_id)
                    continue
                observed_gap_pairs.add((gap['sourceId'], gap['message']))
            if observed_gap_pairs != expected_gap_pairs:
                fail('Per-Prefab Spine stage-gap set differs from explicit dynamic gaps', prefab_id)

    return failures + warnings
