"""Single supported native target/layout table for build, acceptance and release."""
import json
from pathlib import Path
import platform

TARGETS={
 'macos-arm64':dict(system='Darwin',machines=('arm64','aarch64'),lock='plugin/runtime-lock.json',
                    python='runtime/bin/python3',site='runtime/lib/python3.12/site-packages',triple='aarch64-apple-darwin'),
 'windows-x64':dict(system='Windows',machines=('amd64','x86_64'),lock='plugin/runtime-windows-x64.lock.json',
                    python='runtime/python.exe',site='runtime/Lib/site-packages',triple='x86_64-pc-windows-msvc'),
}
def native_target():
 for name,row in TARGETS.items():
  if platform.system()==row['system'] and platform.machine().lower() in row['machines']:return name
 raise ValueError('No native complete-plugin target for this OS/architecture')
def target_config(target=None):
 name=target or native_target()
 if name not in TARGETS:raise ValueError('Unknown plugin target')
 return name,TARGETS[name]
def runtime_lock(source,target):return json.loads(source[TARGETS[target]['lock']][0])
def archive_name(target):return 'grea-plugin-'+target+'.zip'
def report_name(target):return 'plugin-acceptance-'+target+'.json'

def client_launch(target,client):
 if target=='macos-arm64':
  return {'command':'./plugin/launcher/grea','args':['mcp'],'cwd':'.'} if client=='codex' else {
   'type':'stdio','command':'${CLAUDE_PLUGIN_ROOT}/plugin/launcher/grea','args':['mcp']}
 # Direct native executable; no cmd/%*/PowerShell interpretation of plugin paths.
 prefix='./' if client=='codex' else '${CLAUDE_PLUGIN_ROOT}/'
 code="import runpy,sys;from pathlib import Path;runpy.run_path(str(Path(sys.executable).resolve().parent.parent/'plugin/launcher/start.py'),run_name='__main__')"
 value={'command':prefix+'runtime/python.exe','args':['-I','-B','-c',code,'mcp']}
 if client=='codex':value['cwd']='.'
 else:value['type']='stdio'
 return value
