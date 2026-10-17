#!/usr/bin/env python3
"""Download a pinned native client into a NEW test-only directory, never install globally."""
import argparse,hashlib,io,urllib.request,zipfile
from pathlib import Path
URL='https://github.com/openai/codex/releases/download/rust-v0.163.0/codex-x86_64-pc-windows-msvc.exe.zip'
SHA='dabdb4d16aaf10fea40b74811c96efddcd9138f122163b69ed604fcb3eb704c3'
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise FileExistsError(a.out)
 with urllib.request.urlopen(urllib.request.Request(URL,headers={'User-Agent':'grea-native-client-test'}),timeout=120) as stream:raw=stream.read(180000000)
 if len(raw)!=167080091 or hashlib.sha256(raw).hexdigest()!=SHA:raise ValueError('Client release identity mismatch')
 with zipfile.ZipFile(io.BytesIO(raw)) as archive:
  names=[n for n in archive.namelist() if n.rsplit('/',1)[-1]=='codex-x86_64-pc-windows-msvc.exe']
  if len(names)!=1:raise ValueError('Pinned client binary missing/ambiguous')
  data=archive.read(names[0])
 a.out.mkdir(parents=True);(a.out/'codex.exe').write_bytes(data)
if __name__=='__main__':main()
