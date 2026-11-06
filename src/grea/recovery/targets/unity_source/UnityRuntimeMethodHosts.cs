#if UNITY_EDITOR
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Globalization;
using UnityEditor;
using UnityEngine;

public static class UnityRuntimeMethodHosts
{
    [Serializable] private class Manifest { public Host[] hosts; }
    [Serializable] private class Host {
        public string asset, sourceCab, sourceComponent, siblingPath, node, type, assembly, scriptGuid;
        public int componentIndex;
    }

    public static void Save() { Inspect(true); }
    public static void Cold() { Inspect(false); }

    [Serializable] private class Signatures { public ExpectedMethod[] methods; }
    [Serializable] private class ExpectedMethod {
        public string scriptGuid, owner, name, result;
        public int index;
        public bool isStatic;
        public string[] parameters;
    }
    private static readonly System.Collections.Generic.Dictionary<Type,string> aliases =
        new System.Collections.Generic.Dictionary<Type,string>{
            {typeof(bool),"bool"},{typeof(string),"string"},{typeof(float),"float"},{typeof(double),"double"},
            {typeof(decimal),"decimal"},{typeof(char),"char"},{typeof(void),"void"},{typeof(object),"object"},
            {typeof(int),"int"},{typeof(uint),"uint"},{typeof(short),"short"},{typeof(ushort),"ushort"},
            {typeof(long),"long"},{typeof(ulong),"ulong"},{typeof(byte),"byte"},{typeof(sbyte),"sbyte"}
        };

    private static bool MatchesType(string source, Type actual) {
        source=source.Replace("global::","");
        if (actual.IsArray) {
            string suffix="["+new string(',',actual.GetArrayRank()-1)+"]";
            return source.EndsWith(suffix,StringComparison.Ordinal) &&
                MatchesType(source.Substring(0,source.Length-suffix.Length),actual.GetElementType());
        }
        if (actual.IsGenericType) {
            int start=source.IndexOf('<');
            if(start<0 || !source.EndsWith(">",StringComparison.Ordinal))return false;
            var args=actual.GetGenericArguments();
            int depth=0,position=start+1,index=0;
            for(int i=position;i<source.Length;i++){
                char ch=source[i];
                if(depth==0 && (ch==',' || i==source.Length-1)){
                    if(index>=args.Length || !MatchesType(source.Substring(position,i-position),args[index++]))return false;
                    position=i+1;
                } else if(ch=='<' || ch=='[')depth++;
                else if(ch=='>' || ch==']')depth--;
            }
            if(depth!=0 || index!=args.Length)return false;
            source=source.Substring(0,start);
            actual=actual.GetGenericTypeDefinition();
        }
        string full=(actual.FullName ?? actual.Name).Split('`')[0].Replace('+','.');
        return (aliases.TryGetValue(actual,out string alias) && source==alias) || source==full ||
            source==actual.Name.Split('`')[0] || (actual.IsNested && full.EndsWith("."+source,StringComparison.Ordinal));
    }
    private static bool Matches(ExpectedMethod source, MethodBase method) {
        if (method.Name!=source.name || method.IsStatic!=source.isStatic) return false;
        var args=method.GetParameters();
        if (source.parameters.Length!=args.Length) return false;
        for(int i=0;i<args.Length;i++){
            var arg=args[i];
            string expected=source.parameters[i];
            if(arg.ParameterType.IsByRef){
                string prefix=arg.IsOut?"out ":arg.IsIn?"in ":"ref ";
                if(!expected.StartsWith(prefix,StringComparison.Ordinal))return false;
                expected=expected.Substring(prefix.Length);
            }
            if(!MatchesType(expected,arg.ParameterType.IsByRef?arg.ParameterType.GetElementType():arg.ParameterType))return false;
        }
        return MatchesType(source.result,(method as MethodInfo)?.ReturnType ?? typeof(void));
    }
    private static void CheckMethodSignatures(string directory,bool save) {
        string path=Path.Combine(directory,"expected-method-signatures.json");
        string additions=Path.Combine(directory,"expected-method-signatures.d");
        var extra=Directory.Exists(additions)?Directory.GetFiles(additions,"*.json"):Array.Empty<string>();
        if(!File.Exists(path)){
            if(extra.Length!=0)throw new InvalidDataException("Missing native signature baseline: "+path);
            return;
        }
        var catalogs=new System.Collections.Generic.List<string>{path};
        catalogs.AddRange(extra.OrderBy(f=>f,StringComparer.Ordinal));
        var records=new System.Collections.Generic.List<ExpectedMethod>();
        var known=new System.Collections.Generic.Dictionary<string,string>();
        foreach(var catalog in catalogs){
            var expected=JsonUtility.FromJson<Signatures>(File.ReadAllText(catalog));
            if(expected?.methods==null || expected.methods.Length==0)throw new InvalidDataException(catalog);
            foreach(var record in expected.methods){
                string key=record.scriptGuid+"-"+record.index.ToString(CultureInfo.InvariantCulture);
                if(catalog!=path && (expected.methods.Length!=1 || Path.GetFileNameWithoutExtension(catalog)!=key))
                    throw new InvalidDataException("Unexpected signature catalog identity: "+catalog);
                string signature=JsonUtility.ToJson(record);
                if(known.TryGetValue(key,out string previous)){
                    if(signature!=previous)throw new InvalidDataException("Conflicting compiled overload "+key);
                    continue;
                }
                known.Add(key,signature);records.Add(record);
            }
        }
        var rows=new System.Collections.Generic.List<string>();
        const BindingFlags flags=BindingFlags.DeclaredOnly|BindingFlags.Static|BindingFlags.Instance|BindingFlags.Public|BindingFlags.NonPublic;
        foreach(var record in records){
            var script=AssetDatabase.LoadAssetAtPath<MonoScript>(AssetDatabase.GUIDToAssetPath(record.scriptGuid));
            Type component=script?script.GetClass():null;
            if(component==null)throw new InvalidDataException("Missing compiled script "+record.scriptGuid);
            var owner=component;
            if(owner.FullName!=record.owner){
                if(!record.owner.StartsWith(component.FullName+".",StringComparison.Ordinal))throw new InvalidDataException(record.owner);
                foreach(var nested in record.owner.Substring(component.FullName.Length+1).Split('.'))
                    owner=owner?.GetNestedType(nested,BindingFlags.Public|BindingFlags.NonPublic);
            }
            var method=owner?.GetMembers(flags).OfType<MethodBase>().SingleOrDefault(m=>Matches(record,m));
            if(method==null)throw new InvalidDataException("Missing compiled overload "+record.index+" "+record.owner+"."+record.name+"("+string.Join(",",record.parameters)+")");
            rows.Add(string.Join("\t",record.index.ToString(CultureInfo.InvariantCulture),record.scriptGuid,record.owner,method.ToString()));
        }
        string saved=Path.Combine(directory,"method-signatures-saved.tsv");
        if(!save && !File.ReadAllLines(saved).SequenceEqual(rows))throw new InvalidDataException("Compiled overloads changed after reopening");
        File.WriteAllLines(save?saved:Path.Combine(directory,"method-signatures-cold.tsv"),rows);
    }

