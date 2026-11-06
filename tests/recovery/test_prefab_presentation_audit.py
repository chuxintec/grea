from grea.recovery.prefab_presentation_audit import check_images, check_parent_links


def test_parent_identity_detects_swap_between_same_named_groups():
    def node(local_id):
        return dict(hierarchy='Group', physicalComponents=[
            dict(nativeType='UnityEngine.RectTransform', guid='asset', localFileId=local_id)])
    saved = {'a': node(10), 'b': node(20), 'child': node(30)}
    count, issues = check_parent_links({'30': '  m_Father: {fileID: 20}\n'}, saved,
                                       {'child': {'parent': 'a'}}, 'asset')
    assert count == 0 and issues


def test_wrong_sprite_from_same_project_is_detected(tmp_path):
    expected = 'a' * 32
    (tmp_path/'frame.png.meta').write_text('guid: ' + expected + '\n')
    sprites = [dict(sourceId='sprite', spriteFrame='frame', convertible=True, trim=False,
                    untrimmedGeometryPolicy='creator24-packed-frame-insets')]
    receipt = dict(guid='asset', components=[dict(sourceId='sprite', guid='asset', localFileId=7)])
    bindings, issues = check_images(tmp_path, {'7': '  m_Sprite: {fileID: 21300000, guid: ' +
                                               'b' * 32 + ', type: 3}\n'}, receipt, sprites,
                                    {'frame': {'path': 'frame.png'}})
    assert bindings[0]['expectedTexture'] == expected and issues
