// Derived from monkey, MIT license retained in licenses/MONKEY-MIT.txt.
// MIT License. Native asset moves/imports for monkey's reviewed adoption plans.
#if UNITY_EDITOR
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Reflection;
using System.Security.Cryptography;
using UnityEditor;
using UnityEngine;

public static class BeaverAdoption {
    static string JobPath() {
        var encoded=Environment.GetEnvironmentVariable("BEAVER_ADOPT_JOB_BASE64");
        if(String.IsNullOrEmpty(encoded)||encoded.Length>65536)throw new Exception("Explicit ASCII-encoded native job required");
        return new System.Text.UTF8Encoding(false,true).GetString(Convert.FromBase64String(encoded));
    }

    [Serializable] public class Op {
        public string action, source, target, guid;
        public string beforeFileHash, beforeMetaHash, afterFileHash, afterMetaHash;
        public bool preserveLocalIds, compileStage;
    }
    [Serializable] public class Job {
        public string targetRoot, stage, mode, deadlineUtc, planSha256;
        public int budgetSeconds;
        public Op[] operations;
        public string[] watch;
        public bool codeRestored, sdkMigrationEnabled;
        public SdkMigration sdkMigration;
    }
    [Serializable] public class SdkMigration {
        public string path, sha256, candidateManifestSha256, targetAssetsSha256, referenceCoverage;
        public SdkLicense[] licenses;
        public SdkPair[] assemblies;
        public SdkReference[] references;
        public SdkRetainedInactiveBlock retainedInactiveAssemblies;
    }
    [Serializable] public class SdkRetainedInactiveBlock { public string policy; public SdkRetainedInactiveImage[] assemblies; }
    [Serializable] public class SdkRetainedInactiveImage {
        public string path,guid,sha256,metaSha256,assemblyName,moduleVersionId,canonicalEditorPath;
        public string[] roles;
    }
    [Serializable] public class SdkLicense { public string id, root, path, sha256; }
    [Serializable] public class SdkPair { public string role, assemblyName, licenseId, monoScriptPolicy; public SdkVariant[] variants; }
    [Serializable] public class SdkVariant {
        public string domain, action, path, name;
        public SdkImage after, before;
        public string[] publicTypes;
    }
    [Serializable] public class SdkImage {
        public string guid, sha256, metaSha256, moduleVersionId;
        public int[] version;
        public string[] roles, metadataTypes;
    }
    [Serializable] public class SdkMonoScript { public string type, moduleVersionId; public long localId; }
    [Serializable] public class SdkReference {
        public string root, assetPath, assetSha256, propertyPath, action;
        public long objectLocalId;
        public SdkObjectReference source, canonical;
    }
    [Serializable] public class SdkObjectReference { public string guid, type; public long localId; }
    [Serializable] public class Entry {
        public int index;
        public string path, guid;
        public string[] localIds;
    }
    [Serializable] public class Progress {
        public string status, mode, planSha256, error;
        public List<int> written=new List<int>();
        public List<int> restored=new List<int>();
        public List<Entry> assets=new List<Entry>();
        public List<Entry> beforeAssets=new List<Entry>();
        public List<Entry> createdFolders=new List<Entry>();
        public List<string> retainedFolders=new List<string>();
        public bool referencesPreserved;
        public bool sdkBeforeComplete;
        public bool sdkAssembliesVerified, sdkReferencesVerified;
        public bool sdkInactiveAssembliesVerified;
        public List<string> sdkReferenceMappingsApplied=new List<string>();
        public List<SdkScriptSnapshot> sdkBeforeMonoScripts=new List<SdkScriptSnapshot>();
        public List<SdkScriptSnapshot> sdkAfterMonoScripts=new List<SdkScriptSnapshot>();
        public List<SdkRetainedInactiveSnapshot> sdkBeforeInactiveAssemblies=new List<SdkRetainedInactiveSnapshot>();
        public List<SdkRetainedInactiveSnapshot> sdkAfterInactiveAssemblies=new List<SdkRetainedInactiveSnapshot>();
        public List<Observed> observedAfter=new List<Observed>();
    }
    [Serializable] public class Observed { public int index; public string path,fileHash,metaHash; }
    [Serializable] public class SdkScriptSnapshot {
        public string path,guid,assemblyName,expectedEditorModuleVersionId,loadedModuleVersionId,moduleLoadStatus;
        public string evidenceClass,evidenceSourcePath,evidenceSourceSha256,evidenceSourceModuleVersionId,evidenceSourceTupleSha256;
        public string[] roles; public SdkMonoScript[] scripts;
    }
    [Serializable] public class SdkRetainedInactiveSnapshot {
        public string path,guid,sha256,metaSha256,assemblyName,moduleVersionId,canonicalEditorPath,selectedEditorPrecompiledPath,runtimeLoadedModuleVersionId,runtimeLoadedLocation,runtimeSourceEvidence;
        public string[] roles;
        public int monoScriptCount;
        public bool allPlatformsDisabled,runtimeLoadedFromInactivePath,canonicalEditorSourceSelected,inactiveSourceExcluded;
    }
    static Job job;
    static Progress report;
    static DateTime deadline;
    static string root;
    static readonly Dictionary<string,string[]> originalIds=new Dictionary<string,string[]>();
    static readonly Dictionary<int,string> mappedReadbackHashes=new Dictionary<int,string>();
    static void Checkpoint() { if(DateTime.UtcNow>=deadline) throw new Exception("ADOPT_DEADLINE"); }
    static string Full(string relative) {
        if(String.IsNullOrEmpty(relative) || !relative.StartsWith("Assets/",StringComparison.Ordinal) || relative.Contains("\\") || relative.Split('/').Any(p=>p==".."||p=="."||p=="")) throw new Exception("Unsafe asset path");
        var path=Path.GetFullPath(Path.Combine(root,relative));
        if(!path.StartsWith(root+Path.DirectorySeparatorChar,StringComparison.Ordinal)) throw new Exception("Path escaped project");
        return path;
    }
    static string Hash(string path) {
        if(!File.Exists(path))return null;
        using(var input=File.OpenRead(path))using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(input)).Replace("-","").ToLowerInvariant();
    }
    static string HashText(string value) {
        using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(new System.Text.UTF8Encoding(false,true).GetBytes(value))).Replace("-","").ToLowerInvariant();
    }
    static void Expected(string relative,string hash) {
        Checkpoint();if(Hash(Full(relative))!=hash)throw new Exception("ADOPT_DRIFT "+relative);
    }
    static string FileFor(int index,string side,string kind) { return Path.Combine(job.stage,side,index.ToString(),kind); }
    static void Save() {
        var path=Path.Combine(job.stage,"native-"+job.mode+".json");
        File.WriteAllText(path+".tmp",JsonUtility.ToJson(report,true));
        if(File.Exists(path)) File.Replace(path+".tmp",path,null);
        else File.Move(path+".tmp",path);
    }
    static void Folder(string relative) {
        var parent=Path.GetDirectoryName(relative).Replace('\\','/');
        if(parent=="Assets" || AssetDatabase.IsValidFolder(parent))return;
        Folder(parent);
        var grand=Path.GetDirectoryName(parent).Replace('\\','/');
        var guid=AssetDatabase.CreateFolder(grand,Path.GetFileName(parent));
        if(String.IsNullOrEmpty(guid))throw new Exception("CreateFolder failed "+parent);
        report.createdFolders.Add(new Entry{index=-1,path=parent,guid=guid,localIds=new string[0]});Save();
    }
    static string[] Ids(string relative) {
        return AssetDatabase.LoadAllAssetsAtPath(relative).Concat(new[]{AssetDatabase.LoadMainAssetAtPath(relative)}).Where(a=>a!=null).Distinct().Select(a=>{
            string guid;long id;
            if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(a,out guid,out id))throw new Exception("No local identity "+relative);
            return guid+":"+id+":"+a.GetType().FullName;
        }).OrderBy(v=>v,StringComparer.Ordinal).ToArray();
    }
    static string RefSignature(string path) {
        return String.Join("|",AssetDatabase.GetDependencies(path,false).Select(p=>AssetDatabase.AssetPathToGUID(p)).Where(g=>g!="").OrderBy(g=>g,StringComparer.Ordinal));
    }
    static void WritePayload(int index,string side,string target,string fileHash,string metaHash,bool import=true) {
        var file=FileFor(index,side,"file");var meta=FileFor(index,side,"meta");
        if(Hash(file)!=fileHash || Hash(meta)!=metaHash)throw new Exception("Staged payload changed");
        Folder(target);File.Copy(file,Full(target),true);
        if(metaHash!=null)File.Copy(meta,Full(target+".meta"),true);
        if(import)AssetDatabase.ImportAsset(target,ImportAssetOptions.ForceSynchronousImport|ImportAssetOptions.ForceUpdate);
        if(side=="after") {
            report.observedAfter.RemoveAll(row=>row.index==index);
            report.observedAfter.Add(new Observed{index=index,path=target,fileHash=Hash(Full(target)),metaHash=Hash(Full(target+".meta"))});
            Save();
        }
        Expected(target,fileHash);
        if(metaHash!=null)Expected(target+".meta",metaHash);
    }
    static void VerifyAsset(int index,Op op) {
        string mappedHash;
        Expected(op.target,job.mode=="verify"&&mappedReadbackHashes.TryGetValue(index,out mappedHash)?mappedHash:op.afterFileHash);
        if(op.afterMetaHash!=null)Expected(op.target+".meta",op.afterMetaHash);
        var guid=AssetDatabase.AssetPathToGUID(op.target);
        if(op.guid!=null && guid!=op.guid)throw new Exception("GUID changed "+op.target);
        var ids=Ids(op.target);
        if((op.target.EndsWith(".prefab",StringComparison.OrdinalIgnoreCase)||op.target.EndsWith(".asset",StringComparison.OrdinalIgnoreCase)||op.target.EndsWith(".unity",StringComparison.OrdinalIgnoreCase)) && ids.Length==0)throw new Exception("No persistent adopted asset "+op.target);
        if(op.target.EndsWith(".prefab",StringComparison.OrdinalIgnoreCase)) {
            var prefab=AssetDatabase.LoadAssetAtPath<GameObject>(op.target);
            if(prefab==null || prefab.GetComponentsInChildren<Component>(true).Any(c=>c==null))throw new Exception("Missing adopted prefab script "+op.target);
        }
        if(op.preserveLocalIds && originalIds.ContainsKey(op.target) && !originalIds[op.target].SequenceEqual(ids))throw new Exception("Local IDs changed "+op.target);
        report.assets.Add(new Entry{index=index,path=op.target,guid=guid,localIds=ids});
    }
    static SdkScriptSnapshot CheckSdkImage(SdkVariant variant,SdkImage image,string side,string expectedEditorModuleVersionId) {
        var full=Full(variant.path);var meta=Full(variant.path+".meta");
        // JsonUtility may materialize a default SdkImage for JSON null. The
        // action is the authoritative discriminator for an add before-image.
        if(variant.action=="add"&&side=="before") {
            if(File.Exists(full)||File.Exists(meta))throw new Exception("SDK add before-image destination is occupied "+variant.path);
            return null;
        }
        if(image==null) {
            if(File.Exists(full)||File.Exists(meta))throw new Exception("SDK add destination is occupied "+variant.path);
            return null;
        }
        if(Hash(full)!=image.sha256 || Hash(meta)!=image.metaSha256)throw new Exception("SDK "+side+" byte identity differs "+variant.path);
        if(AssetDatabase.AssetPathToGUID(variant.path)!=image.guid)throw new Exception("SDK "+side+" GUID differs "+variant.path);
        Guid expectedMvid;
        if(!Guid.TryParseExact(image.moduleVersionId,"D",out expectedMvid) || !Guid.TryParseExact(expectedEditorModuleVersionId,"D",out expectedMvid))
            throw new Exception("SDK "+side+" normalized Module MVID is missing/invalid "+variant.path);
        var expectedMvidText=expectedEditorModuleVersionId.ToLowerInvariant();
        if(variant.domain=="editor"&&image.moduleVersionId.ToLowerInvariant()!=expectedMvidText)throw new Exception("SDK Editor image MVID differs from the active binding MVID "+variant.path);
        var loaded=AppDomain.CurrentDomain.GetAssemblies().Where(a=>a.GetName().Name==variant.name).ToArray();
        var loadedMvids=loaded.Select(a=>a.ManifestModule.ModuleVersionId.ToString("D").ToLowerInvariant()).Distinct(StringComparer.Ordinal).ToArray();
        if(loadedMvids.Length>1)throw new Exception("SDK loaded assembly identity is ambiguous "+variant.name);
        var loadedMvid=loadedMvids.FirstOrDefault();
        if(loadedMvid!=null && loadedMvid!=expectedMvidText)throw new Exception("SDK loaded assembly MVID differs "+variant.name+" "+loadedMvid);
        var importer=AssetImporter.GetAtPath(variant.path) as PluginImporter;
        if(importer==null)throw new Exception("SDK PluginImporter missing "+variant.path);
        bool editor=importer.GetCompatibleWithEditor();bool any=importer.GetCompatibleWithAnyPlatform();
        // A player-only role is serialized as Any excluding Editor.
        bool nativeRole=image.roles!=null&&image.roles.Length==1&&image.roles[0]=="native-required";
        if(!nativeRole&&(image.roles==null || image.roles.Length!=1 ||
           image.roles[0]=="editor" && (!editor || any) ||
           image.roles[0]=="player" && (editor || !any || !importer.GetExcludeEditorFromAnyPlatform())))
            throw new Exception("SDK "+side+" importer role differs "+variant.path);
        var actualRoles=new List<string>();if(editor)actualRoles.Add("editor");if(any)actualRoles.Add("player");
        var scripts=AssetDatabase.LoadAllAssetsAtPath(variant.path).OfType<MonoScript>().ToArray();
        var actual=new List<SdkMonoScript>();
        foreach(var script in scripts) {
            var type=script.GetClass();string guid;long local;
            if(type==null || !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(script,out guid,out local))throw new Exception("SDK MonoScript class/localID unresolved "+variant.path);
            if(guid!=image.guid)throw new Exception("SDK MonoScript asset GUID differs "+variant.path);
            var scriptMvid=type.Assembly.ManifestModule.ModuleVersionId.ToString("D").ToLowerInvariant();
            if(scriptMvid!=expectedMvidText)throw new Exception("SDK MonoScript resolved through another loaded module MVID "+type.FullName+" "+scriptMvid);
            actual.Add(new SdkMonoScript{type=type.FullName,localId=local,moduleVersionId=scriptMvid});
            if(!(image.metadataTypes??new string[0]).Contains(type.FullName))throw new Exception("SDK MonoScript type is absent from the exact managed metadata inventory "+type.FullName);
            if(type.Assembly.GetName().Name!=variant.name)throw new Exception("SDK MonoScript assembly name differs "+type.FullName);
        }
        Func<SdkMonoScript,string> key=x=>x.type+"\0"+x.localId.ToString(System.Globalization.CultureInfo.InvariantCulture);
        actual=actual.OrderBy(key,StringComparer.Ordinal).ToList();
        return new SdkScriptSnapshot{path=variant.path,guid=image.guid,assemblyName=variant.name,roles=actualRoles.ToArray(),scripts=actual.ToArray(),expectedEditorModuleVersionId=expectedMvidText,loadedModuleVersionId=loadedMvid,moduleLoadStatus=loadedMvid==null?"notObserved":"verified"};
    }
    static string SdkScriptKey(SdkMonoScript x) { return x.type+"\0"+x.localId.ToString(System.Globalization.CultureInfo.InvariantCulture); }
    static bool SameOptionalText(string left,string right) {
        return (String.IsNullOrEmpty(left)&&String.IsNullOrEmpty(right))||String.Equals(left,right,StringComparison.Ordinal);
    }
    static bool SameSdkSnapshot(SdkScriptSnapshot left,SdkScriptSnapshot right,bool compareRoles=false) {
        return left!=null&&right!=null&&left.path==right.path&&left.guid==right.guid&&left.assemblyName==right.assemblyName&&
               left.expectedEditorModuleVersionId==right.expectedEditorModuleVersionId&&SameOptionalText(left.loadedModuleVersionId,right.loadedModuleVersionId)&&left.moduleLoadStatus==right.moduleLoadStatus&&
               SameOptionalText(left.evidenceClass,right.evidenceClass)&&SameOptionalText(left.evidenceSourcePath,right.evidenceSourcePath)&&SameOptionalText(left.evidenceSourceSha256,right.evidenceSourceSha256)&&SameOptionalText(left.evidenceSourceModuleVersionId,right.evidenceSourceModuleVersionId)&&SameOptionalText(left.evidenceSourceTupleSha256,right.evidenceSourceTupleSha256)&&
               (!compareRoles||(left.roles??new string[0]).SequenceEqual(right.roles??new string[0]))&&
               (left.scripts??new SdkMonoScript[0]).Select(x=>SdkScriptKey(x)+"\0"+x.moduleVersionId).SequenceEqual((right.scripts??new SdkMonoScript[0]).Select(x=>SdkScriptKey(x)+"\0"+x.moduleVersionId));
    }
    static bool SameSdkBindings(SdkScriptSnapshot left,SdkScriptSnapshot right) {
        return left!=null&&right!=null&&left.path==right.path&&left.guid==right.guid&&left.assemblyName==right.assemblyName&&
               (left.scripts??new SdkMonoScript[0]).Select(SdkScriptKey).SequenceEqual((right.scripts??new SdkMonoScript[0]).Select(SdkScriptKey));
    }
    static bool SameSdkRollbackSnapshot(SdkScriptSnapshot old,SdkScriptSnapshot current) {
        if(!SameSdkBindings(old,current)||old.expectedEditorModuleVersionId!=current.expectedEditorModuleVersionId||
           !SameOptionalText(old.evidenceClass,current.evidenceClass)||!SameOptionalText(old.evidenceSourcePath,current.evidenceSourcePath)||!SameOptionalText(old.evidenceSourceSha256,current.evidenceSourceSha256)||!SameOptionalText(old.evidenceSourceModuleVersionId,current.evidenceSourceModuleVersionId)||!SameOptionalText(old.evidenceSourceTupleSha256,current.evidenceSourceTupleSha256)||
           (old.roles??new string[0]).Length!=(current.roles??new string[0]).Length||!(old.roles??new string[0]).SequenceEqual(current.roles??new string[0]))return false;
        var before=old.scripts??new SdkMonoScript[0];var now=current.scripts??new SdkMonoScript[0];
        if(!before.Select(x=>x.moduleVersionId).SequenceEqual(now.Select(x=>x.moduleVersionId)))return false;
        return String.IsNullOrEmpty(old.loadedModuleVersionId)||SameOptionalText(old.loadedModuleVersionId,current.loadedModuleVersionId);
    }
    static bool SameRetainedInactiveSnapshot(SdkRetainedInactiveSnapshot left,SdkRetainedInactiveSnapshot right) {
        return left!=null&&right!=null&&left.path==right.path&&left.guid==right.guid&&left.sha256==right.sha256&&left.metaSha256==right.metaSha256&&
               left.assemblyName==right.assemblyName&&left.moduleVersionId==right.moduleVersionId&&left.canonicalEditorPath==right.canonicalEditorPath&&left.selectedEditorPrecompiledPath==right.selectedEditorPrecompiledPath&&
               SameOptionalText(left.runtimeLoadedModuleVersionId,right.runtimeLoadedModuleVersionId)&&SameOptionalText(left.runtimeLoadedLocation,right.runtimeLoadedLocation)&&left.runtimeSourceEvidence==right.runtimeSourceEvidence&&
               left.canonicalEditorSourceSelected&&right.canonicalEditorSourceSelected&&left.inactiveSourceExcluded&&right.inactiveSourceExcluded&&left.monoScriptCount==right.monoScriptCount&&
               left.allPlatformsDisabled&&right.allPlatformsDisabled&&!left.runtimeLoadedFromInactivePath&&!right.runtimeLoadedFromInactivePath&&
               (left.roles??new string[0]).SequenceEqual(right.roles??new string[0]);
    }
    static string FullReferencePath(string path) {
        if(String.IsNullOrEmpty(path))throw new Exception("CompilationPipeline returned an empty precompiled reference path");
        return Path.GetFullPath(Path.IsPathRooted(path)?path:Path.Combine(root,path)).TrimEnd(Path.DirectorySeparatorChar);
    }
    static void CheckSdkInactiveAssemblies(bool after) {
        if(!SdkEnabled()||job.sdkMigration==null||job.sdkMigration.retainedInactiveAssemblies==null)return;
        var block=job.sdkMigration.retainedInactiveAssemblies;
        if(block.policy!="preserve-exact-disabled-target-assemblies"||block.assemblies==null||block.assemblies.Length==0)
            throw new Exception("Unsupported retained inactive SDK policy");
        if((job.operations??new Op[0]).Any(op=>block.assemblies.Any(row=>op.source==row.path||op.target==row.path)))
            throw new Exception("Retained inactive SDK DLL is in the native write set");
        var snapshots=after?report.sdkAfterInactiveAssemblies:report.sdkBeforeInactiveAssemblies;
        snapshots.Clear();
        var precompiled=UnityEditor.Compilation.CompilationPipeline.GetPrecompiledAssemblyPaths(UnityEditor.Compilation.CompilationPipeline.PrecompiledAssemblySources.UserAssembly)
            .Select(FullReferencePath).ToArray();
        foreach(var row in block.assemblies) {
            if((row.roles??new string[0]).Length!=0)throw new Exception("Retained inactive SDK role declaration must be empty "+row.path);
            var full=Full(row.path);var meta=Full(row.path+".meta");
            if(Hash(full)!=row.sha256||Hash(meta)!=row.metaSha256)throw new Exception("Retained inactive SDK before/meta hash changed "+row.path);
            if(AssetDatabase.AssetPathToGUID(row.path)!=row.guid)throw new Exception("Retained inactive SDK GUID changed "+row.path);
            var importer=AssetImporter.GetAtPath(row.path) as PluginImporter;
            if(importer==null||importer.GetCompatibleWithEditor()||importer.GetCompatibleWithAnyPlatform())throw new Exception("Retained inactive SDK is active for Editor/Any platform "+row.path);
            foreach(BuildTarget target in Enum.GetValues(typeof(BuildTarget)))if(importer.GetCompatibleWithPlatform(target))
                throw new Exception("Retained inactive SDK is enabled for BuildTarget "+target+" at "+row.path);
            if(AssetDatabase.LoadAllAssetsAtPath(row.path).OfType<MonoScript>().Any())throw new Exception("Retained inactive SDK exposes MonoScripts "+row.path);
            var editorVariant=(job.sdkMigration.assemblies??new SdkPair[0]).SelectMany(pair=>pair.variants??new SdkVariant[0])
                .SingleOrDefault(variant=>variant.domain=="editor"&&variant.path==row.canonicalEditorPath);
            if(editorVariant==null||editorVariant.after==null||editorVariant.before==null||editorVariant.after.sha256!=row.sha256||
               editorVariant.after.moduleVersionId!=row.moduleVersionId||editorVariant.after.guid==row.guid)
                throw new Exception("Retained inactive SDK lacks a distinct byte-identical canonical Editor source pair "+row.path);
            var editorImage=after?editorVariant.after:editorVariant.before;
            if(Hash(Full(editorVariant.path))!=editorImage.sha256||Hash(Full(editorVariant.path+".meta"))!=editorImage.metaSha256||AssetDatabase.AssetPathToGUID(editorVariant.path)!=editorImage.guid)
                throw new Exception("Canonical Editor source differs from its phase-bound image "+editorVariant.path);
            var canonicalEditorPath=Path.GetFullPath(Full(editorVariant.path)).TrimEnd(Path.DirectorySeparatorChar);
            var inactivePath=Path.GetFullPath(full).TrimEnd(Path.DirectorySeparatorChar);
            var matchingPrecompiled=new List<string>();
            foreach(var precompiledPath in precompiled) {
                string managedName;
                try { managedName=AssemblyName.GetAssemblyName(precompiledPath).Name; }
                catch(Exception error) { throw new Exception("Cannot identify a selected Editor precompiled reference "+precompiledPath,error); }
                if(String.Equals(managedName,row.assemblyName,StringComparison.OrdinalIgnoreCase))matchingPrecompiled.Add(precompiledPath);
            }
            bool canonicalSelected=matchingPrecompiled.Count==1&&matchingPrecompiled[0].Equals(canonicalEditorPath,StringComparison.OrdinalIgnoreCase);
            bool inactiveExcluded=!precompiled.Any(path=>path.Equals(inactivePath,StringComparison.OrdinalIgnoreCase));
            if(!canonicalSelected||!inactiveExcluded)throw new Exception("CompilationPipeline cannot uniquely prove canonical Editor selection over inactive duplicate "+row.path);
            var fullNormalized=Path.GetFullPath(full);
            bool loadedFromPath=false;
            var loadedAssemblies=AppDomain.CurrentDomain.GetAssemblies().Where(a=>a.GetName().Name==row.assemblyName).ToArray();
            var loadedMvids=loadedAssemblies.Select(a=>a.ManifestModule.ModuleVersionId.ToString("D").ToLowerInvariant()).Distinct(StringComparer.Ordinal).ToArray();
            if(loadedMvids.Length>1)throw new Exception("Retained inactive SDK runtime assembly MVID is ambiguous "+row.assemblyName);
            if(loadedAssemblies.Length>1)throw new Exception("Retained inactive SDK runtime assembly location is ambiguous "+row.assemblyName);
            var loadedMvid=loadedMvids.FirstOrDefault();
            if(editorImage==null)throw new Exception("Retained inactive SDK has no active Editor image for this phase "+row.path);
            if(loadedMvid!=null&&loadedMvid!=editorImage.moduleVersionId)throw new Exception("Loaded same-name SDK MVID differs from the phase Editor image "+row.assemblyName);
            string loadedLocation=null;
            foreach(var assembly in loadedAssemblies) {
                if(assembly.IsDynamic)throw new Exception("Retained inactive SDK runtime assembly has no source location "+row.assemblyName);
                string location;
                try { location=assembly.Location; }
                catch(Exception error) { throw new Exception("Cannot verify retained inactive SDK runtime load location "+row.assemblyName,error); }
                if(String.IsNullOrEmpty(location))throw new Exception("Retained inactive SDK runtime assembly has no verifiable location "+row.assemblyName);
                loadedLocation=Path.GetFullPath(location);
                if(loadedLocation.Equals(fullNormalized,StringComparison.OrdinalIgnoreCase))loadedFromPath=true;
            }
            if(loadedFromPath)throw new Exception("Retained inactive SDK assembly was loaded from its disabled path "+row.path);
            var snapshot=new SdkRetainedInactiveSnapshot{path=row.path,guid=row.guid,sha256=row.sha256,metaSha256=row.metaSha256,
                assemblyName=row.assemblyName,moduleVersionId=row.moduleVersionId,canonicalEditorPath=editorVariant.path,runtimeLoadedModuleVersionId=loadedMvid,
                selectedEditorPrecompiledPath=canonicalSelected?matchingPrecompiled[0]:null,runtimeLoadedLocation=loadedLocation,
                runtimeSourceEvidence="CompilationPipeline.UserAssembly-precompiled-paths+AssemblyName",roles=new string[0],monoScriptCount=0,
                allPlatformsDisabled=true,runtimeLoadedFromInactivePath=false,canonicalEditorSourceSelected=canonicalSelected,inactiveSourceExcluded=inactiveExcluded};
            snapshots.Add(snapshot);Save();
        }
        report.sdkInactiveAssembliesVerified=snapshots.Count==block.assemblies.Length&&snapshots.All(x=>x.allPlatformsDisabled&&!x.runtimeLoadedFromInactivePath&&x.monoScriptCount==0);
        Save();
        if(!report.sdkInactiveAssembliesVerified)throw new Exception("Retained inactive SDK verification is incomplete");
        if(after&&(job.mode=="verify"||job.mode=="apply")) {
            Progress applyReport=null;
            if(job.mode=="verify") {
                applyReport=JsonUtility.FromJson<Progress>(File.ReadAllText(Path.Combine(job.stage,"native-apply.json")));
                report.sdkBeforeInactiveAssemblies=applyReport.sdkBeforeInactiveAssemblies;
            }
            var prior=job.mode=="verify"?applyReport.sdkAfterInactiveAssemblies:report.sdkBeforeInactiveAssemblies;
            var expected=(prior??new List<SdkRetainedInactiveSnapshot>()).OrderBy(x=>x.path,StringComparer.Ordinal).ToArray();
            var observed=snapshots.OrderBy(x=>x.path,StringComparer.Ordinal).ToArray();
            if(expected.Length!=observed.Length)throw new Exception("Retained inactive SDK checkpoint count differs");
            for(int i=0;i<expected.Length;i++)if(!SameRetainedInactiveSnapshot(expected[i],observed[i]))throw new Exception("Retained inactive SDK checkpoint differs "+observed[i].path);
        }
    }
    static string[] LoadedModuleVersionIds(string assemblyName) {
        return AppDomain.CurrentDomain.GetAssemblies().Where(a=>a.GetName().Name==assemblyName)
            .Select(a=>a.ManifestModule.ModuleVersionId.ToString("D").ToLowerInvariant()).Distinct(StringComparer.Ordinal).ToArray();
    }
    static void ConfirmSdkModuleBindings(bool after) {
        if(!SdkEnabled())return;
        if(job.sdkMigration==null)throw new Exception("SDK migration is enabled but its frozen spec is missing");
        var snapshots=after?report.sdkAfterMonoScripts:report.sdkBeforeMonoScripts;
        foreach(var pair in job.sdkMigration.assemblies??new SdkPair[0]) {
            var editor=(pair.variants??new SdkVariant[0]).SingleOrDefault(x=>x.domain=="editor");
            var editorImage=editor==null?null:(after?editor.after:editor.before);
            if(editorImage==null)continue;
            var expected=editorImage.moduleVersionId.ToLowerInvariant();var observed=LoadedModuleVersionIds(pair.assemblyName);
            if(observed.Length>1)throw new Exception("SDK loaded assembly MVID is ambiguous "+pair.assemblyName);
            var loaded=observed.FirstOrDefault();
            if(loaded!=null&&loaded!=expected)throw new Exception("SDK loaded assembly MVID differs from the fixed Editor DLL "+pair.assemblyName+" "+loaded);
            foreach(var snapshot in snapshots.Where(x=>x.assemblyName==pair.assemblyName)) {
                snapshot.expectedEditorModuleVersionId=expected;snapshot.loadedModuleVersionId=loaded;
                snapshot.moduleLoadStatus=loaded==null?"notObserved":"verified";
            }
        }
        report.sdkAssembliesVerified=snapshots.Count>0&&snapshots.All(x=>x.moduleLoadStatus=="verified");Save();
        if(after&&!report.sdkAssembliesVerified)throw new Exception("SDK assembly MVID binding was not observed for every migration pair");
    }
    static bool SdkEnabled() { return job!=null&&job.sdkMigrationEnabled; }
    static void CheckSdkAssemblies(bool after) {
        if(!SdkEnabled())return;
        if(job.sdkMigration==null)throw new Exception("SDK migration is enabled but its frozen spec is missing");
        CheckSdkInactiveAssemblies(after);
        if((job.sdkMigration.assemblies??new SdkPair[0]).Any(pair=>pair.monoScriptPolicy!="capture-before-preserve-and-pair-localids"&&pair.monoScriptPolicy!="capture-before-preserve-and-attest-inactive-player"))throw new Exception("Unsupported SDK MonoScript evidence policy");
        var previous=new Dictionary<string,SdkScriptSnapshot>();
        if(after) {
            var before=report.sdkBeforeMonoScripts;
            if(job.mode=="verify") {
                var applyBefore=JsonUtility.FromJson<Progress>(File.ReadAllText(Path.Combine(job.stage,"native-apply.json")));
                before=applyBefore.sdkBeforeMonoScripts;report.sdkBeforeComplete=applyBefore.sdkBeforeComplete;
            }
            if(before!=null)report.sdkBeforeMonoScripts=before;
            previous=(before??new List<SdkScriptSnapshot>()).ToDictionary(x=>x.path,StringComparer.Ordinal);
        }
        var observedAll=new Dictionary<string,SdkScriptSnapshot>();
        foreach(var pair in job.sdkMigration.assemblies ?? new SdkPair[0]) {
            var editorVariant=(pair.variants??new SdkVariant[0]).SingleOrDefault(x=>x.domain=="editor");
            if(editorVariant==null)throw new Exception("SDK pair has no unique Editor variant "+pair.role);
            var editorImage=after?editorVariant.after:editorVariant.before;
            var expectedEditorMvid=editorImage==null?null:editorImage.moduleVersionId;
            var pairObserved=new List<SdkScriptSnapshot>();
            foreach(var variant in pair.variants ?? new SdkVariant[0]) {
                var snapshot=CheckSdkImage(variant,after?variant.after:variant.before,after?"after":"before",expectedEditorMvid);
                if(snapshot!=null) {
                    pairObserved.Add(snapshot);observedAll[snapshot.path]=snapshot;
                    if(!after){report.sdkBeforeMonoScripts.Add(snapshot);Save();}
                    else {
                        report.sdkAfterMonoScripts=observedAll.Values.OrderBy(x=>x.path,StringComparer.Ordinal).ToList();Save();
                        SdkScriptSnapshot old;
                        if(previous.TryGetValue(snapshot.path,out old)) {
                            if(!SameSdkBindings(old,snapshot))throw new Exception("SDK canonical MonoScript GUID/localID/type changed "+variant.path);
                        }
                    }
                }
            }
            if(after && pairObserved.Count!=2)throw new Exception("SDK Editor/Player MonoScript pair is incomplete "+pair.role);
            if(after) {
                var editorAfter=pairObserved.Single(x=>x.path==editorVariant.path);
                var playerVariant=(pair.variants??new SdkVariant[0]).Single(x=>x.domain=="player");
                var playerAfter=pairObserved.Single(x=>x.path==playerVariant.path);
                var left=editorAfter.scripts.Select(SdkScriptKey).ToArray();var right=playerAfter.scripts.Select(SdkScriptKey).ToArray();
                if(pair.monoScriptPolicy=="capture-before-preserve-and-pair-localids") {
                    if(!right.SequenceEqual(left))throw new Exception("SDK Editor/Player MonoScript localIDs/types differ "+pair.role);
                } else {
                    if(!report.sdkBeforeComplete)throw new Exception("Inactive Player evidence requires a complete native before snapshot "+pair.role);
                    var editorBefore=editorVariant.before;
                    if(editorBefore==null||playerVariant.after.sha256!=editorBefore.sha256||playerVariant.after.moduleVersionId!=editorBefore.moduleVersionId)
                        throw new Exception("Inactive Player bytes/MVID do not exactly match the canonical Editor before-image "+pair.role);
                    SdkScriptSnapshot sourceBefore;
                    if(!previous.TryGetValue(editorVariant.path,out sourceBefore)||sourceBefore.guid!=editorBefore.guid)
                        throw new Exception("Inactive Player source has no complete canonical native before inventory "+pair.role);
                    if(right.Length==0) {
                        playerAfter.evidenceClass="native-before-byte-identical-player";
                        playerAfter.evidenceSourcePath=editorVariant.path;
                        playerAfter.evidenceSourceSha256=editorBefore.sha256;
                        playerAfter.evidenceSourceModuleVersionId=editorBefore.moduleVersionId;
                        var tuple=String.Join("\n",(sourceBefore.scripts??new SdkMonoScript[0]).Select(x=>x.type.Length.ToString(System.Globalization.CultureInfo.InvariantCulture)+":"+x.type+":"+x.localId.ToString(System.Globalization.CultureInfo.InvariantCulture)).ToArray());
                        playerAfter.evidenceSourceTupleSha256=HashText(tuple);Save();
                    } else {
                        if(!right.SequenceEqual(left))throw new Exception("Inactive Player exposes a different native MonoScript table "+pair.role);
                        playerAfter.evidenceClass="native-player-getclass";
                    }
                    var sourceKeys=(sourceBefore.scripts??new SdkMonoScript[0]).Select(SdkScriptKey).ToArray();
                    if(!sourceKeys.SequenceEqual(left))throw new Exception("Inactive Player before tuple differs from canonical Editor after tuple "+pair.role);
                }
            }
        }
        if(after) {
            report.sdkAfterMonoScripts=observedAll.Values.OrderBy(x=>x.path,StringComparer.Ordinal).ToList();
            if(job.mode=="verify") {
                var apply=JsonUtility.FromJson<Progress>(File.ReadAllText(Path.Combine(job.stage,"native-apply.json")));
                var applied=(apply.sdkAfterMonoScripts??new List<SdkScriptSnapshot>()).OrderBy(x=>x.path,StringComparer.Ordinal).ToArray();
                var reopened=report.sdkAfterMonoScripts.OrderBy(x=>x.path,StringComparer.Ordinal).ToArray();
                if(applied.Length!=reopened.Length)throw new Exception("Reopened SDK MonoScript count differs");
                for(int i=0;i<applied.Length;i++)if(!SameSdkSnapshot(applied[i],reopened[i]))throw new Exception("Reopened SDK MonoScript binding differs "+reopened[i].path);
            }
        } else {
            report.sdkBeforeComplete=true;
        }
        var currentBindings=after?report.sdkAfterMonoScripts:report.sdkBeforeMonoScripts;
        report.sdkAssembliesVerified=currentBindings.All(x=>x.moduleLoadStatus=="verified") && currentBindings.Count>0;Save();
    }
    static string ObjectType(UnityEngine.Object value) {
        if(value==null)return null;
        var script=value as MonoScript;
        var type=script!=null?script.GetClass():value.GetType();
        return type==null?null:type.FullName;
    }
    static UnityEngine.Object FindLocalObject(string path,long localId) {
        var all=new List<UnityEngine.Object>();
        all.AddRange(AssetDatabase.LoadAllAssetsAtPath(path));
        var main=AssetDatabase.LoadMainAssetAtPath(path);if(main!=null)all.Add(main);
        var game=main as GameObject;
        if(game!=null)all.AddRange(game.GetComponentsInChildren<Component>(true).Where(c=>c!=null));
        foreach(var item in all.Distinct()) { string guid;long local;if(AssetDatabase.TryGetGUIDAndLocalFileIdentifier(item,out guid,out local)&&local==localId)return item; }
        throw new Exception("SDK serialized object localID not found "+path+"#"+localId);
    }
    static bool ReferenceMatches(UnityEngine.Object value,SdkObjectReference expected) {
        if(value==null)return false;string guid;long local;
        return AssetDatabase.TryGetGUIDAndLocalFileIdentifier(value,out guid,out local)&&guid==expected.guid&&local==expected.localId&&ObjectType(value)==expected.type;
    }
    static UnityEngine.Object FindReference(SdkObjectReference reference) {
        var path=AssetDatabase.GUIDToAssetPath(reference.guid);
        if(String.IsNullOrEmpty(path))throw new Exception("SDK mapped object GUID is absent "+reference.guid);
        var value=FindLocalObject(path,reference.localId);
        if(!ReferenceMatches(value,reference))throw new Exception("SDK mapped object type/localID differs "+reference.guid+"#"+reference.localId);
        return value;
    }
    static void CheckSdkReferences(bool after,bool applyMappings) {
        if(!SdkEnabled())return;
        if(job.sdkMigration==null)throw new Exception("SDK migration is enabled but its frozen spec is missing");
        var retainedGuids=new HashSet<string>((job.sdkMigration.retainedInactiveAssemblies?.assemblies??new SdkRetainedInactiveImage[0]).Select(x=>x.guid),StringComparer.Ordinal);
        Progress mappedCheckpoint=report;
        if(after&&!applyMappings) {
            var appliedPath=Path.Combine(job.stage,"native-apply.json");
            if(!File.Exists(appliedPath))throw new Exception("SDK mapped-reference apply checkpoint is missing");
            mappedCheckpoint=JsonUtility.FromJson<Progress>(File.ReadAllText(appliedPath));
            if(mappedCheckpoint.planSha256!=job.planSha256)throw new Exception("SDK mapped-reference checkpoint belongs to another plan");
        }
        foreach(var row in job.sdkMigration.references ?? new SdkReference[0]) {
            if(!after && row.root!="target")continue;
            if(row.root=="candidate"&&(retainedGuids.Contains(row.source.guid)||retainedGuids.Contains(row.canonical.guid))||
               row.action=="map"&&(retainedGuids.Contains(row.source.guid)||retainedGuids.Contains(row.canonical.guid)))
                throw new Exception("SDK reference cannot be added or mapped to a retained inactive duplicate "+row.assetPath);
            var path=row.assetPath;var asset=FindLocalObject(path,row.objectLocalId);
            bool candidateMap=after&&row.root=="candidate"&&row.action=="map";
            if(!candidateMap&&Hash(Full(path))!=row.assetSha256)
                throw new Exception("SDK serialized reference asset bytes differ "+path);
            int mappedOperation=-1;Observed priorObservation=null;
            if(candidateMap) {
                mappedOperation=Array.FindIndex(job.operations,op=>op.target==path);
                if(mappedOperation<0)throw new Exception("SDK mapped reference is outside the owned adoption write set "+path);
                priorObservation=(mappedCheckpoint.observedAfter??new List<Observed>()).FirstOrDefault(x=>x.index==mappedOperation&&x.path==path);
                var expectedHash=priorObservation==null?row.assetSha256:priorObservation.fileHash;
                if(Hash(Full(path))!=expectedHash)throw new Exception("SDK mapped reference asset differs from its last owned checkpoint "+path);
                if(priorObservation!=null&&Hash(Full(path+".meta"))!=priorObservation.metaHash)throw new Exception("SDK mapped reference importer changed after its owned checkpoint "+path);
            }
            var serialized=new SerializedObject(asset);var property=serialized.FindProperty(row.propertyPath);
            if(property==null || property.propertyType!=SerializedPropertyType.ObjectReference)throw new Exception("SDK serialized reference property is not an object reference "+path+"."+row.propertyPath);
            if(row.action=="map" && after && applyMappings) {
                if(!ReferenceMatches(property.objectReferenceValue,row.source))throw new Exception("SDK serialized reference source identity differs "+path+"."+row.propertyPath);
                if(row.propertyPath=="m_Script")throw new Exception("SDK migration never rewrites m_Script");
                property.objectReferenceValue=FindReference(row.canonical);
                if(!serialized.ApplyModifiedPropertiesWithoutUndo())throw new Exception("SDK serialized reference change was not applied "+path+"."+row.propertyPath);
                var prefab=AssetDatabase.LoadMainAssetAtPath(path) as GameObject;
                if(prefab!=null)PrefabUtility.SavePrefabAsset(prefab);
                else AssetDatabase.SaveAssetIfDirty(asset);
                var beforeMapHash=priorObservation==null?row.assetSha256:priorObservation.fileHash;
                if(Hash(Full(path))==beforeMapHash)throw new Exception("SDK mapped reference save produced no owned byte change "+path);
                report.observedAfter.RemoveAll(x=>x.index==mappedOperation);
                report.observedAfter.Add(new Observed{index=mappedOperation,path=path,fileHash=Hash(Full(path)),metaHash=Hash(Full(path+".meta"))});
                report.sdkReferenceMappingsApplied.Add(path+"#"+row.objectLocalId+"."+row.propertyPath);Save();
            } else {
                var expected=after?row.canonical:row.source;
                if(!ReferenceMatches(property.objectReferenceValue,expected))throw new Exception("SDK serialized reference identity differs "+path+"."+row.propertyPath);
            }
        }
        if(after)CheckSdkReferenceCoverage();
        report.sdkReferencesVerified=true;Save();
    }
    static void CheckSdkReferenceCoverage() {
        if(job.sdkMigration.referenceCoverage!="all-sdk-references-in-adopted-assets")throw new Exception("SDK reference coverage policy is unknown");
        var assemblies=(job.sdkMigration.assemblies??new SdkPair[0]).Select(x=>x.assemblyName).ToArray();
        var guids=(job.sdkMigration.assemblies??new SdkPair[0]).SelectMany(x=>x.variants??new SdkVariant[0]).Select(x=>x.after.guid)
            .Concat((job.sdkMigration.retainedInactiveAssemblies?.assemblies??new SdkRetainedInactiveImage[0]).Select(x=>x.guid)).ToArray();
        var declared=(job.sdkMigration.references??new SdkReference[0]).Where(x=>x.root=="candidate").ToDictionary(x=>x.assetPath+"\0"+x.objectLocalId+"\0"+x.propertyPath,StringComparer.Ordinal);
        var found=new HashSet<string>(StringComparer.Ordinal);
        foreach(var op in job.operations) {
            var path=op.target;
            if(!(path.EndsWith(".prefab",StringComparison.OrdinalIgnoreCase)||path.EndsWith(".asset",StringComparison.OrdinalIgnoreCase)))continue;
            var objects=new List<UnityEngine.Object>();objects.AddRange(AssetDatabase.LoadAllAssetsAtPath(path));
            var main=AssetDatabase.LoadMainAssetAtPath(path);if(main!=null)objects.Add(main);
            var game=main as GameObject;
            if(game!=null) {
                foreach(var transform in game.GetComponentsInChildren<Transform>(true)) {
                    objects.Add(transform.gameObject);objects.AddRange(transform.GetComponents<Component>().Where(c=>c!=null));
                }
            }
            foreach(var item in objects.Distinct()) {
                string objectGuid;long objectId;
                if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(item,out objectGuid,out objectId))continue;
                var serialized=new SerializedObject(item);var iterator=serialized.GetIterator();
                while(iterator.Next(true)) {
                    if(iterator.propertyType!=SerializedPropertyType.ObjectReference||iterator.objectReferenceValue==null)continue;
                    string referenceGuid;long referenceId;
                    if(!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(iterator.objectReferenceValue,out referenceGuid,out referenceId))continue;
                    var objectType=ObjectType(iterator.objectReferenceValue);
                    var key=path+"\0"+objectId+"\0"+iterator.propertyPath;
                    if((job.sdkMigration.retainedInactiveAssemblies?.assemblies??new SdkRetainedInactiveImage[0]).Any(x=>x.guid==referenceGuid))
                        throw new Exception("Adopted asset references a retained inactive duplicate "+key);
                    var referenceAssembly=iterator.objectReferenceValue is MonoScript ? ((MonoScript)iterator.objectReferenceValue).GetClass()?.Assembly.GetName().Name : iterator.objectReferenceValue.GetType().Assembly.GetName().Name;
                    if(!guids.Contains(referenceGuid)&&!assemblies.Contains(referenceAssembly))continue;
                    SdkReference row;
                    if(!declared.TryGetValue(key,out row))throw new Exception("Adopted asset has an undeclared SDK serialized reference "+key);
                    if(referenceGuid!=row.canonical.guid||referenceId!=row.canonical.localId||objectType!=row.canonical.type)
                        throw new Exception("Adopted SDK serialized reference differs from explicit canonical map "+key);
                    found.Add(key);
                }
            }
        }
        foreach(var key in declared.Keys)if(!found.Contains(key))throw new Exception("Explicit SDK serialized reference was not observed in adopted assets "+key);
    }
    public static void Run() {
        int code=1;
        try {
            var jobPath=JobPath();
            if(Application.unityVersion!="6000.6.2f1")throw new Exception("Unexpected Unity version");
            job=JsonUtility.FromJson<Job>(File.ReadAllText(jobPath));
            if(job.sdkMigrationEnabled&&job.sdkMigration==null)throw new Exception("SDK migration is enabled but its frozen spec is missing");
            if(!job.sdkMigrationEnabled)job.sdkMigration=null;
            root=Path.GetFullPath(job.targetRoot).TrimEnd(Path.DirectorySeparatorChar);
            if(root!=Path.GetFullPath(Directory.GetParent(Application.dataPath).FullName).TrimEnd(Path.DirectorySeparatorChar))throw new Exception("Wrong target project");
            foreach(var op in job.operations) {
                if(op.source=="")op.source=null;if(op.guid=="")op.guid=null;
                if(op.beforeFileHash=="")op.beforeFileHash=null;if(op.beforeMetaHash=="")op.beforeMetaHash=null;if(op.afterMetaHash=="")op.afterMetaHash=null;
            }
            deadline=DateTime.UtcNow.AddSeconds(job.budgetSeconds);
            var outer=DateTime.Parse(job.deadlineUtc,null,System.Globalization.DateTimeStyles.RoundtripKind).ToUniversalTime();if(outer<deadline)deadline=outer;
            report=new Progress{status="running",mode=job.mode,planSha256=job.planSha256};Save();
            if(job.mode=="rollback") {
                var priorPath=Path.Combine(job.stage,"native-apply.json");
                if(!File.Exists(priorPath))priorPath=Path.Combine(job.stage,"native-code.json");
                var previous=JsonUtility.FromJson<Progress>(File.ReadAllText(priorPath));
                if(previous.planSha256!=job.planSha256)throw new Exception("Wrong native rollback checkpoint");
                var codeCheckpoint=Path.Combine(job.stage,"native-code.json");
                if(File.Exists(codeCheckpoint)) {
                    var codePrior=JsonUtility.FromJson<Progress>(File.ReadAllText(codeCheckpoint));
                    if(codePrior.planSha256!=job.planSha256)throw new Exception("Wrong code checkpoint");
                    previous.written=codePrior.written.Concat(previous.written).Distinct().ToList();
                    if(previous.beforeAssets.Count==0)previous.beforeAssets=codePrior.beforeAssets;
                    if(previous.sdkBeforeMonoScripts==null||previous.sdkBeforeMonoScripts.Count==0)previous.sdkBeforeMonoScripts=codePrior.sdkBeforeMonoScripts;
                    if(previous.sdkBeforeInactiveAssemblies==null||previous.sdkBeforeInactiveAssemblies.Count==0)previous.sdkBeforeInactiveAssemblies=codePrior.sdkBeforeInactiveAssemblies;
                    previous.sdkBeforeComplete=previous.sdkBeforeComplete||codePrior.sdkBeforeComplete;
                    previous.createdFolders=codePrior.createdFolders.Concat(previous.createdFolders).GroupBy(e=>e.path).Select(g=>g.First()).ToList();
                }
                foreach(var i in previous.written.AsEnumerable().Reverse()) {
                    Checkpoint();var op=job.operations[i];var at=File.Exists(Full(op.target))?op.target:op.source;
                    if(job.codeRestored && op.compileStage) {
                        if(op.source!=null){Expected(op.source,op.beforeFileHash);Expected(op.source+".meta",op.beforeMetaHash);}
                        if(op.source!=op.target){Expected(op.target,null);Expected(op.target+".meta",null);}
                        report.restored.Add(i);Save();continue;
                    }
                    if(at==null || !File.Exists(Full(at))) { if(op.action=="add"){report.restored.Add(i);Save();continue;}throw new Exception("Rollback asset missing"); }
                    var fh=Hash(Full(at));var mh=Hash(Full(at+".meta"));
                    var observed=(previous.observedAfter ?? new List<Observed>()).FirstOrDefault(row=>row.index==i&&row.path==at);
                    bool ownedObserved=observed!=null&&fh==observed.fileHash&&mh==observed.metaHash;
                    if(!ownedObserved&&(fh!=op.afterFileHash && fh!=op.beforeFileHash || mh!=op.afterMetaHash && mh!=op.beforeMetaHash))throw new Exception("Rollback conflicts with later changes "+at);
                    if(op.action=="add") { if(!AssetDatabase.DeleteAsset(at))throw new Exception("Delete added asset failed"); }
                    else {
                        if(at!=op.source){Folder(op.source);var error=AssetDatabase.MoveAsset(at,op.source);if(error!="")throw new Exception(error);}
                        WritePayload(i,"before",op.source,op.beforeFileHash,op.beforeMetaHash);
                    }
                    report.restored.Add(i);Save();
                }
                foreach(var folder in (previous.createdFolders ?? new List<Entry>()).AsEnumerable().Reverse()) {
                    if(!Directory.Exists(Full(folder.path)))continue;
                    if(Directory.EnumerateFileSystemEntries(Full(folder.path)).Any()){report.retainedFolders.Add(folder.path);continue;}
                    if(AssetDatabase.AssetPathToGUID(folder.path)!=folder.guid)throw new Exception("Created folder identity changed");
                    if(!AssetDatabase.DeleteAsset(folder.path))throw new Exception("Delete empty owned folder failed");
                }
                foreach(var old in previous.beforeAssets ?? new List<Entry>()) {
                    if(AssetDatabase.AssetPathToGUID(old.path)!=old.guid || !Ids(old.path).SequenceEqual(old.localIds))throw new Exception("Restored local identities differ "+old.path);
                }
                CheckSdkAssemblies(false);CheckSdkReferences(false,false);ConfirmSdkModuleBindings(false);
                var expectedInactive=previous.sdkBeforeInactiveAssemblies??new List<SdkRetainedInactiveSnapshot>();
                var restoredInactive=report.sdkBeforeInactiveAssemblies.ToDictionary(x=>x.path,StringComparer.Ordinal);
                foreach(var old in expectedInactive) {
                    SdkRetainedInactiveSnapshot restored;
                    if(!restoredInactive.TryGetValue(old.path,out restored)||!SameRetainedInactiveSnapshot(old,restored))throw new Exception("Rollback retained inactive SDK differs "+old.path);
                }
                var expectedSdkBefore=previous.sdkBeforeMonoScripts??new List<SdkScriptSnapshot>();
                var restoredSdkByPath=report.sdkBeforeMonoScripts.ToDictionary(x=>x.path,StringComparer.Ordinal);
                // Failed preflight may stop midway through native capture. Its
                // checkpoint is a verified subset; a fresh complete pass above
                // verifies every current before-image and records the full set.
                if(previous.sdkBeforeComplete&&expectedSdkBefore.Count!=restoredSdkByPath.Count)throw new Exception("Rollback SDK MonoScript inventory count differs");
                foreach(var old in expectedSdkBefore) {
                    SdkScriptSnapshot restored;
                    if(!restoredSdkByPath.TryGetValue(old.path,out restored)||!SameSdkRollbackSnapshot(old,restored))throw new Exception("Rollback SDK MonoScript identity/role differs "+old.path);
                }
                var refs=Path.Combine(job.stage,"reference-signatures.json");
                if(File.Exists(refs))foreach(var line in File.ReadAllLines(refs)){var parts=line.Split('\t');if(parts.Length!=2||RefSignature(parts[0])!=parts[1])throw new Exception("Restored watcher dependencies differ");}
                report.status="rolled-back";report.referencesPreserved=true;
            } else {
                var signatures=new Dictionary<string,string>();
                if(job.mode=="code" || job.mode=="apply") {
                    var codePath=Path.Combine(job.stage,"native-code.json");
                    bool staged=job.mode=="apply" && File.Exists(codePath);
                    if(staged) {
                        var prior=JsonUtility.FromJson<Progress>(File.ReadAllText(codePath));
                        if(prior.status!="staged" || prior.planSha256!=job.planSha256)throw new Exception("Invalid compilation checkpoint");
                        report.written=prior.written;report.beforeAssets=prior.beforeAssets;report.createdFolders=prior.createdFolders;report.observedAfter=prior.observedAfter;report.sdkBeforeMonoScripts=prior.sdkBeforeMonoScripts;report.sdkBeforeComplete=prior.sdkBeforeComplete;report.sdkBeforeInactiveAssemblies=prior.sdkBeforeInactiveAssemblies;
                        foreach(var line in File.ReadAllLines(Path.Combine(job.stage,"reference-signatures.json"))){var parts=line.Split('\t');if(parts.Length!=2||RefSignature(parts[0])!=parts[1])throw new Exception("Compiled watcher dependencies changed");signatures[parts[0]]=parts[1];}
                        foreach(var old in report.beforeAssets)if(job.operations[old.index].preserveLocalIds)originalIds[job.operations[old.index].target]=old.localIds;
                    } else {
                        if(job.mode=="code"||SdkEnabled()){CheckSdkAssemblies(false);CheckSdkReferences(false,false);}
                        foreach(var watch in job.watch ?? new string[0])signatures[watch]=RefSignature(watch);
                        // Capture every original identity before changing compiler inputs.
                        for(int i=0;i<job.operations.Length;i++) {
                            var op=job.operations[i];
                            if(op.source!=null){Expected(op.source,op.beforeFileHash);Expected(op.source+".meta",op.beforeMetaHash);if(op.guid!=null&&AssetDatabase.AssetPathToGUID(op.source)!=op.guid)throw new Exception("Source GUID differs");var ids=Ids(op.source);report.beforeAssets.Add(new Entry{index=i,path=op.source,guid=AssetDatabase.AssetPathToGUID(op.source),localIds=ids});if(op.preserveLocalIds)originalIds[op.target]=ids;}
                            else {Expected(op.target,null);Expected(op.target+".meta",null);}
                        }
                        File.WriteAllText(Path.Combine(job.stage,"reference-signatures.json"),String.Join("\n",signatures.Select(p=>p.Key+"\t"+p.Value)));Save();
                    }
                    if(job.mode=="code") {
                        // All directories are created through the Editor before reload is locked.
                        foreach(var op in job.operations.Where(op=>op.compileStage))Folder(op.target);
                        EditorApplication.LockReloadAssemblies();AssetDatabase.DisallowAutoRefresh();
                    }
                    for(int i=0;i<job.operations.Length;i++) {
                        Checkpoint();var op=job.operations[i];
                        if(staged && op.compileStage){VerifyAsset(i,op);Save();continue;}
                        if(job.mode=="code" && !op.compileStage)continue;
                        if(op.source!=null){Expected(op.source,op.beforeFileHash);Expected(op.source+".meta",op.beforeMetaHash);}
                        else {Expected(op.target,null);Expected(op.target+".meta",null);}
                        report.written.Add(i);Save();
                        if(op.action=="move") {Folder(op.target);var error=AssetDatabase.MoveAsset(op.source,op.target);if(error!="")throw new Exception(error);}
                        WritePayload(i,"after",op.target,op.afterFileHash,op.afterMetaHash,job.mode!="code");if(job.mode!="code")VerifyAsset(i,op);Save();
                    }
                    if(job.mode!="code")foreach(var watch in signatures.Keys)if(RefSignature(watch)!=signatures[watch])throw new Exception("Unchanged watcher dependencies changed "+watch);
                    if(job.mode=="apply") { CheckSdkAssemblies(true);CheckSdkReferences(true,true);ConfirmSdkModuleBindings(true); }
                } else if(job.mode=="verify") {
                    CheckSdkAssemblies(true);CheckSdkReferences(true,false);
                    ConfirmSdkModuleBindings(true);
                    var applyReport=JsonUtility.FromJson<Progress>(File.ReadAllText(Path.Combine(job.stage,"native-apply.json")));
                    if(applyReport.planSha256!=job.planSha256)throw new Exception("Wrong apply readback identity");
                    foreach(var reference in SdkEnabled()?job.sdkMigration.references:new SdkReference[0]) if(reference.action=="map"&&reference.root=="candidate") {
                        var index=Array.FindIndex(job.operations,op=>op.target==reference.assetPath);
                        var observed=applyReport.observedAfter.FirstOrDefault(row=>row.index==index&&row.path==reference.assetPath);
                        if(index<0||observed==null)throw new Exception("SDK mapped reference readback is missing "+reference.assetPath);
                        mappedReadbackHashes[index]=observed.fileHash;
                    }
                    for(int i=0;i<job.operations.Length;i++){Checkpoint();VerifyAsset(i,job.operations[i]);}
                    foreach(var line in File.ReadAllLines(Path.Combine(job.stage,"reference-signatures.json"))){var parts=line.Split('\t');if(parts.Length!=2||RefSignature(parts[0])!=parts[1])throw new Exception("Reopened dependencies changed");}
                    if(applyReport.assets.Count!=report.assets.Count)throw new Exception("Readback count differs");
                    for(int i=0;i<applyReport.assets.Count;i++)if(!applyReport.assets[i].localIds.SequenceEqual(report.assets[i].localIds))throw new Exception("Reopened local IDs differ");
                } else throw new Exception("Unknown adoption mode");
                report.status=job.mode=="code"?"staged":"verified";report.referencesPreserved=job.mode!="code";
            }
            Save();code=0;
        } catch(Exception error) {if(report!=null){report.status="failed";report.error=error.ToString();Save();}Debug.LogException(error);}
        EditorApplication.Exit(code);
    }
}
#endif
