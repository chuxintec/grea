"""Run the production pinned source/controlled Canvas context matcher offline."""
from pathlib import Path
import shutil
import subprocess
import tempfile


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


def test_source_evidence_matches_controlled_worldspace_host_without_scaler():
    dotnet = shutil.which("dotnet")
    if not dotnet:
        import pytest
        pytest.skip("dotnet SDK unavailable")
    source = (ROOT / "src/grea/recovery/targets/UnityStaticSpineRendering.cs").read_text()
    signatures = (
        "[Serializable] sealed class StaticSpineCanvasComponentEvidence",
        "[Serializable] sealed class StaticSpineCanvasContextEvidenceRow",
        "[Serializable] sealed class StaticSpineCanvasContextEvidence\n",
        "static string StaticSpineCanvasEvidenceHash(",
        "static bool StaticSpineCanvasContextEvidenceMatches(",
    )
    members = "\n".join(declaration(source, signature) for signature in signatures)
    derived = (ROOT / "src/grea/recovery/targets/UnityStaticSpineRenderingDerived.cs").read_text()
    members += "\n" + declaration(derived, "static bool SpineUnitClose(")
    program = r'''
static void Require(bool good,string message){if(!good)throw new Exception(message);}
static void Main(){
    var e=new StaticSpineCanvasContextEvidence{
        sourceManifestSha256=new string('a',64),renderingPlanSha256=new string('b',64),
        sourceReferencePixelsPerUnit=100,sourceNodeGeometryVerified=true,sourceCanvasContextVerified=true,
        sourceNodeCount=3,
        contexts=new[]{new StaticSpineCanvasContextEvidenceRow{contextIndex=0,
            sourceCanvasRenderMode="ScreenSpaceOverlay",sourceCanvasReferencePixelsPerUnit=100,
            sourceScalerReferencePixelsPerUnit=100,sourceCanvasScalerPresent=true,sourceCanvasPpuMatchesScaler=true}},
        components=new[]{new StaticSpineCanvasComponentEvidence{sourceComponentId="source-component",
            sourceDataAssetId="source-data",sourceCanvasContextIndex=0,sourceCanvasContextVerified=true,
            sourceNodeActive=true,sourceNodeActivityVerified=true,sourceComponentEnabled=true}}};
    e.evidenceSha256=StaticSpineCanvasEvidenceHash(e);
    Require(StaticSpineCanvasContextEvidenceMatches(e,"source-component","source-data",new string('a',64),
        new string('b',64),100,"WorldSpace",true),"paired WorldSpace host with independently captured 100 PPU");
    Require(!StaticSpineCanvasContextEvidenceMatches(e,"source-component","source-data",new string('a',64),
        new string('b',64),99,"WorldSpace",true),"host PPU drift");
    Require(!StaticSpineCanvasContextEvidenceMatches(e,"other-component","source-data",new string('a',64),
        new string('b',64),100,"WorldSpace",true),"wrong source component");
    Require(!StaticSpineCanvasContextEvidenceMatches(e,"source-component","other-data",new string('a',64),
        new string('b',64),100,"WorldSpace",true),"wrong source data identity");
    Require(!StaticSpineCanvasContextEvidenceMatches(e,"source-component","source-data",new string('c',64),
        new string('b',64),100,"WorldSpace",true),"wrong source manifest pin");
    Require(!StaticSpineCanvasContextEvidenceMatches(e,"source-component","source-data",new string('a',64),
        new string('d',64),100,"WorldSpace",true),"wrong rendering file pin");
    Require(!StaticSpineCanvasContextEvidenceMatches(e,"source-component","source-data",new string('a',64),
        new string('b',64),100,"ScreenSpaceOverlay",true),"unowned host mode");
    Require(!StaticSpineCanvasContextEvidenceMatches(e,"source-component","source-data",new string('a',64),
        new string('b',64),100,"WorldSpace",false),"unexpected CanvasScaler on controlled host");
    e.sourceReferencePixelsPerUnit=80;
    Require(!StaticSpineCanvasContextEvidenceMatches(e,"source-component","source-data",new string('a',64),
        new string('b',64),100,"WorldSpace",true),"tampered source evidence hash");
    e.sourceReferencePixelsPerUnit=100;e.evidenceSha256=StaticSpineCanvasEvidenceHash(e);
    e.components[0].sourceNodeActivityVerified=false;
    e.evidenceSha256=StaticSpineCanvasEvidenceHash(e);
    Require(!StaticSpineCanvasContextEvidenceMatches(e,"source-component","source-data",new string('a',64),
        new string('b',64),100,"WorldSpace",true),"unverified source activity");
    Console.WriteLine("production Spine Canvas evidence: pass");
}'''
    unity_stubs = r'''
namespace UnityEngine {
 public enum RenderMode { ScreenSpaceOverlay, ScreenSpaceCamera, WorldSpace }
 public static class JsonUtility {
  public static T FromJson<T>(string raw) => System.Text.Json.JsonSerializer.Deserialize<T>(raw,
   new System.Text.Json.JsonSerializerOptions{IncludeFields=true});
  public static string ToJson(object value) => System.Text.Json.JsonSerializer.Serialize(value,
   new System.Text.Json.JsonSerializerOptions{IncludeFields=true});
 }
}
'''
    wrapper = "using System;using System.Linq;using System.Security.Cryptography;using System.Text;using UnityEngine;\n" + unity_stubs + "\nstatic class Probe {\n" + members + "\n" + program + "\n}"
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp)
        (out / "Probe.cs").write_text(wrapper)
        (out / "Probe.csproj").write_text(
            '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType>'
            '<TargetFramework>net8.0</TargetFramework><Nullable>disable</Nullable></PropertyGroup></Project>')
        (out / "NuGet.Config").write_text("<configuration><packageSources><clear /></packageSources></configuration>")
        result = subprocess.run([dotnet, "run", "--project", str(out / "Probe.csproj"),
            "--property:RestoreConfigFile=" + str(out / "NuGet.Config")],
            capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "production Spine Canvas evidence: pass" in result.stdout


def test_controlled_owner_binding_is_scoped_and_never_changes_activity():
    source = (ROOT / "src/grea/recovery/targets/UnityStaticSpineRendering.cs").read_text()
    binder = declaration(source, "public static void RegisterStaticSpineReadbackOwnerContext(")
    proof = declaration(source, "static bool TryGetStaticSpineSourceCanvasProof(")
    writer = declaration(source, "static void WriteStaticSpineRenderingReadback(")
    bridge = (ROOT / "src/grea/recovery/targets/UnityStaticSortSpineBinding.cs").read_text()
    assert "persistentNodes.TryGetValue" in binder and "loadedNodes.TryGetValue" in binder
    assert "persistentComponents[0].SkeletonDataAsset != dataAsset" in binder
    assert "loadedComponents[0].SkeletonDataAsset != dataAsset" in binder
    assert "persistentNode.activeSelf != nodeExpected.active" in binder
    assert "loadedNode.activeSelf != nodeExpected.active" in binder
    assert ".activeSelf =" not in binder and ".enabled =" not in binder
    assert "row.persistentOwner == graphic" in proof and "row.loadedOwner == graphic" in proof
    assert "controlled.canvas" in proof and "GetComponent<CanvasScaler>() == null" in proof
    assert 'StaticSpineCanvasContextEvidencePath = "Analysis/Readback/SpineRendering/source-canvas-context.json"' in source
    assert "File.WriteAllBytes(contextPath, contextBytes)" in writer
    assert "sourceCanvasContextEvidenceFileSha256=contextFileSha" in writer
    assert "sourceCanvasContext=staticSpineSourceCanvasContext" in writer
    assert "controlledHostContextEvidence=hostEvidence" in source
    assert "sourceNodeActivityVerified" in source and "sourceComponentEnabled = component.sourceComponentEnabled" in source
    assert "TryGetStaticSpineSourceCanvasProof(sourceOwner" in bridge
    assert "canvas.referencePixelsPerUnit /" not in bridge
    assert "dataScale" not in bridge
