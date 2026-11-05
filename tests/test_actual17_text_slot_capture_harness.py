"""Offline harness for the production text-slot lifecycle against actual17 inventory.

Unity/TMP objects are represented by deterministic providers. The checked
production call chain and lifecycle hash/denominator code are extracted from
the current C# source, while the fixture supplies only source identities and
the previously observed slot inventory. It does not claim TMP rendering or
Editor persistence was executed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / ".private/foodstreet-four-activity-20261104/dev23-text-slot-lifecycle/actual17-text-lifecycle-inventory.json"
DEFAULT_ACTUAL18_FAILURE = ROOT / ".private/foodstreet-four-activity-20261104/dev24-text-context-capture/actual18-text-context-failure.json"
DEFAULT_SAVED_TEXT_CONTEXTS = ROOT / ".private/foodstreet-four-activity-20261104/dev24-text-context-capture/actual17-saved-text-contexts.json"


def _declaration(source: str, signature: str) -> str:
    start = source.index(signature)
    opening = source.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
        end += 1
    return source[start:end]


def _member(source: str, signature: str) -> str:
    """Extract a block or expression-bodied C# member without consuming its neighbors."""
    start = source.index(signature)
    arrow = source.find("=>", start)
    opening = source.find("{", start)
    if arrow >= 0 and (opening < 0 or arrow < opening):
        return source[start:source.index(";", arrow) + 1]
    return _declaration(source, signature)


def _inventory_path() -> Path:
    return Path(os.environ.get("MONKEY_ACTUAL17_TEXT_INVENTORY", DEFAULT_INVENTORY))


def _inventory():
    path = _inventory_path()
    if not path.is_file():
        pytest.skip("actual17 read-only inventory fixture is not present")
    return path, json.loads(path.read_text(encoding="utf-8"))


def _verify_readonly_pins(inv):
    failures = []
    for pin in inv["pins"]:
        path = Path(pin["path"])
        if not path.is_file():
            failures.append((str(path), "missing"))
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != pin["sha256"]:
            failures.append((str(path), digest))
    return failures


def _verify_actual18_pins(fixture):
    failures = []
    for pin in fixture["inputPins"]:
        path = Path(pin["path"])
        if not path.is_file():
            failures.append((str(path), "missing"))
        elif hashlib.sha256(path.read_bytes()).hexdigest() != pin["sha256"]:
            failures.append((str(path), "changed"))
    return failures


def _normalize_saved_context_fixture(source: Path, output: Path):
    """Decode Unity YAML bool/int-array scalar forms for the in-memory DTO adapter."""
    fixture = json.loads(source.read_text(encoding="utf-8"))
    bool_fields = (
        "worldCameraAssigned", "ownerAutoSizing", "textLineBoxPresent", "textLineBoxActive",
        "contentSizeFitterPresent", "contentSizeFitterActive", "textLineBoxHeightProvenanceVerified",
        "autoSizing", "extraPadding", "richText", "parseControlCharacters", "rightToLeft",
        "useMaxVisibleDescender", "visible", "usingAlternateTypeface",
    )
    rows = []
    for row in fixture["rows"]:
        context = json.loads(json.dumps(row["textScaleContext"]))
        for field in bool_fields:
            if field in context:
                context[field] = bool(context[field])
            if field in context.get("textLayoutInputs", {}):
                context["textLayoutInputs"][field] = bool(context["textLayoutInputs"][field])
        raw_features = context["textLayoutInputs"].get("fontFeatures")
        if isinstance(raw_features, str) and raw_features.endswith("i"):
            raw_hex = raw_features[:-1]
            if not raw_hex or len(raw_hex) % 2:
                raise ValueError(f"unsupported Unity packed fontFeatures value: {raw_features}")
            context["textLayoutInputs"]["fontFeatures"] = [int.from_bytes(bytes.fromhex(raw_hex), "little", signed=True)]
        elif raw_features is None:
            context["textLayoutInputs"]["fontFeatures"] = []
        elif not isinstance(raw_features, list):
            raise ValueError(f"unsupported fontFeatures shape: {type(raw_features).__name__}")
        authored_height = context["textLayoutInputs"].get("textLineBoxAuthoredPreferredHeight")
        if authored_height is not None and not isinstance(authored_height, str):
            context["textLayoutInputs"]["textLineBoxAuthoredPreferredHeight"] = format(float(authored_height), ".17g")
        for character in context.get("characters", []):
            for field in ("visible", "usingAlternateTypeface"):
                character[field] = bool(character[field])
        rows.append({"sourceComponentId": row["sourceComponentId"], "materialSlot": row["materialSlot"],
                     "textScaleContext": context})
    output.write_text(json.dumps({"contract": "monkey-actual17-context-operands-adapter/1",
                                  "sourceFixtureSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                                  "fontFeaturesDecode": "Unity little-endian signed int32 bytes plus i postfix",
                                  "storedEvidenceHashesAreNotUsedAsCurrentEvidence": True,
                                  "rows": rows}, indent=2) + "\n", encoding="utf-8")


