#!/usr/bin/env python3
"""Read-only Windows desktop/Unity gate inventory. Does not install or open projects."""
import argparse,json,os,platform,shutil,subprocess
from pathlib import Path

def inspect():
    result={'schema_version':1,'host':platform.system(),'architecture':platform.machine(),
            'desktop':'not_run','unity_editor':'not_run','player':'not_run',
            'limits':['Server/CLI tests are not Windows 11 desktop or Unity Player acceptance.']}
    if os.name!='nt':
        result['blocked_reason']='Requires a native Windows x64 desktop; current host is not Windows.'
        return result
    edition=platform.win32_edition();version=platform.version();build=int(version.split('.')[-1])
    result.update(windows_edition=edition,windows_build=build,
                  windows_11_candidate=build>=22000 and not edition.lower().startswith('server'))
    binary=shutil.which('unity') or shutil.which('unity.exe')
    result['unity_cli']={'binary_present':bool(binary),'connection':'not_run'}
    # A version probe cannot establish Editor connection/license/project success.
    if binary:
        p=subprocess.run([binary,'--version'],capture_output=True,text=True,encoding='utf-8',timeout=20)
        result['unity_cli'].update(version=p.stdout.strip()[:200],exit_code=p.returncode)
    result['next_steps']=[
        'Verify the candidate SHA256SUMS and target before unpacking.',
        'Use verify_plugin.py for relocated runtime/denial probes.',
        'Use verify_plugin_clients.py --client codex with a native client and independent configuration; no model requests.',
        'Prepare a NEW numeric-combat sample with prepare-unity-framework.py; do not select an original game.',
        'Run unity run <new-project> -- -nographics -executeMethod Numeric.Editor.SampleBuilder.Seed, then EditMode/PlayMode tests.',
        'Use build-framework-sample.py --target windows-x64 with NEW source/work/output paths.',
        'Save/reopen the Editor, then test the actual Windows Player input, pause/cancel, pending reward and save reopen; retain source hashes and receipts.'
    ]
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    with a.out.open('x',encoding='utf-8') as stream:json.dump(inspect(),stream,ensure_ascii=False,indent=2);stream.write('\n')
