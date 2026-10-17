import sys
"""CLI/MCP share the actual run-tool path, including partial and malformed inputs."""
import json
import asyncio
from pathlib import Path
import subprocess
import tempfile
import unittest
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from grea.common import package_root
from grea.cocos_contracts import documents
from grea.tools.cocos_assets import error_report, ParseError

PLAIN=[1,[],[],[['cc.Node',['_name'],2]],[[0,0,2]],[[0,'root']],[],[],[],[],[]]
class DispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_cli_mcp_reports_errors_and_no_overwrite(self):
        root=package_root()
        with tempfile.TemporaryDirectory() as t:
            base=Path(t).resolve();source=base/'source.json';source.write_text(json.dumps(PLAIN))
            async with Client(StdioServerParameters(command=sys.executable,args=[str(root/'launch.py'),'mcp']),read_timeout_seconds=30) as client:
                listing=await client.call_tool('describe_tool',{'tool_id':'cocos_assets'})
                self.assertEqual(listing.structured_content['status'],'ok')
                for n,content,wanted in [('valid',PLAIN,'ok'),('unsupported',[999],'partial'),('truncated',[1],'error')]:
                    source.write_text(json.dumps(content))
                    args=dict(tool_id='cocos_assets',arguments=['--input',str(source),'--output',str(base/('out-'+n))],run_dir=str(base/('mcp-'+n)))
                    result=(await client.call_tool('run_tool',args)).structured_content
                    self.assertEqual(result['status'],wanted)
                    native=result['result']['parsed_stdout']
                    Draft202012Validator(documents()['cocos-evidence.schema.json']).validate(native)
                    args['run_dir']=str(base/('cli-'+n));args['arguments'][-1]=str(base/('cli-out-'+n))
                    cli=await asyncio.to_thread(subprocess.run,[sys.executable,str(root/'launch.py'),'run-tool',json.dumps(args)],capture_output=True,text=True)
                    self.assertEqual(json.loads(cli.stdout)['status'],wanted)
                self.assertFalse((base/'out-truncated').exists())
                original=(base/'out-valid/decoded.json').read_bytes()
                source.write_text(json.dumps(PLAIN))
                bad=await client.call_tool('run_tool',dict(tool_id='cocos_assets',arguments=['--input',str(source),'--output',str(base/'out-valid')],run_dir=str(base/'conflict')))
                self.assertEqual(bad.structured_content['status'],'error');self.assertEqual((base/'out-valid/decoded.json').read_bytes(),original)

    def test_versioned_error_contract(self):
        for error in [ParseError('INDEX_OUT_OF_RANGE','$[5]','invalid'),ParseError('UNSUPPORTED_VERSION','$[0]','unknown'),OSError('missing')]:
            Draft202012Validator(documents()['cocos-evidence.schema.json']).validate(error_report('cocos_assets','cocos-2.4-compiled-v1',error))

    async def test_authoring_tools_use_same_cli_and_mcp_contract(self):
        root=package_root()
        with tempfile.TemporaryDirectory() as t:
            base=Path(t).resolve(); schema=base/'schema.json';rows=base/'rows.json';recipe=base/'recipe.json'
            schema.write_text(json.dumps(dict(schema_version=1,namespace='Own.Typed',name='Hint',key='Id',fields=[dict(name='Id',type='int'),dict(name='Text',type='string',nullable=True)])))
            rows.write_text('[{"Id":1,"Text":null},{"Id":2,"Text":""}]')
            recipe.write_text(json.dumps(dict(schema_version=1,sprites=[],targets=[dict(path='Widget',scale=[2,3,1])],clips=[dict(name='Move',duration=1,loop=True,curves=[dict(target='Widget',property='m_LocalPosition.x',keys=[[0,0],[1,4]])],events=[])])))
            async with Client(StdioServerParameters(command=sys.executable,args=[str(root/'launch.py'),'mcp']),read_timeout_seconds=30) as client:
                for name,arguments,readback in [('unity_config_candidate',['--schema',str(schema),'--input',str(rows)],'source-rows.json'),('unity_native_assets',['prepare','--recipe',str(recipe)],'native-request.json')]:
                    hashes=[]
                    for transport in ('cli','mcp'):
                        out=base/(name+'-'+transport);args=dict(tool_id=name,arguments=arguments+['--output',str(out)],run_dir=str(base/(name+'-'+transport+'-receipt')))
                        if transport=='cli':
                            process=await asyncio.to_thread(subprocess.run,[sys.executable,str(root/'launch.py'),'run-tool',json.dumps(args)],capture_output=True,text=True);result=json.loads(process.stdout)
                        else:result=(await client.call_tool('run_tool',args)).structured_content
                        self.assertEqual(result['status'],'ok');hashes.append((out/readback).read_bytes())
                    self.assertEqual(*hashes)
                # Missing target fails without a candidate; malformed recipe is not a partial success.
                document=json.loads(recipe.read_text());document['clips'][0]['curves'][0]['target']='Missing';recipe.write_text(json.dumps(document))
                out=base/'invalid';bad=(await client.call_tool('run_tool',dict(tool_id='unity_native_assets',arguments=['prepare','--recipe',str(recipe),'--output',str(out)],run_dir=str(base/'invalid-receipt')))).structured_content
                self.assertEqual(bad['status'],'error');self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
