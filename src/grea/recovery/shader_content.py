"""Conservative, content-first shader asset classification.

This module identifies source-like or compiled-looking content. It never
certifies that a shader is complete, valid, importable, or usable by a target.
"""

from __future__ import annotations

import re


_UNSUPPORTED_SUFFIXES = {".shadergraph", ".shadervariants"}
_BINARY_SIGNATURES = (
    (b"DXBC", "dxbc-signature"),
    (b"DXIL", "dxil-signature"),
    (b"\x03\x02\x23\x07", "spirv-signature"),
    (b"MTLB", "metallib-signature"),
)


def _evidence(code: str, message: str, **extra: object) -> dict:
    return {"code": code, "message": message, **extra}


def _result(classification: str, dialect: str | None = None, *,
            evidence: list[dict] | None = None, platforms: list[int | str] | None = None) -> dict:
    return {
        "classification": classification,
        "dialect": dialect,
        "evidence": evidence or [],
        "platforms": platforms or [],
    }


def _lexical_view(text: str) -> str:
    """Blank comments and quoted literals while retaining token boundaries."""
    pattern = re.compile(
        r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
        re.MULTILINE,
    )
    return pattern.sub(lambda match: "__STRING__" if match.group().startswith(('"', "'"))
                       else " " * len(match.group()), text)


def _serialized_platforms(text: str) -> list[int]:
    """Read only explicit little-endian hex platform byte arrays."""
    found: list[int] = []
    for match in re.finditer(r"(?im)^\s*(?:m_)?platforms\s*:\s*([^\r\n]+)", text):
        value = match.group(1).strip().strip('"\'')
        value = re.sub(r"[\s,\[\]{}]", "", value)
        value = value.removeprefix("0x")
        if value and re.fullmatch(r"(?:[0-9a-fA-F]{8})+", value):
            raw = bytes.fromhex(value)
            found.extend(int.from_bytes(raw[i:i + 4], "little") for i in range(0, len(raw), 4))
    return found


def _shaderlab_source(code: str) -> bool:
    # ShaderLab's shader name is a required quoted string, so check source text
    # directly around the token; comments and string contents were removed.
    shader = re.search(r"\bShader\s+__STRING__", code)
    subshader = re.search(r"\bSubShader\s*\{", code)
    program = re.search(r"\b(?:CGPROGRAM|HLSLPROGRAM|GLSLPROGRAM)\b", code)
    ends = re.search(r"\b(?:ENDCG|ENDHLSL|ENDGLSL)\b", code)
    balance = 0
    for char in code:
        if char == "{": balance += 1
        elif char == "}": balance -= 1
        if balance < 0: return False
    return bool(shader and subshader and program and ends and balance == 0)


def classify(raw: bytes, suffix: str) -> dict:
    """Classify shader bytes without asserting native compilation or validity."""
    suffix = (suffix or "").lower()
    if suffix and not suffix.startswith("."):
        suffix = "." + suffix
    if suffix in _UNSUPPORTED_SUFFIXES:
        return _result("unsupported", evidence=[_evidence(
            "UNSUPPORTED_ASSET_TYPE", "Recognized shader asset type is outside this content classifier.")])

    data = bytes(raw)
    # A signature is evidence only when enough bytes exist for a plausible
    # container header. Short/truncated data remains unknown.
    for signature, name in _BINARY_SIGNATURES:
        if data.startswith(signature):
            minimum = 20 if name == "spirv-signature" else 32
            if len(data) < minimum:
                return _result("unknown", evidence=[_evidence(
                    "TRUNCATED_BINARY_SIGNATURE", f"{name} signature is present but the payload is too short.")])
            return _result("platform-compiled", evidence=[_evidence(
                "BINARY_SIGNATURE_ONLY", f"Recognized {name} signature; completeness and usability are unverified.")])

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _result("unknown", evidence=[_evidence("INVALID_SOURCE_ENCODING", "UTF-8 source text could not be verified.")])
    if b"\x00" in data:
        return _result("unknown", evidence=[_evidence("BINARY_OR_DAMAGED_TEXT", "Content is not safely readable as shader source text.")])
    code = _lexical_view(text)

    serialized = text.lstrip().startswith(("%YAML", "--- !u!"))
    class48 = serialized and bool(re.search(r"^--- !u!48 &", text, re.M))
    class200 = serialized and bool(re.search(r"^--- !u!200 &", text, re.M))
    if class200:
        return _result("unsupported", evidence=[_evidence(
            "UNSUPPORTED_SHADER_VARIANT_COLLECTION", "Unity ShaderVariantCollection asset is outside this classifier.")])
    if class48:
        platforms = _serialized_platforms(text)
        has_blob = bool(re.search(r"(?m)^\s*(?:compressedBlob|m_CompressedBlob)\s*:\s*[0-9a-fA-F]{2}", code, re.I))
        has_program_table = bool(re.search(r"\b(?:m_)?(?:SubProgram|GpuProgramIndex|m_Program)\b", code))
        if has_blob or has_program_table:
            return _result("platform-compiled", evidence=[_evidence(
                "UNITY_SHADER_COMPILED_DATA", "Unity class 48 contains compiled-data fields; no compilation check performed.",
                compressedBlob=has_blob, programTable=has_program_table)], platforms=platforms)
        return _result("recovered-binary", evidence=[_evidence(
            "UNITY_SHADER_WITHOUT_COMPILED_BLOB", "Unity class 48 shader has no sufficient compiled-data field evidence.")], platforms=platforms)

    # Recovered disassembly/dump markers take precedence over source extensions.
    if any(marker in code for marker in ('"', "'", "/*", "*/")):
        return _result("unknown", evidence=[_evidence("UNTERMINATED_SOURCE_LEXEME", "Source comments or literals are incomplete.")])
    dump_markers = re.findall(r"\b(?:Program|SubProgram)\s+__STRING__\s*\{|\bGpuProgramIndex\s*(?::|[0-9])|!!\s*(?:GLES[0-9]*|SPIRV|METAL|DXBC)\b", code)
    if dump_markers:
        return _result("recovered-binary", evidence=[_evidence(
            "RECOVERED_PROGRAM_DUMP", "Program/subprogram dump markers indicate recovered binary text.",
            markers=sorted(set(item.strip() for item in dump_markers)))])

    if _shaderlab_source(code):
        return _result("source-text", "ShaderLab", evidence=[_evidence(
            "SHADERLAB_SOURCE_STRUCTURE", "ShaderLab source structure is present; compilation is unverified.")])

    hlsl = bool(re.search(r"\b(?:cbuffer|Texture\w*|SamplerState|SV_Target|SV_Position)\b", code)
                and re.search(r"\b(?:float|half|int|void)\w*(?:[1-4](?:x[1-4])?)?\s+\w+\s*\([^;{}]*\)\s*\{", code))
    glsl = bool(re.search(r"(?m)^\s*#\s*version\b|\b(?:precision\s+(?:lowp|mediump|highp)|gl_Position|gl_FragColor)\b", code)
                and re.search(r"\bvoid\s+main\s*\(\s*\)\s*\{", code))
    if hlsl or glsl:
        dialect = "HLSL" if hlsl else "GLSL"
        return _result("source-text", dialect, evidence=[_evidence(
            "SHADER_LANGUAGE_SOURCE_STRUCTURE", f"{dialect} source structure is present; compilation is unverified.")])

    return _result("unknown", evidence=[_evidence(
        "INSUFFICIENT_SHADER_CONTENT_EVIDENCE", "Content does not establish a supported shader source or binary classification.")])
