import copy,unittest
from monkey.targets.unity import gallery_readback


class ResourceGalleryTests(unittest.TestCase):
    def test_gallery_is_explicit_not_a_substitute_for_source_nodes_and_keeps_all_sprite_identities(self):
        plan=dict(galleryReadback='exact-sprite-and-rect-v1',galleryOnly=True,nodes=[],components=[],sourcePrefabs=[],textures=[dict(id='frame',guid='a'*32),dict(id='frame@original',guid='b'*32)])
        proof=dict(nativeScope='resources-and-gallery-only',sourceGraphVerification='not_run',gallery=[dict(id='frame',spriteGuid='a'*32,geometryVerified=True)])
        self.assertEqual(gallery_readback(plan,proof),[])
        for mutate in ['foreign','duplicated','missing','geometry','scope']:
            bad=copy.deepcopy(proof)
            if mutate=='foreign':bad['gallery'][0]['spriteGuid']='b'*32
            elif mutate=='duplicated':bad['gallery']*=2
            elif mutate=='missing':bad['gallery']=[]
            elif mutate=='geometry':bad['gallery'][0]['geometryVerified']=False
            else:bad['sourceGraphVerification']='pass'
            self.assertEqual(gallery_readback(plan,bad)[0]['code'],'NATIVE_GALLERY_READBACK')
        plan['nodes']=[dict(sourceId='real-source-node')]
        self.assertTrue(gallery_readback(plan,proof))


if __name__=='__main__':unittest.main()
