// Reconstruct a source-described Unity Prefab as a fresh native object graph.
// This path is limited to an isolated candidate and never loads source components.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MonkeyUnitySource
{
    public static partial class UnityPrefabStaticReadback
    {
        // The caller owns the candidate and is responsible for reopening/checking it after this method.
        // Nothing is saved until the complete in-memory hierarchy has passed CheckTree.
        static void ReconstructRoot(string projectRoot, RootPlan plan, RootResult result)
        {
            if (String.IsNullOrWhiteSpace(projectRoot)) throw new InvalidOperationException("Candidate projectRoot is empty");
            ValidateAssetPrefabPath(projectRoot, plan == null ? null : plan.path);
            if (plan == null || String.IsNullOrEmpty(plan.sourceId) || plan.nodes == null || plan.nodes.Length == 0)
                throw new InvalidOperationException("Reconstruction requires a complete non-empty RootPlan");

            string fullProjectRoot = System.IO.Path.GetFullPath(projectRoot);
            string targetPath = System.IO.Path.GetFullPath(System.IO.Path.Combine(fullProjectRoot,
                plan.path.Replace('/', System.IO.Path.DirectorySeparatorChar)));
            RequireWithin(fullProjectRoot, targetPath, "candidate Prefab");
            string originalGuid = AssetDatabase.AssetPathToGUID(plan.path);
            if (String.IsNullOrEmpty(originalGuid) || AssetDatabase.LoadAssetAtPath<GameObject>(plan.path) == null)
                throw new InvalidOperationException("The isolated candidate Prefab must already exist so its asset GUID can be preserved: " + plan.path);

            Dictionary<string, Type> componentTypes = PreflightReconstructionPlan(plan);
            Dictionary<string, NodePlan> nodesById = new Dictionary<string, NodePlan>(StringComparer.Ordinal);
            Dictionary<string, NodePlan> nodesByIndex = new Dictionary<string, NodePlan>(StringComparer.Ordinal);
            ValidateChildIndexCoverage(plan.nodes);
            foreach (NodePlan node in plan.nodes)
            {
                if (!nodesById.TryAdd(node.sourceId, node))
                    throw new InvalidOperationException("Duplicate node sourceId: " + node.sourceId);
                string key = IndexKey(node.indices);
                if (!nodesByIndex.TryAdd(key, node))
                    throw new InvalidOperationException("Duplicate node child-index path: " + key);
            }
            if (!nodesByIndex.ContainsKey(String.Empty)) throw new InvalidOperationException("Root node must use empty indices[]");
            if (!String.Equals(nodesByIndex[String.Empty].sourceId, plan.sourceId, StringComparison.Ordinal))
                throw new InvalidOperationException("RootPlan.sourceId does not match the empty-index root node sourceId");

            Scene preview = default(Scene);
            bool previewOpened = false;
            try
            {
                preview = EditorSceneManager.NewPreviewScene();
                previewOpened = true;
                var nodeObjects = new Dictionary<string, GameObject>(StringComparer.Ordinal);
                var componentsById = new Dictionary<string, Component>(StringComparer.Ordinal);
                var unityObjectBySourceId = new Dictionary<string, UnityEngine.Object>(StringComparer.Ordinal);

                NodePlan[] orderedNodes = plan.nodes.OrderBy(n => n.indices.Length)
                    .ThenBy(n => n.indices, IndexArrayComparer.Instance).ToArray();
                foreach (NodePlan node in orderedNodes)
                {
                    Type transformType = ExpectedTransformType(node, componentTypes);
                    var gameObject = new GameObject(node.name, transformType);
                    gameObject.SetActive(false);
                    SceneManager.MoveGameObjectToScene(gameObject, preview);
                    gameObject.layer = node.layer;
                    if (!String.IsNullOrEmpty(node.tag)) gameObject.tag = node.tag;
                    nodeObjects.Add(node.sourceId, gameObject);
                    unityObjectBySourceId.Add(node.sourceId, gameObject);
                    if (node.indices.Length != 0)
                    {
                        int[] parentIndices = node.indices.Take(node.indices.Length - 1).ToArray();
                        NodePlan parentPlan;
                        if (!nodesByIndex.TryGetValue(IndexKey(parentIndices), out parentPlan))
                            throw new InvalidOperationException("Parent node is missing for source node " + node.sourceId);
                        GameObject parent;
                        if (!nodeObjects.TryGetValue(parentPlan.sourceId, out parent))
                            throw new InvalidOperationException("Parent node was not constructed before child " + node.sourceId);
                        gameObject.transform.SetParent(parent.transform, false);
                        int sibling = node.indices[node.indices.Length - 1];
                        if (sibling < 0 || sibling > parent.transform.childCount - 1)
                            throw new InvalidOperationException("Source child index cannot be placed exactly: " + IndexKey(node.indices));
                        gameObject.transform.SetSiblingIndex(sibling);
                    }
                }

                foreach (NodePlan node in orderedNodes)
                {
                    GameObject gameObject = nodeObjects[node.sourceId];
                    ComponentPlan[] expected = node.components ?? new ComponentPlan[0];
                    if (expected.Length == 0) throw new InvalidOperationException("Source node has no ordered Transform component: " + node.sourceId);
                    for (int componentIndex = 0; componentIndex < expected.Length; componentIndex++)
                    {
                        ComponentPlan componentPlan = expected[componentIndex];
                        Type expectedType = componentTypes[componentPlan.sourceId];
                        Component[] existing = gameObject.GetComponents<Component>();
                        if (existing.Length <= componentIndex)
                        {
                            Component added = gameObject.AddComponent(expectedType);
                            if (added == null) throw new InvalidOperationException("Unity AddComponent returned null: " + componentPlan.sourceId);
                            existing = gameObject.GetComponents<Component>();
                        }
                        if (existing.Length <= componentIndex)
                            throw new InvalidOperationException("Unity did not create the expected component slot: " + componentPlan.sourceId);
                        Component actual = existing[componentIndex];
                        if (actual == null) throw new InvalidOperationException("Unity created a MissingScript slot at " + componentPlan.sourceId);
                        if (actual.GetType() != expectedType)
                            throw new InvalidOperationException("AddComponent/RequireComponent order differs at " + node.sourceId + "[" + componentIndex + "]: expected=" + expectedType.FullName + ", actual=" + actual.GetType().FullName);
                        if (!componentsById.TryAdd(componentPlan.sourceId, actual))
                            throw new InvalidOperationException("Duplicate component sourceId: " + componentPlan.sourceId);
                        unityObjectBySourceId.Add(componentPlan.sourceId, actual);
                    }
                    Component[] finalComponents = gameObject.GetComponents<Component>();
                    if (finalComponents.Any(c => c == null))
                        throw new InvalidOperationException("Unity hierarchy contains MissingScript after component construction: " + node.sourceId);
                    if (finalComponents.Length != expected.Length)
                        throw new InvalidOperationException("Unity/RequireComponent inserted an undeclared extra component on " + node.sourceId + ": expected=" + expected.Length + ", actual=" + finalComponents.Length);
                }

                // Per-leaf writes may populate a constructor/default AnimationCurve even
                // when the source array is empty. Preserve an imported built-in component
                // only after every retained empty-curve field matches the original source.
                // Remaining source fields and references are applied and checked below.
                var seedRows = new List<BuiltinSeedEvidence>();
                var seededSourceIds = new HashSet<string>(StringComparer.Ordinal);
                GameObject originalAsset = AssetDatabase.LoadAssetAtPath<GameObject>(plan.path);
                foreach (NodePlan node in orderedNodes)
                for (int index = 0; index < node.components.Length; index++)
                {
                    ComponentPlan componentPlan = node.components[index];
                    BuiltinSeedEvidence seed = SeedOriginalParticleState(plan, node, index,
                        originalAsset, componentsById[componentPlan.sourceId], originalGuid);
                    if (seed == null) continue;
                    if (!String.IsNullOrEmpty(componentPlan.particleBounceProfile))
                    {
                        if (componentPlan.particleBounceProfile != ParticleBounceProfile || Application.unityVersion != "6000.6.2f1")
                            throw new InvalidOperationException("Unknown native ParticleSystem reconstruction profile");
                        var collision = ((ParticleSystem)componentsById[componentPlan.sourceId]).collision;
                        if (collision.enabled) throw new InvalidOperationException("ParticleSystem Collision must remain disabled");
                        collision.bounce = new ParticleSystem.MinMaxCurve(1f);
                    }
                    seedRows.Add(seed);
                    seededSourceIds.Add(componentPlan.sourceId);
                    result.builtinSeeds = seedRows.ToArray();
                }

                // Source references can point forward, so all node and component identities must exist first.
                // Populate every scalar before references can activate native SDK drivers.
                // A Slider can otherwise track a child RectTransform's constructor values.
                foreach (bool referencesOnly in new[] {false, true})
                foreach (NodePlan node in orderedNodes)
                foreach (ComponentPlan componentPlan in node.components)
                    ApplySourceFields(componentPlan, componentsById[componentPlan.sourceId], unityObjectBySourceId,
                        seededSourceIds.Contains(componentPlan.sourceId), referencesOnly);

                // All objects were inactive while being populated. Set children first and the root last,
                // so activation follows only the source activeSelf values and cannot expose partial state.
                foreach (NodePlan node in orderedNodes.OrderByDescending(n => n.indices.Length))
                    nodeObjects[node.sourceId].SetActive(node.active);

                var validationResult = new RootResult { failures = new Failure[0], limitations = new string[0] };
                var failures = new List<Failure>();
                MappedTree constructed = CheckTree(plan, nodeObjects[nodesByIndex[String.Empty].sourceId],
                    "reconstruction-before-save", false, false, validationResult, failures);
                if (failures.Count != 0)
                    throw new InvalidOperationException("Constructed hierarchy failed CheckTree: " + String.Join(" | ", failures.Select(f => f.message).ToArray()));

                result.reconstructionValidated = true;
                result.reconstructionFieldsChecked = constructed.fieldsChecked;
                result.particleRepresentations = validationResult.particleRepresentations;
                bool saved;
                GameObject savedAsset = SavePlannedPrefab(plan, nodeObjects[nodesByIndex[String.Empty].sourceId],
                    componentsById, unityObjectBySourceId, plan.path, out saved);
                string savedGuid = AssetDatabase.AssetPathToGUID(plan.path);
                if (!String.Equals(originalGuid, savedGuid, StringComparison.Ordinal))
                    throw new InvalidOperationException("Candidate Prefab GUID changed during reconstruction save: before=" + originalGuid + ", after=" + savedGuid);
            }
            finally
            {
                if (previewOpened && preview.IsValid()) EditorSceneManager.ClosePreviewScene(preview);
            }
        }

        static GameObject SavePlannedPrefab(RootPlan plan, GameObject root,
            Dictionary<string, Component> components, Dictionary<string, UnityEngine.Object> sourceObjects,
            string path, out bool saved)
        {
            // Native SDK trackers may serialize pre-driven cached RectTransform values.
            // Deactivate to clear drivers, then restore the already verified planned state.
            // Restore source root activeSelf on the persistent asset, without scene activation.
            root.SetActive(false);
            foreach (NodePlan node in plan.nodes)
            foreach (ComponentPlan componentPlan in node.components)
                ApplySourceFields(componentPlan, components[componentPlan.sourceId], sourceObjects,
                    NeedsEmptyParticleCurveSeed(componentPlan), false);
            GameObject asset = PrefabUtility.SaveAsPrefabAsset(root, path, out saved);
            if (!saved || asset == null || !AssetDatabase.Contains(asset))
                throw new InvalidOperationException("SaveAsPrefabAsset failed for isolated planned Prefab: " + path);
            asset.SetActive(plan.nodes.Single(n => n.indices.Length == 0).active);
            EditorUtility.SetDirty(asset);
            AssetDatabase.SaveAssets();
            return asset;
        }

        static BuiltinSeedEvidence SeedOriginalParticleState(RootPlan plan, NodePlan node,
            int componentIndex, GameObject originalAsset, Component target, string originalGuid)
        {
            ComponentPlan componentPlan = node.components[componentIndex];
            if (!NeedsEmptyParticleCurveSeed(componentPlan)) return null;
            Component source = ResolveOriginalBuiltin(plan, node, componentIndex, originalAsset);
            if (target == null || target.GetType() != typeof(ParticleSystem) || source.GetType() != target.GetType() ||
                target == source || AssetDatabase.Contains(target))
                throw new InvalidOperationException("Builtin seed requires a distinct transient native ParticleSystem target");
            string seedGuid; long seedLocalId;
            if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(source, out seedGuid, out seedLocalId) ||
                seedGuid != originalGuid || seedLocalId == 0 || AssetDatabase.GetAssetPath(source) != plan.path)
                throw new InvalidOperationException("Builtin seed source native identity differs");
            var emptyCurves = componentPlan.fields.Where(f => f.kind == "integer" && f.intValue == 0 &&
                f.path.EndsWith(".m_Curve.Array.size", StringComparison.Ordinal))
                .Select(f => f.path.Substring(0, f.path.Length - ".m_Curve.Array.size".Length) + ".").ToArray();
            var fields = componentPlan.fields.Where(f => emptyCurves.Any(prefix =>
                f.path.StartsWith(prefix, StringComparison.Ordinal))).ToArray();
            VerifyBuiltinSeedFields(componentPlan, source, fields);
            EditorUtility.CopySerialized(source, target);
            VerifyBuiltinSeedFields(componentPlan, target, fields);
            return new BuiltinSeedEvidence { sourceId = componentPlan.sourceId,
                sourceAssetPath = plan.path, sourceGuid = seedGuid,
                sourceLocalId = seedLocalId.ToString(Invariant), type = source.GetType().FullName,
                method = "EditorUtility.CopySerialized;source-empty-curve-fields-verified;remaining-source-fields-applied;references-rebound",
                checkedSourceFields = fields.Length };
        }

        static bool NeedsEmptyParticleCurveSeed(ComponentPlan plan)
        {
            if (plan.type != "UnityEngine.ParticleSystem" || plan.assembly != "UnityEngine.ParticleSystemModule") return false;
            return plan.fields.Any(field => field.kind == "integer" && field.intValue == 0 &&
                field.path.EndsWith(".m_Curve.Array.size", StringComparison.Ordinal));
        }

        static Component ResolveOriginalBuiltin(RootPlan plan, NodePlan node, int componentIndex, GameObject original)
        {
            if (original == null) throw new InvalidOperationException("Original provider Prefab is absent for builtin seed");
            Transform current = original.transform;
            for (int depth = 0; depth <= node.indices.Length; depth++)
            {
                int[] prefix = node.indices.Take(depth).ToArray();
                NodePlan[] matches = plan.nodes.Where(n => IndexKey(n.indices) == IndexKey(prefix)).ToArray();
                if (matches.Length != 1 || current.name != matches[0].name)
                    throw new InvalidOperationException("Original provider/source hierarchy identity differs for builtin seed;depth=" + depth.ToString(Invariant) + ";expected=" + (matches.Length == 1 ? matches[0].name : "ambiguous") + ";actual=" + current.name);
                if (depth == node.indices.Length) break;
                int index = node.indices[depth];
                if (index < 0 || index >= current.childCount)
                    throw new InvalidOperationException("Original provider child index is absent for builtin seed");
                current = current.GetChild(index);
            }
            Component[] components = current.GetComponents<Component>();
            if (components.Length != node.components.Length || componentIndex >= components.Length ||
                components[componentIndex] == null || components[componentIndex].GetType() != typeof(ParticleSystem))
                throw new InvalidOperationException("Original provider ordered component identity differs for builtin seed");
            return components[componentIndex];
        }

        static void VerifyBuiltinSeedFields(ComponentPlan plan, Component component, FieldPlan[] fields)
        {
            if (fields.Length == 0) throw new InvalidOperationException("Builtin seed has no source fields");
            var serialized = new SerializedObject(component);
            serialized.UpdateIfRequiredOrScript();
            foreach (FieldPlan field in fields)
            {
                FieldResult check = CheckField(plan, component, serialized, field,
                    new Dictionary<string, UnityEngine.Object>(StringComparer.Ordinal),
                    "source-builtin-seed", true, false);
                if (!check.passed) throw new InvalidOperationException("Builtin seed/source field differs: " +
                    plan.sourceId + "." + field.path + ";expected=" + check.expected + ";actual=" + check.actual);
            }
        }

        static Dictionary<string, Type> PreflightReconstructionPlan(RootPlan plan)
        {
            PreflightPlanCallbacks(plan);
            var result = new Dictionary<string, Type>(StringComparer.Ordinal);
            var usedSourceIds = new HashSet<string>(StringComparer.Ordinal);
            foreach (NodePlan node in plan.nodes)
            {
                if (node == null || String.IsNullOrEmpty(node.sourceId) || node.name == null || node.indices == null || node.components == null)
                    throw new InvalidOperationException("Source node plan is incomplete");
                if (!usedSourceIds.Add(node.sourceId)) throw new InvalidOperationException("Duplicate sourceId: " + node.sourceId);
                if (node.layer < 0 || node.layer > 31) throw new InvalidOperationException("Source node layer is outside Unity layer range: " + node.sourceId);
                foreach (ComponentPlan component in node.components)
                {
                    if (component == null || String.IsNullOrEmpty(component.sourceId) || String.IsNullOrEmpty(component.type) ||
                        String.IsNullOrEmpty(component.assembly) || component.fields == null)
                        throw new InvalidOperationException("Source component plan is incomplete on " + node.sourceId);
                    if (!usedSourceIds.Add(component.sourceId)) throw new InvalidOperationException("Duplicate sourceId: " + component.sourceId);
                    Assembly[] assemblies = AppDomain.CurrentDomain.GetAssemblies()
                        .Where(a => AssemblyMatches(component.assembly, a)).ToArray();
                    if (assemblies.Length != 1)
                        throw new InvalidOperationException("Cannot identify exactly one loaded target assembly for " + component.sourceId + ": " + component.assembly);
                    Type[] matches = SafeTypes(assemblies[0]).Where(t => TypeMatches(component.type, t)).ToArray();
                    if (matches.Length != 1)
                        throw new InvalidOperationException("Cannot identify exactly one loaded target type for " + component.sourceId + ": " + component.assembly + "/" + component.type);
                    Type type = matches[0];
                    if (!typeof(Component).IsAssignableFrom(type) || type.IsAbstract || type.ContainsGenericParameters)
                        throw new InvalidOperationException("Source target type is not a concrete Unity Component: " + type.FullName);
                    if (!AssemblyMatches(component.assembly, type.Assembly) || !TypeMatches(component.type, type))
                        throw new InvalidOperationException("Resolved target type identity does not match the source plan: " + component.sourceId);
                    if (!IsUnityOwnedAssembly(component.assembly) && typeof(MonoBehaviour).IsAssignableFrom(type))
                    {
                        EnsureTypeSafe(type, plan.sourceId);
                        EnsureNoResetCallback(type, plan.sourceId);
                        EnsureTrivialInstanceConstructors(type, plan.sourceId);
                    }
                    result.Add(component.sourceId, type);
                    foreach (FieldPlan field in component.fields)
                    {
                        if (field == null || String.IsNullOrEmpty(field.path))
                            throw new InvalidOperationException("Source serialized field is incomplete on " + component.sourceId);
                        if (!(field.kind == "integer" || field.kind == "character" || field.kind == "byte" || field.kind == "float" ||
                              field.kind == "boolean" || field.kind == "string" || field.kind == "reference"))
                            throw new InvalidOperationException("Unsupported source serialized field kind " + field.kind + " at " + component.sourceId + "." + field.path);
                        if (field.path == "m_Script" && (field.kind != "reference" || field.isNull))
                            throw new InvalidOperationException("m_Script must be a non-null reference on " + component.sourceId);
                        if (field.kind == "byte" && (field.intValue < 0 || field.intValue > 255))
                            throw new InvalidOperationException("Source byte value is outside 0..255 at " + component.sourceId + "." + field.path);
                        if (field.kind == "reference") ValidateReferencePlan(field, component);
                    }
                }
            }
            return result;
        }

        static void ValidateReferencePlan(FieldPlan field, ComponentPlan component)
        {
            bool hasSource = !String.IsNullOrEmpty(field.refSourceId);
            bool hasGuid = !String.IsNullOrEmpty(field.refGuid);
            bool hasLocal = !String.IsNullOrEmpty(field.refLocalId);
            if (field.isNull)
            {
                if (hasSource || hasGuid || hasLocal || !String.IsNullOrEmpty(field.refType) || !String.IsNullOrEmpty(field.refName))
                    throw new InvalidOperationException("Null reference contains a conflicting identity at " + component.sourceId + "." + field.path);
                return;
            }
            if (field.path == "m_Script")
            {
                if (String.IsNullOrEmpty(field.refGuid) || !hasLocal)
                    throw new InvalidOperationException("m_Script requires its exact source GUID and local ID: " + component.sourceId);
                return;
            }
            if (!hasSource && !hasGuid)
                throw new InvalidOperationException("Reference needs an exact sourceId or asset GUID: " + component.sourceId + "." + field.path);
            if (hasGuid && String.IsNullOrEmpty(field.refType))
                throw new InvalidOperationException("Asset reference GUID must include its exact object type: " + component.sourceId + "." + field.path);
            if (hasLocal && !hasGuid)
                throw new InvalidOperationException("Asset local ID cannot be provided without a GUID: " + component.sourceId + "." + field.path);
        }

        static void EnsureNoResetCallback(Type type, string rootSourceId)
        {
            for (Type current = type; current != null && current != typeof(MonoBehaviour) &&
                 current != typeof(Behaviour) && current != typeof(Component); current = current.BaseType)
            {
                if (IsUnityOwnedAssembly(current.Assembly.GetName().Name)) break;
                bool reset = current.GetMethods(BindingFlags.Instance | BindingFlags.Public |
                    BindingFlags.NonPublic | BindingFlags.DeclaredOnly)
                    .Any(method => method.Name == "Reset" && method.GetParameters().Length == 0);
                if (reset)
                    throw new InvalidOperationException("Reconstruction blocked to avoid Unity Editor Reset callback " + current.FullName + ".Reset; root=" + rootSourceId);
            }
        }

        static void EnsureTrivialInstanceConstructors(Type type, string rootSourceId)
        {
            for (Type current = type; current != null && current != typeof(MonoBehaviour) &&
                 current != typeof(Behaviour) && current != typeof(Component); current = current.BaseType)
            {
                if (IsUnityOwnedAssembly(current.Assembly.GetName().Name)) break;
                ConstructorInfo[] constructors = current.GetConstructors(BindingFlags.Instance | BindingFlags.Public |
                    BindingFlags.NonPublic | BindingFlags.DeclaredOnly);
                foreach (ConstructorInfo constructor in constructors)
                {
                    byte[] il;
                    try { il = constructor.GetMethodBody() == null ? null : constructor.GetMethodBody().GetILAsByteArray(); }
                    catch { il = null; }
                    // The only accepted body is `ldarg.0; call base::.ctor; ret`.
                    if (il == null || il.Length != 7 || il[0] != 0x02 || il[1] != 0x28 || il[6] != 0x2a)
                        throw new InvalidOperationException("Reconstruction blocked for non-trivial instance constructor " + current.FullName + "; root=" + rootSourceId);
                    int token = BitConverter.ToInt32(il, 2);
                    MethodBase called;
                    try { called = current.Module.ResolveMethod(token); }
                    catch { called = null; }
                    ConstructorInfo baseConstructor = called as ConstructorInfo;
                    if (baseConstructor == null || baseConstructor.DeclaringType != current.BaseType)
                        throw new InvalidOperationException("Reconstruction blocked for constructor that does not only chain to its base type: " + current.FullName + "; root=" + rootSourceId);
                }
            }
        }

        static Type ExpectedTransformType(NodePlan node, Dictionary<string, Type> componentTypes)
        {
            if (node.components == null || node.components.Length == 0)
                throw new InvalidOperationException("Source node has no Transform: " + node.sourceId);
            Type type = componentTypes[node.components[0].sourceId];
            if (type != typeof(Transform) && type != typeof(RectTransform))
                throw new InvalidOperationException("The first source component must be Transform or RectTransform: " + node.sourceId + ", actual=" + type.FullName);
            if (node.components.Skip(1).Any(c => componentTypes[c.sourceId] == typeof(Transform) || componentTypes[c.sourceId] == typeof(RectTransform)))
                throw new InvalidOperationException("A source node has more than one Transform component: " + node.sourceId);
            return type;
        }

        static void ApplySourceFields(ComponentPlan plan, Component component,
                                      Dictionary<string, UnityEngine.Object> sourceObjects, bool scalarStateSeeded, bool referencesOnly)
        {
            if (plan.disabledUnavailable && !(component is MonoBehaviour))
                throw new InvalidOperationException("disabledUnavailable applies to a non-MonoBehaviour: " + plan.sourceId);
            var serialized = new SerializedObject(component);
            serialized.UpdateIfRequiredOrScript();
            foreach (FieldPlan field in plan.fields)
            {
                if ((field.kind == "reference") != referencesOnly) continue;
                SerializedProperty property = serialized.FindProperty(field.path);
                if (property == null)
                    throw new InvalidOperationException("SerializedProperty is absent: " + plan.sourceId + "." + field.path);

                // Unity owns these object-graph headers; create them through native hierarchy APIs and verify later.
                if (IsHierarchyHeader(field.path)) continue;
                if (field.path == "m_Script")
                {
                    ValidateNativeScript(component, field);
                    continue;
                }
                if (scalarStateSeeded && field.kind != "reference")
                {
                    FieldResult retained = CheckField(plan, component, serialized, field, sourceObjects,
                        "retained-native-builtin-scalar", true, false);
                    // Avoid setters for already matching scalar state. Source differences still
                    // use the normal typed setter; the full tree is checked before saving.
                    if (retained.passed) continue;
                }
                if (field.kind == "character")
                {
                    if (field.intValue < 0 || field.intValue > 65535 || property.propertyType != SerializedPropertyType.Character)
                        throw PropertyTypeError(plan, field, "Character/UTF-16 code unit", property);
                    property.intValue = checked((int)field.intValue);
                }
                else if (field.kind == "integer")
                {
                    if (property.propertyType != SerializedPropertyType.Integer && property.propertyType != SerializedPropertyType.Enum &&
                        property.propertyType != SerializedPropertyType.ArraySize)
                        throw PropertyTypeError(plan, field, "Integer/Enum/ArraySize", property);
                    if (property.propertyType == SerializedPropertyType.Integer) property.longValue = field.intValue;
                    else property.intValue = checked((int)field.intValue);
                }
                else if (field.kind == "byte")
                {
                    if (field.intValue < 0 || field.intValue > 255)
                        throw new InvalidOperationException("Byte source value outside 0..255: " + plan.sourceId + "." + field.path);
                    if (property.propertyType == SerializedPropertyType.Boolean)
                    {
                        if (field.intValue != 0 && field.intValue != 1)
                            throw new InvalidOperationException("Byte source value cannot be represented by native Boolean except 0 or 1: " + plan.sourceId + "." + field.path);
                        property.boolValue = field.intValue == 1;
                    }
                    else if (property.propertyType == SerializedPropertyType.Integer || property.propertyType == SerializedPropertyType.Enum)
                    {
                        property.intValue = (int)field.intValue;
                    }
                    else
                    {
                        throw PropertyTypeError(plan, field, "Integer/Enum (byte)", property);
                    }
                }
                else if (field.kind == "float")
                {
                    if (property.propertyType != SerializedPropertyType.Float)
                        throw PropertyTypeError(plan, field, "Float", property);
                    if (Double.IsNaN(field.floatValue) || Double.IsInfinity(field.floatValue))
                        throw new InvalidOperationException("Non-finite source float: " + plan.sourceId + "." + field.path);
                    property.doubleValue = field.floatValue;
                }
                else if (field.kind == "boolean")
                {
                    if (property.propertyType != SerializedPropertyType.Boolean)
                        throw PropertyTypeError(plan, field, "Boolean", property);
                    property.boolValue = plan.disabledUnavailable && field.path == "m_Enabled" ? false : field.boolValue;
                }
                else if (field.kind == "string")
                {
                    if (property.propertyType != SerializedPropertyType.String)
                        throw PropertyTypeError(plan, field, "String", property);
                    property.stringValue = field.stringValue ?? String.Empty;
                }
                else if (field.kind == "reference")
                {
                    if (property.propertyType != SerializedPropertyType.ObjectReference)
                        throw PropertyTypeError(plan, field, "ObjectReference", property);
                    property.objectReferenceValue = ResolveReference(field, sourceObjects, component, plan);
                }
                else
                {
                    throw new InvalidOperationException("Unsupported serialized field kind: " + field.kind + " at " + plan.sourceId + "." + field.path);
                }
            }
            if (!serialized.ApplyModifiedPropertiesWithoutUndo())
            {
                // Unity returns false when values were already equal. Readback below distinguishes that from failure.
                serialized.UpdateIfRequiredOrScript();
            }
            if (plan.disabledUnavailable)
            {
                ((Behaviour)component).enabled = false;
                if (((Behaviour)component).enabled) throw new InvalidOperationException("Could not disable unavailable behavior: " + plan.sourceId);
            }
        }

        static bool IsHierarchyHeader(string path)
        {
            return path == "m_GameObject" || path == "m_Father" || path == "m_Children" ||
                path == "m_Children.Array.size" ||
                (path.StartsWith("m_Children.Array.data[", StringComparison.Ordinal) && path.EndsWith("]", StringComparison.Ordinal)) ||
                path == "m_RootOrder";
        }

        static InvalidOperationException PropertyTypeError(ComponentPlan component, FieldPlan field,
                                                             string expected, SerializedProperty actual)
        {
            return new InvalidOperationException("SerializedProperty type mismatch at " + component.sourceId + "." + field.path +
                ": expected " + expected + ", actual " + actual.propertyType);
        }

        static UnityEngine.Object ResolveReference(FieldPlan field,
                                                   Dictionary<string, UnityEngine.Object> sourceObjects,
                                                   Component owner, ComponentPlan componentPlan)
        {
            if (field.isNull) return null;
            if (!String.IsNullOrEmpty(field.refSourceId))
            {
                UnityEngine.Object mapped;
                if (!sourceObjects.TryGetValue(field.refSourceId, out mapped) || mapped == null)
                    throw new InvalidOperationException("Reference sourceId does not map to exactly one reconstructed object: " + field.refSourceId);
                VerifyPlannedReferenceTypeAndName(field, mapped, componentPlan);
                return mapped;
            }
            if (field.path == "m_Script") throw new InvalidOperationException("m_Script must be produced by AddComponent, never assigned by this module");
            if (String.IsNullOrEmpty(field.refGuid))
                throw new InvalidOperationException("Persistent asset reference has no exact GUID: " + componentPlan.sourceId + "." + field.path);
            string assetPath = AssetDatabase.GUIDToAssetPath(field.refGuid);
            if (String.IsNullOrEmpty(assetPath))
                throw new InvalidOperationException("Asset GUID is not present in the candidate project: " + field.refGuid);
            UnityEngine.Object[] assets = AssetDatabase.LoadAllAssetsAtPath(assetPath);
            var matches = new List<UnityEngine.Object>();
            foreach (UnityEngine.Object asset in assets)
            {
                if (asset == null || !TypeMatches(field.refType, asset.GetType())) continue;
                string guid;
                long localId;
                if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(asset, out guid, out localId) || guid != field.refGuid) continue;
                if (!String.IsNullOrEmpty(field.refLocalId) && localId.ToString(CultureInfo.InvariantCulture) != field.refLocalId) continue;
                matches.Add(asset);
            }
            if (matches.Count != 1)
                throw new InvalidOperationException("Asset reference identity is not unique by GUID/localID/type: " + field.refGuid + "/" +
                    (field.refLocalId ?? String.Empty) + "/" + field.refType + ", matches=" + matches.Count);
            UnityEngine.Object resolved = matches[0];
            VerifyPlannedReferenceTypeAndName(field, resolved, componentPlan);
            return resolved;
        }

        static void VerifyPlannedReferenceTypeAndName(FieldPlan field, UnityEngine.Object actual, ComponentPlan owner)
        {
            if (!String.IsNullOrEmpty(field.refType) && !TypeMatches(field.refType, actual.GetType()))
                throw new InvalidOperationException("Reference object type differs at " + owner.sourceId + "." + field.path +
                    ": expected=" + field.refType + ", actual=" + actual.GetType().FullName);
            if (!String.IsNullOrEmpty(field.refName) && !String.Equals(field.refName, actual.name, StringComparison.Ordinal))
                throw new InvalidOperationException("Reference object name differs at " + owner.sourceId + "." + field.path +
                    ": expected=" + field.refName + ", actual=" + actual.name);
        }

        static void ValidateNativeScript(Component component, FieldPlan sourceField)
        {
            MonoBehaviour behaviour = component as MonoBehaviour;
            if (behaviour == null) throw new InvalidOperationException("m_Script appears on a non-MonoBehaviour: " + component.GetType().FullName);
            MonoScript script = MonoScript.FromMonoBehaviour(behaviour);
            Type scriptClass = script == null ? null : script.GetClass();
            if (script == null || scriptClass != component.GetType() || !AssemblyMatches(component.GetType().Assembly.GetName().Name, scriptClass.Assembly))
                throw new InvalidOperationException("Native MonoScript.GetClass/assembly does not exactly match added component " + component.GetType().FullName);
            string targetGuid;
            long targetLocalId;
            if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(script, out targetGuid, out targetLocalId))
                throw new InvalidOperationException("Native MonoScript has no persistent GUID/localID for " + component.GetType().FullName);
            SerializedProperty scriptProperty = new SerializedObject(component).FindProperty("m_Script");
            if (scriptProperty == null || scriptProperty.objectReferenceValue != script)
                throw new InvalidOperationException("The native m_Script property differs from MonoScript.FromMonoBehaviour");
            string targetLocalText = targetLocalId.ToString(CultureInfo.InvariantCulture);
            if (!String.Equals(sourceField.refGuid, targetGuid, StringComparison.Ordinal) ||
                !String.Equals(sourceField.refLocalId, targetLocalText, StringComparison.Ordinal))
                throw new InvalidOperationException("Native MonoScript target identity differs from the pinned plan: expected=" +
                    sourceField.refGuid + "/" + sourceField.refLocalId + ", actual=" + targetGuid + "/" + targetLocalText +
                    "; component=" + component.GetType().FullName + "; assembly=" + component.GetType().Assembly.GetName().Name);
        }

        sealed class IndexArrayComparer : IComparer<int[]>
        {
            internal static readonly IndexArrayComparer Instance = new IndexArrayComparer();
            public int Compare(int[] left, int[] right)
            {
                int count = Math.Min(left.Length, right.Length);
                for (int i = 0; i < count; i++)
                {
                    int compare = left[i].CompareTo(right[i]);
                    if (compare != 0) return compare;
                }
                return left.Length.CompareTo(right.Length);
            }
        }
    }
}
