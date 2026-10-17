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
