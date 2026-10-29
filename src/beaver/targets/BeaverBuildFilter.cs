// Read-only Unity Editor dependency snapshot for beaver build filtering.
// The owning native runner is responsible for invoking this collector and
// writing the returned schemaVersion=1 snapshot as UTF-8 JSON.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEngine;

public static class BeaverBuildFilter
{
    [Serializable]
    public sealed class AssetRecord
    {
        public string path;
        public string guid;
        public long[] localIds;
        public string[] types;
        public ObjectIdentity[] objects;
        public string status;
        public string identityStatus;
        public int objectCount;
        public string error;
    }

    [Serializable]
    public sealed class ObjectIdentity
    {
        public string guid;
        public long localId;
        public string type;
        public string name;
        public string state;
    }

    [Serializable]
    public sealed class DependencyRecord
    {
        public string path;
        public string guid;
        public long localId;
        public string type;
        public string[] roots;
    }

    [Serializable]
    public sealed class UnresolvedDependencyRecord
    {
        public string path;
        public string guid;
        public string[] roots;
        public string error;
    }

    [Serializable]
    public sealed class Snapshot
    {
        public int schemaVersion = 1;
        public string target;
        public string pipeline;
        public string[] buildScenes;
        public string[] explicitRoots;
        public string[] implicitRoots;
        public Coverage coverage;
        public AssetRecord[] assets;
        public DependencyRecord[] dependencies;
        public UnresolvedDependencyRecord[] unresolvedDependencies;
    }

    [Serializable]
    public sealed class Coverage { public bool complete; public string[] blockers; }

    [Serializable]
    private sealed class Job
    {
        public string projectRoot;
        public string stage;
        // `assets` are the enabled build-scene paths; `roots` are additional
        // explicitly selected asset roots. The collector also inventories the
        // complete current Assets catalog directly from AssetDatabase.
        public string[] assets;
        public string[] roots;
        public bool includeObjectIdentities;
        public string platform;
        public string renderPipeline;
        public string reportName;
    }

    [Serializable]
    private sealed class FailedReport { public string status; public string error; }

    // Called by the shared runner on the Editor main thread. AssetDatabase is
    // read-only here: no import, save, move, delete, or settings mutation.
    private static string ActivePipelineIdentity()
    {
        var active = UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline;
        if (active == null) return "BuiltIn";
        var path = AssetDatabase.GetAssetPath(active);
        var guid = String.IsNullOrEmpty(path) ? "" : AssetDatabase.AssetPathToGUID(path).ToLowerInvariant();
        return active.GetType().FullName + "|" + guid;
    }

    private static UnityEngine.Object[] PersistentObjects(string path)
    {
        var main = AssetDatabase.LoadMainAssetAtPath(path);
        var all = AssetDatabase.LoadAllAssetsAtPath(path) ?? Array.Empty<UnityEngine.Object>();
        return all.Concat(main == null ? Array.Empty<UnityEngine.Object>() : new[] { main })
            .Where(item => item != null).Distinct().ToArray();
    }

    private static void AddUnresolved(Dictionary<string, UnresolvedDependencyRecord> unresolved, string path, string guid, string root, string error)
    {
        UnresolvedDependencyRecord record;
        if (!unresolved.TryGetValue(path, out record))
        {
            record = new UnresolvedDependencyRecord { path = path, guid = guid ?? "", roots = Array.Empty<string>(), error = error };
            unresolved.Add(path, record);
        }
        if (String.IsNullOrEmpty(record.guid) && !String.IsNullOrEmpty(guid)) record.guid = guid;
        if (!record.roots.Contains(root)) record.roots = record.roots.Concat(new[] { root }).OrderBy(x => x, StringComparer.Ordinal).ToArray();
        if (String.IsNullOrEmpty(record.error)) record.error = error;
    }

