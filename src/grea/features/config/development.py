"""Config development command declarations and orchestration.

Algorithms and transaction guards remain in grea.development.
"""

ROUTES = {"config": "", "config3": "schema"}


def register(sub, *, include_intake_plan=True):
    config = sub.add_parser("config").add_subparsers(dest="action", required=True)
    validate = config.add_parser("validate")
    validate.add_argument("--schema", required=True)
    validate.add_argument("--input", required=True)
    generate = config.add_parser("generate")
    generate.add_argument("--schema", required=True)
    generate.add_argument("--out", required=True)
    config3 = sub.add_parser("config3").add_subparsers(dest="action", required=True)
    cv = config3.add_parser("validate")
    cv.add_argument("--schema", required=True)
    cv.add_argument("--input", required=True)
    cv.add_argument("--tables")
    cv.add_argument("--project")
    cg = config3.add_parser("generate")
    cg.add_argument("--schema", required=True)
    cg.add_argument("--out", required=True)
    cc = config3.add_parser("compare")
    cc.add_argument("--before-schema", required=True)
    cc.add_argument("--after-schema", required=True)
    cc.add_argument("--before-input")
    cc.add_argument("--after-input")


def dispatch(a):
    if a.command == "config":
        from grea.development.configuration import validate, generate

        return validate(a.schema, a.input) if a.action == "validate" else generate(a.schema, a.out)
    if a.command == "config3":
        from grea.development.configuration_v3 import validate, generate, compare
        from grea.development.io import load, read

        if a.action == "validate":
            return validate(a.schema, a.input, load(read(a.tables)) if a.tables else None, a.project)
        if a.action == "generate":
            return generate(a.schema, a.out)
        return compare(a.before_schema, a.after_schema, a.before_input, a.after_input)
    raise ValueError(f"Unknown development command: {a.command}")
