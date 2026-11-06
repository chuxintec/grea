// Verify schema-derived candidates; optionally save a fresh independent Prefab copy. Never invokes game methods.
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Reflection;
using UnityEngine;
using UnityEditor;

namespace Monkey.UnityRecovery {
public static class SourceVerifier {
    [Serializable] public class Spec { public string prefabPath; public string className; public string scriptPath; public string[] fields; public int[] expectedArrayLengths; public string deadlineUtc; public int budgetSeconds; public bool saveRoundtrip; public int expectedSpriteReferences; public bool verifySourceDescriptors; public string expectedScriptGuid; public string expectedPrefabGuid; public string expectedRootName; public Vector3 expectedPosition, expectedScale; public Quaternion expectedRotation; public bool expectedActive; public SpriteSpec[] expectedSprites; public TextureSpec[] expectedTextures; public Move[] formatMoves; }
    [Serializable] public class TextureSpec { public string path,guid,rgbaRawSha256; public int width,height; }
    [Serializable] public class TextureReadback { public string path,guid,rgbaRawSha256,previousCompression,compression; public int width,height; public bool readableRestored,alphaDilationDisabled; }
    [Serializable] public class SpriteSpec { public string name,guid,fileId,textureGuid,sourceFile,sourcePathId,sourceRawSha256; public float x,y,width,height; public bool verifyMesh; public Vector2[] meshVertices,meshUv; public int[] triangleIndices; }
    [Serializable] public class Move { public string from,to,guid,kind; }
    [Serializable] public class Field { public string name; public string type; public int arrayLength; public int nullElements; }
    [Serializable] public class SpriteReference { public string field,sourceFile,sourcePathId,sourceRawSha256,name,guid,localFileId,textureGuid; public int index,vertexCount,triangleIndexCount; public bool sourceGeometryVerified; public Vector2[] vertices,uv; public int[] triangles; }
    [Serializable] public class Result { public string status; public string unityVersion; public string prefabPath; public string guid; public string rootFileId; public string componentFileId; public string scriptGuid; public string scriptFileId; public string scriptClass; public string[] componentTypes; public Vector3 localPosition; public Vector3 localScale; public Quaternion localRotation; public bool active; public int nodeCount; public int missingScripts; public bool classFound; public Field[] fields; public bool saved; public bool prefabReloaded; public bool referencesPreserved; public int spriteReferences; public SpriteReference[] spriteReadback; public TextureReadback[] textureReadback; public Move[] movedAssets; public bool sourceDescriptorsVerified; public bool geometryPreserved; public string error; }
    static string ReferenceSignature(MonoBehaviour component,string[] names,out int count,SpriteSpec[] expected=null,List<SpriteReference> records=null) {
        int found=0;
        var signature=string.Join("|",names.Select(name=>{
            var field=component.GetType().GetField(name,BindingFlags.Instance|BindingFlags.Public|BindingFlags.DeclaredOnly);
            if(field==null)throw new Exception("Missing schema field: "+name);
            var array=field.GetValue(component) as Array;
            return name+":"+(array==null?"null":array.Length.ToString())+":"+(array==null?"":string.Join(",",array.Cast<object>().Select((value,index)=>{
                var asset=value as UnityEngine.Object;
                if(asset==null)throw new Exception("Unresolved dependency; save blocked");
                string guid;long id;
                if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(asset,out guid,out id))throw new Exception("Native reference identity missing");
                if(asset is Sprite) {
                    if(expected!=null) {
                        if(found>=expected.Length)throw new Exception("Unexpected source Sprite reference");
                        var target=(Sprite)asset;var match=expected[found];var rect=target.rect;
                        if(target.name!=match.name||guid!=match.guid||id.ToString(System.Globalization.CultureInfo.InvariantCulture)!=match.fileId||!rect.x.Equals(match.x)||!rect.y.Equals(match.y)||!rect.width.Equals(match.width)||!rect.height.Equals(match.height))throw new Exception("Source Sprite identity/atlas rect differs: "+match.name);
                        string textureGuid;long textureId;
                        if(target.texture==null||!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(target.texture,out textureGuid,out textureId)||textureGuid!=match.textureGuid)throw new Exception("Source Sprite atlas texture differs: "+match.name);
                        if(match.verifyMesh) {
                            var vertices=target.vertices;var triangles=target.triangles;var uv=target.uv;
                            if(match.meshVertices==null||match.meshUv==null||match.triangleIndices==null||vertices.Length!=match.meshVertices.Length||uv.Length!=match.meshUv.Length||triangles.Length!=match.triangleIndices.Length)throw new Exception("Source tight Sprite mesh count differs: "+match.name);
                            for(var i=0;i<vertices.Length;i++)if(!vertices[i].Equals(match.meshVertices[i])||!(Math.Abs(uv[i].x-match.meshUv[i].x)<=0.000001f)||!(Math.Abs(uv[i].y-match.meshUv[i].y)<=0.000001f))throw new Exception("Source tight Sprite vertex/UV differs: "+match.name);
                            for(var i=0;i<triangles.Length;i++)if(triangles[i]!=match.triangleIndices[i])throw new Exception("Source tight Sprite triangle differs: "+match.name);
                        }
                    }
                    if(records!=null) {
                        var evidence=expected!=null&&found<expected.Length?expected[found]:null;
                        var sprite=(Sprite)asset;string actualTextureGuid;long actualTextureId;
                        if(sprite.texture==null||!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(sprite.texture,out actualTextureGuid,out actualTextureId))throw new Exception("Sprite texture identity missing");
                        records.Add(new SpriteReference {field=name,index=index,sourceFile=evidence?.sourceFile,sourcePathId=evidence?.sourcePathId,sourceRawSha256=evidence?.sourceRawSha256,name=sprite.name,guid=guid,localFileId=id.ToString(System.Globalization.CultureInfo.InvariantCulture),textureGuid=actualTextureGuid,vertexCount=sprite.vertices.Length,triangleIndexCount=sprite.triangles.Length,sourceGeometryVerified=evidence!=null&&evidence.verifyMesh,vertices=sprite.vertices,uv=sprite.uv,triangles=sprite.triangles.Select(v=>(int)v).ToArray()});
                    }
                    found++;
                }
                return guid+"/"+id.ToString(System.Globalization.CultureInfo.InvariantCulture);
            })));
        }));
        count=found;return signature;
    }
    public static void Run() {
        var result=new Result { status="failed",unityVersion=Application.unityVersion,saved=false };
        int exitCode=1;
        try {
            if(Application.unityVersion!="6000.6.2f1")throw new Exception("Exact Unity 6000.6.2f1 required");
            var spec=JsonUtility.FromJson<Spec>(File.ReadAllText(File.Exists("Analysis/Plans/native-check-spec.json")||!File.Exists("Analysis/native-check-spec.json")?"Analysis/Plans/native-check-spec.json":"Analysis/native-check-spec.json"));
            if(!spec.prefabPath.StartsWith("Assets/",StringComparison.Ordinal) || spec.prefabPath.Contains("..") || !spec.prefabPath.EndsWith(".prefab",StringComparison.Ordinal)) throw new Exception("Unsafe prefab path");
            if(spec.budgetSeconds<1 || spec.budgetSeconds>1200)throw new Exception("Invalid method budget");
            var started=DateTime.UtcNow;
            var deadline=DateTime.Parse(spec.deadlineUtc,null,System.Globalization.DateTimeStyles.AdjustToUniversal);
            Action checkpoint=()=>{if(DateTime.UtcNow>=deadline || (DateTime.UtcNow-started).TotalSeconds>spec.budgetSeconds)throw new TimeoutException("Native readback deadline");};
            checkpoint();
            var textureReadback=new List<TextureReadback>();
            foreach(var expected in spec.expectedTextures??new TextureSpec[0]) {
                checkpoint();
                if(!expected.path.StartsWith("Assets/",StringComparison.Ordinal)||expected.path.Contains(".."))throw new Exception("Unsafe texture path");
                var importer=AssetImporter.GetAtPath(expected.path)as TextureImporter;
                if(importer==null||AssetDatabase.AssetPathToGUID(expected.path)!=expected.guid)throw new Exception("Texture importer identity differs");
                if(importer.GetPlatformTextureSettings("Standalone").overridden)throw new Exception("Explicit platform texture override requires a separate profile");
                bool readable=importer.isReadable;var previous=importer.textureCompression.ToString();
                string pixelsSha="";int width=0,height=0;
                try {
                    importer.textureCompression=TextureImporterCompression.Uncompressed;importer.alphaIsTransparency=false;importer.isReadable=true;importer.SaveAndReimport();
                    var texture=AssetDatabase.LoadAssetAtPath<Texture2D>(expected.path);width=texture.width;height=texture.height;
                    if(width!=expected.width||height!=expected.height||texture.mipmapCount!=1)throw new Exception("Native texture dimensions/mips differ");
                    var pixels=texture.GetPixels32();var bytes=new byte[pixels.Length*4];
                    for(int i=0;i<pixels.Length;i++){bytes[i*4]=pixels[i].r;bytes[i*4+1]=pixels[i].g;bytes[i*4+2]=pixels[i].b;bytes[i*4+3]=pixels[i].a;}
                    using(var hash=SHA256.Create())pixelsSha=BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-","").ToLowerInvariant();
                    if(pixelsSha!=expected.rgbaRawSha256)throw new Exception("Native imported pixels differ from the exact cache decode: "+pixelsSha);
                } finally {importer.isReadable=readable;importer.SaveAndReimport();}
                textureReadback.Add(new TextureReadback{path=expected.path,guid=AssetDatabase.AssetPathToGUID(expected.path),rgbaRawSha256=pixelsSha,width=width,height=height,readableRestored=importer.isReadable==readable,alphaDilationDisabled=!importer.alphaIsTransparency,previousCompression=previous,compression=importer.textureCompression.ToString()});
            }
            result.textureReadback=textureReadback.ToArray();
            var moves=spec.formatMoves??new Move[0];
            foreach(var move in moves) {
                checkpoint();
                if(!move.from.StartsWith("Assets/",StringComparison.Ordinal)||!move.to.StartsWith("Assets/Game/Content/Images/",StringComparison.Ordinal)||move.from.Contains("..")||move.to.Contains(".."))throw new Exception("Unsafe typed format move");
                var assetType=AssetDatabase.GetMainAssetTypeAtPath(move.from);
                if((move.kind=="sprite"&&assetType!=typeof(Sprite))||(move.kind=="texture"&&assetType!=typeof(Texture2D))||!new[]{"sprite","texture"}.Contains(move.kind))throw new Exception("Format asset type differs");
                if(AssetDatabase.AssetPathToGUID(move.from)!=move.guid||!string.IsNullOrEmpty(AssetDatabase.AssetPathToGUID(move.to)))throw new Exception("Format move identity/collision");
                var parts=Path.GetDirectoryName(move.to).Replace('\\','/').Split('/');var parent="Assets";
                foreach(var part in parts.Skip(1)){var folder=parent+"/"+part;if(!AssetDatabase.IsValidFolder(folder))AssetDatabase.CreateFolder(parent,part);parent=folder;}
                var error=AssetDatabase.MoveAsset(move.from,move.to);
                if(!string.IsNullOrEmpty(error)||AssetDatabase.AssetPathToGUID(move.to)!=move.guid)throw new Exception("Native format move failed: "+error);
            }
            result.movedAssets=moves;
            var prefab=AssetDatabase.LoadAssetAtPath<GameObject>(spec.prefabPath);
            if(prefab==null)throw new Exception("Prefab could not be loaded");
            var nodes=prefab.GetComponentsInChildren<Transform>(true);
            result.prefabPath=spec.prefabPath;result.guid=AssetDatabase.AssetPathToGUID(spec.prefabPath);result.nodeCount=nodes.Length;
            string nativeGuid;long nativeId;
            if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(prefab,out nativeGuid,out nativeId))throw new Exception("Prefab identity unavailable");
            result.rootFileId=nativeId.ToString(System.Globalization.CultureInfo.InvariantCulture);
            result.localPosition=prefab.transform.localPosition;result.localScale=prefab.transform.localScale;result.localRotation=prefab.transform.localRotation;result.active=prefab.activeSelf;
            if(spec.verifySourceDescriptors) {
                if(result.guid!=spec.expectedPrefabGuid||prefab.name!=spec.expectedRootName||prefab.activeSelf!=spec.expectedActive||!prefab.transform.localPosition.Equals(spec.expectedPosition)||!prefab.transform.localScale.Equals(spec.expectedScale)||!prefab.transform.localRotation.Equals(spec.expectedRotation))throw new Exception("Source root identity/geometry differs");
                if(spec.expectedSprites==null||spec.expectedSprites.Length!=spec.expectedSpriteReferences)throw new Exception("Missing exact source Sprite descriptors");
            }
            result.missingScripts=nodes.Sum(t=>GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject));
            var script=AssetDatabase.LoadAssetAtPath<MonoScript>(spec.scriptPath);
            if(script!=null) {
                result.scriptClass=script.GetClass()==null?"":script.GetClass().FullName;
                if(AssetDatabase.TryGetGUIDAndLocalFileIdentifier(script,out nativeGuid,out nativeId)) {result.scriptGuid=nativeGuid;result.scriptFileId=nativeId.ToString(System.Globalization.CultureInfo.InvariantCulture);}
            }
            result.componentTypes=prefab.GetComponentsInChildren<Component>(true).Select(c=>c==null?"<missing>":c.GetType().FullName).ToArray();
            var candidates=prefab.GetComponentsInChildren<MonoBehaviour>(true).Where(c=>c!=null&&c.GetType().FullName==spec.className).ToArray();
            if(candidates.Length!=1)throw new Exception("Expected one unambiguous schema component");
            var component=candidates[0];
            result.classFound=component!=null;
            if(component==null)throw new Exception("Schema-derived component not registered");
            if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(component,out nativeGuid,out nativeId))throw new Exception("Component identity unavailable");
            result.componentFileId=nativeId.ToString(System.Globalization.CultureInfo.InvariantCulture);
            if(script==null || !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(script,out nativeGuid,out nativeId))throw new Exception("Script identity unavailable");
            result.scriptGuid=nativeGuid;result.scriptFileId=nativeId.ToString(System.Globalization.CultureInfo.InvariantCulture);
            var boundScript=MonoScript.FromMonoBehaviour(component);
            if(boundScript!=script||script.GetClass()==null||script.GetClass().FullName!=spec.className||(spec.verifySourceDescriptors&&nativeGuid!=spec.expectedScriptGuid))throw new Exception("Schema component script binding differs");
            result.fields=spec.fields.Select(name=>{
                checkpoint();var f=component.GetType().GetField(name,BindingFlags.Instance|BindingFlags.Public|BindingFlags.DeclaredOnly);
                if(f==null)throw new Exception("Missing schema field: "+name);
                var value=f.GetValue(component);var array=value as Array;
                int missing=array==null?0:array.Cast<object>().Count(v=>v==null || (v is UnityEngine.Object && (UnityEngine.Object)v==null));
                return new Field {name=name,type=f.FieldType.FullName,arrayLength=array==null?-1:array.Length,nullElements=missing};
            }).ToArray();
            if(spec.verifySourceDescriptors && (spec.expectedArrayLengths==null || !result.fields.Select(f=>f.arrayLength).SequenceEqual(spec.expectedArrayLengths) || result.fields.Any(f=>f.type!="UnityEngine.Sprite[]")))throw new Exception("Source array schema/length differs");
            if(spec.saveRoundtrip) {
                int references;var before=ReferenceSignature(component,spec.fields,out references,spec.verifySourceDescriptors?spec.expectedSprites:null);
                if(references!=spec.expectedSpriteReferences)throw new Exception("Sprite reference count differs before save");
                const string folder="Assets/MonkeyRecoveryVerification";
                if(AssetDatabase.IsValidFolder(folder))throw new Exception("Fresh verification folder required");
                AssetDatabase.CreateFolder("Assets","MonkeyRecoveryVerification");
                var copy=folder+"/"+Path.GetFileName(spec.prefabPath);
                var contents=PrefabUtility.LoadPrefabContents(spec.prefabPath);
                try {
                    checkpoint();bool saved;
                    var asset=PrefabUtility.SaveAsPrefabAsset(contents,copy,out saved);
                    if(!saved || asset==null)throw new Exception("Editable prefab save failed");
                    result.saved=true;
                } finally { PrefabUtility.UnloadPrefabContents(contents); }
                AssetDatabase.ImportAsset(copy,ImportAssetOptions.ForceSynchronousImport|ImportAssetOptions.ForceUpdate);
                var reopened=PrefabUtility.LoadPrefabContents(copy);
                try {
                    checkpoint();var typed=reopened.GetComponentsInChildren<MonoBehaviour>(true).FirstOrDefault(c=>c!=null&&c.GetType().FullName==spec.className);
                    if(typed==null || reopened.GetComponentsInChildren<Transform>(true).Sum(t=>GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject))!=0)throw new Exception("Saved prefab component missing");
                    var spriteReadback=new List<SpriteReference>();int reopenedCount;var after=ReferenceSignature(typed,spec.fields,out reopenedCount,spec.verifySourceDescriptors?spec.expectedSprites:null,spriteReadback);
                    if(before!=after || references!=reopenedCount)throw new Exception("Saved prefab references changed");
                    if(reopened.name!=prefab.name||reopened.activeSelf!=prefab.activeSelf||!reopened.transform.localPosition.Equals(prefab.transform.localPosition)||!reopened.transform.localScale.Equals(prefab.transform.localScale)||!reopened.transform.localRotation.Equals(prefab.transform.localRotation))throw new Exception("Saved root geometry changed");
                    result.geometryPreserved=true;result.sourceDescriptorsVerified=spec.verifySourceDescriptors;
                    result.prefabReloaded=true;result.referencesPreserved=true;result.spriteReferences=reopenedCount;result.spriteReadback=spriteReadback.ToArray();
                } finally { PrefabUtility.UnloadPrefabContents(reopened); }
                result.status="resource_subset_verified";
            } else result.status="read_only_partial";
            exitCode=0;
        } catch(Exception error) { result.error=error.GetType().Name+": "+error.Message; }
        Directory.CreateDirectory("Analysis/Readback");File.WriteAllText("Analysis/Readback/unity-source-readback.json",JsonUtility.ToJson(result,true));
        EditorApplication.Exit(exitCode);
    }
}
}