    public static Snapshot Collect(string target, string pipeline, string[] buildScenes, string[] explicitRoots,
        bool includeObjectIdentities = false)
    {
        if (String.IsNullOrWhiteSpace(target) || String.IsNullOrWhiteSpace(pipeline))
            throw new ArgumentException("Exact build target and render pipeline identity are required.");
        if (!String.Equals(EditorUserBuildSettings.activeBuildTarget.ToString(), target, StringComparison.Ordinal))
            throw new InvalidOperationException("Requested platform differs from Editor activeBuildTarget: requested=" + target + " active=" + EditorUserBuildSettings.activeBuildTarget);
        var activePipeline = ActivePipelineIdentity();
        if (!String.Equals(activePipeline, pipeline, StringComparison.Ordinal))
            throw new InvalidOperationException("Requested render pipeline differs from active Editor pipeline: requested=" + pipeline + " active=" + activePipeline);
        buildScenes = (buildScenes ?? Array.Empty<string>()).Distinct().OrderBy(x => x, StringComparer.Ordinal).ToArray();
        explicitRoots = (explicitRoots ?? Array.Empty<string>()).Distinct().OrderBy(x => x, StringComparer.Ordinal).ToArray();
        var enabledScenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).Distinct().OrderBy(x => x, StringComparer.Ordinal).ToArray();
        if (!enabledScenes.SequenceEqual(buildScenes, StringComparer.Ordinal))
            throw new InvalidOperationException("Requested scenes do not exactly match Editor enabled build scenes.");
        var roots = buildScenes.Concat(explicitRoots).Distinct().OrderBy(x => x, StringComparer.Ordinal).ToArray();
        if (roots.Length == 0) throw new ArgumentException("At least one build scene or explicit root is required.");

        foreach (var scene in buildScenes)
        {
            if (String.IsNullOrWhiteSpace(scene) || !scene.StartsWith("Assets/", StringComparison.Ordinal) || scene.Contains("\\") || scene.Split('/').Any(x => x == ".." || x == "." || x == ""))
                throw new ArgumentException("Build scenes must be normalized project-relative Assets paths: " + scene);
            if (AssetDatabase.LoadAssetAtPath<SceneAsset>(scene) == null)
                throw new InvalidOperationException("Enabled build scene is missing or not imported as SceneAsset: " + scene);
        }
        foreach (var root in explicitRoots)
            if (String.IsNullOrWhiteSpace(root) || !root.StartsWith("Assets/", StringComparison.Ordinal) || root.Contains("\\") || root.Split('/').Any(x => x == ".." || x == "." || x == ""))
                throw new ArgumentException("Explicit roots must be normalized project-relative Assets paths: " + root);

