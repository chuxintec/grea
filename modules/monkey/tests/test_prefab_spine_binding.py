import hashlib
import tempfile
import unittest
from pathlib import Path

from monkey.prefab_spine_binding import build_source_binding_contract, recover_private_sidecar


def varint(value):
    out=bytearray()
    while value>0x7f:
        out.append((value&0x7f)|0x80);value>>=7
    out.append(value);return bytes(out)


def spine_string(value):
    raw=value.encode();return varint(len(raw)+1)+raw


def fixture_manifest(component=None,duplicate_data=False,redirect=False,atlas_page='page.png'):
    root=Path(tempfile.mkdtemp(dir='/private/tmp',prefix='spine-fixture-'));(root/'native').mkdir()
    binary=spine_string('source-hash')+spine_string('3.8.99')+b'fixture-binary-payload';texture=b'fixture texture bytes'
    (root/'native/skeleton.bin').write_bytes(binary);(root/'native/page.png').write_bytes(texture)
    data_uuid='12345678-1234-4234-8234-123456789abc';texture_uuid='abcdefab-cdef-4abc-8def-abcdefabcdef'
    comp={'__type__':'sp.Skeleton','node':{'__id__':2},'_N$skeletonData':{'__uuid__':data_uuid},
          'defaultSkin':'default','defaultAnimation':'idle','_animationName':'idle','loop':False,'_playTimes':2,
          'premultipliedAlpha':False,'_preCacheMode':1}
    if component is not None:comp=component
    atlas=f'\n{atlas_page}\nsize: 1,1\nformat: RGBA8888\nfilter: Linear,Linear\nrepeat: none\nregion\n  rotate: false\n'
    prefab={'bundle':'gameAsset','key':'prefab-uuid','sourceId':'gameAsset:prefab-uuid','kind':'cc.Prefab','logicalPath':'Prefab/UI/Test',
            'document':{'root':0,'instances':[{'__type__':'cc.Prefab','data':{'__id__':1}},
              {'__type__':'cc.Node','_name':'Root','_children':[{'__id__':2}]},
              {'__type__':'cc.Node','_name':'SpineNode','_parent':{'__id__':1},'_components':[{'__id__':3}]},comp]}}
    data={'bundle':'spineAsset','key':data_uuid,'sourceId':'spineAsset:'+data_uuid,'kind':'sp.SkeletonData','logicalPath':'Spine/Exact/Asset',
          'native':'native/skeleton.bin','document':{'root':0,'instances':[{'__type__':'sp.SkeletonData','_name':'other-name',
            '_atlasText':atlas,'textureNames':[atlas_page],'textures':[{'__uuid__':texture_uuid}]}]}}
    texture_row={'bundle':'spineAsset','key':texture_uuid,'sourceId':'spineAsset:'+texture_uuid,'kind':'cc.Texture2D','logicalPath':'Texture/UnrelatedName','native':'native/page.png','document':{'root':0,'instances':[{'__type__':'cc.Texture2D'}]}}
    assets=[prefab,data,texture_row,{'bundle':'gameAsset','key':data_uuid,'sourceId':'gameAsset:'+data_uuid,'kind':'redirect','redirectBundle':'spineAsset','redirectTarget':'spineAsset:'+data_uuid}]
    if duplicate_data:
        duplicate=dict(data,logicalPath='Spine/Another/Asset')
        assets.extend([duplicate,dict(duplicate)])
    if redirect:
        redirected_uuid='11111111-2222-4333-8444-555555555555'
        data['document']['instances'][0]['textures']=[{'__uuid__':redirected_uuid}]
        assets[2]['sourceId']='spineAsset:real-texture';assets[2]['key']='real-texture'
        assets.append({'bundle':'spineAsset','key':redirected_uuid,'sourceId':'spineAsset:'+redirected_uuid,'kind':'redirect','redirectTarget':'spineAsset:real-texture'})
    inputs=[]
    for rel in ('native/skeleton.bin','native/page.png'):
        raw=(root/rel).read_bytes();inputs.append({'bundle':'spineAsset','path':rel,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    manifest={'bundle':'gameAsset','sourceProfile':'fixture','sourceVersion':'2.4.15','sourceRoots':{'gameAsset':str(root),'spineAsset':str(root)},'inputs':inputs,'assets':assets}
    return manifest,root


class PrefabSpineBindingTests(unittest.TestCase):
    def test_exact_uuid_cross_bundle_binding_preserves_serialized_fields_and_receipts(self):
        manifest,_=fixture_manifest()
        contract=build_source_binding_contract(manifest,[{'id':'P01','sourceId':'gameAsset:prefab-uuid'}])
        self.assertEqual(contract['boundComponentCount'],1)
        self.assertEqual(contract['unboundComponentCount'],0)
        bind=contract['bindings'][0]
        self.assertEqual(bind['sourceComponentId'],'gameAsset:prefab-uuid#3')
        self.assertEqual(bind['nodePath'],'Root/SpineNode')
        self.assertEqual(bind['dataAssetSourceId'],'spineAsset:12345678-1234-4234-8234-123456789abc')
        self.assertEqual(bind['properties']['skin']['sourceFields']['defaultSkin'],'default')
        self.assertEqual(bind['properties']['loop']['sourceFields']['loop'],False)
        self.assertEqual(bind['properties']['tint']['status'],'not_serialized_default_unresolved')
        data=contract['skeletonData'][0]
        self.assertEqual(data['spineVersion'],'3.8.99')
        self.assertEqual(data['skeletonDataReceipt']['status'],'verified')
        self.assertEqual(data['pageClosureStatus'],'complete')
        self.assertEqual(data['atlasPages'][0]['sourceReceipt']['status'],'verified')
        self.assertEqual(contract['nativeIdentityStatus'],'not_run')
        self.assertFalse(contract['callbacksExecuted'])

    def test_inline_components_use_normalizer_source_id_scheme_and_count_once(self):
        manifest,_=fixture_manifest()
        prefab=next(a for a in manifest['assets'] if a['sourceId']=='gameAsset:prefab-uuid')
        prefab['document']['instances'][1]['_components']=[{'__type__':'sp.Skeleton','node':{'__id__':1},
            '_N$skeletonData':{'__uuid__':'12345678-1234-4234-8234-123456789abc'},'defaultSkin':'inline'}]
        contract=build_source_binding_contract(manifest,[{'id':'P01','sourceId':'gameAsset:prefab-uuid'}])
        by_id={row['sourceComponentId']:row for row in contract['bindings']}
        self.assertEqual(set(by_id),{'gameAsset:prefab-uuid#1/components/0','gameAsset:prefab-uuid#3'})
        self.assertEqual(by_id['gameAsset:prefab-uuid#1/components/0']['sourceOrigin'],'inline-node-component')
        self.assertEqual(by_id['gameAsset:prefab-uuid#3']['sourceOrigin'],'top-level-instance')
        self.assertEqual(contract['skeletonComponentCount'],2)

    def test_absent_uuid_does_not_bind_to_same_named_data(self):
        manifest,_=fixture_manifest(component={'__type__':'sp.Skeleton','node':{'__id__':1},'_name':'ExactSameName'})
        manifest['assets'][1]['document']['instances'][0]['_name']='ExactSameName'
        contract=build_source_binding_contract(manifest,[{'id':'P01','sourceId':'gameAsset:prefab-uuid'}])
        self.assertEqual(contract['boundComponentCount'],0)
        self.assertEqual(contract['unbound'][0]['status'],'skeleton_data_uuid_not_serialized')

    def test_duplicated_uuid_is_ambiguous_and_never_bundle_guessed(self):
        manifest,_=fixture_manifest(duplicate_data=True)
        contract=build_source_binding_contract(manifest,[{'id':'P01','sourceId':'gameAsset:prefab-uuid'}])
        self.assertEqual(contract['boundComponentCount'],0)
        self.assertEqual(contract['unbound'][0]['status'],'source_uuid_ambiguous')

    def test_texture_redirect_is_followed_only_through_exact_source_id(self):
        manifest,_=fixture_manifest(redirect=True)
        contract=build_source_binding_contract(manifest,[{'id':'P01','sourceId':'gameAsset:prefab-uuid'}])
        page=contract['skeletonData'][0]['atlasPages'][0]
        self.assertEqual(page['textureMatch']['status'],'exact_bundle_uuid_texture_match')
        self.assertEqual(page['textureMatch']['sourceId'],'spineAsset:real-texture')
        self.assertEqual(page['sourceReceipt']['status'],'verified')

    def test_atlas_page_identity_mismatch_is_an_explicit_closure_gap(self):
        manifest,_=fixture_manifest(atlas_page='some-other.png')
        manifest['assets'][1]['document']['instances'][0]['textureNames']=['not-the-atlas-page.png']
        contract=build_source_binding_contract(manifest,[{'id':'P01','sourceId':'gameAsset:prefab-uuid'}])
        self.assertEqual(contract['skeletonData'][0]['dataDocumentStatus'],'atlas_page_order_or_texture_count_mismatch')

    def test_sidecar_writer_rejects_destinations_outside_authorized_private_root(self):
        manifest,_=fixture_manifest()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):recover_private_sidecar(manifest,Path(temp)/'outside',allowed_root=Path(temp)/'allowed',namespace='fixture')


if __name__=='__main__':unittest.main()
