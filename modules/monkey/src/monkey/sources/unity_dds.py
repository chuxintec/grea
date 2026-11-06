"""Bounded decoder for explicitly identified Unity DDS DXT5 payloads."""

from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
import struct


class DdsDependencyError(ValueError):
    """The pinned DDS decoder is unavailable or has the wrong version."""

    def __init__(self, detail):
        self.code = "DEPENDENCY_VERSION" if detail.startswith("found ") else "DEPENDENCY_MISSING"
        super().__init__(f"DDS decoding requires Pillow==12.2.0 ({detail})")


_MAX_PIXELS = 16_777_216
_DDSD_LINEARSIZE = 0x80000


def decode_dds_dxt5(raw: bytes, width: int, height: int) -> tuple[bytes, dict]:
    """Decode one exact-size, single-level DDS/BC3 image to row-major RGBA bytes."""
    if not isinstance(raw, bytes) or len(raw) < 128:
        raise ValueError("Expected a DDS byte string with a complete 128-byte header")
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        raise ValueError("Width and height must be positive integers")
    if width * height > _MAX_PIXELS:
        raise ValueError("DDS pixel count exceeds the 16777216 pixel limit")

    if raw[:4] != b"DDS ":
        raise ValueError("Invalid DDS magic")
    header_size, flags, declared_height, declared_width = struct.unpack_from("<4I", raw, 4)
    pitch_or_linear, depth, mip_count = struct.unpack_from("<3I", raw, 20)
    pf_size, pf_flags = struct.unpack_from("<2I", raw, 76)
    fourcc = raw[84:88]
    caps2 = struct.unpack_from("<I", raw, 112)[0]

    if header_size != 124 or pf_size != 32:
        raise ValueError("Invalid DDS header or pixel format size")
    if flags & 0x1007 != 0x1007 or pf_flags & 0x4 == 0 or pf_flags & ~5 or fourcc != b"DXT5":
        raise ValueError("Only DDS FOURCC DXT5 (BC3) is supported")
    if declared_width != width or declared_height != height:
        raise ValueError("DDS dimensions must exactly match the requested dimensions")
    if mip_count not in (0, 1):
        raise ValueError("DDS mipmaps are unsupported")
    if caps2 != 0 or flags & 0x800000 or depth not in (0, 1):
        raise ValueError("DDS cubemaps and volume textures are unsupported")

    payload_bytes = ((width + 3) // 4) * ((height + 3) // 4) * 16
    if flags & _DDSD_LINEARSIZE and pitch_or_linear != payload_bytes:
        raise ValueError("DDS linear size does not match the DXT5 payload size")
    if len(raw) != 128 + payload_bytes:
        raise ValueError("DDS payload length must exactly match the DXT5 dimensions")

    try:
        installed = version("Pillow")
    except PackageNotFoundError as exc:
        raise DdsDependencyError("package not installed") from exc
    if installed != "12.2.0":
        raise DdsDependencyError(f"found {installed}")
    try:
        from PIL import Image
    except ImportError as exc:
        raise DdsDependencyError("Pillow import failed") from exc
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.format != "DDS" or image.size != (width, height):
                raise ValueError("Pillow did not identify the expected DDS image")
            rgba = image.convert("RGBA").tobytes()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Pillow could not decode this DDS/DXT5 payload") from exc
    if len(rgba) != width * height * 4:
        raise ValueError("Decoded DDS byte count does not match its dimensions")

    return rgba, dict(format="DDS", fourcc="DXT5", width=width, height=height,
                      payloadBytes=payload_bytes, decoder="Pillow12.2.0")
