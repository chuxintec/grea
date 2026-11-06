"""Finite conversion-time AnimationClip subset. No source callbacks or runtime evaluation."""
import math
import struct
import sys
from ..io import diagnostic
from ..sources.compiled import fail, ParseError

SCHEMA=1

# Values fixed before reading per-clip error results. Source-unit tolerances are
# intentionally strict for transform scale/opacity and sub-pixel for position.
CHANNEL_TOLERANCE={'position':0.25,'scale':0.001,'opacity':0.25}
MAX_APPROXIMATION_KEYS=256
APPROXIMATION_PROBE_INTERVALS=2048
SUPPORTED_EASING={'sineIn','sineOut','sineInOut'}


def _source_progress(curve, time):
    """Cocos Creator 2.4.15 easing/Bezier semantics for normalized time."""
    if curve=='sineIn':return 1-math.cos(time*math.pi/2)
    if curve=='sineOut':return math.sin(time*math.pi/2)
    if curve=='sineInOut':return 0.5*(1-math.cos(math.pi*time))
    if isinstance(curve,list) and len(curve)==4:
        x1,y1,x2,y2=curve
        # Restrict the cubic x control polygon to a monotonic interval so time
        # has one inverse. Cocos accepts broader Cardano roots; those are held.
        if not (0<=x1<=x2<=1):raise ValueError('Bezier time controls must satisfy 0 <= x1 <= x2 <= 1')
        lo,hi=0.0,1.0
        for _ in range(56):
            u=(lo+hi)/2
            inv=1-u
            x=3*inv*inv*u*x1+3*inv*u*u*x2+u*u*u
            if x<time:lo=u
            else:hi=u
        u=(lo+hi)/2
        inv=1-u
        return 3*inv*inv*u*y1+3*inv*u*u*y2+u*u*u
    raise ValueError('Unsupported easing/Bezier curve')


def _segment_source_value(curve,a,b,u):
    return a+(b-a)*_source_progress(curve,u)


def _linear_value(a,b,u):return a+(b-a)*u


def _adaptive_segment(curve,a,b,tolerance):
    """Linearize a bounded segment; return interior samples and measured error."""
    if curve in ('sineIn','sineOut','sineInOut'):
        # For sine easing, |f''| <= pi^2/2. The interpolation-error bound
        # |delta|*M*h^2/8 is conservative for each normalized subinterval.
        second_bound={'sineIn':math.pi**2/4,'sineOut':math.pi**2/4,'sineInOut':math.pi**2/2}[curve]
        steps=max(1,math.ceil(math.sqrt(abs(b-a)*second_bound/(8*tolerance))))
    else:
        steps=1
    while True:
        if steps>MAX_APPROXIMATION_KEYS:raise ValueError('Approximation key budget exceeded')
        worst=0.0
        for i in range(steps):
            u0=i/steps;u1=(i+1)/steps
            y0=_segment_source_value(curve,a,b,u0);y1=_segment_source_value(curve,a,b,u1)
            for q in (0.25,0.5,0.75):
                u=u0+(u1-u0)*q
                worst=max(worst,abs(_segment_source_value(curve,a,b,u)-_linear_value(y0,y1,q)))
        if worst>tolerance:
            steps*=2;continue
        # Independent dense readback guards the adaptive criterion and records
        # a repeatable error bound for the generated native linear keys.
        max_error=0.0
        for j in range(APPROXIMATION_PROBE_INTERVALS+1):
            u=j/APPROXIMATION_PROBE_INTERVALS
            scaled=u*steps;idx=min(steps-1,int(scaled));local=scaled-idx
            y0=_segment_source_value(curve,a,b,idx/steps)
            y1=_segment_source_value(curve,a,b,(idx+1)/steps)
            max_error=max(max_error,abs(_segment_source_value(curve,a,b,u)-_linear_value(y0,y1,local)))
        if max_error<=tolerance+1e-12:break
        steps*=2
    interior=[dict(u=i/steps,value=_segment_source_value(curve,a,b,i/steps)) for i in range(1,steps)]
    return interior,max_error,steps


