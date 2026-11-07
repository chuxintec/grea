"""Research recovery command declarations and orchestration.

Algorithms and transaction guards remain in grea.recovery.
"""

ROUTES = {"research-matrix": "matrix"}


def register(sub, *, include_intake_plan=True):
    p = sub.add_parser(
        "research-matrix", help="Discover every Research game without converting or following external sources"
    )
    p.add_argument("--root", required=True)
    p.add_argument("--out", required=True)


def dispatch(args, *, usage_parser):
    if args.command == "research-matrix":
        from grea.recovery.research_cases import discover

        return (discover(args.root, args.out), 0)
    raise ValueError(f"Unknown recovery command: {args.command}")
