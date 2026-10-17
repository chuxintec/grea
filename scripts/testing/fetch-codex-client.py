#!/usr/bin/env python3
"""Download a pinned native client into a NEW test-only directory, never install globally."""
import argparse,hashlib,io,urllib.request,zipfile,tarfile,platform,os
from pathlib import Path
URL='https://github.com/openai/codex/releases/download/rust-v0.163.0/codex-x86_64-pc-windows-msvc.exe.zip'
SHA='dabdb4d16aaf10fea40b74811c96efddcd9138f122163b69ed604fcb3eb704c3'
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise FileExistsError(a.out)
 mac=platform.system()=='Darwin'
 url=URL if not mac else 'https://github.com/openai/codex/releases/download/rust-v0.163.0/codex-aarch64-apple-darwin.tar.gz'
 digest=SHA if not mac else '61c4d9a92521bdb42b0c1d9f87c673f6da628a06de5945cbdd9a0010632f6d10'
 size=99551880 if mac else 167080091
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'grea-native-client-test'}),timeout=120) as stream:raw=stream.read(180000000)
 if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Client release identity mismatch')
 if mac:
  with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
   names=[n for n in archive.getmembers() if n.isfile() and n.name.rsplit('/',1)[-1]=='codex-aarch64-apple-darwin']
   if len(names)!=1:raise ValueError('Pinned client binary missing/ambiguous')
   data=archive.extractfile(names[0]).read()
 else:
  with zipfile.ZipFile(io.BytesIO(raw)) as archive:
   names=[n for n in archive.namelist() if n.rsplit('/',1)[-1]=='codex-x86_64-pc-windows-msvc.exe']
   if len(names)!=1:raise ValueError('Pinned client binary missing/ambiguous')
   data=archive.read(names[0])
 a.out.mkdir(parents=True);binary=a.out/('codex' if mac else 'codex.exe');binary.write_bytes(data);binary.chmod(0o755)
if __name__=='__main__':main()
