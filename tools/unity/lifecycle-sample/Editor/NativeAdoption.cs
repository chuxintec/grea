using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
// Explicit repair for the owned LC1 sample. Not a source-engine converter.
public static class NativeAdoption {
 public static void Import() {
  if(Application.unityVersion!="6000.6.2f1" || File.Exists("Assets/Generated/Views/Candidate.prefab"))throw new Exception("Pinned fresh isolated candidate required");
  foreach(string path in Directory.GetFiles("Assets/Generated/Art","*.png")) {
   var importer=(TextureImporter)AssetImporter.GetAtPath(path);
   importer.textureShape=TextureImporterShape.Texture2D;importer.textureType=TextureImporterType.Sprite;importer.spriteImportMode=SpriteImportMode.Single;
   importer.SaveAndReimport();AssetDatabase.ImportAsset(path,ImportAssetOptions.ForceUpdate|ImportAssetOptions.ForceSynchronousImport);
   if(AssetDatabase.LoadAssetAtPath<Sprite>(path)==null)throw new Exception("Actual Sprite missing: "+path);
  }
  var scene=EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
  Directory.CreateDirectory("Assets/Game/Scenes");if(!EditorSceneManager.SaveScene(scene,"Assets/Game/Scenes/ImportBootstrap.unity"))throw new Exception("Bootstrap save failed");
  // Invoke the fixed external provider's own generated adapter without replacing it.
  Directory.CreateDirectory("Assets/Generated/Scenes");AssetDatabase.Refresh();
  MonkeyImporter.ImportBatch();
 }
}
