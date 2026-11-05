import argparse
import json
import sys
import zipfile
from . import __version__
from .sources.bundle import inspect, PROFILE
from .sources.compiled import ParseError, fail
from .sources.project import inspect as inspect_project, catalog, PROFILE as PROJECT_PROFILE
from .normalize import normalize
from .targets.unity import plan, export, verify, handoff, PROFILE as UNITY_PROFILE
from .byte_budgets import defaults as default_byte_budgets
from .targets import cocos
from . import incremental
from pathlib import Path


def main(argv=None):
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw[:1] == ['tool']:
        from monkey.toolkit.runner import main as run_tool
        return run_tool(raw[1:])
    if raw[:1] == ['static-code-bindings']:
        from .static_code_bindings import main as run_static_code_bindings
        try:
            result=run_static_code_bindings(raw[1:])
            counts=result.get('counts',{})
            return 1 if any(counts.get(key,0)for key in ('partial','blocked','not_executed'))else 0
        except (ParseError, OSError, ValueError, KeyError, TypeError, IndexError, RecursionError) as error:
            print(json.dumps(dict(status='error',code=getattr(error,'code','INPUT_ERROR'),message=str(error)),ensure_ascii=False),file=sys.stderr)
            return 2
    parser = argparse.ArgumentParser(prog='monkey')
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    sub = parser.add_subparsers(dest='command', required=True)
    cap = sub.add_parser('capabilities')
    cap.add_argument('--json', action='store_true')
    sub.add_parser('static-code-bindings',help='Prepare source-proven inert MonoBehaviours, stage a fresh candidate, or audit static destinations; no gameplay acceptance')
    p=sub.add_parser('resource-probe',help='Prepare a minimal native resource probe from exact frozen candidate closures')
    p.add_argument('--candidate',required=True);p.add_argument('--expected-manifest',required=True)
    resource=p.add_mutually_exclusive_group(required=True);resource.add_argument('--spine',action='append');resource.add_argument('--shader')
    p.add_argument('--out',required=True)
    p=sub.add_parser('diagnose',help='Index existing recovery gaps with source identities, evidence hashes and next actions')
    p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--evidence',action='append',default=[])
    p.add_argument('--max-issues',type=int,default=2000);p.add_argument('--max-document-bytes',type=int,default=32*1024*1024)
    p=sub.add_parser('doctor',help='Read local dependency/editor metadata; no installation or Editor launch')
    p.add_argument('--out',required=True);p.add_argument('--unity-editor');p.add_argument('--creator-editor');p.add_argument('--provider-python')
    p=sub.add_parser('space-preview',help='Estimate retained data and reviewable Editor caches; never deletes files')
    p.add_argument('--root',required=True);p.add_argument('--out',required=True);p.add_argument('--protect',action='append',default=[])
    p.add_argument('--max-files',type=int,default=500000)
    p=sub.add_parser('acquire-resources',help='Fetch only an explicit resource list; verified partial receipts can be resumed into a fresh layer')
    p.add_argument('--manifest',required=True);p.add_argument('--input-set',required=True);p.add_argument('--out',required=True)
    p.add_argument('--cache-root');p.add_argument('--resume-from');p.add_argument('--offline',action='store_true')
    p.add_argument('--budget-seconds',type=int,default=900);p.add_argument('--max-attempts',type=int,default=3)
    for name in ('query-methods','query-tables','inspect-aliases'):
        p=sub.add_parser(name,help='Inspect exact frozen evidence; no source program execution')
        p.add_argument('--source',required=name!='query-tables')
        p.add_argument('--member',help='Exact ZIP member; expected SHA identifies member bytes, not the outer ZIP')
        p.add_argument('--expected-sha',required=name!='query-tables')
        p.add_argument('--limit',type=int,default=20)
        p.add_argument('--out',required=True)
        if name=='query-methods':
            p.add_argument('--type',default='');p.add_argument('--method',default='')
            p.add_argument('--module');p.add_argument('--function',type=int)
        elif name=='query-tables':
            p.add_argument('--manifest',required=True);p.add_argument('--expected-manifest-sha',required=True)
            p.add_argument('--contains',default='');p.add_argument('--extract')
        else:
            p.add_argument('--alias');p.add_argument('--content-source');p.add_argument('--content-prefix',default='')
    p = sub.add_parser('adopt', help='Deprecated compatibility: three-way asset adoption; ownership transferred to beaver')
    p.add_argument('--candidate', help='Frozen incoming package or Unity-source project')
    p.add_argument('--target', help='Existing owned development project; never the source export')
    p.add_argument('--baseline', help='Explicit frozen common generation for first adoption')
    p.add_argument('--lineage', help='Explicit stable game namespace for Unity-source exports without their own namespace')
    p.add_argument('--plan', help='Previously reviewed adoption-plan.json; required for execution')
    p.add_argument('--expected-plan', help='Exact SHA256 of the reviewed adoption plan')
    p.add_argument('--execute', action='store_true')
    p.add_argument('--editor-path', help='Existing exact target Editor executable')
    p.add_argument('--budget-seconds', type=int, default=1200)
    p.add_argument('--out', required=True)
    p = sub.add_parser('adopt-recover', help='Deprecated compatibility: recover an existing adoption transaction; ownership transferred to beaver')
    p.add_argument('--transaction', required=True)
    p.add_argument('--editor-path', required=True)
    p.add_argument('--budget-seconds', type=int, default=1200)
    p = sub.add_parser('convert', description='Expanded input batch defaults to 2048 MiB; each package entry is limited to 128 MiB. An explicit input set can set its combined budget.', help='Convert a source project into an isolated native project candidate')
    p.add_argument('--source', help='Local wxapkg/APK, resource/project directory, project.json or bundle config.json')
    p.add_argument('--format',choices=['none','grea'],default=None,help='Deprecated: every output already uses monkey-project/2.0.0; grea is accepted as an alias.')
    p.add_argument('--layout',help='Game layout.json: module/rename/bundle-role overrides for monkey-project/2.0.0 paths (docs/PROJECT-SPEC.md section 7)')
    p.add_argument('--source-family', choices=['auto','cocos','unity','laya','layaair','egret','eraget','custom','other'], default='auto')
    p.add_argument('--provider-python', help='Existing Python with UnityPy 1.25.3 for Unity source conversion')
    p.add_argument('--asset-ripper', help='Existing exact AssetRipper 2.0.0 provider executable')
    p.add_argument('--provider-budget-seconds', type=int, default=600)
    p.add_argument('--unity-object-value-limit',type=int,help='Unity inline value limit per object; default 250000, maximum 1000000; streamed payloads have separate byte limits')
    p.add_argument('--unity-container-value-limit',type=int,help='Unity inline value limit per input container; default 8000000, maximum 16000000')
    p.add_argument('--unity-texture-cache',help='Explicit local ASTC or single-level DDS/DXT5 cache pool for supported Unity texture-key hydration')
    p.add_argument('--unity-quarantine-invalid-textures',action='store_true',help='Explicit partial export excluding exact invalid ETC1 objects; originals and unresolved references retained')
    p.add_argument('--unity-dependency-manifest',help='Frozen Unity bundle lookup pool; export only exact reachable serialized-file closure')
    p.add_argument('--unity-export-scope',choices=['reachable','all'],default='reachable',help='all exports every unique container in the explicit Unity bundle manifest')
    p.add_argument('--unity-prepared-textures',help='Frozen prepare-unity-bulk output; reuse exact derived containers')
    p.add_argument('--unity-reuse-provider-export',help='Frozen export-unity-bulk output; assemble without relaunching provider')
    p.add_argument('--unity-reuse-inspection',help='Reuse an exact same-worker complete inspect-unity --bundle-manifest snapshot')
    p.add_argument('--unity-code-evidence',help='Frozen metadata/declaration/source-code evidence manifest for a self-contained AI handoff')
    p.add_argument('--unity-schema-manifest',help='Frozen bundle pool for exact missing TypeTree lookup during Unity conversion')
    p.add_argument('--code-source',help='Exact original JS file present by SHA/bytes in this package or frozen resource candidate')
    p.add_argument('--module-contract',help='Reviewed source-bound typed module contract for the complete Unity candidate')
    p.add_argument('--module-selectors',help='Exact classId/methodId roots; infer provable types and close dependencies, optionally using --module-contract as evidence')
    p.add_argument('--configuration-table',help='Exact source-bound runtime JSON table accepted by the selected module configuration adapter')
    p.add_argument('--reuse-candidate',help='Frozen complete resource candidate to compose with recovered modules, without redecoding source resources')
    p.add_argument('--expected-candidate',help='Required exact SHA256 of the frozen candidate owning manifest')
    p.add_argument('--numeric-code-contract',help='Explicit source identity and numeric Label-field or reviewed static Number-method contract; fresh package conversion only')
    p.add_argument('--cocos-code-language',choices=['ts','js'],default='ts',help='Cocos code output; TypeScript first; JS uses an explicit ESM package boundary')
    p.add_argument('--reuse-source-stages',help='Fresh package output using verified source stages; supports names-v1 metadata migration')
    p.add_argument('--input-set', help='Explicit local roots and identity/provenance manifest (schema 1)')
    p.add_argument('--target', choices=['unity','cocos','unity6','cocos38','both',UNITY_PROFILE,cocos.PROFILE])
    p.add_argument('--package', action='store_true', help='Inventory all input files and generate self-contained recovery workspaces')
    p.add_argument('--out', '--output', help='Fresh output directory; package targets use UnityProject/ and CocosProject/')
    p.add_argument('--resume', help='Resume a conversion with identity/hash checks; packages also require --input-set')
    p.add_argument('--recipe', help='Reusable JSON input/selection options; combine with --out')
    p.add_argument('--offline', action='store_true', help='Explicitly generate and verify an offline candidate only')
    p.add_argument('--namespace')
    p.add_argument('--source-profile', choices=[PROFILE,PROJECT_PROFILE,'generic-image-resources-v1','egret-custom-resource-plist-v1'])
    pick = p.add_mutually_exclusive_group()
    pick.add_argument('--asset-index', type=int, action='append')
    pick.add_argument('--all-assets', action='store_true', help='Explicitly select every bundle entry (project default)')
    p.add_argument('--dependency-source', action='append', default=[])
    p.add_argument('--evidence-source', action='append', default=[])
    p.add_argument('--bindings')
    p.add_argument('--animation', action='append')
    p.add_argument('--native', action='store_true', help='After fresh package conversion, execute sequential bounded native imports')
    p.add_argument('--native-out', help='Fresh separate native workspace; default OUTPUT-native')
    p.add_argument('--unity-editor', help='Exact installed Unity executable for --native')
    p.add_argument('--creator-editor', help='Exact installed CocosCreator executable for --native')
    p.add_argument('--native-budget-seconds', type=int, default=1200, help='Method budget per Editor, 1..1200; each window is at most 30 minutes')
    p.add_argument('--remote-manifest', help='Explicit URL/path/SHA/byte downloads; Cocos requires --input-set, Unity accepts an explicit source container')
    p.add_argument('--remote-cache-root', help='Read-only root for paths in the remote manifest')
    p.add_argument('--acquisition-out', help='Fresh acquired-files workspace; default OUTPUT-acquired')
    p.add_argument('--remote-budget-seconds', type=int, default=900, help='Acquisition budget, 30..3600 seconds')
    p = sub.add_parser('acquire-unity-textures',help='Capture exact serialized ASTC keys under a literal original DATA_CDN')
    for name in ('inspection','cache-manifest','cdn-source','cdn-root','out'):p.add_argument('--'+name,required=True)
    p.add_argument('--cache-root');p.add_argument('--budget-seconds',type=int,default=1200);p.add_argument('--workers',type=int,default=8);p.add_argument('--resume',action='store_true')
    p = sub.add_parser('hydrate-unity', help='Resolve explicit WeChat texture keys against a pinned local ASTC or DDS/DXT5 cache pool')
    p.add_argument('--source',required=True)
    p.add_argument('--texture-cache',required=True)
    p.add_argument('--selection-manifest',help='Frozen source SHA and exact Texture2D file/pathId/rawSha256/logicalPath selection; unselected objects stay unchanged and pending')
    p.add_argument('--provider-python',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--budget-seconds',type=int,default=120)
    p = sub.add_parser('export-unity-textures',help='Export exact selected hydrated Texture2D pixels as PNG candidates without whole-container AssetRipper export')
    for name in ('source','derivative','hydration-report','expected-hydration-sha256','selection-manifest','provider-python','out'):p.add_argument('--'+name,required=True)
    p.add_argument('--budget-seconds',type=int,default=120)
    p = sub.add_parser('index-unity', help='Index exact serialized files and PPtr IDs from an explicit frozen bundle list')
    p.add_argument('--manifest', required=True)
    p.add_argument('--provider-python', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--budget-seconds',type=int,default=600)
    p = sub.add_parser('unity-field-plan', help='Validate frozen field semantics and exact source/target identities; never edits Unity assets')
    for name in ('candidate','trusted','trusted-sha256','bindings','inventory','inventory-sha256','source','metadata','target-root','out'):
        p.add_argument('--'+name, required=True)
    p = sub.add_parser('unity-code-model', help='Recover named C# data fields from embedded Unity TypeTree evidence')
    p.add_argument('--inspection', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--bulk',action='store_true',help='Alias repeated MonoScript only with exact raw bytes and proven field equality')
    p = sub.add_parser('export-unity', help='Export a Unity bundle through an existing fixed AssetRipper in an isolated copy')
    p.add_argument('--source', required=True)
    p.add_argument('--asset-ripper', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--budget-seconds', type=int, default=600)
    p = sub.add_parser('classify-unity-shaders',help='Classify frozen recovered Shader evidence without compiling, moving or re-exporting assets')
    for name in ('project','manifest','expected-manifest','out'):p.add_argument('--'+name,required=True)
    p.add_argument('--source-mapping');p.add_argument('--expected-source-mapping')
    p = sub.add_parser('inspect-unity', help='Strict typed inspection of an explicit Unity serialized file or AssetBundle')
    p.add_argument('--source', required=True)
    p.add_argument('--schema-manifest', help='Explicit frozen bundle pool; borrow only identical version/platform/script/type hashes')
    p.add_argument('--provider-python', required=True, help='Existing Python with UnityPy 1.25.3; never installed automatically')
    p.add_argument('--out', required=True)
    p.add_argument('--budget-seconds', type=int, default=120)
    p.add_argument('--bundle-manifest',help='Inspect every unique container in the explicit frozen bundle pool in one worker')
    p.add_argument('--unity-object-value-limit',type=int,help='Unity inline value limit per object; default 250000, maximum 1000000; streamed payloads have separate byte limits')
    p.add_argument('--unity-container-value-limit',type=int,help='Unity inline value limit per input container; default 8000000, maximum 16000000')
    p = sub.add_parser('format-project',help='Retired: new outputs are already monkey-project/2.0.0 (docs/PROJECT-SPEC.md)')
    p.add_argument('--project',required=True)
    p.add_argument('--profile',choices=['grea'],default='grea')
    pick=p.add_mutually_exclusive_group(required=True)
    pick.add_argument('--preview',action='store_true')
    pick.add_argument('--plan')
    p.add_argument('--out',required=True)
    p = sub.add_parser('layout-preview', help='Replay a finished conversion under a layout.json and list current -> previewed paths; writes no project')
    p.add_argument('--conversion', required=True)
    p.add_argument('--layout', help='Game layout.json to preview (docs/PROJECT-SPEC.md section 7)')
    p.add_argument('--out', required=True)
    p = sub.add_parser('layout-migration', help='Old candidate path -> new candidate path for every shared GUID/UUID, for AssetDatabase.MoveAsset in adopted projects')
    p.add_argument('--from', dest='old', required=True)
    p.add_argument('--to', dest='new', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('project-model', help='Inspect explicit target asset path slots and identity without moving files')
    p.add_argument('--candidate', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('code-emit', help='Emit source-bound typed C# modules or legacy numeric field methods; unknown methods stay excluded')
    p.add_argument('--source',required=True)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--code-model')
    group.add_argument('--module-contract',help='Exact source/class/method SHA256 and explicit typed C# call domain')
    group.add_argument('--module-profile',help='Explicit optional legacy extension profile; exact source identity required, never selected by default')
    p.add_argument('--reuse-from');p.add_argument('--expected-manifest')
    p.add_argument('--configuration-table',help='Explicit legacy project-extension configuration table; exact source/table identity required, original JSON remains runtime data')
    p.add_argument('--namespace',default='monkey-project')
    p.add_argument('--numeric-field',action='append',default=[],help='Explicit numeric call-subdomain contract; not a global JS type inference')
    p.add_argument('--cocos-code-language',choices=['ts','js'],default='ts')
    p.add_argument('--out',required=True)
    p = sub.add_parser('freeze-resource-candidate',help='Seal saved resource inventory and retain current verification gaps; does not grant accepted selection; no Editor launch')
    p.add_argument('--candidate',required=True);p.add_argument('--expected-manifest',required=True);p.add_argument('--expected-readback',required=True);p.add_argument('--out',required=True)
    p = sub.add_parser('code-draft',help='Export every available source method/function as best-effort C# drafts; type/syntax/API gaps do not gate export')
    p.add_argument('--source',required=True);p.add_argument('--expected-source');p.add_argument('--out',required=True)
    p.add_argument('--reuse-from');p.add_argument('--expected-manifest')
    p = sub.add_parser('code-postprocess',help='Explicit optional bounded Codex CLI pass over independent copies of selected generated C#')
    p.add_argument('--candidate',required=True);p.add_argument('--expected-manifest',required=True)
    p.add_argument('--selected-path',action='append',required=True);p.add_argument('--task-file',required=True);p.add_argument('--out',required=True)
    p.add_argument('--evidence-root');p.add_argument('--evidence-file',action='append',default=[])
    p.add_argument('--codex',default='/opt/homebrew/bin/codex');p.add_argument('--budget-seconds',type=int,default=900)
    p.add_argument('--idle-seconds',type=int,default=180);p.add_argument('--prepare-only',action='store_true',help='Prepare workspace and probe CLI help; no model session')
    p = sub.add_parser('code-postprocess-resume',help='Resume only the exact recorded Codex checkpoint session; never resume latest')
    p.add_argument('--run',required=True);p.add_argument('--session',required=True)
    p = sub.add_parser('code-project-prepare',help='Prepare an exact whole-candidate C# batch queue and independent complete project')
    p.add_argument('--candidate',required=True);p.add_argument('--expected-manifest',required=True);p.add_argument('--out',required=True)
    p.add_argument('--batch-max-files',type=int,default=128);p.add_argument('--batch-code-bytes',type=int,default=512*1024)
    p.add_argument('--batch-seconds',type=int,default=3600);p.add_argument('--idle-seconds',type=int,default=900);p.add_argument('--attempts',type=int,default=2)
    p.add_argument('--codex',default='/opt/homebrew/bin/codex')
    for command in ('code-project-run','code-project-status','code-project-resume'):
        p=sub.add_parser(command,help='Run all ready batches, inspect durable progress, or resume exact project checkpoints')
        p.add_argument('--run',required=True)
        if command=='code-project-resume':p.add_argument('--retry-failed',action='store_true',help='Explicitly grant a new finite retry window to exhausted failed batches')
    p=sub.add_parser('code-project-pause',help='Request cooperative pause and preserve the active exact-session checkpoint')
    p.add_argument('--run',required=True)
    p.add_argument('--after-current-attempt',action='store_true',help='Let the current attempt finish before pausing; do not interrupt the active model')
    p=sub.add_parser('code-project-configure',help='Change finite batch budgets only while the supervisor and child are stopped')
    p.add_argument('--run',required=True);p.add_argument('--batch-seconds',type=int,required=True);p.add_argument('--idle-seconds',type=int,required=True)
    p=sub.add_parser('code-project-recheck',help='Revalidate completed saved reviews after validator fixes without a new model call')
    p.add_argument('--run',required=True)
    p=sub.add_parser('code-architecture-prepare',help='Prepare one whole-source native Unity architecture design with immutable evidence')
    p.add_argument('--candidate',required=True);p.add_argument('--expected-manifest',required=True);p.add_argument('--out',required=True)
    p.add_argument('--namespace',default='Game');p.add_argument('--codex',default='/opt/homebrew/bin/codex')
    p.add_argument('--budget-seconds',type=int,default=3600);p.add_argument('--idle-seconds',type=int,default=900)
    p=sub.add_parser('code-architecture-run',help='Run or precisely resume the architecture design task, then validate its executable generation contract')
    p.add_argument('--run',required=True);p.add_argument('--session')
    p=sub.add_parser('code-architecture-status',help='Read architecture-stage status without running a model')
    p.add_argument('--run',required=True)
    p=sub.add_parser('code-architecture-recheck',help='Revalidate a saved finalized architecture patch without another model invocation')
    p.add_argument('--run',required=True)
    p=sub.add_parser('code-architecture-refine',help='Prepare a bounded ownership repair over a previous architecture output')
    p.add_argument('--run',required=True);p.add_argument('--out',required=True);p.add_argument('--codex',default='/opt/homebrew/bin/codex')
    p.add_argument('--budget-seconds',type=int,default=3600);p.add_argument('--idle-seconds',type=int,default=900)
    p=sub.add_parser('code-native-prepare',help='Prepare all designed feature modules and one isolated five-layer candidate')
    p.add_argument('--architecture',required=True);p.add_argument('--out',required=True)
    p.add_argument('--codex',default='/opt/homebrew/bin/codex')
    p.add_argument('--budget-seconds',type=int,default=3600);p.add_argument('--idle-seconds',type=int,default=900)
    p.add_argument('--external-references-file',help='Explicit JSON layer-to-assembly reference map from verified installed packages')
    p.add_argument('--retained-support-path',action='append',default=[],help='Explicit existing native layout helper and paired meta path retained from the frozen candidate')
    for command in ('code-native-run','code-native-status'):
        p=sub.add_parser(command,help='Run ready modules serially through candidate assembly, or read durable progress')
        p.add_argument('--run',required=True)
    p=sub.add_parser('code-native-continue',help='Version a stopped module schedule, reusing pinned terminal outputs and prioritizing unfinished core modules')
    p.add_argument('--run',required=True);p.add_argument('--out',required=True)
    p.add_argument('--priority',action='append',required=True)
    p.add_argument('--stop-after',help='Natural module boundary for integration; a later run continues the remaining full scope')
    p=sub.add_parser('code-native-reassemble',help='Read-only reclassify terminal module outputs and assemble a fresh unvalidated candidate')
    p.add_argument('--run',required=True);p.add_argument('--out',required=True)
    p.add_argument('--allow-incomplete',action='store_true',help='Explicit stopped integration checkpoint; preserve all ungenerated classes as missing, never fabricate shells')
    p=sub.add_parser('code-native-revise',help='Apply a hash-pinned C# ownership revision to a fresh native candidate')
    p.add_argument('--candidate',required=True);p.add_argument('--expected-manifest',required=True)
    p.add_argument('--revision',required=True);p.add_argument('--expected-revision',required=True);p.add_argument('--out',required=True)
    p=sub.add_parser('code-native-add-json',help='Add explicitly self-authored local-test JSON assets to a fresh owned native candidate')
    p.add_argument('--candidate',required=True);p.add_argument('--expected-manifest',required=True)
    p.add_argument('--spec',required=True);p.add_argument('--expected-spec',required=True);p.add_argument('--out',required=True)
    p=sub.add_parser('code-architecture-module-prepare',help='Prepare one complete feature module from a designed architecture')
    p.add_argument('--architecture',required=True);p.add_argument('--module',required=True);p.add_argument('--out',required=True)
    p.add_argument('--dependency',action='append',default=[])
    p.add_argument('--previous');p.add_argument('--expected-previous-manifest')
    p.add_argument('--supplemental-csharp-spec',help='Explicit JSON list of read-only native integration source {path,sha256} pins; never original-source ownership')
    p.add_argument('--codex',default='/opt/homebrew/bin/codex')
    p.add_argument('--budget-seconds',type=int,default=3600);p.add_argument('--idle-seconds',type=int,default=900)
    for command in ('code-architecture-module-run','code-architecture-module-status','code-architecture-module-recheck','code-architecture-module-recover'):
        p=sub.add_parser(command,help='Run or inspect one isolated source-bound module task')
        p.add_argument('--run',required=True)
        if command.endswith('-run'):p.add_argument('--session')
    p = sub.add_parser('code-types',help='Extract only statically proven source types/dependencies and write named fillable evidence gaps')
    p.add_argument('--source',required=True);p.add_argument('--selectors',required=True);p.add_argument('--type-evidence');p.add_argument('--namespace');p.add_argument('--out',required=True)
    p = sub.add_parser('code-select',help='Select reviewed source methods, close typed dependencies and check actual lowering; no source execution')
    p.add_argument('--source',required=True);p.add_argument('--selectors',required=True);p.add_argument('--out',required=True)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--type-evidence');group.add_argument('--module-profile')
    p = sub.add_parser('code-handoff',help='Generate source-bound named drafts from a frozen Cocos candidate; optional additive owned-copy handoff')
    p.add_argument('--candidate',required=True);p.add_argument('--out',required=True)
    p.add_argument('--expected-manifest');p.add_argument('--apply-owned',action='store_true');p.add_argument('--reuse-facts');p.add_argument('--expected-facts')
    p = sub.add_parser('code-model', help='Inspect named methods and evidenced semantic candidates without executing JavaScript')
    p.add_argument('--source', required=True)
    p.add_argument('--module-name')
    p.add_argument('--lexical-graph',action='store_true',help='Complete-source lexical class/call evidence, not executable recovery')
    p.add_argument('--expected-source');p.add_argument('--method-id',action='append',default=[])
    p.add_argument('--out', required=True)
    p.add_argument('--bulk',action='store_true',help='Preserve ambiguous whole-file assignments as unsupported evidence')
    p = sub.add_parser('unity-code-source',help='Static Mono decompilation or source-bound IL2CPP metadata evidence; never execute original assembly')
    p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--expected-source',required=True)
    p.add_argument('--family',choices=['mono','il2cpp-wasm'],default='mono');p.add_argument('--provider')
    p.add_argument('--metadata');p.add_argument('--method-map');p.add_argument('--expected-metadata');p.add_argument('--expected-method-map')
    p = sub.add_parser('unity-code-candidate',help='Prepare exact static Mono C# drafts; closure is not IL-equivalence or Unity verification')
    p.add_argument('--source-report',required=True);p.add_argument('--expected-report',required=True);p.add_argument('--out',required=True)
    p.add_argument('--method-id',action='append')
    p = sub.add_parser('wasm-code-source',help='Verify exact decoded WASM code bodies and v29 metadata/map identities; never execute a module')
    p.add_argument('--source',required=True);p.add_argument('--expected-source',required=True);p.add_argument('--metadata',required=True);p.add_argument('--expected-metadata',required=True)
    p.add_argument('--method-map',required=True);p.add_argument('--expected-method-map',required=True);p.add_argument('--decoded-segments',required=True);p.add_argument('--brotli-provider')
    p.add_argument('--method-id',action='append');p.add_argument('--out',required=True)
    p = sub.add_parser('wasm-code-candidate',help='Lift supported exact WASM operators to isolated C# fragments; heap and unknown calls remain evidence')
    p.add_argument('--source-report',action='append',required=True);p.add_argument('--expected-report',action='append',required=True)
    p.add_argument('--method',action='append',required=True);p.add_argument('--out',required=True)
    p = sub.add_parser('code-native-probe',help='Prepare the exact supported HealthState Unity6 probe; no Editor launch')
    p.add_argument('--candidate',required=True);p.add_argument('--expected-manifest',required=True);p.add_argument('--out',required=True)
    p.add_argument('--recipe-module',action='store_true',help='Also bind the exact source recipe JSON and recovered catalog in the independent probe')
    p.add_argument('--interactive',action='store_true',help='Prepare a fresh Editor pointer flow over the source-bound modules and original recipe JSON')
    p = sub.add_parser('research-matrix', help='Discover every Research game without converting or following external sources')
    p.add_argument('--root', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('native-layout-audit',help='Audit a frozen native flow-layout subset for standard Unity replacements')
    p.add_argument('--candidate',required=True);p.add_argument('--expected-manifest',required=True);p.add_argument('--out',required=True)
    p = sub.add_parser('native-layout-prepare',help='Create an independent warm candidate for an audited native layout patch')
    p.add_argument('--audit',required=True);p.add_argument('--out',required=True);p.add_argument('--previous-execution',help='Resume an exact exited partial layer, reusing its saved native asset evidence')
    p = sub.add_parser('native-layout-patch',help='Plan or execute one bounded prepared native layout replacement')
    p.add_argument('--preparation',required=True);p.add_argument('--out',required=True);p.add_argument('--editor',required=True)
    p.add_argument('--budget-seconds',type=int,default=900);p.add_argument('--deadline-utc',required=True);p.add_argument('--window-end-utc',required=True);p.add_argument('--execute',action='store_true')
    p = sub.add_parser('native-layout-finish',help='Freeze an exited successful native layout subset and consumer-guarded delta')
    p.add_argument('--execution',required=True);p.add_argument('--out',required=True)
    p = sub.add_parser('native-layout-bundle',help='Package a frozen verified Prefab/runtime delta with old-hash and identity guards')
    p.add_argument('--delta',required=True);p.add_argument('--out',required=True)
    p = sub.add_parser('freeze-unity-handoff',help='Freeze complete original/acquired input dispositions in a Unity-source initial')
    p.add_argument('--candidate',required=True);p.add_argument('--texture-cache',required=True);p.add_argument('--source-manifest',required=True);p.add_argument('--source-root',required=True);p.add_argument('--expected-manifest',required=True);p.add_argument('--out',required=True)
    p = sub.add_parser('freeze-handoff',help='Freeze an additive source-native identity and named-code initial handoff')
    p.add_argument('--candidate',required=True);p.add_argument('--native-contract',required=True);p.add_argument('--verification',required=True);p.add_argument('--expected-manifest',required=True);p.add_argument('--out',required=True);p.add_argument('--apply-owned',action='store_true')
    p = sub.add_parser('export-unity-bulk',help='Export all frozen prepared containers in one separately bounded AssetRipper stage')
    p.add_argument('--prepared',required=True);p.add_argument('--asset-ripper',required=True);p.add_argument('--out',required=True);p.add_argument('--budget-seconds',type=int,default=1200)
    p.add_argument('--deadline-utc',required=True);p.add_argument('--window-end-utc',required=True)
    p = sub.add_parser('prepare-unity-bulk',help='Resume exact whole-pool texture preparation independently of provider export')
    p.add_argument('--inspection',required=True);p.add_argument('--texture-cache',required=True);p.add_argument('--capture',required=True);p.add_argument('--provider-python',required=True);p.add_argument('--out',required=True)
    p.add_argument('--budget-seconds',type=int,default=1200);p.add_argument('--resume',action='store_true')
    p = sub.add_parser('native-finish-plan',help='Prepare incremental source Scene export and SHRINK evidence using existing native assets')
    p.add_argument('--candidate',required=True);p.add_argument('--out',required=True);p.add_argument('--exclude-scene',action='append',default=[])
    p = sub.add_parser('native-finish',help='Plan or execute one bounded incremental finish in an explicitly owned native project')
    p.add_argument('--candidate',required=True);p.add_argument('--preparation',required=True);p.add_argument('--out',required=True)
    p.add_argument('--editor-path',required=True);p.add_argument('--expected-manifest',required=True)
    p.add_argument('--budget-seconds',type=int,default=600);p.add_argument('--deadline-utc',required=True)
    p.add_argument('--window-end-utc',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--previous-execution')
    p = sub.add_parser('native-import',help='Plan or explicitly execute a bounded Unity/Creator import in a fresh copy')
    p.add_argument('--candidate',required=True);p.add_argument('--out',required=True)
    p.add_argument('--editor-path',required=True);p.add_argument('--expected-manifest',required=True)
    p.add_argument('--budget-seconds',type=int,default=600);p.add_argument('--deadline-utc',required=True)
    p.add_argument('--window-end-utc',required=True);p.add_argument('--execute',action='store_true')
    p.add_argument('--render-preview',action='store_true',help='Unity: use a real graphics device for diagnostic previews')
    p = sub.add_parser('recover-native-execution',help='Write a hash-bound independent receipt for a stopped transaction without changing old evidence or launching an Editor')
    p.add_argument('--request',required=True);p.add_argument('--expected-request',required=True);p.add_argument('--out',required=True)
    p = sub.add_parser('preflight',help='Check frozen candidate and classify startup logs without launching an Editor')
    p.add_argument('--candidate',required=True);p.add_argument('--out',required=True);p.add_argument('--log');p.add_argument('--progress')
    p = sub.add_parser('inspect')
    p.add_argument('--source', required=True)
    p.add_argument('--source-profile', choices=[PROFILE,PROJECT_PROFILE], required=True)
    p.add_argument('--evidence-source',action='append',default=[])
    p.add_argument('--dependency-source',action='append',default=[])
    p.add_argument('--asset-index', type=int, action='append', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('catalog')
    p.add_argument('--source',required=True)
    p.add_argument('--source-profile',choices=[PROJECT_PROFILE],required=True)
    p.add_argument('--out',required=True)
    p = sub.add_parser('normalize')
    p.add_argument('--manifest', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('continue-static-prefabs', help='Continue pinned component families in a fresh plan without rerunning source normalization')
    p.add_argument('--request',required=True);p.add_argument('--expected-request',required=True);p.add_argument('--out',required=True)
    p = sub.add_parser('refresh-static-spine-helpers', help='Refresh pinned native helpers and Atlas mapping in a fresh stage while reusing decoded texture bytes')
    p.add_argument('--request',required=True);p.add_argument('--expected-request',required=True);p.add_argument('--out',required=True)
    p = sub.add_parser('complete-static-spine-defaults',help='Apply pinned source-version defaults and reuse decoded Spine pages in a fresh stage')
    p.add_argument('--request',required=True);p.add_argument('--expected-request',required=True);p.add_argument('--out',required=True)
    p = sub.add_parser('prepare-source-text-reference',help='Prepare an offline source-version Cocos Label reference with pinned runtime and inputs')
    p.add_argument('--request',required=True);p.add_argument('--expected-request',required=True);p.add_argument('--out',required=True)
    p = sub.add_parser('capture-source-text-reference',help='Capture an actual controlled source-version Label reference in an existing headless browser')
    p.add_argument('--preparation',required=True);p.add_argument('--expected-preparation',required=True)
    p.add_argument('--browser-executable',required=True);p.add_argument('--timeout-seconds',type=int,default=90);p.add_argument('--out',required=True)
    p = sub.add_parser('prefab-static-fields', help='Preserve serialized custom fields in a fresh IR stage without rerunning resources')
    p.add_argument('--manifest', required=True)
    p.add_argument('--ir', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('prefab-behavior-ir', help='Generate source-bound native behavior scripts in an independent IR stage')
    p.add_argument('--manifest', required=True)
    p.add_argument('--ir', required=True)
    p.add_argument('--source-bundle', required=True)
    p.add_argument('--expected-source-bundle', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--ir',required=True)
    p.add_argument('--static-source-bundle',help='Original JS bundle, parsed only for static constructor fields')
    p.add_argument('--expected-static-source-bundle',help='Expected source bundle SHA-256')
    p.add_argument('--system-font-resolution',help='Explicit macOS CoreText resolution receipt for source system-font Labels')
    p.add_argument('--expected-system-font-resolution',help='Expected resolution receipt SHA-256')
    p.add_argument('--static-font-generation',help='Pinned generated CoreText SDF receipt for an explicitly resolved static face')
    p.add_argument('--expected-static-font-generation',help='Expected generated SDF receipt SHA-256')
    p.add_argument('--spine-bindings',help='Pinned source component and resource emission receipt for Creator')
    p.add_argument('--expected-spine-bindings',help='Expected Spine emission receipt SHA-256')
    p.add_argument('--spine-resources',help='Frozen monkey Creator Spine resource candidate')
    p.add_argument('--namespace',required=True)
    p.add_argument('--bindings')
    p.add_argument('--animation',action='append',help='Select a source AnimationClip ID; default all normalized clips')
    p.add_argument('--target-profile',choices=[UNITY_PROFILE,cocos.PROFILE],required=True)
    p.add_argument('--out',required=True)
    p = sub.add_parser('prepare-button-material-retry', help='Prepare a pinned Unity adapter for source-backed tiled Button target Images')
    for flag in ('candidate','expected-manifest','plan','ir','out'):
        p.add_argument('--'+flag, required=True)
    p = sub.add_parser('prepare-context-preview', help='Prepare a source-proven parent capture for an isolated Unity copy')
    for flag in ('project','source-manifest','parent-id','target-id','out'):
        p.add_argument('--'+flag, required=True)
    p = sub.add_parser('shard-unity-plan', help='Checkpoint all owned Unity plan inputs in verified chunks')
    p.add_argument('--plan', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--expected-manifest', required=True)
    p.add_argument('--max-new-chunks', type=int)
    p = sub.add_parser('restore-unity-plan', help='Reassemble the exact owned plan stage from its pinned index')
    p.add_argument('--index', required=True)
    p.add_argument('--expected-index', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('export')
    p.add_argument('--plan',required=True)
    p.add_argument('--out',required=True)
    p = sub.add_parser('verify', description='Unity import instructions are limited to 256 MiB and checked against the candidate manifest.')
    p.add_argument('--candidate',required=True)
    p.add_argument('--level',choices=['static','editor'],default='static')
    p.add_argument('--out',required=True)
    p = sub.add_parser('freeze-native-selection', help='Freeze selected saved Unity Prefabs with native identities and producer-declared compile dependencies')
    p.add_argument('--candidate', required=True)
    p.add_argument('--prefab', action='append', required=True, help='Exact candidate-relative Assets Prefab path; repeat to select more than one')
    p.add_argument('--expected-manifest', required=True)
    p.add_argument('--expected-readback', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('upgrade-native-runtime', help='Copy a frozen selection and upgrade only exact known native presentation templates')
    p.add_argument('--candidate', required=True)
    p.add_argument('--expected-manifest', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('recover-unity-prefabs', help='Recover selected Unity-source Prefabs from exact reader/provider caches and structural type evidence')
    p.add_argument('--request', required=True)
    p.add_argument('--expected-request', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--input-path-map', help='Explicit input-root relocation descriptor; original input hashes remain mandatory')
    p.add_argument('--expected-input-path-map', help='SHA256 of the explicit relocation descriptor')
    p = sub.add_parser('inspect-unity-prefab-schemas', help='Read exact built-in schemas from a pinned source bundle without executing game code')
    p.add_argument('--request', required=True)
    p.add_argument('--expected-request', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('rebuild-unity-prefab-texture-material-assets', help='Rebind selected original texture pixels into before-pinned native Materials; Shader semantics remain unverified')
    p.add_argument('--request', required=True)
    p.add_argument('--expected-request', required=True)
    p.add_argument('--unity-editor', required=True)
    p.add_argument('--budget-seconds', type=int, default=600)
    p.add_argument('--out', required=True)
    p = sub.add_parser('rebuild-unity-prefab-assets', help='Create and independently reopen explicitly selected source-derived native Sprite assets')
    p.add_argument('--request', required=True)
    p.add_argument('--expected-request', required=True)
    p.add_argument('--unity-editor', required=True)
    p.add_argument('--budget-seconds', type=int, default=600)
    p.add_argument('--out', required=True)
    p = sub.add_parser('verify-unity-prefabs', help='Verify a selected Unity-source candidate in a fresh owned native Editor project')
    p.add_argument('--headless', action='store_true', help='Use no graphics or Editor window; visible presentation remains not_run')
    p.add_argument('--candidate', required=True)
    p.add_argument('--expected-manifest', required=True)
    p.add_argument('--unity-editor', required=True)
    p.add_argument('--budget-seconds', type=int, default=600)
    p.add_argument('--out', required=True)
    p.add_argument('--input-path-map', help='Explicit input-root relocation descriptor; original input hashes remain mandatory')
    p.add_argument('--expected-input-path-map', help='SHA256 of the explicit relocation descriptor')
    p = sub.add_parser('freeze-unity-prefabs', help='Freeze exact independently reopened Unity-source candidate bytes')
    p.add_argument('--native-output', required=True)
    p.add_argument('--expected-execution', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--input-path-map', help='Explicit input-root relocation descriptor; original input hashes remain mandatory')
    p.add_argument('--expected-input-path-map', help='SHA256 of the explicit relocation descriptor')
    p = sub.add_parser('audit-native-code-dependencies', help='Supplement a frozen selection with exact producer code proofs without changing its warnings')
    p.add_argument('--candidate', required=True)
    p.add_argument('--expected-manifest', required=True)
    p.add_argument('--producer-candidate', required=True)
    p.add_argument('--expected-producer-manifest', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('prepare-source-system-fonts', help='Resolve pinned source system Labels using existing CoreText and Unity font contracts')
    p.add_argument('--request',required=True);p.add_argument('--expected-request',required=True);p.add_argument('--out',required=True)
    p = sub.add_parser('generate-source-system-fonts', help='Generate and validate static glyph inputs from a pinned source font preparation')
    p.add_argument('--preparation',required=True);p.add_argument('--expected-preparation',required=True);p.add_argument('--out',required=True)
    p.add_argument('--budget-seconds',type=int,default=240)
    p = sub.add_parser('complete-native-font', help='Append an explicitly pinned consumer text corpus using the same static font face and preserved glyphs')
    p.add_argument('--request', required=True)
    p.add_argument('--expected-request', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('stage-native-font', help='Prepare a separate native Unity project to apply a pinned static-font completion')
    p.add_argument('--candidate', required=True)
    p.add_argument('--expected-manifest', required=True)
    p.add_argument('--completion', required=True)
    p.add_argument('--expected-completion', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('finish-native-font', help='Freeze the actually saved font candidate after native identity and glyph checks')
    p.add_argument('--project', required=True)
    p.add_argument('--expected-stage-manifest', required=True)
    p.add_argument('--readback', required=True)
    p.add_argument('--expected-readback', required=True)
    p.add_argument('--out', required=True)
    p = sub.add_parser('handoff')
    p.add_argument('--candidate',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--native-contract',action='store_true',help='Read existing Sprite importer, actual fileID and Prefab reference evidence')
    p = sub.add_parser('diff')
    p.add_argument('--before',required=True);p.add_argument('--after',required=True);p.add_argument('--out',required=True)
    p = sub.add_parser('register')
    p.add_argument('--candidate',required=True);p.add_argument('--out',required=True)
    p = sub.add_parser('apply')
    p.add_argument('--target',required=True);p.add_argument('--candidate',required=True)
    p.add_argument('--expected-manifest',required=True);p.add_argument('--out',required=True)
    p.add_argument('--write',action='store_true');p.add_argument('--preview')
    args = parser.parse_args(argv)
    unity_parse_limits={k:v for k,v in [('objectValues',getattr(args,'unity_object_value_limit',None)),('containerValues',getattr(args,'unity_container_value_limit',None))] if v is not None} or None
    try:
        if args.command=='resource-probe':
            from .resource_probe import prepare,prepare_shader
            result=prepare_shader(args.candidate,args.expected_manifest,args.shader,args.out) if args.shader else prepare(args.candidate,args.expected_manifest,args.spine,args.out)
            print(json.dumps(result,ensure_ascii=False));return 0
        if args.command=='diagnose':
            from .diagnostics import diagnose
            result=diagnose(args.source,args.out,args.evidence,args.max_issues,args.max_document_bytes)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['status']=='no_reported_gaps' else 1
        if args.command=='doctor':
            from .operations import doctor
            result=doctor(args.out,args.unity_editor,args.creator_editor,args.provider_python)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['status']=='ready_for_checked_scope'else 1
        if args.command=='space-preview':
            from .operations import space_preview
            result=space_preview(args.root,args.out,args.protect,args.max_files)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['status']=='preview' else 1
        if args.command=='acquire-resources':
            from .acquisition import prepare,acquire
            from .inputs import input_set
            settings=prepare(args.manifest,args.out,input_set(args.input_set),args.cache_root,args.budget_seconds,
                             resume_from=args.resume_from,max_attempts=args.max_attempts)
            result=acquire(settings,args.offline)
            print(json.dumps(dict(status='complete' if result['summary']['allDeclaredAvailable'] else 'partial',
                report=str(result['receipt']),inputSet=str(result['inputSet']),summary=result['summary']),ensure_ascii=False))
            return 0 if result['summary']['allDeclaredAvailable'] else 1
        if args.command in ('query-methods','query-tables','inspect-aliases'):
            from .evidence_queries import query_methods,query_tables,inspect_aliases
            try:
                if args.command=='query-methods':
                    result=query_methods(args.source,args.expected_sha,args.out,member=args.member,type_name=args.type,
                                         method=args.method,module=args.module,function=args.function,limit=args.limit)
                elif args.command=='query-tables':
                    result=query_tables(args.manifest,args.expected_manifest_sha,args.out,source=args.source,
                                        expected=args.expected_sha,member=args.member,contains=args.contains,extract=args.extract,limit=args.limit)
                else:
                    result=inspect_aliases(args.source,args.expected_sha,args.out,member=args.member,alias=args.alias,limit=args.limit,
                                           content_source=args.content_source,content_prefix=args.content_prefix)
            except (zipfile.BadZipFile,EOFError) as error:fail('EVIDENCE_ARCHIVE',args.source or args.manifest,str(error))
            print(json.dumps(dict(status=result['status'],operation=result['operation'],report=str(args.out)+'/inspection.json'),ensure_ascii=False))
            return 0
        if args.command == 'recover-unity-prefabs':
            from .unity_prefab_recovery import recover
            from .input_relocation import command_context
            with command_context(args):
                result = recover(args.request, args.expected_request, args.out)
            print(json.dumps(dict(status=result['status'], report=str(args.out)+'/result.json', native=result['native']), ensure_ascii=False))
            return 1 if result['status'] == 'needs_action' else 0
        if args.command == 'inspect-unity-prefab-schemas':
            from .unity_prefab_recovery import pinned
            from .unity_prefab_schemas import extract_builtin_schemas
            _, raw = pinned(dict(path=args.request, sha256=args.expected_request), 8 * 1024 * 1024)
            request = json.loads(raw)
            if request.get('contract') != 'monkey-unity-prefab-builtin-schema-request/1' or request.get('schemaVersion') != 1:
                fail('UNITY_PREFAB_BUILTIN_SCHEMA_REQUEST', args.request, 'Versioned built-in schema request required')
            result = extract_builtin_schemas(request['source']['path'], request['source']['sha256'], request['providerPython'],
                request['wantedObjects'], args.out, budget_seconds=request.get('budgetSeconds',120), prior_reader_evidence=request.get('priorReaderEvidence'))
            print(json.dumps(dict(status=result['status'],report=str(args.out)+'/receipt.json',processExited=result['processExited']), ensure_ascii=False))
            return 0 if result['status'] == 'schemas_read' else 1
        if args.command == 'rebuild-unity-prefab-texture-material-assets':
            from .unity_prefab_texture_material_rebuild import execute
            result = execute(args.request, args.expected_request, args.out, args.unity_editor, args.budget_seconds)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.command == 'rebuild-unity-prefab-assets':
            from .unity_prefab_asset_rebuild import execute
            result = execute(args.request, args.expected_request, args.out, args.unity_editor, args.budget_seconds)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        if args.command == 'verify-unity-prefabs':
            from .unity_prefab_native import execute
            from .input_relocation import command_context
            with command_context(args):
                result = execute(args.candidate, args.expected_manifest, args.out, args.unity_editor, args.budget_seconds, headless=args.headless)
            print(json.dumps({k:v for k,v in result.items() if k != 'savedFiles'}, ensure_ascii=False))
            return 0 if result['status'] == 'native-verified-subset' else 1
        if args.command == 'freeze-unity-prefabs':
            from .unity_prefab_native import freeze
            from .input_relocation import command_context
            with command_context(args):
                result = freeze(args.native_output, args.expected_execution, args.out)
            print(json.dumps(result, ensure_ascii=False))
            return 1 if result['status'] == 'needs_action' else 0
        if args.command == 'capabilities':
            from .output_limits import policy
            from .code_profiles import profile_capabilities
            legacy_profile_capabilities=profile_capabilities()
            print(json.dumps(dict(version=__version__, byteBudgets=default_byte_budgets(), profiles=[PROFILE,PROJECT_PROFILE,'cocos-2.4.11-bundle','cocos-3.8.7-bundle','cocos-3.4.1-bundle','cocos-2.1.2-resource','generic-image-resources-v1','egret-custom-resource-plist-v1'], targetProfiles=[UNITY_PROFILE,cocos.PROFILE], activeTargetProfiles=[UNITY_PROFILE], pausedCompatibilityTargetProfiles=[cocos.PROFILE],
                ownership=dict(recoveryCandidates='monkey',developmentProjectOperations='beaver',workflow='GREA'),
                unityPrefabRecovery=dict(command='recover-unity-prefabs',requestContract='monkey-unity-prefab-recovery-request/1',scope='selected-source-roots-and-provider-GUID-closure',nativeCommand='verify-unity-prefabs',native='implemented-acceptance-pending',sourceCodeExecuted=False),
                nativeSdkDeclarations=dict(command='audit-native-code-dependencies',contract='monkey-native-sdk-declaration/1',schemaVersion=1,coverage='manifest-pinned-Spine-stage-and-literal-script-reference-tuples',assemblyInspectionOwner='beaver',migration='not-performed'),
                codeRecovery=dict(status='partial',sourceExecution=False,lexicalGraph='complete-source-static-binding-and-utf8-spans',typedModules='explicit-source-class-method-hashes-and-call-domain',moduleProfiles=legacy_profile_capabilities['profiles'],moduleProfileExtensions=legacy_profile_capabilities['extensions'],selection='optional-strict-typed-dependency-closure-and-lowering',methods='default-full-source-best-effort-CSharp-bodies;unknown-fragments-retained',fullDrafts=dict(commands=['code-draft','convert'],typeContractRequired=False,sourceMethods='all-indexed-plus-auxiliary-functions',fields='known-class-or-unresolved-owner-binding',diagnostics='source-linked-bounded-shards',compilation='excluded;syntax-and-API-errors-allowed'),projectPostprocess=dict(commands=['code-project-prepare','code-project-run','code-project-status','code-project-resume','code-project-pause','code-project-configure','code-project-recheck'],scope='all-manifest-owned-CSharp-files',execution='single-CLI-continuous-batches;per-batch-limits;exact-session',status='legacy-file-repair;active-run-superseded'),nativeArchitecture=dict(commands=['code-architecture-prepare','code-architecture-run','code-architecture-status','code-architecture-recheck','code-architecture-refine','code-native-prepare','code-native-run','code-native-status','code-native-continue','code-native-reassemble','code-native-revise','code-native-add-json','code-architecture-module-prepare','code-architecture-module-run','code-architecture-module-status','code-architecture-module-recheck','code-architecture-module-recover'],scope='complete-frozen-source-modules-members-and-resources',layers=['Bootstrap','Domain','Gameplay','Presentation','Services'],execution='single-existing-Codex-CLI;versioned-source-and-target-ownership',status='architecture-design-stage-available;native-implementation-in-progress'),optionalPostprocess=dict(commands=['code-postprocess','code-postprocess-resume'],defaultEnabled=False,provider='existing-local-Codex-CLI',workspace='independent-selected-code-copy',sourceCandidate='immutable',budgets='total-idle-output',resume='exact-recorded-session-only'),packageComposition='exact-frozen-resource-reuse;one-manifest-with-Scene-Prefab-JSON-and-CSharp',incremental='owned-candidate-fingerprints-and-hash-verified-reuse',mono='static-decompiler-drafts;legal-fixture-target-compiled',il2cpp='v29-exact-WASM-body-evidence;8-pure-i64-operator-fragments;caller-map-assumption;stateful-bodies-not-lifted',native='separate-probe-required;not-implied-by-emission'),
                recoveryOperations=dict(commands=['acquire-resources','diagnose','doctor','space-preview','resource-probe'],
                    resume='same-manifest-and-input-set; completed-partial-receipt-to-fresh-layer; rehash-selected-payloads',
                    retries='1..3; transient-network-or-408-429-5xx-only; fixed-byte-time-budgets',
                    diagnostics='selected-existing-evidence; no source parsing or target-byte validation implied',space='metadata-preview-only; no deletion',
                    spine='creator-3.8.8/standard-3.8-native-reference-page-time-and-pose-representatives',shader='exact-cocos-2.4.15-builtin-2d-sprite-macro-profile'),
                evidenceInspection=dict(commands=['query-methods','query-tables','inspect-aliases'],inputs=['strict-streamed-json-array','manifest-hashed-table-zip','exact-url-content-alias-index'],sourceExecution=False,metadataIsMethodBody=False,hashVerification='complete-selected-source; outer-ZIP-not-implied',maxSourceBytes=536870912,maxRowBytes=8388608,maxResults=1000),
                projectOperations=dict(status='deprecated-compatibility',owner='beaver',commands=['adopt','adopt-recover','register','apply'],replacement='beaver-0.1.0-local-verified;consumer-switch-pending',scope='frozen-transition-implementation; not a new monkey mainline capability',unityNative='representative-move-and-reopen-verified-on-predecessor-WIP; latest-add-folder-runtime-not_run',creatorNative='unsupported'),
                outputPolicy=dict(wholeInput=policy({'scopeMode':'whole-input'}),selection=policy({}),hashChunkBytes=1048576,sourceDecoderBudgets='independent'),
                additionalPackageProfiles={'cocos-3.4.1-bundle':dict(scope='version-proven-node-ui-prefab-and-resource-subset',graphs='856-of-857-source-graphs;22503-nodes;52-instances;one-null-quaternion-rejected',native='5-source-frames-plus-6-prefabs-331-nodes-8-instances-7-mounted-nodes-1-mounted-widget-both-targets-verified',operations=['package-convert']), 'egret-custom-resource-plist-v1':dict(scope='reviewed-custom-resource-manifest-plist-binjson-v2',targets=['unity6'],sourceSkins='typed-data-only-native-layout-pending',remoteAcquisition='explicit-manifest-cache-and-bounded-fetch',native='132-source-frames-verified; expanded-atlas-set-pending',operations=['package-convert']), 'cocos-2.1.2-resource':dict(scope='version-proven-resource-subset',native='211-source-frames-both-targets-verified',graphs='pending',operations=['package-convert']), 'generic-image-resources-v1':dict(scope='derived-original-image-gallery-only',families=['laya','layaair','egret','eraget','custom','other'],targets=['unity6'],native='Egret-16-derived-images-verified',sourceGraphs='not-restored',operations=['package-convert']), 'cocos-2.4.11-bundle':dict(scope='version-proven-published-bundle-subset',native='91-source-graphs-both-targets-verified',operations=['package-convert']), 'cocos-3.8.7-bundle':dict(scope='version-proven-node-ui-template-and-resource-subset',native='83-static-graphs-plus-4-prefab-5-native-relations-and-16-node-dynamic-ui-representatives-both-targets-verified',graphs='114-root-closures-static;5-graphs-missing-6-exact-templates;not-all-native-validated',operations=['package-convert'])},
                toolkit=dict(contract='grea-toolkit/1',runner='monkey tool <id>',tools=list(__import__('monkey.toolkit',fromlist=['TOOLS']).TOOLS)),
                 schemaVersion=1, dynamicUi=dict(probeVersion=2,verifiedLayoutGroups=6,verifiedLayoutStates=54,native='historical-v02-grid-scale-constraints-child-resize-and-linear-scale-representatives',timing='Editor-native-forced-update;Player-not_run',unityFlowReplacement=dict(status='verified-subset',sourcePrefabs=48,sourceComponents=63,aggregateAssets=50,representatives=6,scope='horizontal-flexible-unscaled-uniform-grid-or-proven-single-row',otherLayouts='review-required;no-source-flow-runtime-fallback',sourceText='questionnaire-Label-not-recovered;Rect-resize-only')), formatting=dict(implemented=['unity-creator-unimported-owned-grea-v1','fresh-package-convert-none-grea'],pending=['unity-general-scene-native-format','unity-source-positive-native-move-sample'],rejected=['materialized-native-assets-require-a-future-native-move-adapter']), unitySourceProfile=dict(inspectionPolicy=dict(defaultObjectValues=250000,defaultContainerValues=8000000,maxObjectValues=1000000,maxContainerValues=16000000,maxDepth=96,streamedFields=['Font.m_FontData','AssetBundle.m_PreloadTable'],chunkElements=8192,maxPayloadBytes=268435456),name='unityfs-unitypy-1.25.3-assetripper-2.0.0',status='partial',inputs='explicit-unity-bundle-or-webdata-files-and-exact-local-texture-cache',additionalContainers=['UnityWebData1.0'],invalidTexturePolicy='block-default-explicit-quarantine-retains-original',dependencyClosure='explicit-frozen-pool-exact-serialized-file-closure',editor='one-prefab-schema-reference-save-reload-verified',publicNative=True,nativeProfile='unity-leaf-prefab-sprite-array-v1',textureHydration=dict(selectionManifest='unity-texture-selection/1',scopes=['container','selected-texture-set'],cachePaths='exact-frozen-literal-bucket-and-token-filename',partialDerivative=True,partialExitCode=1,selectedPngExport='unity-selected-texture-export/1'),shaderHandoff='monkey-shader-handoff/1',nativeFormatting='typed-resource-moves-with-dynamic-path-pins; real sample pinned all 134 assets',methodsRecovered=0), implemented=['shard-unity-plan','restore-unity-plan','prepare-button-material-retry','prepare-context-preview','static-code-bindings','recover-native-execution','prepare-source-text-reference','capture-source-text-reference','complete-static-spine-defaults','refresh-static-spine-helpers','continue-static-prefabs','generate-source-system-fonts','prepare-source-system-fonts','rebuild-unity-prefab-texture-material-assets','rebuild-unity-prefab-assets','inspect-unity-prefab-schemas','recover-unity-prefabs','verify-unity-prefabs','freeze-unity-prefabs','audit-native-code-dependencies','stage-native-font','finish-native-font','complete-native-font','upgrade-native-runtime','freeze-native-selection','prefab-static-fields','prefab-behavior-ir','code-draft','code-types','freeze-resource-candidate','acquire-resources','diagnose','doctor','space-preview','resource-probe','query-methods','query-tables','inspect-aliases','adopt','adopt-recover','unity-field-plan','convert','catalog','inspect','normalize','plan','export','verify','handoff','diff','register','apply','preflight','native-import','research-matrix','code-model','code-emit','code-select','wasm-code-source','wasm-code-candidate','unity-code-source','unity-code-candidate','code-native-probe','format-project','project-model','inspect-unity','export-unity','unity-code-model','index-unity','hydrate-unity','export-unity-textures','classify-unity-shaders','code-handoff','native-finish-plan','native-finish','acquire-unity-textures','prepare-unity-bulk','export-unity-bulk','freeze-handoff','freeze-unity-handoff','native-layout-audit','native-layout-prepare','native-layout-patch','native-layout-finish','native-layout-bundle'], planned=[],
                targetValidation={UNITY_PROFILE:dict(static='implemented',editor='representative-subset-verified',visual='not_run'),cocos.PROFILE:dict(static='implemented',editor='representative-subset-verified',visual='not_run')},
                compiledFormats=['compiled-v1','pack-v1','texture-pack-v1'],
                containerFormats=['plain-wxapkg','APK-ZIP','Cocos-resource-directory'],
                packageWorkflow=dict(fileAccounting='implemented',staticModuleRecovery='partial',codeDrafts='default-full-source-actual-CSharp-drafts-with-source-linked-sharded-diagnostics',
                                     nativeObjectRecovery='shared-ir-supported-subset',packageResume='hash-checked',inputSets='explicit-local-roots',editorOrchestration='manifest-bound-native-import-command',remoteAcquisition='explicit-manifest-bounded-fetch',cocosCodeLanguages=['ts','js'],defaultCocosCodeLanguage='ts',numericCodeContracts=['numeric-call-subdomain-v1','static-number-methods-v1'],staticNumericScope='reviewed-Creator3-descriptor-helper-and-lexical-dependency; no component binding'),
                imageFormats=['PNG','JPEG','ASTC (optional pinned decoder)'],animationSchemaVersion=1,
                animationSubset=['local-position','local-scale','opacity','linear','constant-step','Normal','Loop'],animationEvents='manual-contract-only', targetEditorValidation='representative-subsets-only'), ensure_ascii=False))
            return 0
        if args.command == 'adopt':
            print('Deprecated compatibility: development-project adoption belongs to beaver; beaver 0.1.0 has local verification; consumer switch is still pending. See docs/V0.5-ADOPTION.md.',file=sys.stderr)
            if args.execute:
                if not args.plan or not args.expected_plan or not args.editor_path or any((args.candidate,args.target,args.baseline,args.lineage)):
                    parser.error('adopt --execute requires --plan --expected-plan --editor-path and no candidate/target/baseline')
                from .adoption_native import execute
                result=execute(args.plan,args.out,args.editor_path,args.budget_seconds,args.expected_plan)
            else:
                if not args.candidate or not args.target or any((args.plan,args.expected_plan,args.editor_path)):
                    parser.error('adopt preview requires --candidate --target and optional --baseline')
                from .adoption import preview
                result=preview(args.candidate,args.target,args.out,args.baseline,args.lineage)
            print(json.dumps(result,ensure_ascii=False));return 1 if result['status']=='blocked' else 0
        if args.command == 'adopt-recover':
            print('Deprecated compatibility: recovery of existing adoption transactions is retained during beaver handoff.',file=sys.stderr)
            from .adoption_native import recover
            result=recover(args.transaction,args.editor_path,args.budget_seconds)
            print(json.dumps(result,ensure_ascii=False));return 0
        if args.command == 'code-emit':
            if args.module_contract or args.module_profile:
                if args.numeric_field or args.namespace!='monkey-project' or args.cocos_code_language!='ts':parser.error('Module emission excludes legacy numeric/namespace/language flags; use the typed contract namespace')
                from .code_modules import emit,emit_profile
                result=(emit_profile if args.module_profile else emit)(args.source,args.module_profile or args.module_contract,args.out,reuse_from=args.reuse_from,expected_manifest_sha256=args.expected_manifest,configuration_table=args.configuration_table)
            else:
                if not args.numeric_field or args.reuse_from or args.expected_manifest or args.configuration_table:parser.error('Legacy code emission requires --numeric-field and excludes module/configuration flags')
                from .code_emit import emit
                result=emit(args.source,args.code_model,args.out,args.numeric_field,args.cocos_code_language,args.namespace)
            print(json.dumps(result,ensure_ascii=False));return 1
        if args.command == 'freeze-resource-candidate':
            from .package_modules import freeze_native_resources
            result=freeze_native_resources(args.candidate,args.expected_manifest,args.expected_readback,args.out)
            print(json.dumps(result,ensure_ascii=False));return 1 if result['workflowStatus']=='partial'else 0
        if args.command == 'code-draft':
            from .code_drafts import emit
            result=emit(args.source,args.out,expected_source_sha256=args.expected_source,reuse_from=args.reuse_from,expected_manifest_sha256=args.expected_manifest)
            print(json.dumps(result,ensure_ascii=False));return 1
        if args.command=='code-native-add-json':
            from .code_architecture_resources import add_json_assets
            from .io import read,safe,sha
            result=add_json_assets(args.candidate,args.expected_manifest,args.spec,args.expected_spec,args.out)
            path=safe(args.out)/'manifest.json'
            print(json.dumps(dict(status='candidate_json_added_unvalidated',manifestPath=str(path),
                manifestSha256=sha(read(path,max_bytes=128*1024*1024)),fileCount=len(result['files']),
                compileStatus=result['compileStatus'],runtimeStatus=result['runtimeStatus']),ensure_ascii=False));return 0
        if args.command=='code-native-revise':
            from .code_architecture_revision import revise_native_candidate
            from .io import read,safe,sha
            manifest=revise_native_candidate(args.candidate,args.expected_manifest,args.revision,args.expected_revision,args.out)
            path=safe(args.out)/'manifest.json'
            revision=manifest['architectureRevision']
            print(json.dumps(dict(status='candidate_revised_unvalidated',implementationStatus=manifest['implementationStatus'],
                manifestPath=str(path),manifestSha256=sha(read(path,max_bytes=128*1024*1024)),fileCount=len(manifest['files']),
                revisionId=revision['revisionId'],revisionPlanSha256=revision['revisionPlanSha256'],changedFileCount=len(revision['changes']),
                compileStatus=manifest['compileStatus'],runtimeStatus=manifest['runtimeStatus']),ensure_ascii=False));return 0
        if args.command in ('code-native-prepare','code-native-run','code-native-status','code-native-reassemble','code-native-continue'):
            from . import code_architecture_pipeline as native
            if args.command=='code-native-prepare':
                from .io import load,read,safe
                references=load(read(safe(args.external_references_file),max_bytes=1024*1024))if args.external_references_file else None
                result=native.prepare(args.architecture,args.out,codex=args.codex,timeout_seconds=args.budget_seconds,
                    idle_seconds=args.idle_seconds,external_references=references,retained_support_paths=args.retained_support_path)
            elif args.command=='code-native-run':result=native.run(args.run)
            elif args.command=='code-native-continue':result=native.continue_run(args.run,args.out,args.priority,stop_after_module=args.stop_after)
            elif args.command=='code-native-reassemble':
                from .code_architecture_reassembly import reassemble
                result=reassemble(args.run,args.out,allow_incomplete=args.allow_incomplete)
            else:result=native.status(args.run)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['status']in ('prepared','candidate_assembled_unvalidated','integration_checkpoint')or args.command=='code-native-status' else 1
        if args.command in ('code-architecture-module-prepare','code-architecture-module-run','code-architecture-module-status','code-architecture-module-recheck','code-architecture-module-recover'):
            from . import code_architecture_modules as module
            if args.command=='code-architecture-module-prepare':
                if bool(args.previous)!=bool(args.expected_previous_manifest):
                    raise ValueError('--previous and --expected-previous-manifest must be supplied together')
                previous=dict(root=args.previous,manifestSha256=args.expected_previous_manifest)if args.previous else None
                from .io import load,read,safe
                supplements=load(read(safe(args.supplemental_csharp_spec),max_bytes=1024*1024)) if args.supplemental_csharp_spec else []
                result=module.prepare(args.architecture,args.module,args.out,dependency_roots=args.dependency,previous_module=previous,supplemental_sources=supplements,
                    codex=args.codex,timeout_seconds=args.budget_seconds,idle_seconds=args.idle_seconds)
            elif args.command=='code-architecture-module-run':result=module.run(args.run,session_id=args.session)
            elif args.command=='code-architecture-module-recheck':result=module.recheck(args.run)
            elif args.command=='code-architecture-module-recover':result=module.recover(args.run)
            else:result=module.status(args.run)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['status']in ('prepared','generated_unreviewed','rechecked')or args.command=='code-architecture-module-status' else 1
        if args.command in ('code-architecture-prepare','code-architecture-run','code-architecture-status','code-architecture-recheck','code-architecture-refine'):
            from . import code_architecture as architecture
            if args.command=='code-architecture-prepare':
                result=architecture.prepare(args.candidate,args.expected_manifest,args.out,namespace=args.namespace,codex=args.codex,
                    timeout_seconds=args.budget_seconds,idle_seconds=args.idle_seconds)
            elif args.command=='code-architecture-run':result=architecture.run(args.run,session_id=args.session)
            elif args.command=='code-architecture-recheck':result=architecture.recheck(args.run)
            elif args.command=='code-architecture-refine':result=architecture.refine(args.run,args.out,codex=args.codex,timeout_seconds=args.budget_seconds,idle_seconds=args.idle_seconds)
            else:result=architecture.status(args.run)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['status'] in ('prepared','architecture_designed') or args.command=='code-architecture-status' else 1
        if args.command == 'code-postprocess':
            from .code_postprocess import prepare,run
            from .io import safe,read
            task=read(safe(args.task_file),max_bytes=16000).decode('utf-8')
            prepared=prepare(args.candidate,args.selected_path,args.expected_manifest,args.out,task,
                evidence_root=args.evidence_root,evidence_files=args.evidence_file,codex=args.codex,
                timeout_seconds=args.budget_seconds,no_progress_seconds=args.idle_seconds)
            if args.prepare_only:
                print(json.dumps(dict(status='prepared',request=str(prepared.manifest_path),workspace=str(prepared.workspace),modelStarted=False),ensure_ascii=False));return 0
            result=run(prepared)
            print(json.dumps(dict(status=result['status'],report=str(prepared.output/'manifest.json'),sessionId=result.get('sessionId'),changedFiles=len(result.get('actualChanges',[])),unresolved=len(result.get('unresolved',[]))),ensure_ascii=False));return 0 if result['status']=='complete' else 1
        if args.command == 'code-postprocess-resume':
            from .code_postprocess import run
            result=run(args.run,session_id=args.session)
            print(json.dumps(dict(status=result['status'],report=str(Path(args.run)/'manifest.json'),sessionId=result.get('sessionId'),changedFiles=len(result.get('actualChanges',[])),unresolved=len(result.get('unresolved',[]))),ensure_ascii=False));return 0 if result['status']=='complete' else 1
        if args.command == 'code-project-prepare':
            from .code_project_postprocess import prepare
            result=prepare(args.candidate,args.expected_manifest,args.out,max_files=args.batch_max_files,max_code_bytes=args.batch_code_bytes,
                batch_seconds=args.batch_seconds,idle_seconds=args.idle_seconds,max_attempts=args.attempts,codex=args.codex)
            print(json.dumps(result,ensure_ascii=False));return 0
        if args.command in ('code-project-run','code-project-status','code-project-resume'):
            from . import code_project_postprocess as project
            result=project.status(args.run) if args.command=='code-project-status' else project.resume(args.run,retry_failed=args.retry_failed) if args.command=='code-project-resume' else project.run(args.run)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['status'] in ('complete','complete_with_partial') or args.command=='code-project-status' else 1
        if args.command in ('code-project-pause','code-project-configure'):
            from . import code_project_postprocess as project
            result=project.request_pause(args.run,finish_current=args.after_current_attempt) if args.command=='code-project-pause' else project.configure(args.run,batch_seconds=args.batch_seconds,idle_seconds=args.idle_seconds)
            print(json.dumps(result,ensure_ascii=False));return 0
        if args.command=='code-project-recheck':
            from .code_project_postprocess import recheck
            print(json.dumps(recheck(args.run),ensure_ascii=False));return 0
        if args.command == 'code-types':
            from .code_type_evidence import extract_type_evidence
            from .io import load,read,safe,new_output,write_json
            source=safe(args.source);selectors=safe(args.selectors);evidence=safe(args.type_evidence) if args.type_evidence else None
            result=extract_type_evidence(source,load(read(selectors,max_bytes=64*1024)),load(read(evidence,max_bytes=128*1024)) if evidence else None,namespace=args.namespace if evidence else args.namespace or 'Game.Domain.Recovered')
            out=new_output(args.out,[source,selectors]+([evidence] if evidence else []));write_json(out/'type-evidence.json',result)
            if result['status']=='ready' and result.get('contract'):write_json(out/'module-contract.json',result['contract'])
            if result.get('fillableContract'):write_json(out/'missing-types.json',result['fillableContract'])
            print(json.dumps(dict(status=result['status'],report=str(out/'type-evidence.json'),contract=str(out/'module-contract.json') if result['status']=='ready' and result.get('contract') else None,missing=str(out/'missing-types.json') if result.get('fillableContract') else None),ensure_ascii=False));return 0 if result['status']=='ready' else 1
        if args.command == 'code-select':
            from .code_selection import write_selection
            result=write_selection(args.source,args.selectors,args.out,type_evidence=args.type_evidence,module_profile=args.module_profile)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['status']=='selected_ready' else 1
        if args.command == 'unity-code-source':
            from .unity_code_sources import inspect as inspect_code_source
            result=inspect_code_source(args.source,args.out,expected_sha256=args.expected_source,family=args.family,provider=args.provider,metadata=args.metadata,method_map=args.method_map,expected_metadata_sha256=args.expected_metadata,expected_method_map_sha256=args.expected_method_map)
            print(json.dumps(result,ensure_ascii=False));return 1
        if args.command == 'unity-code-candidate':
            from .unity_code_candidate import prepare_candidate
            print(json.dumps(prepare_candidate(args.source_report,args.out,expected_report_sha256=args.expected_report,method_ids=args.method_id),ensure_ascii=False));return 1
        if args.command == 'wasm-code-source':
            from .wasm_code_sources import inspect_wasm
            from .io import load,read,safe
            result=inspect_wasm(args.source,args.out,expected_source_sha256=args.expected_source,metadata=args.metadata,expected_metadata_sha256=args.expected_metadata,method_map=args.method_map,expected_method_map_sha256=args.expected_method_map,decoded_segments=load(read(safe(args.decoded_segments),max_bytes=1024*1024)),method_ids=args.method_id,brotli_provider=args.brotli_provider)
            print(json.dumps(result,ensure_ascii=False));return 1
        if args.command == 'wasm-code-candidate':
            if len(args.source_report)!=len(args.expected_report):parser.error('Supply one --expected-report SHA256 per source report, in the same order')
            from .wasm_code_semantics import recover_wasm_subset
            refs=[dict(report=p,expectedSha256=h)for p,h in zip(args.source_report,args.expected_report)]
            print(json.dumps(recover_wasm_subset(refs,args.out,selections=args.method),ensure_ascii=False));return 1
        if args.command == 'code-native-probe':
            if args.interactive:
                from .code_interactive_probe import prepare
                result=prepare(args.candidate,args.expected_manifest,args.out)
            else:
                from .code_native_probe import prepare
                result=prepare(args.candidate,args.expected_manifest,args.out,recipe_module=args.recipe_module)
            print(json.dumps(result,ensure_ascii=False));return 0
        if args.command == 'acquire-unity-textures':
            from .unity_texture_acquisition import acquire
            result=acquire(args.inspection,args.cache_manifest,args.cdn_source,args.cdn_root,args.out,args.cache_root,args.budget_seconds,args.workers,args.resume)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['status']=='captured'else 1
        if args.command == 'hydrate-unity':
            from .unity_textures import hydrate
            result=hydrate(args.source,args.texture_cache,args.provider_python,args.out,args.budget_seconds,args.selection_manifest)
            print(json.dumps(result,ensure_ascii=False))
            return 0 if result['status']=='hydrated' else 1
        if args.command == 'export-unity-textures':
            from .unity_texture_export import export as export_textures
            result=export_textures(args.source,args.derivative,args.hydration_report,args.expected_hydration_sha256,args.selection_manifest,args.provider_python,args.out,args.budget_seconds)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['status']=='exported'else 1
        if args.command == 'classify-unity-shaders':
            from .shader_handoff import classify_project
            result=classify_project(args.project,args.manifest,args.expected_manifest,args.out,args.source_mapping,args.expected_source_mapping)
            print(json.dumps(result,ensure_ascii=False));return 0
        if args.command == 'index-unity':
            from .unity_index import catalog as index_unity
            result=index_unity(args.manifest,args.provider_python,args.out,args.budget_seconds)
            print(json.dumps(result,ensure_ascii=False))
            return 0 if result['status']=='indexed' else 1
        if args.command == 'unity-field-plan':
            from .unity_field_plan import plan as unity_field_plan
            result = unity_field_plan(args.candidate,args.trusted,args.trusted_sha256,args.bindings,args.inventory,
                                      args.inventory_sha256,args.source,args.metadata,args.target_root,args.out)
            print(json.dumps(result,ensure_ascii=False))
            return 0 if result['writable'] else 1
        if args.command == 'unity-code-model':
            from .unity_code_model import model as unity_code_model
            print(json.dumps(unity_code_model(args.inspection,args.out,args.bulk),ensure_ascii=False))
            return 1
        if args.command == 'export-unity':
            from .providers.assetripper import export as export_unity
            result=export_unity(args.source,args.asset_ripper,args.out,args.budget_seconds)
            print(json.dumps(result,ensure_ascii=False))
            return 1
        if args.command == 'inspect-unity':
            from .sources.unity_serialized import inspect as inspect_unity
            if args.bundle_manifest:
                from .unity_batch import inspect_set
                result=inspect_set(args.source,args.bundle_manifest,args.provider_python,args.out,args.budget_seconds,args.schema_manifest,parse_limits=unity_parse_limits)
            else:
                result = inspect_unity(args.source,args.provider_python,args.out,args.budget_seconds,schema_manifest=args.schema_manifest,parse_limits=unity_parse_limits)
            print(json.dumps(result,ensure_ascii=False))
            return 0 if result['status']=='inspected' else 1
        if args.command == 'format-project':
            from .layout.standard import VERSION
            fail('FORMAT_RETIRED',args.project,'Post-export formatting is retired; convert again to get a '+VERSION+' project (docs/PROJECT-SPEC.md)')
        if args.command == 'layout-preview':
            from .layout import load_overrides
            from .layout.records import preview
            print(json.dumps(preview(args.conversion,args.out,load_overrides(args.layout)[0] if args.layout else None),ensure_ascii=False))
            return 0
        if args.command == 'layout-migration':
            from .layout.records import migration
            print(json.dumps(migration(args.old,args.new,args.out),ensure_ascii=False))
            return 0
        if args.command == 'project-model':
            from .project_model import inspect as project_model
            print(json.dumps(project_model(args.candidate,args.out),ensure_ascii=False))
            return 0
        if args.command == 'native-layout-audit':
            from .native_layout_patch import audit
            print(json.dumps(audit(args.candidate,args.out,args.expected_manifest),ensure_ascii=False));return 0
        if args.command == 'native-layout-prepare':
            from .native_layout_patch import prepare
            print(json.dumps(prepare(args.audit,args.out,args.previous_execution),ensure_ascii=False));return 0
        if args.command == 'native-layout-patch':
            from .native_layout_patch import execute
            result=execute(args.preparation,args.out,args.editor,args.budget_seconds,args.deadline_utc,args.window_end_utc,args.execute)
            print(json.dumps(result,ensure_ascii=False));return 0 if result.get('status')in('planned','completed')else 2
        if args.command == 'native-layout-finish':
            from .native_layout_patch import finish
            print(json.dumps(finish(args.execution,args.out),ensure_ascii=False));return 0
        if args.command == 'native-layout-bundle':
            from .native_layout_patch import bundle
            print(json.dumps(bundle(args.delta,args.out),ensure_ascii=False));return 0
        if args.command == 'freeze-unity-handoff':
            from .unity_bulk_freeze import freeze as freeze_unity
            print(json.dumps(freeze_unity(args.candidate,args.texture_cache,args.source_manifest,args.source_root,args.out,args.expected_manifest),ensure_ascii=False));return 0
        if args.command == 'freeze-handoff':
            from .bulk_handoff import freeze
            print(json.dumps(freeze(args.candidate,args.native_contract,args.verification,args.out,args.expected_manifest,args.apply_owned),ensure_ascii=False));return 0
        if args.command == 'export-unity-bulk':
            from .unity_bulk_prepare import export_prepared
            result=export_prepared(args.prepared,args.asset_ripper,args.out,args.budget_seconds,args.deadline_utc,args.window_end_utc)
            print(json.dumps({k:result.get(k)for k in ('status','stage','pid','processExited','exitCode','outputFiles','outputBytes','nativeAssetFiles','sourceUnchanged','error')},ensure_ascii=False));return 0 if result['status']=='exported_partial'else 1
        if args.command == 'prepare-unity-bulk':
            from .unity_bulk_prepare import prepare as prepare_bulk
            result=prepare_bulk(args.inspection,args.texture_cache,args.capture,args.provider_python,args.out,args.budget_seconds,args.resume)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['status']=='prepared'else 1
        if args.command == 'native-finish':
            from .cocos_native_finish import execute as native_finish
            result=native_finish(args.candidate,args.preparation,args.out,args.editor_path,args.expected_manifest,args.budget_seconds,args.deadline_utc,args.window_end_utc,args.execute,args.previous_execution)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['status']in ('planned','completed')else 1
        if args.command == 'native-finish-plan':
            from .cocos_native_finish import prepare
            print(json.dumps(prepare(args.candidate,args.out,args.exclude_scene),ensure_ascii=False));return 0
        if args.command == 'handoff' and args.native_contract:
            from .cocos_native_contract import export as native_contract
            print(json.dumps(native_contract(args.candidate,args.out),ensure_ascii=False));return 0
        if args.command == 'code-handoff':
            from .cocos_code_handoff import enrich
            print(json.dumps(enrich(args.candidate,args.out,args.expected_manifest,args.apply_owned,args.reuse_facts,args.expected_facts),ensure_ascii=False))
            return 1
        if args.command == 'code-model':
            if args.lexical_graph:
                if not args.expected_source or args.bulk:parser.error('--lexical-graph requires --expected-source and excludes --bulk')
                from .code_graph import inspect as code_model
                result=code_model(args.source,args.out,args.expected_source,args.method_id)
            else:
                if not args.module_name or args.expected_source or args.method_id:parser.error('Legacy code-model requires --module-name; graph flags require --lexical-graph')
                from .code_model import inspect as code_model
                result=code_model(args.source,args.out,args.module_name,bulk=args.bulk)
            print(json.dumps(result,ensure_ascii=False))
            return 1
        if args.command == 'research-matrix':
            from .research_cases import discover
            print(json.dumps(discover(args.root,args.out),ensure_ascii=False))
            return 0
        if args.command == 'convert':
            typed_requested=any((args.code_source,args.module_contract,args.module_selectors,args.configuration_table,args.reuse_candidate,args.expected_candidate))
            typed_settings=None
            if typed_requested:
                if args.target not in ('unity','unity6',UNITY_PROFILE) or not args.out: parser.error('Typed package modules require --target unity6 and a fresh --out')
                if any((args.numeric_code_contract,args.resume,args.recipe,args.asset_index,args.all_assets,args.bindings,args.animation,args.native,args.remote_manifest)):
                    parser.error('Typed package modules use fresh local package/candidate assembly; numeric/slice/resume/native/remote flags cannot combine')
                from .package_modules import settings as module_settings
                typed_settings=module_settings(args.code_source,args.module_contract,args.module_selectors,args.configuration_table)
                if args.reuse_candidate:
                    if not args.expected_candidate or any((args.source,args.input_set,args.reuse_source_stages,args.layout,args.namespace,args.provider_python,args.asset_ripper,args.format)):
                        parser.error('Frozen candidate composition requires --expected-candidate and excludes fresh source/layout/provider options')
                    from .package_modules import assemble
                    result=assemble(args.reuse_candidate,args.expected_candidate,args.out,typed_settings)
                    drafts=result.get('codeDrafts') or {}
                    draft_summary={k:v for k,v in drafts.items() if k!='files'}
                    draft_summary['generatedFiles']=len(drafts.get('files',[]))
                    print(json.dumps(dict(status=result['status'],completed=result['completed'],projects=result['projects'],codeModules=result.get('codeModules'),codeDrafts=draft_summary,report=str(Path(args.out).resolve()/'conversion-result.json')),ensure_ascii=False));return 1
                if args.expected_candidate: parser.error('--expected-candidate requires --reuse-candidate')
                if args.source_family not in ('auto','cocos'): parser.error('Fresh typed JS package conversion currently requires Cocos; use frozen Unity resources for other source routes')
            if args.numeric_code_contract and any((args.resume,args.recipe,args.reuse_source_stages,args.asset_index,args.bindings,args.animation)):
                parser.error('--numeric-code-contract requires fresh package source stages')
            if args.cocos_code_language!='ts' and not args.numeric_code_contract:parser.error('--cocos-code-language requires --numeric-code-contract')
            if args.format is not None and (args.resume or args.recipe):parser.error('--format requires a fresh package conversion; resume/recipe retain their declared contract')
            generic_selection=None
            generic_family=args.source_family if args.source_family in ('laya','layaair','egret','eraget','custom','other')else None
            if args.source_family=='auto' and args.source_profile in ('generic-image-resources-v1','egret-custom-resource-plist-v1'):
                generic_family='egret'if args.source_profile=='egret-custom-resource-plist-v1'else'other'
            if args.input_set and args.source_family=='auto':
                from .inputs import input_set
                generic_selection=input_set(args.input_set)
                if generic_selection['sourceProfile']=='generic-image-resources-v1':generic_family='other'
                elif generic_selection['sourceProfile']=='egret-custom-resource-plist-v1':generic_family='egret'
            if generic_family:
                if typed_settings: parser.error('Typed JS modules require a Cocos package or an explicit frozen resource candidate')
                if args.target not in ('unity','unity6',UNITY_PROFILE):parser.error('Non-Cocos sources target Unity 6 only')
                if not all((args.source or args.input_set,args.target,args.out))or args.source and args.input_set:parser.error('Image-resource conversion requires --source or --input-set, --target unity6 and --out')
                if args.source_profile and args.source_profile not in ('generic-image-resources-v1','egret-custom-resource-plist-v1'):parser.error('Resource sources require a supported explicit resource profile')
                if unity_parse_limits or any((args.resume,args.recipe,args.reuse_source_stages,args.numeric_code_contract,args.provider_python,args.asset_ripper,args.unity_texture_cache,args.unity_schema_manifest,args.unity_dependency_manifest,args.unity_quarantine_invalid_textures,args.asset_index,args.all_assets,args.bindings,args.animation,args.dependency_source,args.evidence_source,args.cocos_code_language!='ts',args.provider_budget_seconds!=600)):
                    parser.error('Initial generic image profile supports explicit local roots; source adapters, remote manifests and source code binding are pending')
                if not args.remote_manifest and any((args.remote_cache_root,args.acquisition_out,args.remote_budget_seconds!=900)):parser.error('Remote options require --remote-manifest')
                acquired=None;remote_settings=None;conversion_input_set=args.input_set
                if args.remote_manifest:
                    if not args.input_set:parser.error('Egret remote acquisition requires an explicit --input-set')
                    from .inputs import input_set
                    generic_selection=generic_selection or input_set(args.input_set)
                    if generic_selection['sourceProfile']!='egret-custom-resource-plist-v1':parser.error('Generic family image acquisition is pending; remote resource roots require the reviewed Egret profile')
                    from .acquisition import prepare
                    acquisition_out=Path(args.acquisition_out).resolve()if args.acquisition_out else Path(args.out).resolve().with_name(Path(args.out).resolve().name+'-acquired')
                    remote_settings=prepare(args.remote_manifest,acquisition_out,generic_selection,args.remote_cache_root,args.remote_budget_seconds,[Path(args.out).resolve()])
                if args.native and args.offline:parser.error('--native cannot combine with --offline')
                if not args.native and any((args.native_out,args.unity_editor,args.creator_editor,args.native_budget_seconds!=1200)):parser.error('native options require --native')
                settings=None
                if args.native:
                    from .orchestration import options
                    from .inputs import input_set
                    generic_selection=generic_selection or (input_set(args.input_set)if args.input_set else None)
                    roots=[r['path']for r in generic_selection['inputs']]if generic_selection else [args.source]
                    if remote_settings:roots.append(acquisition_out)
                    settings=options(args.out,args.target,args.native_out,args.unity_editor,args.creator_editor,args.native_budget_seconds,roots)
                if remote_settings:
                    from .acquisition import acquire
                    acquired=acquire(remote_settings,args.offline);conversion_input_set=str(acquired['inputSet'])
                from .resource_package import convert as convert_images
                result=convert_images(args.source,args.target,args.out,args.namespace or 'monkey-project',args.offline,conversion_input_set,args.format or 'none',generic_family,args.source_profile)
                if acquired:
                    from .acquisition import attach
                    attach(result,args.out,acquired)
                summary=dict(status=result['workflowStatus'],completed=result['completed'],resultKind=result['resultKind'],sourceFamily=result['sourceFamily'],sourceProfile=result['sourceProfile'],completionScope=result['completionScope'],sourceSpriteFrames=result['sourceSpriteFrames'],derivedFullImageFrames=result.get('derivedFullImageFrames',0),sourceData=result.get('sourceData'),projects=result['projects'],diagnostics=result['diagnostics'],report=str(Path(args.out).resolve()/'conversion-result.json'))
                if settings:
                    from .orchestration import run
                    summary['nativeExecution']=run(result,settings)
                print(json.dumps(summary,ensure_ascii=False));return 1
            source_file=Path(args.source) if args.source else None
            unity_source=args.source_family=='unity'
            if args.source_family=='auto' and source_file and source_file.is_file():
                from .io import safe as safe_source
                from .sources.unity_serialized import container_kind
                with safe_source(source_file).open('rb') as stream:unity_source=container_kind(stream.read(16)) is not None
            if unity_source:
                if typed_settings: parser.error('Reuse the frozen Unity resource candidate for source-bound module assembly')
                if args.numeric_code_contract or args.cocos_code_language!='ts':parser.error('Numeric JS code contracts/language selection require Cocos package sources')
                if args.native and args.offline:parser.error('--native cannot combine with --offline')
                if args.native and (not args.unity_editor or args.creator_editor):parser.error('Unity source --native requires only --unity-editor')
                if not args.native and any((args.native_out,args.unity_editor,args.creator_editor,args.native_budget_seconds!=1200)):parser.error('native options require --native')
                if args.target not in ('unity','unity6',UNITY_PROFILE):parser.error('Unity sources target Unity 6 only')
                if not all((args.source,args.out,args.provider_python,args.asset_ripper)):parser.error('Unity source requires --source --out --provider-python --asset-ripper')
                if any((args.input_set,args.resume,args.recipe,args.reuse_source_stages,args.asset_index,args.all_assets,args.bindings,args.animation,args.evidence_source,args.source_profile,args.namespace)):
                    parser.error('Unity source profile accepts explicit bundle/dependency/texture inputs; input sets/slice options are not implemented')
                if not args.remote_manifest and any((args.remote_cache_root,args.acquisition_out,args.remote_budget_seconds!=900)):parser.error('remote options require --remote-manifest')
                if args.unity_dependency_manifest and args.dependency_source:parser.error('Choose --unity-dependency-manifest or explicit --dependency-source')
                native_settings=None;remote_settings=None;acquired=None
                protected=[]
                if args.native or args.remote_manifest:
                    from .unity_acquisition import protected_inputs
                    protected=protected_inputs(args.source,args.dependency_source,args.unity_texture_cache,args.unity_schema_manifest,args.unity_dependency_manifest,args.provider_python,args.asset_ripper)
                if args.remote_manifest:
                    from .unity_acquisition import prepare
                    from .io import safe
                    if safe(args.out).exists():parser.error('Choose a fresh conversion output before acquisition')
                    acquisition_out=safe(args.acquisition_out or str(args.out)+'-acquired')
                    remote_settings=prepare(args.source,acquisition_out,args.remote_manifest,args.remote_cache_root,args.remote_budget_seconds,[*protected,safe(args.out)])
                    protected.extend([acquisition_out,remote_settings['manifest']])
                    if remote_settings['cache']:protected.append(remote_settings['cache'])
                if args.native:
                    from .orchestration import options
                    native_settings=options(args.out,args.target,args.native_out,args.unity_editor,args.creator_editor,args.native_budget_seconds,protected)
                inputs=dict(dependencies=args.dependency_source,texture_cache=args.unity_texture_cache,dependency_manifest=args.unity_dependency_manifest)
                if remote_settings:
                    from .acquisition import acquire
                    from .unity_acquisition import merge
                    acquired=acquire(remote_settings,args.offline)
                    inputs=merge(acquired,**{k:inputs[k]for k in ('texture_cache','dependency_manifest','dependencies')})
                from .recover_unity import convert as convert_unity
                result=convert_unity(args.source,args.out,args.provider_python,args.asset_ripper,args.provider_budget_seconds,schema_manifest=args.unity_schema_manifest,quarantine_invalid_textures=args.unity_quarantine_invalid_textures,export_scope=args.unity_export_scope,code_evidence=args.unity_code_evidence,reuse_inspection=args.unity_reuse_inspection,prepared_textures=args.unity_prepared_textures,reuse_export=args.unity_reuse_provider_export,layout_path=args.layout,parse_limits=unity_parse_limits,**inputs)
                if acquired:
                    from .unity_acquisition import attach
                    attach(result,args.out,acquired)
                if native_settings:
                    from .unity_native import finish_conversion
                    result=finish_conversion(result,native_settings,args.format or 'none')
                print(json.dumps(dict(status=result['status'],completed=result['completed'],resultKind=result['resultKind'],sourceFamily='unity',projects=result['projects'],diagnostics=[{k:d.get(k)for k in ('code','references','message')}for d in result['diagnostics']],nativeExecution=result.get('nativeExecution'),remoteAcquisition=result.get('acquisition'),format=result['format'],report=str(Path(args.out).resolve()/'conversion-result.json')),ensure_ascii=False))
                return 1
            if args.unity_export_scope!='reachable' or args.unity_code_evidence or args.unity_reuse_inspection or args.unity_prepared_textures or args.unity_reuse_provider_export:parser.error('Unity bulk export/code evidence require a Unity source')
            if unity_parse_limits or args.provider_python or args.asset_ripper or args.unity_texture_cache or args.unity_schema_manifest or args.unity_dependency_manifest or args.unity_quarantine_invalid_textures or args.provider_budget_seconds!=600:parser.error('Unity provider options require a Unity source')
            from .convert import convert, resume, recipe
            if not args.remote_manifest and any((args.remote_cache_root,args.acquisition_out,args.remote_budget_seconds!=900)):
                parser.error('remote options require --remote-manifest')
            if args.remote_manifest and (not args.input_set or args.resume):
                parser.error('--remote-manifest requires a fresh conversion with explicit --input-set')
            if not args.native and any((args.native_out,args.unity_editor,args.creator_editor,args.native_budget_seconds!=1200)):
                parser.error('native options require --native')
            if args.native and (args.offline or args.resume or args.recipe):
                parser.error('--native requires a fresh package conversion and cannot combine with --offline/--resume/--recipe')
            if args.reuse_source_stages and not args.input_set:parser.error('--reuse-source-stages requires --input-set and fresh --out')
            if args.resume and args.input_set:
                if any((args.source,args.target,args.out,args.recipe,args.asset_index,args.all_assets,args.bindings,
                        args.dependency_source,args.evidence_source,args.animation,args.source_profile,args.namespace,args.package,args.reuse_source_stages)):
                    parser.error('package resume accepts --resume, --input-set and optional --offline only')
                from .package import resume_package
                result=resume_package(args.resume,args.input_set,args.offline,layout_path=args.layout)
                print(json.dumps(dict(status=result['workflowStatus'],resultKind=result['resultKind'],completed=result['completed'],
                                      projects=result['projects'],report=str(Path(args.resume).resolve()/'conversion-result.json')),ensure_ascii=False))
                return 1
            source_path=Path(args.source) if args.source else None
            package_mode=args.input_set or args.package or args.target in ('both','unity6','cocos38') or (source_path is not None and
                (source_path.suffix.lower() in ('.apk','.wxapkg') or source_path.is_dir() and not args.asset_index and not args.recipe))
            if (args.numeric_code_contract or typed_settings) and not package_mode:parser.error('Source-bound code contracts require package conversion')
            if package_mode:
                if not all((args.source or args.input_set,args.target,args.out)) or args.source and args.input_set or any((args.resume,args.recipe,args.asset_index,
                        args.dependency_source,args.evidence_source,args.bindings,args.animation,args.source_profile)):
                    parser.error('package conversion requires --source/--target/--out; slice options are unsupported')
                from .package import convert_package
                selection=None
                if args.input_set and (args.native or args.remote_manifest):
                    from .inputs import input_set
                    selection=input_set(args.input_set)
                acquired=None;remote_settings=None
                acquisition_out=Path(args.acquisition_out).resolve() if args.acquisition_out else Path(args.out).resolve().with_name(Path(args.out).resolve().name+'-acquired')
                if args.remote_manifest:
                    from .acquisition import prepare
                    remote_settings=prepare(args.remote_manifest,acquisition_out,selection,args.remote_cache_root,args.remote_budget_seconds,[Path(args.out).resolve()])
                native_settings=None
                if args.native:
                    from .orchestration import options
                    if args.input_set:
                        source_roots=[r['path'] for r in selection['inputs']]
                    else:source_roots=[args.source]
                    if remote_settings:source_roots.append(acquisition_out)
                    native_settings=options(args.out,args.target,args.native_out,args.unity_editor,args.creator_editor,args.native_budget_seconds,source_roots)
                conversion_input_set=args.input_set
                if remote_settings:
                    from .acquisition import acquire
                    acquired=acquire(remote_settings,args.offline);conversion_input_set=str(acquired['inputSet'])
                    if args.reuse_source_stages and Path(conversion_input_set).resolve()!=Path(args.input_set).resolve():
                        raise ValueError('New acquired files require fresh source stages; acquired evidence is preserved')
                result=convert_package(args.source,args.target,args.out,args.namespace or 'monkey-project',args.offline,conversion_input_set,reuse_source_stages=args.reuse_source_stages,format_profile=args.format or 'none',code_contract=args.numeric_code_contract,cocos_code_language=args.cocos_code_language,layout_path=args.layout,typed_modules=typed_settings)
                if acquired:
                    from .acquisition import attach
                    attach(result,args.out,acquired)
                summary=dict(status=result['workflowStatus'],resultKind=result['resultKind'],
                     completed=result['completed'],projects=result['projects'],format=result.get('format'),inputFiles=result['inputFiles'],
                     inputBytes=result['inputBytes'],diagnostics=len(result['diagnostics']),nextAction=result['nextAction'],
                     report=str(Path(args.out).resolve()/'conversion-result.json'))
                if acquired:summary['remoteAcquisition']=dict(acquired['summary'],receipt=str(acquired['receipt']))
                if native_settings:
                    from .orchestration import run
                    summary['nativeExecution']=run(result,native_settings)
                    if summary['nativeExecution']['status']!='not_run':
                        summary['nextAction']=dict(code='REVIEW_NATIVE_AND_SOURCE_GAPS',message='Review native receipt; source/visual/business gaps remain separate')
                print(json.dumps(summary,ensure_ascii=False))
                return 1
            if args.format=='grea':parser.error('--format grea requires a fresh package conversion')
            if args.native:parser.error('--native requires package conversion (use --target unity6/cocos38/both or --package)')
            if args.resume:
                if any((args.source,args.target,args.out,args.source_profile,args.asset_index,args.all_assets,
                        args.dependency_source,args.evidence_source,args.bindings,args.animation,args.offline,args.recipe,args.namespace)):
                    parser.error('--resume cannot be combined with conversion inputs')
                result = resume(args.resume)
            elif args.recipe:
                if not args.out or any((args.source,args.target,args.source_profile,args.asset_index,args.all_assets,
                                        args.dependency_source,args.evidence_source,args.bindings,args.animation,args.namespace)):
                    parser.error('--recipe requires --out and cannot be combined with explicit input options')
                result = convert(output=args.out,offline=args.offline,**recipe(args.recipe))
            else:
                if not all((args.source,args.target,args.out)):
                    parser.error('convert requires --source, --target and --out (or --resume)')
                result = convert(args.source,args.target,args.out,args.namespace or 'monkey-project',args.source_profile,
                             args.asset_index,args.all_assets,args.dependency_source,args.evidence_source,
                             args.bindings,args.animation,args.offline)
            print(json.dumps(dict(status=result['workflowStatus'], resultKind=result['resultKind'], completed=result['completed'], project=result['project'],
                                  diagnostics=len(result['diagnostics']), validation=result['validation'],
                                  nextAction=result['nextAction'],report=result.get('report') or str(Path(args.out).resolve()/'manifest.json')), ensure_ascii=False))
            return 2 if result['workflowStatus']=='failed' else 1
        if args.command == 'inspect':
            if args.source_profile == PROJECT_PROFILE:
                if args.dependency_source or args.evidence_source: parser.error('Editable project does not accept bundle dependencies')
                result=inspect_project(args.source,args.asset_index,args.out)
            else:
                result = inspect(args.source, args.asset_index, args.out,args.dependency_source,args.evidence_source)
        elif args.command == 'catalog':
            result=catalog(args.source,args.out)
        elif args.command == 'normalize':
            result = normalize(args.manifest, args.out)
        elif args.command == 'continue-static-prefabs':
            from .prefab_static_continuation import prepare
            result=prepare(args.request,args.expected_request,args.out)
            print(json.dumps({k:result[k]for k in ('preparationStatus','planPath','familyResults','native','visual')},ensure_ascii=False))
            return 0 if result['preparationStatus']=='prepared' else 1
        elif args.command == 'refresh-static-spine-helpers':
            from .prefab_static_spine_refresh import prepare
            result=prepare(args.request,args.expected_request,args.out)
            print(json.dumps({k:result[k] for k in ('preparationStatus','planPath','native','visual')},ensure_ascii=False))
            return 0 if result['preparationStatus']=='prepared' else 1
        elif args.command == 'complete-static-spine-defaults':
            from .prefab_static_spine_defaults import prepare
            result=prepare(args.request,args.expected_request,args.out)
            print(json.dumps({k:result[k]for k in ('status','planPath','rendering','native','visual')},ensure_ascii=False))
            return 0 if result['status']=='prepared' else 1
        elif args.command == 'prepare-source-text-reference':
            from .prefab_source_text_reference import prepare
            result=prepare(args.request,args.expected_request,args.out)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['status']=='prepared' else 1
        elif args.command == 'capture-source-text-reference':
            from .prefab_source_text_reference import capture
            result=capture(args.preparation,args.expected_preparation,args.browser_executable,args.out,timeout_seconds=args.timeout_seconds)
            print(json.dumps(result,ensure_ascii=False));return 0 if result['status']=='captured' else 1
        elif args.command == 'prefab-static-fields':
            from .prefab_static_pipeline import project_ir
            result=project_ir(args.manifest,args.ir,args.out)
        elif args.command == 'prefab-behavior-ir':
            from .prefab_behavior_pipeline import project_ir as prefab_behavior_ir
            result=prefab_behavior_ir(args.manifest,args.ir,args.source_bundle,args.expected_source_bundle,args.out)['manifest']
        elif args.command == 'plan':
            if args.target_profile==cocos.PROFILE:
                if args.system_font_resolution or args.expected_system_font_resolution or args.static_font_generation or args.expected_static_font_generation:parser.error('Explicit TMP system-font resolution applies only to Unity')
                result=cocos.plan(args.ir,args.namespace,args.out,args.bindings,args.animation,spine_bindings=args.spine_bindings,expected_spine_bindings=args.expected_spine_bindings,spine_resources=args.spine_resources,static_source_bundle=args.static_source_bundle,expected_static_source_bundle=args.expected_static_source_bundle)
            else:
                if args.spine_bindings or args.expected_spine_bindings or args.spine_resources:parser.error('Spine component receipt currently requires Creator; Unity runtime binding is pending')
                result=plan(args.ir,args.namespace,args.out,args.bindings,args.animation,system_font_resolution=args.system_font_resolution,expected_system_font_resolution=args.expected_system_font_resolution,static_font_generation=args.static_font_generation,expected_static_font_generation=args.expected_static_font_generation,static_source_bundle=args.static_source_bundle,expected_static_source_bundle=args.expected_static_source_bundle)
        elif args.command == 'diff':
            result=incremental.diff(args.before,args.after,args.out)
        elif args.command == 'apply':
            result=incremental.apply(args.target,args.candidate,args.expected_manifest,args.out,Path.cwd(),args.write,args.preview)
        elif args.command == 'register':
            from .io import new_output, write_json, finish
            record=incremental.register(args.candidate,Path.cwd())
            out=new_output(args.out,[Path(args.candidate).resolve()]);write_json(out/'registration.json',record)
            result=finish(out,dict(schemaVersion=1,diagnostics=[],registration=record))
        elif args.command == 'prepare-button-material-retry':
            from .button_material_retry import prepare
            print(json.dumps(prepare(args.candidate,args.expected_manifest,args.plan,args.ir,args.out)))
            return 0
        elif args.command == 'prepare-context-preview':
            from .prefab_context_preview import prepare_request
            print(json.dumps(prepare_request(args.project,args.source_manifest,args.parent_id,args.target_id,args.out)))
            return 0
        elif args.command == 'shard-unity-plan':
            from .export_plan import shard
            result = shard(args.plan, args.out, args.expected_manifest, args.max_new_chunks)
            print(json.dumps(result))
            return 1 if result['status'] == 'paused' else 0
        elif args.command == 'restore-unity-plan':
            from .export_plan import restore
            print(json.dumps(restore(args.index, args.expected_index, args.out)))
            return 0
        elif args.command == 'export':
            from .targets.unity import dispatch_export
            result = dispatch_export(args.plan, args.out)
            output_path=Path(args.out).resolve()
            if output_path.is_relative_to(Path.cwd()/'outputs'):
                incremental.register(output_path,Path.cwd())
        elif args.command == 'native-import':
            from .native import native_import
            result=native_import(args.candidate,args.out,args.editor_path,args.expected_manifest,args.budget_seconds,args.deadline_utc,args.window_end_utc,args.execute,render_preview=args.render_preview)
            print(json.dumps({k:result.get(k) for k in ('status','processStarted','processExited','pid','reason','report')},ensure_ascii=False))
            return 0 if result['status'] in ('planned','candidate') else 1
        elif args.command == 'recover-native-execution':
            from .native import recover_execution
            result=recover_execution(args.request,args.expected_request,args.out)
            print(json.dumps(result,ensure_ascii=False))
            return 0
        elif args.command == 'preflight':
            from .preflight import preflight
            result=preflight(args.candidate,args.out,args.log,args.progress)
        elif args.command in ('stage-native-font', 'finish-native-font'):
            from .native_font_stage import stage, finish_stage, NativeFontStageError
            try:
                if args.command == 'stage-native-font':
                    result = stage(args.candidate, args.expected_manifest, args.completion, args.expected_completion, args.out)
                else:
                    result = finish_stage(args.project, args.expected_stage_manifest, args.readback, args.expected_readback, args.out)
            except NativeFontStageError as exc:
                fail('NATIVE_FONT_STAGE_REJECTED', args.out, str(exc))
            print(json.dumps(result, ensure_ascii=False))
            return 0
        elif args.command == 'prepare-source-system-fonts':
            from .source_system_font_preparation import prepare
            prepared = prepare(args.request,args.expected_request,args.out)
            print(json.dumps(prepared.record,ensure_ascii=False))
            return 0 if prepared.status=='prepared' else 1
        elif args.command == 'generate-source-system-fonts':
            from .source_system_font_preparation import generate
            generated = generate(args.preparation,args.expected_preparation,args.out,budget_seconds=args.budget_seconds)
            print(json.dumps(generated.record,ensure_ascii=False))
            return 0 if generated.status=='prepared' else 1
        elif args.command == 'complete-native-font':
            from .io import read, load, sha
            from .native_font_completion import complete_native_font_from_corpus, NativeFontCompletionError
            raw_request = read(args.request)
            if sha(raw_request) != args.expected_request:
                fail('FONT_REQUEST_SHA_MISMATCH', args.request, 'Consumer font request differs from its pin')
            request = load(raw_request)
            allowed = {'corpus_path','expected_corpus_sha256','base_binding_path','expected_base_binding_sha256',
                'base_generation_receipt_path','expected_base_generation_receipt_sha256','base_static_plan_path',
                'expected_base_static_plan_sha256','static_font_asset_id','requested_primary_family',
                'expected_primary_style','watch_files'}
            required = allowed - {'requested_primary_family','expected_primary_style','watch_files'}
            if not isinstance(request, dict) or set(request) - allowed or required - set(request):
                fail('FONT_REQUEST_INVALID', args.request, 'Expected the documented pinned consumer font request fields')
            try:
                result = complete_native_font_from_corpus(**request,
                    generator_path=Path(__file__).parent / 'targets' / 'GenerateCoreTextSdf.swift', output_dir=args.out)
            except NativeFontCompletionError as exc:
                fail('FONT_COMPLETION_REJECTED', args.request, str(exc))
            print(json.dumps(result, ensure_ascii=False))
            return 0
        elif args.command == 'audit-native-code-dependencies':
            from .native_code_dependencies import audit
            result = audit(args.candidate, args.expected_manifest, args.producer_candidate,
                args.expected_producer_manifest, args.out)
            print(json.dumps(dict(status=result['status'], scripts=len(result['scripts']),
                uncovered=result['uncovered'], report=str(Path(args.out) / 'code-dependency-supplement.json'))))
            return 0
        elif args.command == 'upgrade-native-runtime':
            from .native_runtime_update import upgrade
            updated = upgrade(args.candidate, args.expected_manifest, args.out)
            print(json.dumps(dict(status='prepared', manifest=str(Path(args.out) / 'manifest.json'),
                runtimeUpdate=updated['runtimeUpdate']), ensure_ascii=False))
            return 0
        elif args.command == 'freeze-native-selection':
            from .native_selection import freeze
            frozen = freeze(args.candidate, args.prefab, args.out, args.expected_manifest, args.expected_readback)
            print(json.dumps(dict(status='frozen', manifest=str(Path(args.out) / 'manifest.json'),
                files=len(frozen['files']), selection=frozen['selection'],
                diagnostics=frozen.get('diagnostics', [])), ensure_ascii=False))
            return 0
        elif args.command == 'verify':
            from .io import safe, read, load
            from .io import stage_manifest
            profile=stage_manifest(safe(args.candidate)).get('targetProfile')
            result = (cocos.verify if profile==cocos.PROFILE else verify)(args.candidate,args.out,args.level)
        else:
            result = handoff(args.candidate,args.out)
        print(json.dumps(dict(status=result['status'], assets=result.get('counts',{}).get('assets',len(result.get('assets',[]))),
                              spriteFrames=result.get('counts',{}).get('spriteFrames',len(result.get('spriteFrames',[]))),
                              diagnostics=len(result['diagnostics']), report=str(args.out)+'/manifest.json'), ensure_ascii=False))
        return 1 if result['status'] == 'partial' else 0
    except (ParseError, OSError, ValueError, KeyError, TypeError, IndexError, RecursionError) as error:
        print(json.dumps(dict(status='error', code=getattr(error,'code','INPUT_ERROR'), message=str(error), **({'byteBudget': error.byte_budget} if hasattr(error, 'byte_budget') else {})), ensure_ascii=False), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
