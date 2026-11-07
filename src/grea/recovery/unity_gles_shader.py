"""Reconstruct static ShaderLab passes from Unity HLSLcc GLES2/GLES3 program evidence.

Input is the original serialized Shader.m_ParsedForm (form.json) and its
numbered decompressed GLES subprograms (<blobIndex>.glsl). The supported
profile uses non-instanced combined vertex/fragment programs. Always compile
and check the result in the target Editor before accepting a new source family.
"""
import argparse
import json
from pathlib import Path
import re

VECTOR_TYPES = {'vec2': 'float2', 'vec3': 'float3', 'vec4': 'float4', 'ivec2': 'int2', 'ivec3': 'int3', 'ivec4': 'int4', 'uvec2': 'uint2', 'uvec3': 'uint3', 'uvec4': 'uint4', 'bvec2': 'bool2', 'bvec3': 'bool3', 'bvec4': 'bool4'}
MATRIX_UNIFORMS = {'hlslcc_mtx4x4unity_ObjectToWorld': 'unity_ObjectToWorld', 'hlslcc_mtx4x4unity_MatrixVP': 'UNITY_MATRIX_VP', 'hlslcc_mtx4x4unity_WorldToObject': 'unity_WorldToObject', 'hlslcc_mtx4x4glstate_matrix_projection': 'UNITY_MATRIX_P', 'hlslcc_mtx4x4_cylinderMatrix': '_cylinderMatrix'}
# Unity 6 Built-in renderer declarations from UnityShaderVariables.cginc.
BUILTIN_UNIFORMS = {
    '_CosTime',
    '_LightColor0',
    '_LightPositionRange',
    '_LightProjectionParams',
    '_LightShadowData',
    '_LightSplitsFar',
    '_LightSplitsNear',
    '_ProjectionParams',
    '_ScreenParams',
    '_SinTime',
    '_Time',
    '_WorldSpaceCameraPos',
    '_WorldSpaceLightPos0',
    '_ZBufferParams',
    'glstate_lightmodel_ambient',
    'glstate_matrix_projection',
    'glstate_matrix_transpose_modelview0',
    'unity_4LightAtten0',
    'unity_4LightPosX0',
    'unity_4LightPosY0',
    'unity_4LightPosZ0',
    'unity_AmbientEquator',
    'unity_AmbientGround',
    'unity_AmbientSky',
    'unity_CameraInvProjection',
    'unity_CameraProjection',
    'unity_CameraToWorld',
    'unity_CameraWorldClipPlanes',
    'unity_DeltaTime',
    'unity_DynamicLightmapST',
    'unity_FogColor',
    'unity_FogParams',
    'unity_HalfStereoSeparation',
    'unity_IndirectSpecColor',
    'unity_LODFade',
    'unity_LightAtten',
    'unity_LightColor',
    'unity_LightPosition',
    'unity_LightShadowBias',
    'unity_LightmapST',
    'unity_MatrixInvV',
    'unity_MatrixV',
    'unity_MatrixVP',
    'unity_ObjectToWorld',
    'unity_OcclusionMaskSelector',
    'unity_OrthoParams',
    'unity_ProbeVolumeMin',
    'unity_ProbeVolumeParams',
    'unity_ProbeVolumeSizeInv',
    'unity_ProbeVolumeWorldToObject',
    'unity_ProbesOcclusion',
    'unity_RenderingLayer',
    'unity_SHAb',
    'unity_SHAg',
    'unity_SHAr',
    'unity_SHBb',
    'unity_SHBg',
    'unity_SHBr',
    'unity_SHC',
    'unity_ShadowColor',
    'unity_ShadowFadeCenterAndType',
    'unity_ShadowSplitSpheres',
    'unity_ShadowSplitSqRadii',
    'unity_SpecCube0_BoxMax',
    'unity_SpecCube0_BoxMin',
    'unity_SpecCube0_HDR',
    'unity_SpecCube0_ProbePosition',
    'unity_SpecCube1_BoxMax',
    'unity_SpecCube1_BoxMin',
    'unity_SpecCube1_HDR',
    'unity_SpecCube1_ProbePosition',
    'unity_SpotDirection',
    'unity_StereoCameraInvProjection',
    'unity_StereoCameraProjection',
    'unity_StereoCameraToWorld',
    'unity_StereoEyeIndex',
    'unity_StereoMatrixInvV',
    'unity_StereoMatrixP',
    'unity_StereoMatrixV',
    'unity_StereoMatrixVP',
    'unity_StereoScaleOffset',
    'unity_StereoWorldSpaceCameraPos',
    'unity_StereoWorldToCamera',
    'unity_WorldToCamera',
    'unity_WorldToObject',
    'unity_WorldToShadow',
    'unity_WorldTransformParams',
}
DECLARATION = '\\b(in|out|uniform)\\s+(?:(?:highp|mediump|lowp)\\s+)?(\\w+)\\s+(\\w+)(?:\\[(\\d+)\\])?\\s*;'

