using Mono.Cecil;
using Mono.Cecil.Cil;

if (args.Length < 2)
{
    Console.Error.WriteLine("Usage: AssemblySanitizer <plugins-directory> <backup-directory> [--unity-editor <path>] [--apply]");
    return 2;
}

var pluginsDirectory = Path.GetFullPath(args[0]);
var backupDirectory = Path.GetFullPath(args[1]);
var apply = args.Contains("--apply", StringComparer.Ordinal);
var editorPath = OptionValue(args, "--unity-editor");
if (!Directory.Exists(pluginsDirectory))
{
    Console.Error.WriteLine($"Plugins directory does not exist: {pluginsDirectory}");
    return 2;
}
if (apply)
    Directory.CreateDirectory(backupDirectory);

var resolver = new DefaultAssemblyResolver();
resolver.AddSearchDirectory(pluginsDirectory);
if (editorPath is not null)
{
    var contents = editorPath.EndsWith(".app", StringComparison.OrdinalIgnoreCase)
        ? Path.Combine(editorPath, "Contents")
        : editorPath;
    foreach (var relative in new[] { "Managed", "Managed/UnityEngine", "UnityReferenceAssemblies/unity-4.8-api" })
    {
        var searchPath = Path.Combine(contents, relative);
        if (Directory.Exists(searchPath))
            resolver.AddSearchDirectory(searchPath);
    }
}

var changed = 0;
foreach (var assemblyPath in Directory.EnumerateFiles(pluginsDirectory, "*.dll", SearchOption.TopDirectoryOnly))
{
    using var assembly = AssemblyDefinition.ReadAssembly(assemblyPath, new ReaderParameters
    {
        AssemblyResolver = resolver,
        InMemory = true,
        ReadWrite = false,
    });

    var generatedTypes = assembly.MainModule.Types
        .Where(type => type.Name.Contains("UnitySourceGeneratedAssemblyMonoScriptTypes", StringComparison.Ordinal))
        .ToArray();
    var hadExecutableMetadata = assembly.MainModule.Kind != ModuleKind.Dll || assembly.EntryPoint is not null;
    var pinvokeMethods = AllTypes(assembly.MainModule.Types)
        .SelectMany(type => type.Methods)
        .Where(method => method.IsPInvokeImpl || method.PInvokeInfo is not null)
        .ToArray();
    if (generatedTypes.Length == 0 && !hadExecutableMetadata && pinvokeMethods.Length == 0)
    {
        continue;
    }

    Console.WriteLine(
        $"{(apply ? "sanitizing" : "would-sanitize")} {Path.GetFileName(assemblyPath)} " +
        $"({generatedTypes.Length} generated type(s), executableMetadata={hadExecutableMetadata}, " +
        $"pinvokeStubs={pinvokeMethods.Length})");
    if (!apply)
    {
        changed++;
        continue;
    }

    var backupPath = Path.Combine(backupDirectory, Path.GetFileName(assemblyPath));
    if (!File.Exists(backupPath))
    {
        File.Copy(assemblyPath, backupPath);
    }

    foreach (var generatedType in generatedTypes)
    {
        assembly.MainModule.Types.Remove(generatedType);
    }

    // AssetRipper dummy assemblies can retain executable PE metadata even though
    // Unity consumes every file in Assets/Plugins as a library. UnityLinker then
    // attempts to resolve a missing executable entry point and crashes.
    assembly.MainModule.Kind = ModuleKind.Dll;
    assembly.EntryPoint = null;

    var coreLibrary = assembly.MainModule.AssemblyReferences
        .FirstOrDefault(reference => reference.Name == "mscorlib");
    if (coreLibrary is null)
    {
        coreLibrary = new AssemblyNameReference("mscorlib", new Version(4, 0, 0, 0));
        assembly.MainModule.AssemblyReferences.Add(coreLibrary);
    }

    var notSupportedType = new TypeReference(
        "System", "NotSupportedException", assembly.MainModule, coreLibrary);
    var notSupportedConstructor = new MethodReference(
        ".ctor", assembly.MainModule.TypeSystem.Void, notSupportedType)
    {
        HasThis = true,
    };
    notSupportedConstructor.Parameters.Add(
        new ParameterDefinition(assembly.MainModule.TypeSystem.String));
    foreach (var method in pinvokeMethods)
    {
        method.PInvokeInfo = null;
        method.Attributes &= ~MethodAttributes.PInvokeImpl;
        method.ImplAttributes &= ~(MethodImplAttributes.InternalCall | MethodImplAttributes.Native | MethodImplAttributes.Runtime);
        method.ImplAttributes |= MethodImplAttributes.IL | MethodImplAttributes.Managed;
        method.Body = new MethodBody(method);
        var il = method.Body.GetILProcessor();
        il.Append(il.Create(OpCodes.Ldstr, $"Recovered native entry point is unavailable: {method.FullName}"));
        il.Append(il.Create(OpCodes.Newobj, notSupportedConstructor));
        il.Append(il.Create(OpCodes.Throw));
    }

    var temporaryPath = assemblyPath + ".sanitized";
    assembly.Write(temporaryPath);
    File.Move(temporaryPath, assemblyPath, overwrite: true);
    changed++;
}

Console.WriteLine($"mode={(apply ? "apply" : "dry-run")} candidates={changed}");
return 0;

static string? OptionValue(string[] arguments, string option)
{
    for (var index = 0; index < arguments.Length - 1; index++)
        if (string.Equals(arguments[index], option, StringComparison.Ordinal))
            return Path.GetFullPath(arguments[index + 1]);
    return null;
}

static IEnumerable<TypeDefinition> AllTypes(IEnumerable<TypeDefinition> roots)
{
    foreach (var type in roots)
    {
        yield return type;
        foreach (var nested in AllTypes(type.NestedTypes))
        {
            yield return nested;
        }
    }
}
