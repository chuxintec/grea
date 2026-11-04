"""Exercise the production static-field writer/reader without an Editor."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT=Path(__file__).resolve().parents[1]


def declaration(source, signature):
    start=source.index(signature);opening=source.index('{',start);depth=1;end=opening+1
    while depth:
        if source[end]=='{':depth+=1
        elif source[end]=='}':depth-=1
        end+=1
    return source[start:end]


class UnityStaticFamilyContractTests(unittest.TestCase):
    def test_spine_independent_skin_fields_empty_values_and_mutations(self):
        dotnet=shutil.which('dotnet')
        if not dotnet:self.skipTest('dotnet SDK unavailable')
        targets=ROOT/'src/monkey/targets'
        editor=(targets/'UnityStaticSpineContinuation.cs').read_text()
        members='\n'.join(declaration(editor,key)for key in (
            '[Serializable] sealed class SpineField',
            'static void SpineAssignFields(', 'static bool SpineTypedFieldsMatch('))
        program=r'''
static void Require(bool good,string message){if(!good)throw new Exception(message);}
static NativeStaticSpineReference Create(SpineField[] fields){
    var c=new NativeStaticSpineReference();c.enabled=false;SpineAssignFields(c,fields);return c;
}
static void Main(){
    var fields=new[]{new SpineField{name="defaultSkin",present=true,stringValue=""},
        new SpineField{name="_skinName",present=false},
        new SpineField{name="loop",present=true,boolValue=false},
        new SpineField{name="timeScale",present=true,numberValue=1},
        new SpineField{name="enableBatch",present=true,boolValue=true}};
    var c=Create(fields);Require(SpineTypedFieldsMatch(c,fields),"independent absent alias");
    c.defaultSkin="changed";Require(!SpineTypedFieldsMatch(c,fields),"empty source value mutation");
    c=Create(fields);c.loop=true;Require(!SpineTypedFieldsMatch(c,fields),"bool mutation");
    c=Create(fields);c.hasSkinName=true;Require(!SpineTypedFieldsMatch(c,fields),"unknown flag mutation");
    c=Create(fields);c.timeScale=2;Require(!SpineTypedFieldsMatch(c,fields),"number mutation");
    c=Create(fields);c.enabled=true;Require(!SpineTypedFieldsMatch(c,fields),"enabled policy mutation");
    fields[1].present=true;fields[1].stringValue="other skin";
    c=Create(fields);Require(SpineTypedFieldsMatch(c,fields),"distinct serialized skin values");
    c.skinName="wrong";Require(!SpineTypedFieldsMatch(c,fields),"alias value mutation");
    Console.WriteLine("production typed source fields: pass");
}'''
        runtime=(targets/'NativeStaticSpineReference.cs').read_text().replace('using UnityEngine;','')
        stubs='namespace UnityEngine { public class Object{} public class MonoBehaviour:Object{public bool enabled;} }\npublic class NativeStaticSpineData:UnityEngine.Object{}\npublic class NativeRetainedMaterial:UnityEngine.Object{}'
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp).resolve()
            (out/'Probe.cs').write_text('using System;using UnityEngine;'+stubs+runtime+'\nclass Probe{'+members+program+'}')
            (out/'Probe.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><Nullable>disable</Nullable><NoWarn>CS0649</NoWarn></PropertyGroup></Project>')
            (out/'NuGet.Config').write_text('<configuration><packageSources><clear /></packageSources></configuration>')
            result=subprocess.run([dotnet,'run','--project',str(out/'Probe.csproj'),
                '--property:RestoreConfigFile='+str(out/'NuGet.Config')],capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('production typed source fields: pass',result.stdout)


if __name__=='__main__':unittest.main()
