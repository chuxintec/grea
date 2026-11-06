"""Exercise production static-mask presence/denominator gates without Editor.

Unity JsonUtility observations are pinned separately in the private GREA68
receipt. This managed harness starts after deserialization and does not emulate
or claim Unity JsonUtility behavior.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


ROOT = Path(__file__).resolve().parents[2]


def declaration(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:end]


def source_statement(source, signature):
    start = source.index(signature)
    end = source.index(";", start) + 1
    return source[start:end]


def test_production_presence_denominator_and_legacy_contract_harness():
    dotnet = shutil.which("dotnet")
    if not dotnet:
        pytest.skip("dotnet SDK unavailable")
    source = (ROOT / "src/grea/recovery/targets/UnityStaticMaskIntegration.cs").read_text()
    members = "\n".join(declaration(source, signature) for signature in (
        "[Serializable] public class StaticMaskSourceDefault",
        "[Serializable] public class StaticMaskSourceEngine",
        "[Serializable] public class StaticMaskContract",
        "static string[] StaticMaskSourceIds(",
        "static bool HasStaticMaskContractPayload(",
        "static bool StaticMaskSourceActivity(",
        "static void ValidateStaticMaskContract(",
    ))
    members += "\n" + "\n".join(source_statement(source, signature) for signature in (
        "static bool IsLegacyStaticMaskContract(",
        "static bool HasStaticMasks(",
    ))
    constants = "\n".join(source_statement(source, signature) for signature in (
        "const string StaticMaskContractName=",
        "const string StaticMaskSourceProfile=",
        "const string StaticMaskSourceVersion=",
        "const string StaticMaskSourceEnginePath=",
        "const string StaticMaskSourceEngineSha256=",
        "const string StaticMaskSourceEngineUrl=",
    ))
    program = r'''
static void Require(bool value,string message){if(!value)throw new Exception(message);}
static void Refuse(Plan p,string expected){
    try{ValidateStaticMaskContract(p);}
    catch(InvalidOperationException e){Require(e.Message.StartsWith(expected),"expected "+expected+" got "+e.Message);return;}
    throw new Exception("expected refusal: "+expected);
}
static Plan Source(bool marker,bool includeMask){
    return new Plan{staticMasksPresent=marker,sourceManifestSha256=new string('a',64),
        components=includeMask?new[]{new ComponentSpec{sourceId="mask-source",type="cc.Mask",node="mask-node",
            nativeId="native-mask",enabled=true,maskType=0,inverted=false}}:Array.Empty<ComponentSpec>(),
        nodes=includeMask?new[]{new NodeSpec{sourceId="mask-node",parent=null,active=true}}:Array.Empty<NodeSpec>(),
        staticSortQueue=Array.Empty<ProxyQueueSpec>()};
}
static MaskSpec LegacyRow(){return new MaskSpec{sourceId="mask-source",node="mask-node",nativeId="native-mask",
    sourceOriginId="mask-source",sourceFieldsJson="{}",sourceQueueDisposition="outside-static-sort-queue-scope",
    sourceActiveSelf=true,sourceActive=true,maskType=0,enabled=true,inverted=false,alphaThreshold=.1f,
    sourceDefaultFields=Array.Empty<string>()};}
static StaticMaskContract ModernContract(string sourcePin,MaskSpec[] rows){return new StaticMaskContract{
    schemaVersion=1,contract="monkey-static-mask-continuation/1",sourceManifestSha256=sourcePin,
    sourceProfile="cocos-2.4.15-bundle",sourceVersion="2.4.15",
    sourceEngine=new StaticMaskSourceEngine{path="cocos2d/core/components/CCMask.js",
      sha256="33484e873f07be39fa6433c22819609bc52e51419992ffe8d230d68c453017a6",
      url="https://raw.githubusercontent.com/cocos/cocos-engine/v2.4.15/cocos2d/core/components/CCMask.js"},
    sourceDefaults=Array.Empty<StaticMaskSourceDefault>(),masks=rows};}
static void Main(){
    // Actual GREA68 JsonUtility receipt: absent/null/{} yielded a phantom
    // StaticMaskContract object with schemaVersion=0, masks=null, and in two
    // cases a non-null but all-empty sourceEngine. Marker false treats that
    // empty DTO as absent when the source denominator is zero.
    var absent=Source(false,false);absent.staticMasks=new StaticMaskContract{sourceEngine=new StaticMaskSourceEngine()};
    Require(!HasStaticMasks(absent),"phantom DTO is not a declared mask contract");
    ValidateStaticMaskContract(absent);
    absent.staticMasks=null;ValidateStaticMaskContract(absent);
    var phantomEmptyArrays=Source(false,false);phantomEmptyArrays.staticMasks=new StaticMaskContract{
        sourceEngine=new StaticMaskSourceEngine(),sourceDefaults=Array.Empty<StaticMaskSourceDefault>(),masks=Array.Empty<MaskSpec>()};
    Require(!HasStaticMaskContractPayload(phantomEmptyArrays.staticMasks),"empty arrays do not declare a contract");
    ValidateStaticMaskContract(phantomEmptyArrays);

    // A missing contract is never excused by the absence of a sort queue or by
    // a harmless-looking empty nested JsonUtility DTO when source masks exist.
    var missingRequired=Source(false,true);missingRequired.staticMasks=new StaticMaskContract{sourceEngine=new StaticMaskSourceEngine()};
    Require(!HasStaticMasks(missingRequired),"source mask without declaration is missing");
    Refuse(missingRequired,"STATIC_MASK_CONTRACT_REQUIRED:");
    var declaredButNull=Source(true,false);declaredButNull.staticMasks=null;
    Refuse(declaredButNull,"STATIC_MASK_CONTRACT_DECLARED_BUT_NULL");
    var explicitObject=Source(true,false);explicitObject.staticMasks=new StaticMaskContract();
    Refuse(explicitObject,"STATIC_MASK_CONTRACT_ROWS_MISSING");
    var unmarkedModernPayload=Source(false,false);unmarkedModernPayload.staticMasks=new StaticMaskContract{
        schemaVersion=1,contract="monkey-static-mask-continuation/1"};
    Refuse(unmarkedModernPayload,"STATIC_MASK_CONTRACT_PRESENCE_MARKER_MISMATCH");

    // Preserve explicit legacy schema-1 contracts (including empty contract
    // name) while still joining their exact rows to every source cc.Mask.
    var legacy=Source(false,true);legacy.staticMasks=new StaticMaskContract{schemaVersion=1,
        sourceManifestSha256=legacy.sourceManifestSha256,masks=new[]{LegacyRow()}};
    Require(HasStaticMasks(legacy),"legacy mask rows remain an explicit contract");
    ValidateStaticMaskContract(legacy);
    legacy.staticMasksPresent=true;ValidateStaticMaskContract(legacy);
    legacy.staticMasks.masks=Array.Empty<MaskSpec>();
    Refuse(legacy,"STATIC_MASK_COMPONENT_IDENTITY_DENOMINATOR_MISMATCH");

    // Modern contracts retain profile, source pin, fields and full-row gates.
    var modern=Source(true,true);modern.staticMasks=ModernContract(modern.sourceManifestSha256,new[]{LegacyRow()});
    ValidateStaticMaskContract(modern);
    modern.staticMasks.masks[0].sourceId="different-source";
    Refuse(modern,"STATIC_MASK_COMPONENT_IDENTITY_DENOMINATOR_MISMATCH");
    Console.WriteLine("production static-mask presence and denominator: pass");
}'''
    wrapper = (
        "using System;using System.Collections.Generic;using System.Linq;\n"
        "public static class MonkeyImporter {\n"
        + constants + r'''
public sealed class ComponentSpec { public string sourceId,type,node,nativeId; public bool enabled,inverted; public int maskType; }
public sealed class NodeSpec { public string sourceId,parent; public bool active; }
public sealed class ProxyMaskSpec { public string sourceId,node,nativeId; public bool enabled,inverted; public int maskType; public float alphaThreshold; }
public sealed class ProxyQueueSpec { public ProxyMaskSpec[] masks; }
public sealed class MaskSpec { public string sourceId,node,nativeId,sourceOriginId,sourceFieldsJson,sourceQueueDisposition,sourceMaterialResolution,sourceMaterialResolverPath,sourceMaterialResolverSha256,sourceMaterialId,sourceEffectId; public bool sourceActiveSelf,sourceActive,enabled,inverted; public int maskType; public float alphaThreshold; public string[] sourceDefaultFields; }
public sealed class Plan { public ComponentSpec[] components; public StaticMaskContract staticMasks; public bool staticMasksPresent; public string sourceManifestSha256; public ProxyQueueSpec[] staticSortQueue; public NodeSpec[] nodes; }
''' + members
        + "\n" + program + "\n}")
    with tempfile.TemporaryDirectory() as temporary:
        out = Path(temporary)
        (out / "Probe.cs").write_text(wrapper)
        (out / "Probe.csproj").write_text(
            '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType>'
            '<TargetFramework>net8.0</TargetFramework><Nullable>disable</Nullable></PropertyGroup></Project>')
        (out / "NuGet.Config").write_text("<configuration><packageSources><clear /></packageSources></configuration>")
        result = subprocess.run([dotnet, "run", "--project", str(out / "Probe.csproj"),
            "--property:RestoreConfigFile=" + str(out / "NuGet.Config")],
            capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "production static-mask presence and denominator: pass" in result.stdout


def test_all_static_mask_entrypoints_validate_before_optional_noop():
    source = (ROOT / "src/grea/recovery/targets/UnityStaticMaskIntegration.cs").read_text()
    create = declaration(source, "static void CreateStaticMasks(")
    refresh = declaration(source, "static partial void RefreshOptionalStaticMasksForPrefab(")
    create_prefab = declaration(source, "static void CreateStaticMasksForPrefab(")
    readback = declaration(source, "static MaskReadback[] ReadStaticMasks(")
    assert "ValidateStaticMaskContract(plan);" in create and "if(!HasStaticMasks(plan))return;" in create
    assert "CreateStaticMasksForPrefab(plan,prefab,nodes,sprites);" in refresh
    assert "ValidateStaticMaskContract(plan);" in create_prefab and "if(!HasStaticMasks(plan))return;" in create_prefab
    assert "ValidateStaticMaskContract(plan);" in readback and "if(!HasStaticMasks(plan))return Array.Empty<MaskReadback>();" in readback


@pytest.mark.parametrize("state", ["absent", "null", "empty-object"])
def test_production_export_preserves_optional_mask_presence(tmp_path, state):
    """Transport preserves declarations; an explicit {} is not a valid contract."""
    import json
    from grea.recovery.io import encoded, sha, write_json
    from grea.recovery.targets import unity
    from .test_unity_export_optional_spine_source_sets import _write_plan_stage

    plan_path = _write_plan_stage(tmp_path, scenario="OptionalMaskPresence")
    plan = json.loads(plan_path.read_text())
    if state != "absent":
        plan["staticMasks"] = {} if state == "empty-object" else None
    raw = encoded(plan)
    plan_path.write_bytes(raw)
    write_json(plan_path.parent / "manifest.json", {
        "files": [{"path": "plan.json", "sha256": sha(raw), "bytes": len(raw)}],
    })
    output = tmp_path / "export"
    if state == "empty-object":
        from grea.recovery.sources.compiled import ParseError
        with pytest.raises(ParseError, match="STATIC_MASK_CONTRACT_PRESENCE_MARKER_MISMATCH"):
            unity.export(plan_path, output)
        assert not output.exists()
        return
    unity.export(plan_path, output)
    instruction = json.loads((output / "Assets/Game/Editor/Conversion/import-plan.json").read_text())
    assert instruction["staticMasksPresent"] is (state == "empty-object")
    assert instruction["staticMasks"] == ({} if state == "empty-object" else None)