def _expand_scalar_keys(frames,values,curve_modes,duration,prop,tloc,source_property):
    tolerance=CHANNEL_TOLERANCE['position' if prop.startswith('position.') else 'scale' if prop.startswith('scale.') else 'opacity']
    result=[];max_error=0.0;generated=0;approximated=[]
    for i,(frame,value) in enumerate(zip(frames,values)):
        result.append(dict(time=frame,value=value,interpolation='linear',sourceLocation=f'{tloc}/{i}'))
        if i+1>=len(frames):continue
        mode=curve_modes[i];next_time=frames[i+1];next_value=values[i+1]
        if mode in (None,'linear'):
            continue
        if mode=='constant':
            result[-1]['interpolation']='step';continue
        if source_property in ('position','scale','opacity'):
            pass
        else:
            raise ValueError('Easing approximation is restricted to position, scale and opacity channels')
        interior,error,steps=_adaptive_segment(mode,value,next_value,tolerance)
        span=next_time-frame
        for point in interior:
            result.append(dict(time=frame+span*point['u'],value=point['value'],interpolation='linear',sourceLocation=f'{tloc}/{i}',generated=True))
        max_error=max(max_error,error);generated+=len(interior)
        approximated.append(dict(segment=i,mode=mode,keys=steps+1,maxAbsoluteProbeError=error))
    if not result:raise ValueError('No scalar keyframes')
    if result[-1]['time']<duration:result.append(dict(time=duration,value=result[-1]['value'],interpolation='linear',sourceLocation=tloc,generated=True))
    if len(result)>MAX_APPROXIMATION_KEYS+len(frames)+1:raise ValueError('Per-channel approximation key budget exceeded')
    return result,dict(method='adaptive-source-curve-to-linear',tolerance=tolerance,maxAbsoluteProbeError=max_error,
                       probeIntervals=APPROXIMATION_PROBE_INTERVALS,generatedKeyCount=generated,segments=approximated)


def finite(value,location):
    if type(value) not in (int,float) or not math.isfinite(value):fail('ANIMATION_INVALID_NUMBER',location,'Expected finite numeric value')
    return value


