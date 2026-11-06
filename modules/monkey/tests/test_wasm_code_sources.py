import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from monkey.sources.compiled import ParseError
from monkey.wasm_code_semantics import recover_wasm_subset
from monkey.wasm_code_sources import inspect_wasm


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def uleb(value):
    out = bytearray()
    while True:
        byte = value & 0x7f
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def section(section_id, payload):
    return bytes((section_id,)) + uleb(len(payload)) + payload


def fixture_metadata():
    strings = bytearray()
    name_offsets = {}
    for value in ("FP", "BattleCore", "_serializedValue", "op_Addition"):
        name_offsets[value] = len(strings)
        strings.extend(value.encode("utf-8") + b"\0")
    field_row = struct.pack("<IiI", name_offsets["_serializedValue"], 41429, 0x04000001)
    method_row = struct.pack("<IiiiiIHHHH", name_offsets["op_Addition"], 0, 1, 0, -1,
                             0x06000001, 0, 0, 0, 2)
    # The v29 TypeDef row follows the local decoder's fixed 88-byte layout.
    type_values = (name_offsets["FP"], name_offsets["BattleCore"], 1, -1, -1, -1, -1, 0,
                   0, 0, 0, 0, 0, 0, 0, 0,
                   1, 0, 1, 0, 0, 0, 0, 0, 0, 0x02000001)
    type_row = struct.pack("<IIiiiiiIiiiiiiiiHHHHHHHHII", *type_values)
    header_size = 8 + 31 * 8
    data = bytearray(b"\0" * header_size)
    pairs = [(header_size, 0) for _ in range(31)]
    def append_table(index, raw):
        pairs[index] = (len(data), len(raw))
        data.extend(raw)
    append_table(2, bytes(strings))
    append_table(5, method_row)
    append_table(11, field_row)
    append_table(19, type_row)
    struct.pack_into("<II", data, 0, 0xFAB11BAF, 29)
    for index, pair in enumerate(pairs):
        struct.pack_into("<II", data, 8 + index * 8, *pair)
    return bytes(data)


def fixture_module():
    body = bytes.fromhex("00 20 00 20 01 7c 0f 0b")
    types = bytes.fromhex("01 60 03 7e 7e 7f 01 7e")
    functions = bytes.fromhex("01 00")
    code_payload = bytes((1, len(body))) + body
    wasm = b"\0asm\x01\0\0\0" + section(1, types) + section(3, functions) + section(10, code_payload)
    body_offset = wasm.index(body)
    body_record = {"functionIndex": 0, "offset": body_offset, "bytes": len(body), "sha256": sha(body)}
    index = {"schemaVersion": 1, "source": "segment-0.bin", "sha256": sha(wasm),
             "sections": [], "customSections": [], "importedFunctions": 0,
             "exports": [], "bodies": [body_record], "codeExecuted": False,
             "methodIdentity": "unresolved; function index alone is not CSharp method identity"}
    method_map = {"schemaVersion": 1, "method": "test fixture map", "tableSlots": 1,
                  "secondaryOverrides": 0,
                  "methods": [{"typeIndex": 0, "type": "BattleCore.FP", "method": "op_Addition",
                               "token": "0x06000001", "metadataMethodIndex": 0,
                               "signature": "public static FP op_Addition(FP x, FP y) { }",
                               "binding": {"segment": 0, "functionIndex": 0, "body": body_record}}],
                  "sourceCodeExecuted": False, "semantics": "fixture"}
    return wasm, body, index, method_map