VECTOR_COMPARISONS = {
    'lessThan': '<', 'lessThanEqual': '<=', 'greaterThan': '>', 'greaterThanEqual': '>=',
    'equal': '==', 'notEqual': '!=',
}


def translate_vector_constructors(source):
    pat = r'\b(vec[234]|[ibu]vec[234]|' + '|'.join(VECTOR_COMPARISONS) + r')\s*\('
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
    if t in VECTOR_COMPARISONS:
        if len(args) != 2:
            raise ValueError(f'Expected two operands for GLSL {t}')
        val = f'(({args[0]}) {VECTOR_COMPARISONS[t]} ({args[1]}))'
    elif len(args) == 1:
        val = f'(({VECTOR_TYPES[t]})({args[0]}))'
    else:
        val = VECTOR_TYPES[t] + '(' + ','.join(args) + ')'
    return source[:m.start()] + val + translate_vector_constructors(source[i + 1:])

def rewrite_calls(source, function, replacement):
    """Rewrite balanced GLSL calls without dropping optional sampling operands."""
    pattern = re.compile(r'\b' + re.escape(function) + r'\s*\(')
    cursor = 0
    while match := pattern.search(source, cursor):
        depth, start, arguments = 0, match.end(), []
        for end in range(start, len(source)):
            char = source[end]
            if char == '(':
                depth += 1
            elif char == ')':
                if depth == 0:
                    arguments.append(source[start:end])
                    break
                depth -= 1
            elif char == ',' and depth == 0:
                arguments.append(source[start:end])
                start = end + 1
        else:
            raise ValueError('Unbalanced GLSL call')
        value = replacement(arguments)
        if value is None:
            cursor = end + 1
        else:
            source = source[:match.start()] + value + source[end + 1:]
            cursor = match.start() + len(value)
    return source


def extract_helpers(source):
    """Keep generated GLSL helper bodies, including GLES2 dynamic-array access."""
    pattern = re.compile(r'(?:float|int|uint|bool|[biu]?vec[234])\s+\w+\s*\([^{};]*\)\s*\{')
    cursor = 0
    while match := pattern.search(source, cursor):
        depth = 1
        end = match.end()
        while end < len(source) and depth:
            depth += (source[end] == '{') - (source[end] == '}')
            end += 1
        if depth:
            raise ValueError('Unbalanced GLES helper body')
        yield source[match.start():end]
        cursor = end


