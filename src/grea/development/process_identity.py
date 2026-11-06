"""Read-only macOS process identity and kernel argv/environment snapshot.

This module does not launch, attach to, signal, or load code into processes.
Arguments and environment are returned only to the direct caller; errors never
include their raw contents.
"""
from __future__ import annotations

import ctypes
import os
import struct
import sys

MAX_PROCARGS_BYTES = 4 * 1024 * 1024
MAX_ARGC = 65536
MAX_ENV_COUNT = 65536
MAX_VALUE_BYTES = 1024 * 1024
MAX_PID_BUFFER = 4 * 1024 * 1024
_KERN_PROCARGS2 = 49  # sys/sysctl.h (guarded by __APPLE_API_UNSTABLE)
_CTL_KERN = 1
_PROC_ALL_PIDS = 1  # sys/proc_info.h
_PROC_PIDTBSDINFO = 3
_PROC_PIDPATHINFO_MAXSIZE = 4096  # PROC_PIDPATHINFO_MAXSIZE = 4 * MAXPATHLEN


class _ProcBsdInfo(ctypes.Structure):
    _fields_ = [
        ("pbi_flags", ctypes.c_uint32), ("pbi_status", ctypes.c_uint32),
        ("pbi_xstatus", ctypes.c_uint32), ("pbi_pid", ctypes.c_uint32),
        ("pbi_ppid", ctypes.c_uint32), ("pbi_uid", ctypes.c_uint32),
        ("pbi_gid", ctypes.c_uint32), ("pbi_ruid", ctypes.c_uint32),
        ("pbi_rgid", ctypes.c_uint32), ("pbi_svuid", ctypes.c_uint32),
        ("pbi_svgid", ctypes.c_uint32), ("rfu_1", ctypes.c_uint32),
        ("pbi_comm", ctypes.c_char * 16), ("pbi_name", ctypes.c_char * 32),
        ("pbi_nfiles", ctypes.c_uint32), ("pbi_pgid", ctypes.c_uint32),
        ("pbi_pjobc", ctypes.c_uint32), ("e_tdev", ctypes.c_uint32),
        ("e_tpgid", ctypes.c_uint32), ("pbi_nice", ctypes.c_int32),
        ("pbi_start_tvsec", ctypes.c_uint64), ("pbi_start_tvusec", ctypes.c_uint64),
    ]


def _unknown(pid):
    return {"status":"unknown","pid":pid,"ppid":None,"executablePath":None,
            "uniqueId":None,"birthIdentitySource":"PROC_PIDTBSDINFO",
            "startTime":None,"arguments":None,"environment":None}


def _missing(pid):
    return {"status":"missing","pid":pid,"ppid":None,"executablePath":None,
            "uniqueId":None,"birthIdentitySource":"PROC_PIDTBSDINFO",
            "startTime":None,"arguments":None,"environment":None}


def _decode_cstring(data, pos, limit):
    if pos < 0 or pos >= limit:
        raise ValueError("missing NUL-terminated process argument")
    end=data.find(b"\0",pos,limit)
    if end<0 or end-pos>MAX_VALUE_BYTES:
        raise ValueError("unterminated or oversized process argument")
    return data[pos:end],end+1


def _parse_procargs2(data: bytes):
    """Parse KERN_PROCARGS2 bytes: argc, exec path, argv, then KEY=VALUE env."""
    if not isinstance(data,bytes) or len(data)<5 or len(data)>MAX_PROCARGS_BYTES:
        raise ValueError("invalid KERN_PROCARGS2 buffer size")
    argc=struct.unpack_from("=i",data,0)[0]
    if argc<1 or argc>MAX_ARGC:
        raise ValueError("invalid KERN_PROCARGS2 argc")
    exec_path,pos=_decode_cstring(data,4,len(data))
    if not exec_path:
        raise ValueError("missing process exec path")
    # The kernel inserts NUL padding between exec_path and argv.
    while pos<len(data) and data[pos]==0: pos+=1
    args=[]
    for _ in range(argc):
        raw,pos=_decode_cstring(data,pos,len(data))
        args.append(os.fsdecode(raw))
    env={};count=0
    while pos<len(data):
        raw,pos=_decode_cstring(data,pos,len(data))
        if not raw: continue
        count+=1
        if count>MAX_ENV_COUNT: raise ValueError("environment entry budget exceeded")
        if b"=" not in raw: raise ValueError("malformed environment entry")
        key,value=raw.split(b"=",1)
        if not key: raise ValueError("empty environment key")
        decoded_key=os.fsdecode(key)
        if decoded_key in env: raise ValueError("duplicate environment key")
        env[decoded_key]=os.fsdecode(value)
    return args,env


def _darwin_api():
    libproc=ctypes.CDLL("/usr/lib/libproc.dylib",use_errno=True)
    libproc.proc_pidinfo.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_uint64,ctypes.c_void_p,ctypes.c_int]
    libproc.proc_pidinfo.restype=ctypes.c_int
    libproc.proc_pidpath.argtypes=[ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32]
    libproc.proc_pidpath.restype=ctypes.c_int
    libproc.proc_listpids.argtypes=[ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p,ctypes.c_int]
    libproc.proc_listpids.restype=ctypes.c_int
    libc=ctypes.CDLL(None,use_errno=True)
    libc.sysctl.argtypes=[ctypes.POINTER(ctypes.c_int),ctypes.c_uint,ctypes.c_void_p,
                          ctypes.POINTER(ctypes.c_size_t),ctypes.c_void_p,ctypes.c_size_t]
    libc.sysctl.restype=ctypes.c_int
    return libproc,libc