        var allPaths = AssetDatabase.GetAllAssetPaths()
            .Where(p => p.StartsWith("Assets/", StringComparison.Ordinal) && !AssetDatabase.IsValidFolder(p)
                && !p.Equals("Assets/BeaverReadbackTools", StringComparison.Ordinal)
                && !p.StartsWith("Assets/BeaverReadbackTools/", StringComparison.Ordinal))
            .Distinct().OrderBy(p => p, StringComparer.Ordinal).ToArray();
        var assets = new List<AssetRecord>();
        var blockers = new List<string>();
        foreach (var path in allPaths)
        {
            UnityEngine.Object[] objects = Array.Empty<UnityEngine.Object>();
            var ids = new SortedSet<long>();
            var types = new SortedSet<string>(StringComparer.Ordinal);
            var objectIdentities = new Dictionary<string, ObjectIdentity>(StringComparer.Ordinal);
            var errors = new List<string>();
            var guid = AssetDatabase.AssetPathToGUID(path);
            if (String.IsNullOrEmpty(guid)) errors.Add("AssetDatabase path GUID is unavailable.");
            var objectCount = -1;
            var identityStatus = "inspection-failed";
            try
            {
                objects = PersistentObjects(path);
                objectCount = objects.Length;
                identityStatus = objectCount == 0 ? "no-persistent-object" : "verified";
            }
            catch (Exception error) { errors.Add("AssetDatabase object inspection failed: " + error.Message); }
            if (objectCount == 0) errors.Add("AssetDatabase returned zero objects from main asset and subassets.");
            if (String.IsNullOrEmpty(guid)) errors.Add("AssetDatabase path GUID is unavailable.");
            foreach (var obj in objects)
            {
                types.Add(obj.GetType().FullName);
                if (includeObjectIdentities && !EditorUtility.IsPersistent(obj))
                {
                    errors.Add("Object is not persistent on disk: " + obj.GetType().FullName + ".");
                    identityStatus = "persistent-identity-unavailable";
                    continue;
                }
                string objectGuid; long localId;
                if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(obj, out objectGuid, out localId) || String.IsNullOrEmpty(objectGuid) || localId == 0)
                {
                    errors.Add("Persistent GUID/localID unavailable for " + obj.GetType().FullName + ".");
                    identityStatus = "persistent-identity-unavailable";
                    continue;
                }
                if (!String.IsNullOrEmpty(guid) && !String.Equals(objectGuid, guid, StringComparison.OrdinalIgnoreCase))
                {
                    errors.Add("Object GUID differs from AssetDatabase path GUID for " + obj.GetType().FullName + ".");
                    identityStatus = "persistent-identity-unavailable";
                    continue;
                }
                ids.Add(localId);
                if (includeObjectIdentities)
                {
                    string objectName;
                    try
                    {
                        objectName = obj.name;
                        if (objectName == null) throw new InvalidOperationException("Unity object name is null.");
                    }
                    catch (Exception error)
                    {
                        errors.Add("Persistent object name unavailable for " + obj.GetType().FullName + ": " + error.Message);
                        identityStatus = "persistent-identity-unavailable";
                        continue;
                    }
                    var identityGuid = objectGuid.ToLowerInvariant();
                    var key = identityGuid + ":" + localId.ToString(System.Globalization.CultureInfo.InvariantCulture);
                    if (!objectIdentities.ContainsKey(key))
                        objectIdentities.Add(key, new ObjectIdentity { guid = identityGuid, localId = localId,
                            type = obj.GetType().FullName, name = objectName, state = "persistent" });
                }
            }
            if (objectCount > 0 && (String.IsNullOrEmpty(guid) || ids.Count == 0 || errors.Count > 0))
                identityStatus = "persistent-identity-unavailable";
            var status = identityStatus == "verified" && ids.Count > 0 ? "observed" : "unknown";
            if (status == "unknown") blockers.Add("Asset identity incomplete: " + path + " — " + String.Join(" ", errors));
            assets.Add(new AssetRecord { path = path, guid = guid == null ? "" : guid.ToLowerInvariant(), localIds = ids.ToArray(),
                types = types.ToArray(), objects = includeObjectIdentities ? objectIdentities.Values
                    .OrderBy(x => x.guid, StringComparer.Ordinal).ThenBy(x => x.localId).ToArray() : null,
                status = status, identityStatus = identityStatus, objectCount = objectCount,
                error = errors.Count == 0 ? "" : String.Join(" ", errors) });
        }

        var implicitAssets = new List<KeyValuePair<string, string>>();
        foreach (var path in allPaths)
        {
            var parts = path.Split('/');
            if (parts.Skip(1).Take(Math.Max(0, parts.Length - 2)).Contains("Resources", StringComparer.Ordinal))
                implicitAssets.Add(new KeyValuePair<string, string>(path, "implicit:Resources"));
            if (parts.Length >= 3 && parts[1] == "StreamingAssets")
                implicitAssets.Add(new KeyValuePair<string, string>(path, "implicit:StreamingAssets"));
        }
        foreach (var preloaded in PlayerSettings.GetPreloadedAssets().Where(o => o != null))
        {
            var path = AssetDatabase.GetAssetPath(preloaded);
            if (!path.StartsWith("Assets/", StringComparison.Ordinal) || !allPaths.Contains(path, StringComparer.Ordinal))
            {
                blockers.Add("Preloaded asset has no active Assets path: " + preloaded.GetType().FullName + " / " + path);
                continue;
            }
            implicitAssets.Add(new KeyValuePair<string, string>(path, "implicit:PreloadedAssets"));
        }
        var implicitRoots = implicitAssets.Select(x => x.Value).Distinct().OrderBy(x => x, StringComparer.Ordinal).ToArray();
        var dependencyRoots = roots.Select(x => new KeyValuePair<string, string>(x, x)).Concat(implicitAssets)
            .OrderBy(x => x.Value, StringComparer.Ordinal).ThenBy(x => x.Key, StringComparer.Ordinal).ToArray();
        var records = new Dictionary<string, DependencyRecord>(StringComparer.Ordinal);
        var unresolvedRecords = new Dictionary<string, UnresolvedDependencyRecord>(StringComparer.Ordinal);
        foreach (var rootInfo in dependencyRoots)
        {
            var root = rootInfo.Key; var rootLabel = rootInfo.Value;
            var rootImported = true;
            if (!String.IsNullOrEmpty(rootLabel) && !rootLabel.StartsWith("implicit:", StringComparison.Ordinal))
            {
                try { rootImported = allPaths.Contains(root, StringComparer.Ordinal) && AssetDatabase.LoadMainAssetAtPath(root) != null; }
                catch (Exception error)
                {
                    var reason = "AssetDatabase could not inspect explicit root: " + error.Message;
                    blockers.Add("Explicit root unresolved: " + root + " — " + reason);
                    AddUnresolved(unresolvedRecords, root, AssetDatabase.AssetPathToGUID(root), rootLabel, reason);
                    continue;
                }
            }
            if (!rootImported)
            {
                var reason = "Explicit root is absent from the imported asset catalog or has no main imported object.";
                blockers.Add("Explicit root unresolved: " + root + " — " + reason);
                AddUnresolved(unresolvedRecords, root, AssetDatabase.AssetPathToGUID(root), rootLabel, reason);
                continue;
            }
            string[] dependencyPaths;
            try { dependencyPaths = AssetDatabase.GetDependencies(root, true).Distinct().OrderBy(p => p, StringComparer.Ordinal).ToArray(); }
            catch (Exception error)
            {
                var reason = "AssetDatabase dependency scan failed: " + error.Message;
                blockers.Add("Dependency root unresolved: " + root + " — " + reason);
                AddUnresolved(unresolvedRecords, root, AssetDatabase.AssetPathToGUID(root), rootLabel, reason);
                continue;
            }
            foreach (var path in dependencyPaths)
            {
                if (!path.StartsWith("Assets/", StringComparison.Ordinal) || AssetDatabase.IsValidFolder(path)) continue;
                if (!allPaths.Contains(path, StringComparer.Ordinal))
                {
                    var reason = "Dependency path is missing from the active AssetDatabase catalog.";
                    blockers.Add("Dependency asset unresolved: " + path + " — " + reason);
                    AddUnresolved(unresolvedRecords, path, AssetDatabase.AssetPathToGUID(path), rootLabel, reason);
                    continue;
                }
                UnityEngine.Object[] objects;
                try { objects = PersistentObjects(path); }
                catch (Exception error)
                {
                    var reason = "Dependency object inspection failed: " + error.Message;
                    blockers.Add("Dependency identity unresolved: " + path + " — " + reason);
                    AddUnresolved(unresolvedRecords, path, AssetDatabase.AssetPathToGUID(path), rootLabel, reason);
                    continue;
                }
                if (objects.Length == 0)
                {
                    var reason = "Dependency has no persistent main asset or subasset object.";
                    blockers.Add("Dependency identity unresolved: " + path + " — " + reason);
                    AddUnresolved(unresolvedRecords, path, AssetDatabase.AssetPathToGUID(path), rootLabel, reason);
                    continue;
                }
                foreach (var obj in objects)
                {
                    string guid; long localId;
                    if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(obj, out guid, out localId) || String.IsNullOrEmpty(guid) || localId == 0)
                    {
                        var reason = "Dependency persistent GUID/localID unavailable for " + obj.GetType().FullName + ".";
                        blockers.Add("Dependency identity unresolved: " + path + " — " + reason);
                        AddUnresolved(unresolvedRecords, path, AssetDatabase.AssetPathToGUID(path), rootLabel, reason);
                        continue;
                    }
                    var key = path + "\n" + localId.ToString(System.Globalization.CultureInfo.InvariantCulture);
                    DependencyRecord record;
                    if (!records.TryGetValue(key, out record))
                    {
                        record = new DependencyRecord { path = path, guid = guid.ToLowerInvariant(), localId = localId,
                            type = obj.GetType().FullName, roots = Array.Empty<string>() };
                        records.Add(key, record);
                    }
                    if (!record.roots.Contains(rootLabel)) record.roots = record.roots.Concat(new[] { rootLabel }).OrderBy(x => x, StringComparer.Ordinal).ToArray();
                }
            }
        }

        return new Snapshot { target = target, pipeline = pipeline, buildScenes = buildScenes, explicitRoots = explicitRoots,
            implicitRoots = implicitRoots, coverage = new Coverage { complete = blockers.Count == 0, blockers = blockers.OrderBy(x => x, StringComparer.Ordinal).ToArray() },
            assets = assets.ToArray(), dependencies = records.Values.OrderBy(x => x.path, StringComparer.Ordinal).ThenBy(x => x.localId).ToArray(),
            unresolvedDependencies = unresolvedRecords.Values.OrderBy(x => x.path, StringComparer.Ordinal).ToArray() };
    }

    public static void Run()
    {
        Job job = null;
        string reportPath = null;
        try
        {
            var encoded = Environment.GetEnvironmentVariable("BEAVER_NATIVE_JOB_BASE64");
            if (String.IsNullOrEmpty(encoded)) throw new InvalidOperationException("BEAVER_NATIVE_JOB_BASE64 is missing.");
            var jobPath = new UTF8Encoding(false, true).GetString(Convert.FromBase64String(encoded));
            var raw = File.ReadAllText(jobPath, new UTF8Encoding(false, true));
            job = JsonUtility.FromJson<Job>(raw);
            if (job == null || String.IsNullOrWhiteSpace(job.projectRoot) || String.IsNullOrWhiteSpace(job.stage) ||
                String.IsNullOrWhiteSpace(job.reportName) || Path.GetFileName(job.reportName) != job.reportName ||
                !job.reportName.EndsWith(".json", StringComparison.Ordinal))
                throw new InvalidOperationException("Build filter job identity or report path is invalid.");
            var editorProjectRoot = Directory.GetParent(Application.dataPath).FullName.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            var requestedProjectRoot = Path.GetFullPath(job.projectRoot).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            if (!String.Equals(requestedProjectRoot, editorProjectRoot, StringComparison.Ordinal))
                throw new InvalidOperationException("Build filter job targets a different project root.");
            reportPath = Path.Combine(Path.GetFullPath(job.stage), job.reportName);
            Directory.CreateDirectory(Path.GetDirectoryName(reportPath));
            var snapshot = Collect(job.platform, job.renderPipeline, job.assets, job.roots, job.includeObjectIdentities);
            File.WriteAllText(reportPath, SerializeSnapshot(snapshot, job.includeObjectIdentities), new UTF8Encoding(false));
            EditorApplication.Exit(0);
        }
        catch (Exception error)
        {
            if (job != null && !String.IsNullOrWhiteSpace(job.stage) && !String.IsNullOrWhiteSpace(job.reportName) && Path.GetFileName(job.reportName) == job.reportName)
            {
                try
                {
                    var failurePath = Path.Combine(Path.GetFullPath(job.stage), job.reportName);
                    Directory.CreateDirectory(Path.GetDirectoryName(failurePath));
                    File.WriteAllText(failurePath, JsonUtility.ToJson(new FailedReport { status = "failed", error = error.ToString() }, true), new UTF8Encoding(false));
                }
                catch { /* Preserve the original Editor failure. */ }
            }
            UnityEngine.Debug.LogException(error);
            EditorApplication.Exit(1);
        }
    }

    private static string SerializeSnapshot(Snapshot snapshot, bool includeObjectIdentities)
    {
        var json = JsonUtility.ToJson(snapshot, true);
        if (includeObjectIdentities) return json;
        // Unity's JsonUtility emits null public array fields. Keep the historical
        // schema byte shape by removing only this new opt-in field when disabled.
        return Regex.Replace(json, @"(?m)^\s*""objects"": (?:null|\[\]),\r?\n", String.Empty);
    }
}
