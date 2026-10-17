"""Temporary AppContainer for candidate verification, never a user firewall change.

Grants access only on verifier-owned temporary trees. No capabilities (including
network) are granted. The caller must run and inspect real denial probes; merely
creating this object does not establish isolation.
"""
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path
import subprocess
import uuid

class Capabilities(c.Structure):
 _fields_=[('sid',w.LPVOID),('capabilities',w.LPVOID),('count',w.DWORD),('reserved',w.DWORD)]

class AppContainer:
 def __init__(self,root,work,home):
  self.paths=[Path(p).resolve() for p in (root,work,home)]
  self.name='grea.verify.'+uuid.uuid4().hex;self.sid=w.LPVOID();self.created=False
 def __enter__(self):
  self.user=c.WinDLL('userenv',use_last_error=True);self.adv=c.WinDLL('advapi32',use_last_error=True);self.k=c.WinDLL('kernel32',use_last_error=True)
  self.user.CreateAppContainerProfile.argtypes=[w.LPCWSTR,w.LPCWSTR,w.LPCWSTR,w.LPVOID,w.DWORD,c.POINTER(w.LPVOID)];self.user.CreateAppContainerProfile.restype=c.c_long
  self.user.DeleteAppContainerProfile.argtypes=[w.LPCWSTR];self.user.DeleteAppContainerProfile.restype=c.c_long
  self.adv.ConvertSidToStringSidW.argtypes=[w.LPVOID,c.POINTER(w.LPWSTR)];self.adv.ConvertSidToStringSidW.restype=w.BOOL
  self.adv.FreeSid.argtypes=[w.LPVOID];self.adv.FreeSid.restype=w.LPVOID
  self.k.LocalFree.argtypes=[w.LPVOID];self.k.LocalFree.restype=w.LPVOID
  result=self.user.CreateAppContainerProfile(self.name,self.name,'Ephemeral grea candidate verifier',None,0,c.byref(self.sid))
  if result<0:raise OSError('CreateAppContainerProfile failed: '+hex(result&0xffffffff))
  self.created=True
  try:
   text=w.LPWSTR()
   if not self.adv.ConvertSidToStringSidW(self.sid,c.byref(text)):raise c.WinError(c.get_last_error())
   try:sid=text.value
   finally:self.k.LocalFree(c.cast(text,w.LPVOID))
   tool=str(Path(os.environ['SystemRoot'])/'System32/icacls.exe')
   for path,rights in zip(self.paths,('RX','F','F')):
    subprocess.run([tool,str(path),'/grant','*'+sid+':(OI)(CI)('+rights+')','/T','/Q'],check=True,capture_output=True)
    if rights=='F':subprocess.run([tool,str(path),'/setintegritylevel','(OI)(CI)L','/T','/Q'],check=True,capture_output=True)
   self.capabilities=Capabilities(self.sid,None,0,0)
   return self
  except BaseException:self.__exit__(None,None,None);raise
 def __exit__(self,*_):
  if self.created:
   result=self.user.DeleteAppContainerProfile(self.name);self.created=False
   self.adv.FreeSid(self.sid)
   if result<0:raise OSError('Temporary AppContainer profile cleanup failed: '+hex(result&0xffffffff))
