import zlib

import pytest

from grea.recovery.unity_animation_bindings import restore, restore_script_slots
from grea.recovery.unity_asset_references import reference_type
from grea.recovery.unity_gles_shader import translate_program


def test_clip_names_require_exact_original_crc():
    path = 'Panel/标题 (1)'
    code = zlib.crc32(path.encode())
    raw = f'    path: path_0x{code:X}_unknown\n'.encode()
    result, edits = restore(raw, paths={code: path})
    assert result == ('    path: "' + path + '"\n').encode()
    assert edits[0]['hash'] == code
    with pytest.raises(ValueError, match='CRC'):
        restore(raw, paths={code: 'guessed/path'})
    assert restore(raw)[0] == raw


def test_clip_script_slots_preserve_distinct_source_component_types():
    prop = zlib.crc32(b'm_Color.a')
    code = zlib.crc32(b'Panel/Icon')
    sentinel = '{fileID: 0, guid: 0000000deadbeef15deadf00d0000000, type: 2}'
    raw = (f'    attribute: m_Color.a\n    path: Panel/Icon\n    classID: 114\n    script: {{fileID: 0}}\n'
           f'      path: {code}\n      attribute: {prop}\n      script: {sentinel}\n'
           '    attribute: m_Color.a\n    path: Panel/Label\n    classID: 114\n    script: {fileID: 0}\n').encode()
    icon = ('a' * 32, 11500000)
    label = ('b' * 32, 11500000)
    result, edits = restore_script_slots(raw, {(code, prop): icon, (zlib.crc32(b'Panel/Label'), prop): label})
    assert result.count(('guid: ' + icon[0]).encode()) == 2
    assert result.count(('guid: ' + label[0]).encode()) == 1
    assert len(edits) == 3
    assert b'deadbeef' not in result


@pytest.mark.parametrize(('path', 'expected'), [
    ('Assets/Game/Content/Shaders/skin.shader', 3),
    ('Assets/Game/Content/Shaders/skin.asset', 2),
    ('Assets/Game/Content/Materials/skin.mat', 2),
    ('Assets/Game/Content/Fonts/body.ttf', 3),
    ('Resources/unity_builtin_extra', 0),
])
def test_pptr_storage_tracks_the_actual_destination_importer(path, expected):
    assert reference_type(path) == expected


def test_unknown_importer_does_not_inherit_provider_storage():
    with pytest.raises(ValueError, match='Unknown native'):
        reference_type('Assets/custom.unknown')


def test_gles2_scalar_varying_and_fragment_output():
    raw = '''#ifdef VERTEX
attribute highp vec4 in_POSITION0;
varying mediump float vs_TEXCOORD0;
void main(){ gl_Position = in_POSITION0; vs_TEXCOORD0 = 0.5; }
#endif
#ifdef FRAGMENT
uniform sampler2D _MainTex;
varying mediump float vs_TEXCOORD0;
#define SV_Target0 gl_FragData[0]
void main(){ SV_Target0 = texture2D(_MainTex, vec2(vs_TEXCOORD0)); }
#endif'''
    code = translate_program(raw)
    assert 'float vs_TEXCOORD0 : TEXCOORD0;' in code
    assert 'o.pos = v.in_POSITION0' in code
    assert 'result = GreaSample2D(_MainTex' in code
    assert 'i.vs_TEXCOORD0' in code
    assert 'gl_FragData' not in code


def test_shadow_comparison_and_matrix_array_keep_native_bindings():
    raw = '''#ifdef VERTEX
uniform vec4 hlslcc_mtx4x4_Bones[8];
in vec4 in_POSITION0;
out vec3 vs_TEXCOORD0;
void main(){gl_Position = hlslcc_mtx4x4_Bones[5] + in_POSITION0; vs_TEXCOORD0 = vec3(0.2);}
#endif
#ifdef FRAGMENT
uniform sampler2DShadow hlslcc_zcmp_ShadowMapTexture;
in vec3 vs_TEXCOORD0;
out vec4 SV_Target0;
void main(){SV_Target0 = vec4(textureLod(hlslcc_zcmp_ShadowMapTexture, vs_TEXCOORD0, 0.0));}
#endif'''
    code = translate_program(raw)
    assert 'float4x4 _Bones[2];' in code
    assert 'transpose(_Bones[(int)(5)/4])[(int)(5)%4]' in code
    assert 'UNITY_DECLARE_SHADOWMAP(_ShadowMapTexture);' in code
    assert 'UNITY_SAMPLE_SHADOW(_ShadowMapTexture, i.vs_TEXCOORD0)' in code
    assert 'hlslcc_zcmp_' not in code
    with pytest.raises(ValueError, match='Nonzero comparison'):
        translate_program(raw.replace('vs_TEXCOORD0, 0.0)', 'vs_TEXCOORD0, 2.0)'))


