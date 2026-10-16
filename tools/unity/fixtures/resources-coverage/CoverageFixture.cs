// Editor-only, create-only own fixture. Caller supplies a scene root and NEW external report.
using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Grea.Tools;
using Own.Coverage;
using Object=UnityEngine.Object;

public static class CoverageFixture
{
    public static void Seed()
    {
        if(Directory.Exists("Assets/Coverage"))throw new IOException("New fixture directory required");
        Directory.CreateDirectory("Assets/Coverage/Resources");Directory.CreateDirectory("Assets/Coverage/Indirect");Directory.CreateDirectory("Assets/Coverage/Editor/Resources");AssetDatabase.Refresh();
        var indirect=ScriptableObject.CreateInstance<CoverageData>();AssetDatabase.CreateAsset(indirect,"Assets/Coverage/Indirect/Link.asset");
        var data=ScriptableObject.CreateInstance<CoverageData>();data.link=indirect;AssetDatabase.CreateAsset(data,"Assets/Coverage/Resources/Unreferenced.asset");
        AssetDatabase.CreateAsset(ScriptableObject.CreateInstance<CoverageData>(),"Assets/Coverage/Editor/Resources/Excluded.asset");
        var go=new GameObject("Coverage");try{go.AddComponent<CoverageProbe>();PrefabUtility.SaveAsPrefabAsset(go,"Assets/Coverage/Resources/Unreferenced.prefab");}finally{Object.DestroyImmediate(go);}
        AssetDatabase.SaveAssets();Verify();
    }
    public static void Verify()
    {
        NativeExitEditorAudit.Run();var args=Environment.GetCommandLineArgs();var request=JsonUtility.FromJson<NativeExitEditorAudit.Request>(File.ReadAllText(args[Array.IndexOf(args,"-greaAuditRequest")+1]));
        var report=JsonUtility.FromJson<NativeExitEditorAudit.Report>(File.ReadAllText(request.output));
        foreach(string path in new[]{"Assets/Coverage/Resources/Unreferenced.asset","Assets/Coverage/Resources/Unreferenced.prefab","Assets/Coverage/Indirect/Link.asset"})
            if(!report.dependencies.Contains(path))throw new InvalidOperationException("Omitted runtime Resource/dependency: "+path);
        if(report.dependencies.Contains("Assets/Coverage/Editor/Resources/Excluded.asset") || report.dependencies.Distinct().Count()!=report.dependencies.Length)throw new InvalidOperationException("Editor Resources/deduplication failed");
        if(!report.editor_asset_types.Any(x=>x.asset=="Assets/Coverage/Resources/Unreferenced.prefab"&&x.editor_loaded_type==typeof(CoverageProbe).FullName) || !report.editor_asset_types.Any(x=>x.asset=="Assets/Coverage/Resources/Unreferenced.asset"&&x.editor_loaded_type==typeof(CoverageData).FullName))throw new InvalidOperationException("Missing actual Editor type observations");
        Debug.Log("GREA_RESOURCES_COVERAGE_ASSERTIONS_OK");
    }
}
