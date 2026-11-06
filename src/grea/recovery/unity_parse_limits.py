"""Versioned, bounded parser policy and complete reader implementation identity."""
import hashlib
from pathlib import Path

DEFAULT_OBJECT_VALUES=250_000
DEFAULT_CONTAINER_VALUES=8_000_000
MAX_DOCUMENT_BYTES=128*1024**2
MAX_DOCUMENT_NODES=64_000_000


def parse_limits(value=None):
    value=value or {}
    if not isinstance(value,dict) or set(value)-{'objectValues','containerValues'}:
        raise ValueError('Expected objectValues/containerValues parse limits')
    result=dict(objectValues=value.get('objectValues',DEFAULT_OBJECT_VALUES),containerValues=value.get('containerValues',DEFAULT_CONTAINER_VALUES))
    for key,maximum in [('objectValues',1_000_000),('containerValues',16_000_000)]:
        if type(result[key]) is not int or not 1<=result[key]<=maximum:raise ValueError(key+' limit must be 1..'+str(maximum))
    return result


def reader_fingerprint():
    root=Path(__file__).parent;h=hashlib.sha256()
    for name in ('sources/unity_worker.py','sources/unity_dds.py','unity_texture_selection.py','unity_parse_limits.py','unity_payloads.py','unity_semantics.py'):
        h.update(name.encode()+b'\0');h.update((root/name).read_bytes())
    return h.hexdigest()