def translate_program(raw):
    """Rebuild vertex and fragment entry points from one HLSLcc GLES2/GLES3 program."""
    if 'gl_InstanceID' in raw:
        return None
    vertex, frag = raw.split('#ifdef FRAGMENT', 1)
    parts = []
    uniforms = {}
    helpers = {}
    attributes = []
    varyings = []
    has_front_face = 'gl_FrontFacing' in frag
    for i, source in enumerate((vertex, frag)):
        # GLES2 uses attribute/varying instead of GLES3 in/out declarations.
        # Normalize only declaration qualifiers; preserve actual program math.
        source = re.sub(r'\battribute\s+', 'in ', source)
        source = re.sub(r'\bvarying\s+', 'out ' if i == 0 else 'in ', source)
        declarations = list(re.finditer(DECLARATION, source))
        before, body = source.split('void main()', 1)
        for helper in extract_helpers(before):
            translated = translate_vector_constructors(helper)
            for original, target in {**VECTOR_TYPES, 'dFdx': 'ddx', 'dFdy': 'ddy'}.items():
                translated = re.sub(r'\b' + original + r'\b', target, translated)
            translated = re.sub(r'\b(?:highp|mediump|lowp)\s+', '', translated)
            helpers[helper.split('{', 1)[0]] = translated
        body = body[body.index('{') + 1:body.rindex('}')]
        body = re.sub(r'\btexture(?:2D|Cube)LodEXT\b', 'textureLod', body)
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
                elif n.startswith('hlslcc_mtx4x4'):
                    native = n[len('hlslcc_mtx4x4'):]
                    if type_name != 'vec4' or not arr or int(arr) % 4:
                        raise ValueError('Unsupported flattened HLSLcc matrix uniform')
                    count = int(arr) // 4
                    if native not in BUILTIN_UNIFORMS:
                        uniforms[native] = 'float4x4 ' + native + (f'[{count}]' if count > 1 else '') + ';'
                    if count == 1:
                        body = re.sub(r'\b' + re.escape(n) + r'\b', 'transpose(' + native + ')', body)
                    else:
                        pattern = r'\b' + re.escape(n) + r'\[([^\[\]]+)\]'
                        body = re.sub(pattern, lambda m: 'transpose(' + native + '[(int)(' + m[1] + ')/4])[(int)(' + m[1] + ')%4]', body)
                        if re.search(r'\b' + re.escape(n) + r'\b', body):
                            raise ValueError('Unsupported nested flattened matrix index')
                elif type_name == 'sampler2DShadow':
                    native = '_' + n[len('hlslcc_zcmp_'):] if n.startswith('hlslcc_zcmp_') else n
                    uniforms[native] = 'UNITY_DECLARE_SHADOWMAP(' + native + ');'
                    def shadow_call(args):
                        if args[0].strip() != n:
                            return None
                        if len(args) == 3 and args[2].strip() not in ('0', '0.0', '0.0f'):
                            raise ValueError('Nonzero comparison-sampler LOD is unsupported')
                        if len(args) not in (2, 3):
                            raise ValueError('Unsupported shadow sample arity')
                        return 'UNITY_SAMPLE_SHADOW(' + native + ',' + args[1] + ')'
                    for call in ('texture', 'textureLod'):
                        body = rewrite_calls(body, call, shadow_call)
                elif n in ('unity_SpecCube0' ,'unity_SpecCube1','unity_Lightmap','unity_LightmapInd','unity_ShadowMask','unity_DynamicLightmap','unity_DynamicDirectionality','unity_DynamicNormal','unity_ProbeVolumeSH'):
                    dimension = 'CUBE' if type_name == 'samplerCube' else '3D' if type_name == 'sampler3D' else '2D'
                    macro = 'UNITY_SAMPLE_TEX' + dimension
                    body = re.sub(r'\btextureLod\s*\(\s*'+re.escape(n)+r'\s*,', macro+'_LOD('+n+',', body)
                    body = re.sub(r'\btexture(?:2D|Cube|3D)?\s*\(\s*'+re.escape(n)+r'\s*,', macro+'('+n+',', body)
                elif type_name in ('sampler2D','samplerCube'):
                    cube = type_name == 'samplerCube'
                    uniforms[n] = ('samplerCUBE' if cube else 'sampler2D') + ' ' + n + ';'
                    body = re.sub(r'\btextureLod\s*\(\s*'+re.escape(n)+r'\s*,', ('GreaCubeLod(' if cube else 'Grea2DLod(')+n+',', body)
                    body = re.sub(r'\btexture(?:2D|Cube|3D)?\s*\(\s*'+re.escape(n)+r'\s*,', ('GreaSampleCube(' if cube else 'GreaSample2D(')+n+',', body)
                elif n not in BUILTIN_UNIFORMS:
                    uniforms[n] = VECTOR_TYPES.get(type_name, type_name) + ' ' + n + (f'[{arr}]' if arr else '') + ';'
            elif kind == 'in':
                if i == 0:
                    attributes.append(f'{VECTOR_TYPES.get(type_name, type_name)} {n} : {n[3:]};')
                body = re.sub('\\b' + n + '\\b', ('v.' if i == 0 else 'i.') + n, body)
            elif kind == 'out':
                if i == 0:
                    varyings.append(f'{VECTOR_TYPES.get(type_name, type_name)} {n} : {n[3:]};')
                body = re.sub('\\b' + n + '\\b', 'o.' + n if i == 0 else 'result', body)
        if i == 1:
            body = re.sub(r'\b(?:SV_Target0|gl_FragColor)\b|gl_FragData\s*\[\s*0\s*\]', 'result', body)
        body = body.replace('gl_Position', 'o.pos').replace('gl_FrontFacing', 'front')
        body = translate_vector_constructors(body)
        body = re.sub('\\b(?:mediump|lowp|highp)\\s+', '', body)
        for x, y in {**VECTOR_TYPES, 'texture': 'tex2D', 'texture2D': 'tex2D', 'textureCube': 'texCUBE', 'fract': 'frac', 'inversesqrt': 'rsqrt', 'roundEven': 'round', 'dFdx': 'ddx', 'dFdy': 'ddy'}.items():
            body = re.sub('\\b' + x + '\\b', y, body)
        if i == 0:
            parts.append('Varyings vert(Attributes v){Varyings o=(Varyings)0;\n' + body + '\nreturn o;\n}')
        else:
            parts.append('float4 frag(Varyings i' + (',bool front:SV_IsFrontFace' if has_front_face else '') + ') : SV_Target {float4 result=0;\n' + body + '\nreturn result;\n}')
    for token, declaration in [
        ('GreaSample2D(', 'float4 GreaSample2D(sampler2D s,float2 uv){return tex2D(s,uv);}'
         'float4 GreaSample2D(sampler2D s,float2 uv,float bias){return tex2Dbias(s,float4(uv,0,bias));}'),
        ('GreaSampleCube(', 'float4 GreaSampleCube(samplerCUBE s,float3 uv){return texCUBE(s,uv);}'
         'float4 GreaSampleCube(samplerCUBE s,float3 uv,float bias){return texCUBEbias(s,float4(uv,bias));}')]:
        if any(token in block for block in parts):
            uniforms[token] = declaration
    for text, macro in [('Grea2DLod(', '#define Grea2DLod(s,uv,lod) tex2Dlod(s,float4(uv,0,lod))'),
                        ('GreaCubeLod(', '#define GreaCubeLod(s,uv,lod) texCUBElod(s,float4(uv,lod))')]:
        if any(text in block for block in parts):
            uniforms[text] = macro
    return '\n'.join([*uniforms.values(), *helpers.values()]) + '\nstruct Attributes {\n' + '\n'.join(attributes) + '\n};\nstruct Varyings {float4 pos:SV_POSITION;\n' + '\n'.join(varyings) + '\n};\n' + '\n'.join(parts)

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
    supported_subshaders = 0
    for sub in t['m_SubShaders']:
        # Serialized shaders retain subshaders stripped for this source GPU.
        # Unity selects the next supported subshader; do not discard its real fallback.
        available = any(p.get('m_Type') == 1 or any(v['m_GpuProgramType'] in (4, 5)
                        for group in p['progVertex']['m_PlayerSubPrograms'] for v in group)
                        for p in sub['m_Passes'])
        if not available:
            continue
        supported_subshaders += 1
        lines += ['SubShader {', tags(sub['m_Tags']), 'LOD ' + str(sub['m_LOD'])]
        for shader_pass in sub['m_Passes']:
            if shader_pass.get('m_Type') == 1:
                name_ref = shader_pass['m_UseName']
                if not name_ref or any(c in name_ref for c in '"\r\n'):
                    raise ValueError('Invalid serialized UsePass name')
                lines.append('UsePass "' + name_ref + '"')
                variant_counts.append(0)
                continue
            variants = {}
            programs = [v for group in shader_pass['progVertex']['m_PlayerSubPrograms'] for v in group]
            gpu_type = 4 if any(v['m_GpuProgramType'] == 4 for v in programs) else 5
            for g in shader_pass['progVertex']['m_PlayerSubPrograms']:
                for v in g:
                    if v['m_GpuProgramType'] != gpu_type:
                        continue
                    keys = tuple(sorted((t['m_KeywordNames'][k] for k in v['m_KeywordIndices'])))
                    if 'INSTANCING_ON' in keys:
                        continue
                    code = translate_program(read_program(v['m_BlobIndex']))
                    if code:
                        variants[keys] = code
            if not variants:
                raise ValueError('No non-instanced GLES program for ' + name)
            keywords = sorted(set.union(*(set(ks) for ks in variants)) - set.intersection(*(set(ks) for ks in variants)))
            lines += ['Pass {', *(['Name "' + shader_pass['m_State']['m_Name'] + '"'] if shader_pass['m_State']['m_Name'] else []), *renderstate(shader_pass['m_State']), 'HLSLPROGRAM', '#pragma target 3.5', '#pragma vertex vert', '#pragma fragment frag']
            shadowcaster = dict(shader_pass['m_State']['m_Tags']['tags']).get('LightMode') == 'ShadowCaster'
            shadow_keys = {'SHADOWS_DEPTH', 'SHADOWS_CUBE'} if shadowcaster else set()
            if set(keywords) & shadow_keys:
                lines += ['#pragma multi_compile_shadowcaster']
            exclusive = set()
            # A pass with exactly one of these keywords for every serialized program
            # has no keyword-free variant. Preserve that axis for native compilation.
            axes = [set(keywords), {'DIRECTIONAL', 'DIRECTIONAL_COOKIE', 'POINT', 'POINT_COOKIE', 'SPOT'}]
            for axis in axes:
                group = (axis & set(keywords)) - exclusive - shadow_keys
                if len(group)>1 and all(len(group & set(ks))==1 for ks in variants):
                    lines.append('#pragma multi_compile_local ' + ' '.join(sorted(group)))
                    exclusive.update(group)
            for k in keywords:
                if k not in exclusive and k not in shadow_keys:
                    lines += ['#pragma shader_feature_local __ ' + k]
            lines += ['#include "UnityCG.cginc"', '#include "UnityLightingCommon.cginc"']
            for j, (keys, code) in enumerate(variants.items()):
                lines += ['#' + ('if ' if j == 0 else 'elif ') + (' && '.join((('' if k in keys else '!') + 'defined(' + k + ')' for k in keywords)) or '1'), code]
            lines += ['#else', '#error Source_variant_unavailable', '#endif', 'ENDHLSL', '}']
            variant_counts.append(len(variants))
        lines += ['}']
    if not supported_subshaders:
        raise ValueError('No source GLES subshader in ' + name)
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


