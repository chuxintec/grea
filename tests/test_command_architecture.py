"""Protect command ownership and the boundaries exercised by bulk recovery."""

import argparse
import ast
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from grea.commands.catalog import collect, commands
from grea.commands.interface import route
from grea.commands.model import Command, leaves, parameters
from grea.commands.result import CommandResult
from grea.features.catalog import core_owners, feature_modules, stage_modules


ROOT = Path(__file__).resolve().parents[1] / "src/grea"


class ArchitectureTests(unittest.TestCase):
    def test_transport_has_no_stage_imports_or_backend_dispatch(self):
        for file in (ROOT / "commands").glob("*.py"):
            tree = ast.parse(file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertFalse((node.module or "").startswith(("grea.recovery", "grea.development")), file)
                if isinstance(node, ast.Attribute):
                    self.assertNotEqual(node.attr, "backend", file)
        for stage in ("recovery", "development"):
            for module in stage_modules(stage):
                tree = ast.parse(Path(module.__file__).read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        self.assertNotIn(node.module, ("grea.recovery.cli", "grea.development.cli"))

    def test_new_module_action_needs_no_central_dispatch_edit(self):
        cmd = Command(
            "prefab",
            "fixture",
            (),
            argparse.ArgumentParser(),
            {},
            "",
            lambda args, raw, parser: CommandResult({"sourceObjects": 12}, 1),
        )
        provider = SimpleNamespace(declared_commands=lambda: [cmd])
        catalog = collect([("prefab", provider)])
        result = catalog["prefab", "fixture"].handler(None, [], cmd.parser)
        self.assertEqual((result.value, result.exit_code), ({"sourceObjects": 12}, 1))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            collect([("prefab", provider), ("prefab", provider)])
        with self.assertRaisesRegex(ValueError, "Invalid"):
            collect([("asset", provider)])

    def test_every_core_operation_has_exactly_one_feature_owner(self):
        from grea.contracts import CONTRACTS

        self.assertEqual(set(core_owners()), set(CONTRACTS))
        self.assertEqual({name for name, _ in feature_modules()}, {cmd.module for cmd in commands().values()})
        from grea.commands.groups import CORE_MODULE, HELPER_MODULE
        from grea.features.catalog import helper_owners

        self.assertEqual(CORE_MODULE, core_owners())
        self.assertEqual(HELPER_MODULE, helper_owners())

    def test_public_and_legacy_parsers_share_parameters_without_alias_leaks(self):
        from grea.recovery.cli import parser as recovery_parser
        from grea.development.cli import parser as development_parser

        for stage, factory in (("recovery", recovery_parser), ("development", development_parser)):
            legacy = {path: (defaults, leaf) for path, defaults, leaf, _ in leaves(factory())}
            original_flags = {path: tuple(leaf._option_string_actions) for path, (_, leaf) in legacy.items()}
            for module in stage_modules(stage):
                domain = module.__name__.split(".")[-2]
                for path, (defaults, parser) in legacy.items():
                    if path[0] not in module.ROUTES or module.ROUTES[path[0]] is None:
                        continue
                    action = "-".join(x for x in (module.ROUTES[path[0]], *path[1:]) if x)
                    public = commands()[domain, action]
                    with self.subTest(stage=stage, action=action):
                        self.assertEqual(defaults, public.defaults)
                        self.assertIsNot(parser, public.parser)
                        self.assertEqual(parameters(parser), parameters(public.parser))
                        self.assertEqual(tuple(parser._option_string_actions), original_flags[path])
                        if "--out" in parser._option_string_actions:
                            self.assertIsNot(
                                parser._option_string_actions["--out"], public.parser._option_string_actions["--out"]
                            )

    def test_implementation_pin_includes_moved_commands_and_ignores_caches(self):
        from grea.development import implementation

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("development/core.py", "features/prefab/development.py", "commands/model.py"):
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("initial")
            (root / "development" / implementation.SCOPE_FILE).write_text(json.dumps(implementation.SCOPE))
            with patch.object(implementation, "__file__", str(root / "development/implementation.py")):
                before = implementation.identity()
                (root / "features/prefab/development.py").write_text("changed handler")
                after = implementation.identity()
                self.assertNotEqual(before, after)
                (root / "commands/model.py").write_text("changed arguments")
                self.assertNotEqual(after, implementation.identity())
                after = implementation.identity()
                cache = root / "features/prefab/__pycache__/development.pyc"
                cache.parent.mkdir()
                cache.write_bytes(b"cache")
                self.assertEqual(after, implementation.identity())

    def test_historical_runtime_pin_format_is_preserved_without_executing_it(self):
        from grea.development.implementation import inventory, SCOPE_FILE, SCOPE
        from grea.development.errors import BeaverError
        from grea.development.io import sha

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            runtime = root / "legacy-runtime"
            runtime.mkdir()
            raw = b"raise AssertionError('never import supplied runtime')"
            (runtime / "implementation.py").write_bytes(raw)
            self.assertEqual(inventory(runtime), {"implementation.py": sha(raw)})
            (runtime / SCOPE_FILE).write_text(json.dumps(SCOPE))
            with self.assertRaises(BeaverError):
                inventory(runtime)


class StructuredExecutionTests(unittest.TestCase):
    def public(self, arguments):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = route(arguments)
        return code, json.loads(output.getvalue())

    def test_recovery_capabilities_describe_the_same_legacy_surface(self):
        from grea.recovery.cli import parser

        code, receipt = self.public(["system", "recovery-capabilities"])
        roots = next(a.choices for a in parser()._actions if isinstance(a, argparse._SubParsersAction))
        self.assertEqual(code, 0)
        self.assertEqual(receipt["result"]["implemented"], sorted(roots))

    def test_binding_export_can_read_exact_flat_historical_runtime(self):
        import shutil
        import grea.development as development
        from grea.development.implementation import inventory, SCOPE_FILE
        from grea.development.intake_bindings import export_existing
        from grea.development.io import encoded, sha, write_json
        from tests.development.test_intake_binding_export import BindingExportTests

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            runtime = root / "old-runtime"
            shutil.copytree(
                Path(development.__file__).parent, runtime, ignore=shutil.ignore_patterns("__pycache__", SCOPE_FILE)
            )
            producer = sha(encoded(inventory(runtime)))
            with patch("grea.development.intake_bindings.identity", return_value=producer):
                fixture = BindingExportTests().fixture(root)
            stage, plan = fixture["stage"], fixture["plan"]
            expected = sha(encoded(plan))
            for index, mode in enumerate(("apply", "verify")):
                write_json(
                    stage / (mode + "-process.json"),
                    dict(pid=12345 + index, exited=True, exitCode=0, interrupted=False),
                )
            before = inventory(runtime)
            result = export_existing(stage, expected, runtime, producer, root / "continued")
            self.assertEqual(result["native"], "verified-original-gates-reused")
            self.assertFalse(result["editorStarted"])
            self.assertEqual(inventory(runtime), before)

    def test_recovery_and_development_do_not_roundtrip_through_stdout(self):
        from grea.recovery.io import encoded, sha
        from grea.recovery.cli import main as legacy

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / "methods.json"
            source.write_bytes(encoded([dict(type=".ActorHp", name="UpdateHp", module="main", function=9)]))
            original = source.read_bytes()
            base = ["--source", str(source), "--expected-sha", sha(original)]
            with patch("grea.features.adapters.printed_result", side_effect=AssertionError("stdout adapter called")):
                code, receipt = self.public(["code", "query-methods", *base, "--output", str(root / "public")])
                self.assertEqual((code, receipt["status"]), (0, "ok"))
                query = root / "request.json"
                query.write_text(
                    json.dumps(dict(source=str(source), expected_sha=sha(original), output=str(root / "request")))
                )
                code, requested = self.public(["--request", str(query), "code", "query-methods"])
                self.assertEqual(code, 0)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(legacy(["query-methods", *base, "--out", str(root / "legacy")]), 0)
                for folder in ("public", "request", "legacy"):
                    report = json.loads((root / folder / "inspection.json").read_text())
                    self.assertEqual(report["rows"][0]["name"], "UpdateHp")
                    self.assertTrue(report["sources"][0]["verified"])
                self.assertEqual(source.read_bytes(), original)
                code, _ = self.public(["system", "version"])
                self.assertEqual(code, 0)
                code, bad = self.public(
                    [
                        "code",
                        "query-methods",
                        "--source",
                        str(source),
                        "--expected-sha",
                        "0" * 64,
                        "--output",
                        str(root / "refused"),
                    ]
                )
                self.assertEqual((code, bad["status"], bad["result"]), (2, "error", None))
                self.assertEqual(json.loads(bad["diagnostics"])["status"], "error")
                self.assertFalse((root / "refused").exists())
