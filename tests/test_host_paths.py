"""Canonical target identity and strict/missing behavior across native hosts."""
import os,subprocess,tempfile,unittest
from grea.host.paths import Path

class CanonicalPathTests(unittest.TestCase):
 def test_existing_missing_and_normalized_parent(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).resolve(strict=True);(root/'source').mkdir()
   self.assertTrue(os.path.samefile(root,(root/'source'/'..').resolve(strict=True)))
   missing=root/'missing'/'child'
   self.assertEqual(missing.resolve(),missing)
   self.assertEqual((root/'missing'/'..').resolve(),root)
   with self.assertRaises(FileNotFoundError):missing.resolve(strict=True)
 def test_link_resolves_to_target_instead_of_lexical_alias(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);target=root/'actual';target.mkdir();link=root/'alias'
   if os.name=='nt':subprocess.run(['cmd.exe','/c','mklink','/J',str(link),str(target)],check=True,capture_output=True)
   else:link.symlink_to(target,target_is_directory=True)
   try:self.assertEqual(link.resolve(strict=True),target.resolve(strict=True))
   finally:
    if os.name=='nt':link.rmdir()
    else:link.unlink()

class VolumeIdentityTests(unittest.TestCase):
 def test_drive_alias_requires_the_same_opened_volume_identity(self):
  from unittest.mock import patch
  from grea.host.paths import final_name
  class Kernel:
   def __init__(self,volume):self.volume=volume;self.closed=[]
   def GetFinalPathNameByHandleW(self,handle,buffer,size,flags):
    assert flags==2
    buffer.value='\\Device\\HarddiskVolume4\\actual\\file' if handle==1 else self.volume
    return len(buffer.value)
   def CreateFileW(self,name,access,share,security,creation,flags,template):
    assert name=='C:\\' and access==0
    return 2
   def CloseHandle(self,handle):self.closed.append(handle)
  with patch('grea.host.paths.in_appcontainer',return_value=True):
   matching=Kernel('\\Device\\HarddiskVolume4\\')
   self.assertEqual(final_name(matching,1,'C:\\alias\\file'),'C:\\actual\\file')
   other=Kernel('\\Device\\HarddiskVolume8\\')
   self.assertEqual(final_name(other,1,'C:\\alias\\file'),'\\\\?\\GLOBALROOT\\Device\\HarddiskVolume4\\actual\\file')
   self.assertEqual(matching.closed,[2]);self.assertEqual(other.closed,[2])


class PrivateDirectoryTests(unittest.TestCase):
 def test_private_staging_is_writable_and_cleanup_is_scoped(self):
  from grea.host.files import temporary_directory
  with tempfile.TemporaryDirectory() as base:
   untouched=Path(base)/'keep';untouched.write_text('keep')
   with temporary_directory(prefix='grea-unit-',dir=base) as tmp:
    path=Path(tmp);(path/'marker').write_text('private')
    self.assertEqual((path/'marker').read_text(),'private')
    if os.name!='nt':self.assertEqual(path.stat().st_mode & 0o077,0)
   self.assertFalse(path.exists());self.assertEqual(untouched.read_text(),'keep')
