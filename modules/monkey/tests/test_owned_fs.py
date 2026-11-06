import os
import tempfile
import unittest
from pathlib import Path
from monkey.owned_fs import RootReader
from monkey.io import sha
from monkey.sources.compiled import ParseError


class OwnedReadTests(unittest.TestCase):
    def test_symlink_file_and_parent_are_never_followed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();(root/'owned').mkdir();(root/'outside').mkdir();(root/'outside/secret').write_bytes(b'outside')
            (root/'owned/link').symlink_to(root/'outside',target_is_directory=True);(root/'owned/file').symlink_to(root/'outside/secret')
            with RootReader(root/'owned') as view:
                for name in ['link/secret','file','../outside/secret']:
                    with self.assertRaises((ParseError,OSError)):view.read(name)

    def test_cached_directory_handle_resists_a_later_path_pivot(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();(root/'owned/sub').mkdir(parents=True);(root/'owned/sub/value').write_bytes(b'owned');(root/'outside').mkdir();(root/'outside/value').write_bytes(b'outside')
            with RootReader(root/'owned') as view:
                self.assertEqual(view.read('sub/value'),b'owned')
                if not view.native:self.skipTest('No no-follow directory handles')
                (root/'owned/sub').rename(root/'owned/old');(root/'owned/sub').symlink_to(root/'outside',target_is_directory=True)
                self.assertEqual(view.read('sub/value'),b'owned')

    def test_file_kind_and_byte_limits_and_descriptor_cache_are_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();(root/'big').write_bytes(b'12345')
            with RootReader(root) as view:
                with self.assertRaises(ParseError):view.read('big',4)
                with self.assertRaises(ParseError):view.digest('big',4)
                self.assertEqual(view.digest('big'),(sha(b'12345'),5))
                for i in range(150):
                    p=root/str(i);p.mkdir();(p/'value').write_bytes(b'x');self.assertEqual(view.read(str(i)+'/value'),b'x')
                self.assertLessEqual(len(view.cache),128)
                if hasattr(os,'mkfifo') and view.native:
                    os.mkfifo(root/'fifo')
                    with self.assertRaises(ParseError):view.read('fifo')