def test_reference_remap_changes_storage_and_preserves_subobject_identity():
    from grea.recovery.unity_asset_references import remap_pointers
    old, new = 'a' * 32, 'b' * 32
    raw = f'{{fileID: 4800000, guid: {old}, type: 2}}\n{{fileID: 42, guid: {old}, type: 2}}'.encode()
    actual = remap_pointers(raw, {old: (4800000, new, 4800000, 'Assets/Game/Content/Shaders/native.shader')})
    assert actual == f'{{fileID: 4800000, guid: {new}, type: 3}}\n{{fileID: 42, guid: {new}, type: 3}}'.encode()


def test_visual_handoff_rejects_ambiguous_material_slots_and_path_escape(tmp_path):
    import argparse
    import json
    from grea.features.asset.prepare_visual import prepare
    texture = tmp_path / 'texture.json'
    atlas = tmp_path / 'atlas.json'
    bindings = tmp_path / 'binding.json'
    texture.write_text('{"textures": []}')
    atlas.write_text('{"atlases": []}')
    row = dict(material='Assets/Game/Content/Materials/Test.mat', property='_MainTex',
               texture='Assets/Game/Content/Textures/test.png', textureGuid='a'*32, allowed=['b'*32])
    bindings.write_text(json.dumps(dict(materials=[row, row])))
    args = argparse.Namespace(texture_plan=str(texture), atlas_plan=str(atlas), font_plan=None,
                              binding_plan=str(bindings), output=str(tmp_path/'result'), packable_sprites=True)
    with pytest.raises(ValueError, match='Duplicate or conflicting'):
        prepare(args)
    row['texture'] = 'Assets/../outside.png'
    bindings.write_text(json.dumps(dict(materials=[row])))
    with pytest.raises(ValueError, match='canonical'):
        prepare(args)
    assert not (tmp_path/'result').exists()


def test_visual_handoff_pins_native_atlas_authoring_helper(tmp_path):
    import argparse
    from grea.features.asset.prepare_visual import prepare
    texture = tmp_path / 'texture.json'
    atlas = tmp_path / 'atlas.json'
    texture.write_text('{"textures": []}')
    atlas.write_text('{"atlases": []}')
    result = prepare(argparse.Namespace(texture_plan=str(texture), atlas_plan=str(atlas), font_plan=None,
                     binding_plan=None, output=str(tmp_path/'result'), packable_sprites=True))
    assert result['nativeReadback'] == 'not_run'
    assert (tmp_path/'result'/'SpriteAtlasRecovery.cs').is_file()


def test_existing_project_budget_does_not_raise_candidate_output_budget():
    from grea.development.output_limits import check_inventory, check_project_inventory, FILE_BYTES
    from grea.development.errors import BeaverError
    rows = [dict(bytes=FILE_BYTES) for _ in range(18)]
    check_project_inventory(rows, 'existing-project')
    with pytest.raises(BeaverError, match='OUTPUT_BUDGET'):
        check_inventory(rows, dict(scopeMode='whole-input'), 'candidate')
    with pytest.raises(BeaverError, match='OUTPUT_BUDGET'):
        check_inventory(rows, dict(scopeMode='existing-project'), 'candidate-cannot-select-project-policy')
    with pytest.raises(BeaverError, match='OUTPUT_BUDGET'):
        check_project_inventory([dict(bytes=FILE_BYTES) for _ in range(129)], 'too-large-project')
