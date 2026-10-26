"""Versioned JSON CLI. No shell passthrough and no automatic provider installs."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import uuid
from . import __version__
from .errors import BeaverError, fail
from .io import sha, encoded


def implementation_identity():
    root = Path(__file__).parent
    return sha(encoded({p.relative_to(root).as_posix(): sha(p.read_bytes())
                        for p in sorted(root.rglob("*")) if p.suffix in (".py", ".cs")}))


def capabilities():
    capabilities = [
        dict(id='batch.plan',state='implemented',effects='plan-output',verification='scoped hashes, dependency/compilation inputs; cache is not authority'),
        dict(id='batch.apply',state='requires_provider',provider='Unity 6000.6.2f1 + project uGUI/TMP',effects='declared-project-write',verification='one Editor process; native checkpoint and serialized save/reload checks'),
        dict(id='batch.recover',state='requires_provider',provider='same pinned beaver + Unity 6000.6.2f1',effects='hash-owned-restore',verification='exact witnessed after state required; later edits and missing checkpoints block'),
        dict(id='references',state='implemented',effects='read-and-index-output',verification='static GUID graph, literal spans, unknown dynamic keys; incremental cache'),
        dict(id='debug.start',state='implemented',effects='owned-budgeted-process',verification='fixed candidate manifest; asynchronous worker'),
        dict(id='debug.inspect',state='implemented',effects='read',verification='PID/executable/start/marker identity; unknown probes remain partial'),
        dict(id='debug.target',state='implemented',effects='read',verification='pinned Editor/PlayMode transaction evidence; no external attachment'),
        dict(id='debug.stop',state='implemented',effects='own-worker-stop-request',verification='worker Popen child ownership; no arbitrary PID signals'),
        dict(id='debug.tail',state='implemented',effects='read',verification='bounded redacted own session log'),
        dict(id='debug.screenshot',state='implemented',effects='evidence-registration',verification='caller supplied hash only; screenshot origin not authenticated'),
        dict(id="project.inspect", state="implemented", effects="read", verification="python"),
        dict(id="adoption.plan", state="implemented", effects="plan-output", engines=["unity-6000.6.2f1", "creator-3.8.8"], verification="python; large isolated Unity manifest preview"),
        dict(id="adoption.apply", state="requires_provider", provider="Unity 6000.6.2f1", effects="project-write", verification="native add/move/save/reopen and interrupted-import fixture"),
        dict(id="adoption.rollback", state="requires_provider", provider="Unity 6000.6.2f1", effects="project-write", verification="native normal/failed transaction restore; later-edit rejection"),
        dict(id="unity.plan", state="implemented", effects="plan-output", verification="python; exact source and implementation identity"),
        dict(id="unity.ui.create", state="requires_provider", provider="Unity 6000.6.2f1 + uGUI/TMP Essentials + explicit font", effects="project-write", verification="native save/reopen/source audit"),
        dict(id="unity.prefab.inspect", state="requires_provider", provider="Unity 6000.6.2f1", effects="temporary-editor-helper", verification="native hierarchy/localID/component/importer readback"),
        dict(id="unity.prefab.edit", state="requires_provider", provider="Unity 6000.6.2f1", effects="project-write", verification="native text/component/Sprite binding save/reopen"),
        dict(id="unity.assets.move", state="requires_provider", provider="Unity 6000.6.2f1", effects="project-write", verification="native GUID/localID and save/reopen"),
        dict(id="unity.project.import", state="requires_provider", provider="Unity 6000.6.2f1", effects="declared-meta-initialization", verification="native generated C# compile and import"),
        dict(id="unity.sprite.configure", state="requires_provider", provider="Unity 6000.6.2f1", effects="selected-importer-meta", verification="native importer/GUID/localID and save/reopen"),
        dict(id="unity.validate.play", state="requires_provider", provider="Unity 6000.6.2f1", effects="bounded-playmode", verification="3-second isolated scene; zero runtime errors"),
        dict(id="unity.build.macos", state="requires_provider", provider="Unity 6000.6.2f1 + Mac module", effects="create-only-artifact", verification="native BuildPipeline; unchanged source; artifact manifest"),
        dict(id="player.run", state="implemented", effects="bounded-owned-process", verification="hash-bound macOS artifact launch; application verdict remains separate"),
        dict(id="image.inspect", state="requires_provider", provider="Pillow", effects="read", verification="exact RGBA/alpha fixture"),
        dict(id="image.compress", state="requires_provider", provider="Pillow", effects="create-only", verification="lossless PNG stream and exact decoded RGBA"),
        dict(id="config.validate", state="implemented", effects="read", verification="strict scalar JSON; native runtime rejects missing/wrong-type fields"),
        dict(id="config.generate", state="implemented", effects="create-only", verification="generated C# compiled; runtime TextAsset JSON reader"),
        dict(id="code.inspect", state="implemented", effects="read", verification="static asmdef/using inventory; unresolved optional constraints remain partial"),
        dict(id="payload.verify", state="implemented", effects="read", verification="shared file/alias/inode/collision checks; also used by build and Player"),
        dict(id="payload.plan", state="implemented", effects="plan-output", verification="explicit source/override identities and alias redirection"),
        dict(id="payload.apply", state="implemented", effects="new-independent-payload", verification="macOS independent-copy and atomic no-replace fixtures; Linux/Windows promotion not_run"),
        dict(id="creator.apply", state="not_supported", effects="none", verification="explicit rejection before provider lookup"),
        dict(id="creator.build", state="not_supported", effects="none", verification="not_run")
    ]
    return dict(contract="beaver-capabilities/1", capabilities=capabilities, requiredProviders=[],
                nativeOperationContract="beaver-unity/1", batchOperationContract='beaver-batch/2',batchTransactionContract='beaver-batch-transaction/2',adoptionContract="beaver-adopt/1",
                limitations=["Provider readiness is not Editor connection or gameplay", "Native tests cover Unity 6000.6.2f1 only", "No source package parser; candidates are produced by monkey", "No global install, release, account/service/savegame writes", "Native receipts do not prove physical input, visual parity or game business acceptance"])


class Parser(argparse.ArgumentParser):
    def error(self, message):
        fail("CLI_USAGE", "arguments", message)


def parser():
    p = Parser(prog="beaver")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("version")
    sub.add_parser("capabilities")
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--editor-path")
    project = sub.add_parser("project").add_subparsers(dest="action", required=True)
    inspect = project.add_parser("inspect")
    inspect.add_argument("--project", required=True)
    inspect.add_argument("--assets", action="store_true")
    adopt = sub.add_parser("adopt").add_subparsers(dest="action", required=True)
    plan = adopt.add_parser("plan")
    plan.add_argument("--candidate", required=True)
    plan.add_argument("--baseline")
    plan.add_argument("--target", required=True)
    plan.add_argument("--lineage")
    plan.add_argument("--out", required=True)
    apply = adopt.add_parser("apply")
    apply.add_argument("--plan", required=True)
    apply.add_argument("--expected-plan", required=True)
    apply.add_argument("--out", required=True)
    apply.add_argument("--editor-path", required=True)
    apply.add_argument("--timeout", type=int, default=600)
    recover = adopt.add_parser("rollback")
    recover.add_argument("--transaction", required=True)
    recover.add_argument("--editor-path", required=True)
    recover.add_argument("--timeout", type=int, default=600)
    image = sub.add_parser("image").add_subparsers(dest="action", required=True)
    image_inspect = image.add_parser("inspect")
    image_inspect.add_argument("--input", required=True)
    compress = image.add_parser("compress")
    compress.add_argument("--input", required=True)
    compress.add_argument("--output", required=True)
    compress.add_argument("--apply", action="store_true")
    compress.add_argument("--expected-source")
    config = sub.add_parser("config").add_subparsers(dest="action", required=True)
    validate = config.add_parser("validate")
    validate.add_argument("--schema", required=True)
    validate.add_argument("--input", required=True)
    generate = config.add_parser("generate")
    generate.add_argument("--schema", required=True)
    generate.add_argument("--out", required=True)
    code=sub.add_parser('code').add_subparsers(dest='action',required=True)
    code_inspect=code.add_parser('inspect')
    code_inspect.add_argument('--project',required=True)
    unity = sub.add_parser("unity").add_subparsers(dest="action", required=True)
    unity_plan = unity.add_parser("plan")
    unity_plan.add_argument("--project", required=True)
    unity_plan.add_argument("--spec", required=True)
    unity_plan.add_argument("--out", required=True)
    unity_apply = unity.add_parser("apply")
    unity_apply.add_argument("--plan", required=True)
    unity_apply.add_argument("--expected-plan", required=True)
    unity_apply.add_argument("--out", required=True)
    unity_apply.add_argument("--editor-path", required=True)
    unity_apply.add_argument("--timeout", type=int, default=600)
    batch = sub.add_parser('batch').add_subparsers(dest='action',required=True)
    bp=batch.add_parser('plan');bp.add_argument('--project',required=True);bp.add_argument('--spec',required=True);bp.add_argument('--out',required=True)
    ba=batch.add_parser('apply');ba.add_argument('--plan',required=True);ba.add_argument('--expected-plan',required=True);ba.add_argument('--out',required=True);ba.add_argument('--editor-path',required=True);ba.add_argument('--timeout',type=int,default=600)
    br=batch.add_parser('recover');br.add_argument('--transaction',required=True);br.add_argument('--out',required=True);br.add_argument('--editor-path',required=True);br.add_argument('--timeout',type=int,default=600)
    refs=sub.add_parser('references');refs.add_argument('--project',required=True);refs.add_argument('--out',required=True);refs.add_argument('--cache')
    debug=sub.add_parser('debug').add_subparsers(dest='action',required=True)
    ds=debug.add_parser('start');ds.add_argument('--manifest',required=True);ds.add_argument('--expected',required=True);ds.add_argument('--out',required=True);ds.add_argument('--duration',type=int,default=3600);ds.add_argument('--width',type=int);ds.add_argument('--height',type=int)
    for name in ('inspect','stop','tail','screenshot'):
        d=debug.add_parser(name);d.add_argument('--session',required=True)
        if name=='tail':d.add_argument('--lines',type=int,default=80)
        if name=='screenshot':d.add_argument('--input',required=True);d.add_argument('--expected',required=True)
    dt=debug.add_parser('target');dt.add_argument('--transaction',required=True)
    player=sub.add_parser('player').add_subparsers(dest='action',required=True)
    player_run=player.add_parser('run')
    player_run.add_argument('--manifest',required=True)
    player_run.add_argument('--out',required=True)
    player_run.add_argument('--duration',type=int,default=10)
    player_run.add_argument('--expected-manifest',required=True)
    payload=sub.add_parser('payload').add_subparsers(dest='action',required=True)
    payload_verify=payload.add_parser('verify')
    payload_verify.add_argument('--root',required=True)
    payload_verify.add_argument('--manifest',required=True)
    payload_verify.add_argument('--scope')
    payload_verify.add_argument('--allow-unlisted',action='store_true')
    payload_verify.add_argument('--unity-artifact',action='store_true')
    payload_plan=payload.add_parser('plan')
    payload_plan.add_argument('--root',required=True)
    payload_plan.add_argument('--manifest',required=True)
    payload_plan.add_argument('--target',required=True)
    payload_plan.add_argument('--out',required=True)
    payload_plan.add_argument('--overrides')
    payload_plan.add_argument('--override-root')
    payload_apply=payload.add_parser('apply')
    payload_apply.add_argument('--plan',required=True)
    payload_apply.add_argument('--expected-plan',required=True)
    payload_apply.add_argument('--out',required=True)
    return p


def dispatch(a):
    if a.command == "version":
        return dict(version=__version__)
    if a.command == "capabilities":
        return capabilities()
    if a.command == "doctor":
        from .io import safe
        editor = safe(a.editor_path) if a.editor_path else None
        return dict(python=sys.version.split()[0], unityCLI=shutil.which("unity"),
                    pillow="available" if importlib.util.find_spec("PIL") else "not_available",
                    editor=dict(path=str(editor) if editor else None, present=editor.is_file() if editor else False),
                    nativeConnection="not_probed", autoInstall=False)
    if a.command == "project":
        from .context import inspect
        return inspect(a.project, a.assets)
    if a.command == "adopt":
        if a.action == "plan":
            from .adoption import preview
            return preview(a.candidate, a.target, a.out, a.baseline, a.lineage)
        if a.action == "apply":
            from .adoption_native import execute
            return execute(a.plan, a.out, a.editor_path, a.timeout, a.expected_plan)
        from .adoption_native import recover
        return recover(a.transaction, a.editor_path, a.timeout)
    if a.command == "image":
        from .images import inspect, compress
        return inspect(a.input) if a.action == "inspect" else compress(a.input, a.output, a.apply, a.expected_source)
    if a.command == "config":
        from .configuration import validate, generate
        return validate(a.schema, a.input) if a.action == "validate" else generate(a.schema, a.out)
    if a.command == "unity":
        from .unity import plan, apply
        return plan(a.project,a.spec,a.out) if a.action == "plan" else apply(a.plan,a.out,a.editor_path,a.expected_plan,a.timeout)
    if a.command=='batch':
        from .batch import plan,apply,recover
        if a.action=='plan':return plan(a.project,a.spec,a.out)
        if a.action=='apply':return apply(a.plan,a.out,a.editor_path,a.expected_plan,a.timeout)
        return recover(a.transaction,a.out,a.editor_path,a.timeout)
    if a.command=='references':
        from .references import inspect_graph
        result=inspect_graph(a.project,a.out,a.cache)
        return dict(status=result['status'],report=result['report'],counts=result['counts'],timingMs=result['timingMs'],
                    indexedGuids=len(result['guidToPath']),dependencySources=len(result['dependencies']),literalLoads=len(result['literalLoads']),
                    unknownDynamicLoads=len(result['unknownDynamicLoads']),unresolvedJsonStrings=len(result['unresolvedJsonStrings']),
                    limitations=result['limitations'])
    if a.command=='debug':
        from .debug import start,inspect_session,stop,tail,screenshot_record,inspect_native
        if a.action=='target':return inspect_native(a.transaction)
        if a.action=='start':return start(a.manifest,a.out,a.expected,a.duration,a.width,a.height)
        if a.action=='inspect':return inspect_session(a.session)
        if a.action=='stop':return stop(a.session)
        if a.action=='tail':return tail(a.session,a.lines)
        return screenshot_record(a.session,a.input,a.expected)
    if a.command == 'code':
        from .codecheck import inspect_code
        return inspect_code(a.project)
    if a.command == 'player':
        from .player import run
        return run(a.manifest,a.out,a.duration,a.expected_manifest)
    if a.command=='payload':
        from .payload import verify_manifest,plan,apply
        if a.action=='verify':return verify_manifest(a.root,a.manifest,a.scope,allow_unlisted=a.allow_unlisted,artifact=a.unity_artifact)
        if a.action=='plan':return plan(a.root,a.manifest,a.target,a.out,a.overrides,a.override_root)
        return apply(a.plan,a.out,a.expected_plan)


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if argv==['--version']:
        argv=['version']
    run_id = uuid.uuid4().hex
    base = dict(schemaVersion=1, contract="beaver-result/1", operationId=run_id,
                producer=dict(name="beaver", version=__version__, implementationSha256=implementation_identity()),
                actualChanges=[], artifacts=[], diagnostics=[], limitations=[],
                verification=dict(native="not_run", player="not_run", visual="not_run", business="not_run"))
    try:
        a = parser().parse_args(argv)
        data = dispatch(a)
        status = data.get("status") if data.get("status") in ("blocked","partial","failed","not_run") else "ok"
        if data.get('status') in ('identity_unknown','starting','stopping','not_available'):status='partial'
        base.update(status=status, data=data)
        result_path = data.get("report")
        if result_path and Path(result_path).is_file():
            base["artifacts"].append(dict(path=result_path, sha256=sha(Path(result_path).read_bytes())))
        if data.get("nativeReadback"):
            base["verification"]["native"] = data["nativeReadback"]
        if a.command == "adopt" and a.action == "apply":
            base["actualChanges"] = [dict(operation='adoption.apply',transaction=data['transaction'],counts=data.get('counts',{}))]
        if a.command == "unity" and a.action == "apply":
            base["actualChanges"] = data.get("changes", [])
        if a.command=='batch' and a.action in ('apply','recover'):
            base['actualChanges']=data.get('changes',[dict(operation='batch.recover',restored=data.get('restored'))])
        if a.command=='adopt' and a.action=='rollback':
            base['verification']['native']='rolled_back'
            base['actualChanges']=[dict(operation='adoption.rollback',restored=data.get('restored'),report=data.get('report'))]
        if a.command=='player':
            base['verification']['player']='launched_and_exited' if not data.get('stoppedByBudget') else 'launched_and_stopped_by_budget'
        if a.command=='payload' and a.action=='apply':
            base['actualChanges']=[dict(operation='payload.materialize',targetRoot=data['targetRoot'],files=data['files'],overrides=len(data['overrides']))]
        print(json.dumps(base, ensure_ascii=False, allow_nan=False))
        return {'blocked':3,'partial':1,'failed':2,'not_run':3}.get(status,0)
    except (BeaverError, OSError, ValueError, TypeError, KeyError, ImportError, OverflowError) as error:
        blocked=isinstance(error,BeaverError) and error.status=='blocked'
        base.update(status="blocked" if blocked else "failed",
                    diagnostics=[error.as_dict() if isinstance(error, BeaverError) else dict(code="IO_OR_INPUT", location="input", message=str(error))])
        if isinstance(error,BeaverError):
            location=Path(error.location)
            if location.is_dir() and (location/'journal.json').is_file():
                base['artifacts'].append(dict(path=str(location/'journal.json'),sha256=sha((location/'journal.json').read_bytes())))
                base['actualChanges']=[dict(status='inspect_transaction',transaction=str(location),reason='Failure can follow partial native writes; no zero-write claim')]
                if '_NATIVE_FAILED' in error.code:
                    base['verification']['native']='failed'
        print(json.dumps(base, ensure_ascii=False))
        return 3 if blocked else 2


if __name__ == "__main__":
    sys.exit(main())
