import os
import struct
import subprocess
import sys
import time
import unittest
from unittest import mock

from grea.development.process_identity import _ProcBsdInfo, _parse_procargs2, list_executables, snapshot


def procargs_fixture(argv, env):
    encoded_argv=[x.encode()+b"\0" for x in argv]
    encoded_env=[k.encode()+b"="+v.encode()+b"\0" for k,v in env]
    path=(argv[0] if argv else "/usr/bin/example").encode()+b"\0"
    return struct.pack("=i",len(argv))+path+b"\0\0"+b"".join(encoded_argv)+b"".join(encoded_env)


class ProcessIdentityTests(unittest.TestCase):
    def test_procargs2_decodes_argv_and_environment_without_logging_them(self):
        raw=procargs_fixture(["/usr/bin/python3","-c","pass","arg with spaces"],[("PATH","/usr/bin"),("EMPTY",""),("PAIR","a=b")])
        argv,env=_parse_procargs2(raw)
        self.assertEqual(argv,["/usr/bin/python3","-c","pass","arg with spaces"])
        self.assertEqual(env,{"PATH":"/usr/bin","EMPTY":"","PAIR":"a=b"})

    def test_procargs2_rejects_malformed_and_bounded_inputs(self):
        with self.assertRaises(ValueError): _parse_procargs2(struct.pack("=i",-1)+b"x\0")
        with self.assertRaises(ValueError): _parse_procargs2(struct.pack("=i",1)+b"/bin/x\0\0\0")
        duplicate=procargs_fixture(["/bin/x"],[("A","1"),("A","2")])
        with self.assertRaises(ValueError): _parse_procargs2(duplicate)
        with self.assertRaises(ValueError): _parse_procargs2(b"x"*(4*1024*1024+1))

    def test_darwin_bsdinfo_structure_matches_sdk_field_layout(self):
        if sys.platform!="darwin": self.skipTest("Darwin SDK process-info layout is platform-specific")
        self.assertEqual(_ProcBsdInfo.pbi_start_tvsec.offset,120)
        self.assertEqual(_ProcBsdInfo.pbi_start_tvusec.offset,128)
        self.assertEqual(__import__("ctypes").sizeof(_ProcBsdInfo),136)

    def test_snapshot_of_current_process_is_verified_or_conservatively_unknown(self):
        result=snapshot(os.getpid())
        self.assertIn(result["status"],("verified","unknown"))
        self.assertEqual(result["pid"],os.getpid())
        if result["status"]=="verified":
            self.assertIsInstance(result["ppid"],int)
            self.assertTrue(result["executablePath"].startswith("/"))
            self.assertRegex(result["uniqueId"],r"^\d+:\d+:\d+$")
            self.assertEqual(result["birthIdentitySource"],"PROC_PIDTBSDINFO")
            self.assertIsInstance(result["startTime"],list)
            self.assertIsInstance(result["arguments"],list)
            self.assertIsInstance(result["environment"],dict)

    @unittest.skipUnless(sys.platform=="darwin","requires Darwin process introspection")
    def test_controlled_subprocess_exec_keeps_birth_identity_when_verified(self):
        before_code="import os,sys,time; time.sleep(.8); os.execv(sys.executable,[sys.executable,'-c','import time; time.sleep(1.0)','after-exec'])"
        child=subprocess.Popen([sys.executable,"-c",before_code,"before-exec"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            first=snapshot(child.pid)
            time.sleep(.95)
            second=snapshot(child.pid)
            self.assertIn(first["status"],("verified","unknown"))
            self.assertIn(second["status"],("verified","unknown"))
            if first["status"]!="verified" or second["status"]!="verified":
                self.skipTest("kernel process/argv introspection unavailable in this sandbox")
            self.assertEqual(first["pid"],second["pid"])
            self.assertEqual(first["uniqueId"],second["uniqueId"])
            self.assertEqual(first["startTime"],second["startTime"])
            self.assertNotEqual(first["arguments"],second["arguments"])
        finally:
            # The child exits on its own after exec; do not signal or terminate it.
            child.wait(timeout=5)

    def test_invalid_pid_contract(self):
        with self.assertRaises(ValueError): snapshot(True)
        with self.assertRaises(ValueError): snapshot(0)

    @unittest.skipUnless(sys.platform=="darwin","requires Darwin process introspection")
    def test_executable_discovery_keeps_partial_coverage_unknown(self):
        fake=object()
        with mock.patch("grea.development.process_identity._darwin_api",return_value=(fake,object())), \
             mock.patch("grea.development.process_identity._list_pids",return_value=[101,102,103]), \
             mock.patch("grea.development.process_identity._path",side_effect=["/Applications/A.app/Contents/MacOS/A",None,"/usr/bin/zsh"]):
            result=list_executables()
        self.assertEqual(result["status"],"unknown")
        self.assertEqual(result["processes"],[{"pid":101,"executablePath":"/Applications/A.app/Contents/MacOS/A"},{"pid":103,"executablePath":"/usr/bin/zsh"}])
        self.assertEqual(result["inaccessiblePids"],[102])
        self.assertTrue(all(set(row)=={"pid","executablePath"} for row in result["processes"]))

    @unittest.skipUnless(sys.platform=="darwin","requires Darwin process introspection")
    def test_executable_discovery_pidlist_failure_is_unknown(self):
        with mock.patch("grea.development.process_identity._darwin_api",return_value=(object(),object())), \
             mock.patch("grea.development.process_identity._list_pids",return_value=None):
            result=list_executables()
        self.assertEqual(result,{"status":"unknown","processes":[],"inaccessiblePids":[]})

    @unittest.skipUnless(sys.platform=="darwin","requires Darwin process introspection")
    def test_executable_discovery_can_find_current_process(self):
        result=list_executables()
        self.assertIn(result["status"],("verified","unknown"))
        self.assertTrue(all(set(row)=={"pid","executablePath"} for row in result["processes"]))
        current=[row for row in result["processes"] if row["pid"]==os.getpid()]
        self.assertEqual(len(current),1)
        self.assertTrue(current[0]["executablePath"].startswith("/"))


if __name__=="__main__": unittest.main()
