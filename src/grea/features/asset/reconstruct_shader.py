"""Reconstruct ShaderLab from pinned serialized states and extracted HLSLcc programs."""
import json
from pathlib import Path

from grea.common import hash_file
from grea.development.io import new_output, safe
from grea.recovery.unity_gles_shader import shaderlab


def reconstruct(args):
    source = safe(args.source)
    form_path = source / 'form.json'
    form = json.loads(form_path.read_text())
    used = {str(form_path): hash_file(form_path)}

    def program(index):
        if not isinstance(index, int) or index < 0:
            raise ValueError('Invalid source shader program index')
        path = source / f'{index}.glsl'
        used[str(path)] = hash_file(path)
        return path.read_text()

    code, counts = shaderlab(form, program)
    out = new_output(args.output, [source])
    output = out / 'reconstructed.shader'
    output.write_text(code)
    report = dict(shader=form['m_Name'], sourceFiles=used,
                  nonInstancedVariantsPerPass=counts, shaderPath=str(output),
                  shaderSha256=hash_file(output)['sha256'], nativeReadback='not_run',
                  limitation='GLES2/GLES3 combined programs only; target Editor compilation is required.')
    (out / 'shader.json').write_text(json.dumps(report, indent=2))
    return report
