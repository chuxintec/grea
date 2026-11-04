import copy
import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

from monkey.normalize import component_ir
from monkey.targets.progress import configure_progress


def fixture():
    progress,_=component_ir('asset',7,{'__type__':'cc.ProgressBar','node':{'__id__':0},
        '_N$barSprite':{'__id__':6},'_N$progress':.6,'_N$totalLength':360})
    progress['convertible']=True
    sprite={'sourceId':'asset#6','node':'asset#1','type':'cc.Sprite','mode':2,
            'spriteFrame':'sprite','convertible':True,'enabled':True}
    nodes={'asset#0':{'sourceId':'asset#0','size':[380,54],'children':['asset#1']},
           'asset#1':{'sourceId':'asset#1','parent':'asset#0','size':[216,34],
                      'anchor':[0,.5],'scale':[1,1,1],'rotation':[0,0,0,1]}}
    return [progress,sprite],nodes


class NativeProgressTests(unittest.TestCase):
    def test_intermediate_source_geometry_preserves_distinct_full_and_parent_lengths(self):
        rows,nodes=fixture();before=copy.deepcopy(nodes)
        self.assertEqual(configure_progress(rows,nodes),[])
        self.assertEqual(rows[0]['barNode'],'asset#1')
        self.assertEqual(rows[0]['totalLength'],360)
        self.assertEqual(rows[0]['directionEvidence'],'source-left-pivot-and-intermediate-width')
        self.assertEqual(nodes,before)

    def test_omitted_numeric_properties_are_not_invented(self):
        row,gaps=component_ir('a',0,{'__type__':'cc.ProgressBar'})
        self.assertIsNone(row['progress']);self.assertIsNone(row['totalLength'])
        self.assertIsNone(row['progressMode']);self.assertIsNone(row['progressReverse'])
        self.assertTrue(gaps)

    def test_exact_engine_profile_restores_omitted_serialized_defaults(self):
        source={'__type__':'cc.ProgressBar','_N$barSprite':{'__id__':2}}
        row,gaps=component_ir('a',0,source,source_profile='cocos-2.4.15-bundle')
        self.assertEqual(gaps,[])
        self.assertEqual([row['progress'],row['totalLength'],row['progressMode'],row['progressReverse']],[1,1,0,False])
        self.assertEqual(row['engineDefaults']['version'],'2.4.15')
        other,_=component_ir('a',0,source,source_profile='cocos-2.4.11-bundle')
        self.assertIsNone(other['progress']);self.assertNotIn('engineDefaults',other)
        explicit,_=component_ir('a',0,dict(source,**{'_N$progress':0}),source_profile='cocos-2.4.15-bundle')
        self.assertEqual(explicit['progress'],0)
        self.assertNotIn('progress',explicit['engineDefaults']['fields'])

    def test_invalid_or_unproven_cases_preserve_geometry_and_handoff(self):
        mutations=[
            lambda r,n:r[0].update(progress=None),
            lambda r,n:r[0].update(progress=True),
            lambda r,n:r[0].update(progress=float('nan')),
            lambda r,n:r[0].update(totalLength=float('inf')),
            lambda r,n:r[0].update(progress=0),
            lambda r,n:r[0].update(progressMode=1),
            lambda r,n:r[0].update(progressMode=False),
            lambda r,n:r[0].update(progressReverse=True),
            lambda r,n:r[0].update(progressReverse=0),
            lambda r,n:r[1].update(mode=3),
            lambda r,n:r[1].update(convertible=False),
            lambda r,n:r[1].update(spriteFrame=None),
            lambda r,n:n['asset#1'].update(size=[228,34]),
            lambda r,n:n['asset#1'].update(anchor=[1,.5]),
            lambda r,n:n['asset#1'].update(scale=[2,1,1]),
            lambda r,n:n['asset#1'].update(parent='other'),
            lambda r,n:r.append(dict(r[0],sourceId='second')),
            lambda r,n:r.append({'sourceId':'widget','node':'asset#1','type':'cc.Widget','enabled':True}),
            lambda r,n:r.append({'sourceId':'layout','node':'asset#0','type':'cc.Layout','enabled':True}),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                rows,nodes=fixture();mutation(rows,nodes);before=copy.deepcopy(nodes)
                gaps=configure_progress(rows,nodes)
                self.assertFalse(rows[0]['convertible']);self.assertTrue(gaps)
                self.assertNotIn('barNode',rows[0]);self.assertEqual(nodes,before)

    def test_explicit_direction_can_preserve_endpoint(self):
        rows,nodes=fixture();rows[0].update(progress=0,progressMode=0,progressReverse=False)
        nodes['asset#1']['size'][0]=0
        self.assertEqual(configure_progress(rows,nodes),[])
        self.assertEqual(rows[0]['directionEvidence'],'explicit-source-direction')

    def test_disabled_geometry_controller_does_not_drive_the_fill(self):
        rows,nodes=fixture()
        rows.append({'sourceId':'widget','node':'asset#1','type':'cc.Widget','enabled':False})
        self.assertEqual(configure_progress(rows,nodes),[])

    def test_static_fields_keep_typed_sprite_reference_for_vertical_reverse_case(self):
        rows,nodes=fixture()
        rows[0].update(progress=.35,totalLength=200,progressMode=1,progressReverse=True)
        nodes['asset#1']['size']=[34,70]
        # This is a neutral parameter change from the old horizontal+tiled
        # profile. It must retain source values without claiming that profile.
        rows[1].update(mode=1)
        gaps=configure_progress(rows,nodes)
        binding=rows[0]['staticProgressBinding']
        self.assertTrue(gaps)
        self.assertFalse(rows[0]['convertible'])
        self.assertEqual(binding['policy'],'native-static-progress-v1')
        self.assertEqual(binding['barSpriteSourceId'],'asset#6')
        self.assertEqual(binding['barNodeSourceId'],'asset#1')
        self.assertEqual([binding['progress'],binding['totalLength'],binding['mode'],binding['reverse']],
                         [.35,200.0,1,True])
        self.assertEqual(binding['displayGeometryEvidence'],'source-bar-axis-matches-progress')

    def test_static_fields_reject_missing_or_unsupported_reference_without_nulling(self):
        for mutation in (
            lambda rows,nodes: rows[0].update(barSprite=None),
            lambda rows,nodes: rows[1].update(convertible=False),
            lambda rows,nodes: rows[0].update(progressMode=3),
            lambda rows,nodes: rows[0].update(progress=math.nan),
        ):
            with self.subTest(mutation=mutation):
                rows,nodes=fixture();mutation(rows,nodes)
                original=rows[0].get('barSprite')
                configure_progress(rows,nodes)
                self.assertNotIn('staticProgressBinding',rows[0])
                if original is not None:
                    self.assertEqual(rows[0]['barSprite'],original)

    def test_native_static_progress_carriers_declare_typed_references_and_persistence(self):
        from pathlib import Path
        targets=Path(__file__).resolve().parents[1]/'src/monkey/targets'
        unity=(targets/'UnityStaticProgress.cs').read_text()
        creator=(targets/'CreatorStaticProgress.js').read_text()
        self.assertIn('Image barSprite;',unity)
        self.assertIn('SerializeField] float progress',unity)
        self.assertIn('component._barSprite = sprite;',creator)
        self.assertIn('component._progress = spec.progress;',creator)
        self.assertIn('component.enabled = false;',creator)

    def test_public_cli_inspects_and_exports_typed_progress_references(self):
        from monkey.cli import main
        from monkey.io import write_json
        from tests.fixtures import fixture, normal, PREFAB, FRAME
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();config=fixture(root/'Source')
            def node(name,parent,children,components,width,height,anchor):
                return dict(__type__='cc.Node',_name=name,_parent=parent,_children=children,
                    _components=components,_contentSize=dict(width=width,height=height),
                    _anchorPoint=dict(x=anchor,y=.5))
            source=[{'__type__':'cc.Prefab','data':{'__id__':1}},
                node('Progress',None,[{'__id__':2}],[{'__id__':4}],380,54,.5),
                node('Bar',{'__id__':1},[],[{'__id__':3}],216,34,0),
                dict(__type__='cc.Sprite',node={'__id__':2},_spriteFrame={'__uuid__':FRAME},_type=2),
                dict(__type__='cc.ProgressBar',node={'__id__':1},**{'_N$barSprite':{'__id__':3},'_N$progress':.6,'_N$totalLength':360})]
            write_json(root/'Source/import'/PREFAB[:2]/(PREFAB+'.a.json'),normal(source))
            commands=[['inspect','--source',str(config),'--source-profile','cocos-2.4.15-bundle','--asset-index','2','--out',str(root/'Inspect')],
                ['normalize','--manifest',str(root/'Inspect/source-manifest.json'),'--out',str(root/'IR')],
                ['plan','--ir',str(root/'IR/ir.json'),'--namespace','progress-test','--target-profile','unity-6000.6.2f1-ugui','--out',str(root/'Plan')],
                ['export','--plan',str(root/'Plan/plan.json'),'--out',str(root/'Candidate')]]
            for command in commands:
                with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(command),0)
            plan=json.loads((root/'Plan/plan.json').read_text())
            progress=next(c for c in plan['components'] if c['type']=='cc.ProgressBar')
            self.assertTrue(progress['convertible']);self.assertEqual(progress['totalLength'],360)
            self.assertEqual(progress['barNode'],'synthetic:'+PREFAB+'#2')
            self.assertTrue((root/'Candidate/Assets/Game/Presentation/Common/Layout/NativeHorizontalProgressFill.cs').is_file())
            for command in [
                ['plan','--ir',str(root/'IR/ir.json'),'--namespace','progress-test','--target-profile','cocos-3.8.8','--out',str(root/'CreatorPlan')],
                ['export','--plan',str(root/'CreatorPlan/plan.json'),'--out',str(root/'CreatorCandidate')]]:
                with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(command),0)
            creator=json.loads((root/'CreatorPlan/plan.json').read_text())
            progress=next(c for c in creator['components']if c['type']=='cc.ProgressBar')
            self.assertTrue(progress['convertible']);self.assertEqual(progress['nativeType'],'cc.ProgressBar')
            self.assertEqual(progress['barNode'],'synthetic:'+PREFAB+'#2')
            self.assertTrue((root/'CreatorCandidate/extensions/monkey-import/progress.js').is_file())


if __name__=='__main__':unittest.main()