def normalize_clip(value,sid,location):
    gaps=[];tracks=[];events=[]
    def gap(code,loc,msg):gaps.append(diagnostic(code,loc,msg,sid))
    duration=finite(value.get('_duration',0),location+'/_duration');sample=finite(value.get('sample',60),location+'/sample')
    speed=finite(value.get('speed',1),location+'/speed');wrap=value.get('wrapMode',1)
    timing=0<duration<=600 and 0<sample<=240 and speed==1 and type(wrap) is int and wrap in (1,2)
    if not timing:gap('ANIMATION_TIMING_UNSUPPORTED',location,'Only positive duration <=600s, sample <=240, speed=1 and explicit/default Normal or Loop')
    known={'__type__','_name','_objFlags','_duration','sample','speed','wrapMode','curveData','events','_native'}
    for key in value.keys()-known:gap('ANIMATION_FIELD_UNSUPPORTED',location+'/'+key,'Unknown clip field')
    curve=value.get('curveData',{})
    if not isinstance(curve,dict):fail('ANIMATION_INVALID_CURVES',location,'Expected curveData object')
    sections=[('',curve,location+'/curveData')]
    paths=curve.get('paths',{})
    if not isinstance(paths,dict) or len(paths)>128:fail('ANIMATION_TRACK_BUDGET',location,'Invalid or excessive paths')
    sections += [(path,body,location+'/curveData/paths/'+path) for path,body in paths.items()]
    for path,body,loc in sections:
        if not isinstance(path,str) or (path and any(p in ('','..','.') for p in path.split('/'))) or not isinstance(body,dict):
            gap('ANIMATION_PATH_UNSUPPORTED',loc,'Expected canonical node path');continue
        for key in body.keys()-({'props','comps','paths'} if path=='' else {'props','comps'}):
            gap('ANIMATION_CURVE_GROUP_UNSUPPORTED',loc+'/'+key,'Unknown curve group')
        if body.get('comps'):gap('ANIMATION_COMPONENT_CURVES_UNSUPPORTED',loc+'/comps','Component curves need a separate reviewed mapping')
        props=body.get('props',{})
        if not isinstance(props,dict):fail('ANIMATION_INVALID_CURVES',loc,'Expected props object')
        for prop,frames in props.items():
            tloc=loc+'/props/'+prop
            if not isinstance(frames,list) or len(frames)>8192:fail('ANIMATION_KEY_BUDGET',tloc,'Invalid/excessive key list')
            if not frames:continue
            channels={'x':['position.x'],'y':['position.y'],'z':['position.z'],
                      'scaleX':['scale.x'],'scaleY':['scale.y'],'scaleZ':['scale.z'],'opacity':['opacity']}.get(prop)
            if prop not in ('position','scale') and channels is None:
                gap('ANIMATION_PROPERTY_UNSUPPORTED',tloc,'Unsupported property '+prop);continue
            try:
                keys=[];dimensions=None;last=-1
                for i,f in enumerate(frames):
                    kloc=tloc+'/'+str(i)
                    if not isinstance(f,dict):fail('ANIMATION_INVALID_KEY',kloc,'Expected frame object')
                    unknown=f.keys()-{'frame','value','curve'}
                    if unknown:fail('ANIMATION_KEY_FIELD_UNSUPPORTED',kloc,'Unknown key fields: '+','.join(sorted(unknown)))
                    time=finite(f.get('frame'),kloc+'/frame')
                    if time<=last or time<0 or time>duration+1e-9:fail('ANIMATION_TIME_ORDER',kloc,'Times must strictly increase within duration')
                    if i==0 and time!=0:fail('ANIMATION_START_UNSUPPORTED',kloc,'First subset requires key at time zero')
                    last=time;mode=f.get('curve')
                    if mode is not None and not (isinstance(mode,str) or isinstance(mode,list)):
                        fail('ANIMATION_INTERPOLATION_UNSUPPORTED',kloc+'/curve','Expected a Cocos easing name or four-control Bezier array')
                    if isinstance(mode,list) and (len(mode)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in mode)):
                        fail('ANIMATION_BEZIER_INVALID',kloc+'/curve','Expected four finite [x1,y1,x2,y2] control values')
                    if isinstance(mode,list) and mode[0]==mode[1] and mode[2]==mode[3]:mode='linear'
                    if isinstance(mode,str) and mode not in ('linear','constant') and mode not in SUPPORTED_EASING:
                        fail('ANIMATION_INTERPOLATION_UNSUPPORTED',kloc+'/curve','Unsupported Cocos easing '+mode)
                    raw=f.get('value')
                    if prop in ('position','scale'):
                        if isinstance(raw,dict) and raw.get('__value_type__') in (0,1):raw=raw.get('values')
                        if not isinstance(raw,list) or len(raw) not in (2,3):fail('ANIMATION_VECTOR_UNSUPPORTED',kloc,'Expected 2D/3D vector')
                        vals=[finite(v,kloc+'/value') for v in raw]
                    else:vals=[finite(raw,kloc+'/value')]
                    if dimensions is not None and dimensions!=len(vals):fail('ANIMATION_VECTOR_UNSUPPORTED',kloc,'Vector dimensions changed')
                    dimensions=len(vals)
                    if prop=='opacity' and not 0<=vals[0]<=255:fail('ANIMATION_OPACITY_BOUNDS',kloc,'Opacity must be 0..255')
                    keys.append(dict(time=time,values=vals,curve=mode,sourceLocation=kloc))
                if prop not in ('position','scale','opacity') and any(k['curve'] not in (None,'linear','constant') for k in keys[:-1]):
                    fail('ANIMATION_INTERPOLATION_UNSUPPORTED',tloc,'Nonlinear interpolation is limited to canonical position, scale and opacity channels')
                names=[prop+'.'+axis for axis in 'xyz'[:dimensions]] if prop in ('position','scale') else channels
                for axis,name in enumerate(names):
                    try:
                        scalar,approximation=_expand_scalar_keys([k['time'] for k in keys],[k['values'][axis] for k in keys],[k['curve'] for k in keys],duration,name,tloc,prop)
                    except ValueError as e:
                        code='ANIMATION_APPROXIMATION_BUDGET' if 'budget' in str(e).lower() else 'ANIMATION_APPROXIMATION_UNVERIFIED'
                        gap(code,tloc,str(e));continue
                    track=dict(sourceId=sid+'@'+path+'/'+name,nodePath=path,property=name,keys=scalar,sourceLocation=tloc)
                    if approximation['segments']:track['curveApproximation']=approximation
                    tracks.append(track)
            except ParseError as e:gap(e.code,e.location,e.message)
    if len(tracks)>256:fail('ANIMATION_TRACK_BUDGET',location,'Too many scalar channels')
    raw_events=value.get('events',[])
    if not isinstance(raw_events,list) or len(raw_events)>1024:fail('ANIMATION_EVENT_BUDGET',location,'Invalid/excessive events')
    for i,e in enumerate(raw_events):
        eloc=location+'/events/'+str(i)
        if not isinstance(e,dict) or not isinstance(e.get('func'),str) or not isinstance(e.get('params',[]),list):
            gap('ANIMATION_EVENT_UNSUPPORTED',eloc,'Expected frame, function name and JSON params');continue
        time=finite(e.get('frame'),eloc+'/frame')
        if time<0 or time>duration:gap('ANIMATION_EVENT_TIME_INVALID',eloc,'Event outside duration');continue
        events.append(dict(time=time,function=e['func'],parameters=e.get('params',[]),sourceLocation=eloc,binding='manual-only',executed=False))
        gap('ANIMATION_EVENT_BINDING_REQUIRED',eloc,'Event is a source contract only; no native callback generated')
    return dict(sourceId=sid,name=value.get('_name','Animation'),duration=duration,sample=sample,wrap='loop' if wrap==2 else 'normal',
                timingSupported=timing,tracks=tracks,events=events,sourceLocation=location,partial=bool(gaps)),gaps


