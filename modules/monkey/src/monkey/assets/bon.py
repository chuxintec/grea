"""Bounded static BON tagged little-endian decoder; never executes source JS.

Independently implemented from the observed client and the read-only static-bon-reader
algorithm (docs/PROVENANCE.md). Binary/Date values need a typed JSON adapter.
"""
import math
import struct


class BonError(ValueError):
    pass


def decode(raw, *, max_nodes=2_000_000, max_depth=100):
    if len(raw)>64*1024*1024:raise BonError('BON byte budget exceeded')
    pos=0;strings=[];nodes=0
    def take(size):
        nonlocal pos
        if size<0 or pos+size>len(raw):raise BonError('Truncated BON')
        value=raw[pos:pos+size];pos+=size;return value
    def varint():
        value=0
        for shift in range(0,35,7):
            byte=take(1)[0]
            if shift==28 and byte>15:raise BonError('BON varint overflow')
            value|=(byte&127)<<shift
            if not byte&128:return value
        raise BonError('BON varint overflow')
    def value(depth=0):
        nonlocal nodes
        nodes+=1
        if nodes>max_nodes or depth>max_depth:raise BonError('BON node/depth budget exceeded')
        tag=take(1)[0]
        if tag==0:return None
        if tag in (1,2,3,4):
            fmt={1:'<i',2:'<q',3:'<f',4:'<d'}[tag]
            number=struct.unpack(fmt,take(struct.calcsize(fmt)))[0]
            if isinstance(number,float) and not math.isfinite(number):raise BonError('Non-finite BON number')
            return number
        if tag==5:
            try:text=take(varint()).decode('utf-8')
            except UnicodeError as error:raise BonError('Invalid BON UTF-8') from error
            strings.append(text);return text
        if tag==6:
            flag=take(1)[0]
            if flag not in (0,1):raise BonError('Invalid BON boolean')
            return bool(flag)
        if tag in (7,10):raise BonError('BON Binary/Date requires a typed JSON adapter')
        if tag in (8,9):
            count=varint();minimum=count*(2 if tag==8 else 1)
            if minimum>max_nodes-nodes or minimum>len(raw)-pos:raise BonError('BON container budget/truncation')
            if tag==9:return [value(depth+1) for _ in range(count)]
            result={}
            for _ in range(count):
                key=value(depth+1)
                if not isinstance(key,str):raise BonError('Non-string BON object key requires an adapter')
                if key in result:raise BonError('Duplicate BON object key')
                result[key]=value(depth+1)
            return result
        if tag==99:
            index=varint()
            if index>=len(strings):raise BonError('Invalid BON string reference')
            return strings[index]
        raise BonError('Unknown BON tag '+str(tag))
    result=value()
    if pos!=len(raw):raise BonError('Trailing BON bytes')
    if not isinstance(result,dict):raise BonError('Expected BON config object')
    return result
