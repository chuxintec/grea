"""Portable installed-wheel CLI smoke; no Editor, global install, source game or CDN."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--python',default=sys.executable);parser.add_argument('--out',required=True)
    args=parser.parse_args();output=Path(args.out).absolute()
    if output.exists():raise FileExistsError(output)
    python=str(Path(args.python).absolute());checks=[]
    with tempfile.TemporaryDirectory(prefix='monkey-installed-smoke-')as temp:
        work=Path(temp).resolve();env={k:v for k,v in os.environ.items()if k not in ('PYTHONPATH','PYTHONHOME')}
        def run(argv,expected=0):
            result=subprocess.run([python,'-I','-B',*argv],cwd=work,env=env,capture_output=True,text=True,timeout=30)
            checks.append(dict(arguments=argv,exitCode=result.returncode,expectedExitCode=expected))
            if result.returncode!=expected:raise RuntimeError('Installed CLI failed: '+str(argv)+' '+result.stderr[-500:])
            return result.stdout
        identity=json.loads(run(['-c','import json,monkey,sys;print(json.dumps(dict(version=monkey.__version__,module=monkey.__file__,python=sys.version.split()[0])))']))
        if 'site-packages'not in identity['module']:raise RuntimeError('Smoke requires an installed wheel outside the source checkout')
        run(['-m','monkey.cli','--version']);cap=json.loads(run(['-m','monkey.cli','capabilities','--json']))
        for command in ('acquire-resources','diagnose','doctor','space-preview','resource-probe','adopt','code-model','code-emit','code-select','wasm-code-source','wasm-code-candidate','unity-code-source','unity-code-candidate','code-native-probe',
                        'static-code-bindings','code-native-prepare','code-native-run','code-native-status','code-native-continue','code-native-reassemble','code-native-revise','code-native-add-json',
                        'code-architecture-module-prepare','code-architecture-module-run','code-architecture-module-status','code-architecture-module-recheck','code-architecture-module-recover'):
            run(['-m','monkey.cli',command,'--help'])
        run(['-m','monkey.cli','static-code-bindings','destinations','--prepared',str(work/'missing-prepared'),'--candidate',str(work/'missing-candidate'),'--output',str(work/'must-not-exist.json')],expected=2)
        assert not (work/'must-not-exist.json').exists()
        run(['-m','monkey.cli','tool','--help'])
        for tool in ('laya_contract_audit','read_elf_values','unpack_xapk','shader_probe','decrypt_v1mmwx_wxapkg','unpack_wxapkg','export_config_tables'):
            run(['-m','monkey.cli','tool',tool,'--help'])
        run(['-c','from importlib.resources import files; p=files("monkey.targets"); assert all(p.joinpath(x).is_file() for x in ("CreatorResources.js","RecoveredSprite.shader","UnityShaderProbe.cs","CodeCollections.cs","behaviors/probes/UnityBehaviorProbe.cs.meta","behaviors/probes/Editor/MonkeyBehaviorProbeBootstrap.cs.meta")); assert files("monkey").joinpath("code-graph.cjs").is_file(); assert files("monkey.extensions.legacy_foodstreet").joinpath("RecipeJsonConfiguration.cs").is_file(); assert files("monkey.extensions.legacy_foodstreet").joinpath("extension.json").is_file(); assert all(files("monkey.extensions.legacy_foodstreet").joinpath("code_profiles",x+".json").is_file() for x in ("foodstreet-demand-health-v1","foodstreet-motion-math-v1"))'])
        code_status='not_run_node_unavailable'
        if shutil.which('node'):
            source=work/'original.js';source.write_text('var Rules=(function(){function e(){} e.Clamp=function(x){if(x<0)return 0;return x;};return e;})();',encoding='utf-8')
            source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
            run(['-m','monkey.cli','code-model','--source',str(source),'--lexical-graph','--expected-source',source_sha,'--out',str(work/'code-index')],expected=1)
            graph=json.loads((work/'code-index/code-graph.json').read_bytes());cls=graph['classes'][0];method=graph['methods'][0]
            contract=work/'contract.json';contract.write_text(json.dumps(dict(schemaVersion=1,sourceSha256=source_sha,namespace='Game.Domain.Recovered',records=[],modules=[dict(id='Rules',targetClass='Rules',classId=cls['id'],classSha256=cls['sourceSha256'],fields={},methods=[dict(id=method['id'],sha256=method['sourceSha256'],name='Clamp',parameters=['Number'],returns='Number')])])),encoding='utf-8')
            selectors=work/'selectors.json';selectors.write_text(json.dumps([dict(classId=cls['id'],methodId=method['id'])]),encoding='utf-8')
            run(['-m','monkey.cli','code-select','--source',str(source),'--selectors',str(selectors),'--type-evidence',str(contract),'--out',str(work/'selection')])
            assert json.loads((work/'selection/selection.json').read_bytes())['lowering']=='passed'
            run(['-m','monkey.cli','code-emit','--source',str(source),'--module-contract',str(work/'selection/module-contract.json'),'--out',str(work/'code-candidate')],expected=1)
            generated=(work/'code-candidate/Assets/Game/Domain/Recovered/Rules.cs').read_text()
            assert 'if (' in generated and 'return x;' in generated
            assert (work/'code-candidate/SourceRecovery/Code/Source/RecoveredSource.js').read_bytes()==source.read_bytes()
            code_status='installed_graph_and_typed_body_emission_passed;compile_not_run'
        (work/'source').mkdir();(work/'source/manual.txt').write_text('retained',encoding='utf-8')
        evidence=work/'evidence.json';evidence.write_text(json.dumps(dict(files=[dict(sourceKey='explicit',path='missing.bin',status='unavailable',httpStatus=404)])),encoding='utf-8')
        run(['-m','monkey.cli','doctor','--out',str(work/'doctor')])
        run(['-m','monkey.cli','space-preview','--root',str(work/'source'),'--out',str(work/'space')])
        run(['-m','monkey.cli','diagnose','--source',str(evidence),'--out',str(work/'diagnose')],expected=1)
        diagnostics=json.loads((work/'diagnose/diagnostics.json').read_bytes())
        assert diagnostics['issues'][0]['code']=='CDN_HTTP_404'
        assert (work/'source/manual.txt').read_text()=='retained'
        report=dict(schemaVersion=1,status='pass',platform=sys.platform,machine=platform.machine(),installed=identity,
                    checks=checks,declaredTargetProfiles=cap['targetProfiles'],codeModules=code_status,editorStarted=False,remoteFetched=False,globalInstall=False)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='pass',platform=sys.platform,checks=len(checks),report=str(output))))


if __name__=='__main__':main()
