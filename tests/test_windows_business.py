"""Two different payloads through the registered native path, plus corruption."""
import os,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from grea.runner import execute
from module_support import with_modules

def package(name,payload):
 raw=name.encode('utf-8');size=4+12+len(raw);offset=14+size
 return b'\xbe'+b'\0'*4+struct.pack('>II',size,len(payload))+b'\xed'+struct.pack('>I',1)+struct.pack('>I',len(raw))+raw+struct.pack('>II',offset,len(payload))+payload

@unittest.skipUnless(os.name=='nt','Native registered Windows wxapkg adapter')
class WindowsBusiness(unittest.TestCase):
 @with_modules
 def test_registered_unpack_handles_two_shapes_and_rejects_corruption(self):
  with tempfile.TemporaryDirectory(prefix='grea 中文 & ! () ') as tmp:
   root=Path(tmp)
   home=root/'isolated home';home.mkdir()
   env={'HOME':str(home),'USERPROFILE':str(home),'GREA_PROVIDER_STATE_DIR':str(root/'state')}
   if os.name=='nt':
    env.update(HOMEDRIVE=home.drive,HOMEPATH=str(home)[len(home.drive):] or '\\',
               PATH=str(Path(os.environ['SystemRoot'])/'System32'))
   else:env['PATH']=''
   with patch.dict(os.environ,env):
    for i,(name,data) in enumerate((('/目录/data.json','{"k":0}'.encode()),('/nested/file.bin',b'\0\xff\x10'))):
     source=root/f'{i}.wxapkg';source.write_bytes(package(name,data));out=root/f'out{i}'
     receipt,_,error=execute('wxapkg-unpack',[str(source),str(out)],root/f'run{i}')
     self.assertIsNone(error,receipt);self.assertTrue(receipt['capture_complete']);self.assertEqual(receipt['cleanup_scope'],'owned_job')
     self.assertEqual((out/name.lstrip('/')).read_bytes(),data)
    source=root/'bad.wxapkg';source.write_bytes(b'not a package')
    receipt,_,error=execute('wxapkg-unpack',[str(source),str(root/'bad-out')],root/'bad-run')
    self.assertIsNotNone(error);self.assertFalse((root/'bad-out').exists())
