import tempfile,unittest
from pathlib import Path
from monkey import io
from monkey.prefab_static_button import enrich
from monkey.sources.compiled import ParseError

class StaticButtonTests(unittest.TestCase):
    def candidate(self,root,source=None,profile='cocos-2.4.15-bundle'):
        m={'assets':[{'sourceId':'b:panel','document':{'instances':[
            {'__type__':'cc.Prefab'}, {'__type__':'cc.Node'},
            {'__type__':'cc.Button','node':{'__id__':1},**(source or {})}]}}]}
        io.write_json(root/'source-manifest.json',m);io.finish(root,{'sourceProfile':profile})
        return {'sourceProfile':profile,'sourceManifestPath':str(root/'source-manifest.json'),
                'sourceManifestSha256':io.sha((root/'source-manifest.json').read_bytes()),
                'components':[{'sourceId':'b:panel#2','type':'cc.Button','node':'b:panel#1','transition':1,'enabled':True}]}
    def test_explicit_packed_color_and_version_defaults_are_retained(self):
        with tempfile.TemporaryDirectory()as tmp:
            ir=self.candidate(Path(tmp).resolve(),{'_N$disabledColor':{'__value_type__':4,'values':[0xFF030201]}});enrich(ir)
            s=ir['components'][0]['staticButtonBinding']
            self.assertEqual(s['disabledColor'],[1,2,3,255]);self.assertEqual(s['pressedColor'],[211,211,211,255])
            self.assertEqual(s['behavior'],'disabled');self.assertFalse(s['eventsBound']);self.assertTrue(s['renderReady'])
    def test_auto_gray_requires_material_mapping_and_unknown_profile_is_not_assumed(self):
        with tempfile.TemporaryDirectory()as tmp:
            ir=self.candidate(Path(tmp).resolve(),{'enableAutoGrayEffect':True});enrich(ir)
            self.assertFalse(ir['components'][0]['staticButtonBinding']['renderReady'])
            ir['sourceProfile']='unknown';ir['components'][0].pop('staticButtonBinding');enrich(ir)
            self.assertNotIn('staticButtonBinding',ir['components'][0])
    def test_frozen_manifest_changes_are_rejected(self):
        with tempfile.TemporaryDirectory()as tmp:
            ir=self.candidate(Path(tmp).resolve());Path(ir['sourceManifestPath']).write_text('{}')
            with self.assertRaises(ParseError):enrich(ir)

    def test_none_and_external_scale_targets_preserve_disabled_source_policy(self):
        for transition,zoom in [(0,1.1),(3,.85)]:
            with tempfile.TemporaryDirectory() as tmp:
                ir=self.candidate(Path(tmp).resolve(),{'_N$transition':transition,'zoomScale':zoom})
                c=ir['components'][0];c.update(transition=transition,zoomScale=zoom,target='b:panel#9')
                enrich(ir);spec=c['staticButtonBinding']
                self.assertEqual(spec['sourceTransition'],transition)
                self.assertEqual(spec['sourceZoomScale'],zoom)
                self.assertEqual(c['target'],'b:panel#9')
                self.assertEqual(spec['behavior'],'disabled')
                self.assertFalse(spec['eventsBound'])
                self.assertTrue(spec['renderReady'])
