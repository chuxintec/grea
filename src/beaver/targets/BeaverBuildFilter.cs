// Read-only Unity Editor dependency snapshot for beaver build filtering.
// The owning native runner is responsible for invoking this collector and
// writing the returned schemaVersion=1 snapshot as UTF-8 JSON.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
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

    public static Snapshot Collect(string target, string pipeline, string[] buildScenes, string[] explicitRoots)
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

        foreach (var root in roots)
        {
            if (String.IsNullOrWhiteSpace(root) || !root.StartsWith("Assets/", StringComparison.Ordinal) || root.Contains("\\") || root.Split('/').Any(x => x == ".." || x == "." || x == ""))
                throw new ArgumentException("Roots must be normalized project-relative Assets paths: " + root);
            if (AssetDatabase.LoadMainAssetAtPath(root) == null)
                throw new InvalidOperationException("Build dependency root is missing or not an asset: " + root);
        }

        var allPaths = AssetDatabase.GetAllAssetPaths()
            .Where(p => p.StartsWith("Assets/", StringComparison.Ordinal) && !AssetDatabase.IsValidFolder(p)
                && !p.Equals("Assets/BeaverReadbackTools", StringComparison.Ordinal)
                && !p.StartsWith("Assets/BeaverReadbackTools/", StringComparison.Ordinal))
            .Distinct().OrderBy(p => p, StringComparer.Ordinal).ToArray();
        var assets = new List<AssetRecord>();
        foreach (var path in allPaths)
        {
            var objects = PersistentObjects(path);
            var ids = new SortedSet<long>();
            var types = new SortedSet<string>(StringComparer.Ordinal);
            foreach (var obj in objects)
            {
                string objectGuid; long localId;
                if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(obj, out objectGuid, out localId) || String.IsNullOrEmpty(objectGuid) || localId == 0)
                    throw new InvalidOperationException("Persistent GUID/localID unavailable: " + path + " / " + obj.GetType().FullName);
                ids.Add(localId); types.Add(obj.GetType().FullName);
            }
            var guid = AssetDatabase.AssetPathToGUID(path);
            if (String.IsNullOrEmpty(guid) || ids.Count == 0)
                throw new InvalidOperationException("Asset has no persistent identity: " + path);
            assets.Add(new AssetRecord { path = path, guid = guid.ToLowerInvariant(), localIds = ids.ToArray(), types = types.ToArray() });
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
        var blockers = new List<string>();
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
        foreach (var rootInfo in dependencyRoots)
        {
            var root = rootInfo.Key; var rootLabel = rootInfo.Value;
            foreach (var path in AssetDatabase.GetDependencies(root, true).Distinct().OrderBy(p => p, StringComparer.Ordinal))
            {
                if (!path.StartsWith("Assets/", StringComparison.Ordinal) || AssetDatabase.IsValidFolder(path)) continue;
                foreach (var obj in PersistentObjects(path))
                {
                    string guid; long localId;
                    if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(obj, out guid, out localId) || String.IsNullOrEmpty(guid) || localId == 0)
                        throw new InvalidOperationException("Dependency lacks persistent identity: " + path + " / " + obj.GetType().FullName);
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
            assets = assets.ToArray(), dependencies = records.Values.OrderBy(x => x.path, StringComparer.Ordinal).ThenBy(x => x.localId).ToArray() };
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
            var snapshot = Collect(job.platform, job.renderPipeline, job.assets, job.roots);
            File.WriteAllText(reportPath, JsonUtility.ToJson(snapshot, true), new UTF8Encoding(false));
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
}
