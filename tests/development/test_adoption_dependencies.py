import unittest

from grea.development.adoption_dependencies import validate_dependencies
from grea.development.errors import BeaverError


CONSUMER = "Assets/Game/Consumer.cs"
PROVIDER = "Assets/Game/Provider.cs"


def declaration(edges):
    return {
        "schemaVersion": 1,
        "coverage": "producer-declared",
        "edges": edges,
    }


def edge(path=CONSUMER, requires=None, **extra):
    value = {"path": path, "requires": list(requires or []), "kind": "csharp-compile"}
    value.update(extra)
    return value


class AdoptionDependencyTests(unittest.TestCase):
    def test_undeclared_is_explicit_and_not_complete(self):
        result = validate_dependencies({}, {})
        self.assertEqual(result, {"status": "undeclared", "coverage": None, "edges": []})

    def test_missing_member_blocks_declared_dependency_closure(self):
        manifest = {"adoptionDependencies": declaration([edge(requires=[PROVIDER])])}
        with self.assertRaises(BeaverError) as caught:
            validate_dependencies(manifest, {CONSUMER: {"path": CONSUMER}})
        self.assertEqual(caught.exception.code, "ADOPTION_DEPENDENCIES_MISSING_FILE")
        self.assertEqual(caught.exception.location, PROVIDER)

    def test_valid_cycles_are_allowed_and_output_is_canonical(self):
        manifest = {
            "adoptionDependencies": declaration([
                edge(path=PROVIDER, requires=[CONSUMER]),
                edge(path=CONSUMER, requires=[PROVIDER]),
            ])
        }
        result = validate_dependencies(manifest, {CONSUMER: {}, PROVIDER: {}})
        self.assertEqual(result["status"], "declared")
        self.assertEqual([item["path"] for item in result["edges"]], [CONSUMER, PROVIDER])
        self.assertEqual(result["edges"][0]["requires"], [PROVIDER])

    def test_rejects_unsafe_noncanonical_and_non_source_paths(self):
        for unsafe in (
            "Assets/../Provider.cs",
            "Assets\\Game\\Provider.cs",
            "/Assets/Game/Provider.cs",
            "Assets/Game/Provider.cs.meta",
            "Assets/Game/Provider.txt",
        ):
            with self.subTest(path=unsafe), self.assertRaises(BeaverError):
                validate_dependencies(
                    {"adoptionDependencies": declaration([edge(requires=[unsafe])])},
                    {CONSUMER: {}, unsafe: {}},
                )

    def test_rejects_unknown_fields_repeated_edges_and_self_edges(self):
        bad_declarations = [
            {**declaration([]), "complete": True},
            declaration([edge(extra=True)]),
            declaration([edge(), edge()]),
            declaration([edge(requires=[CONSUMER])]),
            declaration([edge(requires=[PROVIDER, PROVIDER])]),
        ]
        for bad in bad_declarations:
            with self.subTest(declaration=bad), self.assertRaises(BeaverError):
                validate_dependencies(
                    {"adoptionDependencies": bad}, {CONSUMER: {}, PROVIDER: {}}
                )


if __name__ == "__main__":
    unittest.main()
