import unittest

from monkey.shader_content import classify


class ShaderContentTests(unittest.TestCase):
    def test_shaderlab_and_hlsl_sources_are_candidates_only(self):
        shaderlab = b'Shader "Example/Lit" { SubShader { Pass { HLSLPROGRAM\nfloat4 vert() { return 0; }\nENDHLSL } } }'
        result = classify(shaderlab, ".shader")
        self.assertEqual((result["classification"], result["dialect"]), ("source-text", "ShaderLab"))
        hlsl = b"Texture2D tex; float4 main(float2 uv : TEXCOORD0) { return 0; }"
        self.assertEqual(classify(hlsl, ".bytes")["dialect"], "HLSL")
        self.assertIn("unverified", classify(hlsl, ".bytes")["evidence"][0]["message"])

    def test_glsl_version_and_function_are_source_structure(self):
        source=b'#version 330 core\nlayout(location=0) out vec4 color;\nvoid main(){color=vec4(1);}'
        self.assertEqual(classify(source,'.frag')['dialect'],'GLSL')

    def test_recovered_dump_markers_override_shader_suffix(self):
        raw = b"Shader \"Dump\" { SubProgram \"gles\" { GpuProgramIndex 0 } }"
        result = classify(raw, ".shader")
        self.assertEqual(result["classification"], "recovered-binary")
        self.assertEqual(result["evidence"][0]["code"], "RECOVERED_PROGRAM_DUMP")

    def test_comments_and_string_literals_cannot_create_shader_structure_or_dump(self):
        raw = b'// Shader "Fake" { SubShader { Program } }\nconst char* s = "Shader \\\"Nope\\\" { SubProgram }";'
        result = classify(raw, ".shader")
        self.assertEqual(result["classification"], "unknown")

    def test_serialized_unity_shader_blob_is_compiled_data_with_raw_platform_ids(self):
        raw = b"""%YAML 1.1
--- !u!48 &4800000
Shader:
  platforms: 0100000002000000
  compressedBlob: ABCD
"""
        result = classify(raw, ".asset")
        self.assertEqual(result["classification"], "platform-compiled")
        self.assertEqual(result["platforms"], [1, 2])
        self.assertEqual(result["evidence"][0]["code"], "UNITY_SHADER_COMPILED_DATA")

    def test_unity_shader_without_compiled_data_is_recovered_binary(self):
        result = classify(b"--- !u!48 &1\nShader:\n  m_Name: recovered\n", ".shader")
        self.assertEqual(result["classification"], "recovered-binary")

    def test_signature_only_and_truncated_binary_evidence(self):
        self.assertEqual(classify(b"DXBC" + bytes(40), ".bin")["classification"], "platform-compiled")
        damaged = classify(b"DXBC", ".bin")
        self.assertEqual(damaged["classification"], "unknown")
        self.assertEqual(damaged["evidence"][0]["code"], "TRUNCATED_BINARY_SIGNATURE")

    def test_damaged_or_incomplete_source_is_not_promoted(self):
        valid=b'Shader "T" { SubShader { Pass { HLSLPROGRAM\nfloat4 f(){return 0;}\nENDHLSL } } }'
        for raw in [b'\xff'+valid,b'\0'+valid,valid[:-1],b'Shader "T" { SubShader {} }',b'/* '+valid]:
            with self.subTest(raw=raw[:20]):self.assertNotEqual(classify(raw,'.shader')['classification'],'source-text')
        source=b'Texture2D t; float4 Program(float2 p){return 0;}'
        self.assertEqual(classify(source,'.hlsl')['classification'],'source-text')

    def test_unknown_and_unsupported_types_remain_distinct(self):
        self.assertEqual(classify(b"just some text", ".shader")["classification"], "unknown")
        self.assertEqual(classify(b"{}", ".shadergraph")["classification"], "unsupported")
        collection = classify(b"--- !u!200 &1\nShaderVariantCollection:\n", ".asset")
        self.assertEqual(collection["classification"], "unsupported")


if __name__ == "__main__":
    unittest.main()
