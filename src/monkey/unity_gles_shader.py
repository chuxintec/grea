"""Reconstruct static ShaderLab passes from Unity HLSLcc GLES3 program evidence.

Input is the original serialized Shader.m_ParsedForm (form.json) and its
numbered decompressed GLES3 subprograms (<blobIndex>.glsl). The supported
profile uses non-instanced combined vertex/fragment programs. Always compile
and check the result in the target Editor before accepting a new source family.
"""
import argparse
import json
from pathlib import Path
import re

VECTOR_TYPES = {'vec2': 'float2', 'vec3': 'float3', 'vec4': 'float4', 'ivec2': 'int2', 'ivec3': 'int3', 'ivec4': 'int4', 'uvec2': 'uint2', 'uvec3': 'uint3', 'uvec4': 'uint4', 'bvec2': 'bool2', 'bvec3': 'bool3', 'bvec4': 'bool4'}
MATRIX_UNIFORMS = {'hlslcc_mtx4x4unity_ObjectToWorld': 'unity_ObjectToWorld', 'hlslcc_mtx4x4unity_MatrixVP': 'UNITY_MATRIX_VP', 'hlslcc_mtx4x4unity_WorldToObject': 'unity_WorldToObject', 'hlslcc_mtx4x4glstate_matrix_projection': 'UNITY_MATRIX_P', 'hlslcc_mtx4x4_cylinderMatrix': '_cylinderMatrix'}
BUILTIN_UNIFORMS = {'_Time', '_ProjectionParams', '_ScreenParams', '_WorldSpaceCameraPos', 'unity_LightShadowBias', '_LightColor0'}
DECLARATION = '\\b(in|out|uniform)\\s+(?:(?:highp|mediump|lowp)\\s+)?(\\w+)\\s+(\\w+)(?:\\[(\\d+)\\])?\\s*;'

def translate_vector_constructors(source):
    pat = '\\b(vec[234]|ivec[234]|bvec[234]|uvec[234]|greaterThanEqual)\\s*\\('
    m = re.search(pat, source)
    if not m:
        return source
    args = []
    depth = 0
    start = m.end()
    for i in range(start, len(source)):
        c = source[i]
        if c == '(':
            depth += 1
        elif c == ')':
            if depth == 0:
                args.append(translate_vector_constructors(source[start:i]))
                break
            depth -= 1
        elif c == ',' and depth == 0:
            args.append(translate_vector_constructors(source[start:i]))
            start = i + 1
    t = m[1]
    if t == 'greaterThanEqual':
        val = f'(({args[0]}) >= ({args[1]}))'
    elif len(args) == 1:
        val = f'(({VECTOR_TYPES[t]})({args[0]}))'
    else:
        val = VECTOR_TYPES[t] + '(' + ','.join(args) + ')'
    return source[:m.start()] + val + translate_vector_constructors(source[i + 1:])

