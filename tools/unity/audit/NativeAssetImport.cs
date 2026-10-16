// Finite offline converter. Copy into an authorized isolated project's Editor directory.
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using Object=UnityEngine.Object;

namespace Grea.Tools
{
    public static class NativeAssetImport
    {
        [Serializable] public sealed class SpriteSpec { public string name,png_sha256; public float[] pivot,border;public float pixels_per_unit; }
        [Serializable] public sealed class Target { public string path;public float[] scale; }
        [Serializable] public sealed class Key { public float time,value; }
        [Serializable] public sealed class Curve {public string target,property;public Key[] keys; }
        [Serializable] public sealed class Event {public float time;public string function; }
        [Serializable] public sealed class Clip {public string name;public float duration;public bool loop;public Curve[] curves;public Event[] events; }
        [Serializable] public sealed class Request {public int schema_version;public string recipe_sha256;public SpriteSpec[] sprites;public Target[] targets;public Clip[] clips; }
        [Serializable] public sealed class FileRow {public string path,guid,sha256; }
        [Serializable] public sealed class Receipt {public int schema_version=1;public string tool="unity_native_assets_editor",status="started",run_id=Guid.NewGuid().ToString("N"),request_sha256,recipe_sha256,error;public FileRow[] outputs;public string scope="Finite native Sprite + linear Transform AnimationClip; no source runtime"; }
        static string Hash(byte[] data) {using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(data)).Replace("-","").ToLowerInvariant();}
        static string Arg(string flag) {var a=Environment.GetCommandLineArgs();int i=Array.IndexOf(a,flag);if(i<0 || i+1>=a.Length)throw new ArgumentException(flag+" required");return a[i+1];}
        static void NoLinks(string path) {for(FileSystemInfo p=File.Exists(path)?(FileSystemInfo)new FileInfo(path):new DirectoryInfo(path);p!=null;p=p is FileInfo f?f.Directory:((DirectoryInfo)p).Parent)if(p.Exists && (p.Attributes&FileAttributes.ReparsePoint)!=0)throw new IOException("Linked path rejected");}
        static bool Finite(float v)=>!float.IsNaN(v)&&!float.IsInfinity(v)&&Math.Abs(v)<=100000;
        static bool Name(string v)=>v!=null && Regex.IsMatch(v,"^[A-Za-z_][A-Za-z0-9_]{0,63}$");
        static bool TargetPath(string v)=>v!=null && v.Length<256 && v.Split('/').Length<=8 && v.Split('/').All(Name);
        public static void Run()
        {
            string input=Path.GetFullPath(Arg("-greaNativeRequest")),root=Arg("-greaNativeRoot"),output=Path.GetFullPath(Arg("-greaNativeReceipt"));
            NoLinks(input);NoLinks(output);NoLinks(Path.GetFullPath(root));
            string project=Path.GetDirectoryName(Application.dataPath);
            if(!root.StartsWith("Assets/",StringComparison.Ordinal) || !TargetPath(root.Substring(7)) || Directory.Exists(root) || File.Exists(root))throw new IOException("New Assets directory required; existing native assets are never overwritten");
            if(output.StartsWith(project+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase) || File.Exists(output) || !Directory.Exists(Path.GetDirectoryName(output)))throw new IOException("New receipt outside project required");
            byte[] raw=File.ReadAllBytes(input);if(raw.Length>8*1024*1024)throw new IOException("Request budget exceeded");
            var request=JsonUtility.FromJson<Request>(System.Text.Encoding.UTF8.GetString(raw));
            var receipt=new Receipt {request_sha256=Hash(raw),recipe_sha256=request.recipe_sha256};
            var paths=new HashSet<string>(StringComparer.OrdinalIgnoreCase);var targets=new HashSet<string>();
            if(request.schema_version!=1 || request.sprites==null || request.targets==null || request.clips==null || request.sprites.Length>64 || request.targets.Length>64 || request.clips.Length>64)throw new ArgumentException("Unsupported request");
            foreach(var s in request.sprites)
            {
                if(!Name(s.name) || !paths.Add(s.name+".png") || s.pivot==null || s.pivot.Length!=2 || s.border==null || s.border.Length!=4 || !s.pivot.All(v=>Finite(v)&&v>=0&&v<=1) || !s.border.All(v=>Finite(v)&&v>=0) || !Finite(s.pixels_per_unit) || s.pixels_per_unit<=0 || s.pixels_per_unit>10000)throw new ArgumentException("Invalid Sprite spec");
                string source=Path.Combine(Path.GetDirectoryName(input),s.name+".png");NoLinks(source);if(!File.Exists(source) || new FileInfo(source).Length>32*1024*1024)throw new IOException("Missing/budgeted PNG");
                if(Hash(File.ReadAllBytes(source))!=s.png_sha256)throw new IOException("PNG identity differs from prepared request");
            }
            foreach(var t in request.targets)if(!TargetPath(t.path) || !targets.Add(t.path) || t.scale==null || t.scale.Length!=3 || !t.scale.All(v=>Finite(v)&&v!=0))throw new ArgumentException("Duplicate/invalid target");
            foreach(var c in request.clips)
            {
                if(!Name(c.name) || !paths.Add(c.name+".anim") || !Finite(c.duration) || c.duration<=0 || c.duration>600 || c.curves==null || c.curves.Length==0 || c.curves.Length>128 || c.events==null || c.events.Length>128)throw new ArgumentException("Invalid clip");
                var bindings=new HashSet<string>();int count=0;
                foreach(var curve in c.curves)
                {
                    if(!targets.Contains(curve.target) || !Regex.IsMatch(curve.property??"","^m_Local(Position|Scale)\\.[xyz]$") || !bindings.Add(curve.target+":"+curve.property) || curve.keys==null || curve.keys.Length<2 || curve.keys.Length>10000)throw new ArgumentException("Missing/duplicate binding");
                    count+=curve.keys.Length;if(count>20000)throw new ArgumentException("Key budget");
                    if(curve.keys[0].time!=0 || curve.keys.Last().time!=c.duration)throw new ArgumentException("Boundary keys required");
                    for(int i=0;i<curve.keys.Length;i++)if(!Finite(curve.keys[i].time) || !Finite(curve.keys[i].value) || (i>0 && curve.keys[i].time<=curve.keys[i-1].time))throw new ArgumentException("Invalid keys");
                }
                foreach(var e in c.events)if(!Finite(e.time) || e.time<0 || e.time>c.duration || e.function!="Pulse")throw new ArgumentException("Unsupported event");
            }
            GameObject go=null;
            try
            {
                Directory.CreateDirectory(root);AssetDatabase.Refresh();
                foreach(var s in request.sprites)
                {
                    string path=root+"/"+s.name+".png";File.Copy(Path.Combine(Path.GetDirectoryName(input),s.name+".png"),path,false);AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceSynchronousImport);
                    var importer=(TextureImporter)AssetImporter.GetAtPath(path);importer.textureType=TextureImporterType.Sprite;importer.spriteImportMode=SpriteImportMode.Single;importer.spritePixelsPerUnit=s.pixels_per_unit;
                    var settings=new TextureImporterSettings();importer.ReadTextureSettings(settings);settings.spriteAlignment=(int)SpriteAlignment.Custom;settings.spritePivot=new Vector2(s.pivot[0],s.pivot[1]);settings.spriteBorder=new Vector4(s.border[0],s.border[1],s.border[2],s.border[3]);importer.SetTextureSettings(settings);
                    importer.textureCompression=TextureImporterCompression.Uncompressed;importer.maxTextureSize=4096;importer.npotScale=TextureImporterNPOTScale.None;importer.mipmapEnabled=false;importer.isReadable=true;importer.SaveAndReimport();
                    var sprite=AssetDatabase.LoadAssetAtPath<Sprite>(path);if(!sprite || sprite.border!=settings.spriteBorder)throw new InvalidOperationException("Sprite readback failed");
                }
                go=new GameObject("NativeRoot");
                foreach(var t in request.targets)
                {
                    Transform current=go.transform;foreach(string part in t.path.Split('/')){var found=current.Find(part);if(!found){found=new GameObject(part).transform;found.SetParent(current,false);}current=found;}
                    current.localScale=new Vector3(t.scale[0],t.scale[1],t.scale[2]);
                }
                if(request.sprites.Length>0){var renderer=go.AddComponent<SpriteRenderer>();renderer.sprite=AssetDatabase.LoadAssetAtPath<Sprite>(root+"/"+request.sprites[0].name+".png");}
                var clips=new List<AnimationClip>();
                foreach(var c in request.clips)
                {
                    var clip=new AnimationClip {name=c.name,frameRate=60,wrapMode=c.loop?WrapMode.Loop:WrapMode.Once};
                    foreach(var curve in c.curves)
                    {
                        var native=new AnimationCurve(curve.keys.Select(k=>new Keyframe(k.time,k.value)).ToArray());
                        for(int i=0;i<native.length;i++){AnimationUtility.SetKeyLeftTangentMode(native,i,AnimationUtility.TangentMode.Linear);AnimationUtility.SetKeyRightTangentMode(native,i,AnimationUtility.TangentMode.Linear);}
                        AnimationUtility.SetEditorCurve(clip,EditorCurveBinding.FloatCurve(curve.target,typeof(Transform),curve.property),native);
                    }
                    AnimationUtility.SetAnimationEvents(clip,c.events.Select(e=>new AnimationEvent {time=e.time,functionName=e.function}).ToArray());
                    var settings=AnimationUtility.GetAnimationClipSettings(clip);settings.loopTime=c.loop;AnimationUtility.SetAnimationClipSettings(clip,settings);
                    AssetDatabase.CreateAsset(clip,root+"/"+c.name+".anim");clips.Add(clip);
                }
                if(clips.Count>0)
                {
                    var controller=AnimatorController.CreateAnimatorControllerAtPath(root+"/Native.controller");var machine=controller.layers[0].stateMachine;
                    foreach(var clip in clips){var state=machine.AddState(clip.name);state.motion=clip;if(!machine.defaultState)machine.defaultState=state;}
                    go.AddComponent<Animator>().runtimeAnimatorController=controller;
                }
                PrefabUtility.SaveAsPrefabAsset(go,root+"/Native.prefab");AssetDatabase.SaveAssets();
                receipt.status="native_assets_created";
            }
            catch(Exception e){receipt.status="failed_partial_outputs_preserved";receipt.error=e.ToString();throw;}
            finally
            {
                if(go)Object.DestroyImmediate(go);
                receipt.outputs=Directory.Exists(root)?Directory.GetFiles(root,"*",SearchOption.AllDirectories).OrderBy(x=>x).Select(x=>new FileRow {path=x,guid=AssetDatabase.AssetPathToGUID(x),sha256=Hash(File.ReadAllBytes(x))}).ToArray():new FileRow[0];
                using(var stream=new FileStream(output,FileMode.CreateNew))using(var writer=new StreamWriter(stream))writer.Write(JsonUtility.ToJson(receipt,true));
            }
        }
    }
}
