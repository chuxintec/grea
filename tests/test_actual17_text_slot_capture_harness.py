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
    text_methods = "\n".join(_declaration(text_source, s) for s in (
        "static string HashText(",
        "public static NativeStaticSortTextCaptureLifecycle BeginCaptureLifecycle(",
        "public static NativeStaticSortTextCapturePhase CaptureLifecyclePhase(",
        "public static void AppendCaptureLifecyclePhase(",
        "static NativeStaticSortTextCaptureSlot CaptureLifecycleSlot(",
        "public static bool TextSlotDenominatorMatches(",
        "public static int[] TextSlotDrawableIds(",
        "static string TextSlotEvidenceSummary(",
        "public static bool TextLayoutContextMatches(",
        "public static bool ValidateCapturedSlotTransition(",
        "static string SlotBindingTransitionSummary(",
        "public static bool CaptureLifecycleReadyForRebind(",
        "public static string CaptureLifecycleHash(",
        "public static bool ValidateCaptureLifecycle(",
        "public static bool FinalizeCaptureLifecycle(",
        "static bool PersistentAsset(",
        "static string TextSlotRowHash(",
        "static string TextSlotEnumerationHash(",
        "static bool IsValidTextSlotEnumeration(",
        "static bool IsSha256(",
        "static bool CapturePhaseSlotsMatchEnumeration(",
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
    native_types = native_types.replace("public string evidenceSha256;", "public string evidenceSha256; public bool harnessValid;")
    return r'''#nullable disable
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Monkey.StaticSortQueueProxy;
using TMPro;
using UnityEngine;
using UnityEditor;

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
 public static int PrepareCalls, CaptureCalls, RegisterCalls, RebindCalls;
 public static bool failRegistration, driftText, driftAtlas, driftCharacters, driftFont, driftLayout, driftMesh, driftMaterial, driftCount;
 public static void ResetProvider(){PrepareCalls=CaptureCalls=RegisterCalls=RebindCalls=0;failRegistration=driftText=driftAtlas=driftCharacters=driftFont=driftLayout=driftMesh=driftMaterial=driftCount=false;}
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
     if(driftLayout){b.currentTextScaleContext=(NativeStaticSortTextScaleContext)JsonSerializer.Deserialize<NativeStaticSortTextScaleContext>(JsonSerializer.Serialize(b.currentTextScaleContext,new JsonSerializerOptions{IncludeFields=true}),new JsonSerializerOptions{IncludeFields=true});b.currentTextScaleContext.textLayoutInputs.rectSize.x+=1;b.currentTextScaleContext.textLayoutEvidenceSha256+="drift";}
     if(driftMesh)b.sourceMeshSha256=new string('d',64);
     if(driftMaterial)b.sourceMaterialFingerprint=new string('e',64);
    }
    enumeration=CloneEnum(enumeration);
    foreach(var b in slots.Where(x=>x!=null)){if(driftMesh)enumeration.rows[b.materialSlot].sourceMeshSha256=b.sourceMeshSha256;if(driftMaterial)enumeration.rows[b.materialSlot].sourceGraphicMaterialFingerprint=b.sourceMaterialFingerprint;}
    Rehash(enumeration);
   }
   return true;
 }
 public static bool PrepareSource(TMP_Text owner,string sid,out string d) { PrepareCalls++; if(owner.finalEnumeration!=null){owner.finalSnapshot=true;foreach(var b in owner.finalBindings.Where(x=>x!=null))b.textSlotEnumeration=owner.finalEnumeration;} d=null; return true; }
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
   if(current==null||!ValidateCapturedSlotTransition(captured,current,e,out d)){rebound=null;return false;}
   rebound=current;return true;
 }
''' + text_methods + r'''
 static string MaterialFingerprint(Material m)=>m==null?null:m.fingerprint;
 static bool AssetIdentity(UnityEngine.Object o,out string g,out long id) { g=o?.guid;id=o?.localFileId??0;return o!=null&&!String.IsNullOrWhiteSpace(g)&&id!=0; }
 static bool IsValidTextScaleContext(NativeStaticSortTextScaleContext c)=>c!=null&&c.harnessValid;
 static bool Finite(float x)=>!float.IsNaN(x)&&!float.IsInfinity(x);
 static string FloatEvidence(float x)=>x.ToString("R",CultureInfo.InvariantCulture);
 static bool HasVerifiedTextLineBoxHeight(NativeStaticSortTextLayoutEvidence x)=>false;
 static string TextLayoutEvidenceDifference(NativeStaticSortTextLayoutEvidence a,NativeStaticSortTextLayoutEvidence b)=>a==null||b==null?"missing":FloatEvidence(a.rectSize.x)+"!="+FloatEvidence(b.rectSize.x);
 static bool Fail(string s,out string d){d=s;return false;}
 static NativeStaticSortTextSlotEnumeration CloneEnum(NativeStaticSortTextSlotEnumeration e,string sourceTextSha256=null){var x=JsonSerializer.Deserialize<NativeStaticSortTextSlotEnumeration>(JsonSerializer.Serialize(e,new JsonSerializerOptions{IncludeFields=true}),new JsonSerializerOptions{IncludeFields=true});if(sourceTextSha256!=null)x.sourceTextSha256=sourceTextSha256;Rehash(x);return x;}
 static void Rehash(NativeStaticSortTextSlotEnumeration e){foreach(var r in e.rows)r.evidenceSha256=TextSlotRowHash(r);e.evidenceSha256=TextSlotEnumerationHash(e);}
}

static class ProxyHarness {
 static string HashText(string s){using var sha=SHA256.Create();return Convert.ToHexString(sha.ComputeHash(Encoding.UTF8.GetBytes(s??""))).ToLowerInvariant();}
 static void WriteTextSlotCaptureFailure(string code,string sourceComponentId,string phase,string sourceTextSha256,string diagnostic,NativeStaticSortTextSlotEnumeration initial,NativeStaticSortTextSlotEnumeration current,NativeStaticSortTextCaptureLifecycle lifecycle) {
  var checker=typeof(UnityStaticSortTextSource).GetMethod("CapturePhaseSlotsMatchEnumeration",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Static);
  foreach(var p in lifecycle.phases.Where(x=>!(bool)checker.Invoke(null,new object[]{x}))) {
   var s=p.slots.FirstOrDefault(); if(s==null)continue; var r=p.enumeration.rows[s.slot];
   Console.Error.WriteLine("BAD "+p.phase+" slot="+s.slot+
    " disp="+s.disposition+"/"+r.disposition+" asset="+s.sourceAssetGuid+":"+s.sourceAssetLocalFileId+"/"+r.sourceAssetGuid+":"+r.sourceAssetLocalFileId+
    " atlas="+s.atlasGuid+":"+s.atlasLocalFileId+"/"+r.atlasGuid+":"+r.atlasLocalFileId+
    " mats="+s.sourceGraphicMaterialGuid+":"+s.sourceGraphicMaterialLocalFileId+":"+s.sourceGraphicMaterialFingerprint+"/"+r.sourceGraphicMaterialGuid+":"+r.sourceGraphicMaterialLocalFileId+":"+r.sourceGraphicMaterialFingerprint+
    " textmat="+s.textInfoMaterialGuid+":"+s.textInfoMaterialLocalFileId+":"+s.textInfoMaterialFingerprint+"/"+r.textInfoMaterialGuid+":"+r.textInfoMaterialLocalFileId+":"+r.textInfoMaterialFingerprint+
    " shader="+s.sourceShaderGuid+":"+s.sourceShaderLocalFileId+"/"+r.sourceShaderGuid+":"+r.sourceShaderLocalFileId
    +" tex="+s.sourceTextureGuid+":"+s.sourceTextureLocalFileId+"/"+r.sourceTextureGuid+":"+r.sourceTextureLocalFileId
    +" counts="+s.characterReferences+"/"+r.characterReferences+","+s.visibleCharacterReferences+"/"+r.visibleCharacterReferences+","+s.textInfoVertexCount+"/"+r.textInfoVertexCount+","+s.textInfoTriangleIndexCount+"/"+r.textInfoTriangleIndexCount+","+s.textInfoNondegenerateTriangleCount+"/"+r.textInfoNondegenerateTriangleCount+","+s.canvasVertexCount+"/"+r.canvasVertexCount+","+s.canvasTriangleIndexCount+"/"+r.canvasTriangleIndexCount+","+s.canvasNondegenerateTriangleCount+"/"+r.canvasNondegenerateTriangleCount
    +" chars="+s.characterAssetEvidenceSha256+"/"+r.characterAssetEvidenceSha256+" mesh="+s.sourceMeshSha256+"/"+r.sourceMeshSha256);
  }
 }

''' + proxy_helpers + r'''
''' + capture_method + r'''
 public static List<TextSlotBinding> Run(ProxyQueueSpec s,ProxyRendererSpec r,TMP_Text o,out NativeStaticSortTextSlotEnumeration e)=>CaptureAndRebindTextSlots(s,r,o,null,out e);
}

class Program {
 static void Need(bool x,string m){if(!x)throw new Exception(m);}
 static string H(string s){using var sha=SHA256.Create();return Convert.ToHexString(sha.ComputeHash(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();}
 static string GuidFor(string s)=>H("guid|"+s).Substring(0,32);
 static object Refusal(string name,Action configure,string expected,string sid,string text){
  UnityStaticSortTextSource.ResetProvider();configure();var owner=Owner(sid,text,1,new[]{0},GuidFor("font|"+sid),GuidFor("atlas|"+sid),H("characters|"+sid));owner.driftSlotCount=UnityStaticSortTextSource.driftCount;
  try{ProxyHarness.Run(new ProxyQueueSpec(),new ProxyRendererSpec{sourceComponentId=sid,sourceText=text},owner,out _);throw new Exception("expected refusal did not occur: "+name);}
  catch(InvalidOperationException ex){if(!ex.Message.Contains(expected,StringComparison.Ordinal))throw new Exception("wrong refusal for "+name+": "+ex.Message);return new{name,refusal=expected};}
 }
 static NativeStaticSortTextSlotEnumeration MakeEnum(string sid,string text,int count,int[] drawableSlots,string asset,string atlas,string charAsset) {
  var e=new NativeStaticSortTextSlotEnumeration{evidenceContract="monkey-static-sort-text-slot-enumeration/2",sourceComponentId=sid,sourceTextSha256=H(text),slotCount=count,verified=true,rows=new NativeStaticSortTextSlotEvidence[count]};
  for(int i=0;i<count;i++){bool draw=drawableSlots.Contains(i);var r=e.rows[i]=new NativeStaticSortTextSlotEvidence{evidenceContract="monkey-static-sort-text-slot-evidence/2",slot=i,characterReferences=draw?2:0,visibleCharacterReferences=draw?2:0,disposition=draw?"drawable":"empty-placeholder",sourceAssetKind="font",sourceAssetGuid=asset,sourceAssetLocalFileId=101,atlasGuid=atlas,atlasLocalFileId=200+i,characterEvidenceSha256=H(sid+"c"+i),characterAssetEvidenceSha256=charAsset,sourceMeshSha256=draw?H(sid+"m"+i):null,textInfoVertexCount=draw?8:0,textInfoTriangleIndexCount=draw?6u:0u,textInfoNondegenerateTriangleCount=draw?2:0,canvasVertexCount=draw?8:0,canvasTriangleIndexCount=draw?6u:0u,canvasNondegenerateTriangleCount=draw?2:0,sourceGraphicMaterialGuid=GuidFor("source-mat|"+sid+"|"+i),sourceGraphicMaterialLocalFileId=300+i,textInfoMaterialGuid=GuidFor("text-mat|"+sid+"|"+i),textInfoMaterialLocalFileId=400+i,sourceShaderGuid=GuidFor("shader|"+sid),sourceShaderLocalFileId=1,sourceTextureGuid=atlas,sourceTextureLocalFileId=200+i,sourceGraphicMaterialFingerprint=H("sm"+sid+"|"+i),textInfoMaterialFingerprint=H("tm"+i)};}
  foreach(var r in e.rows) r.evidenceSha256=typeof(UnityStaticSortTextSource).GetMethod("TextSlotRowHash",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Static).Invoke(null,new object[]{r}).ToString();
  var method=typeof(UnityStaticSortTextSource).GetMethod("TextSlotEnumerationHash",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Static);e.evidenceSha256=method.Invoke(null,new object[]{e}).ToString();return e;
 }
 static TMP_Text Owner(string sid,string text,int slots,int[] drawableSlots,string asset,string atlas,string chars) {
  var font=new TMP_FontAsset{guid=asset,localFileId=101,assetPath="Assets/font.asset"};var mat=new Material{guid=GuidFor("font-mat|"+sid),localFileId=102,assetPath="Assets/font.mat",fingerprint=H("fm|"+sid)};
  var owner=new TMP_Text{text=text,font=font,fontSharedMaterial=mat,bindings=new List<TextSlotBinding>()};owner.enumeration=MakeEnum(sid,text,slots,drawableSlots,asset,atlas,chars);
  owner.finalBindings=new List<TextSlotBinding>();foreach(int i in drawableSlots){var texture=new Texture{guid=atlas,localFileId=200+i,assetPath="Assets/atlas.asset"};var graphic=new Graphic();var ctx=new NativeStaticSortTextScaleContext{sourceComponentId=sid,sourceTextSha256=H(text),materialSlot=i,harnessValid=true,textLayoutEvidenceSha256=H("layout"+sid+i),textLayoutInputs=new NativeStaticSortTextLayoutEvidence{rectSize=new Vector2{x=100,y=28}}};var b=new TextSlotBinding{sourceComponentId=sid,sourceTextSha256=H(text),owner=owner,sourceGraphic=graphic,sourceMesh=new Mesh{vertexCount=4},materialSlot=i,fontAsset=font,fontAssetGuid=asset,fontAssetLocalFileId=101,ownerFontSharedMaterial=mat,ownerFontMaterialGuid=mat.guid,ownerFontMaterialLocalFileId=mat.localFileId,ownerFontMaterialFingerprint=mat.fingerprint,sourceTexture=texture,sourceTextureGuid=atlas,sourceTextureLocalFileId=200+i,sourceMeshSha256=H(sid+"m"+i),textInfoCharacterCount=2,textInfoVisibleCharacterCount=2,textInfoTriangleIndexCount=6,canvasTriangleIndexCount=6,textInfoCharacterSlotVerified=true,textInfoCharacterMaterialVerified=true,textInfoFontAssetVerified=true,textInfoAtlasVerified=true,textInfoCharacterEvidenceSha256=H(sid+"c"+i),textInfoCharacterAssetEvidenceSha256=chars,textInfoCharacterMaterialFingerprint=H("tm"+i),sourceMaterial=new Material{guid=GuidFor("source-mat|"+sid+"|"+i),localFileId=300+i,assetPath="Assets/source.mat",fingerprint=H("sm"+sid+"|"+i),shader=new Shader{guid=GuidFor("shader|"+sid),localFileId=1,assetPath="Assets/shader.shader"}},sourceMaterialGuid=GuidFor("source-mat|"+sid+"|"+i),sourceMaterialLocalFileId=300+i,sourceMaterialFingerprint=H("sm"+sid+"|"+i),sourceShaderGuid=GuidFor("shader|"+sid),sourceShaderLocalFileId=1,currentTextScaleContext=ctx,fallbackFontAssetGuid=GuidFor("fallback-font|"+sid),fallbackFontAssetLocalFileId=500+i,fallbackFontMaterialGuid=GuidFor("fallback-mat|"+sid),fallbackFontMaterialLocalFileId=600+i,fallbackFontMaterialFingerprint=H("fbm"),fallbackAtlasGuid=atlas,tmpFallbackAlgorithm="offline-provider-v1",transientFallbackFingerprint=H("sm"+sid+"|"+i),textSlotEnumeration=owner.enumeration};owner.bindings.Add(b);owner.finalBindings.Add(b.Copy());}
  return owner;
 }
 static void Main(string[] args){
  var path=args[0];var inventory=JsonDocument.Parse(File.ReadAllText(path)).RootElement;
  var queue=inventory.GetProperty("queueRendererSourceIds").EnumerateArray().Select(x=>x.GetString()).ToArray();
  Need(queue.Length==87,"actual queue denominator");
  var slotsById=new Dictionary<string,int>();var drawableById=new Dictionary<string,int[]>();
  foreach(var row in inventory.GetProperty("slotReadbacks").EnumerateArray()){var id=row.GetProperty("sourceComponentId").GetString();if(slotsById.ContainsKey(id))continue;var enumeration=row.GetProperty("enumeration");slotsById[id]=enumeration.GetProperty("slotCount").GetInt32();drawableById[id]=enumeration.GetProperty("rows").EnumerateArray().Where(x=>x.GetProperty("disposition").GetString()=="drawable").Select(x=>x.GetProperty("slot").GetInt32()).Distinct().OrderBy(x=>x).ToArray();}
  var groupById=inventory.GetProperty("textGroups").EnumerateArray().ToDictionary(x=>x.GetProperty("sourceLabelId").GetString());
  int observed=0,modeled=0,totalDrawable=0,phaseRows=0;var receiptRows=new List<object>();
  foreach(var sid in queue){var g=groupById[sid];var text=g.GetProperty("sourceText").GetString()??"";var n=slotsById.GetValueOrDefault(sid,1);var drawable=drawableById.GetValueOrDefault(sid,new[]{0});if(slotsById.ContainsKey(sid))observed++;else modeled++;
   var asset=GuidFor("font|"+sid);var atlas=GuidFor("atlas|"+sid);var chars=H("characters|"+sid);var owner=Owner(sid,text,n,drawable,asset,atlas,chars);
   var result=ProxyHarness.Run(new ProxyQueueSpec(),new ProxyRendererSpec{sourceComponentId=sid,sourceText=text},owner,out var enumeration);
   Need(result.Count==drawable.Length,"rebound denominator "+sid);Need(UnityStaticSortTextSource.ValidateCaptureLifecycle(result[0].captureLifecycle),"lifecycle receipt "+sid);
   totalDrawable+=result.Count;phaseRows+=result[0].captureLifecycle.phases.Length;
   foreach(var b in result)receiptRows.Add(new{sourceComponentId=sid,materialSlot=b.materialSlot,captureLifecycle=b.captureLifecycle});
  }
  var failure=inventory.GetProperty("failure");var failedId=failure.GetProperty("sourceLabelId").GetString();var failureText=groupById[failedId].GetProperty("sourceText").GetString();
  var refusals=new[]{
   Refusal("fallback-registration",()=>UnityStaticSortTextSource.failRegistration=true,"STATIC_SORT_PROXY_TEXT_FALLBACK_VARIANT_REGISTRATION_FAILED",failedId,failureText),
   Refusal("source-text-drift",()=>UnityStaticSortTextSource.driftText=true,"STATIC_SORT_PROXY_TEXT_FINAL_SOURCE_DENOMINATOR_CHANGED",failedId,failureText),
   Refusal("font-identity-drift",()=>UnityStaticSortTextSource.driftFont=true,"STATIC_SORT_PROXY_TEXT_FINAL_SOURCE_DENOMINATOR_CHANGED",failedId,failureText),
   Refusal("atlas-identity-drift",()=>UnityStaticSortTextSource.driftAtlas=true,"STATIC_SORT_PROXY_TEXT_FINAL_SOURCE_DENOMINATOR_CHANGED",failedId,failureText),
   Refusal("character-asset-drift",()=>UnityStaticSortTextSource.driftCharacters=true,"STATIC_SORT_PROXY_TEXT_FINAL_SOURCE_DENOMINATOR_CHANGED",failedId,failureText),
   Refusal("slot-count-drift",()=>UnityStaticSortTextSource.driftCount=true,"STATIC_SORT_PROXY_TEXT_FINAL_SOURCE_DENOMINATOR_CHANGED",failedId,failureText),
   Refusal("layout-geometry-drift",()=>UnityStaticSortTextSource.driftLayout=true,"STATIC_SORT_PROXY_TEXT_SLOT_SOURCE_IDENTITY_CHANGED",failedId,failureText),
   Refusal("source-mesh-only-drift",()=>UnityStaticSortTextSource.driftMesh=true,"STATIC_SORT_PROXY_TEXT_SLOT_SOURCE_IDENTITY_CHANGED",failedId,failureText),
   Refusal("fallback-material-profile-drift",()=>UnityStaticSortTextSource.driftMaterial=true,"STATIC_SORT_PROXY_TEXT_SLOT_SOURCE_IDENTITY_CHANGED",failedId,failureText),
  };
  UnityStaticSortTextSource.ResetProvider();
  var counts=inventory.GetProperty("counts");
  var receipt=new{contract="monkey-actual17-offline-text-capture-receipt/1",evidenceBoundary=new{unityEditorExecuted=false,tmpNativeRenderingExecuted=false,assetDatabaseExecuted=false,persistentReferences="simulated-valid-identities-only",phaseDeltas="synthetic-provider-stimuli;actual17 failure had no captured field delta",observedSourceInventory=true},textSources=receiptRows};
  if(args.Length>1)File.WriteAllText(args[1],JsonSerializer.Serialize(receipt,new JsonSerializerOptions{IncludeFields=true}));
  var report=new {contract="offline-production-method-extraction/1",actualInputs=new{textGroups=counts.GetProperty("textGroups").GetInt32(),queueRendererRows=queue.Length,observedSlotReadbackLabels=observed,modeledQueueLabels=modeled,nonQueueLabels=inventory.GetProperty("notInQueueRendererInputs").GetArrayLength()},execution=new{queueRowsSucceeded=queue.Length,totalDrawableSlots=totalDrawable,lifecyclePhaseRows=phaseRows,negativeRefusals=refusals.Length,editorExecuted=false,tmpNativeRenderingExecuted=false,assetDatabaseExecuted=false},productionMethodsExecuted=new[]{"CaptureAndRebindTextSlots","CapturedTextSlotSourceIdentityMatches","TextSlotDenominatorMatches","TextLayoutContextMatches","ValidateCapturedSlotTransition","CaptureLifecycleReadyForRebind","CapturePhaseSlotsMatchEnumeration","CaptureLifecycleHash","ValidateCaptureLifecycle","FinalizeCaptureLifecycle","TextSlotRowHash(v2)","TextSlotEnumerationHash(v2)"},providerBoundaries=new[]{"TMP_Text/Graphic/Material/AssetDatabase objects are deterministic stubs","GetCurrentSlots, PrepareSource, fallback profile bake/registration, and RebindCapturedSlot surface are providers","RebindCapturedSlot provider calls exact production ValidateCapturedSlotTransition; full RebindCapturedSlot body is not invoked","IsValidTextScaleContext is a stub validity provider; production TextLayoutContextMatches field comparisons execute"},refusals,failureBoundary=inventory.GetProperty("observedPhaseDeltaBoundary").Clone()};
  Console.WriteLine(JsonSerializer.Serialize(report));
 }
}
}
''' + r'''
namespace UnityEngine {
 public class Object {public string guid,assetPath;public long localFileId;}
 public struct Vector2 {public float x,y;}
 public struct Vector4 {public float x,y,z,w;}
 public class Material:Object {public string fingerprint;public Shader shader;}
 public class Shader:Object {}
 public class Texture:Object {}
 public class Mesh:Object {public int vertexCount;}
 public class Graphic:Object {}
}
namespace TMPro {
 public class TMP_FontAsset:UnityEngine.Object{}
 public class TMP_SpriteAsset:UnityEngine.Object{}
 public class TMP_Text:UnityEngine.Object {public string text;public TMP_FontAsset font;public UnityEngine.Material fontSharedMaterial;public List<Monkey.StaticSortQueueProxy.TextSlotBinding> bindings,finalBindings;public Monkey.StaticSortQueueProxy.NativeStaticSortTextSlotEnumeration enumeration,finalEnumeration;public bool finalSnapshot,driftSlotCount;public string GetParsedText()=>text;}
}
public enum RenderMode {ScreenSpaceOverlay=0,ScreenSpaceCamera=1,WorldSpace=2}
static class Mathf {public static bool Approximately(float a,float b)=>Math.Abs(a-b)<0.0001f;}
static class Canvas {public static void ForceUpdateCanvases(){}}
namespace UnityEditor {
 public static class AssetDatabase {public static bool TryGetGUIDAndLocalFileIdentifier(UnityEngine.Object x,out string g,out long id){g=x?.guid;id=x?.localFileId??0;return x!=null;}public static string GetAssetPath(UnityEngine.Object x)=>x?.assetPath;}
}
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
    result = subprocess.run([dotnet, "exec", str(tmp_path / "bin/Debug/net8.0/Harness.dll"), str(inventory_path), str(receipt_path)], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["execution"]["queueRowsSucceeded"] == 87
    assert report["execution"]["editorExecuted"] is False
    assert report["execution"]["tmpNativeRenderingExecuted"] is False
    assert report["execution"]["assetDatabaseExecuted"] is False
    assert report["actualInputs"]["observedSlotReadbackLabels"] == 57
    assert report["actualInputs"]["modeledQueueLabels"] == 30
    assert report["failureBoundary"]["capturedPerPhaseDelta"] is False
    assert report["execution"]["negativeRefusals"] == 9
    assert "ValidateCapturedSlotTransition" in report["productionMethodsExecuted"]
    assert "full RebindCapturedSlot body is not invoked" in " ".join(report["providerBoundaries"])
    exported = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert len(exported["textSources"]) == report["execution"]["totalDrawableSlots"]
    assert exported["evidenceBoundary"]["persistentReferences"] == "simulated-valid-identities-only"
    assert hashlib.sha256(inventory_path.read_bytes()).hexdigest() == inventory_sha_before
    assert _verify_readonly_pins(inv) == []
    report_path = os.environ.get("MONKEY_TEXT_SLOT_LIFECYCLE_REPORT")
    if report_path:
        destination = Path(report_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