def extract_programs(shader, form):
    """Read only referenced GLES subprograms from Unity 2021 segmented blobs.

    Some entry zero records are sentinels, not GLSL. Reading arbitrary table
    entries can consume subsequent records and manufacture corrupt programs.
    """
    import struct
    from UnityPy.helpers import CompressionHelper
    from UnityPy.streams import EndianBinaryReader
    from UnityPy.export.ShaderConverter import ShaderSubProgram

    platforms = [int(p) for p in shader.platforms]
    platform = 9 if 9 in platforms else 5
    if platform not in platforms:
        raise ValueError('No GLES source platform in serialized shader')
    index = platforms.index(platform)
    gpu = 4 if platform == 9 else 5
    segments = [CompressionHelper.decompress_lz4(
        bytes(shader.compressedBlob[start:start + length]), size)
        for start, length, size in zip(shader.offsets[index],
                                      shader.compressedLengths[index],
                                      shader.decompressedLengths[index], strict=True)]
    if not segments or len(segments[0]) < 4:
        raise ValueError('Missing GLES subprogram table')
    table = segments[0]
    count = struct.unpack_from('<I', table)[0]
    if 4 + count * 12 > len(table):
        raise ValueError('Truncated GLES subprogram table')
    wanted = {v['m_BlobIndex'] for sub in form['m_SubShaders']
              for shader_pass in sub['m_Passes']
              for group in shader_pass['progVertex']['m_PlayerSubPrograms']
              for v in group if v['m_GpuProgramType'] == gpu}
    result = {}
    for index in sorted(wanted):
        if not 0 <= index < count:
            raise ValueError('GLES program index outside source table')
        offset, length, segment = struct.unpack_from('<III', table, 4 + index * 12)
        if segment >= len(segments) or offset + length > len(segments[segment]):
            raise ValueError('GLES subprogram outside source segment')
        reader = EndianBinaryReader(segments[segment][offset:offset + length], endian='<')
        program = ShaderSubProgram(reader)
        code = bytes(program.m_ProgramCode).decode('utf8').rstrip('\x00')
        if '#ifdef VERTEX' not in code or '#ifdef FRAGMENT' not in code:
            raise ValueError('Referenced subprogram lacks combined GLES source')
        result[index] = code
    return result
