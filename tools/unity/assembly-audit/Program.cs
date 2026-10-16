using System.Security.Cryptography;
using System.Text.Json;
using Mono.Cecil;
using Mono.Cecil.Cil;

// Metadata only. Never Assembly.Load, Resolve inspected types, or execute inspected IL.
sealed class RejectResolver : IAssemblyResolver
{
    public AssemblyDefinition Resolve(AssemblyNameReference name) => throw new AssemblyResolutionException(name);
    public AssemblyDefinition Resolve(AssemblyNameReference name, ReaderParameters parameters) => throw new AssemblyResolutionException(name);
    public void Dispose() { }
}
static class Program
{
    static int typeCount, methodCount, fieldCount, callCount;
    static IEnumerable<TypeDefinition> Types(IEnumerable<TypeDefinition> roots)
    {
        var pending=new Stack<TypeDefinition>(roots.Reverse());
        while(pending.Count>0) {var type=pending.Pop(); yield return type; foreach(var nested in type.NestedTypes.Reverse()) pending.Push(nested);}
    }
    static int Main(string[] args)
    {
        try
        {
            if(args.Length!=3) throw new ArgumentException("Expected manifest, managed directory, and explicit call-type JSON array");
            using var manifest=JsonDocument.Parse(File.ReadAllBytes(args[0]));
            var selected=JsonSerializer.Deserialize<string[]>(args[2])!.ToHashSet(StringComparer.Ordinal);
            var assemblies=new List<object>(); long totalBytes=0;
            using var resolver=new RejectResolver();
            foreach(var input in manifest.RootElement.GetProperty("assemblies").EnumerateArray())
            {
                string relative=input.GetProperty("path").GetString()!, path=Path.Combine(args[1],relative);
                var bytes=new FileInfo(path).Length;totalBytes+=bytes;
                if(bytes>64L*1024*1024 || totalBytes>512L*1024*1024) throw new InvalidDataException("ASSEMBLY_BUDGET_EXCEEDED");
                using var stream=File.OpenRead(path);
                using var assembly=AssemblyDefinition.ReadAssembly(stream,new ReaderParameters {ReadSymbols=false,ReadingMode=ReadingMode.Deferred,AssemblyResolver=resolver});
                var types=new List<object>();
                foreach(var type in Types(assembly.MainModule.Types))
                {
                    if(type.Name=="<Module>") continue;
                    if(++typeCount>100000) throw new InvalidDataException("TYPE_BUDGET_EXCEEDED");
                    var fields=new List<object>();var methods=new List<string>();var calls=new List<object>();
                    foreach(var field in type.Fields) {if(++fieldCount>500000) throw new InvalidDataException("FIELD_BUDGET_EXCEEDED"); fields.Add(new {name=field.Name,type=field.FieldType.FullName});}
                    foreach(var method in type.Methods)
                    {
                        if(++methodCount>500000) throw new InvalidDataException("METHOD_BUDGET_EXCEEDED");
                        methods.Add(method.FullName);
                        if(!selected.Contains(type.FullName) || !method.HasBody) continue;
                        foreach(var instruction in method.Body.Instructions)
                        {
                            if((instruction.OpCode.Code==Code.Call || instruction.OpCode.Code==Code.Callvirt || instruction.OpCode.Code==Code.Newobj) && instruction.Operand is MethodReference target)
                            {
                                if(++callCount>250000) throw new InvalidDataException("CALL_BUDGET_EXCEEDED");
                                calls.Add(new {method=method.FullName,offset=instruction.Offset,opcode=instruction.OpCode.Name,target=target.FullName});
                            }
                        }
                    }
                    types.Add(new {name=type.FullName,base_type=type.BaseType?.FullName,fields,methods,calls});
                }
                stream.Position=0;string sha=Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
                assemblies.Add(new {path=relative,sha256=sha,name=assembly.Name.Name,mvid=assembly.MainModule.Mvid.ToString(),references=assembly.MainModule.AssemblyReferences.Select(x=>x.Name).Order().ToArray(),types});
            }
            string result=JsonSerializer.Serialize(new {schema_version=1,reader="grea-cecil-metadata",implementation_version="0.1.0",assemblies});
            if(System.Text.Encoding.UTF8.GetByteCount(result)>32*1024*1024) throw new InvalidDataException("REPORT_BUDGET_EXCEEDED");
            Console.WriteLine(result);return 0;
        }
        catch(Exception error) {Console.WriteLine(JsonSerializer.Serialize(new {error=new {code="METADATA_READ_ERROR",message=error.GetType().Name+": "+error.Message}}));return 2;}
    }
}