class WasmCodeSourceTests(unittest.TestCase):
    def prepare_inputs(self, root):
        wasm, body, index, method_map = fixture_module()
        source = root / "module.wasm.br"
        segment = root / "segment-0.bin"
        metadata = root / "global-metadata.dat"
        index_path = root / "segment-0-index.json"
        map_path = root / "selected-method-map.json"
        source.write_bytes(wasm)
        segment.write_bytes(wasm)
        metadata.write_bytes(fixture_metadata())
        index_path.write_text(json.dumps(index, sort_keys=True) + "\n")
        map_path.write_text(json.dumps(method_map, sort_keys=True) + "\n")
        mapping = [{"segment": 0, "path": str(segment), "expected_sha256": sha(wasm),
                    "index_path": str(index_path), "expected_index_sha256": sha(index_path.read_bytes()),
                    "source_path": str(source), "source_sha256": sha(wasm)}]
        kwargs = {"expected_source_sha256": sha(wasm), "metadata": metadata,
                  "expected_metadata_sha256": sha(metadata.read_bytes()), "method_map": map_path,
                  "expected_method_map_sha256": sha(map_path.read_bytes()), "decoded_segments": mapping}
        return source, metadata, map_path, kwargs, body

    def test_exact_source_map_metadata_and_function_body_join_then_csharp_candidate(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            source, _, _, kwargs, body = self.prepare_inputs(root)
            inspection = inspect_wasm(source, root / "inspect", **kwargs)
            report = json.loads(Path(inspection["report"]).read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["exactBodySlices"], 1)
            self.assertFalse(report["wasmInstantiated"])
            self.assertTrue(report["methods"][0]["bodyEvidence"]["verifiedAgainstSegment"])
            self.assertEqual((Path(inspection["report"]).parent / report["methods"][0]["bodyEvidence"]["snapshot"]).read_bytes(), body)
            candidate = recover_wasm_subset(inspection, root / "candidate", selections=["BattleCore.FP::op_Addition"])
            code = Path(candidate["candidate"]).read_text(encoding="utf-8")
            self.assertIn("operator +(FP x, FP y)", code)
            self.assertIn("unchecked(x._serializedValue + y._serializedValue)", code)
            self.assertFalse(candidate["wasmInstantiated"])

    def test_pinned_report_change_and_body_change_fail_before_output(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root=Path(directory);source,_,_,kwargs,_=self.prepare_inputs(root)
            inspection=inspect_wasm(source,root/'inspect',**kwargs)
            path=Path(inspection['report']);pin=sha(path.read_bytes())
            path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaisesRegex(ParseError,'REPORT_CHANGED'):
                recover_wasm_subset({'report':str(path),'expectedSha256':pin},root/'changed',selections=['BattleCore.FP::op_Addition'])
            self.assertFalse((root/'changed').exists())
            report=json.loads(path.read_bytes());body=path.parent/report['methods'][0]['bodyEvidence']['snapshot'];body.write_bytes(body.read_bytes()+b'x')
            with self.assertRaisesRegex(ParseError,'BODY_CHANGED'):
                recover_wasm_subset({'report':str(path),'expectedSha256':sha(path.read_bytes())},root/'body-changed',selections=['BattleCore.FP::op_Addition'])
            self.assertFalse((root/'body-changed').exists())

    def test_mixed_revision_reports_and_duplicate_methods_are_rejected(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as directory:
            root=Path(directory);source,_,_,kwargs,_=self.prepare_inputs(root)
            inspection=inspect_wasm(source,root/'inspect',**kwargs)
            with self.assertRaisesRegex(ParseError,'METHOD_DUPLICATE'):
                recover_wasm_subset([inspection,inspection],root/'duplicate',selections=['BattleCore.FP::op_Addition'])
            report=json.loads(Path(inspection['report']).read_bytes());report['metadata']['sha256']='f'*64
            other=root/'other.json';other.write_text(json.dumps(report))
            with self.assertRaisesRegex(ParseError,'SOURCE_SET'):
                recover_wasm_subset([inspection,str(other)],root/'mixed',selections=['BattleCore.FP::op_Addition'])
            self.assertFalse((root/'duplicate').exists());self.assertFalse((root/'mixed').exists())

    def test_wrong_body_offset_fails_even_if_map_hash_is_recomputed(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            source, _, map_path, kwargs, _ = self.prepare_inputs(root)
            document = json.loads(map_path.read_text())
            document["methods"][0]["binding"]["body"]["offset"] += 1
            map_path.write_text(json.dumps(document, sort_keys=True) + "\n")
            kwargs["expected_method_map_sha256"] = sha(map_path.read_bytes())
            with self.assertRaisesRegex(ParseError, "WASM_CODE_BODY_BOUNDARY"):
                inspect_wasm(source, root / "bad-boundary", **kwargs)

    def test_metadata_token_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            source, _, map_path, kwargs, _ = self.prepare_inputs(root)
            document = json.loads(map_path.read_text())
            document["methods"][0]["token"] = "0x06000002"
            map_path.write_text(json.dumps(document, sort_keys=True) + "\n")
            kwargs["expected_method_map_sha256"] = sha(map_path.read_bytes())
            with self.assertRaisesRegex(ParseError, "WASM_CODE_METADATA_MAP_JOIN"):
                inspect_wasm(source, root / "bad-metadata-join", **kwargs)

    def test_compressed_source_link_must_match_mapping(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            source, _, _, kwargs, _ = self.prepare_inputs(root)
            kwargs["decoded_segments"][0]["source_sha256"] = "0" * 64
            with self.assertRaisesRegex(ParseError, "WASM_CODE_SOURCE_SEGMENT_LINK"):
                inspect_wasm(source, root / "bad-source-link", **kwargs)

    def test_explicit_brotli_provider_verifies_exact_bytes_and_reports_provider_hash(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            source, _, _, kwargs, _ = self.prepare_inputs(root)
            provider = root / "brotli-fixture"
            provider.write_text('#!/bin/sh\ncat "$3"\n', encoding="utf-8")
            provider.chmod(0o755)
            result = inspect_wasm(source, root / "verified", brotli_provider=provider, **kwargs)
            report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
            self.assertEqual(report["brotliDecode"]["status"], "verified_brotli_bytes")
            self.assertEqual(report["brotliDecode"]["provider"]["sha256"], sha(provider.read_bytes()))
            self.assertEqual(report["summary"]["sourceToDecoded"], "verified_brotli_bytes")
            self.assertEqual(report["methodMapAssociation"]["metadataMethodIndexToFunctionIndex"],
                             "caller-map; not independently verified")
            self.assertEqual(report["methods"][0]["metadataMethodToFunctionAssociation"],
                             "caller-map; codeRegistration not parsed")

    def test_explicit_brotli_provider_stops_on_output_overrun(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            root = Path(directory)
            source, _, _, kwargs, _ = self.prepare_inputs(root)
            provider = root / "brotli-overrun"
            provider.write_text('#!/bin/sh\ncat "$3"\nprintf x\n', encoding="utf-8")
            provider.chmod(0o755)
            with self.assertRaisesRegex(ParseError, "WASM_CODE_BROTLI_OUTPUT_BUDGET"):
                inspect_wasm(source, root / "overrun", brotli_provider=provider, **kwargs)


if __name__ == "__main__":
    unittest.main()
