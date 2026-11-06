import pytest

from grea.recovery.unity_gles_shader import translate_vector_constructors


@pytest.mark.parametrize(('name','operator'), [
    ('lessThan','<'), ('lessThanEqual','<='), ('greaterThan','>'),
    ('greaterThanEqual','>='), ('equal','=='), ('notEqual','!='),
])
def test_vector_comparison_preserves_components_and_nested_constructors(name, operator):
    source = f'{name}(u.xy, vec2(-1.0, v.x)).yx'
    expected = f'((u.xy) {operator} (float2(-1.0, v.x))).yx'
    assert ''.join(translate_vector_constructors(source).split()) == ''.join(expected.split())
