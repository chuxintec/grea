#!/usr/bin/env python3
"""Owned loopback demonstration; does not test a product or a real payment provider."""
import http.client,json,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
identity=json.loads((ROOT/'.local/identity.json').read_text())
assert identity['name'].startswith('grea-')
port=identity['port'];token=None;checks=[]
def request(path,body,authorized=True):
 c=http.client.HTTPConnection('127.0.0.1',port,timeout=6)
 headers={'Content-Type':'application/json'}
 if authorized and token:headers['Authorization']='Bearer '+token
 try:
  c.request('POST',path,json.dumps(body),headers);r=c.getresponse();raw=r.read();return r.status,json.loads(raw)
 finally:c.close()
for _ in range(80):
 try:
  status,_=request('/v1/state',{},False)
  if status==401:break
 except (OSError,ValueError):pass
 time.sleep(.5)
else:raise RuntimeError('Gateway did not become available')
checks.append('unauthenticated state refused')
credential=(ROOT/'.local/development_credential.secret').read_text()
status,r=request('/v1/login',dict(credential=credential),False);assert status==200,(status,r);token=r['sessionId'];checks.append('durable development login')
status,state=request('/v1/state',{});assert status==200 and state['balance']=='0' and state['revision']=='0',(status,state)
command=dict(operationId='owned-starter-001',expectedRevision='0',action='claim_starter',configVersion='example-v1')
# Intentionally discard the first HTTP response. The command may have committed.
c=http.client.HTTPConnection('127.0.0.1',port,timeout=6);c.request('POST','/v1/command',json.dumps(command),{'Content-Type':'application/json','Authorization':'Bearer '+token});c.close();time.sleep(.3)
status,first=request('/v1/command',command);assert status==200 and first['code']=='APPLIED' and first['balance']=='7' and first['revision']=='1',(status,first)
status,again=request('/v1/command',command);assert status==200 and again==first,(status,again)
checks+=['discarded response recovered with same command','persistent identical retry returns same revision and award']
status,r=request('/v1/command',dict(command,expectedRevision='1'));assert status==200 and r['code']=='COMMAND_ID_CONFLICT',(status,r);checks.append('same ID different content refused')
status,r=request('/v1/command',dict(command,operationId='owned-starter-002',expectedRevision='1'));assert status==200 and r['code']=='REJECTED' and r['balance']=='7',(status,r);checks.append('business once-only reward holds across different IDs')
status,r=request('/v1/command',dict(command,operationId='wrong-config',configVersion='wrong'));assert status==409,(status,r);checks.append('config version mismatch refused')
status,r=request('/v1/command',dict(command,expectedRevision=0));assert status==400,(status,r);checks.append('int64 wire string enforced')
status,r=request('/v1/chat',dict(operationId='owned-chat-001',text='owned demonstration'));assert status==200 and r['message']=='owned demonstration',(status,r)
status,r=request('/v1/chat',dict(operationId='owned-chat-001',text='different'));assert status==200 and r['code']=='COMMAND_ID_CONFLICT',(status,r);checks.append('authenticated chat idempotence and conflict')
status,r=request('/v1/order',dict(operationId='owned-order-001',action='create_order',text='example-sku'));assert status==200 and r['code']=='PENDING_PROVIDER',(status,r)
status,r=request('/v1/order',dict(operationId='owned-order-001',action='fulfill'));assert status==503,(status,r);checks.append('payment provider and grant unavailable')
# Restart only these two explicitly recorded grea services, retaining the isolated MySQL volume.
subprocess.run(['docker','compose','-p',identity['name'],'-f',str(ROOT/'compose.json'),'restart','server','login'],check=True,capture_output=True)
for _ in range(80):
 try:
  status,state=request('/v1/state',{})
  if status==200:break
 except (OSError,ValueError):pass
 time.sleep(.5)
else:raise RuntimeError('Restart recovery unavailable')
assert state['balance']=='7' and state['revision']=='1',state
status,r=request('/v1/command',command);assert status==200 and r==first,(status,r);checks.append('session state and durable receipt survive service restart')
result=dict(schema_version=1,status='pass',checks=checks,roles=['gateway','chat','server','login','world','billing'],scope='isolated owned development stack, MySQL/Redis, HTTP ProtoJSON and internal gRPC',not_run=['Unity/Cocos actual network clients','production TLS/WSS/payment','node migration and outbox/inbox'],model_or_game_requests=False)
(ROOT/'smoke-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
