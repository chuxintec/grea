"""Production comparer treats Unity's absent/empty optional strings identically."""
from pathlib import Path
import shutil
import subprocess
import pytest
from . import test_unity_static_mask_optional_contract as helpers

ROOT = Path(__file__).resolve().parents[2]


def test_saved_optional_strings_do_not_drop_required_resolver_or_identity_values(tmp_path):
    dotnet = shutil.which('dotnet')
    if not dotnet:
        pytest.skip('dotnet required for production managed predicate')
    source = (ROOT/'src/grea/recovery/targets/UnityStaticMaskSort.cs').read_text()
    method = helpers.declaration(source, 'public static bool OptionalMaterialSourceFieldMatches(')
    main = '''
    public static void Main() {
        string[][] cases = new[] { new string[]{null,null,"1"}, new string[]{null,"","1"},
            new string[]{"",null,"1"}, new string[]{"","","1"},
            new string[]{"engine-default-builtin","engine-default-builtin","1"},
            new string[]{"","engine-default-builtin","0"},new string[]{null,"engine-default-builtin","0"},
            new string[]{"wrong","engine-default-builtin","0"},new string[]{" ",null,"0"},
            new string[]{"ABC","abc","0"} };
        foreach(var row in cases)if(OptionalMaterialSourceFieldMatches(row[0],row[1])!=(row[2]=="1"))throw new Exception("Optional material mismatch");
        Console.WriteLine("production optional material cases: 10 passed");
    }
'''
    (tmp_path/'Probe.cs').write_text('using System; public static class Probe {\n'+method+main+'\n}')
    (tmp_path/'Probe.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><Nullable>disable</Nullable></PropertyGroup></Project>')
    config=tmp_path/'NuGet.Config';config.write_text('<configuration><packageSources><clear /></packageSources></configuration>')
    result=subprocess.run([dotnet,'run','--project',str(tmp_path/'Probe.csproj'),'--property:RestoreConfigFile='+str(config)],capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'production optional material cases: 10 passed' in result.stdout
