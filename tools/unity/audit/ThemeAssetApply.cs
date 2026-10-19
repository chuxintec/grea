// Editor-only companion. Copy only into an authorized isolated project's Editor folder.
// Writes PNG bytes and imports via AssetDatabase; never writes serialized YAML or .meta.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;

namespace Grea.Tools
{
    public static class ThemeAssetApply
    {
        [Serializable] public sealed class SpriteContract { public int width,height; public float[] pivot,border; public float pixels_per_unit; public long file_id; public string mode; }
        [Serializable] public sealed class Mapping { public string usage,asset,source_sha256,replacement_sha256,meta_sha256,guid,before,after; public SpriteContract sprite; }
        [Serializable] public sealed class Change { public string scope,product_id,baseline_product_id,save_namespace,baseline_save_namespace; }
        [Serializable] public sealed class Plan { public int schema_version; public string plan_id,status; public Mapping[] bundle; public Change change_contract; }
        [Serializable] public sealed class Outcome { public string asset,state,sha256; }
        [Serializable] public sealed class Receipt { public int schema_version=1; public string tool="theme_assets_editor",implementation_version="0.1.0"; public string status,action,plan_id,error; public List<Outcome> outcomes=new List<Outcome>(); public bool gameplayOrVisualAcceptance; }
        static string Arg(string key)
        {
            var args=Environment.GetCommandLineArgs();int i=Array.IndexOf(args,key);
            if(i<0 || i+1>=args.Length)throw new ArgumentException("Missing "+key);
            return args[i+1];
        }
        static string Hash(string path)
        {
            using(var h=SHA256.Create()) using(var f=File.OpenRead(path))
                return BitConverter.ToString(h.ComputeHash(f)).Replace("-","").ToLowerInvariant();
        }
        static string SafeMember(string root,string relative)
        {
            if(String.IsNullOrEmpty(relative) || relative.Contains("\\") || relative.Contains(":") || relative.Split('/').Any(p=>p=="" || p=="." || p==".."))throw new IOException("Unsafe relative path");
            root=Path.GetFullPath(root);var path=Path.GetFullPath(Path.Combine(root,relative));
            if(!path.StartsWith(root+Path.DirectorySeparatorChar,StringComparison.Ordinal))throw new IOException("Path escapes root");
            for(var p=path;p!=null;p=Path.GetDirectoryName(p))
            {
                if((File.Exists(p)||Directory.Exists(p)) && (File.GetAttributes(p)&FileAttributes.ReparsePoint)!=0)throw new IOException("Linked path");
                if(p==root)break;
            }
            if(!File.Exists(path))throw new FileNotFoundException(path);
            return path;
        }
        static void Geometry(Mapping row)
        {
            var c=row.sprite;
            var importer=AssetImporter.GetAtPath(row.asset) as TextureImporter;
            var sprite=AssetDatabase.LoadAssetAtPath<Sprite>(row.asset);
            if(c==null || c.mode!="single" || importer==null || importer.spriteImportMode!=SpriteImportMode.Single || sprite==null)throw new IOException("Only existing single Sprite supported");
            importer.GetSourceTextureWidthAndHeight(out int width,out int height);
            if(c.width!=width || c.height!=height || c.pivot==null || c.pivot.Length!=2 || c.border==null || c.border.Length!=4)throw new IOException("Sprite canvas/shape mismatch");
            if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(sprite,out string guid,out long fileID) || guid!=row.guid || fileID!=c.file_id)throw new IOException("GUID/local fileID mismatch");
            var pivot=sprite.pivot;var rect=sprite.rect;var border=sprite.border;
            bool Same(float a,float b)=>Mathf.Abs(a-b)<0.00001f;
            if(!Same(pivot.x/rect.width,c.pivot[0]) || !Same(pivot.y/rect.height,c.pivot[1]) || !Same(sprite.pixelsPerUnit,c.pixels_per_unit) || !Same(border.x,c.border[0]) || !Same(border.y,c.border[1]) || !Same(border.z,c.border[2]) || !Same(border.w,c.border[3]))throw new IOException("Pivot/border/PPU mismatch");
        }
        public static void Run()
        {
            string root=Path.GetFullPath(Path.Combine(Application.dataPath,".."));
            string folder=Path.GetFullPath(Arg("-greaThemeBundle"));
            string output=Path.GetFullPath(Arg("-greaThemeReport"));
            string action=Arg("-greaThemeAction");
            if(action!="apply" && action!="rollback")throw new ArgumentException("Use apply or rollback");
            if(File.Exists(output) || Directory.Exists(output) || !Directory.Exists(Path.GetDirectoryName(output)) || output.StartsWith(root+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase) || output.StartsWith(folder+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new IOException("Use a new receipt outside project and bundle");
            if(folder==root || folder.StartsWith(root+Path.DirectorySeparatorChar,StringComparison.Ordinal) || root.StartsWith(folder+Path.DirectorySeparatorChar,StringComparison.Ordinal))throw new IOException("Bundle and project overlap");
            var result=new Receipt {status="failed_or_partial",action=action};
            try
            {
                var planFile=SafeMember(folder,"theme-plan.json");
                if(new FileInfo(planFile).Length>4*1024*1024)throw new IOException("Plan budget exceeded");
                var plan=JsonUtility.FromJson<Plan>(File.ReadAllText(planFile));
                if(plan.schema_version!=1 || plan.status!="incremental_bundle_prepared_not_applied" || String.IsNullOrEmpty(plan.plan_id) || plan.bundle==null || plan.bundle.Length>256)throw new IOException("Not a prepared theme bundle");
                var change=plan.change_contract;
                if(change==null || change.scope!="ui_ux" || change.product_id!=PlayerSettings.productName || String.Equals(change.product_id,change.baseline_product_id,StringComparison.OrdinalIgnoreCase) || String.Equals(change.save_namespace,change.baseline_save_namespace,StringComparison.OrdinalIgnoreCase) || String.IsNullOrEmpty(change.save_namespace))throw new IOException("Derived product identity/declared save isolation required");
                result.plan_id=plan.plan_id;
                var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);long total=0;
                // Complete preflight before first write. Unknown third-party edits block both actions.
                foreach(var row in plan.bundle)
                {
                    if(row.usage!="ui_sprite" || !row.asset.StartsWith("Assets/",StringComparison.Ordinal) || !row.asset.EndsWith(".png",StringComparison.Ordinal) || !names.Add(row.asset.Normalize()))throw new IOException("Invalid/duplicate PNG target");
                    var target=SafeMember(root,row.asset);var meta=SafeMember(root,row.asset+".meta");
                    var before=SafeMember(folder,row.before);var after=SafeMember(folder,row.after);
                    total+=new FileInfo(target).Length+new FileInfo(before).Length+new FileInfo(after).Length;
                    if(total>192L*1024*1024)throw new IOException("Byte budget exceeded");
                    if(Hash(before)!=row.source_sha256 || Hash(after)!=row.replacement_sha256 || Hash(meta)!=row.meta_sha256)throw new IOException("Stale bundle/meta");
                    var current=Hash(target);
                    if(current!=row.source_sha256 && current!=row.replacement_sha256)throw new IOException("Target has unrelated edits; do not overwrite");
                    if(AssetDatabase.AssetPathToGUID(row.asset)!=row.guid)throw new IOException("Asset GUID mismatch");
                    if(action=="apply" || current==row.source_sha256)Geometry(row);
                }
                foreach(var row in plan.bundle)
                {
                    var target=SafeMember(root,row.asset);var hash=action=="apply"?row.replacement_sha256:row.source_sha256;
                    var item=new Outcome {asset=row.asset,state="unchanged",sha256=Hash(target)};result.outcomes.Add(item);
                    if(item.sha256==hash)continue;
                    var source=SafeMember(folder,action=="apply"?row.after:row.before);
                    var stage=target+".grea-stage-"+Guid.NewGuid().ToString("N");item.state="attempted";
                    try { File.Copy(source,stage,false);File.Replace(stage,target,null); }
                    finally { if(File.Exists(stage))File.Delete(stage); }
                    AssetDatabase.ImportAsset(row.asset,ImportAssetOptions.ForceSynchronousImport|ImportAssetOptions.ForceUpdate);
                    Geometry(row);
                    item.sha256=Hash(target);
                    if(item.sha256!=hash || Hash(target+".meta")!=row.meta_sha256)throw new IOException("Post-import bytes/meta mismatch; preserve failure receipt");
                    item.state="verified";
                }
                result.status="completed_asset_byte_and_importer_checks_only";
            }
            catch(Exception e) {result.error=e.GetType().Name+": "+e.Message;throw;}
            finally
            {
                // New receipt only. A process interruption still requires explicit current-byte recovery.
                using(var f=new FileStream(output,FileMode.CreateNew,FileAccess.Write))
                using(var w=new StreamWriter(f))w.Write(JsonUtility.ToJson(result,true));
            }
        }
    }
}
