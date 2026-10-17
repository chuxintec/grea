"""Temporary user-session drive views of verifier-owned trees; no ACL changes.

AppContainer cannot query metadata of unrelated user-profile ancestors. Drive
roots expose exactly the owned test trees so full ancestor/reparse checks still
run, without granting access to those unrelated directories. No admin switch,
physical volume, network mapping, or persistent install is used.
"""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path

class TemporaryDrives:
 def __init__(self,*paths):
  self.targets=[Path(p).resolve() for p in paths];self.created=[]
 def __enter__(self):
  self.k=c.WinDLL('kernel32',use_last_error=True)
  self.k.GetLogicalDrives.argtypes=[];self.k.GetLogicalDrives.restype=w.DWORD
  self.k.DefineDosDeviceW.argtypes=[w.DWORD,w.LPCWSTR,w.LPCWSTR];self.k.DefineDosDeviceW.restype=w.BOOL
  mask=self.k.GetLogicalDrives()
  if not mask:raise c.WinError(c.get_last_error())
  available=[chr(i+65)+':' for i in range(25,15,-1) if not mask&(1<<i)]
  if len(available)<len(self.targets):raise OSError('Not enough unused temporary drive letters')
  try:
   for drive,path in zip(available,self.targets):
    # RAW_TARGET_PATH | NO_BROADCAST_SYSTEM. Local DOS definitions belong to
    # this logon session. Exact-target cleanup cannot remove a foreign mapping.
    target='\\??\\'+str(path)
    if not self.k.DefineDosDeviceW(9,drive,target):raise c.WinError(c.get_last_error())
    self.created.append((drive,target))
   self.paths=[Path(drive+'\\') for drive,_ in self.created]
   return self
  except BaseException:self.__exit__(None,None,None);raise
 def __exit__(self,*_):
  failures=[]
  for drive,target in reversed(self.created):
   if not self.k.DefineDosDeviceW(1|2|4|8,drive,target):failures.append((drive,c.get_last_error()))
  self.created=[]
  if failures:raise OSError('Temporary exact-target drive cleanup failed: '+repr(failures))