def _bsd(libproc,pid):
    info=_ProcBsdInfo()
    size=ctypes.sizeof(info)
    got=libproc.proc_pidinfo(pid,_PROC_PIDTBSDINFO,0,ctypes.byref(info),size)
    if got!=size or info.pbi_pid!=pid:
        return None
    sec=int(info.pbi_start_tvsec);usec=int(info.pbi_start_tvusec)
    if sec<=0 or not 0<=usec<1_000_000: return None
    return int(info.pbi_ppid),(sec,usec)


def _pid_exists(libproc,pid):
    pids=_list_pids(libproc)
    return None if pids is None else pid in pids


def _list_pids(libproc):
    """Return a complete PID snapshot or None; never use process text tools."""
    needed=libproc.proc_listpids(_PROC_ALL_PIDS,0,None,0)
    if needed<=0 or needed>MAX_PID_BUFFER: return None
    capacity=min(MAX_PID_BUFFER,needed+4096)
    buf=ctypes.create_string_buffer(capacity)
    got=libproc.proc_listpids(_PROC_ALL_PIDS,0,buf,capacity)
    if got<=0 or got>=capacity or got%ctypes.sizeof(ctypes.c_int): return None
    pids=struct.unpack_from("="+"i"*(got//ctypes.sizeof(ctypes.c_int)),buf.raw,0)
    clean=[pid for pid in pids if pid>0]
    if len(clean)!=len(set(clean)): return None
    return clean


def _path(libproc,pid):
    buf=ctypes.create_string_buffer(_PROC_PIDPATHINFO_MAXSIZE)
    got=libproc.proc_pidpath(pid,buf,len(buf))
    if got<=0 or got>=len(buf): return None
    raw=buf.raw[:got].split(b"\0",1)[0]
    if not raw: return None
    return os.fsdecode(raw)


def _procargs(libc,pid):
    mib=(ctypes.c_int*3)(_CTL_KERN,_KERN_PROCARGS2,pid)
    size=ctypes.c_size_t(0)
    if libc.sysctl(mib,3,None,ctypes.byref(size),None,0)!=0: return None
    if size.value<5 or size.value>MAX_PROCARGS_BYTES: return None
    buf=ctypes.create_string_buffer(size.value)
    actual=ctypes.c_size_t(size.value)
    if libc.sysctl(mib,3,ctypes.cast(buf,ctypes.c_void_p),ctypes.byref(actual),None,0)!=0:
        return None
    if actual.value<5 or actual.value>size.value: return None
    try: return _parse_procargs2(buf.raw[:actual.value])
    except (ValueError,UnicodeError): return None


def snapshot(pid: int) -> dict:
    """Return a bounded birth-identity snapshot for a live Darwin process.

    Non-Darwin platforms report ``unknown``. ``missing`` is used only after the
    kernel process list confirms that the requested PID is absent. Kernel/API
    access failures, PID races and inconsistent repeated argv/env/path reads
    report ``unknown`` without exposing diagnostic text.
    """
    if type(pid) is not int or not 1<=pid<=0x7fffffff:
        raise ValueError("pid must be a positive 32-bit process id")
    if sys.platform!="darwin": return _unknown(pid)
    try:
        libproc,libc=_darwin_api()
        first=_bsd(libproc,pid)
        if first is None:
            exists=_pid_exists(libproc,pid)
            return _unknown(pid) if exists is None or exists else _missing(pid)
        path1=_path(libproc,pid);procargs1=_procargs(libc,pid)
        path2=_path(libproc,pid);procargs2=_procargs(libc,pid)
        second=_bsd(libproc,pid)
        if first is None or second is None or first!=second or path1 is None or path1!=path2 or procargs1 is None or procargs1!=procargs2:
            return _unknown(pid)
        ppid,start=first;args,env=procargs1
        unique=f"{pid}:{start[0]}:{start[1]}"
        return {"status":"verified","pid":pid,"ppid":ppid,"executablePath":path1,
                "uniqueId":unique,"birthIdentitySource":"PROC_PIDTBSDINFO",
                "startTime":[start[0],start[1]],"arguments":args,"environment":env}
    except (OSError,AttributeError,TypeError,ValueError,OverflowError):
        return _unknown(pid)


def list_executables() -> dict:
    """List kernel-reported PIDs with kernel executable paths on Darwin.

    No argv or environment is read. Any PID whose path cannot be observed is
    included in ``inaccessiblePids`` and makes overall coverage ``unknown``.
    A failed or truncated PID-list query returns unknown with an empty result.
    """
    if sys.platform!="darwin": return {"status":"unknown","processes":[],"inaccessiblePids":[]}
    try:
        libproc,_=_darwin_api()
        pids=_list_pids(libproc)
        if pids is None: return {"status":"unknown","processes":[],"inaccessiblePids":[]}
        processes=[];inaccessible=[]
        for pid in pids:
            path=_path(libproc,pid)
            if path is None: inaccessible.append(pid)
            else: processes.append({"pid":pid,"executablePath":path})
        status="verified" if not inaccessible else "unknown"
        return {"status":status,"processes":processes,"inaccessiblePids":inaccessible}
    except (OSError,AttributeError,TypeError,ValueError,OverflowError):
        return {"status":"unknown","processes":[],"inaccessiblePids":[]}
