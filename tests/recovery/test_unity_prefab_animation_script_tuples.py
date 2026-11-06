from grea.recovery.unity_prefab_script_tuples import rebind


def test_animation_curve_and_binding_table_use_the_same_sdk_script():
    source = '8b6b0933debec03db3ed40115224c1a8'
    target = '1234567890abcdef1234567890abcdef'
    pointer = f'{{fileID: 11500000, guid: {source}, type: 3}}'
    clip = (f'%YAML 1.1\n--- !u!74 &7400000\nAnimationClip:\n'
            f'    classID: 114\n    script: {pointer}\n'
            f'      script: {pointer}\n      typeID: 114\n'
            f'    value: {pointer}\n').encode()
    bindings = {(source, 11500000, 3): (target, 11500000, 3)}
    updated = rebind(clip, bindings)
    assert updated.count(target.encode()) == 2
    assert f'    value: {pointer}'.encode() in updated
    assert rebind(updated, bindings) == updated
    other = clip.replace(b'!u!74 &7400000\nAnimationClip:', b'!u!114 &11400000\nMonoBehaviour:')
    assert rebind(other, bindings) == other
