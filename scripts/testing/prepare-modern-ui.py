#!/usr/bin/env python3
"""Prepare a new opt-in modern sample. Does not run Unity or change other projects."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[2]
PROFILE=ROOT/'tools/unity/profiles/modern-ui'


def prepare(output,sample,font,font_license=None):
    output=Path(output).absolute();font=Path(font).absolute()
    if output.exists() or any(p.is_symlink() for p in (output,*output.parents,font,*font.parents)):
        raise ValueError('New output and ordinary font required')
    if sample not in ('numeric-combat','grid-puzzle') or font.suffix.lower() not in ('.ttf','.otf') or not font.is_file():
        raise ValueError('Select a supported consumer and explicitly licensed font')
    shutil.copytree(ROOT/'tools/unity/framework/packages',output/'Packages')
    for package in (PROFILE/'packages').iterdir():
        if package.is_dir():shutil.copytree(package,output/'Packages'/package.name)
    shutil.copytree(PROFILE/'Assets',output/'Assets')
    asset=output/'Assets/Fonts'/('sample_font'+font.suffix.lower());asset.parent.mkdir();shutil.copyfile(font,asset)
    if font_license:
        license_path=Path(font_license).absolute()
        if not license_path.is_file() or any(p.is_symlink() for p in (license_path,*license_path.parents)):raise ValueError('Ordinary explicit font license file required')
        shutil.copyfile(license_path,asset.parent/'FONT_LICENSE.txt')
    (output/'font-source.marker').write_text(asset.relative_to(output).as_posix())
    (output/'font-source.json').write_text(json.dumps({'sha256':hashlib.sha256(font.read_bytes()).hexdigest(),'source_name':font.name}))
    (output/'modern-profile.marker').write_text(sample)
    dependencies={'com.unity.ugui':'2.6.0','com.unity.inputsystem':'1.20.0','com.unity.render-pipelines.universal':'17.6.0','com.unity.test-framework':'1.8.0','com.unity.modules.audio':'1.0.0','com.unity.modules.particlesystem':'1.0.0','com.unity.modules.animation':'1.0.0'}
    (output/'Packages/manifest.json').write_text(json.dumps({'dependencies':dependencies,'testables':[p.name for p in (output/'Packages').iterdir() if p.is_dir()]},indent=2))
    (output/'ProjectSettings').mkdir();(output/'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.6.2f1\n')
    snapshot={p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file()}
    (output/'prepared-inputs.json').write_text(json.dumps(snapshot,indent=2));return {'project':str(output),'profile':'modern-ui-v1','sample':sample,'unityExecuted':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--sample',choices=['numeric-combat','grid-puzzle'],required=True);p.add_argument('--font',required=True);p.add_argument('--font-license')
    a=p.parse_args();print(json.dumps(prepare(a.output,a.sample,a.font,a.font_license)))