def _csharp_program(proxy_source: str, text_source: str, native_source: str) -> str:
    capture_method = _declaration(proxy_source, "static List<TextSlotBinding> CaptureAndRebindTextSlots(")
    proxy_helpers = "\n".join(_declaration(proxy_source, s) for s in (
        "static bool CaptureOwnerSourceStateMatches(",
        "static KeyValuePair<string, long> CapturePersistentUnityIdentity(",
        "static string IdentitySummary(",
        "static bool TextBindingPersistentReferencesVerified(",
        "static bool CapturedTextSlotSourceIdentityMatches(",
        "static string TextSlotBindingSummary(",
        "static InvalidOperationException TextSlotCaptureRefusal(",
        "static string TextSlotEnumerationSummary(",
        "static void ValidateTextSlotEnumeration(",
        "static bool SameTextSlotEnumeration(",
        "static bool IsExactEmptyTextSource(",
    ))
    # These are the production lifecycle builder, verifier and source-denominator
    # methods. The harness provider supplies only TMP/Unity object operations.
    text_methods = "\n".join(_member(text_source, s) for s in (
        "static string HashText(",
        "static NativeStaticSortTextLayoutEvidence TextLayoutEvidence(",
        "static decimal? DecimalFloat(",
        "static string TextLineBoxSemanticHeight(",
        "static bool HasVerifiedTextLineBoxHeight(",
        "static string TextLayoutEvidenceSha256(",
        "static string FloatEvidence(",
        "static bool Finite(",
        "static void AppendVector(",
        "static int UvDimension(",
        "static bool TryBuildTextScaleContext(",
        "static bool IsValidTextScaleContext(",
        "static bool TextScaleContextUvMatchesMesh(",
        "static float ComputeTmpUvScale(",
        "static bool VerifyTextScaleFormulaAgainstMesh(",
        "public static bool CaptureCurrentTextScaleContext(",
        "public static string MeshFingerprint(",
        "public static NativeStaticSortTextCaptureLifecycle BeginCaptureLifecycle(",
        "public static NativeStaticSortTextCapturePhase CaptureLifecyclePhase(",
        "public static void AppendCaptureLifecyclePhase(",
        "static NativeStaticSortTextCaptureSlot CaptureLifecycleSlot(",
        "public static bool TextSlotDenominatorMatches(",
        "public static int[] TextSlotDrawableIds(",
        "static string TextSlotEvidenceSummary(",
        "public static bool TextLayoutContextMatches(",
        "static string TextLayoutEvidenceDifference(",
        "public static bool ValidateCapturedSlotTransition(",
        "static string SlotBindingTransitionSummary(",
        "public static bool CaptureLifecycleReadyForRebind(",
        "public static string CaptureLifecycleHash(",
        "public static bool ValidateCaptureLifecycle(",
        "static bool CapturePhaseSlotsMatchEnumeration(",
        "public static bool FinalizeCaptureLifecycle(",
        "static bool PersistentAsset(",
        "static string TextSlotRowHash(",
        "static string TextSlotEnumerationHash(",
        "static bool IsValidTextSlotEnumeration(",
        "static bool IsSha256(",
    ))
    native_types = "\n".join(_declaration(native_source, s) for s in (
        "public sealed class NativeStaticSortTextSlotEvidence",
        "public sealed class NativeStaticSortTextSlotEnumeration",
        "public sealed class NativeStaticSortTextCaptureLifecycle",
        "public sealed class NativeStaticSortTextCapturePhase",
        "public sealed class NativeStaticSortTextCaptureSlot",
        "public sealed class NativeStaticSortTextScaleContext",
        "public sealed class NativeStaticSortTextLayoutEvidence",
        "public sealed class NativeStaticSortTextScaleCharacter",
    ))
    return r'''#nullable disable
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Reflection;
using Monkey.StaticSortQueueProxy;
using Monkey.StaticMaskSort;
using TMPro;
using UnityEngine;
using UnityEditor;
using UnityEngine.UI;
using UnityEngine.Rendering;

namespace Monkey.StaticSortQueueProxy {
''' + native_types + r'''
public sealed class TextSlotBinding {
 public string sourceComponentId,sourceTextSha256,textInfoCharacterEvidenceSha256,textInfoCharacterAssetEvidenceSha256,
  textInfoCharacterMaterialFingerprint,sourceMeshSha256,sourceTextureGuid,sourceMaterialGuid,sourceShaderGuid,
  fontAssetGuid,spriteAssetGuid,ownerFontMaterialGuid,ownerFontMaterialFingerprint,fallbackFontAssetGuid,
  fallbackFontMaterialGuid,fallbackFontMaterialFingerprint,fallbackAtlasGuid,transientFallbackFingerprint,
  sourceMaterialFingerprint,proxyMaterialFingerprint,proxyMaterialGuid,bakedProxyMaterialFingerprint,bakedProxyMaterialGuid;
 public long sourceTextureLocalFileId,sourceMaterialLocalFileId,sourceShaderLocalFileId,fontAssetLocalFileId,
  spriteAssetLocalFileId,ownerFontMaterialLocalFileId,fallbackFontAssetLocalFileId,fallbackFontMaterialLocalFileId,
  fallbackAtlasLocalFileId,proxyMaterialLocalFileId,bakedProxyMaterialLocalFileId;
 public int materialSlot,textInfoCharacterCount,textInfoVisibleCharacterCount;
 public uint textInfoTriangleIndexCount,canvasTriangleIndexCount;
 public bool generatedSubmesh,sourceGraphicEnabled=true,sourceGraphicActiveSelf=true,textInfoMaterialMissing,
  tmpFallbackMaterialBaked,requiresPersistentFallbackRegistration,persistentFallbackVariantRegistered,
  textInfoCharacterSlotVerified=true,textInfoCharacterMaterialVerified=true,textInfoFontAssetVerified=true,textInfoAtlasVerified=true;
 public string tmpFallbackAlgorithm;
 public TMP_Text owner; public Graphic sourceGraphic; public Mesh sourceMesh;
 public TMP_FontAsset fontAsset,fallbackFontAsset; public TMP_SpriteAsset spriteAsset;
 public Material ownerFontSharedMaterial,fallbackFontMaterial,sourceMaterial,proxyMaterial;
 public Texture sourceTexture; public NativeStaticSortTextSlotEnumeration textSlotEnumeration;
 public NativeStaticSortTextCaptureLifecycle captureLifecycle; public object ownerStyle;
 public NativeStaticSortTextScaleContext currentTextScaleContext;
 public TextSlotBinding Copy()=>(TextSlotBinding)MemberwiseClone();
}
public sealed class OwnerFontStyleDescriptor {}
public sealed class ProxyQueueSpec { public string meshAssetFolder="Assets/Generated"; }
public sealed class ProxyRendererSpec {
 public string sourceComponentId,sourceText,nativeTextExpectation; public bool sourceTextEmpty;
}

static class UnityStaticSortTextSource {
 const string TEXT_SLOT_ENUMERATION_CONTRACT_V2="monkey-static-sort-text-slot-enumeration/2";
 const string TEXT_SLOT_EVIDENCE_CONTRACT_V2="monkey-static-sort-text-slot-evidence/2";
 static readonly FieldInfo CharacterWidthAdjustmentField=typeof(TMP_Text).GetField("m_charWidthAdjDelta",BindingFlags.Instance|BindingFlags.NonPublic);
 static readonly FieldInfo CharacterHorizontalScaleField=typeof(TMP_Text).GetField("m_characterHorizontalScale",BindingFlags.Instance|BindingFlags.NonPublic);
 public static int PrepareCalls, CaptureCalls, RegisterCalls, RebindCalls;
 public static bool failRegistration, driftText, driftAtlas, driftCharacters, driftFont, driftLayout, driftMesh, driftMaterial, driftCount, driftScale;
 public static bool skipContextCapture;
 public static void ResetProvider(){PrepareCalls=CaptureCalls=RegisterCalls=RebindCalls=0;failRegistration=driftText=driftAtlas=driftCharacters=driftFont=driftLayout=driftMesh=driftMaterial=driftCount=driftScale=skipContextCapture=false;}
 public static bool GetCurrentSlots(TMP_Text owner,string sid,out List<TextSlotBinding> slots,
   out NativeStaticSortTextSlotEnumeration enumeration,out string diagnostic) {
   slots=owner.finalSnapshot?owner.finalBindings:owner.bindings; enumeration=owner.finalSnapshot?owner.finalEnumeration:owner.enumeration; diagnostic=null;
   if(owner.finalSnapshot && owner.driftSlotCount) { enumeration=CloneEnum(enumeration); enumeration.slotCount++; enumeration.rows=enumeration.rows.Concat(new[]{enumeration.rows.Last()}).ToArray(); Rehash(enumeration); }
   if(owner.finalSnapshot && driftText) enumeration=CloneEnum(enumeration,new string('0',64));
   if(owner.finalSnapshot && (driftAtlas||driftCharacters||driftFont)) {
    enumeration=CloneEnum(enumeration);
    if(driftAtlas) enumeration.rows[0].atlasGuid="foreign-atlas";
    if(driftCharacters) enumeration.rows[0].characterAssetEvidenceSha256=new string('0',64);
    if(driftFont) enumeration.rows[0].sourceAssetGuid="foreign-font";
    Rehash(enumeration);
   }
   if(owner.finalSnapshot && (driftLayout||driftMesh||driftMaterial)) {
    slots=owner.finalBindings;
    foreach(var b in slots.Where(x=>x!=null)) {
     if(driftMesh)b.sourceMeshSha256=new string('d',64);
     if(driftMaterial)b.sourceMaterialFingerprint=new string('e',64);
    }
    enumeration=CloneEnum(enumeration);
    foreach(var b in slots.Where(x=>x!=null)){if(driftMesh)enumeration.rows[b.materialSlot].sourceMeshSha256=b.sourceMeshSha256;if(driftMaterial)enumeration.rows[b.materialSlot].sourceGraphicMaterialFingerprint=b.sourceMaterialFingerprint;}
    Rehash(enumeration);
   }
   if(owner.finalSnapshot&&driftLayout&&!owner.layoutGeometryDrifted){((RectTransform)owner.transform).rect.width+=1;owner.layoutGeometryDrifted=true;}
   if(owner.finalSnapshot&&driftScale){
    foreach(var b in slots.Where(x=>x!=null)){
     var character=owner.textInfo.characterInfo.First(x=>x.materialReferenceIndex==b.materialSlot&&x.isVisible);character.scale+=0.125f;
     var formulaCharacter=new NativeStaticSortTextScaleCharacter{scale=character.scale,usingAlternateTypeface=character.isUsingAlternateTypeface,fontStyle=(int)character.style,textElementType=(int)character.elementType};
     var formula=typeof(UnityStaticSortTextSource).GetMethod("ComputeTmpUvScale",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,new object[]{formulaCharacter,0f,1f,(int)owner.canvas.renderMode,owner.canvas.worldCamera!=null,owner.transform.lossyScale.y,owner.canvas.scaleFactor});
     for(int vertex=character.vertexIndex;vertex<character.vertexIndex+4;vertex++){var uv=b.sourceMesh.uv0[vertex];uv.w=(float)formula;b.sourceMesh.uv0[vertex]=uv;}
     b.sourceMeshSha256=UnityStaticSortTextSource.MeshFingerprint(b.sourceMesh);enumeration.rows[b.materialSlot].sourceMeshSha256=b.sourceMeshSha256;
    }
    Rehash(enumeration);
   }
   foreach(var b in slots.Where(x=>x!=null))b.textSlotEnumeration=enumeration;
  if(!skipContextCapture)foreach(var binding in slots)if(!CaptureCurrentTextScaleContext(binding,out diagnostic))return false;
   return true;
 }
 public static bool PrepareSource(TMP_Text owner,string sid,out string d) { PrepareCalls++; if(owner.finalEnumeration!=null){owner.finalSnapshot=true;foreach(var b in owner.finalBindings.Where(x=>x!=null))b.textSlotEnumeration=owner.finalEnumeration;if(driftLayout&&!owner.layoutGeometryDrifted){((RectTransform)owner.transform).rect.width+=1;owner.layoutGeometryDrifted=true;}} d=null; return true; }
 public static bool CaptureFallbackMaterialProfile(TextSlotBinding b,string path,out string d) {
   CaptureCalls++; b.tmpFallbackMaterialBaked=true; b.requiresPersistentFallbackRegistration=true;
   b.transientFallbackFingerprint=b.sourceMaterialFingerprint;
   b.bakedProxyMaterialGuid=HashText("baked|"+b.sourceComponentId+"|"+b.materialSlot).Substring(0,32); b.bakedProxyMaterialLocalFileId=100+b.materialSlot;
   b.bakedProxyMaterialFingerprint=b.transientFallbackFingerprint;
   b.proxyMaterial=new Material{guid=b.bakedProxyMaterialGuid,localFileId=b.bakedProxyMaterialLocalFileId,assetPath="Assets/baked.mat",fingerprint=b.bakedProxyMaterialFingerprint}; d=null; return true;
 }
 public static bool RegisterCapturedFallbackVariant(TextSlotBinding b,out string d) {
   RegisterCalls++; d=failRegistration?"injected registration failure":null;
   if(failRegistration)return false; b.requiresPersistentFallbackRegistration=false; b.persistentFallbackVariantRegistered=true;
   var next=b.Copy(); next.sourceMaterial=b.proxyMaterial; next.sourceMaterialGuid=b.bakedProxyMaterialGuid;
   next.sourceMaterialLocalFileId=b.bakedProxyMaterialLocalFileId; next.sourceMaterialFingerprint=b.bakedProxyMaterialFingerprint;
   next.textSlotEnumeration=null; var bindingIndex=b.owner.finalBindings.FindIndex(x=>x!=null&&x.materialSlot==b.materialSlot);b.owner.finalBindings[bindingIndex]=next;
   var e=CloneEnum(b.owner.finalEnumeration??b.owner.enumeration);
   var r=e.rows[b.materialSlot];r.sourceGraphicMaterialGuid=b.bakedProxyMaterialGuid;
   r.sourceGraphicMaterialLocalFileId=b.bakedProxyMaterialLocalFileId;r.sourceGraphicMaterialFingerprint=b.bakedProxyMaterialFingerprint;
   Rehash(e);b.owner.finalEnumeration=e;return true;
 }
 public static bool RebindCapturedSlot(TextSlotBinding captured,TMP_Text owner,Graphic graphic,out TextSlotBinding rebound,out string d) {
   RebindCalls++; GetCurrentSlots(owner,captured.sourceComponentId,out var rows,out var e,out d);
   var current=rows.SingleOrDefault(x=>x.materialSlot==captured.materialSlot);
   if(current==null||!VerifyTextScaleFormulaAgainstMesh(captured.currentTextScaleContext,captured.sourceMesh,out d)||
      !VerifyTextScaleFormulaAgainstMesh(current.currentTextScaleContext,current.sourceMesh,out d)||
      !ValidateCapturedSlotTransition(captured,current,e,out d)){rebound=null;return false;}
   rebound=current;return true;
 }
''' + text_methods + r'''
 static string MaterialFingerprint(Material m)=>m==null?null:m.fingerprint;
 static bool AssetIdentity(UnityEngine.Object o,out string g,out long id) { g=o?.guid;id=o?.localFileId??0;return o!=null&&!String.IsNullOrWhiteSpace(g)&&id!=0; }
 static bool Fail(string s,out string d){d=s;return false;}
 static NativeStaticSortTextSlotEnumeration CloneEnum(NativeStaticSortTextSlotEnumeration e,string sourceTextSha256=null){var x=JsonSerializer.Deserialize<NativeStaticSortTextSlotEnumeration>(JsonSerializer.Serialize(e,new JsonSerializerOptions{IncludeFields=true}),new JsonSerializerOptions{IncludeFields=true});if(sourceTextSha256!=null)x.sourceTextSha256=sourceTextSha256;Rehash(x);return x;}
 static void Rehash(NativeStaticSortTextSlotEnumeration e){foreach(var r in e.rows)r.evidenceSha256=TextSlotRowHash(r);e.evidenceSha256=TextSlotEnumerationHash(e);}
}

static class ProxyHarness {
 static string HashText(string s){using var sha=SHA256.Create();return Convert.ToHexString(sha.ComputeHash(Encoding.UTF8.GetBytes(s??""))).ToLowerInvariant();}
 static void WriteTextSlotCaptureFailure(string code,string sourceComponentId,string phase,string sourceTextSha256,string diagnostic,NativeStaticSortTextSlotEnumeration initial,NativeStaticSortTextSlotEnumeration current,NativeStaticSortTextCaptureLifecycle lifecycle){}

''' + proxy_helpers + r'''
''' + capture_method + r'''
 public static List<TextSlotBinding> Run(ProxyQueueSpec s,ProxyRendererSpec r,TMP_Text o,out NativeStaticSortTextSlotEnumeration e)=>CaptureAndRebindTextSlots(s,r,o,null,out e);
}

class Program {
 static void Need(bool x,string m){if(!x)throw new Exception(m);}
 static string H(string s){using var sha=SHA256.Create();return Convert.ToHexString(sha.ComputeHash(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();}
 static string GuidFor(string s)=>H("guid|"+s).Substring(0,32);
 static Dictionary<string,Dictionary<int,NativeStaticSortTextScaleContext>> ObservedContexts=new();
 static int modeledUnobservedCharacterPlaceholders=0;
 static object Refusal(string name,Action configure,string expected,string sid,string text){
  UnityStaticSortTextSource.ResetProvider();configure();var owner=Owner(sid,text,1,new[]{0},new[]{1},new[]{1},GuidFor("font|"+sid),GuidFor("atlas|"+sid),H("characters|"+sid));owner.driftSlotCount=UnityStaticSortTextSource.driftCount;
  try{ProxyHarness.Run(new ProxyQueueSpec(),new ProxyRendererSpec{sourceComponentId=sid,sourceText=text},owner,out _);throw new Exception("expected refusal did not occur: "+name);}
  catch(InvalidOperationException ex){if(!ex.Message.Contains(expected,StringComparison.Ordinal))throw new Exception("wrong refusal for "+name+": "+ex.Message);return new{name,refusal=expected};}
 }
 static NativeStaticSortTextSlotEnumeration MakeEnum(string sid,string text,int count,int[] drawableSlots,int[] charCounts,int[] visibleCounts,string asset,string atlas,string charAsset) {
  var e=new NativeStaticSortTextSlotEnumeration{evidenceContract="monkey-static-sort-text-slot-enumeration/2",sourceComponentId=sid,sourceTextSha256=H(text),slotCount=count,verified=true,rows=new NativeStaticSortTextSlotEvidence[count]};
  for(int i=0;i<count;i++){bool draw=drawableSlots.Contains(i);int chars=charCounts[i],visible=visibleCounts[i];var r=e.rows[i]=new NativeStaticSortTextSlotEvidence{evidenceContract="monkey-static-sort-text-slot-evidence/2",slot=i,characterReferences=chars,visibleCharacterReferences=visible,disposition=draw?"drawable":"empty-placeholder",sourceAssetKind="font",sourceAssetGuid=asset,sourceAssetLocalFileId=101,atlasGuid=atlas,atlasLocalFileId=200+i,characterEvidenceSha256=H(sid+"c"+i),characterAssetEvidenceSha256=charAsset,sourceMeshSha256=draw?H(sid+"m"+i):null,textInfoVertexCount=visible*4,textInfoTriangleIndexCount=(uint)(visible*6),textInfoNondegenerateTriangleCount=visible*2,canvasVertexCount=visible*4,canvasTriangleIndexCount=(uint)(visible*6),canvasNondegenerateTriangleCount=visible*2,sourceGraphicMaterialGuid=GuidFor("source-mat|"+sid+"|"+i),sourceGraphicMaterialLocalFileId=300+i,textInfoMaterialGuid=GuidFor("text-mat|"+sid+"|"+i),textInfoMaterialLocalFileId=400+i,sourceShaderGuid=GuidFor("shader|"+sid),sourceShaderLocalFileId=1,sourceTextureGuid=atlas,sourceTextureLocalFileId=200+i,sourceGraphicMaterialFingerprint=H("sm"+sid+"|"+i),textInfoMaterialFingerprint=H("tm"+i)};}
  foreach(var r in e.rows)r.evidenceSha256=typeof(UnityStaticSortTextSource).GetMethod("TextSlotRowHash",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,new object[]{r}).ToString();
  var hash=typeof(UnityStaticSortTextSource).GetMethod("TextSlotEnumerationHash",BindingFlags.NonPublic|BindingFlags.Static);e.evidenceSha256=hash.Invoke(null,new object[]{e}).ToString();return e;
 }
 static Mesh MakeMesh(int visible)=>MakeMesh(Enumerable.Repeat(1f,visible*4).ToArray());
 static Mesh MakeMesh(float[] observedW){int vertexCount=observedW.Length;var triangles=new List<int>();for(int i=0;i+3<vertexCount;i+=4)triangles.AddRange(new[]{i,i+1,i+2,i+2,i+1,i+3});return new Mesh{vertexCount=vertexCount,subMeshCount=1,vertices=Enumerable.Range(0,vertexCount).Select(i=>new Vector3(i%2,i/2,0)).ToArray(),colors32=Enumerable.Range(0,vertexCount).Select(i=>new Color32{r=255,g=255,b=255,a=255}).ToArray(),normals=Enumerable.Range(0,vertexCount).Select(i=>new Vector3(0,0,-1)).ToArray(),tangents=Enumerable.Range(0,vertexCount).Select(i=>new Vector4{w=1}).ToArray(),uv0=Enumerable.Range(0,vertexCount).Select(i=>new Vector4{x=(i%2),y=(i/2)%2,w=observedW[i]}).ToArray(),triangles=triangles.ToArray()};}
 static TMP_Text Owner(string sid,string text,int slots,int[] drawableSlots,int[] charCounts,int[] visibleCounts,string asset,string atlas,string chars,Dictionary<int,NativeStaticSortTextScaleContext> actualContexts=null) {
  var font=new TMP_FontAsset{guid=asset,localFileId=101,assetPath="Assets/font.asset"};var mat=new Material{guid=GuidFor("font-mat|"+sid),localFileId=102,assetPath="Assets/font.mat",fingerprint=H("fm|"+sid)};
  var seed=actualContexts?.Values.FirstOrDefault();var layout=seed?.textLayoutInputs;
  var owner=new TextMeshProUGUI{text=text,font=font,fontSharedMaterial=mat,bindings=new List<TextSlotBinding>(),finalBindings=new List<TextSlotBinding>(),canvas=new Canvas{renderMode=(RenderMode)(seed?.canvasRenderMode??(int)RenderMode.ScreenSpaceOverlay),scaleFactor=seed?.canvasScaleFactor??1f,worldCamera=(seed!=null&&seed.worldCameraAssigned?new UnityEngine.Object():null)},transform=new RectTransform{rect=new Rect(layout?.rectSize.x??100f,layout?.rectSize.y??28f),pivot=layout==null?new Vector2(.5f,.5f):new Vector2(layout.pivot.x,layout.pivot.y),lossyScale=new Vector3(1,seed?.ownerLossyScaleY??1f,1)}};
  if(seed!=null)owner.transform.lossyScale=new Vector3(1,seed.ownerLossyScaleY,1);
  if(seed!=null){owner.margin=layout.margin;owner.fontSize=seed.ownerFontSize;owner.fontSizeMin=seed.ownerFontSizeMin;owner.fontSizeMax=seed.ownerFontSizeMax;owner.fontStyle=(FontStyles)seed.ownerFontStyle;owner.enableAutoSizing=seed.ownerAutoSizing;owner.fontWeight=layout.fontWeight;owner.alignment=layout.alignment;owner.textWrappingMode=layout.wrappingMode;owner.overflowMode=layout.overflowMode;owner.maxVisibleCharacters=layout.maxVisibleCharacters;owner.maxVisibleWords=layout.maxVisibleWords;owner.maxVisibleLines=layout.maxVisibleLines;owner.pageToDisplay=layout.pageToDisplay;owner.characterSpacing=layout.characterSpacing;owner.wordSpacing=layout.wordSpacing;owner.lineSpacing=layout.lineSpacing;owner.lineSpacingAdjustment=layout.lineSpacingAdjustment;owner.paragraphSpacing=layout.paragraphSpacing;owner.extraPadding=layout.extraPadding;owner.richText=layout.richText;owner.parseCtrlCharacters=layout.parseControlCharacters;owner.isRightToLeftText=layout.rightToLeft;owner.useMaxVisibleDescender=layout.useMaxVisibleDescender;owner.fontFeatures=layout.fontFeatures??Array.Empty<int>();owner.SetScaleInternals(seed.charWidthAdjustmentDelta,seed.characterHorizontalScale);owner.textInfo.lineCount=layout.textLineBoxLineCount;if(layout.textLineBoxPresent)owner.lineBox=new Monkey.StaticMaskSort.NativeTextLineBox{LineHeight=layout.textLineBoxLineHeight,ExtraLineFraction=layout.textLineBoxExtraLineFraction,preferredHeight=layout.textLineBoxNativePreferredHeight,isActiveAndEnabled=layout.textLineBoxActive};if(layout.contentSizeFitterPresent)owner.fitter=new ContentSizeFitter{horizontalFit=(ContentSizeFitter.FitMode)layout.contentSizeFitterHorizontalFit,verticalFit=(ContentSizeFitter.FitMode)layout.contentSizeFitterVerticalFit,isActiveAndEnabled=layout.contentSizeFitterActive};}
  owner.enumeration=MakeEnum(sid,text,slots,drawableSlots,charCounts,visibleCounts,asset,atlas,chars);owner.textInfo.materialCount=slots;owner.textInfo.lineCount=layout?.textLineBoxLineCount??1;
  var characters=new List<TMP_CharacterInfo>();if(actualContexts!=null){foreach(var context in actualContexts.Values)foreach(var c in context.characters)characters.Add(new TMP_CharacterInfo{characterIndex=c.characterIndex,materialReferenceIndex=c.materialSlot,vertexIndex=c.vertexIndex,character=c.unicode<=65535?(char)c.unicode:'?',textElement=new TMP_TextElement{unicode=(uint)c.unicode},scale=c.scale,isVisible=c.visible,elementType=(TMP_TextElementType)c.textElementType,style=(FontStyles)c.fontStyle,isUsingAlternateTypeface=c.usingAlternateTypeface});characters=characters.OrderBy(x=>x.characterIndex).ToList();}
  else for(int slot=0;slot<slots;slot++)for(int ci=0;ci<charCounts[slot];ci++)characters.Add(new TMP_CharacterInfo{materialReferenceIndex=slot,vertexIndex=ci<visibleCounts[slot]?ci*4:0,character=(char)('A'+ci%26),scale=1,isVisible=ci<visibleCounts[slot],elementType=TMP_TextElementType.Character,style=FontStyles.Normal});
  if(actualContexts!=null&&characters.Count>0){var dense=new List<TMP_CharacterInfo>();for(int i=0;i<=characters.Max(x=>x.characterIndex);i++){var existing=characters.SingleOrDefault(x=>x.characterIndex==i);if(existing==null)modeledUnobservedCharacterPlaceholders++;dense.Add(existing??new TMP_CharacterInfo{characterIndex=i,materialReferenceIndex=-1,vertexIndex=0,character='?',textElement=new TMP_TextElement{unicode=0},scale=1,isVisible=false});}characters=dense;}
  owner.textInfo.characterInfo=characters.ToArray();owner.textInfo.characterCount=characters.Count;
  foreach(int i in drawableSlots){
   var texture=new Texture{guid=atlas,localFileId=200+i,assetPath="Assets/atlas.asset"};var slotContext=actualContexts!=null?actualContexts.GetValueOrDefault(i):null;
   Graphic graphic=i==0?owner:new Graphic{transform=new RectTransform{rect=new Rect(layout?.rectSize.x??100f,layout?.rectSize.y??28f),pivot=layout==null?new Vector2(.5f,.5f):new Vector2(layout.pivot.x,layout.pivot.y),lossyScale=new Vector3(1,slotContext?.graphicLossyScaleY??1f,1)}};
   if(i==0&&slotContext!=null)graphic.transform.lossyScale=new Vector3(1,slotContext.graphicLossyScaleY,1);
   var mesh=slotContext==null?MakeMesh(visibleCounts[i]):MakeMesh(slotContext.meshUv0W);var meshSha=UnityStaticSortTextSource.MeshFingerprint(mesh);
   var sourceMaterial=new Material{guid=GuidFor("source-mat|"+sid+"|"+i),localFileId=300+i,assetPath="Assets/source.mat",fingerprint=H("sm"+sid+"|"+i),shader=new Shader{guid=GuidFor("shader|"+sid),localFileId=1,assetPath="Assets/shader.shader"}};
   var binding=new TextSlotBinding{sourceComponentId=sid,sourceTextSha256=H(text),owner=owner,sourceGraphic=graphic,sourceMesh=mesh,sourceMeshSha256=meshSha,materialSlot=i,fontAsset=font,fontAssetGuid=asset,fontAssetLocalFileId=101,ownerFontSharedMaterial=mat,ownerFontMaterialGuid=mat.guid,ownerFontMaterialLocalFileId=mat.localFileId,ownerFontMaterialFingerprint=mat.fingerprint,sourceTexture=texture,sourceTextureGuid=atlas,sourceTextureLocalFileId=200+i,textInfoCharacterCount=charCounts[i],textInfoVisibleCharacterCount=visibleCounts[i],textInfoTriangleIndexCount=(uint)(visibleCounts[i]*6),canvasTriangleIndexCount=(uint)(visibleCounts[i]*6),textInfoCharacterSlotVerified=true,textInfoCharacterMaterialVerified=true,textInfoFontAssetVerified=true,textInfoAtlasVerified=true,textInfoCharacterEvidenceSha256=H(sid+"c"+i),textInfoCharacterAssetEvidenceSha256=chars,textInfoCharacterMaterialFingerprint=H("tm"+i),sourceMaterial=sourceMaterial,sourceMaterialGuid=sourceMaterial.guid,sourceMaterialLocalFileId=sourceMaterial.localFileId,sourceMaterialFingerprint=sourceMaterial.fingerprint,sourceShaderGuid=sourceMaterial.shader.guid,sourceShaderLocalFileId=sourceMaterial.shader.localFileId,fallbackFontAssetGuid=GuidFor("fallback-font|"+sid),fallbackFontAssetLocalFileId=500+i,fallbackFontMaterialGuid=GuidFor("fallback-mat|"+sid),fallbackFontMaterialLocalFileId=600+i,fallbackFontMaterialFingerprint=H("fbm"),fallbackAtlasGuid=atlas,tmpFallbackAlgorithm="offline-provider-v1",transientFallbackFingerprint=sourceMaterial.fingerprint,textSlotEnumeration=owner.enumeration};
   owner.bindings.Add(binding);
  }
  foreach(var b in owner.bindings)owner.enumeration.rows[b.materialSlot].sourceMeshSha256=UnityStaticSortTextSource.MeshFingerprint(b.sourceMesh);
  RehashEnum(owner.enumeration);foreach(var b in owner.bindings){b.textSlotEnumeration=owner.enumeration;owner.finalBindings.Add(b.Copy());}
  return owner;
 }
 static void RehashEnum(NativeStaticSortTextSlotEnumeration e){foreach(var r in e.rows)r.evidenceSha256=typeof(UnityStaticSortTextSource).GetMethod("TextSlotRowHash",BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,new object[]{r}).ToString();var hash=typeof(UnityStaticSortTextSource).GetMethod("TextSlotEnumerationHash",BindingFlags.NonPublic|BindingFlags.Static);e.evidenceSha256=hash.Invoke(null,new object[]{e}).ToString();}
 static void Main(string[] args){
  var path=args[0];var inventory=JsonDocument.Parse(File.ReadAllText(path)).RootElement;
  if(args.Length>3){using var contextsDoc=JsonDocument.Parse(File.ReadAllText(args[3]));Need(contextsDoc.RootElement.GetProperty("storedEvidenceHashesAreNotUsedAsCurrentEvidence").GetBoolean(),"operand adapter explicitly excludes stored evidence hashes");foreach(var row in contextsDoc.RootElement.GetProperty("rows").EnumerateArray()){var sid=row.GetProperty("sourceComponentId").GetString();var slot=row.GetProperty("materialSlot").GetInt32();var context=JsonSerializer.Deserialize<NativeStaticSortTextScaleContext>(row.GetProperty("textScaleContext").GetRawText(),new JsonSerializerOptions{IncludeFields=true});if(!ObservedContexts.TryGetValue(sid,out var bySlot))ObservedContexts[sid]=bySlot=new Dictionary<int,NativeStaticSortTextScaleContext>();Need(!bySlot.ContainsKey(slot),"duplicate observed operand source slot");bySlot.Add(slot,context);}}
  var queue=inventory.GetProperty("queueRendererSourceIds").EnumerateArray().Select(x=>x.GetString()).ToArray();
  Need(queue.Length==87,"actual queue denominator");
  var slotsById=new Dictionary<string,int>();var drawableById=new Dictionary<string,int[]>();var charsById=new Dictionary<string,int[]>();var visibleById=new Dictionary<string,int[]>();
  foreach(var row in inventory.GetProperty("slotReadbacks").EnumerateArray()){var id=row.GetProperty("sourceComponentId").GetString();if(slotsById.ContainsKey(id))continue;var enumeration=row.GetProperty("enumeration");var rows=enumeration.GetProperty("rows").EnumerateArray().ToArray();slotsById[id]=enumeration.GetProperty("slotCount").GetInt32();drawableById[id]=rows.Where(x=>x.GetProperty("disposition").GetString()=="drawable").Select(x=>x.GetProperty("slot").GetInt32()).Distinct().OrderBy(x=>x).ToArray();charsById[id]=rows.Select(x=>x.GetProperty("characterReferences").GetInt32()).ToArray();visibleById[id]=rows.Select(x=>x.GetProperty("visibleCharacterReferences").GetInt32()).ToArray();}
  var groupById=inventory.GetProperty("textGroups").EnumerateArray().ToDictionary(x=>x.GetProperty("sourceLabelId").GetString());
  int observed=0,modeled=0,operandRows=0,modeledOperandGroups=0,totalDrawable=0,phaseRows=0;var receiptRows=new List<object>();bool phaseContextMutationDenied=false;
  foreach(var sid in queue){var g=groupById[sid];var text=g.GetProperty("sourceText").GetString()??"";var n=slotsById.GetValueOrDefault(sid,1);var drawable=drawableById.GetValueOrDefault(sid,new[]{0});if(slotsById.ContainsKey(sid))observed++;else modeled++;
   var refs=charsById.GetValueOrDefault(sid,new[]{1});var visible=visibleById.GetValueOrDefault(sid,new[]{1});var asset=GuidFor("font|"+sid);var atlas=GuidFor("atlas|"+sid);var chars=H("characters|"+sid);ObservedContexts.TryGetValue(sid,out var actualContexts);if(actualContexts!=null){operandRows+=actualContexts.Count;Need(actualContexts.Values.All(c=>c.sourceTextSha256==H(text)),"observed operand text SHA matches inventory source text: "+sid);foreach(var pair in actualContexts){Need(pair.Key<refs.Length&&pair.Value.characters.Length==refs[pair.Key],"observed character reference count matches source slot inventory: "+sid+" slot "+pair.Key);Need(pair.Value.characters.Count(c=>c.visible)==visible[pair.Key],"observed visible character count matches source slot inventory: "+sid+" slot "+pair.Key);}}else if(slotsById.ContainsKey(sid))modeledOperandGroups++;var owner=Owner(sid,text,n,drawable,refs,visible,asset,atlas,chars,actualContexts);Need(owner.bindings.Count==drawable.Length,"provider binding setup has expected drawable rows "+sid+" binds="+owner.bindings.Count+" drawable="+String.Join(",",drawable));if(actualContexts!=null)Need(Math.Abs(owner.transform.lossyScale.y-actualContexts.Values.First().ownerLossyScaleY)<0.000001f,"observed owner scale hydrated: "+sid+" actual="+actualContexts.Values.First().ownerLossyScaleY+" stub="+owner.transform.lossyScale.y);
   var result=ProxyHarness.Run(new ProxyQueueSpec(),new ProxyRendererSpec{sourceComponentId=sid,sourceText=text},owner,out var enumeration);
   Need(result.Count==drawable.Length,"rebound denominator "+sid);Need(UnityStaticSortTextSource.ValidateCaptureLifecycle(result[0].captureLifecycle),"lifecycle receipt "+sid);
   if(!phaseContextMutationDenied){var mutated=JsonSerializer.Deserialize<NativeStaticSortTextCaptureLifecycle>(JsonSerializer.Serialize(result[0].captureLifecycle,new JsonSerializerOptions{IncludeFields=true}),new JsonSerializerOptions{IncludeFields=true});var phase=mutated.phases.First(p=>p.slots!=null&&p.slots.Length>0);phase.slots[0].textScaleContext=null;mutated.evidenceSha256=(string)typeof(UnityStaticSortTextSource).GetMethod("CaptureLifecycleHash",BindingFlags.Public|BindingFlags.Static).Invoke(null,new object[]{mutated});Need(!UnityStaticSortTextSource.ValidateCaptureLifecycle(mutated),"rehashing outer lifecycle cannot legitimize blank per-phase scale context");phaseContextMutationDenied=true;}
   totalDrawable+=result.Count;phaseRows+=result[0].captureLifecycle.phases.Length;
   foreach(var b in result)receiptRows.Add(new{sourceComponentId=sid,materialSlot=b.materialSlot,captureLifecycle=b.captureLifecycle});
  }
  string actual18Refusal=null;
  if(args.Length>2){
   using var failureDoc=JsonDocument.Parse(File.ReadAllText(args[2]));var failureRoot=failureDoc.RootElement;var actualFailure=failureRoot.GetProperty("failure");
   Need(failureRoot.GetProperty("capturedReadOnly").GetBoolean(),"actual18 failure fixture is read-only");
   Need(actualFailure.GetProperty("code").GetString()=="STATIC_SORT_PROXY_TEXT_SLOT_SOURCE_IDENTITY_CHANGED","actual18 failure code");
   Need(actualFailure.GetProperty("phase").GetString()=="final-prepare-pass2","actual18 failure phase");
   Need(failureRoot.GetProperty("contextSnapshot").GetProperty("allContextsBlank").GetBoolean(),"actual18 all phase contexts blank");
   var sid=actualFailure.GetProperty("sourceComponentId").GetString();var sha=actualFailure.GetProperty("sourceTextSha256").GetString();
   var contextArgs=new object[]{null,null,null};
   var contextAccepted=(bool)typeof(UnityStaticSortTextSource).GetMethod("TextLayoutContextMatches",BindingFlags.Public|BindingFlags.Static).Invoke(null,contextArgs);
   var contextDiagnostic=contextArgs[2]?.ToString()??"";
   Need(!contextAccepted && contextDiagnostic=="context-validity=False/False","actual18 blank saved context fails real context validator: "+contextDiagnostic);
   actual18Refusal="source="+sid+";sourceTextSha256="+sha+";phase="+actualFailure.GetProperty("phase").GetString()+";"+contextDiagnostic+";observedCode="+actualFailure.GetProperty("code").GetString();
  }
  var failure=inventory.GetProperty("failure");var failedId=failure.GetProperty("sourceLabelId").GetString();var failureText=groupById[failedId].GetProperty("sourceText").GetString();
  var refusals=new[]{
   Refusal("fallback-registration",()=>UnityStaticSortTextSource.failRegistration=true,"STATIC_SORT_PROXY_TEXT_FALLBACK_VARIANT_REGISTRATION_FAILED",failedId,failureText),
   Refusal("source-text-drift",()=>UnityStaticSortTextSource.driftText=true,"STATIC_SORT_PROXY_TEXT_FINAL_SLOTS_FAILED",failedId,failureText),
   Refusal("font-identity-drift",()=>UnityStaticSortTextSource.driftFont=true,"STATIC_SORT_PROXY_TEXT_FINAL_SOURCE_DENOMINATOR_CHANGED",failedId,failureText),
   Refusal("atlas-identity-drift",()=>UnityStaticSortTextSource.driftAtlas=true,"STATIC_SORT_PROXY_TEXT_FINAL_SOURCE_DENOMINATOR_CHANGED",failedId,failureText),
   Refusal("character-asset-drift",()=>UnityStaticSortTextSource.driftCharacters=true,"STATIC_SORT_PROXY_TEXT_FINAL_SOURCE_DENOMINATOR_CHANGED",failedId,failureText),
   Refusal("slot-count-drift",()=>UnityStaticSortTextSource.driftCount=true,"STATIC_SORT_PROXY_TEXT_FINAL_SLOTS_FAILED",failedId,failureText),
   Refusal("layout-geometry-drift",()=>UnityStaticSortTextSource.driftLayout=true,"STATIC_SORT_PROXY_TEXT_SLOT_SOURCE_IDENTITY_CHANGED",failedId,failureText),
   Refusal("source-mesh-only-drift",()=>UnityStaticSortTextSource.driftMesh=true,"STATIC_SORT_PROXY_TEXT_FINAL_SLOTS_FAILED",failedId,failureText),
   Refusal("fallback-material-profile-drift",()=>UnityStaticSortTextSource.driftMaterial=true,"STATIC_SORT_PROXY_TEXT_SLOT_SOURCE_IDENTITY_CHANGED",failedId,failureText),
   Refusal("scale-operand-drift-with-valid-new-uv",()=>UnityStaticSortTextSource.driftScale=true,"textLayoutContext=",failedId,failureText),
  };
  UnityStaticSortTextSource.ResetProvider();
  var counts=inventory.GetProperty("counts");
  var receipt=new{contract="monkey-actual17-offline-text-capture-receipt/1",evidenceBoundary=new{unityEditorExecuted=false,tmpNativeRenderingExecuted=false,assetDatabaseExecuted=false,persistentReferences="simulated-valid-identities-only",phaseDeltas="synthetic-provider-stimuli;actual17 failure had no captured field delta",observedSourceInventory=true},textSources=receiptRows};
  if(args.Length>1)File.WriteAllText(args[1],JsonSerializer.Serialize(receipt,new JsonSerializerOptions{IncludeFields=true}));
  var report=new {contract="offline-production-method-extraction/1",actualInputs=new{textGroups=counts.GetProperty("textGroups").GetInt32(),queueRendererRows=queue.Length,observedSlotReadbackLabels=observed,modeledQueueLabels=modeled,observedOperandReplayGroups=ObservedContexts.Count,observedOperandReplayRows=operandRows,modeledOperandGroups=modeledOperandGroups,modeledOperandLabels=modeled,modeledUnobservedCharacterPlaceholders=modeledUnobservedCharacterPlaceholders,nonQueueLabels=inventory.GetProperty("notInQueueRendererInputs").GetArrayLength(),actual18ZeroContextRefusal=actual18Refusal!=null},execution=new{queueRowsSucceeded=queue.Length,totalDrawableSlots=totalDrawable,lifecyclePhaseRows=phaseRows,negativeRefusals=refusals.Length+(actual18Refusal==null?0:1)+(phaseContextMutationDenied?1:0),phaseContextMutationDenied=phaseContextMutationDenied,editorExecuted=false,tmpNativeRenderingExecuted=false,assetDatabaseExecuted=false},productionMethodsExecuted=new[]{"CaptureAndRebindTextSlots","GetCurrentSlotsCore context-capture helper surface","CaptureCurrentTextScaleContext","TryBuildTextScaleContext","IsValidTextScaleContext","TextLayoutEvidenceSha256","TextScaleContextUvMatchesMesh","VerifyTextScaleFormulaAgainstMesh","MeshFingerprint","TextLayoutContextMatches","ValidateCapturedSlotTransition","CaptureLifecycleReadyForRebind","CapturePhaseSlotsMatchEnumeration","CaptureLifecycleHash","ValidateCaptureLifecycle","FinalizeCaptureLifecycle","TextSlotRowHash(v2)","TextSlotEnumerationHash(v2)"},providerBoundaries=new[]{"Observed 57-group/59-slot layout, Canvas, TMP character, and UV0.w operands are hydrated from pinned saved native17 evidence; current contexts and hashes are recomputed by production builder","Unity/TMP object creation, mesh positions/topology, asset identities, and persistence remain deterministic stubs","GetCurrentSlots, PrepareSource, fallback profile bake/registration, and RebindCapturedSlot surface are providers","RebindCapturedSlot provider calls exact production VerifyTextScaleFormulaAgainstMesh and ValidateCapturedSlotTransition; full RebindCapturedSlot body is not invoked","Production context capture, validity, layout hash, UV0 comparison, and TMP equation execute against hydrated or explicitly modeled operands","30 queue groups without saved slot inputs use modeled TMP/Canvas/UV operands; no stored context hash is reused","Gaps in observed global character indices are filled with invisible materialSlot=-1 placeholders and filtered out by production slot-context sampling"},actual18ZeroContextDiagnostic=actual18Refusal,refusals,failureBoundary=inventory.GetProperty("observedPhaseDeltaBoundary").Clone()};
  Console.WriteLine(JsonSerializer.Serialize(report));
 }
}
}
''' + r'''
namespace UnityEngine {
 public class Object {public string guid,assetPath,name;public long localFileId;}
 public struct Vector2 {public float x,y;public Vector2(float a,float b){x=a;y=b;}}
 public struct Vector3 {public float x,y,z;public Vector3(float a,float b,float c){x=a;y=b;z=c;}public static implicit operator Vector4(Vector3 x)=>new Vector4{x=x.x,y=x.y,z=x.z,w=0};}
 public struct Vector4 {public float x,y,z,w;}
 public struct Rect {public float width,height;public Rect(float w,float h){width=w;height=h;}}
 public struct Color32 {public byte r,g,b,a;}
 public class Transform {public Vector3 lossyScale=new Vector3(1,1,1);}
 public class RectTransform:Transform {public Rect rect=new Rect(100,28);public Vector2 pivot=new Vector2(.5f,.5f);}
 public enum RenderMode {ScreenSpaceOverlay=0,ScreenSpaceCamera=1,WorldSpace=2}
 public class Canvas:Object {public RenderMode renderMode=RenderMode.ScreenSpaceOverlay;public float scaleFactor=1;public Object worldCamera;public static void ForceUpdateCanvases(){}}
 public static class Mathf {public static bool Approximately(float a,float b)=>Math.Abs(a-b)<0.0001f;public static float Abs(float x)=>Math.Abs(x);}
 public class Material:Object {public string fingerprint;public Shader shader;}
 public class Shader:Object {}
 public class Texture:Object {}
 public class Mesh:Object {public int vertexCount,subMeshCount=1;public Vector3[] vertices=Array.Empty<Vector3>(),normals=Array.Empty<Vector3>();public Color32[] colors32=Array.Empty<Color32>();public Vector4[] tangents=Array.Empty<Vector4>();public Vector4[] uv0=Array.Empty<Vector4>();public int[] triangles=Array.Empty<int>();public bool HasVertexAttribute(UnityEngine.Rendering.VertexAttribute a)=>a==UnityEngine.Rendering.VertexAttribute.TexCoord0;public int GetVertexAttributeDimension(UnityEngine.Rendering.VertexAttribute a)=>a==UnityEngine.Rendering.VertexAttribute.TexCoord0?4:0;public void GetUVs(int channel,List<Vector4> result){result.Clear();if(channel==0)result.AddRange(uv0);}public int[] GetTriangles(int submesh)=>triangles;}
}
namespace UnityEngine.Rendering {public enum VertexAttribute {TexCoord0=0}}
namespace UnityEngine.UI {
 public class Graphic:UnityEngine.Object {public UnityEngine.Transform transform=new UnityEngine.RectTransform();}
 public class ContentSizeFitter:UnityEngine.Object {public enum FitMode{Unconstrained=0,MinSize=1,PreferredSize=2}public FitMode horizontalFit,verticalFit;public bool isActiveAndEnabled=true;}
}
namespace TMPro {
 public enum TMP_TextElementType {Character=0,Sprite=1}
 public enum FontStyles {Normal=0,Bold=1,Italic=2,Underline=4,UpperCase=8,LowerCase=16,SmallCaps=32}
 public class TMP_FontAsset:UnityEngine.Object{}
 public class TMP_SpriteAsset:UnityEngine.Object{}
 public sealed class TMP_TextElement {public uint unicode;}
 public sealed class TMP_CharacterInfo {public int characterIndex,materialReferenceIndex,vertexIndex;public TMP_TextElement textElement;public char character;public float scale=1;public bool isVisible=true,isUsingAlternateTypeface;public TMP_TextElementType elementType=TMP_TextElementType.Character;public FontStyles style=FontStyles.Normal;}
 public sealed class TMP_TextInfo {public int lineCount=1,materialCount,characterCount;public TMP_CharacterInfo[] characterInfo=Array.Empty<TMP_CharacterInfo>();}
 public class TMP_Text:UnityEngine.UI.Graphic {
  private float m_charWidthAdjDelta=0,m_characterHorizontalScale=1;
  public string text;public TMP_FontAsset font;public UnityEngine.Material fontSharedMaterial;public UnityEngine.Canvas canvas=new UnityEngine.Canvas();public TMP_TextInfo textInfo=new TMP_TextInfo();
  public Monkey.StaticMaskSort.NativeTextLineBox lineBox;public UnityEngine.UI.ContentSizeFitter fitter;public void SetScaleInternals(float widthAdj,float horizontal){m_charWidthAdjDelta=widthAdj;m_characterHorizontalScale=horizontal;}
  public List<Monkey.StaticSortQueueProxy.TextSlotBinding> bindings,finalBindings;public Monkey.StaticSortQueueProxy.NativeStaticSortTextSlotEnumeration enumeration,finalEnumeration;
  public bool finalSnapshot,driftSlotCount,layoutGeometryDrifted;public UnityEngine.Vector4 margin;public float fontSize=28,fontSizeMin=0,fontSizeMax=0,characterSpacing,wordSpacing,lineSpacing,lineSpacingAdjustment,paragraphSpacing;public bool enableAutoSizing,extraPadding,richText=true,parseCtrlCharacters=true,isRightToLeftText,useMaxVisibleDescender;public FontStyles fontStyle=FontStyles.Normal;public int fontWeight=400,alignment,textWrappingMode,overflowMode,maxVisibleCharacters=99999,maxVisibleWords=99999,maxVisibleLines=99999,pageToDisplay=1;public int[] fontFeatures=Array.Empty<int>();
  public T GetComponent<T>() where T:class {if(typeof(T)==typeof(Monkey.StaticMaskSort.NativeTextLineBox))return lineBox as T;if(typeof(T)==typeof(UnityEngine.UI.ContentSizeFitter))return fitter as T;return null;}public string GetParsedText()=>text;
 }
 public class TextMeshProUGUI:TMP_Text{}
}
namespace Monkey.StaticMaskSort {public class NativeTextLineBox:UnityEngine.Object {public float LineHeight,ExtraLineFraction,preferredHeight;public bool isActiveAndEnabled=true;}}
namespace UnityEditor {public static class AssetDatabase {public static bool TryGetGUIDAndLocalFileIdentifier(UnityEngine.Object x,out string g,out long id){g=x?.guid;id=x?.localFileId??0;return x!=null;}public static string GetAssetPath(UnityEngine.Object x)=>x?.assetPath;}}
static class JsonUtility {public static string ToJson(object x,bool pretty=false)=>JsonSerializer.Serialize(x,new JsonSerializerOptions{IncludeFields=true});}
'''


