"""Regression contracts for the module CLI, declared parameters and MCP execution."""
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from grea.commands.catalog import commands
from grea.commands.groups import MODULES
from grea.commands.interface import route
from grea.common import package_root


def run(args):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = route(args)
    return rc, json.loads(output.getvalue())


class ModuleCliTests(unittest.TestCase):
    def test_generated_catalog_matches_all_executable_commands(self):
        data = json.loads((package_root() / "schemas/commands.json").read_text())
        self.assertEqual(set(data["modules"]), set(MODULES))
        self.assertEqual(data["commands"], [cmd.describe() for _, cmd in sorted(commands().items())])
        self.assertEqual(set(data["modules"]), {c.module for c in commands().values()})
        for cmd in commands().values():
            self.assertEqual(cmd.parser.prog, f"grea {cmd.module} {cmd.name}")

    def test_request_file_flags_and_core_schema_have_the_same_meaning(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = Path(tmp) / "args.json"
            req.write_text('{"module":"prefab","action":"recover"}')
            rc, file = run(["--request",str(req),"system","command-catalog"])
            rc2, inline = run(["system","command-catalog","--module","prefab","--action","recover"])
            self.assertEqual((rc,rc2),(0,0))
            self.assertEqual(file["result"]["result"],inline["result"]["result"])
            for invalid in ('{"module":"x","module":"y"}','{"unknown":42}', '{"module":[]}'):
                req.write_text(invalid)
                rc, receipt = run(["--request",str(req),"system","command-catalog"])
                self.assertEqual((rc, receipt["status"], receipt["exit_code"]),(2,"error",2))

    def test_output_alias_and_invalid_input_before_mutation(self):
        cmd = commands()["prefab","recover"]
        self.assertIs(cmd.parser._option_string_actions["--output"],cmd.parser._option_string_actions["--out"])
        with tempfile.TemporaryDirectory() as tmp:
            req = Path(tmp)/"args.json"
            dest = Path(tmp)/"should-not-exist"
            req.write_text(json.dumps(dict(output=str(dest),out=str(dest))))
            rc, result = run(["--request",str(req),"prefab","recover"])
            self.assertEqual(rc,2)
            self.assertIn("Multiple spellings",result["diagnostics"])
            self.assertFalse(dest.exists())
            rc, result = run(["prefab","recover","--unexpected"])
            self.assertEqual(result["status"],"error")
            self.assertFalse(dest.exists())

    def test_flags_after_separator_remain_literal(self):
        from types import SimpleNamespace
        from grea.commands.interface import invoke
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--output","--out")
        handler = lambda argv: argv
        cmd = SimpleNamespace(backend="helper",parser=parser,path=("example",),handler=handler)
        self.assertEqual(invoke(cmd,None,["--output=a","--","--output=b"]),["--out=a","--","--output=b"])


class ModuleMcpTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_queries_catalog_and_executes_the_same_module_as_cli(self):
        client = Client(StdioServerParameters(command=sys.executable,args=["-m","grea.cli","mcp"]),read_timeout_seconds=30)
        async with client:
            response = await client.call_tool("command_catalog",{"module":"code","action":"query-methods"})
            actual = response.structured_content["result"]["commands"]
            self.assertEqual(actual,[commands()["code","query-methods"].describe()])
            with tempfile.TemporaryDirectory() as tmp:
                response = await client.call_tool("run_tool",{"tool_id":"system","arguments":["version"],"run_dir":str(Path(tmp)/"run")})
                self.assertFalse(response.is_error)
                observed = response.structured_content["result"]["parsed_stdout"]
                cli = subprocess.run([sys.executable,"-m","grea.cli","system","version"],capture_output=True,text=True,check=True)
                expected = json.loads(cli.stdout)
                for key in ("product","version","command","status","exit_code"):
                    self.assertEqual(observed[key],expected[key])
                self.assertEqual(observed["result"]["producer"],expected["result"]["producer"])
