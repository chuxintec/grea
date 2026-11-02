import pytest

from monkey.unity_prefab_renderer_profiles import renderer_scalar_mapping
from monkey.sources.compiled import ParseError


def bridge(value=1, field='m_DynamicOccludee', typ='LineRenderer', cid=120, schema=None, versions=None):
    return renderer_scalar_mapping(typ, cid, versions or ['2021.3.30f1'], '6000.6.2f1', field, value,
        schema if schema is not None else dict(name=field, type='UInt8', byteSize=1, children=[]))


@pytest.mark.parametrize('field', ['m_DynamicOccludee', 'm_StaticShadowCaster', 'm_ReceiveShadows'])
@pytest.mark.parametrize('value', [0, 1])
def test_renderer_declared_boolean_retains_source_byte_and_requires_native_boolean(field, value):
    row = bridge(value, field)
    assert row['kind'] == 'boolean' and row['boolValue'] is (value == 1)
    assert row['sourceStoredKind'] == 'UInt8' and row['sourceStoredValue'] == value
    assert row['targetStorage'] == 'Boolean-required-by-native-verifier'


@pytest.mark.parametrize('field', ['m_CastShadows', 'm_MotionVectors', 'm_LightProbeUsage', 'customByte'])
def test_enum_and_other_bytes_are_never_coerced(field):
    assert bridge(1, field) is None


def test_wrong_class_id_custom_component_or_existing_bool_do_not_use_bridge():
    assert bridge(1, typ='MonoBehaviour', cid=114) is None
    assert bridge(1, cid=199) is None
    assert bridge(True) is None


@pytest.mark.parametrize('value', [2, 255, -1, 1.0])
def test_non_boolean_source_values_fail(value):
    with pytest.raises(ParseError, match='UNITY_PREFAB_RENDERER_PROFILE_VALUE'):
        bridge(value)


def test_missing_wrong_schema_and_other_versions_fail():
    for schema in [{}, dict(name='m_DynamicOccludee', type='UInt16', byteSize=2, children=[])]:
        with pytest.raises(ParseError, match='UNITY_PREFAB_RENDERER_PROFILE_SCHEMA'):
            bridge(schema=schema)
    with pytest.raises(ParseError, match='UNITY_PREFAB_RENDERER_PROFILE_VERSION'):
        bridge(versions=['2022.3.1f1'])