def translate_program(raw):
    """Rebuild vertex and fragment entry points from one HLSLcc GLES3 program."""
    if 'gl_InstanceID' in raw:
        return None
    vertex, frag = raw.split('#ifdef FRAGMENT', 1)
    parts = []
    uniforms = {}
    attributes = []
    varyings = []
    has_front_face = 'gl_FrontFacing' in frag
    for i, source in enumerate((vertex, frag)):
        declarations = list(re.finditer(DECLARATION, source))
        before, body = source.split('void main()', 1)
        body = body[body.index('{') + 1:body.rindex('}')]
        body = body.replace('return;', 'return result;' if i else 'return o;')
        temporaries = re.findall('^(?:(?:highp|mediump|lowp)\\s+)?(?:vec[234]|[bui]vec[234]|float|int|uint|bool)\\s+\\w+(?:\\[[0-9]+\\])?;', before, re.M)
        body = '\n'.join(temporaries) + '\n' + body
        for declaration in declarations:
            kind, type_name, n, arr = declaration.groups()
            if kind == 'uniform':
                if n in MATRIX_UNIFORMS:
                    body = re.sub('\\b' + n + '\\b', 'transpose(' + MATRIX_UNIFORMS[n] + ')', body)
                    if n.endswith('_cylinderMatrix'):
                        uniforms[MATRIX_UNIFORMS[n]] = 'float4x4 _cylinderMatrix;'
                elif n not in BUILTIN_UNIFORMS:
                    uniforms[n] = VECTOR_TYPES.get(type_name, type_name) + ' ' + n + (f'[{arr}]' if arr else '') + ';'
            elif kind == 'in':
                if i == 0:
                    attributes.append(f'{VECTOR_TYPES[type_name]} {n} : {n[3:]};')
                body = re.sub('\\b' + n + '\\b', ('v.' if i == 0 else 'i.') + n, body)
            elif kind == 'out':
                if i == 0:
                    varyings.append(f'{VECTOR_TYPES[type_name]} {n} : {n[3:]};')
                body = re.sub('\\b' + n + '\\b', 'o.' + n if i == 0 else 'result', body)
        body = body.replace('gl_Position', 'o.pos').replace('gl_FrontFacing', 'front')
        body = translate_vector_constructors(body)
        body = re.sub('\\b(?:mediump|lowp|highp)\\s+', '', body)
        for x, y in {**VECTOR_TYPES, 'texture': 'tex2D', 'fract': 'frac', 'inversesqrt': 'rsqrt', 'roundEven': 'round'}.items():
            body = re.sub('\\b' + x + '\\b', y, body)
        if i == 0:
            parts.append('Varyings vert(Attributes v){Varyings o=(Varyings)0;\n' + body + '\nreturn o;\n}')
        else:
            parts.append('float4 frag(Varyings i' + (',bool front:SV_IsFrontFace' if has_front_face else '') + ') : SV_Target {float4 result=0;\n' + body + '\nreturn result;\n}')
    return '\n'.join(uniforms.values()) + '\nstruct Attributes {\n' + '\n'.join(attributes) + '\n};\nstruct Varyings {float4 pos:SV_POSITION;\n' + '\n'.join(varyings) + '\n};\n' + '\n'.join(parts)

def tags(tag):
    return 'Tags {' + ' '.join(('"' + k + '"="' + v + '"' for k, v in tag['tags'])) + '}'

def state(x, options=None):
    if x['name'] not in ('', '<noninit>'):
        return '[' + x['name'] + ']'
    v = int(x['val'])
    return options[v] if options else str(v)
COMPARE_FUNCTIONS = 'Always Never Less Equal LEqual Greater NotEqual GEqual Always'.split()
STENCIL_OPERATIONS = 'Keep Zero Replace IncrSat DecrSat Invert IncrWrap DecrWrap'.split()
BLEND_FACTORS = 'Zero One DstColor SrcColor OneMinusDstColor SrcAlpha OneMinusSrcColor DstAlpha OneMinusDstAlpha SrcAlphaSaturate OneMinusSrcAlpha'.split()

def renderstate(s):
    rt = s['rtBlend0']
    cm = rt['colMask']
    mask = state(cm) if cm['name'] not in ('', '<noninit>') else ''.join((c for j, c in enumerate('ABGR') if int(cm['val']) & 1 << j)) or '0'
    op = s['stencilOp']
    lines = [tags(s['m_Tags']), 'Cull ' + state(s['culling'], ['Off', 'Front', 'Back']), 'ZWrite ' + state(s['zWrite'], ['Off', 'On']), 'ZTest ' + state(s['zTest'], COMPARE_FUNCTIONS), 'ColorMask ' + mask, 'Blend ' + state(rt['srcBlend'], BLEND_FACTORS) + ' ' + state(rt['destBlend'], BLEND_FACTORS) + ', ' + state(rt['srcBlendAlpha'], BLEND_FACTORS) + ' ' + state(rt['destBlendAlpha'], BLEND_FACTORS)]
    lines.append('Stencil { Ref ' + state(s['stencilRef']) + ' ReadMask ' + state(s['stencilReadMask']) + ' WriteMask ' + state(s['stencilWriteMask']) + ' Comp ' + state(op['comp'], COMPARE_FUNCTIONS) + ' Pass ' + state(op['pass'], STENCIL_OPERATIONS) + ' Fail ' + state(op['fail'], STENCIL_OPERATIONS) + ' ZFail ' + state(op['zFail'], STENCIL_OPERATIONS) + ' }')
    return lines

