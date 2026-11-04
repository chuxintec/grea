"""Prepare a minimal, frozen resource-only Creator probe from an owned candidate."""
from pathlib import Path
import re

from .io import safe,inside,read,load,sha,stage_manifest,write_json,new_output,finish
from .sources.containers import fingerprint
from .sources.compiled import fail
from .layout.standard import find_analysis
from .assets.spine import atlas_pages

PROFILE='creator-spine-3.8-v1'


def prepare(candidate,expected_manifest,source_ids,output):
    root=safe(candidate)
    if fingerprint(root/'manifest.json')!=expected_manifest:fail('RESOURCE_PROBE_IDENTITY',str(root),'Expected exact frozen manifest')
    manifest=stage_manifest(root)
    if manifest.get('targetProfile')!='cocos-3.8.8':fail('RESOURCE_PROBE_PROFILE',str(root),'Only Creator 3.8.8 Spine 3.8 is covered')
    if not 1<=len(source_ids)<=16 or len(set(source_ids))!=len(source_ids):fail('RESOURCE_PROBE_SELECTION','spine','Select 1..16 distinct exact source IDs')
    owned={f['path']:f for f in manifest['files']};report_path=find_analysis(root,'spine-closures.json')
    def selected_bytes(relative):
        path=inside(root,relative);raw=read(path,max_bytes=32*1024*1024);row=owned.get(relative)
        if row is None or sha(raw)!=row['sha256'] or len(raw)!=row['bytes']:fail('RESOURCE_PROBE_SOURCE_CHANGED',relative,'Selected frozen bytes differ')
        return raw
    report_raw=selected_bytes(report_path.relative_to(root).as_posix());report=load(report_raw)
    closures={r['sourceId']:r for r in report['skeletons']};probes=[];payloads={};total=0
    for sid in source_ids:
        row=closures.get(sid,{})
        if row.get('status')!='closure_recovered' or row.get('runtime')!='creator-builtin-3.8' or not re.fullmatch(r'3\.8\.\d+',str(row.get('skeletonVersion'))):
            fail('RESOURCE_PROBE_SPINE_VERSION',sid,'A recovered exact standard 3.8 closure is required; no version rewriting')
        skeleton=row['skeletonPath'];atlas=row['atlasPath'];members={f['path']:f for f in row['files']}
        names=atlas_pages(selected_bytes(atlas).decode('utf-8'));pages=[]
        for name in names:
            path=(Path(atlas).parent/name).as_posix()
            if path not in members:fail('RESOURCE_PROBE_PAGE_MISSING',path,'Exact declared atlas page required')
            page_meta=load(selected_bytes(path+'.meta'));pages.append(dict(path=path,name=name,imageUuid=page_meta['uuid']))
        skel_meta=load(selected_bytes(skeleton+'.meta'));atlas_meta=load(selected_bytes(atlas+'.meta'))
        if skel_meta.get('userData',{}).get('atlasUuid')!=atlas_meta['uuid']:fail('RESOURCE_PROBE_ATLAS_BINDING',sid,'Exact original atlas UUID required')
        for relative,member in members.items():
            if not relative.startswith('assets/resources/Spine/'):fail('RESOURCE_PROBE_PATH',relative,'Spine closure must remain in the declared content root')
            for path in (relative,relative+'.meta'):
                raw=selected_bytes(path)
                if path==relative and sha(raw)!=member['sha256']:fail('RESOURCE_PROBE_CLOSURE_CHANGED',relative,'Closure receipt differs from candidate ownership')
                payloads[path]=raw
        probes.append(dict(sourceId=sid,skeletonPath=skeleton,skeletonUuid=skel_meta['uuid'],atlasPath=atlas,
                           version=row['skeletonVersion'],sourceSkeletonSha256=members[skeleton]['sha256'],pages=pages,
                           nodeName='SpineProbe'+sha(sid.encode())[:12],files=row['files']))
        total=sum(len(b)for b in payloads.values())
        if total>128*1024*1024:fail('RESOURCE_PROBE_BYTE_BUDGET',sid,'Selected probe closure exceeds 128 MiB')
    out=new_output(output,[root]);plan_root=out/'Plan';plan_root.mkdir()
    resource_probes=dict(profile=PROFILE,spines=probes)
    plan=dict(schemaVersion=1,targetProfile='cocos-3.8.8',namespace='resource-probe-'+expected_manifest[:12],
              sourceManifestSha256=manifest.get('sourceManifestSha256',expected_manifest),sourceRoots={},sourceLocations={},
              designSize=[512,512],assets=[],copies=[],animations=[],nodes=[],components=[],sourcePrefabs=[],prefabInstances=[],bindings={},diagnostics=[],
              scopeMode='resource-probe-only',naming={},resourceProbes=resource_probes)
    write_json(plan_root/'plan.json',plan);finish(plan_root,plan)
    from .targets import cocos
    project=out/'CocosProject';candidate_report=cocos.export(plan_root/'plan.json',project)
    for relative,raw in payloads.items():
        dest=inside(project,relative);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    proof=dict(schemaVersion=1,profile=PROFILE,sourceCandidateManifestSha256=expected_manifest,closureReportSha256=sha(report_raw),
               selectedSourceIds=source_ids,selectedFiles=len(payloads),selectedBytes=total,originalSourceCodeExecuted=False,
               sourceHierarchyIncluded=False,gameplayIncluded=False)
    write_json(project/'Analysis/Evidence/resource-probe-input.json',proof)
    candidate_report['resourceProbes']=resource_probes;finish(project,candidate_report)
    receipt=dict(proof,candidate=str(project),candidateManifestSha256=fingerprint(project/'manifest.json'),editorValidation='not_run')
    write_json(out/'resource-probe.json',receipt)
    return dict(status='prepared',candidate=str(project),candidateManifestSha256=receipt['candidateManifestSha256'],report=str(out/'resource-probe.json'))


