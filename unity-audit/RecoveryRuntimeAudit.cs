// Run through a supported Editor script host, or place in an isolated Assets/Editor.
// Read-only for target assets; reports use FileMode.CreateNew. Does not open/save scenes.
using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;
public static class RecoveryRuntimeAudit
{
 [Serializable] public class Item {public string kind,path,detail;public Item(string k,string p,string d){kind=k;path=p;detail=d;}}
 [Serializable] public class Report {public string unity,project,scope;public bool playing;public List<Item> observations=new List<Item>();public List<Item> findings=new List<Item>();public string limitations="Presence/reference audit only; not visual parity. Spine source version/atlas pages require separate source audit.";}
 static string PathOf(UnityEngine.Object o){return o?AssetDatabase.GetAssetPath(o):"<null>";}
 static string Node(Transform t){return t.parent?Node(t.parent)+"/"+t.name:t.name;}
 static void Inspect(GameObject go, Report report){
  foreach(var t in go.GetComponentsInChildren<Transform>(true)){
   var name=Node(t);int missing=GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject);
   if(missing>0)report.findings.Add(new Item("missing_script",name,missing.ToString()));
   foreach(var sr in t.GetComponents<SpriteRenderer>()){
    report.observations.Add(new Item("sprite",name,"sprite="+PathOf(sr.sprite)+" texture="+PathOf(sr.sprite?sr.sprite.texture:null)+" layer="+sr.sortingLayerName+" order="+sr.sortingOrder));
    if(sr.sprite&&!sr.sprite.texture)report.findings.Add(new Item("sprite_texture_null",name,PathOf(sr.sprite)));
   }
   foreach(var renderer in t.GetComponents<Renderer>())foreach(var mat in renderer.sharedMaterials){
    if(!mat){report.findings.Add(new Item("material_null",name,""));continue;}
    var shader=mat.shader;var sp=PathOf(shader);
    report.observations.Add(new Item("material",name,"asset="+PathOf(mat)+" shader="+sp+" name="+(shader?shader.name:"null")+" queue="+mat.renderQueue));
    if(!shader||shader.name=="Hidden/InternalErrorShader")report.findings.Add(new Item("shader_missing",name,sp));
    if(shader&&sp.EndsWith(".shader")&&File.Exists(sp)&&File.ReadAllText(sp).Contains("DummyShaderTextExporter"))report.findings.Add(new Item("placeholder_shader",name,sp));
   }
   foreach(var c in t.GetComponents<Component>()){
    if(!c)continue;var type=c.GetType();
    if(type.FullName.StartsWith("Spine.")){
     report.observations.Add(new Item("spine_component",name,type.FullName+" assembly="+type.Assembly.GetName().Version));
     // Read serialized reference fields only, without invoking third-party getters.
     var so=new SerializedObject(c);var data=so.FindProperty("skeletonDataAsset");
     if(data!=null&&data.propertyType==SerializedPropertyType.ObjectReference){
      if(!data.objectReferenceValue)report.findings.Add(new Item("spine_data_null",name,type.FullName));
      else InspectSpineData(data.objectReferenceValue,name,report);
     }
    }
   }
  }
 }
 static void InspectSpineData(UnityEngine.Object asset,string node,Report r){
  var so=new SerializedObject(asset);var json=so.FindProperty("skeletonJSON");
  if(json!=null&&json.objectReferenceValue is TextAsset text){
   var head=System.Text.Encoding.UTF8.GetString(text.bytes,0,Math.Min(512,text.bytes.Length));
   var version=System.Text.RegularExpressions.Regex.Match(head,@"[0-9]+\.[0-9]+\.[0-9]+");
   r.observations.Add(new Item("spine_data_version_candidate",node,version.Success?version.Value:"unknown; binary parser required"));
  }
  var atlases=so.FindProperty("atlasAssets");if(atlases==null||!atlases.isArray)return;
  for(int i=0;i<atlases.arraySize;i++){
   var atlas=atlases.GetArrayElementAtIndex(i).objectReferenceValue;if(!atlas){r.findings.Add(new Item("atlas_null",node,i.ToString()));continue;}
   var a=new SerializedObject(atlas);var file=a.FindProperty("atlasFile");var mats=a.FindProperty("materials");
   var materials=new List<Material>();if(mats!=null&&mats.isArray)for(int j=0;j<mats.arraySize;j++)materials.Add(mats.GetArrayElementAtIndex(j).objectReferenceValue as Material);
   if(file==null||!(file.objectReferenceValue is TextAsset source)){r.observations.Add(new Item("atlas_unchecked",node,PathOf(atlas)));continue;}
   var lines=source.text.Replace("\r","").Split('\n');
   for(int j=0;j<lines.Length-1;j++){
    var page=lines[j].Trim();if(page.Length==0||page.Contains(":"))continue;
    var size=System.Text.RegularExpressions.Regex.Match(lines[j+1],@"^\s*size:\s*(\d+),\s*(\d+)");if(!size.Success)continue;
    var name=Path.GetFileNameWithoutExtension(page);var textures=materials.Where(m=>m&&m.mainTexture&&m.mainTexture.name==name).Select(m=>m.mainTexture).ToArray();
    r.observations.Add(new Item("atlas_page",node,page+" declared="+size.Groups[1].Value+"x"+size.Groups[2].Value));
    if(textures.Length==0)r.findings.Add(new Item("atlas_page_texture_missing",node,page));
    foreach(var t in textures)if(t.width!=int.Parse(size.Groups[1].Value)||t.height!=int.Parse(size.Groups[2].Value))r.findings.Add(new Item("atlas_page_size_mismatch",node,page+" actual="+t.width+"x"+t.height));
   }
  }
 }
 public static string Run(string[] args){
  if(args==null||args.Length!=2)throw new ArgumentException("Run args: Assets/subfolder or @loaded-scenes, new absolute report.json");
  if(!Path.IsPathRooted(args[1])||File.Exists(args[1]))throw new ArgumentException("Report must be a new absolute file");
  var r=new Report{unity=Application.unityVersion,project=Directory.GetParent(Application.dataPath).FullName,scope=args[0],playing=EditorApplication.isPlaying};
  if(args[0]=="@loaded-scenes"){
   for(int i=0;i<UnityEngine.SceneManagement.SceneManager.sceneCount;i++){
    var scene=UnityEngine.SceneManagement.SceneManager.GetSceneAt(i);if(scene.isLoaded)foreach(var go in scene.GetRootGameObjects())Inspect(go,r);
   }
  }else{
   if(args[0]!="Assets"&&!args[0].StartsWith("Assets/"))throw new ArgumentException("Scope must be inside Assets");
   if(args[0].Contains("..")||!AssetDatabase.IsValidFolder(args[0]))throw new ArgumentException("Invalid Assets folder");
   foreach(var guid in AssetDatabase.FindAssets("t:Prefab",new[]{args[0]})){var p=AssetDatabase.GUIDToAssetPath(guid);var go=AssetDatabase.LoadAssetAtPath<GameObject>(p);if(go)Inspect(go,r);}
  }
  foreach(var cam in Resources.FindObjectsOfTypeAll<Camera>())if(cam.gameObject.scene.IsValid())r.observations.Add(new Item("camera",Node(cam.transform),"enabled="+cam.enabled+" depth="+cam.depth+" mask="+cam.cullingMask));
  using(var f=new FileStream(args[1],FileMode.CreateNew,FileAccess.Write))using(var w=new StreamWriter(f))w.Write(JsonUtility.ToJson(r,true));
  return "findings="+r.findings.Count+" observations="+r.observations.Count+" report="+args[1];
 }
 [Serializable] public class TextureReport {public string texture,format,filter,wrap,sha256;public int width,height,mips;public bool srgb,rawEqual;}
 public static string Texture(string[] args){
  if(args==null||args.Length!=3)throw new ArgumentException("Texture args: Assets texture path, original raw file, new report file");
  if(!Path.IsPathRooted(args[2])||File.Exists(args[2]))throw new ArgumentException("New absolute report required");
  var t=AssetDatabase.LoadAssetAtPath<Texture2D>(args[0]);if(!t)throw new Exception("Texture not found");
  var bytes=t.GetRawTextureData<byte>().ToArray();var original=File.ReadAllBytes(args[1]);
  string hash;using(var h=SHA256.Create())hash=BitConverter.ToString(h.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();
  var r=new TextureReport{texture=args[0],format=t.format.ToString(),filter=t.filterMode.ToString(),wrap=t.wrapMode.ToString(),width=t.width,height=t.height,mips=t.mipmapCount,srgb=t.isDataSRGB,rawEqual=bytes.SequenceEqual(original),sha256=hash};
  using(var f=new FileStream(args[2],FileMode.CreateNew,FileAccess.Write))using(var w=new StreamWriter(f))w.Write(JsonUtility.ToJson(r,true));
  return JsonUtility.ToJson(r);
 }
 // Only used in an explicitly isolated test project; never invoke on a game project.
 public static void SelfTest(){
  var project=Directory.GetParent(Application.dataPath).FullName;
  if(!File.Exists(Path.Combine(project,"P0_ISOLATED_TEST")))throw new Exception("Missing isolated-test sentinel");
  var go=new GameObject("AuditFixture");go.AddComponent<MeshRenderer>();
  string a=Path.Combine(project,"audit.json");Run(new[]{"@loaded-scenes",a});
  var r=JsonUtility.FromJson<Report>(File.ReadAllText(a));if(!r.findings.Any(x=>x.kind=="material_null"))throw new Exception("Missed null material");
  UnityEngine.Object.DestroyImmediate(go);
  Run(new[]{"@loaded-scenes",Path.Combine(project,"clean.json")});
  var bytes=new byte[]{0,188,0,64,0,56,0,0};var raw=Path.Combine(project,"raw.bin");File.WriteAllBytes(raw,bytes);
  var t=new Texture2D(1,1,TextureFormat.RGBAHalf,false,true);t.filterMode=FilterMode.Point;t.wrapMode=TextureWrapMode.Clamp;t.LoadRawTextureData(bytes);t.Apply(false,false);AssetDatabase.CreateAsset(t,"Assets/test-vat.asset");
  var text=Texture(new[]{"Assets/test-vat.asset",raw,Path.Combine(project,"texture.json")});
  var tr=JsonUtility.FromJson<TextureReport>(text);if(!tr.rawEqual||tr.srgb||tr.mips!=1)throw new Exception("Raw texture roundtrip failed");
  Debug.Log("P0_RUNTIME_AUDIT_TEST_PASS");
 }
}
