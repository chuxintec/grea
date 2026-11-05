"""Bounded plain-wxapkg/APK/directory readers. Input programs are never executed.

Plain wxapkg header/index semantics adapted from grea (MIT, see licenses).
"""
import hashlib
import stat
import struct
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath
from ..io import safe
from ..byte_budgets import BATCH_INPUT, PACKAGE_FILE, enforce
from .compiled import fail

MAX_FILES = 50000
MAX_FILE = PACKAGE_FILE
MAX_TOTAL = BATCH_INPUT
MAX_EXPANDED_ROOT = 1024**3
MAX_EXPLICIT_TOTAL = 8 * 1024 * 1024 * 1024
MAX_CONTAINER = 1024 * 1024 * 1024


def fingerprint(path):
    digest = hashlib.sha256()
    with safe(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def relative(name, wx=False):
    if wx and name.startswith('/') and not name.startswith('//'):
        name = name[1:]
    if (not name or len(name.encode('utf-8'))>4096 or '\\' in name or '\x00' in name or ':' in name
            or name.startswith('/') or any(p in ('','.','..') for p in name.split('/'))):
        fail('UNSAFE_ARCHIVE_PATH', str(name), 'Unsafe input entry')
    return PurePosixPath(name).as_posix()


class Names:
    def __init__(self, max_total=None, *, scope="batchInput"):
        self.scope = scope
        self.max_total = MAX_TOTAL if max_total is None else max_total
        if type(self.max_total) is not int or not 1 <= self.max_total <= MAX_EXPLICIT_TOTAL:
            fail('ARCHIVE_BUDGET',str(self.max_total),'Explicit byte budget must be an integer in 1..8GiB')
        self.files = set(); self.parents = set(); self.total = 0

    def add(self, name, size):
        key = unicodedata.normalize('NFC', name).casefold()
        parents = [str(p) for p in PurePosixPath(key).parents if str(p) != '.']
        if key in self.files or key in self.parents or any(p in self.files for p in parents):
            fail('ARCHIVE_COLLISION',name,'Duplicate/case-folded/path-prefix collision')
        enforce('packageFile', size, MAX_FILE, name, 'ARCHIVE_BUDGET', basis='expanded entry')
        enforce(self.scope, self.total + size, self.max_total, name, 'ARCHIVE_BUDGET', basis='cumulative expanded input')
        if len(self.files) >= MAX_FILES:
            fail('ARCHIVE_BUDGET', name, 'Input file count budget exceeded')
        self.files.add(key)
        self.parents.update(parents)
        self.total += size


def entries(source):
    """Yield (relative path, bytes); whole container identity is checked by caller."""
    source = safe(source); names = Names(MAX_EXPANDED_ROOT, scope='expandedRoot')
    if source.is_dir():
        pending = [source]; directories=0
        while pending:
            folder = pending.pop()
            directories+=1
            if directories>MAX_FILES or len(folder.relative_to(source).parts)>64:
                fail('ARCHIVE_BUDGET',str(folder),'Directory count/depth budget exceeded')
            for p in sorted(folder.iterdir(), reverse=True):
                safe(p)  # Reject all symlinks, including directory symlinks.
                if p.is_dir():
                    pending.append(p)
                    if len(pending)>MAX_FILES: fail('ARCHIVE_BUDGET',str(p),'Directory budget exceeded')
                elif p.is_file():
                    name = relative(p.relative_to(source).as_posix()); names.add(name,p.stat().st_size)
                    with p.open('rb') as stream: data = stream.read(MAX_FILE+1)
                    if len(data) != p.stat().st_size or len(data)>MAX_FILE:
                        fail('SOURCE_CHANGED',name,'Source changed or exceeded file budget')
                    yield name, data
                else:
                    fail('UNSUPPORTED_ENTRY',str(p),'Only regular files/directories are accepted')
        return
    enforce('physicalContainer', source.stat().st_size, MAX_CONTAINER, source, 'ARCHIVE_BUDGET', basis='archive file size')
    if source.suffix.lower() == '.apk':
        with zipfile.ZipFile(source) as archive:
            rows = archive.infolist()
            if len(rows)>MAX_FILES: fail('ARCHIVE_BUDGET',str(source),'Too many ZIP entries')
            for row in rows:
                relative(row.filename.rstrip('/'))
                mode = row.external_attr >> 16
                kind = stat.S_IFMT(mode)
                if kind not in (0,stat.S_IFREG,stat.S_IFDIR):
                    fail('UNSAFE_ARCHIVE_ENTRY',row.filename,'ZIP links/devices are rejected')
                if row.is_dir(): continue
                name=relative(row.filename); names.add(name,row.file_size)
                if row.flag_bits & 1: fail('ENCRYPTED_ARCHIVE',name,'Encrypted ZIP entries are unsupported')
                with archive.open(row) as stream: data = stream.read(MAX_FILE+1)
                if len(data)!=row.file_size or len(data)>MAX_FILE:
                    fail('ARCHIVE_SIZE_MISMATCH',name,'Expanded bytes differ from directory')
                yield name,data
        return
    if source.suffix.lower() != '.wxapkg':
        fail('UNSUPPORTED_CONTAINER',str(source),'Expected plain wxapkg, APK or a resource directory')
    with source.open('rb') as stream:
        header=stream.read(18)
        if len(header)!=18 or header[0]!=0xBE or header[13]!=0xED:
            fail('UNSUPPORTED_WXAPKG',str(source),'Not a supported plain wxapkg; encrypted data is not decrypted')
        index_size,payload_size=struct.unpack_from('>II',header,5)
        count=struct.unpack_from('>I',header,14)[0]
        boundary=14+index_size; total=source.stat().st_size
        if count>MAX_FILES or index_size<4 or boundary>total or payload_size!=total-boundary:
            fail('INVALID_WXAPKG',str(source),'Invalid index/count/payload boundary')
        rows=[]
        for _ in range(count):
            raw=stream.read(4)
            if len(raw)!=4: fail('INVALID_WXAPKG',str(source),'Truncated entry')
            size=struct.unpack('>I',raw)[0]
            if size>4096 or stream.tell()+size+8>boundary: fail('INVALID_WXAPKG',str(source),'Invalid name size')
            name=relative(stream.read(size).decode('utf-8'),wx=True)
            offset,length=struct.unpack('>II',stream.read(8)); names.add(name,length)
            if offset<boundary or offset+length>total: fail('INVALID_WXAPKG',name,'Payload range outside container')
            rows.append((name,offset,length))
        if stream.tell()!=boundary: fail('INVALID_WXAPKG',str(source),'Index boundary mismatch')
        cursor=boundary
        for name,offset,length in sorted(rows,key=lambda row:row[1]):
            if offset!=cursor: fail('INVALID_WXAPKG',name,'Overlapping payload or unaccounted gap')
            cursor+=length
        if cursor!=total: fail('INVALID_WXAPKG',str(source),'Unaccounted payload bytes')
        for name,offset,length in rows:
            stream.seek(offset); data=stream.read(length)
            if len(data)!=length: fail('SOURCE_CHANGED',name,'Container changed while reading')
            yield name,data
