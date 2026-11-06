import struct
import unittest
from monkey.assets.ttf import coverage,missing
from monkey.sources.compiled import ParseError


def sfnt(subtable,encoding=1):
    cmap=struct.pack('>HHHHI',0,1,3,encoding,12)+subtable
    maxp=struct.pack('>IH',0x10000,2)
    header=struct.pack('>IHHHH',0x10000,2,0,0,0)
    directory=struct.pack('>4sIII',b'cmap',0,44,len(cmap))+struct.pack('>4sIII',b'maxp',0,44+len(cmap),6)
    return header+directory+cmap+maxp


class TtfCoverageTests(unittest.TestCase):
    def test_unicode_bmp_and_astral_without_system_fallback(self):
        format4=struct.pack('>16H',4,32,0,4,4,1,0,65,65535,0,65,65535,65472,1,0,0)
        m=coverage(sfnt(format4));self.assertEqual(m['unicodeRanges'],[[65,65]])
        self.assertEqual(missing(m,'A中'),[ord('中')])
        format12=struct.pack('>HHIIIII',12,0,28,0,1,0x1f600,0x1f600)+struct.pack('>I',1)
        m=coverage(sfnt(format12,10));self.assertEqual(missing(m,'😀'),[])
    def test_corrupt_tables_and_overlapping_segments_rejected(self):
        with self.assertRaises(ParseError):coverage(b'not-a-font')
        sub=struct.pack('>16H',4,32,0,4,4,1,0,65,65,0,65,65,65472,65472,0,0)
        with self.assertRaises(ParseError):coverage(sfnt(sub))
        sub=struct.pack('>16H',4,32,0,4,4,1,0,65,65535,0,65,65535,65472,1,0,0)
        raw=bytearray(sfnt(sub));raw[20:24]=struct.pack('>I',999999)
        with self.assertRaises(ParseError):coverage(raw)

if __name__=='__main__':unittest.main()
