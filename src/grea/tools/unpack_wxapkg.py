#!/usr/bin/env python3
"""Unpack a plain wxapkg with boundary and payload-size validation."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path, PurePosixPath


def safe_relative_path(name: str) -> Path:
    value = PurePosixPath(name.lstrip("/"))
    if not value.parts or any(part in {"", ".", ".."} for part in value.parts):
        raise ValueError(f"unsafe package path: {name!r}")
    return Path(*value.parts)


def parse(blob: bytes) -> list[tuple[str, int, int, bytes]]:
    if len(blob) < 18 or blob[0] != 0xBE or blob[13] != 0xED:
        raise ValueError("not a plain wxapkg")
    index_size, payload_size = struct.unpack_from(">II", blob, 5)
    count = struct.unpack_from(">I", blob, 14)[0]
    position = 18
    rows: list[tuple[str, int, int, bytes]] = []
    for _ in range(count):
        if position + 4 > len(blob):
            raise ValueError("truncated filename length")
        name_size = struct.unpack_from(">I", blob, position)[0]
        position += 4
        name = blob[position : position + name_size].decode("utf-8")
        position += name_size
        if position + 8 > len(blob):
            raise ValueError("truncated file offset/size")
        offset, size = struct.unpack_from(">II", blob, position)
        position += 8
        end = offset + size
        if offset < 14 + index_size or end > len(blob):
            raise ValueError(f"invalid payload range for {name!r}: {offset}..{end}")
        rows.append((name, offset, size, blob[offset:end]))

    if position != 14 + index_size:
        raise ValueError(f"index boundary mismatch: {position} != {14 + index_size}")
    if sum(size for _, _, size, _ in rows) != payload_size:
        raise ValueError("declared payload size does not match entry total")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    rows = parse(args.input.read_bytes())
    manifest = []
    for name, offset, size, data in rows:
        relative = safe_relative_path(name)
        target = args.output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest.append({"name": name, "offset": offset, "bytes": size})
    (args.output / "_WXAPKG_INDEX.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"entries={len(rows)}")
    print(f"payload_bytes={sum(size for _, _, size, _ in rows)}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
