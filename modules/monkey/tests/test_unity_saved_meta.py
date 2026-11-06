import hashlib
import unittest

from monkey.unity_saved_meta import SavedMetaVerificationError, verify_saved_meta


GUID = "0123456789abcdef0123456789abcdef"
SOURCE_META = b"""fileFormatVersion: 2
guid: 0123456789abcdef0123456789abcdef
NativeFormatImporter:
  externalObjects: {}
  mainObjectFileID: 11400000
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"""
SAVED_META = b"""fileFormatVersion: 2
guid: 0123456789abcdef0123456789abcdef
NativeFormatImporter:
  externalObjects: {}
  mainObjectFileID: 11400000
"""


def verify(source, saved):
    return verify_saved_meta(source, saved, hashlib.sha256(saved).hexdigest())


class UnitySavedMetaTests(unittest.TestCase):
    def test_unrelated_whitespace_comments_or_field_order_changes_are_rejected(self):
        for changed in (SAVED_META.replace(b'externalObjects: {}',b'externalObjects:  {}'),
                        SAVED_META+b'# comment added after save\n',
                        SAVED_META.replace(b'  externalObjects: {}\n  mainObjectFileID: 11400000\n',
                            b'  mainObjectFileID: 11400000\n  externalObjects: {}\n')):
            with self.subTest(changed=changed), self.assertRaisesRegex(SavedMetaVerificationError,'UNAPPROVED_BYTE_CHANGE'):
                verify(SOURCE_META,changed)

    def test_native_format_empty_metadata_omissions_pass_with_bounded_evidence(self):
        original = bytes(SOURCE_META)
        result = verify(SOURCE_META, SAVED_META)
        self.assertTrue(result["verified"])
        self.assertEqual(result["sourceSha256"], hashlib.sha256(SOURCE_META).hexdigest())
        self.assertEqual(result["savedSha256"], hashlib.sha256(SAVED_META).hexdigest())
        self.assertEqual(result["expectedSavedSha256"], result["savedSha256"])
        self.assertEqual(result["guid"], GUID)
        self.assertEqual(result["importerType"], "NativeFormatImporter")
        self.assertEqual(result["mainObjectFileID"], 11400000)
        self.assertEqual(result["allowedDiff"], [
            {"path": "NativeFormatImporter.assetBundleName", "omittedFrom": "saved", "value": None},
            {"path": "NativeFormatImporter.assetBundleVariant", "omittedFrom": "saved", "value": None},
            {"path": "NativeFormatImporter.userData", "omittedFrom": "saved", "value": None},
        ])
        self.assertEqual(SOURCE_META, original)

    def test_readback_sha_is_exact_and_required(self):
        with self.assertRaisesRegex(SavedMetaVerificationError, "SAVED_META_READBACK_SHA256_MISMATCH"):
            verify_saved_meta(SOURCE_META, SAVED_META, "0" * 64)
        with self.assertRaisesRegex(SavedMetaVerificationError, "SAVED_META_EXPECTED_SHA256_INVALID"):
            verify_saved_meta(SOURCE_META, SAVED_META, "not-a-sha")

    def test_nonempty_known_field_cannot_be_omitted(self):
        source = SOURCE_META.replace(b"userData: \n", b"userData: user authored data\n")
        with self.assertRaisesRegex(SavedMetaVerificationError, "SAVED_META_EFFECTIVE_FIELD_MISSING_OR_ADDED"):
            verify(source, SAVED_META)

    def test_addition_of_empty_known_field_is_not_an_allowed_normalization(self):
        with self.assertRaisesRegex(SavedMetaVerificationError, "SAVED_META_EFFECTIVE_FIELD_MISSING_OR_ADDED"):
            verify(SAVED_META, SOURCE_META)

    def test_nonempty_known_field_change_is_rejected(self):
        source = SOURCE_META.replace(b"userData: \n", b"userData: alpha\n")
        saved = SAVED_META.replace(b"mainObjectFileID: 11400000", b"mainObjectFileID: 11400000\n  userData: beta")
        with self.assertRaisesRegex(SavedMetaVerificationError, "SAVED_META_EFFECTIVE_FIELD_CHANGED"):
            verify(source, saved)

    def test_guid_importer_and_main_object_identity_changes_are_rejected(self):
        for source, saved, code in (
            (SOURCE_META, SAVED_META.replace(GUID.encode(), b"0" * 32), "SAVED_META_GUID_CHANGED"),
            (SOURCE_META, SAVED_META.replace(b"NativeFormatImporter", b"DefaultImporter"), "SAVED_META_IMPORTER_TYPE_CHANGED"),
            (SOURCE_META, SAVED_META.replace(b"11400000", b"11400001"), "SAVED_META_EFFECTIVE_FIELD_CHANGED"),
        ):
            with self.subTest(code=code), self.assertRaisesRegex(SavedMetaVerificationError, code):
                verify(source, saved)

    def test_unknown_schema_or_value_changes_are_rejected(self):
        changed = SAVED_META + b"  futureImporterField: 7\n"
        with self.assertRaisesRegex(SavedMetaVerificationError, "SAVED_META_EFFECTIVE_FIELD_MISSING_OR_ADDED"):
            verify(SOURCE_META, changed)
        changed = SAVED_META.replace(b"externalObjects: {}", b"externalObjects: {fileID: 5}")
        with self.assertRaisesRegex(SavedMetaVerificationError, "SAVED_META_EFFECTIVE_FIELD_"):
            verify(SOURCE_META, changed)

    def test_missing_or_invalid_guid_is_rejected(self):
        for source in (SOURCE_META.replace(b"guid: " + GUID.encode() + b"\n", b""),
                       SOURCE_META.replace(GUID.encode(), b"not-a-guid")):
            with self.subTest(source=source), self.assertRaisesRegex(SavedMetaVerificationError, "SAVED_META_GUID_MISSING_OR_INVALID"):
                verify(source, SAVED_META)

    def test_duplicate_yaml_keys_are_rejected_before_comparison(self):
        duplicate = SOURCE_META.replace(b"guid: " + GUID.encode(), b"guid: " + GUID.encode() + b"\nguid: " + GUID.encode())
        with self.assertRaisesRegex(SavedMetaVerificationError, "SAVED_META_DUPLICATE_KEY"):
            verify(duplicate, SAVED_META)

    def test_nested_mappings_and_sequence_fields_are_compared(self):
        source = b"""fileFormatVersion: 2
guid: 0123456789abcdef0123456789abcdef
TextureImporter:
  externalObjects: {fileID: 0}
  mainObjectFileID: 2800000
  platformSettings:
  - serializedVersion: 3
    buildTarget: DefaultTexturePlatform
    maxTextureSize: 2048
    overridden: 0
  userData: 
"""
        saved = source.replace(b"  userData: \n", b"")
        self.assertEqual(verify(source, saved)["allowedDiff"][0]["path"], "TextureImporter.userData")
        changed = saved.replace(b"maxTextureSize: 2048", b"maxTextureSize: 4096")
        with self.assertRaisesRegex(SavedMetaVerificationError, "SAVED_META_EFFECTIVE_FIELD_CHANGED"):
            verify(source, changed)

    def test_nested_lookalike_empty_field_is_not_allowed_to_disappear(self):
        source = SOURCE_META.replace(b"  externalObjects: {}", b"  externalObjects: {}\n  nested:\n    userData: \n")
        with self.assertRaisesRegex(SavedMetaVerificationError, "SAVED_META_EFFECTIVE_FIELD_MISSING_OR_ADDED"):
            verify(source, SAVED_META)

    def test_duplicate_document_or_unsupported_yaml_construct_is_rejected(self):
        source = b"---\n" + SOURCE_META + b"---\n" + SOURCE_META
        with self.assertRaises(SavedMetaVerificationError):
            verify(source, SAVED_META)
        tagged = SOURCE_META.replace(b"userData: \n", b"userData: &anchor value\n")
        with self.assertRaisesRegex(SavedMetaVerificationError, "SAVED_META_YAML_UNSUPPORTED_SCALAR"):
            verify(tagged, SAVED_META)


if __name__ == "__main__":
    unittest.main()
