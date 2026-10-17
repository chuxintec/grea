"""These are real OS tests on each host, not platform mocks."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from grea.common import GreaError, publish_directory

ROOT=Path(__file__).resolve().parents[1]
ENV=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONUTF8='1')

class HostTests(unittest.TestCase):
    def test_concurrent_publication_never_replaces_target(self):
        with tempfile.TemporaryDirectory(prefix='grea 中文 & ! ') as tmp:
            root=Path(tmp);target=root/'target'
            for n in range(4):(root/str(n)).mkdir();(root/str(n)/'id').write_text(str(n),encoding='utf-8')
            code='from grea.common import publish_directory;import sys;publish_directory(*sys.argv[1:])'
            children=[subprocess.Popen([sys.executable,'-c',code,str(root/str(n)),str(target)],env=ENV,stderr=subprocess.DEVNULL) for n in range(4)]
            self.assertEqual(sum(p.wait()==0 for p in children),1)
            self.assertEqual(sum((root/str(n)).exists() for n in range(4)),3)
            empty=root/'empty';empty.mkdir();stage=root/'stage';stage.mkdir()
            with self.assertRaises(GreaError):publish_directory(stage,empty)
            self.assertTrue(stage.is_dir());self.assertEqual(list(empty.iterdir()),[])

    def test_shared_readers_exclude_writer_and_death_releases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);lock=root/'lock';lock.touch()
            code='from grea.host.files import file_lock;import sys,time;from pathlib import Path\nwith file_lock(sys.argv[1],write=sys.argv[3]=="write"):\n Path(sys.argv[2]).touch();time.sleep(30)'
            def start(name,mode):return subprocess.Popen([sys.executable,'-c',code,str(lock),str(root/name),mode],env=ENV)
            def until(name):
                deadline=time.monotonic()+5
                while not (root/name).exists() and time.monotonic()<deadline:time.sleep(.02)
                self.assertTrue((root/name).exists())
            reader=start('reader','read');reader2=writer=None
            try:
                until('reader');reader2=start('reader2','read');until('reader2')
                writer=start('writer','write');time.sleep(.25);self.assertFalse((root/'writer').exists())
                reader.kill();reader.wait();time.sleep(.1);self.assertFalse((root/'writer').exists())
                reader2.kill();reader2.wait();until('writer')
            finally:
                for p in (reader,reader2,writer):
                    if p and p.poll() is None:p.kill();p.wait()

    @unittest.skipUnless(os.name=='nt','Win32 native Job ownership')
    def test_job_owns_descendants_even_after_parent_exit(self):
        from grea.host.windows_process import OwnedProcess
        with tempfile.TemporaryDirectory() as tmp:
            marker=Path(tmp)/'escaped'
            grand='import time,pathlib;time.sleep(3);pathlib.Path('+repr(str(marker))+').touch()'
            child='import subprocess,sys;subprocess.Popen([sys.executable,"-c",'+repr(grand)+'])'
            parent='import subprocess,sys;subprocess.Popen([sys.executable,"-c",'+repr(child)+'])'
            p=OwnedProcess([sys.executable,'-c',parent],tmp)
            try:
                self.assertEqual(p.wait(5),0);time.sleep(.3);self.assertTrue(p.settle())
                self.assertEqual(p.stdout.read(),b'');self.assertEqual(p.stderr.read(),b'')
                time.sleep(3.2);self.assertFalse(marker.exists())
            finally:
                p.close();p.stdout.close();p.stderr.close()

    @unittest.skipUnless(os.name=='nt','Win32 argv round trip')
    def test_job_unicode_argv_and_launch_failure(self):
        from grea.host.windows_process import OwnedProcess
        with tempfile.TemporaryDirectory(prefix='grea 中文 & ! () ') as tmp:
            args=['中文','a b','a&b!','"quoted"','last\\']
            p=OwnedProcess([sys.executable,'-c','import sys,json;print(json.dumps(sys.argv[1:]))',*args],tmp)
            try:
                self.assertEqual(json.loads(p.stdout.read()),args);self.assertEqual(p.wait(5),0)
                self.assertTrue(p.settle())
            finally:p.close();p.stdout.close();p.stderr.close()
            with self.assertRaises(OSError):OwnedProcess([str(Path(tmp)/'absent.exe')],tmp)

    @unittest.skipUnless(os.name=='nt','Windows junction boundary')
    def test_junction_is_not_read_as_owned_evidence(self):
        from grea.host.files import is_link
        from grea.tools._artifact_common import inventory
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=base/'source';source.mkdir();outside=base/'outside';outside.mkdir();(outside/'private.txt').write_text('owned test only')
            link=source/'jump'
            subprocess.run(['cmd.exe','/c','mklink','/J',str(link),str(outside)],check=True,capture_output=True)
            try:
                self.assertTrue(is_link(link))
                with self.assertRaises(ValueError):inventory(source)
            finally:link.rmdir()
