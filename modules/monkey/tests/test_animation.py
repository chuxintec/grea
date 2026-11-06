import copy
import hashlib
import struct
import tempfile
import unittest
from pathlib import Path
from monkey.assets.animation import normalize_clip,plan_clips,sample,verify_native
from monkey.io import write_json,read,load,finish
from monkey.sources.compiled import ParseError
from monkey.targets import unity,cocos


def base():
    return dict(__type__='cc.AnimationClip',_name='Synthetic finite UI',_duration=1,sample=30,curveData=dict(paths={'child':dict(props={
        'x':[dict(frame=0,value=10),dict(frame=1,value=30)],
        'scale':[dict(frame=0,value=[1,1,1],curve='constant'),dict(frame=1,value=[2,3,1])],
        'opacity':[dict(frame=0,value=0),dict(frame=1,value=255)]})}),events=[dict(frame=.5,func='reward',params=['item',2])])


def ir_for(clip):
    owner='fixture:scene';root=f'{owner}#2';child=f'{owner}#3';anim=f'{root}/components/0'
    def node(sid,name,parent,children,components=None):return dict(sourceId=sid,name=name,parent=parent,children=children,components=components or [],position=[0,0,0],scale=[1,1,1],rotation=[0,0,0,1],size=[100,100],anchor=[.5,.5],active=True,color=[255]*4,opacity=255)
    c,g=normalize_clip(clip,'source:clip','fixture.anim#instances/0')
    return dict(schemaVersion=1,sourceProfile='cocos-2.4.15-project',sourceRoots={},sourceLocations={},aliases={},
        nodes=[node(root,'Root',None,[child],[anim]),node(child,'child',root,[])],assets=[],spriteFrames=[],bitmapFonts=[],materials=[],diagnostics=g,
        animationSchemaVersion=1,animationClips=[c],components=[dict(sourceId=anim,node=root,type='cc.Animation',clips=['source:clip'],enabled=True,materials=[])])


def write_ir_fixture(root, ir, source_clip):
    """Write an owning stage manifest and a source-pinned Cocos 2.4 fixture manifest."""
    ir_dir = Path(root) / 'ir'
    ir_dir.mkdir(parents=True, exist_ok=True)
    source_root = ir_dir / 'synthetic-source'
    source_root.mkdir(exist_ok=True)
    bundle_root = str(source_root.resolve())
    clip_source = ir.setdefault('sourceNames', {}).setdefault(
        'source:clip', {'bundle': 'fixture', 'logicalPath': 'Anim/Synthetic'})
    ir['sourceRoots'] = {'fixture': bundle_root, clip_source['bundle']: bundle_root}
    scene_objects = [
        {'__type__': 'cc.SceneAsset', '_name': 'SyntheticScene', 'scene': {'__id__': 1}},
        {'__type__': 'cc.Scene', '_name': 'SyntheticScene', 'children': [{'__id__': 2}], '_active': True},
        {'__type__': 'cc.Node', '_name': 'Root', '_parent': {'__id__': 1}, '_children': [{'__id__': 3}],
         '_components': [{'__id__': 4}], '_trs': [0, 0, 0, 0, 0, 0, 1, 1, 1, 1], '_active': True},
        {'__type__': 'cc.Node', '_name': 'child', '_parent': {'__id__': 2}, '_children': [], '_components': [],
         '_trs': [0, 0, 0, 0, 0, 0, 1, 1, 1, 1], '_active': True},
        {'__type__': 'cc.Animation', '_clips': [{'__uuid__': 'synthetic-animation-uuid'}],
         '_defaultClip': None, '_playOnLoad': False, 'node': {'__id__': 2}},
    ]
    source_manifest = {
        'schemaVersion': 1, 'sourceProfile': ir['sourceProfile'], 'sourceVersion': '2.4.15',
        'sourceRoots': ir['sourceRoots'], 'bundle': 'fixture', 'sourceRoot': bundle_root,
        'assets': [
            {'sourceId': 'fixture:scene', 'bundle': 'fixture', 'key': 'synthetic-scene-uuid',
             'kind': 'cc.SceneAsset', 'logicalPath': 'Scenes/Synthetic',
             'document': {'instances': scene_objects, 'root': 0}},
            {'sourceId': 'source:clip', 'bundle': clip_source['bundle'], 'key': 'synthetic-animation-uuid',
             'kind': 'cc.AnimationClip', 'logicalPath': clip_source['logicalPath'],
             'document': {'instances': [copy.deepcopy(source_clip)], 'root': 0}},
        ],
        'selection': ['fixture:scene', 'source:clip'], 'inputs': [], 'evidenceFiles': [],
    }
    source_path = ir_dir / 'source-manifest.json'
    write_json(source_path, source_manifest)
    ir['sourceManifestPath'] = str(source_path.resolve())
    ir['sourceManifestSha256'] = hashlib.sha256(read(source_path)).hexdigest()
    ir_path = ir_dir / 'ir.json'
    write_json(ir_path, ir)
    finish(ir_dir, dict(schemaVersion=1, diagnostics=[]))
    return ir_path



