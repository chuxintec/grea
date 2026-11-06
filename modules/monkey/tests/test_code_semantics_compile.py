"""Optional actual C# compiler/runtime check; original JS is never executed."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from monkey.code_modules import emit
from monkey.io import sha,write_json
from tests.test_code_modules import fixture,SOURCE

SDK=Path('/Applications/Unity/Hub/Editor/6000.6.2f1/Unity.app/Contents/Resources/Scripting/DotNetSdk/sdk/8.0.318/Roslyn/bincore/csc.dll')
REFERENCES=Path(__file__).resolve().parents[1]/'.private/v050-resources-20261026/clip-compile.rsp'


@unittest.skipUnless(SDK.is_file() and REFERENCES.is_file() and shutil.which('dotnet'),'Existing Unity SDK and installed dotnet needed')
class CodeSemanticsCompileTests(unittest.TestCase):
    def test_generated_loop_exception_cross_class_and_binary64_index_division(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp).resolve()
            raw=SOURCE.replace(b'return x/2;',b'return x/2;').replace(b'var total=0;',b'var total=0;')
            # Directly exercise int-index arithmetic promoted to JS Number.
            raw=raw.replace(b'e.sum=function',b'e.ratio=function(xs){return xs.length/(xs.length+xs.length);};e.sum=function')
            source,contract=fixture(root,raw);spec=json.loads(contract.read_bytes())
            for module in spec['modules']:
                for method in module['methods']:
                    if method['name']=='ratio':method['parameters']=['List<Number>']
            write_json(contract,spec);emit(source,contract,root/'candidate')
            harness=root/'Check.cs';harness.write_text('''using System;using System.Collections.Generic;using Game.Domain.Recovered;
class Check {static int Main(){var xs=new List<double>{2,3,5};
if(MathRules.sum(xs)!=10 || MathRules.ratio(xs)!=0.5 || OrderRules.price(8)!=5)return 1;
try {MathRules.half(-1);return 2;}catch(InvalidOperationException e){if(e.Message!="negative")return 3;}
return 0;}}''')
            refs=['"'+v+'"'for line in REFERENCES.read_text().splitlines()if(v:=line.strip().strip('"')).startswith('-r:')]
            target=root/'Check.dll';rsp=root/'check.rsp'
            sources=[harness,*sorted((root/'candidate/Assets').rglob('*.cs'))]
            rsp.write_text('\n'.join(['-nologo','-target:exe','"-out:'+str(target)+'"',*refs,*['"'+str(p)+'"'for p in sources]])+'\n')
            compiled=subprocess.run([shutil.which('dotnet'),str(SDK),'@'+str(rsp)],capture_output=True,timeout=60)
            self.assertEqual(compiled.returncode,0,(compiled.stdout+compiled.stderr).decode()[-1800:])
            write_json(root/'Check.runtimeconfig.json',dict(runtimeOptions=dict(tfm='net8.0',framework=dict(name='Microsoft.NETCore.App',version='8.0.0'))))
            ran=subprocess.run([shutil.which('dotnet'),str(target)],capture_output=True,timeout=30)
            self.assertEqual(ran.returncode,0,(ran.stdout+ran.stderr).decode()[-1800:])


if __name__=='__main__':unittest.main()
