"""Bounded, hash-verified evidence streams; never import source programs."""
from contextlib import contextmanager
import codecs
import hashlib
import json
import os
import re
import stat
import unicodedata
import zipfile
from .io import safe, load
from .owned_fs import RootReader
from .output_limits import FILE_BYTES, WHOLE_BYTES, WHOLE_FILES
from .sources.containers import relative
from .sources.compiled import fail

CHUNK = 65536
ROW_BYTES = 8 * 1024**2
MAX_ROWS = 2_000_000


def checksum(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):
        fail('EVIDENCE_HASH','$','Expected an exact lowercase SHA256')
    return value


def zip_index(archive):
    rows=archive.infolist()
    if len(rows)>WHOLE_FILES:fail('ARCHIVE_BUDGET','$','Too many archive entries')
    files={};folded=set();parents=set();total=0
    for row in rows:
        name=relative(row.filename.rstrip('/'));kind=stat.S_IFMT(row.external_attr >> 16)
        if kind not in (0,stat.S_IFREG,stat.S_IFDIR) or row.flag_bits & 1:
            fail('UNSAFE_ARCHIVE_ENTRY',name,'Linked, special or encrypted entry')
        if len(name.split('/'))>64:fail('ARCHIVE_BUDGET',name,'Archive path too deep')
        if row.is_dir():continue
        key=unicodedata.normalize('NFC',name).casefold();parts=key.split('/')
        ancestors={'/'.join(parts[:i]) for i in range(1,len(parts))}
        if key in folded or key in parents or ancestors & folded:
            fail('ARCHIVE_COLLISION',name,'Duplicate, case or path-prefix collision')
        folded.add(key);parents.update(ancestors);files[name]=row;total+=row.file_size
        if row.file_size>FILE_BYTES or total>WHOLE_BYTES:
            fail('ARCHIVE_BUDGET',name,'Archive expanded-byte budget exceeded')
    return files


class VerifiedStream:
    def __init__(self,stream,size,expected,source,selection=None):
        if not 0<=size<=FILE_BYTES:fail('EVIDENCE_BUDGET',source,'Selected evidence exceeds file budget')
        self.stream=stream;self.size=size;self.expected=checksum(expected)
        self.digest=hashlib.sha256();self.count=0;self.verified=False;self.source=source
        self.selection=selection or dict(kind='file')

    def read(self,n=CHUNK):
        raw=self.stream.read(min(n,CHUNK));self.count+=len(raw)
        if self.count>self.size:fail('EVIDENCE_DRIFT',self.source,'Evidence grew beyond its declared size')
        self.digest.update(raw)
        if not raw:
            if self.count!=self.size or self.digest.hexdigest()!=self.expected:
                fail('EVIDENCE_DRIFT',self.source,'Evidence bytes/SHA differ from the frozen identity')
            self.verified=True
        return raw

    def identity(self):
        return dict(source=self.source,selection=self.selection,bytes=self.count,sha256=self.digest.hexdigest(),verified=self.verified)


@contextmanager
def opened(source,expected,member=None):
    path=safe(source);checksum(expected)
    with RootReader(path.parent) as root,root.open(path.name) as raw:
        size=os.fstat(raw.fileno()).st_size
        if size>WHOLE_BYTES:fail('ARCHIVE_BUDGET',str(path),'Source container exceeds 8GiB')
        if member is None:
            yield VerifiedStream(raw,size,expected,str(path))
        else:
            member=relative(member)
            with zipfile.ZipFile(raw) as archive:
                rows=zip_index(archive)
                if member not in rows:fail('EVIDENCE_MEMBER',member,'Exact archive member missing')
                with archive.open(rows[member]) as stream:
                    yield VerifiedStream(stream,rows[member].file_size,expected,str(path)+'!'+member,
                                         dict(kind='zip-member',container=str(path),member=member,containerHashVerified=False))


class JsonRows:
    """Strict JSON array/envelope iterator with bounded per-value buffering.

    Consumers must exhaust rows() before treating source identity as verified.
    It rejects missing delimiters, duplicate keys, trailing data and truncation.
    """
    def __init__(self,stream):
        self.stream=stream;self.text='';self.pos=0;self.eof=False
        self.utf8=codecs.getincrementaldecoder('utf-8-sig')();self.decoder=json.JSONDecoder()
        self.count=0

    def fill(self):
        if self.eof:return
        self.text=self.text[self.pos:];self.pos=0
        if len(self.text.encode('utf-8'))>ROW_BYTES:fail('EVIDENCE_ROW_BUDGET','$','Individual JSON value exceeds 8MiB')
        raw=self.stream.read(CHUNK);self.eof=not raw
        try:self.text+=self.utf8.decode(raw,final=self.eof)
        except UnicodeError:fail('EVIDENCE_UTF8','$','Invalid evidence UTF-8')

    def peek(self):
        while True:
            while self.pos<len(self.text) and self.text[self.pos] in ' \t\r\n':self.pos+=1
            if self.pos<len(self.text):return self.text[self.pos]
            if self.eof:return ''
            self.fill()

    def take(self,char):
        if self.peek()!=char:fail('EVIDENCE_JSON','$','Expected '+char)
        self.pos+=1

    def value(self):
        self.peek()
        while True:
            try:
                value,end=self.decoder.raw_decode(self.text,self.pos)
                if end==len(self.text) and not self.eof:self.fill();continue
                raw=self.text[self.pos:end].encode('utf-8');self.pos=end
                if len(raw)>ROW_BYTES:fail('EVIDENCE_ROW_BUDGET','$','Individual JSON value exceeds 8MiB')
                return load(raw,max_nodes=200000)
            except json.JSONDecodeError:
                if self.eof:fail('EVIDENCE_JSON','$','Malformed or truncated JSON evidence')
                self.fill()
            except (ValueError,UnicodeError,RecursionError):
                fail('EVIDENCE_JSON','$','Unsupported numeric, Unicode or nesting value')

    def array(self):
        self.take('[')
        if self.peek()==']':self.pos+=1;return
        while True:
            row=self.value();self.count+=1
            if self.count>MAX_ROWS:fail('EVIDENCE_ROW_BUDGET','$','Too many evidence rows')
            yield row
            end=self.peek()
            if end==']':self.pos+=1;return
            self.take(',')
            if self.peek()==']':fail('EVIDENCE_JSON','$','Trailing array comma')

    def rows(self,field=None):
        if field is None:
            yield from self.array()
        else:
            self.take('{');seen=set();found=False
            if self.peek()!='}':
                while True:
                    key=self.value()
                    if not isinstance(key,str) or key in seen:fail('EVIDENCE_JSON','$','Invalid or duplicate envelope key')
                    seen.add(key);self.take(':')
                    if len(seen)>1000:fail('EVIDENCE_ROW_BUDGET','$','Too many envelope metadata keys')
                    if key==field:found=True;yield from self.array()
                    else:self.value()
                    if self.peek()=='}':break
                    self.take(',')
                    if self.peek()=='}':fail('EVIDENCE_JSON','$','Trailing object comma')
            self.take('}')
            if not found:fail('EVIDENCE_JSON',field,'Required array field missing')
        if self.peek():fail('EVIDENCE_JSON','$','Trailing evidence data')
