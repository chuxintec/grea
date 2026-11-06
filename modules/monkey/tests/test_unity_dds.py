import struct
import unittest
from unittest.mock import patch

from monkey.sources.unity_dds import DdsDependencyError, decode_dds_dxt5


def dds(width=4, height=4, *, flags=0x81007, mipmaps=0, fourcc=b"DXT5",
        pf_flags=4, caps2=0, depth=0, linear=None, payload=None):
    blocks = ((width + 3) // 4) * ((height + 3) // 4)
    if payload is None:
        # BC3 alpha 255 for every texel; RGB565 red for every texel.
        block = bytes((255, 0)) + bytes(6) + struct.pack("<HHI", 0xF800, 0x07E0, 0)
        payload = block * blocks
    declared_linear = len(payload) if linear is None else linear
    header = bytearray(124)
    struct.pack_into("<7I", header, 0, 124, flags, height, width,
                     declared_linear, depth, mipmaps)
    struct.pack_into("<2I", header, 72, 32, pf_flags)
    header[80:84] = fourcc
    struct.pack_into("<5I", header, 104, 0x1000, caps2, 0, 0, 0)
    return b"DDS " + bytes(header) + payload


class UnityDdsTests(unittest.TestCase):
    def test_dispatch_uses_actual_cache_family_and_reports_missing_astc_dependency(self):
        from monkey.sources.unity_worker import decode_cached_texture
        rgba,proof=decode_cached_texture(dds(),4,4,hint=5,kind='dds')
        self.assertEqual(rgba,bytes((255,0,0,255))*16)
        self.assertEqual(proof['dds']['fourcc'],'DXT5')
        self.assertEqual(proof['normalization'],'DDS-DXT5-to-RGBA-no-flip-v1')
        # A DDS payload must not be mislabelled or sent to the ASTC decoder.
        with self.assertRaises(ValueError):decode_cached_texture(dds(),4,4,kind='astc')
        astc=bytes.fromhex('13aba15c')+bytes([4,4,1,4,0,0,4,0,0,1,0,0])+bytes(16)
        with patch.dict('sys.modules',{'texture2ddecoder':None}),self.assertRaisesRegex(ImportError,'texture2ddecoder==1.0.6'):
            decode_cached_texture(astc,4,4,kind='astc')

    def test_decodes_synthetic_dxt5_color_and_alpha(self):
        rgba, descriptor = decode_dds_dxt5(dds(), 4, 4)
        self.assertEqual(rgba, bytes((255, 0, 0, 255)) * 16)
        self.assertEqual(descriptor, dict(format="DDS", fourcc="DXT5", width=4,
                                          height=4, payloadBytes=16,
                                          decoder="Pillow12.2.0"))

    def test_astc_wrong_decoder_version_has_dependency_version_diagnostic(self):
        from monkey.sources.unity_worker import decode_cached_texture
        astc=bytes.fromhex('13aba15c')+bytes([4,4,1,4,0,0,4,0,0,1,0,0])+bytes(16)
        with patch.dict('sys.modules',{'texture2ddecoder':object()}),patch('importlib.metadata.version',return_value='1.0.5'),self.assertRaises(ImportError) as caught:
            decode_cached_texture(astc,4,4,kind='astc')
        self.assertEqual(caught.exception.code,'DEPENDENCY_VERSION')

    def test_decodes_non_block_aligned_single_level_dimensions(self):
        rgba, descriptor = decode_dds_dxt5(dds(5, 3), 5, 3)
        self.assertEqual(len(rgba), 5 * 3 * 4)
        self.assertEqual(descriptor["payloadBytes"], 32)

    def test_rejects_truncated_or_extra_payload_before_pillow(self):
        for raw in (dds()[:-1], dds() + b"x", b"DDS "):
            with self.subTest(length=len(raw)), patch("monkey.sources.unity_dds.version") as get_version:
                with self.assertRaises(ValueError):
                    decode_dds_dxt5(raw, 4, 4)
                get_version.assert_not_called()

    def test_rejects_dimensions_pixel_budget_and_bad_header(self):
        for args, raw in [((5, 4), dds()), ((4097, 4097), dds(4097, 4097, payload=b"")),
                          ((4, 4), dds(flags=0x80007)),
                          ((4, 4), dds(flags=0x1000)),
                          ((4, 4), dds(flags=0x881007, depth=1)),
                          ((4, 4), dds(fourcc=b"DX10")),
                          ((4, 4), dds(pf_flags=0)),
                          ((4, 4), dds(mipmaps=2)),
                          ((4, 4), dds(caps2=0x200)),
                          ((4, 4), dds(depth=2)),
                          ((4, 4), dds(flags=0x81007, linear=15))]:
            with self.subTest(args=args, raw=raw[80:88]):
                with self.assertRaises(ValueError):
                    decode_dds_dxt5(raw, *args)

    def test_pillow_dependency_is_pinned_and_reported(self):
        with patch("monkey.sources.unity_dds.version", return_value="12.1.0"):
            with self.assertRaisesRegex(DdsDependencyError, "Pillow==12.2.0"):
                decode_dds_dxt5(dds(), 4, 4)
        with patch("monkey.sources.unity_dds.version", side_effect=__import__(
                "importlib.metadata").metadata.PackageNotFoundError("Pillow")):
            with self.assertRaises(DdsDependencyError):
                decode_dds_dxt5(dds(), 4, 4)


if __name__ == "__main__":
    unittest.main()
