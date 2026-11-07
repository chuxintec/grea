"""Qa development command declarations and orchestration.

Algorithms and transaction guards remain in grea.development.
"""

ROUTES = {"debug": "debug", "player": "player", "qa": ""}


def register(sub, *, include_intake_plan=True):
    debug = sub.add_parser("debug").add_subparsers(dest="action", required=True)
    ds = debug.add_parser("start")
    ds.add_argument("--manifest", required=True)
    ds.add_argument("--expected", required=True)
    ds.add_argument("--out", required=True)
    ds.add_argument("--duration", type=int, default=3600)
    ds.add_argument("--width", type=int)
    ds.add_argument("--height", type=int)
    ds.add_argument("--observation-spec")
    ds.add_argument("--expected-observation")
    ds.add_argument("--deadline-utc")
    for name in ("inspect", "stop", "tail", "screenshot"):
        d = debug.add_parser(name)
        d.add_argument("--session", required=True)
        if name == "tail":
            d.add_argument("--lines", type=int, default=80)
        if name == "screenshot":
            d.add_argument("--input", required=True)
            d.add_argument("--expected", required=True)
    dt = debug.add_parser("target")
    dt.add_argument("--transaction", required=True)
    player = sub.add_parser("player").add_subparsers(dest="action", required=True)
    player_run = player.add_parser("run")
    player_run.add_argument("--manifest", required=True)
    player_run.add_argument("--out", required=True)
    player_run.add_argument("--duration", type=int, default=10)
    player_run.add_argument("--expected-manifest", required=True)
    qa = sub.add_parser("qa").add_subparsers(dest="action", required=True)
    qp = qa.add_parser("prepare")
    qp.add_argument("--spec", required=True)
    qp.add_argument("--expected-spec", required=True)
    qp.add_argument("--out")
    for action in ("launch", "collect"):
        q = qa.add_parser(action)
        for field in ("project", "build", "profile", "expected-owner"):
            q.add_argument("--" + field, required=True)
        q.add_argument("--run")
        if action == "launch":
            q.add_argument("--duration", type=int, default=60)
        else:
            q.add_argument("--out")
    for action in ("inspect-instance", "bind"):
        q = qa.add_parser(action)
        for field in ("project", "build", "profile", "expected-owner", "run", "out"):
            q.add_argument("--" + field, required=True)
        if action == "bind":
            q.add_argument("--backend", default="macos-native-ax-pid/1")
            q.add_argument("--window", type=int)
    qi = qa.add_parser("input")
    for field in ("session", "expected-session", "spec", "expected-spec", "out"):
        qi.add_argument("--" + field, required=True)
    qvp = qa.add_parser("virtual-prepare")
    for field in ("spec", "expected-spec", "out"):
        qvp.add_argument("--" + field, required=True)
    qvb = qa.add_parser("virtual-bind")
    for field in ("project", "build", "profile", "expected-owner", "run", "channel", "expected-channel", "out"):
        qvb.add_argument("--" + field, required=True)
    for action in ("virtual-input", "virtual-status", "virtual-stop"):
        qv = qa.add_parser(action)
        for field in ("session", "expected-session", "out"):
            qv.add_argument("--" + field, required=True)
        if action == "virtual-input":
            for field in ("spec", "expected-spec"):
                qv.add_argument("--" + field, required=True)


def dispatch(a):
    if a.command == "debug":
        from grea.development.debug import start, inspect_session, stop, tail, screenshot_record, inspect_native

        if a.action == "target":
            return inspect_native(a.transaction)
        if a.action == "start":
            return start(
                a.manifest,
                a.out,
                a.expected,
                a.duration,
                a.width,
                a.height,
                observation_spec=a.observation_spec,
                expected_observation=a.expected_observation,
                deadline_utc=a.deadline_utc,
            )
        if a.action == "inspect":
            return inspect_session(a.session)
        if a.action == "stop":
            return stop(a.session)
        if a.action == "tail":
            return tail(a.session, a.lines)
        return screenshot_record(a.session, a.input, a.expected)
    if a.command == "player":
        from grea.development.player import run

        return run(a.manifest, a.out, a.duration, a.expected_manifest)
    if a.command == "qa":
        if a.action.startswith("virtual-"):
            from grea.development import qa_virtual_pointer as virtual

            if a.action == "virtual-prepare":
                return virtual.prepare(a.spec, a.expected_spec, a.out)
            if a.action == "virtual-bind":
                return virtual.bind(
                    a.project, a.build, a.profile, a.expected_owner, a.run, a.channel, a.expected_channel, a.out
                )
            if a.action == "virtual-input":
                return virtual.input_event(a.session, a.expected_session, a.spec, a.expected_spec, a.out)
            if a.action == "virtual-status":
                return virtual.status(a.session, a.expected_session, a.out)
            if a.action == "virtual-stop":
                return virtual.stop(a.session, a.expected_session, a.out)
        from grea.development.qa_runtime import prepare, launch, collect
        from grea.development.qa_binding import inspect_instance, bind, input_event

        if a.action == "prepare":
            return prepare(a.spec, a.expected_spec, a.out)
        if a.action == "launch":
            return launch(a.project, a.build, a.profile, a.expected_owner, a.duration, a.run)
        if a.action == "inspect-instance":
            return inspect_instance(a.project, a.build, a.profile, a.expected_owner, a.run, a.out)
        if a.action == "bind":
            return bind(a.project, a.build, a.profile, a.expected_owner, a.run, a.out, a.window, a.backend)
        if a.action == "input":
            return input_event(a.session, a.expected_session, a.spec, a.expected_spec, a.out)
        return collect(a.project, a.build, a.profile, a.expected_owner, a.run, a.out)
    raise ValueError(f"Unknown development command: {a.command}")
