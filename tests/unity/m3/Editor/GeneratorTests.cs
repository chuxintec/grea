using System;
using System.IO;
using System.Linq;
using Grea.Editor;
using Grea.UI.UGUI;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.TestTools;
using UnityEngine.UI;
using Object = UnityEngine.Object;

namespace Grea.Generation.Tests
{
    public sealed class GeneratorTests
    {
        const string TestRoot = "Assets/GreaM3Tests";
        const string Journal = "Temp/grea-m3-journal.json";
        bool owns;
        ProjectGenerator.Request Request => new ProjectGenerator.Request {
            generatorVersion = ProjectGenerator.Version, identity = "synthetic-test",
            bootstrapScene = TestRoot + "/Bootstrap.unity", entryScene = TestRoot + "/Entry.unity",
            bootstrapType = typeof(GeneratorTestBootstrap).FullName, playerSaveNamespace = "player", qaSaveNamespace = "qa" };
        [SetUp] public void Setup()
        {
            if (!File.Exists("grea-m3-test-project.marker")) Assert.Ignore("Only the isolated grea M3 test harness is authorized");
            Assert.IsFalse(Directory.Exists(ProjectGenerator.BasePath)); Assert.IsFalse(Directory.Exists(TestRoot));
            Assert.IsFalse(File.Exists(Journal)); owns = true;
        }
        [TearDown] public void Teardown()
        {
            if (!owns) return;
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            UnityEngine.Rendering.GraphicsSettings.defaultRenderPipeline = null;
            AssetDatabase.DeleteAsset(TestRoot); AssetDatabase.DeleteAsset(ProjectGenerator.BasePath);
            if (File.Exists(Journal)) File.Delete(Journal);
        }
        [Test] public void LoggedErrorIsPersistedAndCannotBecomeRecoverySuccess()
        {
            LogAssert.Expect(LogType.Error, "synthetic import failure");
            bool injected = false;
            Assert.Throws<InvalidOperationException>(() => ProjectGenerator.Generate(Request, Journal, step => {
                if (!injected) { injected = true; Debug.LogError("synthetic import failure"); }
            }));
            var record = JsonUtility.FromJson<ProjectGenerator.Journal>(File.ReadAllText(Journal));
            Assert.IsFalse(record.complete); Assert.AreEqual(1, record.errorCount);
            var before = File.ReadAllBytes(Journal);
            Assert.Throws<InvalidOperationException>(() => ProjectGenerator.Generate(Request, Journal));
            CollectionAssert.AreEqual(before, File.ReadAllBytes(Journal));
        }
        [Test] public void RepeatedGenerationKeepsAssetBytesGuidsAndBindings()
        {
            ProjectGenerator.Generate(Request, Journal); var first = File.ReadAllBytes(Journal);
            var record = JsonUtility.FromJson<ProjectGenerator.Journal>(File.ReadAllText(Journal));
            Assert.AreEqual(8, record.assets.Count); Assert.IsTrue(record.assets.All(x => x.guid.Length == 32 && x.fileIds.Length > 0));
            ProjectGenerator.Generate(Request, Journal); CollectionAssert.AreEqual(first, File.ReadAllBytes(Journal));
            ProjectGenerator.Validate(Request);
        }
        [TestCase(1)] [TestCase(2)] [TestCase(3)] [TestCase(4)] [TestCase(5)] [TestCase(6)] [TestCase(7)] [TestCase(8)]
        public void EveryCompletedAssetCheckpointResumesWithoutChangingIdentity(int stopAfter)
        {
            int steps = 0;
            Assert.Throws<OperationCanceledException>(() => ProjectGenerator.Generate(Request, Journal, step => {
                if (step.StartsWith("after:") && ++steps == stopAfter) throw new OperationCanceledException();
            }));
            var before = JsonUtility.FromJson<ProjectGenerator.Journal>(File.ReadAllText(Journal));
            ProjectGenerator.Generate(Request, Journal);
            foreach (var asset in before.assets) Assert.AreEqual(asset.sha256, ProjectGenerator.Hash(asset.path));
            Assert.IsTrue(JsonUtility.FromJson<ProjectGenerator.Journal>(File.ReadAllText(Journal)).complete);
        }
        [Test] public void InterruptedUncommittedAssetIsRetainedAndNotReplayed()
        {
            Assert.Throws<OperationCanceledException>(() => ProjectGenerator.Generate(Request, Journal, _ => throw new OperationCanceledException()));
            var before = File.ReadAllBytes(Journal);
            Assert.Throws<InvalidOperationException>(() => ProjectGenerator.Generate(Request, Journal));
            CollectionAssert.AreEqual(before, File.ReadAllBytes(Journal));
        }
        [Test] public void ModifiedGeneratedAssetAndMissingManifestRefuseOverwrite()
        {
            ProjectGenerator.Generate(Request, Journal); var path = ProjectGenerator.BasePath + "/ButtonShell.prefab";
            File.AppendAllText(path, "\n# synthetic human modification\n"); var changed = File.ReadAllBytes(path);
            Assert.Throws<InvalidOperationException>(() => ProjectGenerator.Generate(Request, Journal));
            CollectionAssert.AreEqual(changed, File.ReadAllBytes(path));
            File.Delete(Journal); Assert.Throws<InvalidOperationException>(() => ProjectGenerator.Generate(Request, Journal));
            CollectionAssert.AreEqual(changed, File.ReadAllBytes(path));
        }
        [Test] public void VariantOverridesSurviveAndBindingFailuresAreReadOnly()
        {
            ProjectGenerator.Generate(Request, Journal);
            var baseAsset = AssetDatabase.LoadAssetAtPath<GameObject>(ProjectGenerator.BasePath + "/UIHost.prefab");
            var instance = (GameObject)PrefabUtility.InstantiatePrefab(baseAsset); instance.name = "CustomHost";
            var variant = TestRoot + "/CustomHost.prefab";
            PrefabUtility.SaveAsPrefabAsset(instance, variant); Object.DestroyImmediate(instance);
            Assert.AreEqual(PrefabAssetType.Variant, PrefabUtility.GetPrefabAssetType(AssetDatabase.LoadAssetAtPath<GameObject>(variant)));
            var hash = ProjectGenerator.Hash(variant); ProjectGenerator.Generate(Request, Journal); Assert.AreEqual(hash, ProjectGenerator.Hash(variant));
            var loaded = PrefabUtility.LoadPrefabContents(ProjectGenerator.BasePath + "/UIHost.prefab");
            loaded.GetComponent<UIHost>().canvas = null;
            PrefabUtility.SaveAsPrefabAsset(loaded, ProjectGenerator.BasePath + "/UIHost.prefab"); PrefabUtility.UnloadPrefabContents(loaded);
            var broken = ProjectGenerator.Hash(ProjectGenerator.BasePath + "/UIHost.prefab");
            Assert.Throws<InvalidOperationException>(() => ProjectGenerator.Validate(Request));
            Assert.AreEqual(broken, ProjectGenerator.Hash(ProjectGenerator.BasePath + "/UIHost.prefab"));
        }
        [Test] public void OldGeneratorAndMissingTypeRejectedBeforeAssetWrites()
        {
            var old = Request; old.generatorVersion = "0.0.1";
            Assert.Throws<InvalidOperationException>(() => ProjectGenerator.Generate(old, Journal));
            var bad = Request; bad.bootstrapType = "Missing.Bootstrap";
            Assert.Throws<InvalidOperationException>(() => ProjectGenerator.Generate(bad, Journal));
            Assert.IsFalse(Directory.Exists(ProjectGenerator.BasePath));
        }
        [Test] public void DuplicateEventSystemIsRejectedByTheSceneContract()
        {
            ProjectGenerator.Generate(Request, Journal);
            var scene = EditorSceneManager.OpenScene(Request.entryScene, OpenSceneMode.Single);
            new GameObject("DuplicateInputOwner", typeof(UnityEngine.EventSystems.EventSystem));
            Assert.IsTrue(EditorSceneManager.SaveScene(scene, Request.entryScene));
            var error = Assert.Throws<InvalidOperationException>(() => ProjectGenerator.Validate(Request));
            StringAssert.Contains("EventSystem", error.Message);
        }
        [Test] public void PrefabSlotsHaveExplicitNeutralBindingsAndASeparateVisual()
        {
            ProjectGenerator.Generate(Request, Journal);
            var button = AssetDatabase.LoadAssetAtPath<GameObject>(ProjectGenerator.BasePath + "/ButtonShell.prefab");
            var feedback = button.GetComponent<ButtonPressFeedback>();
            Assert.IsNotNull(feedback, "ButtonShell must supply the tested finite feedback component");
            var target = new SerializedObject(feedback).FindProperty("visual").objectReferenceValue as Transform;
            Assert.IsNotNull(target); Assert.AreNotSame(button.transform, target);
            Assert.AreEqual(target.GetComponent<Image>(), button.GetComponent<Button>().targetGraphic);
            Assert.IsTrue(button.GetComponent<Image>().raycastTarget, "The hit target must remain unscaled");
            var text = target.GetComponentInChildren<Text>(true);
            Assert.IsNotNull(text); Assert.IsNotNull(text.font); Assert.IsFalse(text.raycastTarget);
            Assert.IsTrue(target.GetComponentsInChildren<Image>(true).Any(x => x.name == "Icon"));
            var modal = AssetDatabase.LoadAssetAtPath<GameObject>(ProjectGenerator.BasePath + "/ModalShell.prefab");
            Assert.AreEqual(Navigation.Mode.None, modal.GetComponent<ModalPanel>().CloseButton.navigation.mode);
            var bindings = new SerializedObject(modal.GetComponent<ModalPanel>());
            Assert.IsNotNull(bindings.FindProperty("contentSlot")?.objectReferenceValue);
            Assert.IsNotNull(bindings.FindProperty("title")?.objectReferenceValue);
            var host = AssetDatabase.LoadAssetAtPath<GameObject>(ProjectGenerator.BasePath + "/UIHost.prefab");
            Assert.IsNotNull(new SerializedObject(host.GetComponent<UIHost>()).FindProperty("safeAreaRoot")?.objectReferenceValue);
            Assert.AreEqual(new Vector2(1080, 2340), host.GetComponent<CanvasScaler>().referenceResolution);
            Assert.AreEqual(0, BindingValidator.Inspect(host).Count);
        }
        [Test] public void AuthoredPrefabFieldsSurviveSaveUnloadAndReopenWithoutGeneration()
        {
            ProjectGenerator.Generate(Request, Journal);
            string path = ProjectGenerator.BasePath + "/UIHost.prefab";
            var root = PrefabUtility.LoadPrefabContents(path);
            var label = root.GetComponent<UIHost>().openButton.GetComponentInChildren<Text>(true);
            Assert.IsNotNull(label);
            var serialized = new SerializedObject(label);
            serialized.FindProperty("m_Text").stringValue = "AUTHORED LABEL WITH A LONGER TRANSLATED CAPTION";
            serialized.FindProperty("m_FontData.m_FontSize").intValue = 24;
            var visual = label.transform.parent.GetComponent<Image>(); visual.color = Color.magenta;
            ((RectTransform)visual.transform).sizeDelta = new Vector2(-20,-12);
            Assert.IsTrue(serialized.ApplyModifiedPropertiesWithoutUndo());
            PrefabUtility.SaveAsPrefabAsset(root, path); PrefabUtility.UnloadPrefabContents(root);
            AssetDatabase.ImportAsset(path, ImportAssetOptions.ForceSynchronousImport);
            root = PrefabUtility.LoadPrefabContents(path);
            try
            {
                var reopenedLabel = root.GetComponent<UIHost>().openButton.GetComponentInChildren<Text>(true);
                Assert.AreEqual("AUTHORED LABEL WITH A LONGER TRANSLATED CAPTION", reopenedLabel.text);
                Assert.AreEqual(24, reopenedLabel.fontSize);
                Assert.AreEqual(Color.magenta, reopenedLabel.transform.parent.GetComponent<Image>().color);
                Assert.AreEqual(new Vector2(-20,-12), ((RectTransform)reopenedLabel.transform.parent).sizeDelta);
                Assert.AreEqual(0, BindingValidator.Inspect(root).Count);
            }
            finally { PrefabUtility.UnloadPrefabContents(root); }
            Assert.Throws<InvalidOperationException>(() => ProjectGenerator.Generate(Request, Journal));
        }
        [TestCase("UIHost", "safeAreaRoot")]
        [TestCase("ModalShell", "contentSlot")]
        [TestCase("ModalShell", "title")]
        public void MissingSlotReportsAssetComponentFieldWithoutWriting(string asset, string field)
        {
            ProjectGenerator.Generate(Request,Journal);
            string path=ProjectGenerator.BasePath+"/"+asset+".prefab";
            var root=PrefabUtility.LoadPrefabContents(path);
            var component=asset=="UIHost" ? (Component)root.GetComponent<UIHost>() : root.GetComponent<ModalPanel>();
            var serialized=new SerializedObject(component); serialized.FindProperty(field).objectReferenceValue=null;
            serialized.ApplyModifiedPropertiesWithoutUndo(); PrefabUtility.SaveAsPrefabAsset(root,path); PrefabUtility.UnloadPrefabContents(root);
            var before=ProjectGenerator.Hash(path);
            var error=Assert.Throws<InvalidOperationException>(()=>ProjectGenerator.Validate(Request));
            StringAssert.Contains(path,error.Message); StringAssert.Contains(field,error.Message);
            Assert.AreEqual(before,ProjectGenerator.Hash(path));
        }
    }
}
