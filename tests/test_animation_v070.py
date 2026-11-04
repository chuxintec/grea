import math
import unittest

from monkey.assets.animation import normalize_clip, plan_clips, _source_progress


def clip(prop='position',curve='sineOut',start=0.0,end=1.0):
    value0=[start,start,0.0] if prop=='position' else ([start,start,1.0] if prop=='scale' else start)
    value1=[end,end,0.0] if prop=='position' else ([end,end,1.0] if prop=='scale' else end)
    return dict(__type__='cc.AnimationClip',_name='v070 curve fixture',_duration=1.0,sample=30,
        curveData={'props':{},'paths':{'child':{'props':{prop:[dict(frame=0.0,value=value0,curve=curve),dict(frame=1.0,value=value1)]}}}},events=[])


def source_value(curve,a,b,u):
    return a+(b-a)*_source_progress(curve,u)


def dense_error(keys,curve,a,b,intervals=10000):
    worst=0.0
    for i in range(intervals+1):
        t=i/intervals
        for left,right in zip(keys,keys[1:]):
            if t<=right['time']+1e-15:
                local=(t-left['time'])/(right['time']-left['time'])
                approx=left['value']+(right['value']-left['value'])*local
                exact=source_value(curve,a,b,t)
                worst=max(worst,abs(exact-approx));break
    return worst


class AnimationV070Tests(unittest.TestCase):
    def test_cocos_sine_easing_endpoints_midpoint_and_adaptive_native_keys(self):
        self.assertAlmostEqual(_source_progress('sineIn',0),0)
        self.assertAlmostEqual(_source_progress('sineIn',1),1)
        self.assertAlmostEqual(_source_progress('sineOut',.5),math.sqrt(.5))
        self.assertAlmostEqual(_source_progress('sineInOut',.5),.5)
        normalized,gaps=normalize_clip(clip('position','sineOut',0,10),'source:clip','fixture#instances/0')
        track=next(t for t in normalized['tracks'] if t['property']=='position.x')
        self.assertFalse(gaps)
        self.assertGreater(len(track['keys']),2)
        self.assertEqual(track['keys'][0]['time'],0)
        self.assertEqual(track['keys'][-1]['time'],1)
        self.assertTrue(all(a['time']<b['time'] for a,b in zip(track['keys'],track['keys'][1:])))
        evidence=track['curveApproximation']
        self.assertEqual(evidence['tolerance'],.25)
        self.assertLessEqual(dense_error(track['keys'],'sineOut',0,10),evidence['tolerance'])
        self.assertLessEqual(evidence['maxAbsoluteProbeError'],evidence['tolerance'])

    def test_cocos_cubic_bezier_control_order_and_error_bound(self):
        curve=[.25,.1,.25,1.0]
        self.assertAlmostEqual(_source_progress(curve,0),0,places=12)
        self.assertAlmostEqual(_source_progress(curve,1),1,places=12)
        self.assertGreater(_source_progress(curve,.5),.5)
        normalized,gaps=normalize_clip(clip('scale',curve,1,2),'source:bezier','fixture#instances/0')
        track=next(t for t in normalized['tracks'] if t['property']=='scale.x')
        self.assertFalse(gaps)
        self.assertGreater(len(track['keys']),2)
        evidence=track['curveApproximation']
        self.assertLessEqual(dense_error(track['keys'],curve,1,2),evidence['tolerance'])
        self.assertEqual(evidence['method'],'adaptive-source-curve-to-linear')

    def test_cocos_identity_bezier_special_case_remains_linear(self):
        normalized,gaps=normalize_clip(clip('opacity',[0.0,0.0,1.0,1.0],0,255),'source:identity','fixture#instances/0')
        track=next(t for t in normalized['tracks'] if t['property']=='opacity')
        self.assertFalse(gaps)
        self.assertEqual(len(track['keys']),2)
        self.assertNotIn('curveApproximation',track)

    def test_non_monotonic_bezier_and_key_budget_fail_explicitly(self):
        for curve,expected in [([.8,.2,.2,.8],'ANIMATION_APPROXIMATION_UNVERIFIED'),([.25,1e7,.75,-1e7],'ANIMATION_APPROXIMATION_BUDGET')]:
            normalized,gaps=normalize_clip(clip('opacity',curve,0,255),'source:bad','fixture#instances/0')
            self.assertFalse(normalized['tracks'])
            self.assertIn(expected,{g['code'] for g in gaps})

    def test_other_properties_and_unknown_easing_are_not_smoothed(self):
        doc=clip('x','sineOut',0,10)
        normalized,gaps=normalize_clip(doc,'source:x','fixture#instances/0')
        self.assertFalse(normalized['tracks'])
        self.assertIn('ANIMATION_INTERPOLATION_UNSUPPORTED',{g['code'] for g in gaps})
        doc=clip('opacity','backOut',0,255)
        normalized,gaps=normalize_clip(doc,'source:unknown','fixture#instances/0')
        self.assertFalse(normalized['tracks'])
        self.assertIn('ANIMATION_INTERPOLATION_UNSUPPORTED',{g['code'] for g in gaps})


    def test_native_plan_uses_approximated_linear_keys_without_executing_events(self):
        class Naming:
            def reserve(self,items):pass
            def path(self,sid,kind,suffix,metadata=None):return 'Assets/Game/Content/Animations/Curve.anim'
        doc=clip('opacity','sineInOut',0,255);doc['events']=[dict(frame=.5,func='callback',params=[])]
        normalized,gaps=normalize_clip(doc,'gameAsset:curve','curve.json#instances/0')
        ir={'animationSchemaVersion':1,'sourceProfile':'cocos-2.4.15-bundle','sourceNames':{'gameAsset:curve':{'logicalPath':'Prefab/UI/Task/TaskItem'}},
            'nodes':[{'sourceId':'root','name':'Root','parent':None,'children':['child'],'position':[0,0,0],'scale':[1,1,1]},{'sourceId':'child','name':'child','parent':'root','children':[],'position':[0,0,0],'scale':[1,1,1]}],
            'components':[{'sourceId':'root#animation','type':'cc.Animation','node':'root','clips':['gameAsset:curve'],'enabled':True}],
            'animationClips':[normalized]}
        specs,plan_gaps=plan_clips(ir,'fixture','unity-6000.6.2f1-ugui',naming=Naming())
        self.assertFalse(plan_gaps)
        track=specs[0]['tracks'][0]
        self.assertGreater(len(track['keys']),2)
        self.assertTrue(all(k['interpolation']=='linear' for k in track['keys']))
        self.assertTrue(all(k['time']<b['time'] for k,b in zip(track['keys'],track['keys'][1:])))
        self.assertEqual(specs[0]['events'][0]['binding'],'manual-only')
        self.assertFalse(specs[0]['events'][0]['executed'])
        self.assertFalse(specs[0]['autoPlay'])

    def test_source_events_remain_manual_contracts(self):
        doc=clip('opacity','sineOut',0,255)
        doc['events']=[dict(frame=.5,func='onReward',params=['coin'])]
        normalized,gaps=normalize_clip(doc,'source:event','fixture#instances/0')
        self.assertTrue(normalized['tracks'])
        self.assertEqual(normalized['events'][0]['binding'],'manual-only')
        self.assertFalse(normalized['events'][0]['executed'])
        self.assertIn('ANIMATION_EVENT_BINDING_REQUIRED',{g['code'] for g in gaps})


if __name__=='__main__':unittest.main()
