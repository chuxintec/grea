"""Deterministic toneless Mandarin pinyin paths; source identifiers/content remain untouched."""
import re
import unicodedata
from functools import lru_cache
from pypinyin import lazy_pinyin, Style
from ..io import sha

ACRONYMS={'ui','hud','bgm','sfx','vfx','fx','npc','ai','id','vip','pvp','pve','sdk','2d','3d'}
_UNSAFE=re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_DEVICE=re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$',re.I)
SEGMENT_BYTES=64
HAN=re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U000323af]+')


@lru_cache(maxsize=32768)
def romanize(text):
    """Phrase-aware pinyin, no tones, v for ü; never mutate JSON keys or display strings."""
    text=unicodedata.normalize('NFC',text)
    def convert(match):
        syllables=lazy_pinyin(match.group(),style=Style.NORMAL,strict=True)
        if any(HAN.search(s) for s in syllables):
            raise ValueError('No pinyin reading for generated filename: '+match.group())
        before='_' if match.start() and text[match.start()-1].isalnum() else ''
        after='_' if match.end()<len(text) and text[match.end()].isalnum() else ''
        return before+''.join(s[:1].upper()+s[1:] for s in syllables)+after
    return HAN.sub(convert,text) if HAN.search(text) else text


def _kind(ch):
    if ch.isdigit() and ch.isascii():return 'digit'
    if ch.isascii() and ch.isalpha():return 'upper' if ch.isupper() else 'lower'
    return 'other'


def words(text):
    """Split on separators and case changes; letters and following digits stay together (Room7, Area01)."""
    out=[]
    for chunk in re.split(r'[_\-.\s]+',romanize(_UNSAFE.sub('_',str(text)))):
        current=''
        for i,ch in enumerate(chunk):
            if not current:current=ch;continue
            prev,kind=_kind(current[-1]),_kind(ch)
            nxt=_kind(chunk[i+1]) if i+1<len(chunk) else None
            split=(kind=='other')!=(prev=='other')
            split=split or (kind=='upper' and (prev=='lower' or prev=='digit' and nxt=='lower'))
            split=split or (kind=='upper' and prev=='upper' and nxt=='lower')
            if split:out.append(current);current=ch
            else:current+=ch
        if current:out.append(current)
    return out


def _cap(word):
    if word.lower() in ACRONYMS and word.isascii():return word.upper()
    return word[:1].upper()+word[1:] if word[:1].isascii() else word


def _joined(parts,separator):
    """Digit-only words attach to the previous word unless that word already ends with a digit."""
    out=[]
    for word in parts:
        if out and word.isdigit() and not out[-1][-1:].isdigit():out[-1]+=word
        elif out and word.isdigit():out[-1]+=(separator or '_')+word
        else:out.append(word)
    return separator.join(out)


def pascal(text):
    return _limit(_joined([_cap(w) for w in words(text)],'') or 'Unnamed')


def kebab(text):
    return _limit(_joined([w.lower() for w in words(text)],'-') or 'unnamed')


def snake(text):
    return _limit('_'.join(w.lower() for w in words(text)) or 'unnamed')


def _limit(value):
    if _DEVICE.match(value):value+='_'
    if len(value.encode())>SEGMENT_BYTES:
        raw=value.encode()[:SEGMENT_BYTES-7].decode('utf-8',errors='ignore')
        value=raw.rstrip('_-')+'_'+sha(value.encode())[:6]
    return value


def folder(text,engine):
    return pascal(text)


def safe_path(path):
    """Evidence paths use pinyin too; source spelling stays in the ledger, bytes stay exact."""
    parts=[]
    for part in str(path).split('/'):
        clean=_UNSAFE.sub('_',romanize(part)).rstrip(' .') if part not in ('','.','..') else '_'
        clean=clean or '_'
        if _DEVICE.match(clean.split('.')[0]):clean='_'+clean
        if len(clean.encode())>120:clean=clean.encode()[:100].decode('utf-8',errors='ignore')+'_'+sha(clean.encode())[:8]
        parts.append(clean)
    return '/'.join(parts)