def prop(p):
    t = p['m_Type']
    v = [float(p[f'm_DefValue[{i}]']) for i in range(4)]
    attr = ''.join(('[' + a + '] ' for a in p['m_Attributes']))
    type_name = ['Color', 'Vector', 'Float', f'Range({v[1]},{v[2]})', '2D', 'Int'][t]
    default = '(' + ','.join(map(str, v)) + ')' if t in (0, 1) else '"' + p['m_DefTexture']['m_DefaultName'] + '" {}' if t == 4 else str(v[0])
    return f'''{attr}{p['m_Name']} ("{p['m_Description']}", {type_name}) = {default}'''

def shaderlab(t, read_program):
    """Use the serialized pass states, properties and non-instanced keyword variants."""
    name = t['m_Name']
    lines = ['Shader "' + name + '" {', 'Properties {', *[prop(p) for p in t['m_PropInfo']['m_Props']], '}']
    variant_counts = []
    for sub in t['m_SubShaders']:
        lines += ['SubShader {', tags(sub['m_Tags']), 'LOD ' + str(sub['m_LOD'])]
        for shader_pass in sub['m_Passes']:
            variants = {}
            for g in shader_pass['progVertex']['m_PlayerSubPrograms']:
                for v in g:
                    if v['m_GpuProgramType'] != 4:
                        continue
                    keys = tuple(sorted((t['m_KeywordNames'][k] for k in v['m_KeywordIndices'])))
                    if 'INSTANCING_ON' in keys:
                        continue
                    code = translate_program(read_program(v['m_BlobIndex']))
                    if code:
                        variants[keys] = code
            if not variants:
                raise ValueError('No non-instanced GLES3 program for ' + name)
            keywords = sorted(set.union(*(set(ks) for ks in variants)) - set.intersection(*(set(ks) for ks in variants)))
            lines += ['Pass {', *(['Name "' + shader_pass['m_State']['m_Name'] + '"'] if shader_pass['m_State']['m_Name'] else []), *renderstate(shader_pass['m_State']), 'HLSLPROGRAM', '#pragma target 3.5', '#pragma vertex vert', '#pragma fragment frag']
            if set(keywords) & {'SHADOWS_DEPTH', 'SHADOWS_CUBE'}:
                lines += ['#pragma multi_compile_shadowcaster']
            for k in keywords:
                if k not in ('SHADOWS_DEPTH', 'SHADOWS_CUBE'):
                    lines += ['#pragma shader_feature_local __ ' + k]
            lines += ['#include "UnityCG.cginc"', '#include "Lighting.cginc"']
            for j, (keys, code) in enumerate(variants.items()):
                lines += ['#' + ('if ' if j == 0 else 'elif ') + (' && '.join((('' if k in keys else '!') + 'defined(' + k + ')' for k in keywords)) or '1'), code]
            lines += ['#else', '#error Source_variant_unavailable', '#endif', 'ENDHLSL', '}']
            variant_counts.append(len(variants))
        lines += ['}']
    lines += ['}']
    return ('\n'.join(lines), variant_counts)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    form = json.loads((args.source / 'form.json').read_text())
    shader, variants = shaderlab(form, lambda i: (args.source / f'{i}.glsl').read_text())
    if args.output.exists() and args.output.read_text() != shader:
        raise ValueError(f'Output already exists with different contents: {args.output}')
    args.output.write_text(shader)
    print(json.dumps(dict(shader=form['m_Name'], nonInstancedVariantsPerPass=variants)))



def stage_shader_includes(source_shader, target_shader):
    """Copy relative include dependencies beside an exported ShaderLab asset."""
    from .unity_visual_repair import write_owned
    pending = [(Path(source_shader), Path(target_shader))]
    root = Path(source_shader).resolve().parent
    seen = set()
    while pending:
        source, target = pending.pop()
        if source in seen:
            continue
        seen.add(source)
        for name in re.findall(r'^\s*#\s*include(?:_with_pragmas)?\s+"([^"]+)"', source.read_text(), re.M):
            relative = Path(name)
            if relative.is_absolute() or relative.parts[:1] in [('Packages',), ('Assets',)]:
                continue
            include = (source.parent / relative).resolve()
            if not include.is_file():
                continue  # Built-in includes are resolved by the Editor.
            if not include.is_relative_to(root):
                raise ValueError(f'Shader include escapes source directory: {name}')
            destination = target.parent / relative
            write_owned(destination, include.read_bytes())
            pending.append((include, destination))


if __name__ == '__main__':
    main()