def sample(keys,time):
    """Offline QA reference for finite scalar tracks; never emitted to a Player."""
    if time<=keys[0]['time']:return keys[0]['value']
    for a,b in zip(keys,keys[1:]):
        if time<b['time']:
            return a['value'] if a['interpolation']=='step' else a['value']+(b['value']-a['value'])*(time-a['time'])/(b['time']-a['time'])
    return keys[-1]['value']


def _float32_value(value):
    """Return the exact value stored by Creator's Float32Array curve data."""
    try:return struct.unpack('<f',struct.pack('<f',value))[0]
    except (OverflowError,struct.error):return math.inf if value>0 else -math.inf


def _float32_ulp(value):
    """Return the positive Float32 spacing at value's magnitude."""
    rounded=abs(_float32_value(value))
    if not math.isfinite(rounded):return 0.0
    bits=struct.unpack('<I',struct.pack('<f',rounded))[0]
    if bits>=0x7f7fffff:return 0.0
    following=struct.unpack('<f',struct.pack('<I',bits+1))[0]
    return following-rounded


def _native_probe_float32_bound(track,probe):
    """Bound probe drift from Float32 storage and native curve evaluation.

    Creator stores RealCurve key times and values in Float32Arrays. Probe input
    and evaluated values can also cross a Float32 boundary in the native curve
    path. Re-sampling the quantized local segment for both double and Float32
    probe/output forms bounds endpoint value rounding, local-slope time error,
    and output rounding without a global epsilon. Unity's linear tangent mode
    evaluates a tangent-defined curve; its native Float32 Hermite arithmetic
    adds a few local ULPs beyond the quantized linear reference. The four-ULP
    allowance is measured at this probe's adjacent key/value scale, not clip
    or channel scale. This applies only to probe values; native key arrays,
    bindings and interpolation modes remain independently checked.
    """
    keys=track.get('keys',[]);time=probe.get('time')
    if len(keys)<2 or type(time) not in (int,float) or not math.isfinite(time):return 0.0
    rounded=[]
    for key in keys:
        kt=key.get('time');kv=key.get('value')
        if type(kt) not in (int,float) or type(kv) not in (int,float):return 0.0
        rt,rv=_float32_value(kt),_float32_value(kv)
        if not math.isfinite(rt) or not math.isfinite(rv):return 0.0
        rounded.append(dict(time=rt,value=rv,interpolation=key.get('interpolation')))
    if any(a['time']>=b['time'] for a,b in zip(rounded,rounded[1:])):return 0.0
    expected=probe.get('value')
    if type(expected) not in (int,float) or not math.isfinite(expected):return 0.0
    candidates=[]
    for query_time in {time,_float32_value(time)}:
        if not math.isfinite(query_time):return 0.0
        value=sample(rounded,query_time)
        if not math.isfinite(value):return 0.0
        candidates.extend((value,_float32_value(value)))
    candidates=[value for value in candidates if math.isfinite(value)]
    if not candidates:return 0.0
    # Double arithmetic contributes only a tiny relative allowance; native
    # interpolation arithmetic is bounded separately at local Float32 scale.
    arithmetic=16*sys.float_info.epsilon*max(1.0,abs(expected),*(abs(x) for x in candidates))
    query=_float32_value(time)
    nearby=[abs(expected),*(abs(value) for value in candidates)]
    for left,right in zip(rounded,rounded[1:]):
        if left['time']<=query<=right['time']:
            nearby.extend((abs(left['value']),abs(right['value'])))
            break
    local_ulp=max((_float32_ulp(value) for value in nearby),default=0.0)
    return max(abs(value-expected) for value in candidates)+arithmetic+4*local_ulp


