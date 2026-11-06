"""Compile the production C# population validators without a Unity process."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from grea.recovery.prefab_system_fonts import prepare
from .test_system_font_population_policy import fixture


ROOT = Path(__file__).resolve().parents[2]


def declaration(source, signature):
    start=source.index(signature)
    opening=source.index('{',start)
    depth=1;end=opening+1
    while depth:
        depth += (source[end]=='{')-(source[end]=='}')
        end+=1
    return source[start:end]


def build_harness(directory):
    dotnet=shutil.which('dotnet')
    if not dotnet:
        raise unittest.SkipTest('.NET SDK unavailable')
    source=(ROOT/'src/grea/recovery/targets/UnitySystemFonts.cs').read_text()
    members=[declaration(source,'public sealed class '+name) for name in
             ('Spec','FontSpec','GlyphSpec','PhysicalFace','LabelBindingSpec','ResolvedFallbackFace','BindingSet')]
    members += [declaration(source,signature) for signature in
                ('static bool IsSha256(', 'static bool StaticSdfPhysicalFacesSupported(',
                 'static void ValidateSpec(', 'static void ValidateReferences(')]
    constants='const string ExpectedSchema="monkey-unity-system-fonts/1";const string ExpectedFontRoot="Assets/Game/Content/Fonts/System/";'
    program=r'''
static BindingSet Copy(BindingSet value)=>System.Text.Json.JsonSerializer.Deserialize<BindingSet>(
    System.Text.Json.JsonSerializer.Serialize(value,Options),Options);
static System.Text.Json.JsonSerializerOptions Options=new System.Text.Json.JsonSerializerOptions{IncludeFields=true};
static void Check(BindingSet value){ValidateSpec(value);ValidateReferences(value,value.systemFonts.fonts.ToDictionary(f=>f.assetId));}
static FontSpec Static(BindingSet value)=>value.systemFonts.fonts.Single(f=>f.populationMode=="StaticSDFRequired");
static void Refuse(BindingSet original,Action<BindingSet> change,string code){
    var value=Copy(original);change(value);
    try{Check(value);}catch(InvalidOperationException e){if(e.Message.StartsWith(code,StringComparison.Ordinal))return;throw;}
    throw new Exception("invalid population contract accepted: "+code);
}
static void Main(string[] args){
    var original=System.Text.Json.JsonSerializer.Deserialize<BindingSet>(File.ReadAllText(args[0]),Options);
    Check(original);
    if(args.Length==1){Console.WriteLine("production-contract-pass");return;}
    Refuse(original,v=>v.systemFonts.unityPopulationPolicy="dynamic-if-exact-v1","SYSTEM_FONT_STATIC_SDF_CONTRACT_INVALID");
    Refuse(original,v=>v.systemFonts.unityPopulationPolicy=null,"SYSTEM_FONT_STATIC_SDF_CONTRACT_INVALID");
    Refuse(original,v=>v.systemFonts.unityPopulationPolicy="unknown","SYSTEM_FONT_POPULATION_POLICY_INVALID");
    Refuse(original,v=>Static(v).matchingPhysicalFaces[0].postScriptName="different-face","SYSTEM_FONT_STATIC_SDF_CONTRACT_INVALID");
    Refuse(original,v=>Static(v).matchingPhysicalFaces=null,"SYSTEM_FONT_STATIC_SDF_CONTRACT_INVALID");
    Refuse(original,v=>Static(v).matchingPhysicalFaces=new[]{Static(v).matchingPhysicalFaces[0],Static(v).matchingPhysicalFaces[0]},"SYSTEM_FONT_STATIC_SDF_CONTRACT_INVALID");
    Refuse(original,v=>Static(v).fontFileCopiedOrExported=true,"SYSTEM_FONT_STATIC_SDF_CONTRACT_INVALID");
    Refuse(original,v=>Static(v).targetSystemFontFileSha256="invalid","SYSTEM_FONT_STATIC_SDF_CONTRACT_INVALID");
    Refuse(original,v=>Static(v).role="primary","SYSTEM_FONT_STATIC_SDF_CONTRACT_INVALID");
    Refuse(original,v=>v.systemFonts.sourceOSIdentityVerified=true,"SYSTEM_FONT_SOURCE_BOUNDARY_INVALID");
    var legacy=Copy(original);legacy.systemFonts.unityPopulationPolicy=null;Static(legacy).matchingPhysicalFaces=Array.Empty<PhysicalFace>();Check(legacy);
    Console.WriteLine("population-positive-and-ten-refusals-pass");
}
'''
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'Probe.cs').write_text('using System;using System.IO;using System.Linq;using System.Collections.Generic;class Probe{'+constants+'\n'.join(members)+program+'}')
    (directory/'Probe.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>disable</Nullable><NoWarn>CS0649</NoWarn></PropertyGroup></Project>')
    (directory/'NuGet.Config').write_text('<configuration><packageSources><clear /></packageSources></configuration>')
    restored=subprocess.run([dotnet,'restore',str(directory/'Probe.csproj'),'--configfile',str(directory/'NuGet.Config')],capture_output=True,text=True,timeout=60)
    if restored.returncode:
        raise AssertionError(restored.stdout+restored.stderr)
    return [dotnet,'run','--project',str(directory/'Probe.csproj'),'--no-restore','--']


class UnitySystemFontPopulationContractTests(unittest.TestCase):
    def test_production_validators_accept_explicit_static_identity_and_keep_strict_refusals(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();argv=build_harness(root/'harness')
            ir,receipt=fixture();receipt['unityPopulationPolicy']='coretext-static-fallbacks-v1'
            path=root/'resolution.json';raw=json.dumps(receipt).encode();path.write_bytes(raw)
            binding=prepare(ir,'b'*64,path,hashlib.sha256(raw).hexdigest())
            self.assertEqual(binding.status,'prepared',binding.record)
            path=root/'binding.json';path.write_text(json.dumps(binding.record))
            result=subprocess.run(argv+[str(path),'mutations'],capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('population-positive-and-ten-refusals-pass',result.stdout)