def verify(plan,readback):
    spec=plan.get('resourceProbes')
    if not spec:return True
    proof=readback.get('resourceProbes')or{}
    if spec.get('profile')!=PROFILE or proof.get('profile')!=PROFILE:return False
    rows=proof.get('spines',[]);actual={r.get('sourceId'):r for r in rows};expected={r['sourceId']:r for r in spec.get('spines',[])}
    if len(actual)!=len(rows) or set(actual)!=set(expected):return False
    for sid,s in expected.items():
        r=actual[sid];textures=r.get('textures',[])
        if (r.get('skeletonUuid')!=s['skeletonUuid'] or r.get('sourceSkeletonSha256')!=s['sourceSkeletonSha256'] or
                r.get('version')!=s['version'] or r.get('savedReferenceVerified')is not True or r.get('nativeStateAdvanced')is not True or r.get('poseChanged')is not True or
                not isinstance(r.get('animation'),str) or not r['animation'] or type(r.get('bones'))is not int or r['bones']<1 or
                len(textures)!=len(s['pages'])):return False
        for wanted,got in zip(s['pages'],textures):
            uid=got.get('textureUuid')
            if (got.get('name')!=wanted['name'] or got.get('imageUuid')!=wanted['imageUuid'] or not isinstance(uid,str) or
                    not uid.startswith(wanted['imageUuid']+'@') or got.get('nativeUuid')!=uid):return False
        before,after=r.get('trackTimeBefore'),r.get('trackTimeAfter')
        if type(before)not in (float,int) or type(after)not in (float,int) or not 0<=before<after<=1:return False
    return True


def verify_static_resource_probe(plan, readback, execution_result, *, expected_import_plan_sha256: str,
                                 expected_candidate_manifest_sha256: str) -> dict:
    """Verify resource identity and saved references without claiming animation motion.

    This deliberately does not call ``verify``: a static resource may load and
    save correctly while the sampled animation has no observed bone motion.
    Only the known NO_OBSERVED_BONE_MOTION diagnostic is tolerated; dynamic pose
    behavior remains partial in the returned proof.
    """
    spec = plan.get("resourceProbes") or {}
    expected = spec.get("spines", [])
    actual_rows = (readback.get("resourceProbes") or {}).get("spines", [])
    if spec.get("profile") != PROFILE or not isinstance(expected, list) or not expected:
        raise ValueError("static resource probe profile or expected Spine rows are missing")
    if readback.get("creatorVersion") != "3.8.8" or readback.get("manifestSha256") != expected_candidate_manifest_sha256:
        raise ValueError("static resource probe readback candidate identity differs")
    progress = execution_result.get("nativeProgress") or {}
    if (execution_result.get("sourceManifestSha256") != expected_candidate_manifest_sha256
            or execution_result.get("processStarted") is not True
            or execution_result.get("processExited") is not True
            or execution_result.get("stopReason") != "native_completed"
            or execution_result.get("importPlanSha256") != expected_import_plan_sha256
            or progress.get("planSha256") != expected_import_plan_sha256
            or progress.get("status") != "completed" or progress.get("phase") != "complete"
            or progress.get("processed") != progress.get("total") or progress.get("total") != 1):
        raise ValueError("static resource probe native import did not complete for the pinned plan")
    actual = {row.get("sourceId"): row for row in actual_rows if isinstance(row, dict)}
    wanted = {row.get("sourceId"): row for row in expected if isinstance(row, dict)}
    if len(actual) != len(actual_rows) or len(wanted) != len(expected) or set(actual) != set(wanted):
        raise ValueError("static resource probe source ID denominator differs")
    proof_rows = []
    for source_id, source in wanted.items():
        row = actual[source_id]
        textures = row.get("textures", [])
        if (row.get("skeletonUuid") != source.get("skeletonUuid")
                or row.get("sourceSkeletonSha256") != source.get("sourceSkeletonSha256")
                or row.get("version") != source.get("version")
                or row.get("savedReferenceVerified") is not True
                or row.get("nativeStateAdvanced") is not True
                or type(row.get("bones")) is not int or row["bones"] < 1
                or type(row.get("slots")) is not int or row["slots"] < 0
                or len(textures) != len(source.get("pages", []))):
            raise ValueError(f"static resource identity or saved native reference mismatch: {source_id}")
        for wanted_page, got in zip(source.get("pages", []), textures):
            native_uuid = got.get("nativeUuid")
            if (got.get("name") != wanted_page.get("name")
                    or got.get("imageUuid") != wanted_page.get("imageUuid")
                    or not isinstance(native_uuid, str)
                    or not native_uuid.startswith(str(wanted_page.get("imageUuid")) + "@")
                    or got.get("textureUuid") != native_uuid):
                raise ValueError(f"static Spine atlas page identity mismatch: {source_id}")
        diagnostics = row.get("diagnostics", [])
        if any(not isinstance(item, dict) or item.get("code") != "NO_OBSERVED_BONE_MOTION" for item in diagnostics):
            raise ValueError(f"static Spine readback has an unrecognized diagnostic: {source_id}")
        proof_rows.append({"sourceId": source_id, "skeletonUuid": row["skeletonUuid"],
                           "sourceSkeletonSha256": row["sourceSkeletonSha256"], "version": row["version"],
                           "savedReferenceVerified": True, "bones": row["bones"], "slots": row["slots"],
                           "textureIdentitiesVerified": True,
                           "dynamicPoseStatus": "partial_no_observed_bone_motion" if diagnostics else "not_assessed_by_static_proof",
                           "diagnostics": diagnostics})
    return {"schemaVersion": 1, "profile": PROFILE, "status": "static_resource_identity_verified",
            "candidateManifestSha256": expected_candidate_manifest_sha256,
            "importPlanSha256": expected_import_plan_sha256,
            "nativeImportCompleted": True, "sourceCodeExecuted": False,
            "dynamicAnimationComplete": False, "spines": proof_rows}


