"""Bounded Renderer scalar storage bridge, never a general byte-to-bool rule.

Unity 2021.3 Renderer declares these APIs as bool (including native bindings
IsDynamicOccludee and Get/SetIsStaticShadowCaster):
https://github.com/Unity-Technologies/UnityCsReference/blob/2021.3/Runtime/Export/Graphics/GraphicsRenderers.bindings.cs
The exact source object's TypeTree must independently prove UInt8 storage.
The native verifier still requires Boolean at the same target field path.
"""
from .sources.compiled import fail


_RENDERERS = {'MeshRenderer': 23, 'TrailRenderer': 96, 'LineRenderer': 120,
              'SkinnedMeshRenderer': 137, 'ParticleSystemRenderer': 199, 'SpriteRenderer': 212}
_BOOLEAN_APIS = {'m_DynamicOccludee': 'Renderer.allowOcclusionWhenDynamic',
                 'm_StaticShadowCaster': 'Renderer.staticShadowCaster',
                 'm_ReceiveShadows': 'Renderer.receiveShadows'}


def renderer_scalar_mapping(source_type, class_id, source_versions, target_version, path, value, schema):
    """Return a lossless, explicitly evidenced storage normalization or None."""
    if source_type not in _RENDERERS or class_id != _RENDERERS[source_type] or path not in _BOOLEAN_APIS:
        return None
    if isinstance(value, bool) or isinstance(schema, dict) and schema.get('type') == 'bool':
        return None  # Ordinary source bool handling already preserves its type.
    if source_versions != ['2021.3.30f1'] or target_version != '6000.6.2f1':
        fail('UNITY_PREFAB_RENDERER_PROFILE_VERSION', path, 'Renderer scalar bridge is version bounded')
    if (not isinstance(schema, dict) or schema.get('name') != path or schema.get('type') != 'UInt8'
            or schema.get('children') or schema.get('byteSize') != 1):
        fail('UNITY_PREFAB_RENDERER_PROFILE_SCHEMA', path, 'Exact source-object UInt8 TypeTree required')
    if type(value) is not int or value not in (0, 1):
        fail('UNITY_PREFAB_RENDERER_PROFILE_VALUE', path, 'Only exact byte0/1 fits a declared native Boolean')
    return dict(path=path, kind='boolean', boolValue=value == 1, sourceStoredKind='UInt8', sourceStoredValue=value,
                mapping='unity-2021.3-renderer-byte01-to-6000.6-Boolean-v1', sourceApi=_BOOLEAN_APIS[path],
                targetStorage='Boolean-required-by-native-verifier')
