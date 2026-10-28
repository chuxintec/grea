#if UNITY_EDITOR
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine.SceneManagement;

// Exact persistent identity and SerializedObject queries; never parses YAML or plays a scene.
public static class BeaverReadback {
    [Serializable] public class Alias { public string name,propertyPath; }
    [Serializable] public class Query { public string asset,nodePath,componentType,propertyPath; }
    [Serializable] public class CameraSpec { public float[] position,euler,background; public bool orthographic; public float size; }
    [Serializable] public class CaptureSpec { public string asset,cameraPath; public int width,height; public bool temporaryCamera; public CameraSpec camera; }
    [Serializable] public class Job { public int schemaVersion; public bool hasCapture; public string projectRoot,stage; public string[] assets; public Alias[] aliases; public Query[] queries; public CaptureSpec capture; }
    [Serializable] public class Identity { public string path,guid,type,name,state; public long localId; }
    [Serializable] public class AssetRow { public string path,importedType; public Identity[] objects; }
    [Serializable] public class Field { public string asset,nodePath,componentType,requestedPath,propertyPath,status,valueType,value,referenceState,error; public Identity owner,reference; }
    [Serializable] public class Frame { public string status,file,cameraPath,mode,alphaDiagnostic,colorDiagnostic; public int width,height,nonTransparentPixels; public bool cameraBoundToPreviewScene,gameplayObserved=false; }
    [Serializable] public class Report { public int schemaVersion=1; public string contract="beaver-native-readback/1",editorVersion,status; public AssetRow[] assets; public Field[] fields; public Frame capture; public string[] errors; }
    static Job job;static Scene queryScene;
    static UnityEngine.Object[] AssetObjects(string path){return AssetDatabase.LoadAllAssetsAtPath(path).Concat(new[]{AssetDatabase.LoadMainAssetAtPath(path)}).Where(o=>o!=null).Distinct().ToArray();}
    static Identity Id(UnityEngine.Object o) {
        if(o==null)return null;
        string guid;long local;
        bool ok=AssetDatabase.TryGetGUIDAndLocalFileIdentifier(o,out guid,out local);
        if(!ok){var source=PrefabUtility.GetCorrespondingObjectFromSource(o);if(source!=null)ok=AssetDatabase.TryGetGUIDAndLocalFileIdentifier(source,out guid,out local);}
        if(!ok&&queryScene.IsValid()){
            var global=GlobalObjectId.GetGlobalObjectIdSlow(o);
            if(global.identifierType==2&&global.targetObjectId!=0&&global.assetGUID.ToString()==AssetDatabase.AssetPathToGUID(queryScene.path)){
                guid=global.assetGUID.ToString();local=checked((long)global.targetObjectId);ok=true;
            }
        }
        return new Identity{path=AssetDatabase.GetAssetPath(o),guid=ok?guid:"",localId=ok?local:0,type=o.GetType().FullName,name=o.name,state=ok?"persistent":"unavailable"};
    }
    static bool Missing(SerializedProperty p) {
        var modern=typeof(SerializedProperty).GetProperty("objectReferenceEntityIdValue");
        if(modern!=null){var v=modern.GetValue(p,null);return v!=null&&!v.Equals(Activator.CreateInstance(modern.PropertyType));}
        var old=typeof(SerializedProperty).GetProperty("objectReferenceInstanceIDValue");return old!=null&&Convert.ToInt32(old.GetValue(p,null))!=0;
    }
    static string Value(SerializedProperty p) {
        var culture=System.Globalization.CultureInfo.InvariantCulture;
        switch(p.propertyType){
            case SerializedPropertyType.String:return p.stringValue;
            case SerializedPropertyType.Boolean:return p.boolValue?"true":"false";
            case SerializedPropertyType.Integer:return p.longValue.ToString(culture);
            case SerializedPropertyType.Float:return p.doubleValue.ToString("R",culture);
            case SerializedPropertyType.Enum:return p.enumValueIndex.ToString(culture);
            case SerializedPropertyType.ObjectReference:return p.objectReferenceValue?p.objectReferenceValue.name:"null";
            default:return "<structured:"+p.propertyType+">";
        }
    }
    static string NodePath(Transform root,Transform node){return AnimationUtility.CalculateTransformPath(node,root);}
    static UnityEngine.Object[] Owners(Query q) {
        var main=AssetDatabase.LoadMainAssetAtPath(q.asset);var go=main as GameObject;
        if(go!=null){
            var nodes=go.GetComponentsInChildren<Transform>(true).Where(t=>NodePath(go.transform,t)==q.nodePath).ToArray();
            if(String.IsNullOrEmpty(q.componentType))return nodes.Select(t=>(UnityEngine.Object)t.gameObject).ToArray();
            return nodes.SelectMany(t=>t.GetComponents<Component>()).Where(c=>c!=null&&c.GetType().FullName==q.componentType).Cast<UnityEngine.Object>().ToArray();
        }
        if(q.asset.EndsWith(".unity",StringComparison.Ordinal)){
            var nodes=queryScene.GetRootGameObjects().SelectMany(g=>g.GetComponentsInChildren<Transform>(true)).Where(t=>FullPath(t)==q.nodePath).ToArray();
            if(String.IsNullOrEmpty(q.componentType))return nodes.Select(t=>(UnityEngine.Object)t.gameObject).ToArray();
            return nodes.SelectMany(t=>t.GetComponents<Component>()).Where(c=>c!=null&&c.GetType().FullName==q.componentType).Cast<UnityEngine.Object>().ToArray();
        }
        if(!String.IsNullOrEmpty(q.nodePath))return new UnityEngine.Object[0];
        return AssetObjects(q.asset).Where(o=>String.IsNullOrEmpty(q.componentType)||o.GetType().FullName==q.componentType).ToArray();
    }
    static Field Read(Query q) {
        string prop=q.propertyPath;var alias=(job.aliases??new Alias[0]).Where(a=>a.name==prop).ToArray();if(alias.Length==1)prop=alias[0].propertyPath;
        var f=new Field{asset=q.asset,nodePath=q.nodePath,componentType=q.componentType,requestedPath=q.propertyPath,propertyPath=prop,status="unknown"};
        try {
            if(q.asset.EndsWith(".unity",StringComparison.Ordinal))queryScene=EditorSceneManager.OpenPreviewScene(q.asset);
            var owners=Owners(q);if(owners.Length!=1){f.error="Owner count="+owners.Length+"; exact unique selector required";return f;}
            f.owner=Id(owners[0]);var so=new SerializedObject(owners[0]);so.Update();var p=so.FindProperty(prop);
            if(p==null){f.error="SerializedProperty not found";return f;}
            f.status="observed";f.valueType=p.propertyType.ToString();f.value=Value(p);
            if(p.propertyType==SerializedPropertyType.ObjectReference){f.reference=Id(p.objectReferenceValue);f.referenceState=p.objectReferenceValue?f.reference.state=="persistent"?"bound":"nonpersistent":Missing(p)?"missing":"null";}
        }catch(Exception e){f.error=e.GetType().Name+": "+e.Message;}
        finally{if(queryScene.IsValid()){EditorSceneManager.ClosePreviewScene(queryScene);queryScene=default(Scene);}}
        return f;
    }
    static string FullPath(Transform t){return (t.root.name+"/"+NodePath(t.root,t)).TrimEnd('/');}
    static Frame Capture(CaptureSpec spec) {
        Scene preview=default(Scene);GameObject tempCamera=null;RenderTexture rt=null;Texture2D tex=null;Camera camera=null;RenderTexture oldTarget=null,oldActive=RenderTexture.active;bool oldEnabled=false;
        try {
            if(spec.asset.EndsWith(".unity",StringComparison.Ordinal))preview=EditorSceneManager.OpenPreviewScene(spec.asset);
            else {preview=EditorSceneManager.NewPreviewScene();var prefab=AssetDatabase.LoadAssetAtPath<GameObject>(spec.asset);if(!prefab)throw new InvalidOperationException("Capture asset is not a GameObject prefab");PrefabUtility.InstantiatePrefab(prefab,preview);}
            if(spec.temporaryCamera){
                tempCamera=new GameObject("BeaverCaptureCamera");SceneManager.MoveGameObjectToScene(tempCamera,preview);camera=tempCamera.AddComponent<Camera>();
                var c=spec.camera;camera.transform.position=new Vector3(c.position[0],c.position[1],c.position[2]);camera.transform.eulerAngles=new Vector3(c.euler[0],c.euler[1],c.euler[2]);camera.orthographic=c.orthographic;camera.orthographicSize=c.size;
                camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(c.background[0],c.background[1],c.background[2],c.background[3]);
            }else {
                var cameras=preview.GetRootGameObjects().SelectMany(g=>g.GetComponentsInChildren<Camera>(true)).Where(c=>FullPath(c.transform)==spec.cameraPath).ToArray();
                if(cameras.Length!=1)throw new InvalidOperationException("Capture camera selector count="+cameras.Length);camera=cameras[0];
            }
            if(camera.gameObject.scene!=preview)throw new InvalidOperationException("Camera is not bound to owned preview scene");
            // A preview scene camera requires an explicit scene render binding (not merely scene membership).
            camera.scene=preview;
            foreach(var canvas in preview.GetRootGameObjects().SelectMany(g=>g.GetComponentsInChildren<Canvas>(true))){
                if(canvas.renderMode==RenderMode.ScreenSpaceOverlay)throw new InvalidOperationException("ScreenSpaceOverlay capture requires a runtime camera; no implicit canvas conversion");
            }
            oldEnabled=camera.enabled;oldTarget=camera.targetTexture;camera.enabled=false;
            rt=new RenderTexture(spec.width,spec.height,24,RenderTextureFormat.ARGB32);rt.Create();camera.targetTexture=rt;
            camera.aspect=(float)spec.width/spec.height;camera.Render();RenderTexture.active=rt;
            tex=new Texture2D(spec.width,spec.height,TextureFormat.RGBA32,false);tex.ReadPixels(new Rect(0,0,spec.width,spec.height),0,0);tex.Apply();
            var pixels=tex.GetPixels32();int visible=0;bool uniform=true;var first=pixels[0];foreach(var p in pixels){if(p.a>0)visible++;if(p.r!=first.r||p.g!=first.g||p.b!=first.b||p.a!=first.a)uniform=false;}
            const string file="capture.png";File.WriteAllBytes(Path.Combine(job.stage,file),tex.EncodeToPNG());
            return new Frame{status="captured",file=file,cameraPath=FullPath(camera.transform),mode="editor-preview-offscreen",width=spec.width,height=spec.height,nonTransparentPixels=visible,alphaDiagnostic=visible==0?"fully-transparent":"has-nontransparent-pixels",colorDiagnostic=uniform?"uniform-frame":"nonuniform-frame",cameraBoundToPreviewScene=true};
        }finally {
            RenderTexture.active=oldActive;if(camera){camera.targetTexture=oldTarget;camera.enabled=oldEnabled;}
            if(rt){rt.Release();UnityEngine.Object.DestroyImmediate(rt);}if(tex)UnityEngine.Object.DestroyImmediate(tex);
            if(preview.IsValid())EditorSceneManager.ClosePreviewScene(preview);
        }
    }
    public static void Run() {
        var report=new Report{editorVersion=Application.unityVersion,status="failed",capture=new Frame{status="not_requested"}};var errors=new List<string>();int exit=1;
        try {
            string encoded=Environment.GetEnvironmentVariable("BEAVER_NATIVE_JOB_BASE64");if(String.IsNullOrEmpty(encoded))throw new InvalidOperationException("Missing controlled job channel");
            string path=System.Text.Encoding.UTF8.GetString(Convert.FromBase64String(encoded));job=JsonUtility.FromJson<Job>(File.ReadAllText(path));
            if(job.schemaVersion!=1||Path.GetFullPath(Path.Combine(Application.dataPath,"..")).TrimEnd(Path.DirectorySeparatorChar)!=Path.GetFullPath(job.projectRoot).TrimEnd(Path.DirectorySeparatorChar))throw new InvalidOperationException("Job/project identity mismatch");
            var rows=new List<AssetRow>();foreach(var p in job.assets){var type=AssetDatabase.GetMainAssetTypeAtPath(p);rows.Add(new AssetRow{path=p,importedType=type==null?"":type.FullName,objects=AssetObjects(p).Select(Id).ToArray()});}
            report.assets=rows.ToArray();report.fields=(job.queries??new Query[0]).Select(Read).ToArray();if(job.hasCapture)report.capture=Capture(job.capture);
            report.status=report.fields.Any(f=>f.status!="observed")||report.assets.Any(a=>String.IsNullOrEmpty(a.importedType)||a.objects.Length==0)?"partial":"observed";exit=0;
        }catch(Exception e){errors.Add(e.ToString());}
        report.errors=errors.ToArray();if(job!=null)File.WriteAllText(Path.Combine(job.stage,"readback.json"),JsonUtility.ToJson(report,true));EditorApplication.Exit(exit);
    }
}
#endif