def plan_clips(ir,namespace,profile,selection=None,naming=None):
    clips=ir.get('animationClips',[])
    if ('animationSchemaVersion' in ir or clips) and ir.get('animationSchemaVersion')!=SCHEMA:fail('UNSUPPORTED_ANIMATION_IR','$','Expected animation schema 1')
    known={c['sourceId'] for c in clips};selection=set(selection or known)
    if selection-known:fail('UNKNOWN_ANIMATION_SELECTION','$',str(sorted(selection-known)))
    nodes={n['sourceId']:n for n in ir['nodes']};out=[];gaps=[]
    def owner_name(owner,root):
        # A clip shared by many owners is qualified by owner prefab and node before any hash (PROJECT-SPEC 5.4).
        page=(ir.get('sourceNames',{}).get(owner['node'].split('#',1)[0],{}).get('logicalPath') or '').rsplit('/',1)[-1]
        return (page+'_' if page else '')+str(root['name'])
    for clip in clips:
        if clip['sourceId'] not in selection:continue
        owners=[c for c in ir['components'] if c['type']=='cc.Animation' and clip['sourceId'] in c.get('clips',[]) and c.get('node') in nodes]
        if not owners:gaps.append(diagnostic('ANIMATION_OWNER_MISSING',clip['sourceLocation'],'No source Animation component binding',clip['sourceId']))
        for owner in owners:
            root=nodes[owner['node']];tracks=[]
            for track in clip['tracks']:
                current=root;valid=True
                for part in track['nodePath'].split('/') if track['nodePath'] else []:
                    matches=[nodes[k] for k in current['children'] if nodes[k]['name']==part]
                    if len(matches)!=1:valid=False;break
                    current=matches[0]
                if not valid:
                    gaps.append(diagnostic('ANIMATION_TARGET_MISSING_OR_AMBIGUOUS',track['sourceLocation'],'Target path does not resolve uniquely',clip['sourceId']));continue
                if any('/' in n['name'] for n in [root,current]):
                    gaps.append(diagnostic('ANIMATION_TARGET_PATH_UNSUPPORTED',track['sourceLocation'],'Node names contain hierarchy separator',clip['sourceId']));continue
                if track['property'].startswith('position.') and any(c.get('enabled') and ((c['type']=='cc.Widget' and c['node']==current['sourceId'] and c.get('flags')) or (c['type']=='cc.Layout' and c['node']==current['parent'])) for c in ir['components']):
                    gaps.append(diagnostic('ANIMATION_LAYOUT_CONFLICT',track['sourceLocation'],'Layout/Widget owns animated position',clip['sourceId']));continue
                t=dict(track,node=current['sourceId'],path=track['nodePath'])
                if profile.startswith('unity-'):
                    prop=track['property'];t['valueScale']=1/255 if prop=='opacity' else 1
                    t['nativeType']='CanvasGroup' if prop=='opacity' else ('RectTransform' if prop.startswith('position.') else 'Transform')
                    t['nativeProperty']={'position.x':'m_AnchoredPosition.x','position.y':'m_AnchoredPosition.y','position.z':'m_LocalPosition.z','opacity':'m_Alpha'}.get(prop,'m_LocalScale.'+prop[-1])
                else:t.update(valueScale=1,nativeType='UIOpacity' if track['property']=='opacity' else 'Node',nativeProperty=track['property'])
                t['keys']=[dict(k,value=k['value']*t['valueScale']) for k in track['keys']]
                times=sorted(set([k['time'] for k in t['keys']]+[(a['time']+b['time'])/2 for a,b in zip(t['keys'],t['keys'][1:])]))
                t['probes']=[dict(time=time,value=sample(t['keys'],time)) for time in times];tracks.append(t)
            counts={}
            for t in tracks:counts[(t['node'],t['property'])]=counts.get((t['node'],t['property']),0)+1
            if any(n>1 for n in counts.values()):
                gaps.append(diagnostic('ANIMATION_CHANNEL_COLLISION',clip['sourceLocation'],'Overlapping source properties target the same native channel',clip['sourceId']))
                tracks=[t for t in tracks if counts[(t['node'],t['property'])]==1]
            out.append(dict(id=clip['sourceId']+'@'+owner['sourceId'],name=clip['name'],root=owner['node'],duration=clip['duration'],sample=clip['sample'],
                wrap=clip['wrap'],tracks=tracks,convertible=bool(tracks) and clip['timingSupported'],partial=clip['partial'] or len(tracks)!=len(clip['tracks']),
                events=clip['events'],path=None,autoPlay=False,owner=owner_name(owner,root)))
    if naming is None:
        from ..layout import LayoutPlanner
        naming=LayoutPlanner('unity' if profile.startswith('unity-') else 'creator',ir.get('sourceNames'))
    def meta(item):
        source=item['id'].split('@',1)[0]
        value=dict(ir.get('sourceNames',{}).get(source,{}));value['sourceId']=source
        if not value.get('sourceName'):value['sourceName']=item['name']
        return value
    # One clip per (clip, owner); a shared clip name is qualified by its owner node before any hash.
    naming.reserve([(item['id'],'animation','.anim','',meta(item),item.pop('owner')) for item in out])
    for item in out:item['path']=naming.path(item['id'],'animation','.anim',metadata=meta(item))
    return out,gaps


