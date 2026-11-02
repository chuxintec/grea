// Bounded native static validation of a source-derived Unity Prefab plan.
// This bridge never invokes source behavior and writes only owned readback copies.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace MonkeyUnitySource
{
    public static partial class UnityPrefabStaticReadback
    {
        [Serializable] sealed class Plan
        {
            public int schemaVersion;
            public string targetUnityVersion;
            public string outputRelative;
            public bool headless;
            public bool reopenOnly;
            public bool reconstructRoots;
            public RootPlan[] roots;
        }

        [Serializable] sealed class RootPlan
        {
            public string path;
            public string sourceId;
            public bool isRepresentative;
            public NodePlan[] nodes;
        }

        [Serializable] sealed class NodePlan
        {
            public string sourceId;
            public int[] indices;
            public string name;
            public bool active;
            public int layer;
            public string tag;
            public ComponentPlan[] components;
        }

        [Serializable] sealed class ComponentPlan
        {
            public string sourceId;
            public string type;
            public string assembly;
            public bool disabledUnavailable;
            public FieldPlan[] fields;
        }

        [Serializable] sealed class FieldPlan
        {
            public string path;
            public string kind;
            public long intValue;
            public double floatValue;
            public string stringValue;
            public bool boolValue;
            public string refSourceId;
            public string refType;
            public string refName;
            public string refGuid;
            public string refLocalId;
            public bool isNull;
        }

        [Serializable] sealed class Readback
        {
            public int schemaVersion = 1;
            public string status;
            public string editorVersion;
            public string targetVersion;
            public string planSha256;
            public string outputRelative;
            public RootResult[] roots;
            public string sourceCodeExecution = "not_invoked_by_readback; editor_domain_lifecycle_not_independently_audited";
            public string dynamicBehavior = "not_run";
            public string businessBehavior = "not_run";
        }

        [Serializable] sealed class RootResult
        {
            public string sourceId;
            public string sourcePrefabPath;
            public string readbackPrefabPath;
            public string readbackPrefabGuid;
            public string status;
            public int sourceNodes;
            public int sourceComponents;
            public int fieldsExpected;
            public int fieldsCheckedBeforeSave;
            public int fieldsCheckedAfterReopen;
            public int missingScripts;
            public bool saved;
            public bool reopened;
            public bool nativeIdentitiesStable;
            public bool reconstructedFromSource;
            public NativeIdentity[] nativeIdentitiesBefore;
            public NativeIdentity[] nativeIdentitiesAfter;
            public DisabledBehavior[] disabledBehaviors;
            public AssetReferenceIdentity[] assetReferences;
            public AssetReferenceIdentity[] assetReferencesAfter;
            public FieldResult[] fieldResults;
            public FieldResult[] fieldResultsAfter;
            public ImageResult image;
            public EditResult[] editability;
            public string visualCompleteness;
            public string[] limitations;
            public Failure[] failures;
        }

        [Serializable] sealed class NativeIdentity
        {
            public string sourceId;
            public string kind;
            public string guid;
            public string localFileId;
            public string type;
            public string assembly;
            public string name;
            public string assetPath;
        }

        [Serializable] sealed class DisabledBehavior
        {
            public string sourceId;
            public bool sourceEnabled;
            public bool nativeEnabledBeforeDisabling;
            public bool readbackEnabled;
        }

        [Serializable] sealed class AssetReferenceIdentity
        {
            public string ownerSourceId;
            public string fieldPath;
            public string sourceReferenceId;
            public string guid;
            public string localFileId;
            public string assetPath;
            public string type;
            public string assembly;
            public string name;
            public bool isNull;
            public string monoScriptGuid;
            public string monoScriptLocalFileId;
        }

        [Serializable] sealed class FieldResult
        {
            public string sourceId;
            public string path;
            public string kind;
            public string propertyType;
            public bool passed;
            public string expected;
            public string actual;
            public AssetReferenceIdentity reference;
            public string error;
        }

        [Serializable] sealed class ImageResult
        {
            public string status;
            public string path;
            public string sha256;
            public int width;
            public int height;
            public int nonBackgroundPixels;
            public int activeRectCount;
            public int activeGraphicCount;
            public int activeTextCount;
            public float boundsWidth;
            public float boundsHeight;
            public float canvasWidthPixels;
            public float canvasHeightPixels;
            public float referencePixelsPerUnit;
            public string framing;
            public string error;
        }

        [Serializable] sealed class EditResult
        {
            public string kind;
            public string status;
            public string targetSourceId;
            public string beforeImagePath;
            public string beforeImageSha256;
            public string afterImagePath;
            public string afterImageSha256;
            public int changedPixels;
            public bool valueChanged;
            public string beforeValue;
            public string afterValue;
            public string reason;
        }

        [Serializable] sealed class Failure
        {
            public string phase;
            public string message;
        }

        sealed class MappedTree
        {
            public readonly Dictionary<string, GameObject> nodes = new Dictionary<string, GameObject>(StringComparer.Ordinal);
            public readonly Dictionary<string, Component> components = new Dictionary<string, Component>(StringComparer.Ordinal);
            public readonly Dictionary<string, ComponentPlan> componentPlans = new Dictionary<string, ComponentPlan>(StringComparer.Ordinal);
            public readonly List<NativeIdentity> identities = new List<NativeIdentity>();
            public readonly List<AssetReferenceIdentity> references = new List<AssetReferenceIdentity>();
            public readonly List<FieldResult> fields = new List<FieldResult>();
            public int componentCount;
            public int fieldsExpected;
            public int fieldsChecked;
        }

        sealed class CaptureFrame
        {
            public ImageResult result;
            public Color32[] pixels;
            public byte[] pngBytes;
        }

        static readonly CultureInfo Invariant = CultureInfo.InvariantCulture;
        const int MaxPlanBytes = 32 * 1024 * 1024;
        const int MaxRoots = 500;
        const int MaxNodesPerRoot = 20000;
        const int MaxFieldsPerRoot = 250000;
        const int MaxTotalNodes = 100000;
        const int MaxTotalComponents = 250000;
        const int MaxTotalFields = 500000;
        const int MaxRepresentativeRoots = 8;
        const int CaptureSize = 512;

        public static void Run()
        {
            Readback report = null;
            string outputPath = null;
            int exit = 1;
            try
            {
                if (Application.unityVersion != "6000.6.2f1")
                    throw new InvalidOperationException("Exact Unity 6000.6.2f1 is required; actual=" + Application.unityVersion);
                if (EditorApplication.isCompiling || EditorApplication.isUpdating)
                    throw new InvalidOperationException("Editor compilation/import is still active");

                string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
                string planPath = RequiredEnvironment("MONKEY_UNITY_PREFAB_PLAN");
                string expectedPlanHash = RequiredEnvironment("MONKEY_UNITY_PREFAB_PLAN_SHA256");
                if (!Path.IsPathRooted(planPath)) throw new InvalidOperationException("Plan path must be absolute");
                if (!IsSha256(expectedPlanHash)) throw new InvalidOperationException("Plan SHA-256 must be lowercase hexadecimal");
                byte[] planBytes = ReadBounded(planPath, MaxPlanBytes);
                string actualPlanHash = Sha256(planBytes);
                if (!String.Equals(actualPlanHash, expectedPlanHash, StringComparison.Ordinal))
                    throw new InvalidOperationException("Plan bytes do not match MONKEY_UNITY_PREFAB_PLAN_SHA256");
                string json = new UTF8Encoding(false, true).GetString(planBytes);
                Plan plan = JsonUtility.FromJson<Plan>(json);
                ValidatePlan(plan);
                outputPath = SafeReadbackPath(projectRoot, plan.outputRelative);
                if (File.Exists(outputPath)) throw new InvalidOperationException("Readback output already exists; refusing overwrite: " + plan.outputRelative);
                string outputDirectory = Path.GetDirectoryName(outputPath);
                if (String.IsNullOrEmpty(outputDirectory)) throw new InvalidOperationException("Readback output has no parent directory");
                Directory.CreateDirectory(outputDirectory);

                report = new Readback {
                    status = "running", editorVersion = Application.unityVersion,
                    targetVersion = plan.targetUnityVersion, planSha256 = actualPlanHash,
                    outputRelative = plan.outputRelative, roots = new RootResult[plan.roots.Length]
                };
                bool foundRepresentative = plan.roots.Any(r => r.isRepresentative);
                bool implicitRepresentativeSelected = false;
                for (int i = 0; i < plan.roots.Length; i++)
                {
                    RootPlan root = plan.roots[i];
                    bool representative = root.isRepresentative;
                    if (!foundRepresentative && !implicitRepresentativeSelected && IsUiPlan(root))
                    {
                        representative = true;
                        implicitRepresentativeSelected = true;
                    }
                    report.roots[i] = plan.reopenOnly ? VerifyColdRoot(projectRoot, root) : VerifyRoot(projectRoot, root, representative, plan.headless, plan.reconstructRoots);
                }
                bool allPassed = report.roots.All(r => r != null && r.status == "passed");
                bool anyFailed = report.roots.Any(r => r == null || r.status == "failed");
                bool anyPartial = report.roots.Any(r => r != null && r.status == "partial");
                report.status = anyFailed ? "failed" : (anyPartial ? "partial" : "completed");
                File.WriteAllText(outputPath, JsonUtility.ToJson(report, true), new UTF8Encoding(false));
                exit = allPassed ? 0 : 1;
            }
            catch (Exception error)
            {
                Debug.LogError("UNITY_PREFAB_STATIC_READBACK_FAILED: " + error);
                if (report != null && !String.IsNullOrEmpty(outputPath))
                {
                    report.status = "failed";
                    try { File.WriteAllText(outputPath, JsonUtility.ToJson(report, true), new UTF8Encoding(false)); }
                    catch (Exception writeError) { Debug.LogError("Readback result write failed: " + writeError.Message); }
                }
                exit = 1;
            }
            finally
            {
                Debug.Log("UNITY_PREFAB_STATIC_READBACK_EXIT=" + exit.ToString(Invariant));
                if (Application.isBatchMode) EditorApplication.Exit(exit);
            }
        }

        static RootResult VerifyColdRoot(string projectRoot, RootPlan plan)
        {
            var result = new RootResult { sourceId = plan.sourceId, sourcePrefabPath = plan.path, status = "failed" };
            var failures = new List<Failure>();
            GameObject contents = null;
            try
            {
                ValidateAssetPrefabPath(projectRoot, plan.path);
                PreflightPlanCallbacks(plan);
                GameObject asset = AssetDatabase.LoadAssetAtPath<GameObject>(plan.path);
                if (asset == null) throw new InvalidOperationException("Cold-reopen Prefab is absent");
                MappedTree mapped = CheckTree(plan, asset, "independent-cold-asset", false, true, result, failures);
                contents = PrefabUtility.LoadPrefabContents(plan.path);
                if (contents == null) throw new InvalidOperationException("Cold LoadPrefabContents returned null");
                CheckTree(plan, contents, "independent-cold-contents", false, false, result, failures);
                result.sourceNodes = plan.nodes.Length;
                result.sourceComponents = mapped.componentCount;
                result.fieldsExpected = mapped.fieldsExpected;
                result.fieldsCheckedAfterReopen = mapped.fieldsChecked;
                result.fieldResultsAfter = mapped.fields.ToArray();
                result.nativeIdentitiesAfter = mapped.identities.ToArray();
                result.assetReferencesAfter = mapped.references.ToArray();
                result.reopened = true;
                result.readbackPrefabPath = plan.path;
                result.readbackPrefabGuid = AssetDatabase.AssetPathToGUID(plan.path);
                result.visualCompleteness = "not_run_independent_cold_reopen";
                result.limitations = new string[] { "static-render-deferred-no-graphics", "unavailable-source-behavior-remains-disabled" };
                result.status = "partial";
            }
            catch (Exception error)
            {
                failures.Add(new Failure { phase = "independent-cold-reopen", message = error.ToString() });
                result.status = "failed";
                Debug.LogError(error);
            }
            finally
            {
                if (contents != null) PrefabUtility.UnloadPrefabContents(contents);
            }
            result.failures = failures.ToArray();
            return result;
        }

        static RootResult VerifyRoot(string projectRoot, RootPlan plan, bool representative, bool headless, bool reconstruct)
        {
            RootResult result = new RootResult {
                sourceId = plan.sourceId, sourcePrefabPath = plan.path, status = "failed",
                nativeIdentitiesStable = false, visualCompleteness = "not_run",
                limitations = new string[0], failures = new Failure[0],
                fieldResults = new FieldResult[0], assetReferences = new AssetReferenceIdentity[0],
                fieldResultsAfter = new FieldResult[0], assetReferencesAfter = new AssetReferenceIdentity[0],
                editability = new EditResult[0], disabledBehaviors = new DisabledBehavior[0]
            };
            var failures = new List<Failure>();
            result.reconstructedFromSource = reconstruct;
            var limitations = new List<string>();
            string readbackAsset = null;
            GameObject contents = null;
            try
            {
                ValidateAssetPrefabPath(projectRoot, plan.path);
                string sourceGuid = AssetDatabase.AssetPathToGUID(plan.path);
                if (String.IsNullOrEmpty(sourceGuid)) throw new InvalidOperationException("Source Prefab is not an owned project asset: " + plan.path);
                readbackAsset = plan.path;
                string fullReadbackAsset = Path.GetFullPath(Path.Combine(projectRoot, readbackAsset.Replace('/', Path.DirectorySeparatorChar)));
                RequireWithin(projectRoot, fullReadbackAsset, "candidate Prefab");

                PreflightPlanCallbacks(plan);
                if (reconstruct) ReconstructRoot(projectRoot, plan);

                GameObject sourceAsset = AssetDatabase.LoadAssetAtPath<GameObject>(plan.path);
                if (sourceAsset == null) throw new InvalidOperationException("Candidate Prefab asset could not be loaded");
                MappedTree before = CheckTree(plan, sourceAsset, "source-asset", !reconstruct, true, result, failures);
                result.sourceNodes = plan.nodes.Length;
                result.sourceComponents = before.componentCount;
                result.fieldsExpected = before.fieldsExpected;
                result.fieldsCheckedBeforeSave = before.fieldsChecked;
                result.fieldResults = before.fields.ToArray();
                result.nativeIdentitiesBefore = before.identities.ToArray();
                result.assetReferences = before.references.ToArray();

                contents = PrefabUtility.LoadPrefabContents(plan.path);
                if (contents == null) throw new InvalidOperationException("LoadPrefabContents returned null");
                EnsureNoGameLifecycleCallbacks(contents, plan.sourceId);
                MappedTree beforeContents = CheckTree(plan, contents, "source-load", !reconstruct, false, result, failures);
                if (GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(contents) != 0)
                    throw new InvalidOperationException("MissingScript component found on root");

                var disabledRows = new List<DisabledBehavior>();
                foreach (var pair in beforeContents.componentPlans)
                {
                    if (!pair.Value.disabledUnavailable) continue;
                    MonoBehaviour behaviour = beforeContents.components[pair.Key] as MonoBehaviour;
                    if (behaviour == null) throw new InvalidOperationException("disabledUnavailable applies to a non-MonoBehaviour: " + pair.Key);
                    FieldResult sourceEnabled = before.fields.FirstOrDefault(f => f.sourceId == pair.Key && f.path == "m_Enabled");
                    bool enabledBefore = behaviour.enabled;
                    if (sourceEnabled != null) sourceEnabled.actual = enabledBefore.ToString();
                    behaviour.enabled = false;
                    if (behaviour.enabled) throw new InvalidOperationException("Could not disable explicitly unavailable MonoBehaviour: " + pair.Key);
                    FieldPlan sourcePlan = (pair.Value.fields ?? new FieldPlan[0]).FirstOrDefault(f => f.path == "m_Enabled");
                    bool sourceValue = sourcePlan != null ? sourcePlan.boolValue : enabledBefore;
                    disabledRows.Add(new DisabledBehavior { sourceId = pair.Key, sourceEnabled = sourceValue, nativeEnabledBeforeDisabling = enabledBefore, readbackEnabled = behaviour.enabled });
                    limitations.Add("disabled-unavailable:" + pair.Key + ":sourceEnabled=" + sourceValue.ToString().ToLowerInvariant());
                }
                result.disabledBehaviors = disabledRows.ToArray();

                bool saved;
                GameObject savedAsset = PrefabUtility.SaveAsPrefabAsset(contents, readbackAsset, out saved);
                if (!saved || savedAsset == null) throw new InvalidOperationException("SaveAsPrefabAsset failed for candidate Prefab");
                result.saved = true;
                PrefabUtility.UnloadPrefabContents(contents);
                contents = null;
                AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
                GameObject imported = AssetDatabase.LoadAssetAtPath<GameObject>(readbackAsset);
                if (imported == null) throw new InvalidOperationException("Saved readback Prefab could not be loaded");
                result.readbackPrefabPath = readbackAsset;
                result.readbackPrefabGuid = AssetDatabase.AssetPathToGUID(readbackAsset);
                if (String.IsNullOrEmpty(result.readbackPrefabGuid)) throw new InvalidOperationException("Saved readback Prefab GUID is unavailable");
                if (!String.Equals(sourceGuid, result.readbackPrefabGuid, StringComparison.Ordinal))
                    throw new InvalidOperationException("Candidate Prefab GUID changed during same-path save");

                contents = PrefabUtility.LoadPrefabContents(readbackAsset);
                if (contents == null) throw new InvalidOperationException("Reopened readback Prefab is null");
                MappedTree afterContents = CheckTree(plan, contents, "saved-reopen", false, false, result, failures);
                result.reopened = true;
                result.fieldsCheckedAfterReopen = afterContents.fieldsChecked;
                if (GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(contents) != 0)
                    throw new InvalidOperationException("MissingScript component appeared after reopen");
                foreach (DisabledBehavior disposition in result.disabledBehaviors)
                {
                    Component savedComponent;
                    if (!afterContents.components.TryGetValue(disposition.sourceId, out savedComponent) || !(savedComponent is MonoBehaviour))
                        throw new InvalidOperationException("disabledUnavailable source component is absent after reopen: " + disposition.sourceId);
                    disposition.readbackEnabled = ((MonoBehaviour)savedComponent).enabled;
                    if (disposition.readbackEnabled)
                        throw new InvalidOperationException("disabledUnavailable component was re-enabled after Prefab save/reopen: " + disposition.sourceId);
                }
                MappedTree after = CheckTree(plan, imported, "saved-asset-reopen", false, true, result, failures);
                result.nativeIdentitiesAfter = after.identities.ToArray();
                result.assetReferencesAfter = after.references.ToArray();
                result.fieldResultsAfter = after.fields.ToArray();
                result.nativeIdentitiesStable = SameNativeIdentities(before.identities, after.identities);
                if (!result.nativeIdentitiesStable) throw new InvalidOperationException("Node/component GUID or local file IDs changed after save/reopen");
                CompareReferenceTables(before.references, after.references);

                bool hasUi = IsUiPlan(plan);
                if (headless)
                {
                    result.image = new ImageResult { status = "not_run_headless", error = "Rendering and visible edits deferred; no graphics device requested" };
                    result.visualCompleteness = "not_run_headless";
                    limitations.Add("static-render-deferred-no-graphics");
                }
                else if (hasUi)
                {
                    result.image = RenderPrefab(projectRoot, imported, result.readbackPrefabGuid, plan, out EditResult[] edits, representative);
                    result.editability = edits;
                    result.visualCompleteness = limitations.Any(v => v.StartsWith("disabled-unavailable:", StringComparison.Ordinal))
                        ? "partial-disabled-components" : "static-rendered";
                    if (result.image == null || result.image.status != "passed")
                        failures.Add(new Failure { phase = "visual", message = result.image == null ? "No image evidence" : result.image.error });
                    if (representative && !edits.Any(e => e.status == "passed"))
                        limitations.Add("representative-editability-no-applicable-native-ui-field");
                    foreach (EditResult edit in edits.Where(e => e.status == "failed"))
                        failures.Add(new Failure { phase = "editability/" + edit.kind, message = edit.reason });
                    if (representative && edits.Any(e => e.status == "not_applicable"))
                        limitations.Add("representative-editability-partial-not-applicable-kind");
                }
                else
                {
                    result.image = new ImageResult { status = "not_supported_scene_scope", error = "Static readback currently renders UI RectTransform roots only" };
                    result.visualCompleteness = "not_supported_scene_scope";
                    limitations.Add("sprite-renderer-or-non-UI-scene-preview-not-implemented");
                }

                bool incomplete = limitations.Any(v => v.StartsWith("disabled-unavailable:", StringComparison.Ordinal) ||
                    v == "static-render-deferred-no-graphics" ||
                    v == "sprite-renderer-or-non-UI-scene-preview-not-implemented" ||
                    v.StartsWith("representative-editability-", StringComparison.Ordinal));
                result.status = failures.Count > 0 ? "failed" : (incomplete ? "partial" : "passed");
            }
            catch (Exception error)
            {
                failures.Add(new Failure { phase = "root", message = error.ToString() });
                result.status = "failed";
                Debug.LogError("UNITY_PREFAB_STATIC_ROOT_FAILED " + plan.sourceId + ": " + error);
            }
            finally
            {
                if (contents != null)
                {
                    try { PrefabUtility.UnloadPrefabContents(contents); }
                    catch (Exception error) { failures.Add(new Failure { phase = "unload", message = error.Message }); result.status = "failed"; }
                }
            }
            result.failures = failures.ToArray();
            result.limitations = limitations.ToArray();
            if (result.failures.Length > 0) result.status = "failed";
            return result;
        }

        static MappedTree CheckTree(RootPlan plan, GameObject root, string phase, bool verifySourceEnabled,
                                    bool captureNativeIdentity, RootResult result, List<Failure> failures)
        {
            var mapped = new MappedTree();
            var byIndices = new Dictionary<string, NodePlan>(StringComparer.Ordinal);
            var usedSourceIds = new HashSet<string>(StringComparer.Ordinal);
            Dictionary<string, int> expectedChildCounts = ValidateChildIndexCoverage(plan.nodes);
            foreach (NodePlan node in plan.nodes)
            {
                if (String.IsNullOrEmpty(node.sourceId)) throw new InvalidOperationException("Node sourceId is empty");
                if (!usedSourceIds.Add(node.sourceId)) throw new InvalidOperationException("Duplicate sourceId across nodes/components: " + node.sourceId);
                string indexKey = IndexKey(node.indices);
                if (byIndices.ContainsKey(indexKey)) throw new InvalidOperationException("Duplicate node child-index path: " + indexKey);
                byIndices.Add(indexKey, node);
            }
            if (!byIndices.ContainsKey("")) throw new InvalidOperationException("Root node must use empty indices[]");

            foreach (NodePlan node in plan.nodes)
            {
                Transform transform = ResolveIndices(root.transform, node.indices);
                GameObject actual = transform.gameObject;
                if (!String.Equals(actual.name, node.name, StringComparison.Ordinal))
                    throw new InvalidOperationException("Node name differs at " + IndexKey(node.indices) + ": expected=" + node.name + ", actual=" + actual.name);
                if (actual.activeSelf != node.active) throw new InvalidOperationException("Node activeSelf differs: " + node.sourceId);
                if (actual.layer != node.layer) throw new InvalidOperationException("Node layer differs: " + node.sourceId);
                if (!String.IsNullOrEmpty(node.tag) && actual.tag != node.tag) throw new InvalidOperationException("Node tag differs: " + node.sourceId);
                int expectedChildCount = expectedChildCounts.ContainsKey(IndexKey(node.indices)) ? expectedChildCounts[IndexKey(node.indices)] : 0;
                if (actual.transform.childCount != expectedChildCount)
                    throw new InvalidOperationException("Transform child count differs: " + node.sourceId + ", expected=" + expectedChildCount + ", actual=" + actual.transform.childCount);
                mapped.nodes.Add(node.sourceId, actual);
                if (captureNativeIdentity) mapped.identities.Add(ReadIdentity(node.sourceId, "GameObject", actual));
                Component[] actualComponents = actual.GetComponents<Component>();
                int missing = actualComponents.Count(c => c == null);
                result.missingScripts += missing;
                if (missing != 0) throw new InvalidOperationException("MissingScript component in ordered component list: " + node.sourceId + ", count=" + missing);
                ComponentPlan[] expectedComponents = node.components ?? new ComponentPlan[0];
                if (actualComponents.Length != expectedComponents.Length)
                    throw new InvalidOperationException("Ordered component count differs: " + node.sourceId + ", expected=" + expectedComponents.Length + ", actual=" + actualComponents.Length);
                mapped.componentCount += expectedComponents.Length;
                mapped.fieldsExpected += expectedComponents.Sum(c => (c.fields ?? new FieldPlan[0]).Length);
                if (mapped.fieldsExpected > MaxFieldsPerRoot) throw new InvalidOperationException("Field count budget exceeded");
                for (int ci = 0; ci < expectedComponents.Length; ci++)
                {
                    ComponentPlan expected = expectedComponents[ci];
                    Component component = actualComponents[ci];
                    if (String.IsNullOrEmpty(expected.sourceId)) throw new InvalidOperationException("Component sourceId is empty on " + node.sourceId);
                    if (!usedSourceIds.Add(expected.sourceId)) throw new InvalidOperationException("Duplicate sourceId across nodes/components: " + expected.sourceId);
                    Type actualType = component.GetType();
                    if (!TypeMatches(expected.type, actualType))
                        throw new InvalidOperationException("Component type/order differs: " + node.sourceId + "[" + ci + "] expected=" + expected.type + ", actual=" + actualType.FullName);
                    if (!AssemblyMatches(expected.assembly, actualType.Assembly))
                        throw new InvalidOperationException("Component assembly differs: " + expected.sourceId + ", expected=" + expected.assembly + ", actual=" + actualType.Assembly.GetName().Name);
                    if (expected.disabledUnavailable && !(component is MonoBehaviour))
                        throw new InvalidOperationException("disabledUnavailable component is not a MonoBehaviour: " + expected.sourceId);
                    mapped.components.Add(expected.sourceId, component);
                    mapped.componentPlans.Add(expected.sourceId, expected);
                    if (captureNativeIdentity) mapped.identities.Add(ReadIdentity(expected.sourceId, "Component", component));
                }
            }

            var sourceIdMap = new Dictionary<string, UnityEngine.Object>(StringComparer.Ordinal);
            foreach (var pair in mapped.nodes) sourceIdMap.Add(pair.Key, pair.Value);
            foreach (var pair in mapped.components) sourceIdMap.Add(pair.Key, pair.Value);
            foreach (NodePlan node in plan.nodes)
            {
                foreach (ComponentPlan componentPlan in node.components ?? new ComponentPlan[0])
                {
                    Component component = mapped.components[componentPlan.sourceId];
                    var serialized = new SerializedObject(component);
                    foreach (FieldPlan field in componentPlan.fields ?? new FieldPlan[0])
                    {
                        FieldResult fieldResult = CheckField(componentPlan, component, serialized, field, sourceIdMap,
                            phase, verifySourceEnabled, captureNativeIdentity);
                        mapped.fields.Add(fieldResult);
                        if (captureNativeIdentity && phase == "source-asset")
                        {
                            result.fieldResults = mapped.fields.ToArray();
                            result.fieldsExpected = mapped.fieldsExpected;
                            result.fieldsCheckedBeforeSave = mapped.fieldsChecked;
                        }
                        if (!fieldResult.passed)
                        {
                            failures.Add(new Failure { phase = phase + "/field", message = fieldResult.error });
                            throw new InvalidOperationException(fieldResult.error);
                        }
                        mapped.fieldsChecked++;
                        if (captureNativeIdentity && fieldResult.reference != null) mapped.references.Add(fieldResult.reference);
                    }
                }
            }
            return mapped;
        }

        static FieldResult CheckField(ComponentPlan componentPlan, Component component, SerializedObject serialized,
                                      FieldPlan field, Dictionary<string, UnityEngine.Object> sourceIdMap,
                                      string phase, bool verifySourceEnabled, bool captureNativeIdentity)
        {
            var row = new FieldResult { sourceId = componentPlan.sourceId, path = field.path, kind = field.kind, passed = false };
            try
            {
                if (String.IsNullOrEmpty(field.path)) throw new InvalidOperationException("Expected field path is empty");
                SerializedProperty property = serialized.FindProperty(field.path);
                if (property == null) throw new InvalidOperationException("SerializedProperty is absent: " + field.path);
                row.propertyType = property.propertyType.ToString();
                if (field.kind == "byte" && property.propertyType == SerializedPropertyType.Boolean)
                {
                    if (field.intValue != 0 && field.intValue != 1) throw new InvalidOperationException("Source UInt8 cannot represent target Boolean");
                    row.expected = field.intValue.ToString(Invariant) + " (source UInt8 to target Boolean)";
                    row.actual = property.boolValue.ToString();
                    row.passed = property.boolValue == (field.intValue == 1);
                }
                else if (field.kind == "integer" || field.kind == "byte")
                {
                    if (property.propertyType != SerializedPropertyType.Integer &&
                        property.propertyType != SerializedPropertyType.Enum &&
                        property.propertyType != SerializedPropertyType.ArraySize)
                        throw new InvalidOperationException("Field SerializedProperty type is not Integer, Enum or ArraySize");
                    long actualInteger = property.propertyType == SerializedPropertyType.Integer ? property.longValue : property.intValue;
                    row.expected = field.intValue.ToString(Invariant);
                    row.actual = actualInteger.ToString(Invariant);
                    row.passed = actualInteger == field.intValue;
                }
                else if (field.kind == "float")
                {
                    if (property.propertyType != SerializedPropertyType.Float) throw new InvalidOperationException("Field SerializedProperty type is not Float");
                    double actual = property.doubleValue;
                    row.expected = field.floatValue.ToString("R", Invariant);
                    row.actual = actual.ToString("R", Invariant);
                    row.passed = !Double.IsNaN(actual) && !Double.IsInfinity(actual) && Math.Abs(actual - field.floatValue) <= 0.00001d;
                }
                else if (field.kind == "boolean")
                {
                    if (property.propertyType != SerializedPropertyType.Boolean) throw new InvalidOperationException("Field SerializedProperty type is not Boolean");
                    row.expected = field.boolValue.ToString();
                    row.actual = property.boolValue.ToString();
                    bool forcedDisabled = !verifySourceEnabled && componentPlan.disabledUnavailable && field.path == "m_Enabled";
                    row.passed = forcedDisabled ? !property.boolValue : property.boolValue == field.boolValue;
                    if (forcedDisabled) row.expected = "false (explicit disabledUnavailable; source=" + field.boolValue.ToString() + ")";
                }
                else if (field.kind == "string")
                {
                    if (property.propertyType != SerializedPropertyType.String) throw new InvalidOperationException("Field SerializedProperty type is not String");
                    row.expected = field.stringValue ?? String.Empty;
                    row.actual = property.stringValue ?? String.Empty;
                    row.passed = String.Equals(property.stringValue, field.stringValue, StringComparison.Ordinal);
                }
                else if (field.kind == "reference")
                {
                    if (property.propertyType != SerializedPropertyType.ObjectReference) throw new InvalidOperationException("Field SerializedProperty type is not ObjectReference");
                    UnityEngine.Object actual = property.objectReferenceValue;
                    bool expectNull = field.isNull || (String.IsNullOrEmpty(field.refSourceId) && String.IsNullOrEmpty(field.refGuid)
                        && String.IsNullOrEmpty(field.refType) && String.IsNullOrEmpty(field.refName) && String.IsNullOrEmpty(field.refLocalId));
                    if (expectNull && (!String.IsNullOrEmpty(field.refSourceId) || !String.IsNullOrEmpty(field.refGuid)
                        || !String.IsNullOrEmpty(field.refType) || !String.IsNullOrEmpty(field.refName) || !String.IsNullOrEmpty(field.refLocalId)))
                        throw new InvalidOperationException("Null reference expectation carries nonempty identity fields");
                    bool exactMappedReference = false;
                    if (!expectNull && actual != null && !String.IsNullOrEmpty(field.refSourceId) &&
                        !(field.path == "m_Script" && component is MonoBehaviour))
                    {
                        UnityEngine.Object expectedObject;
                        if (!sourceIdMap.TryGetValue(field.refSourceId, out expectedObject))
                            throw new InvalidOperationException("Reference sourceId has no exact node/component map: " + field.refSourceId);
                        if (actual != expectedObject) throw new InvalidOperationException("ObjectReference does not target mapped sourceId: " + field.refSourceId);
                        exactMappedReference = true;
                    }
                    AssetReferenceIdentity identity = DescribeReference(componentPlan.sourceId, field.path, field.refSourceId,
                        actual, component, field.path == "m_Script", !captureNativeIdentity && exactMappedReference);
                    row.reference = identity;
                    if (expectNull)
                    {
                        row.expected = "null";
                        row.actual = actual == null ? "null" : actual.GetType().FullName + ":" + actual.name;
                        row.passed = actual == null;
                    }
                    else if (actual == null)
                    {
                        throw new InvalidOperationException("Expected non-null ObjectReference resolved to null");
                    }
                    else
                    {
                        if (field.path == "m_Script" && component is MonoBehaviour &&
                            (String.IsNullOrEmpty(field.refGuid) || String.IsNullOrEmpty(field.refLocalId)))
                            throw new InvalidOperationException("m_Script requires exact expected MonoScript GUID and local file ID");
                        if (!String.IsNullOrEmpty(field.refSourceId))
                        {
                            if (field.path == "m_Script" && component is MonoBehaviour)
                            {
                                if (String.IsNullOrEmpty(field.refGuid))
                                    throw new InvalidOperationException("m_Script source identity needs exact target refGuid; do not match by class name");
                                MonoScript script = MonoScript.FromMonoBehaviour((MonoBehaviour)component);
                                if (script == null || actual != script) throw new InvalidOperationException("m_Script reference differs from MonoScript.FromMonoBehaviour");
                            }
                            else
                            {
                                UnityEngine.Object expectedObject;
                                if (!sourceIdMap.TryGetValue(field.refSourceId, out expectedObject))
                                    throw new InvalidOperationException("Reference sourceId has no exact node/component map: " + field.refSourceId);
                                if (actual != expectedObject) throw new InvalidOperationException("ObjectReference does not target mapped sourceId: " + field.refSourceId);
                            }
                        }
                        VerifyReferenceExpectations(field, actual, identity, component, field.path == "m_Script",
                            !captureNativeIdentity && exactMappedReference);
                        row.expected = ReferenceExpectation(field);
                        row.actual = identity.guid + "/" + identity.localFileId + ":" + identity.type + ":" + identity.name;
                        row.passed = true;
                    }
                }
                else
                {
                    throw new InvalidOperationException("Unsupported expected field kind: " + field.kind);
                }
                if (!row.passed && String.IsNullOrEmpty(row.error))
                    row.error = "Serialized value differs; phase=" + phase + ";sourceId=" + componentPlan.sourceId + ";field=" + field.path;
            }
            catch (Exception error)
            {
                row.error = componentPlan.sourceId + "." + field.path + ": " + error.Message;
            }
            return row;
        }

        static AssetReferenceIdentity DescribeReference(string ownerId, string path, string sourceId,
                                                        UnityEngine.Object actual, Component owner, bool monoScriptField,
                                                        bool allowTransientMappedReference)
        {
            var row = new AssetReferenceIdentity { ownerSourceId = ownerId, fieldPath = path,
                sourceReferenceId = sourceId, isNull = actual == null };
            if (actual == null) return row;
            string guid; long localId;
            if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(actual, out guid, out localId))
            {
                if (!allowTransientMappedReference)
                    throw new InvalidOperationException("Reference has no native GUID/local file ID: " + actual.name);
            }
            else
            {
                row.guid = guid;
                row.localFileId = localId.ToString(Invariant);
            }
            row.assetPath = AssetDatabase.GetAssetPath(actual);
            row.type = actual.GetType().FullName;
            row.assembly = actual.GetType().Assembly.GetName().Name;
            row.name = actual.name;
            if (monoScriptField && owner is MonoBehaviour)
            {
                MonoScript script = MonoScript.FromMonoBehaviour((MonoBehaviour)owner);
                if (script == null) throw new InvalidOperationException("MonoScript.FromMonoBehaviour returned null");
                string scriptGuid; long scriptId;
                if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(script, out scriptGuid, out scriptId))
                    throw new InvalidOperationException("MonoScript has no native GUID/local file ID");
                row.monoScriptGuid = scriptGuid;
                row.monoScriptLocalFileId = scriptId.ToString(Invariant);
            }
            return row;
        }

        static void VerifyReferenceExpectations(FieldPlan expected, UnityEngine.Object actual,
                                                AssetReferenceIdentity identity, Component owner, bool monoScriptField,
                                                bool allowTransientMappedReference)
        {
            if (!allowTransientMappedReference && !String.IsNullOrEmpty(expected.refGuid) && !String.Equals(expected.refGuid, identity.guid, StringComparison.Ordinal))
                throw new InvalidOperationException("ObjectReference GUID differs: expected=" + expected.refGuid + ", actual=" + identity.guid);
            if (!allowTransientMappedReference && !String.IsNullOrEmpty(expected.refLocalId) && !String.Equals(expected.refLocalId, identity.localFileId, StringComparison.Ordinal))
                throw new InvalidOperationException("ObjectReference local file ID differs: expected=" + expected.refLocalId + ", actual=" + identity.localFileId);
            if (!String.IsNullOrEmpty(expected.refName) && !String.Equals(expected.refName, actual.name, StringComparison.Ordinal))
                throw new InvalidOperationException("ObjectReference name differs: expected=" + expected.refName + ", actual=" + actual.name);
            if (!String.IsNullOrEmpty(expected.refType) && !TypeMatches(expected.refType, actual.GetType()))
                throw new InvalidOperationException("ObjectReference type differs: expected=" + expected.refType + ", actual=" + actual.GetType().FullName);
            if (monoScriptField && owner is MonoBehaviour)
            {
                MonoScript script = MonoScript.FromMonoBehaviour((MonoBehaviour)owner);
                Type scriptType = script == null ? null : script.GetClass();
                if (script == null || scriptType != owner.GetType())
                    throw new InvalidOperationException("m_Script class does not exactly match the component runtime type");
                if (actual != script)
                    throw new InvalidOperationException("m_Script ObjectReference differs from MonoScript.FromMonoBehaviour");
                if (!AssemblyMatches(((MonoBehaviour)owner).GetType().Assembly.GetName().Name, scriptType.Assembly))
                    throw new InvalidOperationException("m_Script assembly differs from the component runtime type");
                string scriptGuid; long scriptId;
                if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(script, out scriptGuid, out scriptId))
                    throw new InvalidOperationException("m_Script native identity unavailable");
                if (!String.IsNullOrEmpty(expected.refGuid) && expected.refGuid != scriptGuid)
                    throw new InvalidOperationException("m_Script GUID differs from exact plan identity");
                if (!String.IsNullOrEmpty(expected.refLocalId) && expected.refLocalId != scriptId.ToString(Invariant))
                    throw new InvalidOperationException("m_Script local file ID differs from exact plan identity");
            }
        }

        static string ReferenceExpectation(FieldPlan field)
        {
            if (!String.IsNullOrEmpty(field.refSourceId)) return "sourceId=" + field.refSourceId;
            if (!String.IsNullOrEmpty(field.refGuid)) return "guid=" + field.refGuid + ";localId=" + field.refLocalId;
            return "type=" + field.refType + ";name=" + field.refName;
        }

        static ImageResult RenderPrefab(string projectRoot, GameObject prefab, string prefabGuid, RootPlan plan,
                                        out EditResult[] editability, bool representative)
        {
            var edits = new List<EditResult>();
            editability = new EditResult[0];
            ImageResult imageResult = null;
            Scene previousScene = SceneManager.GetActiveScene();
            Scene scene = default(Scene);
            RenderTexture target = null;
            GameObject canvasObject = null;
            GameObject cameraObject = null;
            GameObject instance = null;
            RenderTexture previousActive = RenderTexture.active;
            try
            {
                scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Additive);
                if (!scene.IsValid()) throw new InvalidOperationException("Could not create temporary render scene");
                canvasObject = new GameObject("Monkey Static Readback Canvas", typeof(RectTransform), typeof(Canvas), typeof(CanvasScaler));
                SceneManager.MoveGameObjectToScene(canvasObject, scene);
                Canvas canvas = canvasObject.GetComponent<Canvas>();
                canvas.renderMode = RenderMode.WorldSpace;
                CanvasScaler scaler = canvasObject.GetComponent<CanvasScaler>();
                scaler.uiScaleMode = CanvasScaler.ScaleMode.ConstantPixelSize;
                scaler.scaleFactor = 1f;
                scaler.referencePixelsPerUnit = 100f;
                scaler.dynamicPixelsPerUnit = 100f;
                canvasObject.transform.localScale = Vector3.one * 0.01f;
                RectTransform canvasRect = canvasObject.GetComponent<RectTransform>();
                instance = PrefabUtility.InstantiatePrefab(prefab, scene) as GameObject;
                if (instance == null) throw new InvalidOperationException("Could not instantiate saved Prefab into temporary Scene");
                Bounds sourceBounds = UiBounds(instance);
                RectTransform sourceRootRect = instance.transform as RectTransform;
                Vector2 sourceSize = sourceRootRect == null ? Vector2.zero : sourceRootRect.rect.size;
                float canvasWidth = Mathf.Max(100f, Mathf.Max(sourceSize.x, sourceBounds.size.x * 1.25f));
                float canvasHeight = Mathf.Max(100f, Mathf.Max(sourceSize.y, sourceBounds.size.y * 1.25f));
                canvasRect.sizeDelta = new Vector2(canvasWidth, canvasHeight);
                instance.transform.SetParent(canvasRect, false);
                canvas.worldCamera = null;

                Bounds bounds = UiBounds(instance);
                int activeRects = instance.GetComponentsInChildren<RectTransform>(true).Count(r => r != null && r.gameObject.activeInHierarchy);
                Graphic[] graphics = instance.GetComponentsInChildren<Graphic>(true).Where(g => g != null && g.gameObject.activeInHierarchy).ToArray();
                int activeTexts = graphics.Count(g => IsSafeTextProperty(g.GetType().GetProperty("text", BindingFlags.Public | BindingFlags.Instance)));
                cameraObject = new GameObject("Monkey Static Readback Camera", typeof(Camera));
                SceneManager.MoveGameObjectToScene(cameraObject, scene);
                Camera camera = cameraObject.GetComponent<Camera>();
                camera.enabled = false;
                camera.orthographic = true;
                camera.aspect = 1f;
                camera.cullingMask = ~0;
                camera.clearFlags = CameraClearFlags.SolidColor;
                camera.backgroundColor = new Color(0.113f, 0.137f, 0.173f, 1f);
                camera.nearClipPlane = 0.01f;
                camera.farClipPlane = 10000f;
                float extent = Mathf.Max(bounds.extents.y, bounds.extents.x) * 1.12f;
                if (!Finite(extent) || extent < 0.001f) throw new InvalidOperationException("UI bounds are too small or invalid");
                camera.orthographicSize = extent;
                camera.transform.position = new Vector3(bounds.center.x, bounds.center.y, bounds.center.z - Mathf.Max(5f, extent * 4f));
                camera.transform.rotation = Quaternion.identity;
                canvas.worldCamera = camera;
                Canvas.ForceUpdateCanvases();
                target = new RenderTexture(CaptureSize, CaptureSize, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
                target.Create();
                camera.targetTexture = target;
                string imageDirectory = Path.Combine(projectRoot, "Analysis", "Readback", "Prefabs");
                EnsureReadbackDirectory(projectRoot, imageDirectory);
                string imagePath = Path.Combine(imageDirectory, SafeGuid(prefabGuid) + "-static.png");
                CaptureFrame baseline = Capture(camera, target, imagePath);
                imageResult = baseline.result;
                imageResult.framing = "worldspace-canvas-derived-from-source-rect-and-content-bounds;orthographic-bounds";
                imageResult.activeRectCount = activeRects;
                imageResult.activeGraphicCount = graphics.Length;
                imageResult.activeTextCount = activeTexts;
                imageResult.boundsWidth = bounds.size.x;
                imageResult.boundsHeight = bounds.size.y;
                imageResult.canvasWidthPixels = canvasWidth;
                imageResult.canvasHeightPixels = canvasHeight;
                imageResult.referencePixelsPerUnit = scaler.referencePixelsPerUnit;
                if (activeRects == 0 || !Finite(bounds.size.x) || !Finite(bounds.size.y) || bounds.size.x <= 0f || bounds.size.y <= 0f)
                {
                    imageResult.status = "failed";
                    imageResult.error = "Active Rect/text bounds are empty or invalid";
                }

                if (representative)
                {
                    RunRepresentativeEdits(instance, plan, camera, target, imageDirectory, prefabGuid, baseline, edits);
                }
                editability = edits.ToArray();
            }
            finally
            {
                RenderTexture.active = previousActive;
                if (cameraObject != null) UnityEngine.Object.DestroyImmediate(cameraObject);
                if (canvasObject != null) UnityEngine.Object.DestroyImmediate(canvasObject);
                if (instance != null) UnityEngine.Object.DestroyImmediate(instance);
                if (target != null)
                {
                    target.Release();
                    UnityEngine.Object.DestroyImmediate(target);
                }
                if (scene.IsValid()) EditorSceneManager.CloseScene(scene, true);
                if (previousScene.IsValid() && previousScene.isLoaded) SceneManager.SetActiveScene(previousScene);
                Canvas.ForceUpdateCanvases();
            }
            return imageResult;
        }

        static void RunRepresentativeEdits(GameObject instance, RootPlan plan, Camera camera, RenderTexture target,
                                           string imageDirectory, string prefabGuid, CaptureFrame baseline,
                                           List<EditResult> results)
        {
            TextTarget text = FindVisibleText(instance);
            if (text == null)
                results.Add(new EditResult { kind = "text", status = "not_applicable", reason = "No native UI Graphic string text property exists" });
            else
            {
                string before = text.property.GetValue(text.component, null) as string ?? String.Empty;
                string after = before + "x";
                if (String.Equals(before, after, StringComparison.Ordinal)) throw new InvalidOperationException("Text representative mutation did not change the value");
                text.property.SetValue(text.component, after, null);
                Canvas.ForceUpdateCanvases();
                EditResult edit = CaptureEdit(camera, target, imageDirectory, prefabGuid, "text", before, after, baseline);
                edit.targetSourceId = SourceIdFor(instance, plan, text.component);
                text.property.SetValue(text.component, before, null);
                Canvas.ForceUpdateCanvases();
                results.Add(edit);
            }

            Graphic image = FindNativeImage(instance);
            if (image == null)
                results.Add(new EditResult { kind = "image-tint", status = "not_applicable", reason = "No native UI Image component exists" });
            else
            {
                Color before = image.color;
                Color after = new Color(0.97f, 0.17f, 0.83f, before.a);
                if (before == after) after = new Color(0.11f, 0.91f, 0.23f, before.a);
                image.color = after;
                Canvas.ForceUpdateCanvases();
                EditResult edit = CaptureEdit(camera, target, imageDirectory, prefabGuid, "image-tint", before.ToString(), after.ToString(), baseline);
                edit.targetSourceId = SourceIdFor(instance, plan, image);
                image.color = before;
                Canvas.ForceUpdateCanvases();
                results.Add(edit);
            }

            RectTransform rect = instance.GetComponentsInChildren<RectTransform>(true).FirstOrDefault(r => r != null && r.gameObject.activeInHierarchy);
            if (rect == null)
                results.Add(new EditResult { kind = "transform", status = "not_applicable", reason = "No active RectTransform exists" });
            else
            {
                Vector2 before = rect.anchoredPosition;
                Vector2 after = before + new Vector2(10f, 0f);
                if (before == after) throw new InvalidOperationException("Transform representative mutation did not change the value");
                rect.anchoredPosition = after;
                Canvas.ForceUpdateCanvases();
                EditResult edit = CaptureEdit(camera, target, imageDirectory, prefabGuid, "transform", before.ToString(), after.ToString(), baseline);
                edit.targetSourceId = SourceIdFor(instance, plan, null, rect.gameObject);
                rect.anchoredPosition = before;
                Canvas.ForceUpdateCanvases();
                results.Add(edit);
            }
        }

        sealed class TextTarget
        {
            public Component component;
            public PropertyInfo property;
        }

        static TextTarget FindVisibleText(GameObject root)
        {
            foreach (Graphic graphic in root.GetComponentsInChildren<Graphic>(true))
            {
                if (graphic == null || !graphic.gameObject.activeInHierarchy) continue;
                PropertyInfo property = graphic.GetType().GetProperty("text", BindingFlags.Public | BindingFlags.Instance);
                if (IsSafeTextProperty(property))
                    return new TextTarget { component = graphic, property = property };
            }
            return null;
        }

        static bool IsSafeTextProperty(PropertyInfo property)
        {
            return property != null && property.PropertyType == typeof(string) && property.CanRead && property.CanWrite &&
                property.GetGetMethod(true) != null && property.GetSetMethod(true) != null &&
                IsUnityOwnedAssembly(property.GetGetMethod(true).DeclaringType.Assembly.GetName().Name) &&
                IsUnityOwnedAssembly(property.GetSetMethod(true).DeclaringType.Assembly.GetName().Name);
        }

        static Graphic FindNativeImage(GameObject root)
        {
            foreach (Graphic graphic in root.GetComponentsInChildren<Graphic>(true))
            {
                if (graphic == null || !graphic.gameObject.activeInHierarchy) continue;
                PropertyInfo sprite = graphic.GetType().GetProperty("sprite", BindingFlags.Public | BindingFlags.Instance);
                if (sprite != null && sprite.PropertyType == typeof(Sprite) && sprite.CanRead &&
                    sprite.GetGetMethod(true) != null && IsUnityOwnedAssembly(sprite.GetGetMethod(true).DeclaringType.Assembly.GetName().Name))
                    return graphic;
            }
            return null;
        }

        static string SourceIdFor(GameObject instance, RootPlan plan, Component component, GameObject node = null)
        {
            foreach (NodePlan expectedNode in plan.nodes)
            {
                GameObject actualNode = ResolveIndices(instance.transform, expectedNode.indices).gameObject;
                if (component == null)
                {
                    if (actualNode == (node ?? instance)) return expectedNode.sourceId;
                    continue;
                }
                if (actualNode != component.gameObject) continue;
                Component[] actualComponents = actualNode.GetComponents<Component>();
                ComponentPlan[] expectedComponents = expectedNode.components ?? new ComponentPlan[0];
                int count = Math.Min(actualComponents.Length, expectedComponents.Length);
                for (int i = 0; i < count; i++)
                    if (actualComponents[i] == component) return expectedComponents[i].sourceId;
            }
            throw new InvalidOperationException("Temporary preview edit target has no exact plan sourceId");
        }

        static EditResult CaptureEdit(Camera camera, RenderTexture target, string directory, string prefabGuid,
                                      string kind, string before, string after, CaptureFrame baseline)
        {
            var row = new EditResult { kind = kind, status = "failed", beforeValue = before, afterValue = after, valueChanged = before != after };
            string safe = SafeGuid(prefabGuid) + "-edit-" + SafeId(kind);
            row.beforeImagePath = RelativeReadbackImage("Analysis/Readback/Prefabs/" + safe + "-before.png");
            row.afterImagePath = RelativeReadbackImage("Analysis/Readback/Prefabs/" + safe + "-after.png");
            string beforePath = Path.Combine(directory, safe + "-before.png");
            string afterPath = Path.Combine(directory, safe + "-after.png");
            if (File.Exists(beforePath) || File.Exists(afterPath))
                throw new InvalidOperationException("Representative edit image already exists; refusing overwrite: " + safe);
            if (baseline == null || baseline.pngBytes == null || baseline.pixels == null)
                throw new InvalidOperationException("Baseline pixels are unavailable for editability check");
            Directory.CreateDirectory(Path.GetDirectoryName(beforePath));
            File.WriteAllBytes(beforePath, baseline.pngBytes);
            CaptureFrame afterFrame = Capture(camera, target, afterPath);
            row.beforeImageSha256 = baseline.result.sha256;
            row.afterImageSha256 = afterFrame.result.sha256;
            row.changedPixels = CountChangedPixels(baseline.pixels, afterFrame.pixels);
            row.status = row.valueChanged && row.changedPixels > 0 ? "passed" : "failed";
            if (!row.valueChanged) row.reason = "Native value did not change";
            else if (row.changedPixels == 0) row.reason = "Rendered pixels did not change after native edit";
            return row;
        }

        static CaptureFrame Capture(Camera camera, RenderTexture target, string path)
        {
            var previousActive = RenderTexture.active;
            Texture2D image = null;
            try
            {
                Canvas.ForceUpdateCanvases();
                camera.Render();
                RenderTexture.active = target;
                image = new Texture2D(CaptureSize, CaptureSize, TextureFormat.RGBA32, false, false);
                image.ReadPixels(new Rect(0, 0, CaptureSize, CaptureSize), 0, 0, false);
                image.Apply(false, false);
                Color32[] pixels = image.GetPixels32();
                Color32 background = (Color32)camera.backgroundColor;
                int nonBackground = pixels.Count(p => ColorDistance(p, background) > 4);
                byte[] png = image.EncodeToPNG();
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                if (File.Exists(path)) throw new InvalidOperationException("Static image already exists; refusing overwrite: " + path);
                File.WriteAllBytes(path, png);
                string digest = Sha256(png);
                return new CaptureFrame {
                    result = new ImageResult { status = nonBackground > 0 ? "passed" : "failed",
                        path = RelativeReadbackImage(path), sha256 = digest, width = CaptureSize,
                        height = CaptureSize, nonBackgroundPixels = nonBackground,
                        error = nonBackground > 0 ? String.Empty : "Rendered image contains only the configured background" },
                    pixels = pixels,
                    pngBytes = png
                };
            }
            finally
            {
                RenderTexture.active = previousActive;
                if (image != null) UnityEngine.Object.DestroyImmediate(image);
            }
        }

        static int CountChangedPixels(Color32[] before, Color32[] after)
        {
            if (before == null || after == null || before.Length != after.Length) return 0;
            int count = 0;
            for (int i = 0; i < before.Length; i++)
                if (ColorDistance(before[i], after[i]) > 4) count++;
            return count;
        }

        static int ColorDistance(Color32 a, Color32 b)
        {
            return Math.Max(Math.Max(Math.Abs(a.r - b.r), Math.Abs(a.g - b.g)),
                Math.Max(Math.Abs(a.b - b.b), Math.Abs(a.a - b.a)));
        }

        static Bounds UiBounds(GameObject root)
        {
            bool hasBounds = false;
            Bounds bounds = new Bounds();
            foreach (RectTransform rect in root.GetComponentsInChildren<RectTransform>(true))
            {
                if (rect == null || !rect.gameObject.activeInHierarchy) continue;
                Vector3[] corners = new Vector3[4];
                rect.GetWorldCorners(corners);
                for (int i = 0; i < corners.Length; i++)
                {
                    if (!Finite(corners[i].x) || !Finite(corners[i].y) || !Finite(corners[i].z)) continue;
                    if (!hasBounds) { bounds = new Bounds(corners[i], Vector3.zero); hasBounds = true; }
                    else bounds.Encapsulate(corners[i]);
                }
            }
            if (!hasBounds) throw new InvalidOperationException("No active RectTransform bounds for UI framing");
            return bounds;
        }

        static void EnsureNoGameLifecycleCallbacks(GameObject root, string rootSourceId)
        {
            foreach (MonoBehaviour behaviour in root.GetComponentsInChildren<MonoBehaviour>(true))
                if (behaviour != null) EnsureTypeSafe(behaviour.GetType(), rootSourceId);
        }

        static void PreflightPlanCallbacks(RootPlan plan)
        {
            var assemblyCache = new Dictionary<string, Assembly>(StringComparer.Ordinal);
            var typeCache = new Dictionary<Assembly, Type[]>();
            foreach (NodePlan node in plan.nodes)
            foreach (ComponentPlan component in node.components ?? new ComponentPlan[0])
            {
                if (IsUnityOwnedAssembly(component.assembly)) continue;
                Assembly assembly;
                if (!assemblyCache.TryGetValue(component.assembly ?? String.Empty, out assembly))
                {
                    Assembly[] assemblies = AppDomain.CurrentDomain.GetAssemblies()
                        .Where(a => AssemblyMatches(component.assembly, a)).ToArray();
                    if (assemblies.Length != 1)
                        throw new InvalidOperationException("Pre-load safety check could not identify one target assembly for " + component.sourceId + ": " + component.assembly);
                    assembly = assemblies[0];
                    assemblyCache[component.assembly ?? String.Empty] = assembly;
                }
                Type[] available;
                if (!typeCache.TryGetValue(assembly, out available))
                    typeCache[assembly] = available = SafeTypes(assembly).ToArray();
                Type[] matches = available.Where(t => TypeMatches(component.type, t)).ToArray();
                if (matches.Length != 1)
                    throw new InvalidOperationException("Pre-load safety check could not identify one compiled target type for " + component.sourceId + ": " + component.assembly + "/" + component.type);
                if (typeof(MonoBehaviour).IsAssignableFrom(matches[0])) EnsureTypeSafe(matches[0], component.sourceId);
            }
        }

        static IEnumerable<Type> SafeTypes(Assembly assembly)
        {
            try { return assembly.GetTypes(); }
            catch (ReflectionTypeLoadException error) { return error.Types.Where(t => t != null); }
            catch { return new Type[0]; }
        }

        static void EnsureTypeSafe(Type type, string rootSourceId)
        {
            string[] callbacks = { "Awake", "OnEnable", "Start", "Update", "FixedUpdate", "LateUpdate",
                "OnDisable", "OnDestroy", "OnValidate", "OnTransformChildrenChanged", "OnRectTransformDimensionsChange",
                "OnTransformParentChanged", "OnBeforeTransformParentChanged",
                "OnCanvasHierarchyChanged", "OnCanvasGroupChanged", "OnDidApplyAnimationProperties", "OnBeforeSerialize", "OnAfterDeserialize",
                "OnWillRenderObject", "OnBecameVisible", "OnBecameInvisible", "OnPreCull", "OnPreRender",
                "OnRenderObject", "OnPostRender", "OnRenderImage", "OnGUI" };
            for (Type current = type; current != null && current != typeof(MonoBehaviour) && current != typeof(Behaviour) && current != typeof(Component); current = current.BaseType)
            {
                if (IsUnityOwnedAssembly(current.Assembly.GetName().Name)) break;
                var inheritedInterfaces = current.BaseType == null ? new HashSet<Type>() : new HashSet<Type>(current.BaseType.GetInterfaces());
                if (current.GetInterfaces().Any(i => !inheritedInterfaces.Contains(i) && i.FullName == "UnityEngine.ISerializationCallbackReceiver"))
                    throw new InvalidOperationException("Preview blocked: custom type implements serialization callbacks: " + current.FullName + "; root=" + rootSourceId);
                if (current.TypeInitializer != null)
                    throw new InvalidOperationException("Preview blocked: custom type has a static initializer that could execute: " + current.FullName + "; root=" + rootSourceId);
                MethodInfo[] methods = current.GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                MethodInfo callback = methods.FirstOrDefault(m => callbacks.Contains(m.Name, StringComparer.Ordinal));
                if (callback != null)
                    throw new InvalidOperationException("Preview blocked to avoid executing game/custom lifecycle callback " + current.FullName + "." + callback.Name + "; root=" + rootSourceId);
                foreach (CustomAttributeData attribute in CustomAttributeData.GetCustomAttributes(current))
                {
                    string attributeName = attribute.AttributeType.FullName ?? String.Empty;
                    if (attributeName == "UnityEngine.ExecuteAlways" || attributeName == "UnityEngine.ExecuteInEditMode")
                        throw new InvalidOperationException("Preview blocked for edit-mode-executing custom type " + current.FullName + "; root=" + rootSourceId);
                }
            }
        }

        static bool SameNativeIdentities(List<NativeIdentity> before, List<NativeIdentity> after)
        {
            var a = before.OrderBy(x => x.sourceId, StringComparer.Ordinal).ThenBy(x => x.kind, StringComparer.Ordinal).ToArray();
            var b = after.OrderBy(x => x.sourceId, StringComparer.Ordinal).ThenBy(x => x.kind, StringComparer.Ordinal).ToArray();
            if (a.Length != b.Length) return false;
            for (int i = 0; i < a.Length; i++)
                if (a[i].sourceId != b[i].sourceId || a[i].kind != b[i].kind || a[i].guid != b[i].guid ||
                    a[i].localFileId != b[i].localFileId || a[i].type != b[i].type || a[i].assembly != b[i].assembly)
                    return false;
            return true;
        }

        static void CompareReferenceTables(List<AssetReferenceIdentity> before, List<AssetReferenceIdentity> after)
        {
            AssetReferenceIdentity[] a = before.OrderBy(r => r.ownerSourceId, StringComparer.Ordinal)
                .ThenBy(r => r.fieldPath, StringComparer.Ordinal).ToArray();
            AssetReferenceIdentity[] b = after.OrderBy(r => r.ownerSourceId, StringComparer.Ordinal)
                .ThenBy(r => r.fieldPath, StringComparer.Ordinal).ToArray();
            if (a.Length != b.Length) throw new InvalidOperationException("ObjectReference field count changed after save/reopen");
            for (int i = 0; i < a.Length; i++)
            {
                if (a[i].ownerSourceId != b[i].ownerSourceId || a[i].fieldPath != b[i].fieldPath ||
                    a[i].sourceReferenceId != b[i].sourceReferenceId || a[i].isNull != b[i].isNull ||
                    a[i].guid != b[i].guid || a[i].localFileId != b[i].localFileId || a[i].assetPath != b[i].assetPath ||
                    a[i].type != b[i].type || a[i].assembly != b[i].assembly || a[i].name != b[i].name ||
                    a[i].monoScriptGuid != b[i].monoScriptGuid || a[i].monoScriptLocalFileId != b[i].monoScriptLocalFileId)
                    throw new InvalidOperationException("ObjectReference GUID/localID/type table changed after save/reopen at " + a[i].ownerSourceId + "." + a[i].fieldPath);
            }
        }

        static NativeIdentity ReadIdentity(string sourceId, string kind, UnityEngine.Object value)
        {
            string guid; long localId;
            if (value == null || !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value, out guid, out localId))
                throw new InvalidOperationException("Persistent native identity is unavailable: " + sourceId + "/" + kind);
            return new NativeIdentity { sourceId = sourceId, kind = kind, guid = guid,
                localFileId = localId.ToString(Invariant), type = value.GetType().FullName,
                assembly = value.GetType().Assembly.GetName().Name, name = value.name,
                assetPath = AssetDatabase.GetAssetPath(value) };
        }

        static Transform ResolveIndices(Transform root, int[] indices)
        {
            if (indices == null) throw new InvalidOperationException("Node indices is null");
            Transform cursor = root;
            for (int i = 0; i < indices.Length; i++)
            {
                int index = indices[i];
                if (index < 0 || index >= cursor.childCount)
                    throw new InvalidOperationException("Transform child index is outside actual hierarchy: " + IndexKey(indices));
                cursor = cursor.GetChild(index);
            }
            return cursor;
        }

        static Dictionary<string, int> ValidateChildIndexCoverage(NodePlan[] nodes)
        {
            var byParent = new Dictionary<string, List<int>>(StringComparer.Ordinal);
            foreach (NodePlan node in nodes)
            {
                int[] path = node.indices ?? new int[0];
                if (path.Length == 0) continue;
                if (path.Any(i => i < 0)) throw new InvalidOperationException("Negative child index in plan");
                string parent = IndexKey(path.Take(path.Length - 1).ToArray());
                List<int> children;
                if (!byParent.TryGetValue(parent, out children)) byParent[parent] = children = new List<int>();
                children.Add(path[path.Length - 1]);
            }
            var declaredPaths = new HashSet<string>(nodes.Select(n => IndexKey(n.indices)), StringComparer.Ordinal);
            foreach (NodePlan node in nodes)
            {
                int[] path = node.indices ?? new int[0];
                if (path.Length == 0) continue;
                string parent = IndexKey(path.Take(path.Length - 1).ToArray());
                if (!declaredPaths.Contains(parent)) throw new InvalidOperationException("Plan node has no declared parent node: " + IndexKey(path));
            }
            foreach (var pair in byParent)
            {
                int[] indices = pair.Value.OrderBy(i => i).ToArray();
                for (int i = 0; i < indices.Length; i++)
                    if (indices[i] != i) throw new InvalidOperationException("Plan child indices are not a complete ordered range below " + pair.Key);
            }
            return byParent.ToDictionary(pair => pair.Key, pair => pair.Value.Count, StringComparer.Ordinal);
        }

        static bool IsUiPlan(RootPlan root)
        {
            return root != null && root.nodes != null && root.nodes.Any(n => n != null &&
                (n.components ?? new ComponentPlan[0]).Any(c => c != null &&
                    (c.type == "RectTransform" || c.type == "UnityEngine.RectTransform" ||
                     c.type.StartsWith("UnityEngine.UI.", StringComparison.Ordinal) || c.type.StartsWith("TMPro.", StringComparison.Ordinal))));
        }

        static bool TypeMatches(string expected, Type actual)
        {
            return !String.IsNullOrEmpty(expected) &&
                (String.Equals(expected, actual.Name, StringComparison.Ordinal) || String.Equals(expected, actual.FullName, StringComparison.Ordinal));
        }

        static bool AssemblyMatches(string expected, Assembly actual)
        {
            if (String.IsNullOrEmpty(expected) || actual == null) return false;
            string name = actual.GetName().Name;
            return String.Equals(expected, name, StringComparison.Ordinal) ||
                   String.Equals(expected, name + ".dll", StringComparison.Ordinal) ||
                   String.Equals(expected, actual.FullName, StringComparison.Ordinal);
        }

        static bool IsUnityOwnedAssembly(string name)
        {
            return name != null && (name.StartsWith("UnityEngine", StringComparison.Ordinal) ||
                name.StartsWith("Unity.", StringComparison.Ordinal) || name.StartsWith("UnityEditor", StringComparison.Ordinal));
        }

        static string IndexKey(int[] indices)
        {
            if (indices == null || indices.Length == 0) return String.Empty;
            return String.Join("/", indices.Select(i => i.ToString(Invariant)).ToArray());
        }

        static void ValidatePlan(Plan plan)
        {
            if (plan == null || plan.schemaVersion != 1) throw new InvalidOperationException("Plan schemaVersion 1 required");
            if (plan.targetUnityVersion != "6000.6.2f1") throw new InvalidOperationException("Plan targetUnityVersion must be 6000.6.2f1");
            if (plan.roots == null || plan.roots.Length == 0 || plan.roots.Length > MaxRoots)
                throw new InvalidOperationException("Plan roots count is empty or exceeds the bounded limit");
            if (!IsReadbackRelative(plan.outputRelative)) throw new InvalidOperationException("outputRelative must be a safe Analysis/Readback child path");
            var rootIds = new HashSet<string>(StringComparer.Ordinal);
            var rootPaths = new HashSet<string>(StringComparer.Ordinal);
            int totalNodes = 0;
            int totalComponents = 0;
            long totalFields = 0;
            int representatives = 0;
            foreach (RootPlan root in plan.roots)
            {
                if (root == null || String.IsNullOrEmpty(root.sourceId) || String.IsNullOrEmpty(root.path))
                    throw new InvalidOperationException("Every root requires path and sourceId");
                if (!rootIds.Add(root.sourceId)) throw new InvalidOperationException("Duplicate root sourceId: " + root.sourceId);
                if (!rootPaths.Add(root.path)) throw new InvalidOperationException("A candidate Prefab path can appear only once per batch: " + root.path);
                if (root.isRepresentative && ++representatives > MaxRepresentativeRoots)
                    throw new InvalidOperationException("Representative editability root count exceeds bounded limit");
                if (root.nodes == null || root.nodes.Length == 0 || root.nodes.Length > MaxNodesPerRoot)
                    throw new InvalidOperationException("Root nodes are empty or exceed bounded limit: " + root.sourceId);
                totalNodes += root.nodes.Length;
                foreach (NodePlan node in root.nodes)
                {
                    if (node == null || String.IsNullOrEmpty(node.sourceId) || String.IsNullOrEmpty(node.name) || node.indices == null || node.components == null)
                        throw new InvalidOperationException("Every node needs sourceId, indices, name and ordered components: " + root.sourceId);
                    foreach (ComponentPlan component in node.components)
                    {
                        totalComponents++;
                        if (component == null || String.IsNullOrEmpty(component.sourceId) || String.IsNullOrEmpty(component.type) ||
                            String.IsNullOrEmpty(component.assembly) || component.fields == null)
                            throw new InvalidOperationException("Every component needs sourceId, type, assembly and fields: " + node.sourceId);
                        foreach (FieldPlan field in component.fields)
                        {
                            totalFields++;
                            if (field == null || String.IsNullOrEmpty(field.path) ||
                                !(field.kind == "integer" || field.kind == "byte" || field.kind == "float" || field.kind == "boolean" || field.kind == "string" || field.kind == "reference"))
                                throw new InvalidOperationException("Malformed/unsupported serialized field in component " + component.sourceId);
                            if (field.kind == "reference" && field.isNull &&
                                (!String.IsNullOrEmpty(field.refSourceId) || !String.IsNullOrEmpty(field.refGuid) ||
                                 !String.IsNullOrEmpty(field.refLocalId) || !String.IsNullOrEmpty(field.refType) || !String.IsNullOrEmpty(field.refName)))
                                throw new InvalidOperationException("Expected null reference has nonempty identity fields: " + component.sourceId + "." + field.path);
                            if (field.kind == "reference" && !field.isNull && field.path != "m_Script" &&
                                String.IsNullOrEmpty(field.refSourceId) && String.IsNullOrEmpty(field.refGuid) &&
                                (String.IsNullOrEmpty(field.refType) || String.IsNullOrEmpty(field.refName)))
                                throw new InvalidOperationException("Non-null reference needs sourceId, GUID, or both exact type and name: " + component.sourceId + "." + field.path);
                            if (field.kind == "reference" && field.path == "m_Script" && !field.isNull &&
                                (String.IsNullOrEmpty(field.refGuid) || String.IsNullOrEmpty(field.refLocalId)))
                                throw new InvalidOperationException("m_Script requires exact expected MonoScript GUID/local ID: " + component.sourceId);
                        }
                    }
                }
                long fields = root.nodes.Sum(n => (long)n.components.Sum(c => c.fields.Length));
                if (fields > MaxFieldsPerRoot) throw new InvalidOperationException("Root field count exceeds bounded limit: " + root.sourceId);
            }
            if (totalNodes > MaxTotalNodes || totalComponents > MaxTotalComponents || totalFields > MaxTotalFields)
                throw new InvalidOperationException("Aggregate plan node/component/field budget exceeded");
        }

        static string RequiredEnvironment(string key)
        {
            string value = Environment.GetEnvironmentVariable(key);
            if (String.IsNullOrWhiteSpace(value)) throw new InvalidOperationException("Required environment variable is missing: " + key);
            return value;
        }

        static byte[] ReadBounded(string path, int maxBytes)
        {
            var info = new FileInfo(path);
            if (!info.Exists || info.Length < 1 || info.Length > maxBytes)
                throw new InvalidOperationException("Plan file missing/empty/over size limit");
            return File.ReadAllBytes(path);
        }

        static string SafeReadbackPath(string root, string relative)
        {
            if (!IsReadbackRelative(relative)) throw new InvalidOperationException("Unsafe outputRelative path");
            string full = Path.GetFullPath(Path.Combine(root, relative.Replace('/', Path.DirectorySeparatorChar)));
            RequireWithin(root, full, "outputRelative");
            return full;
        }

        static bool IsReadbackRelative(string path)
        {
            if (String.IsNullOrEmpty(path) || Path.IsPathRooted(path) || path.IndexOf('\\') >= 0 || path.IndexOf(':') >= 0)
                return false;
            string[] parts = path.Split('/');
            if (parts.Length < 3 || parts[0] != "Analysis" || parts[1] != "Readback") return false;
            return parts.All(p => !String.IsNullOrEmpty(p) && p != "." && p != "..");
        }

        static void ValidateAssetPrefabPath(string root, string assetPath)
        {
            if (String.IsNullOrEmpty(assetPath) || !assetPath.StartsWith("Assets/", StringComparison.Ordinal) ||
                assetPath.IndexOf('\\') >= 0 || assetPath.Split('/').Any(p => p == ".." || p == ".") ||
                !assetPath.EndsWith(".prefab", StringComparison.Ordinal))
                throw new InvalidOperationException("root.path must be a safe Assets Prefab path");
            string full = Path.GetFullPath(Path.Combine(root, assetPath.Replace('/', Path.DirectorySeparatorChar)));
            RequireWithin(root, full, "root.path");
        }

        static void EnsureReadbackDirectory(string root, string directory)
        {
            string full = Path.GetFullPath(directory);
            RequireWithin(root, full, "image output");
            Directory.CreateDirectory(full);
        }

        static void RequireWithin(string root, string full, string label)
        {
            string normalizedRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            string normalizedFull = Path.GetFullPath(full);
            if (!normalizedFull.StartsWith(normalizedRoot, StringComparison.Ordinal))
                throw new InvalidOperationException(label + " escapes the candidate project");
        }

        static string SafeId(string value)
        {
            if (String.IsNullOrEmpty(value)) throw new InvalidOperationException("Cannot create safe output name from empty identity");
            byte[] bytes = Encoding.UTF8.GetBytes(value);
            using (SHA256 hash = SHA256.Create())
                return BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-", String.Empty).ToLowerInvariant().Substring(0, 24);
        }

        static string SafeGuid(string value)
        {
            if (String.IsNullOrEmpty(value) || value.Any(c => !Uri.IsHexDigit(c))) throw new InvalidOperationException("Native Prefab GUID is invalid");
            return value.ToLowerInvariant();
        }

        static string RelativeReadbackImage(string path)
        {
            string normalized = path.Replace('\\', '/');
            int marker = normalized.LastIndexOf("Analysis/Readback/", StringComparison.Ordinal);
            if (marker < 0) return normalized;
            return normalized.Substring(marker);
        }

        static string Sha256(byte[] bytes)
        {
            using (SHA256 hash = SHA256.Create())
                return BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-", String.Empty).ToLowerInvariant();
        }

        static bool IsSha256(string value)
        {
            return value != null && value.Length == 64 && value.All(c => (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'));
        }

        static bool Finite(float value)
        {
            return !Single.IsNaN(value) && !Single.IsInfinity(value);
        }
    }
}