def test_actual17_text_slot_inventory_and_unknown_phase_delta():
    _, inv = _inventory()
    assert inv["capturedReadOnly"] is True
    assert inv["counts"]["textGroups"] == 119
    assert inv["counts"]["queuedTextGroups"] == 87
    assert inv["counts"]["queuedObservedSlotGroups"] == 57
    assert len(inv["slotReadbacks"]) == 118
    assert len(inv["queuedUnobservedSlotLabels"]) == 30
    assert len(inv["notInQueueRendererInputs"]) == 32
    assert inv["observedPhaseDeltaBoundary"]["capturedPerPhaseDelta"] is False
    assert inv["failure"]["sourceLabelId"] in inv["queueRendererSourceIds"]
    assert _verify_readonly_pins(inv) == []


def test_current_production_capture_chain_against_all_actual17_queue_ids(tmp_path):
    dotnet = shutil.which("dotnet") or ("/opt/homebrew/bin/dotnet" if Path("/opt/homebrew/bin/dotnet").exists() else None)
    if not dotnet:
        pytest.skip(".NET SDK unavailable")
    inventory_path, inv = _inventory()
    inventory_sha_before = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
    assert _verify_readonly_pins(inv) == []
    actual18_path = Path(os.environ.get("MONKEY_ACTUAL18_TEXT_CONTEXT_FAILURE", DEFAULT_ACTUAL18_FAILURE))
    saved_context_path = Path(os.environ.get("MONKEY_ACTUAL17_SAVED_TEXT_CONTEXTS", DEFAULT_SAVED_TEXT_CONTEXTS))
    assert actual18_path.is_file(), "pinned actual18 context failure fixture is required for the lifecycle regression"
    assert saved_context_path.is_file(), "pinned native17 saved contexts are required for scale-context replay"
    actual18_fixture = json.loads(actual18_path.read_text(encoding="utf-8"))
    saved_fixture = json.loads(saved_context_path.read_text(encoding="utf-8"))
    assert actual18_fixture["contextSnapshot"]["allContextsBlank"] is True
    assert len(saved_fixture["rows"]) == 59
    saved_project_root = Path(os.environ.get(
        "MONKEY_ACTUAL17_SAVED_PROJECT_ROOT",
        "/Users/wangmeng/MyProjects/Games/projects/20-foodstreet/Analysis/v050-development-20261104/four-activity-grea-recovery-20261104/" + saved_fixture["source"]["unityProjectRoot"],
    ))
    for relative, expected_sha in saved_fixture["inputPinsBefore"].items():
        source = saved_project_root / relative
        assert source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == expected_sha
    normalized_contexts_path = tmp_path / "actual17-context-operands-adapter.json"
    _normalize_saved_context_fixture(saved_context_path, normalized_contexts_path)
    proxy = (ROOT / "src/monkey/targets/UnityStaticSortQueueProxy.cs").read_text(encoding="utf-8")
    text = (ROOT / "src/monkey/targets/UnityStaticSortTextSource.cs").read_text(encoding="utf-8")
    native = (ROOT / "src/monkey/targets/NativeStaticSortTextSource.cs").read_text(encoding="utf-8")
    harness = tmp_path / "Harness.cs"
    harness.write_text(_csharp_program(proxy, text, native), encoding="utf-8")
    (tmp_path / "Harness.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>disable</Nullable><EnableDefaultCompileItems>true</EnableDefaultCompileItems><NoWarn>CS0649;CS0169;CS0414</NoWarn></PropertyGroup></Project>',
        encoding="utf-8",
    )
    (tmp_path / "NuGet.Config").write_text('<configuration><packageSources><clear /></packageSources></configuration>', encoding="utf-8")
    build = subprocess.run([dotnet, "build", str(tmp_path / "Harness.csproj"), "--configfile", str(tmp_path / "NuGet.Config"), "--nologo", "-v:q"], capture_output=True, text=True, timeout=120)
    assert build.returncode == 0, build.stdout + build.stderr
    receipt_path = Path(os.environ.get("MONKEY_TEXT_SLOT_LIFECYCLE_RECEIPT", tmp_path / "actual17-modeled-text-sources.json"))
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([dotnet, "exec", str(tmp_path / "bin/Debug/net8.0/Harness.dll"), str(inventory_path), str(receipt_path), str(actual18_path), str(normalized_contexts_path)], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["execution"]["queueRowsSucceeded"] == 87
    assert report["execution"]["editorExecuted"] is False
    assert report["execution"]["tmpNativeRenderingExecuted"] is False
    assert report["execution"]["assetDatabaseExecuted"] is False
    assert report["actualInputs"]["observedSlotReadbackLabels"] == 57
    assert report["actualInputs"]["modeledQueueLabels"] == 30
    assert report["actualInputs"]["observedOperandReplayGroups"] == 57
    assert report["actualInputs"]["observedOperandReplayRows"] == 59
    assert report["actualInputs"]["modeledOperandGroups"] == 0
    assert report["actualInputs"]["modeledOperandLabels"] == 30
    assert report["failureBoundary"]["capturedPerPhaseDelta"] is False
    assert report["execution"]["negativeRefusals"] == 12
    assert report["execution"]["phaseContextMutationDenied"] is True
    assert report["actualInputs"]["actual18ZeroContextRefusal"] is True
    assert "context-validity=False/False" in report["actual18ZeroContextDiagnostic"]
    assert any(row["name"] == "scale-operand-drift-with-valid-new-uv" for row in report["refusals"])
    assert "ValidateCapturedSlotTransition" in report["productionMethodsExecuted"]
    assert "full RebindCapturedSlot body is not invoked" in " ".join(report["providerBoundaries"])
    exported = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert len(exported["textSources"]) == report["execution"]["totalDrawableSlots"]
    assert exported["evidenceBoundary"]["persistentReferences"] == "simulated-valid-identities-only"
    assert hashlib.sha256(inventory_path.read_bytes()).hexdigest() == inventory_sha_before
    assert _verify_readonly_pins(inv) == []
    assert _verify_actual18_pins(actual18_fixture) == []
    for relative, expected_sha in saved_fixture["inputPinsBefore"].items():
        source = saved_project_root / relative
        assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_sha
    report_path = os.environ.get("MONKEY_TEXT_SLOT_LIFECYCLE_REPORT")
    if report_path:
        destination = Path(report_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