def module_report(animations):
    approximations=[t.get('curveApproximation',{}) for a in animations for t in a.get('tracks',[]) if t.get('curveApproximation')]
    return dict(schemaVersion=SCHEMA,module='finite-ui-animation',nativeValidation='not_run',callbacksGenerated=False,
        approximationPolicy=dict(channels=CHANNEL_TOLERANCE,maxKeysPerSegment=MAX_APPROXIMATION_KEYS,
            probeIntervals=APPROXIMATION_PROBE_INTERVALS,supportedEasing=sorted(SUPPORTED_EASING),
            bezierControlOrder='[x1,y1,x2,y2]',bezierTimeControls='0<=x1<=x2<=1'),
        approximationSummary=dict(tracks=len(approximations),generatedKeys=sum(a.get('generatedKeyCount',0) for a in approximations),
            maximumObservedError=max([a.get('maxAbsoluteProbeError',0) for a in approximations] or [0])),
        clips=animations,allowedPaths=['Assets/Manual/','assets/manual/'],requirements=['Bind playback explicitly in native code','Review unsupported source channels and Bezier time controls','Wire events only after business implementation'])


def handoff_task(animations,diagnostics):
    return dict(taskId='finite-ui-animation',module='finite-ui-animation',moduleName='Finite UI animation',rootCause='animation-module',
        sourceRefs=([a['id'] for a in animations] or sorted({d['sourceId'] for d in diagnostics if d['code'].startswith('ANIMATION_') and d.get('sourceId')})),generatedTargets=[a['path'] for a in animations],allowedPaths=['Assets/Manual/','assets/manual/'],
        gaps=[d for d in diagnostics if d['code'].startswith('ANIMATION_')],verificationScope=['Native clip re-load, bindings, keys and midpoint probes','Unsupported channels and explicit playback/event wiring'])


