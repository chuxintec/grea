import sys
import asyncio,json,subprocess,tempfile,unittest
from pathlib import Path
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from grea.common import package_root
from grea.contracts import catalog,ENVELOPE_SCHEMA
from module_support import with_modules

class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_catalog_parity_success_and_failure(self):
        root=package_root();client=Client(StdioServerParameters(command=sys.executable,args=[str(root/'launch.py'),'mcp']),read_timeout_seconds=20)
        async with client:
            listing=await client.list_tools()
            self.assertEqual({t.name for t in listing.tools},{t['name'] for t in catalog()})
            for t in listing.tools:Draft202012Validator.check_schema(t.input_schema);Draft202012Validator.check_schema(t.output_schema)
            for name,args in [('session',{}),('describe_tool',{'tool_id':'missing'}),('session',{'unknown':True})]:
                result=await client.call_tool(name,args)
                actual=result.structured_content
                Draft202012Validator(ENVELOPE_SCHEMA).validate(actual)
                cli=subprocess.run([sys.executable,str(root/'launch.py'),name.replace('_','-'),json.dumps(args)],capture_output=True,text=True)
                expected=json.loads(cli.stdout)
                self.assertEqual(actual['status'],expected['status'])
                self.assertEqual(actual['result'],expected['result'])
                self.assertEqual(actual['error'],expected['error'])
                self.assertEqual(result.is_error,actual['status']=='error')
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'artifact';p.write_bytes(b'UnityFS-test')
                result=await client.call_tool('inspect_target',{'path':str(p)})
                self.assertEqual(result.structured_content['result']['target']['format'],'unity-bundle')

    @with_modules
    async def test_stdio_case_and_typed_helper(self):
        root=package_root()
        async with Client(StdioServerParameters(command=sys.executable,args=[str(root/'launch.py'),'mcp'],env=dict(__import__("os").environ)),read_timeout_seconds=20) as client:
            with tempfile.TemporaryDirectory() as d:
                base=Path(d);source=base/'source.apk';source.write_bytes(b'fixture')
                result=await client.call_tool('init_case',{'project_dir':d,'source':str(source),'mode':'fix'})
                self.assertEqual(result.structured_content['status'],'ok')
                status=await client.call_tool('case_status',{'case_dir':d})
                self.assertEqual(status.structured_content['result']['declared_acceptance'],'incomplete')
                a=base/'a.jsonl';b=base/'b.jsonl';a.write_text('{"value":1}\n');b.write_text('{"value":2}\n')
                compared=await client.call_tool('compare_gameplay_traces',{'before':str(a),'after':str(b),'fields':['/value'],'run_dir':str(base/'run')})
                self.assertEqual(compared.structured_content['status'],'partial')
                self.assertEqual(compared.structured_content['result']['exit_code'],1)
                self.assertFalse(compared.is_error)

    async def test_legacy_protocol_cancellation_preserves_receipt(self):
        import os,queue,threading,time
        root=package_root()
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);script=base/'sleep.py';script.write_text('import time\nprint("started",flush=True)\ntime.sleep(20)\n')
            (base/'registry.json').write_text(json.dumps({'tools':[{'id':'fixture','execution':{'command':[sys.executable,str(script)]}}]}))
            env=dict(os.environ,GREA_HOME=d)
            process=subprocess.Popen([sys.executable,'-m','grea.cli','mcp'],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
            def send(value):process.stdin.write(json.dumps(value)+'\n');process.stdin.flush()
            try:
                send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'grea-conformance','version':'1'}}})
                messages=queue.Queue()
                threading.Thread(target=lambda:messages.put(process.stdout.readline()),daemon=True).start()
                initialized=json.loads(messages.get(timeout=10));self.assertEqual(initialized['result']['protocolVersion'],'2025-03-26')
                send({'jsonrpc':'2.0','method':'notifications/initialized'})
                run=base/'cancelled'
                send({'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'run_tool','arguments':{'tool_id':'fixture','arguments':[],'run_dir':str(run)}}})
                deadline=time.monotonic()+5
                while not (run/'stdout.log').exists() and time.monotonic()<deadline:await asyncio.sleep(.02)
                self.assertTrue((run/'stdout.log').exists())
                send({'jsonrpc':'2.0','method':'notifications/cancelled','params':{'requestId':2,'reason':'fixture cancellation'}})
                deadline=time.monotonic()+5
                while not (run/'run.json').exists() and time.monotonic()<deadline:await asyncio.sleep(.02)
                self.assertTrue((run/'run.json').exists())
                receipt=json.loads((run/'run.json').read_text());self.assertEqual(receipt['reason'],'CANCELLED')
            finally:
                process.stdin.close()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()
                process.stdout.close();process.stderr.close()

if __name__=='__main__':unittest.main()
