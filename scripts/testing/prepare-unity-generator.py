#!/usr/bin/env python3
"""Prepare a NEW isolated generator test harness or a copy for generated prefab PlayMode tests."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('m2_prepare', Path(__file__).with_name('prepare-unity-framework.py'))
m2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m2)


def prepare(output, generated_project=None):
    output = Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('Output must be a new path without symlinks')
    tests = ROOT / 'tests/unity/m3'
    if generated_project is None:
        m2.prepare(output)
        shutil.copytree(tests / 'Editor', output / 'Assets/M3Tests')
        shutil.copytree(tests / 'Support', output / 'Assets/M3Support')
        (output / 'grea-m3-test-project.marker').write_text('Isolated synthetic generator tests; never a game project.\n', encoding='utf-8')
    else:
        source = Path(generated_project).resolve()
        if not (source / 'Tools/Generated/manifests/project.json').is_file():
            raise ValueError('Expected a generated M3 source project')
        entries = [p for name in ('Assets','Packages','ProjectSettings') for p in (source/name).rglob('*')]
        if any(p.is_symlink() for p in entries):
            raise ValueError('Symlinks are unsupported')
        output.mkdir(parents=True)
        for name in ('Assets','Packages','ProjectSettings'):
            shutil.copytree(source/name,output/name)
        shutil.copytree(tests/'Runtime',output/'Assets/M3PlayTests')
        manifest=output/'Packages/manifest.json';data=json.loads(manifest.read_text(encoding='utf-8'))
        data['dependencies']['com.unity.test-framework']='1.8.0'
        data['testables']=['com.grea.foundation','com.grea.ui.ugui','com.grea.editor']
        manifest.write_text(json.dumps(data,indent=2)+'\n', encoding='utf-8')
    return {'output':str(output),'unityExecuted':False,'mode':'generated-prefab-playmode' if generated_project else 'generator-editmode'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    parser.add_argument('--generated-project');args=parser.parse_args()
    print(json.dumps(prepare(args.output,args.generated_project),indent=2))