class AnimationTests(unittest.TestCase):
    def test_real_semantic_intervals_scale_step_opacity_units_and_event_contract(self):
        ir=ir_for(base());a,_=plan_clips(ir,'fixture',unity.PROFILE);b,_=plan_clips(ir,'fixture',cocos.PROFILE)
        self.assertEqual(len(a[0]['tracks']),5)
        x=next(t for t in a[0]['tracks'] if t['property']=='position.x');self.assertEqual(sample(x['keys'],.25),15)
        scale=next(t for t in a[0]['tracks'] if t['property']=='scale.x');self.assertEqual(sample(scale['keys'],.999),1);self.assertEqual(sample(scale['keys'],1),2)
        alpha=next(t for t in a[0]['tracks'] if t['property']=='opacity');self.assertEqual(alpha['keys'][-1]['value'],1)
        self.assertEqual(next(t for t in b[0]['tracks'] if t['property']=='opacity')['keys'][-1]['value'],255)
        self.assertFalse(a[0]['autoPlay']);self.assertEqual(a[0]['events'][0]['binding'],'manual-only');self.assertFalse(a[0]['events'][0]['executed'])

    def test_unknown_easing_loop_keytime_and_property_never_silently_linearized(self):
        doc=base();doc['wrapMode']=22;doc['curveData']['paths']['child']['props']['x'][0]['curve']='sineOut'
        doc['curveData']['paths']['child']['props']['active']=[dict(frame=0,value=True)]
        ir=ir_for(doc);a,g=plan_clips(ir,'fixture',unity.PROFILE)
        self.assertFalse(a[0]['convertible']);self.assertNotIn('position.x',[t['property'] for t in a[0]['tracks']])
        self.assertTrue({'ANIMATION_TIMING_UNSUPPORTED','ANIMATION_INTERPOLATION_UNSUPPORTED','ANIMATION_PROPERTY_UNSUPPORTED'}<={d['code'] for d in ir['diagnostics']})
        for times in [[0,0],[.5,.4],[0,2]]:
            doc=base();doc['curveData']['paths']['child']['props']['x']=[dict(frame=t,value=0) for t in times]
            ir=ir_for(doc);self.assertFalse(any(t['property']=='position.x' for t in ir['animationClips'][0]['tracks']))

    def test_missing_ambiguous_targets_overlapping_channels_and_layout_conflicts(self):
        from monkey.assets.animation import handoff_task
        ownerless=ir_for(base());ownerless['components']=[]
        empty,gaps=plan_clips(ownerless,'fixture',unity.PROFILE)
        self.assertEqual(empty,[]);self.assertEqual(handoff_task(empty,gaps)['sourceRefs'],['source:clip'])
        ir=ir_for(base());ir['nodes'][1]['name']='different';a,g=plan_clips(ir,'fixture',unity.PROFILE);self.assertFalse(a[0]['convertible']);self.assertTrue(g)
        ir=ir_for(base());owner=ir['nodes'][0]['sourceId'].split('#',1)[0];other=f'{owner}#4'
        ir['nodes'][0]['children']=[ir['nodes'][1]['sourceId'],other]
        n=dict(ir['nodes'][1],sourceId=other);ir['nodes'].append(n)
        a,g=plan_clips(ir,'fixture',unity.PROFILE);self.assertFalse(a[0]['convertible'])
        doc=base();doc['curveData']['paths']['child']['props']['position']=[dict(frame=0,value=[0,0,0]),dict(frame=1,value=[1,1,0])]
        a,g=plan_clips(ir_for(doc),'fixture',unity.PROFILE);self.assertTrue(any(d['code']=='ANIMATION_CHANNEL_COLLISION' for d in g))
        ir=ir_for(base());ir['components'].append(dict(sourceId='fixture:scene#2/components/1',type='cc.Layout',node=ir['nodes'][0]['sourceId'],enabled=True))
        a,g=plan_clips(ir,'fixture',unity.PROFILE);self.assertFalse(any(t['property']=='position.x' for t in a[0]['tracks']))

    def test_native_wrong_binding_midpoint_or_callback_rejected(self):
        a,_=plan_clips(ir_for(base()),'fixture',unity.PROFILE);s=a[0]
        result=dict(id=s['id'],path=s['path'],guid='native-guid',duration=1,wrap='normal',eventCount=0,curveCount=5,tracks=[dict(path=t['path'],property=t['nativeProperty'],nativeType=t['nativeType'],times=[k['time'] for k in t['keys']],values=[k['value'] for k in t['keys']],interpolations=[k['interpolation'] for k in t['keys']],probeTimes=[p['time'] for p in t['probes']],probeValues=[p['value'] for p in t['probes']]) for t in s['tracks']])
        self.assertFalse(verify_native(a,[result],{s['path']:'hash'}))
        for change in ['event','binding','probe']:
            wrong=copy.deepcopy(result)
            if change=='event':wrong['eventCount']=1
            elif change=='binding':wrong['tracks'][0]['path']='other'
            else:wrong['tracks'][0]['probeValues'][1]+=10
            self.assertTrue(verify_native(a,[wrong],{s['path']:'hash'}))

    def test_probe_readback_accepts_only_local_float32_curve_quantization(self):
        keys=[dict(time=0.6740740999999999,value=44.28028530506723,interpolation='linear'),
              dict(time=0.6777778,value=65.99885650114278,interpolation='linear')]
        probe=dict(time=0.6759259499999999,value=55.13957090310468)
        track=dict(path='Label',nativeType='UIOpacity',nativeProperty='opacity',keys=keys,probes=[probe])
        spec=dict(id='source:curve@source:owner',path='assets/manual/float32.anim',duration=1.5,convertible=True,
                  wrap='normal',events=[],tracks=[track])
        f32=lambda value:struct.unpack('<f',struct.pack('<f',value))[0]
        q=(probe['time']-f32(keys[0]['time']))/(f32(keys[1]['time'])-f32(keys[0]['time']))
        quantized_probe=f32(f32(keys[0]['value'])+(f32(keys[1]['value'])-f32(keys[0]['value']))*q)
        actual=dict(id=spec['id'],path=spec['path'],guid='native-guid',duration=spec['duration'],wrap='normal',
                    eventCount=0,curveCount=1,tracks=[dict(path='Label',nativeType='UIOpacity',property='opacity',
                    times=[k['time'] for k in keys],values=[k['value'] for k in keys],interpolations=['linear','linear'],
                    probeTimes=[probe['time']],probeValues=[quantized_probe])])
        native={spec['path']:'hash'}
        self.assertEqual(verify_native([spec],[actual],native),[])

        large_error=copy.deepcopy(actual);large_error['tracks'][0]['probeValues'][0]+=0.001
        self.assertTrue(verify_native([spec],[large_error],native))
        wrong_binding=copy.deepcopy(actual);wrong_binding['tracks'][0]['property']='position.x'
        self.assertTrue(verify_native([spec],[wrong_binding],native))

    def test_unity_linear_tangent_float32_evaluation_gets_only_local_probe_ulp_margin(self):
        f32=lambda value:struct.unpack('<f',struct.pack('<f',value))[0]
        def unity_linear_tangent_evaluate(t0,y0,t1,y1,time):
            dt=f32(t1-t0);slope=f32(f32(y1-y0)/dt);q=f32(f32(time-t0)/dt)
            q2=f32(q*q);q3=f32(q2*q)
            h00=f32(f32(2*q3)-f32(3*q2)+1)
            h10=f32(q3-f32(2*q2)+q)
            h01=f32(-2*q3+3*q2)
            h11=f32(q3-q2)
            tangent=f32(slope*dt)
            terms=[f32(h00*y0),f32(h10*tangent),f32(h01*y1),f32(h11*tangent)]
            return f32(f32(f32(terms[0]+terms[1])+terms[2])+terms[3])

        keys=[dict(time=6.142565465487603,value=21.73685487282046,interpolation='linear'),
              dict(time=6.297160435754579,value=283.86945838762233,interpolation='linear')]
        probeTime=6.204840571145944
        probeValue=sample(keys,probeTime)
        track=dict(path='Panel',nativeType='RectTransform',nativeProperty='m_AnchoredPosition.x',keys=keys,
                   probes=[dict(time=probeTime,value=probeValue)])
        spec=dict(id='fixture:clip@fixture:owner',path='Assets/Manual/native-float32.anim',duration=2,
                  convertible=True,wrap='normal',events=[],tracks=[track])
        actualValue=unity_linear_tangent_evaluate(f32(keys[0]['time']),f32(keys[0]['value']),
            f32(keys[1]['time']),f32(keys[1]['value']),f32(probeTime))
        row=dict(id=spec['id'],path=spec['path'],guid='native-guid',duration=spec['duration'],wrap='normal',
            eventCount=0,curveCount=1,tracks=[dict(path='Panel',nativeType='RectTransform',
            property='m_AnchoredPosition.x',times=[key['time'] for key in keys],values=[key['value'] for key in keys],
            interpolations=['linear','linear'],probeTimes=[probeTime],probeValues=[actualValue])])
        native={spec['path']:'hash'}
        self.assertEqual(verify_native([spec],[row],native),[])

        wrongProbe=copy.deepcopy(row);wrongProbe['tracks'][0]['probeValues'][0]+=0.01
        self.assertTrue(verify_native([spec],[wrongProbe],native))
        wrongKey=copy.deepcopy(row);wrongKey['tracks'][0]['values'][1]+=0.001
        self.assertTrue(verify_native([spec],[wrongKey],native))
        wrongBinding=copy.deepcopy(row);wrongBinding['tracks'][0]['property']='position.x'
        self.assertTrue(verify_native([spec],[wrongBinding],native))

    def test_invalid_opacity_vectors_and_future_animation_schema_rejected(self):
        for prop,value in [('opacity',256),('scale',[1,float('nan'),1]),('position',[1])]:
            doc=base();doc['curveData']['paths']['child']['props'][prop]=[dict(frame=0,value=value)]
            ir=ir_for(doc);self.assertTrue(any(d['code'].startswith('ANIMATION_') and 'EVENT' not in d['code'] for d in ir['diagnostics']))
        ir=ir_for(base());ir['animationSchemaVersion']=2
        with self.assertRaises(ParseError):plan_clips(ir,'fixture',unity.PROFILE)
        old=ir_for(base());old.pop('animationSchemaVersion');old.pop('animationClips')
        self.assertEqual(plan_clips(old,'fixture',unity.PROFILE),([],[]))

    def test_minigame_animation_is_inside_declared_native_import_root(self):
        from monkey.layout import standard
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();source_clip=base();ir=ir_for(source_clip)
            ir['sourceNames']={'source:clip':dict(bundle='miniGameRes',logicalPath='Anim/Rope3d/fly')}
            ir_path=write_ir_fixture(root,ir,source_clip)
            unity.plan(ir_path,'minigame',root/'plan');unity.export(root/'plan/plan.json',root/'project')
            paths=load(read(root/'project'/standard.unity('outputPaths')))
            plan=load(read(root/'project'/standard.unity('importPlan')))
            clip=next(a for a in plan['animations'] if a['convertible'])
            self.assertIn('/MiniGames/Rope3d/',clip['path'])
            self.assertTrue(clip['path'].startswith(paths['animationsRoot']+'/'),clip['path'])

    def test_shared_ir_dual_export_no_native_files_or_callback_stubs_and_create_only(self):
        with tempfile.TemporaryDirectory() as temp:
            r=Path(temp).resolve();source_clip=base();ir=ir_for(source_clip);ir_path=write_ir_fixture(r,ir,source_clip)
            for target in [unity,cocos]:
                prefix='unity' if target is unity else 'creator'
                target.plan(ir_path,'fixture',r/(prefix+'-plan'));target.export(r/(prefix+'-plan/plan.json'),r/prefix)
                if target is unity:
                    from monkey.layout import standard
                    helper=(r/prefix/standard.unity('importer')).with_name('NativeButtonAnimations.cs')
                    self.assertEqual(helper.read_bytes(),Path(unity.__file__).with_name('UnityButtonAnimations.cs').read_bytes())
                    self.assertTrue(Path(str(helper)+'.meta').is_file())
                module=load(read(r/prefix/'Analysis/Tasks/animation-module.json'));self.assertFalse(module['callbacksGenerated']);self.assertEqual(len(module['clips']),1)
                self.assertFalse(any((r/prefix).rglob('*.anim')))
                task=next(t for t in load(read(r/prefix/'Analysis/Tasks/handoff.json'))['tasks'] if t['taskId']=='finite-ui-animation');self.assertTrue(task['gaps'])
                self.assertEqual(target.verify(r/prefix,r/(prefix+'-static'))['staticValidation'],'pass')
                with self.assertRaises(ParseError):target.export(r/(prefix+'-plan/plan.json'),r/prefix)
                (r/(prefix+'-plan/plan.json')).write_text('{}')
                with self.assertRaises(ParseError):target.export(r/(prefix+'-plan/plan.json'),r/(prefix+'-tampered'))
