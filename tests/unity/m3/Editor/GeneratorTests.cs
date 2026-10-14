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
    }
}
