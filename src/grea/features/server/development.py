"""Server development command declarations and orchestration.

Algorithms and transaction guards remain in grea.development.
"""

ROUTES = {"server": ""}


def register(sub, *, include_intake_plan=True):
    server = sub.add_parser("server").add_subparsers(dest="action", required=True)
    server.add_parser("toolchain")
    si = server.add_parser("inspect")
    si.add_argument("--project", required=True)
    for name in ("generate", "module-generate", "compose-plan"):
        item = server.add_parser(name)
        item.add_argument("--spec", required=True)
        item.add_argument("--out", required=True)
    sm = server.add_parser("module-plan")
    sm.add_argument("--project", required=True)
    sm.add_argument("--spec", required=True)
    sm.add_argument("--out", required=True)
    sd = server.add_parser("protocol-diff")
    sd.add_argument("--before", required=True)
    sd.add_argument("--after", required=True)
    sg = server.add_parser("migration-plan")
    sg.add_argument("--project", required=True)
    sg.add_argument("--out", required=True)
    sb = server.add_parser("check")
    sb.add_argument("--project", required=True)
    sb.add_argument("--package", action="append")
    scb = server.add_parser("build")
    scb.add_argument("--project", required=True)
    scb.add_argument("--architecture", choices=("arm64", "amd64"), default="arm64")
    spt = server.add_parser("protocol-tools")
    spt.add_argument("--out", required=True)
    sms = server.add_parser("migration-state")
    sms.add_argument("--compose", required=True)
    sms.add_argument("--project-name", required=True)
    sms.add_argument("--owner", required=True, choices=("login", "server", "chat", "world", "billing"))
    sri = server.add_parser("runtime-inspect")
    sri.add_argument("--compose", required=True)
    sri.add_argument("--project-name", required=True)
    sri.add_argument("--gateway-port", required=True, type=int)
    sma = server.add_parser("migration-apply")
    sma.add_argument("--project", required=True)
    sma.add_argument("--plan", required=True)
    sma.add_argument("--compose", required=True)
    sma.add_argument("--project-name", required=True)
    sma.add_argument("--owner", required=True, choices=("login", "server", "chat", "world", "billing"))
    sma.add_argument("--expected-state", required=True)


def dispatch(a):
    if a.command == "server":
        from grea.development import server_go as server
        from grea.development.io import load, read

        if a.action == "toolchain":
            return server.toolchain_inspect()
        if a.action == "inspect":
            return server.inspect(a.project)
        if a.action == "generate":
            return server.generate(load(read(a.spec)), a.out)
        if a.action == "module-generate":
            return server.generate_module(load(read(a.spec)), a.out)
        if a.action == "module-plan":
            return server.module_plan(a.project, load(read(a.spec)), a.out)
        if a.action == "compose-plan":
            return server.compose_plan(load(read(a.spec)), a.out)
        if a.action == "protocol-diff":
            return server.protocol_diff(a.before, a.after)
        if a.action == "migration-plan":
            return server.migration_plan(a.project, a.out)
        if a.action == "build":
            return server.build_candidate(a.project, a.architecture)
        if a.action == "protocol-tools":
            return server.prepare_protocol_tools(a.out)
        if a.action == "migration-state":
            return server.inspect_migration_state(a.compose, a.project_name, a.owner)
        if a.action == "runtime-inspect":
            return server.inspect_compose_runtime(a.compose, a.project_name, a.gateway_port)
        if a.action == "migration-apply":
            return server.execute_migrations(a.project, a.plan, a.compose, a.project_name, a.owner, a.expected_state)
        return server.build_diagnostics(a.project, a.package)
    raise ValueError(f"Unknown development command: {a.command}")
