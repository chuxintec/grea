"""Export only proven selected Texture2D pixels; never invoke a whole-bundle exporter."""
from pathlib import Path
import subprocess
from PIL import Image
from .io import safe,read,load,sha,new_output,write_json,inside
from .sources.compiled import fail
from .unity_texture_selection import validate_selection

CONTRACT='unity-selected-texture-export/1'


def export(source,derivative,hydration_report,expected_hydration_sha256,selection_manifest,provider_python,output,budget_seconds=120):
    paths={k:safe(v)for k,v in dict(source=source,derivative=derivative,hydrationReport=hydration_report,selectionManifest=selection_manifest).items()}
    raw={k:read(v,max_bytes=128*1024*1024)for k,v in paths.items()};pins={k:sha(v)for k,v in raw.items()}
    if pins['hydrationReport']!=expected_hydration_sha256:fail('UNITY_TEXTURE_EXPORT_REPORT','$','Frozen hydration report SHA-256 differs')
    proof=load(raw['hydrationReport']);selection=validate_selection(load(raw['selectionManifest']),pins['source'])
    required=dict(scope='selected-texture-set',selectionComplete=True,serializationCommitted=True,inventoryComplete=True,sourceCodeExecuted=False,originalSourceWritten=False,nonTextureObjectsUnchanged=True,unselectedObjectsUnchanged=True)
    if proof.get('status')not in('partial','hydrated')or any((proof.get(k)is not v)if type(v)is bool else(proof.get(k)!=v)for k,v in required.items())or proof.get('sourceSha256')!=pins['source']or proof.get('derivedBundleSha256')!=pins['derivative']or proof.get('wholeContainerComplete')is not(proof['status']=='hydrated')or proof.get('missing')or proof.get('diagnostics'):
        fail('UNITY_TEXTURE_EXPORT_PROOF','$','Committed exact selected hydration proof and input/derivative identities required')
    if type(budget_seconds)is not int or not 1<=budget_seconds<=1200:fail('UNITY_TEXTURE_EXPORT_BUDGET','$','Expected 1..1200 seconds')
    requested=Path(provider_python).absolute();safe(requested.parent);python=safe(requested.resolve(strict=True))
    out=new_output(output,[*paths.values(),python.parent]);job=dict(schemaVersion=1,contract=CONTRACT,paths={k:str(v)for k,v in paths.items()},pins=pins,selection=selection,proof=proof)
    write_json(out/'export-job.json',job);receipt=dict(schemaVersion=1,contract=CONTRACT,status='started',processExited=False)
    with (out/'provider.log').open('wb')as stream:
        (out/'provider.log').chmod(0o600)
        child=subprocess.Popen([str(requested),'-I','-B',str(Path(__file__).parent/'sources/unity_worker.py'),'--export-selected-textures',str(out/'export-job.json'),str(out/'pixel-readback.json')],cwd=out,stdout=stream,stderr=subprocess.STDOUT)
        receipt['pid']=child.pid;write_json(out/'execution.json',receipt)
        try:child.wait(timeout=budget_seconds)
        except subprocess.TimeoutExpired:
            child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:pass
    receipt.update(processExited=child.poll()is not None,exitCode=child.poll())
    if child.poll()!=0:
        receipt['status']='failed'if receipt['processExited']else'pending_child_exit';write_json(out/'execution.json',receipt);return receipt
    receipt['status']='validating-png-output';write_json(out/'execution.json',receipt)
    body=load(read(out/'pixel-readback.json'));records=[];files=[];candidate=out/'Candidate';candidate.mkdir()
    if body.get('status')!='selected-pixels-verified'or body.get('unselectedObjectsUnchanged')is not True or body.get('sourceAndDerivativeUnchanged')is not True or len(body.get('textures',[]))!=len(selection):fail('UNITY_TEXTURE_EXPORT_READBACK','$','Incomplete selected pixel readback')
    for row in body['textures']:
        pixels=read(inside(out,row['payloadPath']),max_bytes=64*1024*1024);w,h=row['width'],row['height']
        if type(w)is not int or type(h)is not int or not 0<w*h<=16777216 or len(pixels)!=w*h*4 or sha(pixels)!=row['rgbaRawSha256']:fail('UNITY_TEXTURE_EXPORT_PIXELS','$','Payload dimensions or pixel SHA differ')
        identity=sha((row['file']+'\0'+row['pathId']+'\0'+row['sourceRawSha256']).encode())
        relative='Assets/Game/Content/Textures/Selected/Texture'+identity+'.png';target=inside(candidate,relative);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():fail('UNITY_TEXTURE_EXPORT_COLLISION',relative,'Fresh per-object PNG path required')
        with Image.frombytes('RGBA',(w,h),pixels)as image:image.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(target,format='PNG')
        with Image.open(target)as image:
            if image.size!=(w,h)or sha(image.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes())!=row['rgbaRawSha256']:fail('UNITY_TEXTURE_EXPORT_PNG','$','PNG readback differs from exact selected pixels')
        record=dict(source={k:row[k]for k in ('file','pathId','sourceRawSha256','sourceName','sourceSettings')},
                    hydration={k:row[k]for k in ('rgbaRawSha256','logicalPath','cacheSha256','normalization','decoder')},
                    target=dict(path=relative,bytes=target.stat().st_size,sha256=sha(read(target)),width=w,height=h,pixelOrientation='vertical-flip-for-unity',nativeGuid='not-assigned',nativeImport='not_run'),
                    importerIntent=dict(textureCompression='Uncompressed',alphaIsTransparency=False,isReadable=False,sourceSampling='retained-in-sourceSettings-for-controlled-adoption',nativeValidated=False))
        records.append(record);files.append(record['target'])
    unchanged=all(sha(read(paths[k],max_bytes=128*1024*1024))==pins[k]for k in paths)
    if not unchanged:fail('UNITY_TEXTURE_EXPORT_INPUT_DRIFT','$','An original, derivative or frozen receipt changed')
    manifest=dict(schemaVersion=1,contract=CONTRACT,status='partial'if proof['status']=='partial'else'exported',scope='selected-texture-pngs',exportComplete=True,
                  wholeContainerComplete=proof['wholeContainerComplete'],sourceContainerStatus=proof['status'],deferred=proof.get('deferred',[]),inputPins=pins,
                  sourceAndDerivativeUnchanged=True,unselectedObjectsUnchanged=True,sourceCodeExecuted=False,assetRipperInvoked=False,nativeImport='not_run',textures=records,files=files)
    write_json(candidate/'manifest.json',manifest)
    receipt.update(status=manifest['status'],exportComplete=True,wholeContainerComplete=manifest['wholeContainerComplete'],textures=len(records),candidate=str(candidate),manifest=str(candidate/'manifest.json'),manifestSha256=sha(read(candidate/'manifest.json')),sourceAndDerivativeUnchanged=True)
    write_json(out/'execution.json',receipt);return receipt
