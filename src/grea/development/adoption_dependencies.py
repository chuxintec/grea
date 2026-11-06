"""Validate producer-declared compile dependencies in an adoption manifest.

This checks declaration shape and file membership only. It does not parse C#,
infer compiler behavior, or claim that a producer declared every dependency.
"""

import unicodedata

from .errors import fail


_DECLARATION_KEYS = {"schemaVersion", "coverage", "edges"}
_EDGE_KEYS = {"path", "requires", "kind"}
_FORBIDDEN_PATH_CHARS = set('<>:"|?*\\')


def _valid_source_path(value, location):
    if not isinstance(value, str) or not value:
        fail("ADOPTION_DEPENDENCIES_PATH", location, "Expected a non-empty source path")
    if value != unicodedata.normalize("NFC", value):
        fail("ADOPTION_DEPENDENCIES_PATH", location, "Path must use NFC Unicode normalization")
    if value.startswith("/") or "\\" in value or "\x00" in value:
        fail("ADOPTION_DEPENDENCIES_PATH", location, "Expected a safe slash-separated relative path")
    parts = value.split("/")
    if len(parts) < 2 or parts[0] != "Assets":
        fail("ADOPTION_DEPENDENCIES_PATH", location, "Source path must be under Assets/")
    for part in parts:
        if part in ("", ".", "..") or part.endswith((".", " ")):
            fail("ADOPTION_DEPENDENCIES_PATH", location, "Path contains a non-canonical segment")
        if any(ord(char) < 32 or ord(char) == 127 or char in _FORBIDDEN_PATH_CHARS for char in part):
            fail("ADOPTION_DEPENDENCIES_PATH", location, "Path contains an unsafe character")
    if value.endswith(".meta") or not value.endswith(".cs"):
        fail("ADOPTION_DEPENDENCIES_PATH", location, "csharp-compile paths must name a .cs source file")
    return value


def validate_dependencies(manifest, files):
    """Return a normalized producer declaration after validating its file closure.

    ``manifest`` is the already-snapshotted manifest mapping. ``files`` maps
    manifest paths to their rows. An absent declaration is surfaced explicitly
    as ``status='undeclared'`` and never treated as complete coverage.
    """
    if not isinstance(manifest, dict):
        fail("ADOPTION_DEPENDENCIES_MANIFEST", "manifest", "Expected a manifest object")
    if not isinstance(files, dict):
        fail("ADOPTION_DEPENDENCIES_FILES", "files", "Expected a path-to-row mapping")

    if "adoptionDependencies" not in manifest:
        return dict(status="undeclared", coverage=None, edges=[])

    declaration = manifest["adoptionDependencies"]
    if not isinstance(declaration, dict):
        fail("ADOPTION_DEPENDENCIES_SCHEMA", "adoptionDependencies", "Expected an object")
    if set(declaration) != _DECLARATION_KEYS:
        fail("ADOPTION_DEPENDENCIES_SCHEMA", "adoptionDependencies", "Expected exactly schemaVersion, coverage, and edges")
    if type(declaration["schemaVersion"]) is not int or declaration["schemaVersion"] != 1:
        fail("ADOPTION_DEPENDENCIES_SCHEMA", "adoptionDependencies.schemaVersion", "Expected integer schema version 1")
    if declaration["coverage"] != "producer-declared":
        fail("ADOPTION_DEPENDENCIES_SCHEMA", "adoptionDependencies.coverage", "Expected producer-declared coverage")
    if not isinstance(declaration["edges"], list):
        fail("ADOPTION_DEPENDENCIES_SCHEMA", "adoptionDependencies.edges", "Expected an array")

    edges = []
    seen_consumers = set()
    for index, edge in enumerate(declaration["edges"]):
        location = f"adoptionDependencies.edges[{index}]"
        if not isinstance(edge, dict) or set(edge) != _EDGE_KEYS:
            fail("ADOPTION_DEPENDENCIES_SCHEMA", location, "Expected exactly path, requires, and kind")
        consumer = _valid_source_path(edge["path"], location + ".path")
        if consumer in seen_consumers:
            fail("ADOPTION_DEPENDENCIES_DUPLICATE", location + ".path", "Consumer path is declared more than once")
        seen_consumers.add(consumer)
        if edge["kind"] != "csharp-compile":
            fail("ADOPTION_DEPENDENCIES_SCHEMA", location + ".kind", "Expected csharp-compile")
        if not isinstance(edge["requires"], list):
            fail("ADOPTION_DEPENDENCIES_SCHEMA", location + ".requires", "Expected an array of source paths")

        requires = []
        seen_requirements = set()
        for requirement_index, raw_path in enumerate(edge["requires"]):
            requirement = _valid_source_path(raw_path, f"{location}.requires[{requirement_index}]")
            if requirement == consumer:
                fail("ADOPTION_DEPENDENCIES_SELF_EDGE", location, "A source cannot require itself")
            if requirement in seen_requirements:
                fail("ADOPTION_DEPENDENCIES_DUPLICATE", location + ".requires", "Required path is repeated")
            seen_requirements.add(requirement)
            requires.append(requirement)

        for path in (consumer, *requires):
            if path not in files:
                fail("ADOPTION_DEPENDENCIES_MISSING_FILE", path, "Declared source is absent from manifest.files")
        edges.append(dict(path=consumer, requires=sorted(requires), kind="csharp-compile"))

    edges.sort(key=lambda item: item["path"])
    return dict(status="declared", schemaVersion=1, coverage="producer-declared", edges=edges)
