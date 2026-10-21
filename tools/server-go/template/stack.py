#!/usr/bin/env python3
"""Explicit isolated development stack; never selects an existing product stack."""
import argparse,json,os,re,secrets,subprocess,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ROLES=['gateway','chat','server','login','world','billing']
def prepare(name,port):
 if not re.fullmatch(r'grea-[a-z0-9-]{6,40}',name):raise ValueError('Use a unique grea- project name')
 if not 1024<=port<=65535:raise ValueError('Use an unprivileged loopback port')
 local=ROOT/'.local'
 if local.exists():raise ValueError('Local stack identity already exists; reuse explicit status/up/down')
 with socket.socket() as s:s.bind(('127.0.0.1',port))
 local.mkdir(mode=0o700)
 def secret(name,value=None):
  p=local/(name+'.secret');p.write_text(value or secrets.token_hex(32));p.chmod(0o644)
 secret('root_password');secret('internal');secret('redis_password');secret('development_credential')
 sql=[]
 for role in ROLES:
  if role=='gateway':continue
  password=secrets.token_hex(32);db='grea_example_'+role
  sql.append(f"CREATE DATABASE `{db}`; CREATE USER '{role}'@'%' IDENTIFIED BY '{password}'; GRANT ALL ON `{db}`.* TO '{role}'@'%';")
  secret(role+'_dsn',f'{role}:{password}@tcp(mysql:3306)/{db}?parseTime=true')
 (local/'bootstrap.sql').write_text('\n'.join(sql));(local/'bootstrap.sql').chmod(0o644)
 (local/'identity.json').write_text(json.dumps(dict(name=name,port=port)))
 compose={'services':{},'volumes':{'mysql':{}},'secrets':{}}
 for n in ['root_password','internal','redis_password','development_credential']+[r+'_dsn' for r in ROLES if r!='gateway']:
  compose['secrets'][n]={'file':'.local/'+n+'.secret'}
 compose['services']['mysql']={'image':'mysql@sha256:2952e3be7807f06fc18de50b3ea1a632d5c70d63482ff7d7376fe3aa8999babf','mem_limit':'512m','cpus':.4,'environment':{'MYSQL_ROOT_PASSWORD_FILE':'/run/secrets/root_password'},'secrets':['root_password'],'volumes':['mysql:/var/lib/mysql','./.local/bootstrap.sql:/docker-entrypoint-initdb.d/bootstrap.sql:ro'],'command':['--innodb-buffer-pool-size=67108864','--performance-schema=OFF','--max-connections=64'],'healthcheck':{'test':['CMD','mysqladmin','ping','-h','127.0.0.1'],'interval':'3s','timeout':'2s','retries':40}}
 compose['services']['redis']={'image':'__REDIS_IMAGE__','mem_limit':'48m','cpus':.1,'secrets':['redis_password'],'command':['sh','-c','exec redis-server --maxmemory 16777216 --maxmemory-policy noeviction --requirepass "$$(cat /run/secrets/redis_password)"']}
 for role in ROLES:
  environment={'GREA_MODE':'development','GREA_INTERNAL_FILE':'/run/secrets/internal'};attached=['internal']
  if role=='gateway':
   environment['GREA_BROWSER_ORIGIN']='http://127.0.0.1:7456';environment['GREA_REDIS_PASSWORD_FILE']='/run/secrets/redis_password';attached+=['redis_password'];depends={'login':{'condition':'service_started'},'redis':{'condition':'service_started'}}
  else:
   environment['GREA_MYSQL_DSN_FILE']='/run/secrets/'+role+'_dsn';attached+=[role+'_dsn'];depends={'mysql':{'condition':'service_healthy'}}
  if role=='login':environment['GREA_DEVELOPMENT_CREDENTIAL_FILE']='/run/secrets/development_credential';attached+=['development_credential']
  service={'image':name+':local','build':'.','command':[role],'environment':environment,'secrets':attached,'depends_on':depends,'mem_limit':'64m','cpus':.1,'read_only':True,'cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],'pids_limit':64}
  if role=='gateway':service['ports']=[f'127.0.0.1:{port}:8080']
  compose['services'][role]=service
 (ROOT/'compose.json').write_text(json.dumps(compose,indent=2)+'\n')
 print('Prepared isolated identity; secrets remain in .local; source configs are not credentials')
def run(action):
 identity=json.loads((ROOT/'.local/identity.json').read_text());name=identity['name']
 if not re.fullmatch(r'grea-[a-z0-9-]{6,40}',name):raise ValueError('Invalid recorded stack identity')
 base=['docker','compose','-p',name,'-f',str(ROOT/'compose.json')]
 command={'up':['up','-d','--build'],'status':['ps','--format','json'],'down':['down','--volumes','--remove-orphans'],'config':['config','--quiet']}[action]
 subprocess.run(base+command,cwd=ROOT,check=True)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','up','status','down','config']);p.add_argument('--name');p.add_argument('--port',type=int,default=18287);a=p.parse_args()
 if a.action=='prepare':prepare(a.name or '',a.port)
 else:run(a.action)