    private static void Inspect(bool save)
    {
        string directory = Directory.GetParent(Application.dataPath).FullName;
        CheckMethodSignatures(directory,save);
        var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(Path.Combine(directory,"expected-hosts.json")));
        if (manifest?.hosts == null || manifest.hosts.Length == 0)
            throw new InvalidDataException("Expected original script hosts");
        var rows = new System.Collections.Generic.List<string>();
        foreach (var group in manifest.hosts.GroupBy(h => h.asset)) {
            if (save) {
                var contents = PrefabUtility.LoadPrefabContents(group.Key);
                try {
                    PrefabUtility.SaveAsPrefabAsset(contents, group.Key, out bool saved);
                    if (!saved) throw new IOException(group.Key);
                } finally { PrefabUtility.UnloadPrefabContents(contents); }
            }
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>(group.Key);
            if (!asset) throw new InvalidDataException(group.Key);
            foreach (var h in group) {
                var indices = h.siblingPath.Split('/');
                if (indices[0] != "0") throw new InvalidDataException(h.siblingPath);
                Transform node = asset.transform;
                foreach (var part in indices.Skip(1)) node = node.GetChild(int.Parse(part,CultureInfo.InvariantCulture));
                var component = node.GetComponents<Component>()[h.componentIndex] as MonoBehaviour;
                if (!component || node.name != h.node || component.GetType().FullName != h.type ||
                    component.GetType().Assembly.GetName().Name != h.assembly)
                    throw new InvalidDataException(group.Key+" "+h.siblingPath+" "+h.type);
                var script = MonoScript.FromMonoBehaviour(component);
                if (!script || script.GetClass()!=component.GetType() ||
                    AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(script))!=h.scriptGuid ||
                    !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(component,out string prefabGuid,out long localId) ||
                    localId==0 || prefabGuid!=AssetDatabase.AssetPathToGUID(group.Key))
                    throw new InvalidDataException("Changed component identity on "+group.Key+" "+h.siblingPath);
                rows.Add(string.Join("\t", group.Key,h.sourceCab,h.sourceComponent,h.siblingPath,h.type,
                                     h.scriptGuid,prefabGuid,localId.ToString(CultureInfo.InvariantCulture)));
            }
        }
        string path=Path.Combine(directory,save?"method-hosts-saved.tsv":"method-hosts-cold.tsv");
        File.WriteAllLines(path,rows);
        if (!save && !File.ReadAllLines(Path.Combine(directory,"method-hosts-saved.tsv")).SequenceEqual(rows))
            throw new InvalidDataException("Component bindings changed after a fresh Unity import");
    }
}
#endif
