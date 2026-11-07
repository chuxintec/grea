"""Config recovery command declarations and orchestration.

Algorithms and transaction guards remain in grea.recovery.
"""

import zipfile
from grea.recovery.sources.compiled import fail

ROUTES = {"query-tables": "query-tables"}


def register(sub, *, include_intake_plan=True):
    p = sub.add_parser("query-tables", help="Inspect exact frozen evidence; no source program execution")
    p.add_argument("--source", required=False)
    p.add_argument("--member", help="Exact ZIP member; expected SHA identifies member bytes, not the outer ZIP")
    p.add_argument("--expected-sha", required=False)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--out", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--expected-manifest-sha", required=True)
    p.add_argument("--contains", default="")
    p.add_argument("--extract")


def dispatch(args, *, usage_parser):
    if args.command == "query-tables":
        from grea.recovery.evidence_queries import query_tables

        try:
            result = query_tables(
                args.manifest,
                args.expected_manifest_sha,
                args.out,
                source=args.source,
                expected=args.expected_sha,
                member=args.member,
                contains=args.contains,
                extract=args.extract,
                limit=args.limit,
            )
        except (zipfile.BadZipFile, EOFError) as error:
            fail("EVIDENCE_ARCHIVE", args.source or args.manifest, str(error))
        return (
            dict(status=result["status"], operation=result["operation"], report=str(args.out) + "/inspection.json"),
            0,
        )
    raise ValueError(f"Unknown recovery command: {args.command}")
