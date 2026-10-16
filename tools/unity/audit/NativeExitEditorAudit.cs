// Copy into an explicitly authorized isolated project's Editor folder. Never a Runtime package.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.Compilation;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using Object=UnityEngine.Object;

namespace Grea.Tools
{
    public static class NativeExitEditorAudit
    {
        [Serializable] public sealed class Request { public int schema_version; public string[] roots; public string[] dynamic_roots; public string output; }
        [Serializable] public sealed class AssemblyRow { public string name; public string[] source_files; public string[] references; }
        [Serializable] public sealed class TypeRow { public string asset; public string editor_loaded_type; public string identity_layer="Editor loaded type; not actual Player metadata"; public string[] editor_declared_fields; }
        [Serializable] public sealed class InputRow { public string path,guid,sha256; public long bytes; }
        [Serializable] public sealed class ObjectRow { public string path,guid,type,name; public long local_id; public string[] dependencies; public float[] sprite_geometry; }
        [Serializable] public sealed class Report
        {
            public int schema_version=1; public string tool="unity_native_exit_editor",implementation_version="0.1.0",status="editor_observed";
            public string source_format="Unity-Editor-observation-v1",scope="CompilationPipeline and Editor asset observations only";
            public string[] errors=new string[0],unsupported=new string[0],effects={"filesystem_read","new_report_write","Unity_import_and_preview_lifecycle"};
            public InputRow[] asset_inputs;
            public string unity_version,build_target,request_sha256; public string[] roots,dynamic_roots,preloaded_roots,resource_roots,excluded_editor_resources,dependencies,issues;
            public string resources_policy="AssetDatabase files below exact Resources segments in Assets; exclude any exact Editor segment; recursive dependencies, deduplicated with explicit/preloaded roots. Package Resources require explicit roots.";
            public AssemblyRow[] player_compilation; public TypeRow[] editor_asset_types;
            public ObjectRow[] asset_objects;
            public string actual_player_metadata="not_run",native_exit="requires_review";
            public string[] limits={"CompilationPipeline source set and Editor-loaded objects are distinct from actual Player types.","Explicit dynamic roots are caller-declared; reflection/computed keys require review.","Imports/preview loads may write Unity caches and invoke Editor lifecycle code; use an authorized isolated project.","No source graph mechanism, gameplay, stripping or platform acceptance verdict is issued."};
        }
        static string Hash(byte[] bytes) { using(var hash=SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-","").ToLowerInvariant(); }
        static string HashFile(string path) { using(var stream=File.OpenRead(path)) using(var hash=SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-","").ToLowerInvariant(); }
        static void Root(string path)
        {
            if(string.IsNullOrEmpty(path) || !path.StartsWith("Assets/",StringComparison.Ordinal) || path.Contains("\\") || path.Split('/').Any(x=>x==".." || x=="." || x=="")) throw new ArgumentException("Explicit Assets-relative roots required");
            if(!File.Exists(path)) throw new FileNotFoundException("Missing asset root",path);
            var current=new FileInfo(Path.GetFullPath(path)) as FileSystemInfo;
            while(current!=null) { if((current.Attributes&FileAttributes.ReparsePoint)!=0) throw new IOException("Linked asset paths are unsupported"); current=current is FileInfo f?f.Directory:(current as DirectoryInfo)?.Parent; }
        }
        static TypeRow Observe(Object value,string path) => new TypeRow {asset=path,editor_loaded_type=value.GetType().FullName,
            editor_declared_fields=value.GetType().GetFields(System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.DeclaredOnly).Select(x=>x.Name+":"+x.FieldType.FullName).OrderBy(x=>x).ToArray()};
        static void Objects(GameObject root,string asset,List<TypeRow> rows,List<string> issues)
        {
            foreach(var component in root.GetComponentsInChildren<MonoBehaviour>(true))
                if(!component) issues.Add("missing_script:"+asset);
                else rows.Add(Observe(component,asset));
        }
        public static void Run()
        {
            var args=Environment.GetCommandLineArgs();int index=Array.IndexOf(args,"-greaAuditRequest");
            if(index<0 || index+1>=args.Length) throw new ArgumentException("Explicit -greaAuditRequest required");
            var bytes=File.ReadAllBytes(args[index+1]);if(bytes.Length>1024*1024) throw new ArgumentException("Request too large");
            var request=JsonUtility.FromJson<Request>(System.Text.Encoding.UTF8.GetString(bytes));
            if(request.schema_version!=1 || request.roots==null || request.roots.Length==0 || request.roots.Length>256 || request.dynamic_roots==null || request.dynamic_roots.Length>256) throw new ArgumentException("Versioned roots and explicit dynamic_roots array required");
            string project=Path.GetDirectoryName(Application.dataPath), output=Path.GetFullPath(request.output);
            if(!Path.IsPathRooted(request.output) || output.StartsWith(project+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase) || File.Exists(output) || Directory.Exists(output) || !Directory.Exists(Path.GetDirectoryName(output))) throw new IOException("New report must be outside project, with existing parent");
            for(var directory=new DirectoryInfo(Path.GetDirectoryName(output));directory!=null;directory=directory.Parent)
                if((directory.Attributes&FileAttributes.ReparsePoint)!=0) throw new IOException("Linked output ancestors are unsupported");
            foreach(var root in request.roots.Concat(request.dynamic_roots)) Root(root);
            var preloaded=PlayerSettings.GetPreloadedAssets().Where(x=>x).Select(AssetDatabase.GetAssetPath).Where(x=>!string.IsNullOrEmpty(x)).Distinct().OrderBy(x=>x).ToArray();
            var resourceCandidates=AssetDatabase.GetAllAssetPaths().Where(path=>path.StartsWith("Assets/",StringComparison.Ordinal) && !AssetDatabase.IsValidFolder(path) && path.Split('/').Contains("Resources")).OrderBy(x=>x).ToArray();
            var excluded=resourceCandidates.Where(path=>path.Split('/').Contains("Editor")).ToArray();
            var resources=resourceCandidates.Except(excluded).ToArray();
            if(resources.Length>10000) throw new InvalidOperationException("Resources root budget exceeded");
            foreach(var path in resources) Root(path);
            var roots=request.roots.Concat(request.dynamic_roots).Concat(preloaded).Concat(resources).Distinct().ToArray();
            var dependencies=AssetDatabase.GetDependencies(roots,true).Distinct().OrderBy(x=>x).ToArray();
            if(dependencies.Length>10000) throw new InvalidOperationException("Asset dependency budget exceeded");
            var types=new List<TypeRow>();var issues=new List<string>();var objects=new List<ObjectRow>();
            foreach(var scene in EditorBuildSettings.scenes.Where(x=>x.enabled)) if(!roots.Contains(scene.path)) issues.Add("unlisted_build_scene:"+scene.path);
            foreach(var path in dependencies)
            {
                foreach(var asset in AssetDatabase.LoadAllAssetsAtPath(path).Where(x=>x))
                {
                    if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(asset,out string guid,out long local)) continue;
                    float[] geometry=null;
                    if(asset is Sprite sprite) geometry=new[]{sprite.rect.x,sprite.rect.y,sprite.rect.width,sprite.rect.height,sprite.pivot.x,sprite.pivot.y,sprite.border.x,sprite.border.y,sprite.border.z,sprite.border.w,sprite.pixelsPerUnit};
                    var refs=EditorUtility.CollectDependencies(new[]{asset}).Where(x=>x).Select(x=>AssetDatabase.TryGetGUIDAndLocalFileIdentifier(x,out string g,out long id)?g+":"+id:null).Where(x=>x!=null).Distinct().OrderBy(x=>x).ToArray();
                    objects.Add(new ObjectRow {path=path,guid=guid,local_id=local,type=asset.GetType().FullName,name=asset.name,sprite_geometry=geometry,dependencies=refs});
                    if(objects.Count>100000) throw new InvalidOperationException("Object identity budget exceeded");
                }
                if(path.EndsWith(".unity",StringComparison.Ordinal))
                {
                    var scene=EditorSceneManager.OpenPreviewScene(path);
                    try {foreach(var root in scene.GetRootGameObjects()) Objects(root,path,types,issues);}
                    finally {EditorSceneManager.ClosePreviewScene(scene);}
                }
                else if(path.EndsWith(".prefab",StringComparison.Ordinal))
                {
                    var root=PrefabUtility.LoadPrefabContents(path);
                    try {Objects(root,path,types,issues);} finally {PrefabUtility.UnloadPrefabContents(root);}
                }
                else foreach(var asset in AssetDatabase.LoadAllAssetsAtPath(path)) if(asset is ScriptableObject) types.Add(Observe(asset,path));
                if(types.Count>100000) throw new InvalidOperationException("Editor object type budget exceeded");
            }
            var assemblies=CompilationPipeline.GetAssemblies(AssembliesType.Player).Select(x=>new AssemblyRow {name=x.name,source_files=x.sourceFiles.OrderBy(v=>v).ToArray(),references=x.assemblyReferences.Select(r=>r.name).OrderBy(v=>v).ToArray()}).OrderBy(x=>x.name).ToArray();
            if(assemblies.Length==0 || types.Count==0) throw new InvalidOperationException("No compilation/type evidence; not a pass");
            long hashedBytes=0;
            var inputs=dependencies.Select(path=> {
                long size=File.Exists(path)?new FileInfo(path).Length:0;hashedBytes+=size;
                if(hashedBytes>512L*1024*1024) throw new InvalidOperationException("Dependency hash byte budget exceeded");
                return new InputRow {path=path,guid=AssetDatabase.AssetPathToGUID(path),sha256=File.Exists(path)?HashFile(path):null,bytes=size};
            }).ToArray();
            var report=new Report {asset_objects=objects.ToArray(),asset_inputs=inputs,unity_version=Application.unityVersion,build_target=EditorUserBuildSettings.activeBuildTarget.ToString(),request_sha256=Hash(bytes),roots=request.roots,dynamic_roots=request.dynamic_roots,preloaded_roots=preloaded,resource_roots=resources,excluded_editor_resources=excluded,dependencies=dependencies,issues=issues.ToArray(),player_compilation=assemblies,editor_asset_types=types.ToArray()};
            using(var stream=new FileStream(output,FileMode.CreateNew,FileAccess.Write)) using(var writer=new StreamWriter(stream)) writer.WriteLine(JsonUtility.ToJson(report,true));
            Debug.Log("GREA_NATIVE_EXIT_EDITOR_OBSERVED "+assemblies.Length+" assemblies; "+types.Count+" Editor type observations; actual Player metadata still not_run");
        }
    }
}