def prepare_shader(candidate,expected_manifest,source_id,output):
    """Select an exact preserved Effect from a frozen candidate; no game adoption."""
    from .shader_profiles import describe,export_profile,prepare_probe
    root=safe(candidate)
    if fingerprint(root/'manifest.json')!=expected_manifest:fail('RESOURCE_PROBE_IDENTITY',str(root),'Expected exact frozen manifest')
    manifest=stage_manifest(root);owned={f['path']:f for f in manifest['files']}
    def selected(relative):
        raw=read(inside(root,relative),max_bytes=32*1024*1024);entry=owned.get(relative,{})
        if sha(raw)!=entry.get('sha256') or len(raw)!=entry.get('bytes'):fail('RESOURCE_PROBE_SOURCE_CHANGED',relative,'Exact selected candidate bytes required')
        return raw
    catalog_path=find_analysis(root,'resource-catalog.json').relative_to(root).as_posix();catalog=load(selected(catalog_path))
    matches=[r for r in catalog.get('shaders',[])if r.get('sourceId')==source_id]
    if len(matches)!=1:fail('RESOURCE_PROBE_SHADER_IDENTITY',source_id,'One exact catalog identity required')
    effects=[f for f in matches[0].get('files',[])if f['path'].endswith('/EffectDescription.json')]
    if len(effects)!=1:fail('RESOURCE_PROBE_SHADER_IDENTITY',source_id,'Exact preserved EffectDescription required')
    raw=selected(effects[0]['path']);effect=load(raw)
    profile=describe(effect,effect_sha256=sha(raw))
    if sha(raw)!=effects[0]['sha256'] or not profile['supported'] or profile['sourceId']!=source_id:
        fail('RESOURCE_PROBE_SHADER_PROFILE',source_id,'Only the exact supported program and macro assignment may be probed')
    out=new_output(output,[root]);subset=out/'UnityCandidate';(subset/'Assets').mkdir(parents=True)
    exported=export_profile(effect,subset,'resource-probe-'+expected_manifest[:12],source_id,effect_sha256=sha(raw))
    if not exported['written']:fail('RESOURCE_PROBE_SHADER_PROFILE',source_id,'Source identity is unsupported; original candidate was not modified')
    proof=dict(schemaVersion=1,sourceCandidateManifestSha256=expected_manifest,sourceId=source_id,effectSha256=sha(raw),
               catalogSha256=fingerprint(root/catalog_path),originalSourceCodeExecuted=False,sourceHierarchyIncluded=False,gameplayIncluded=False)
    write_json(subset/'Analysis/Evidence/resource-probe-input.json',proof)
    finish(subset,dict(schemaVersion=1,targetProfile='unity-6000.6.2f1-ugui',scopeMode='resource-probe-only',diagnostics=[]))
    plan=prepare_probe(subset,exported['profile'],source_id,out/'NativeProbe')
    receipt=dict(proof,status='prepared',profile=exported['profile']['profile'],candidate=str(subset),
                 candidateManifestSha256=fingerprint(subset/'manifest.json'),probeProject=plan['probeProject'],method=plan['method'],editorValidation='not_run')
    write_json(out/'resource-probe.json',receipt)
    return dict(status='prepared',candidate=str(subset),probeProject=plan['probeProject'],method=plan['method'],report=str(out/'resource-probe.json'))
