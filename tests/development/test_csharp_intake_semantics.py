"""Roslyn source semantic inventory fixtures for intake classification."""
import json
from pathlib import Path
import tempfile
import unittest

from grea.development.csharp import _resolve_toolchain, _run_semantic


SDK = Path("/Applications/Unity/Hub/Editor/6000.6.2f1/Unity.app/Contents/Resources/Scripting/DotNetSdk")


class CSharpIntakeSemanticsTests(unittest.TestCase):
    def test_source_types_fields_dependencies_and_editor_domain(self):
        if not (SDK / "dotnet").is_file():
            self.skipTest("Unity SDK toolchain is unavailable")
        sdk_roots = sorted((SDK / "sdk").glob("*"))
        if not sdk_roots:
            self.skipTest("Unity .NET SDK files are unavailable")
        toolchain = _resolve_toolchain({"dotnet": str(SDK / "dotnet"), "sdkRoot": sdk_roots[-1]})
        reference_roots = sorted((SDK / "packs" / "Microsoft.NETCore.App.Ref").glob("*/ref/net8.0"))
        if not reference_roots:
            self.skipTest(".NET 8 reference assemblies are unavailable")
        refs = sorted(str(p) for p in reference_roots[-1].glob("*.dll"))
        unity_editor_ref = Path("/Applications/Unity/Hub/Editor/6000.6.2f1/Unity.app/Contents/Resources/Scripting/Managed/UnityEngine/UnityEditor.CoreModule.dll")
        if unity_editor_ref.is_file():
            refs.append(str(unity_editor_ref))
        with tempfile.TemporaryDirectory(prefix="beaver-semantic-fixture-") as temp:
            project = Path(temp)
            (project / "Carrier.cs").write_text(
                """using System.Collections.Generic;
namespace Game { public sealed class Carrier : UnityEngine.MonoBehaviour {
 public string source = string.Empty;
 public UnityEngine.MonoBehaviour[] items;
 [UnityEngine.SerializeField] private List<int[]> values = null;
} }
""", encoding="utf-8")
            (project / "Stubs.cs").write_text(
                "namespace UnityEngine { public class MonoBehaviour { } public sealed class SerializeField : System.Attribute { } }\n",
                encoding="utf-8")
            (project / "UseCarrier.cs").write_text(
                "namespace Consumer { using CarrierAlias = Game.Carrier; public static class UseCarrier { public static CarrierAlias Make() => new CarrierAlias(); } }\n",
                encoding="utf-8")
            (project / "IslandA.cs").write_text("namespace Shared { public sealed class IslandA { } }\n", encoding="utf-8")
            (project / "IslandB.cs").write_text("namespace Shared { public sealed class IslandB { } }\n", encoding="utf-8")
            (project / "Lookups.cs").write_text(
                "public static class Lookups { public static System.Type Ordinary(object value) => value.GetType(); "
                "public static System.Type Named() => System.Type.GetType(\"Game.Carrier\"); }\n", encoding="utf-8")
            assemblies = [
                {"name": "UnityStubs", "sources": [str(project / "Stubs.cs")], "references": refs},
                {"name": "Assembly-CSharp", "sources": [str(project / "Carrier.cs"), str(project / "UseCarrier.cs")],
                 "references": refs, "projectReferences": ["UnityStubs"], "defines": ["UNITY_EDITOR"]},
            ]
            assemblies[1]["sources"].extend(str(project / name) for name in ("IslandA.cs", "IslandB.cs", "Lookups.cs"))
            response, _ = _run_semantic(project, "inspect", assemblies, toolchain)
        assembly = next(row for row in response["assemblies"] if row["name"] == "Assembly-CSharp")
        rows = {row["path"]: row for row in assembly["sourceSemantics"]}
        carrier = next(row for row in rows["Carrier.cs"]["types"] if row["fullName"] == "Game.Carrier")
        self.assertEqual(carrier["fullName"], "Game.Carrier")
        self.assertEqual(carrier["baseType"], "UnityEngine.MonoBehaviour")
        self.assertTrue(carrier["fieldCarrier"])
        self.assertFalse(carrier["schemaOnly"], "field initializers keep strict schema-only classification false")
        values = next(field for field in carrier["fields"] if field["name"] == "values")
        self.assertTrue(values["type"].startswith("System.Collections.Generic.List`1[[System.Int32[], System.Runtime, Version="), values["type"])
        self.assertTrue(values["type"].endswith(", Culture=neutral, PublicKeyToken=b03f5f7f11d50a3a]]"), values["type"])
        self.assertTrue(values["serialized"])
        self.assertEqual(next(f for f in carrier['fields'] if f['name']=='items')['assembly'],'UnityStubs')
        self.assertTrue(any(dep["path"] == "Carrier.cs" for dep in rows["UseCarrier.cs"]["dependencies"]))
        self.assertFalse(any(dep["path"] == "IslandB.cs" for dep in rows["IslandA.cs"]["dependencies"]))
        self.assertFalse(any(dep["path"] == "IslandA.cs" for dep in rows["IslandB.cs"]["dependencies"]))
        late_bound = rows["Lookups.cs"]["lateBoundDependencies"]
        self.assertEqual(len(late_bound), 1)
        self.assertIn("System.Type.GetType", late_bound[0]["symbol"])
        self.assertEqual(late_bound[0]["stringValues"], ["Game.Carrier"])
        self.assertFalse(rows["Carrier.cs"]["editorOnly"], "UNITY_EDITOR alone does not make a runtime compile input editor-only")
        self.assertTrue(rows["Carrier.cs"]["editorEvidence"]["definesUnityEditor"])


if __name__ == "__main__":
    unittest.main()