def verify_native(specs,actual,native_files):
    gaps=[];actual=actual or [];by_id={a['id']:a for a in actual};expected={a['id']:a for a in specs if a['convertible']}
    def near(a,b):return type(a) in (int,float) and math.isfinite(a) and abs(a-b)<1e-4
    def numbers_equal(a,b):return isinstance(a,list) and len(a)==len(b) and all(near(x,y) for x,y in zip(a,b))
    if set(by_id)!=set(expected) or len(by_id)!=len(actual):
        gaps.append(diagnostic('ANIMATION_READBACK_MISMATCH','animations','Native clip identity set differs'))
    for sid,spec in expected.items():
        a=by_id.get(sid,{})
        good=a.get('path')==spec['path'] and spec['path'] in native_files and bool(a.get('guid') or a.get('uuid'))
        good=good and near(a.get('duration'),spec['duration']) and a.get('wrap')==spec['wrap'] and a.get('eventCount')==0 and a.get('curveCount')==len(spec['tracks'])
        tracks={(t['path'],t['nativeType'],t['nativeProperty']):t for t in spec['tracks']}
        observed={(t.get('path'),t.get('nativeType'),t.get('property')):t for t in a.get('tracks',[])}
        good=good and set(tracks)==set(observed) and len(observed)==len(a.get('tracks',[]))
        for key,t in tracks.items():
            n=observed.get(key,{})
            good=good and numbers_equal(n.get('times'),[k['time'] for k in t['keys']]) and numbers_equal(n.get('values'),[k['value'] for k in t['keys']])
            good=good and n.get('interpolations')==[k['interpolation'] for k in t['keys']]
            good=good and numbers_equal(n.get('probeTimes'),[p['time'] for p in t['probes']])
            actual_probes=n.get('probeValues')
            expected_probes=t['probes']
            good=good and isinstance(actual_probes,list) and len(actual_probes)==len(expected_probes) and all(
                type(actual) in (int,float) and math.isfinite(actual)
                and abs(actual-probe['value'])<=_native_probe_float32_bound(t,probe)
                for probe,actual in zip(expected_probes,actual_probes))
        if not good:gaps.append(diagnostic('ANIMATION_READBACK_MISMATCH',spec['path'],'Saved binding/time/value/interpolation/probes/events differ',sid))
    return gaps
