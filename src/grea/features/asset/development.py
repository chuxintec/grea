"""Asset development command declarations and orchestration.

Algorithms and transaction guards remain in grea.development.
"""

ROUTES = {"image": "image", "resource": "resource", "references": "references"}


def register(sub, *, include_intake_plan=True):
    image = sub.add_parser("image").add_subparsers(dest="action", required=True)
    image_inspect = image.add_parser("inspect")
    image_inspect.add_argument("--input", required=True)
    compress = image.add_parser("compress")
    compress.add_argument("--input", required=True)
    compress.add_argument("--output", required=True)
    compress.add_argument("--apply", action="store_true")
    compress.add_argument("--expected-source")
    resources = sub.add_parser("resource").add_subparsers(dest="action", required=True)
    ri = resources.add_parser("image-inspect")
    ri.add_argument("--input", required=True)
    rp = resources.add_parser("image-produce")
    rp.add_argument("--input", required=True)
    rp.add_argument("--out", required=True)
    rp.add_argument("--policy", required=True)
    rp.add_argument("--expected-source", required=True)
    rv = resources.add_parser("validate-step")
    rv.add_argument("--project", required=True)
    rv.add_argument("--spec", required=True)
    refs = sub.add_parser("references")
    refs.add_argument("--project", required=True)
    refs.add_argument("--out", required=True)
    refs.add_argument("--cache")


def dispatch(a):
    if a.command == "image":
        from grea.development.images import inspect, compress

        return inspect(a.input) if a.action == "inspect" else compress(a.input, a.output, a.apply, a.expected_source)
    if a.command == "resource":
        from grea.development.resources import inspect_image, produce_image, validate_step, declared_paths
        from grea.development.io import load, read

        if a.action == "image-inspect":
            return dict(status="ok", **inspect_image(a.input))
        if a.action == "image-produce":
            return produce_image(a.input, a.out, load(read(a.policy)), a.expected_source)
        step = validate_step(load(read(a.spec)))
        return dict(status="ok", step=step, paths=declared_paths(a.project, step), native="not_run")
    if a.command == "references":
        from grea.development.references import inspect_graph

        result = inspect_graph(a.project, a.out, a.cache)
        return dict(
            status=result["status"],
            report=result["report"],
            counts=result["counts"],
            timingMs=result["timingMs"],
            indexedGuids=len(result["guidToPath"]),
            dependencySources=len(result["dependencies"]),
            literalLoads=len(result["literalLoads"]),
            unknownDynamicLoads=len(result["unknownDynamicLoads"]),
            unresolvedJsonStrings=len(result["unresolvedJsonStrings"]),
            limitations=result["limitations"],
        )
    raise ValueError(f"Unknown development command: {a.command}")
