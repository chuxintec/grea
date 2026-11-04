"""Create a neutral editable source and drive the installed public recovery CLI.

No original game, native receipt, Editor, SDK or network access is used. Outputs
are generated candidates, never claimed to be native-saved or playable assets.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    root = Path(args.out).resolve()
    root.mkdir(parents=True, exist_ok=False)
    source = root / 'source'
    (source / 'assets').mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
    python = str(Path(args.python).absolute())
    checks = []

    def put(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def run(*argv):
        result = subprocess.run([python, '-I', '-m', 'monkey.cli', *map(str, argv)],
                                cwd=root, env=env, capture_output=True, text=True, timeout=120)
        stage = str(argv[0])
        (root / (stage + '-stdout.json')).write_text(result.stdout, encoding='utf-8')
        (root / (stage + '-stderr.txt')).write_text(result.stderr, encoding='utf-8')
        checks.append(dict(command=stage, exitCode=result.returncode))
        if result.returncode not in (0, 1):
            raise RuntimeError(stage + ': ' + result.stderr[-1000:])
        return json.loads(result.stdout)

    texture = '00000000-0000-0000-0000-000000000002'
    frame = '00000000-0000-0000-0000-000000000001'
    prefab = '00000000-0000-0000-0000-000000000003'
    put(source / 'project.json', dict(version='2.4.15', id='neutral-release-fixture'))
    # Generate the bitmap through the installed Python dependency, not a checkout.
    subprocess.run([python, '-I', '-c', 'from PIL import Image; import sys; '
                    'Image.new("RGBA",(8,6),(0,128,255,255)).save(sys.argv[1])',
                    str(source / 'assets/panel.png')], check=True, env=env)
    put(source / 'assets/panel.png.meta', dict(uuid=texture, importer='texture', subMetas={
        'panel': dict(uuid=frame, importer='sprite-frame', rawTextureUuid=texture,
                      trimX=1, trimY=1, width=4, height=3, rawWidth=6, rawHeight=5,
                      offsetX=0, offsetY=0, borderLeft=1, borderTop=1, borderRight=1, borderBottom=1)}))
    put(source / 'assets/panel.prefab.meta', dict(uuid=prefab, importer='prefab'))
    put(source / 'assets/panel.prefab', [
        {'__type__': 'cc.Prefab', 'data': {'__id__': 1}},
        dict(__type__='cc.Node', _name='Neutral panel', _parent=None, _children=[],
             _components=[{'__id__': 2}], _contentSize=dict(width=240, height=150),
             _anchorPoint=dict(x=.5, y=.5),
             _trs={'__type__': 'TypedArray', 'ctor': 'Float64Array',
                   'array': [375, 667, 0, 0, 0, 0, 1, 1, 1, 1]}),
        dict(__type__='cc.Sprite', node={'__id__': 1}, _spriteFrame={'__uuid__': frame}, _type=1, _sizeMode=0)])
    before = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in source.rglob('*') if p.is_file()}
    run('catalog', '--source', source, '--source-profile', 'cocos-2.4.15-project', '--out', root / 'catalog')
    catalog = json.loads((root / 'catalog/catalog.json').read_text(encoding='utf-8'))
    index = next(row['index'] for row in catalog['selection'] if row['key'] == prefab)
    run('inspect', '--source', source, '--source-profile', 'cocos-2.4.15-project',
        '--asset-index', index, '--out', root / 'inspection')
    run('normalize', '--manifest', root / 'inspection/source-manifest.json', '--out', root / 'ir')
    run('plan', '--ir', root / 'ir/ir.json', '--namespace', 'neutral-release',
        '--target-profile', 'unity-6000.6.2f1-ugui', '--out', root / 'plan')
    run('export', '--plan', root / 'plan/plan.json', '--out', root / 'candidate')
    run('verify', '--candidate', root / 'candidate', '--level', 'static', '--out', root / 'verification')
    assert all(hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
               for name, digest in before.items())
    # Independent synthetic code-handoff contract fixture. It carries no native
    # acceptance receipt and is not labelled a saved game selection.
    producer = root / 'code-proof-producer'
    target = root / 'code-proof-target'
    producer.mkdir()
    target.mkdir()
    script = 'Assets/Scripts/StaticFields_Example.cs'
    carrier = subprocess.check_output([python, '-I', '-c',
        'from monkey.prefab_static_carriers import _unity_script; '
        'print(_unity_script("Monkey.Example","StaticFields_Example",'
        '[dict(fieldName="value",storageType="UnityEngine.Object")]),end="")'], env=env)
    digest = lambda raw: hashlib.sha256(raw).hexdigest()
    binding = dict(scriptPath=script, scriptSha256=digest(carrier),
                   typeName='Monkey.Example.StaticFields_Example', behavior='disabled', enabled=False,
                   fields=[dict(fieldName='value', storageType='UnityEngine.Object')])
    plan_path = 'Assets/Game/Editor/Conversion/import-plan.json'
    plan_raw = json.dumps(dict(components=[dict(staticFieldBinding=binding)])).encode()
    source_files = {script: carrier, plan_path: plan_raw}
    target_files = {script: carrier, 'Packages/manifest.json': b'{}',
                    'Packages/packages-lock.json': b'{}'}
    def inventory(folder, payloads):
        rows = []
        for name, raw in payloads.items():
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            rows.append(dict(path=name, sha256=digest(raw), bytes=len(raw)))
        return rows
    producer_rows = inventory(producer, source_files)
    put(producer / 'manifest.json', dict(projectLayout='monkey-project/2.0.0',
        targetProfile='unity-6000.6.2f1-ugui', files=producer_rows))
    producer_sha = digest((producer / 'manifest.json').read_bytes())
    target_rows = inventory(target, target_files)
    warning = dict(path=script, code='UNANALYZED_CSHARP_DEPENDENCIES')
    put(target / 'manifest.json', dict(targetProfile='unity-6000.6.2f1-ugui',
        sourceCandidateManifestSha256=producer_sha, diagnostics=[warning], files=target_rows))
    target_raw = (target / 'manifest.json').read_bytes()
    run('audit-native-code-dependencies', '--candidate', target,
        '--expected-manifest', digest(target_raw), '--producer-candidate', producer,
        '--expected-producer-manifest', producer_sha, '--out', root / 'code-proof-audit')
    supplement = json.loads((root / 'code-proof-audit/code-dependency-supplement.json').read_text())
    assert supplement['uncovered'] == [] and supplement['originalDiagnostics'] == [warning]
    assert (target / 'manifest.json').read_bytes() == target_raw
    manifest = root / 'candidate/manifest.json'
    report = dict(schemaVersion=1, status='generated-and-statically-checked', checks=checks,
                  sourceUnchanged=True, native='not_run', visual='not_run', player='not_run',
                  business='not_run', candidate=str(manifest.parent),
                  candidateManifestSha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                  assurance='neutral source-to-generated-candidate fixture; no synthetic native acceptance')
    put(root / 'fixture-result.json', report)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
