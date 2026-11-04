using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEditor;
using UnityEditorInternal;
using UnityEngine;
using Monkey.StaticMaskSort;

public static partial class MonkeyImporter
{
    [Serializable] public class StaticMaskContract { public MaskSpec[] masks; public string sourceManifestSha256; }
    static Sprite ResolveStaticMaskSprite(string uuid,Plan plan,Dictionary<string,Sprite> sprites)
    {
        if(String.IsNullOrEmpty(uuid))return null;
        var ids=plan.textures.Where(t=>t.id.EndsWith(":"+uuid,StringComparison.Ordinal)).Select(t=>t.id).Distinct().ToArray();
        if(ids.Length!=1||!sprites.TryGetValue(ids[0],out var sprite))throw new InvalidOperationException("STATIC_MASK_FRAME_IDENTITY_AMBIGUOUS: "+uuid);
        return sprite;
    }
    static Material CreateStaticMaskMaterial(MaskSpec spec)
    {
        if(String.IsNullOrEmpty(spec.unityMaskMaterialPath)||!spec.unityMaskMaterialPath.StartsWith("Assets/Game/Content/Materials/StaticMasks/")||spec.unityMaskMaterialPath.Contains(".."))
            throw new InvalidOperationException("STATIC_MASK_MATERIAL_PATH_INVALID");
        var existing=AssetDatabase.LoadAssetAtPath<Material>(spec.unityMaskMaterialPath);
        if(existing!=null)return existing;
        var shader=AssetDatabase.LoadAssetAtPath<Shader>(spec.unityMaskShaderPath);
        if(shader==null)throw new InvalidOperationException("STATIC_MASK_SHADER_MISSING");
        Directory.CreateDirectory(Path.GetDirectoryName(spec.unityMaskMaterialPath));
        var material=new Material(shader);material.SetFloat("_AlphaThreshold",spec.alphaThreshold);
        File.WriteAllText(spec.unityMaskMaterialPath+".meta","fileFormatVersion: 2\nguid: "+spec.unityMaskMaterialGuid+"\n");
        InternalEditorUtility.SaveToSerializedFileAndForget(new UnityEngine.Object[]{material},spec.unityMaskMaterialPath,true);
        UnityEngine.Object.DestroyImmediate(material);
        AssetDatabase.ImportAsset(spec.unityMaskMaterialPath,ImportAssetOptions.ForceSynchronousImport);
        return AssetDatabase.LoadAssetAtPath<Material>(spec.unityMaskMaterialPath);
    }
    static void CreateStaticMasks(Plan plan,Dictionary<string,GameObject> nodes,Dictionary<string,Sprite> sprites)
    {
        if(plan.staticMasks?.masks==null)return;
        UnityStaticMaskSort.CreateStaticMasks(plan.staticMasks.masks,nodes,id=>ResolveStaticMaskSprite(id,plan,sprites),CreateStaticMaskMaterial);
    }
    static MaskReadback[] ReadStaticMasks(Plan plan,Dictionary<string,GameObject> loaded,Dictionary<string,GameObject> persistent,Dictionary<string,Sprite> sprites)
    {
        return (plan.staticMasks?.masks??Array.Empty<MaskSpec>()).Where(s=>loaded.ContainsKey(s.node)).Select(spec=>{
            var saved=persistent[spec.node].GetComponent<NativeStaticMaskIdentity>();
            if(saved==null||!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(saved,out string guid,out long id)||String.IsNullOrEmpty(guid)||id==0)
                throw new InvalidOperationException("STATIC_MASK_PERSISTENT_IDENTITY_MISSING: "+spec.sourceId);
            var row=UnityStaticMaskSort.ReadStaticMask(spec,loaded[spec.node],sid=>ResolveStaticMaskSprite(sid,plan,sprites));
            if(!row.verified)throw new InvalidOperationException("STATIC_MASK_NATIVE_READBACK_FAILED: "+spec.sourceId);
            return row;
        }).ToArray();
    }
}
