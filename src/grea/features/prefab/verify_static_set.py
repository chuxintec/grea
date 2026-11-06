"""Save, cold-open and reimport a hash-pinned set of Prefabs in a fresh Unity project copy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from grea.common import hash_file
from grea.safe_paths import canonical_path, disjoint, relative_name

GUID = re.compile(r"[a-f0-9]{32}")
DIGEST = re.compile(r"[a-f0-9]{64}")
HEADER = re.compile(rb"^--- !u!(\d+) &(-?\d+)(?: stripped)?\r?$", re.M)
REFERENCE = re.compile(rb"\{fileID:\s*(-?\d+),\s*guid:\s*([0-9a-fA-F]{32}),\s*type:\s*\d+\}")
CAPTURES = {"ui", "model", "effect"}
COLUMNS = ("guid", "nodes", "components", "properties", "references", "externalPins", "hierarchy",
           "bindings", "persistedSha256", "error")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True, help="Trusted Unity candidate (copied, never edited)")
    parser.add_argument("--selection", type=Path, required=True, help="UTF-8 JSONL of assetPath, guid, sha256 and sourceNodes; optional source and capture")
    parser.add_argument("--expected-selection", required=True, help="SHA-256 of the exact selection bytes")
    parser.add_argument("--unity-editor", type=Path, required=True, help="Matching installed Unity 6 Editor executable")
    parser.add_argument("--output", type=Path, required=True, help="New directory for the isolated project and receipts")
    parser.add_argument("--budget-seconds", type=int, default=1800, help="Timeout per Editor phase, 30–7200 seconds")
    return parser


def selection_rows(raw):
    rows = []
    guids, paths = set(), set()
    for line in raw.splitlines():
        row = json.loads(line)
        if not isinstance(row, dict) or set(row) - {"assetPath","guid","sha256","sourceNodes","source","capture"}:
            raise ValueError("Unexpected selection fields")
        path = relative_name(row.get("assetPath", "")).as_posix()
        if not path.startswith("Assets/") or not path.endswith(".prefab"):
            raise ValueError(f"Expected a Prefab under Assets: {path}")
        guid = row.get("guid")
        if (not isinstance(guid,str) or not GUID.fullmatch(guid) or guid in guids or path.casefold() in paths or
                not isinstance(row.get("sha256"),str) or not DIGEST.fullmatch(row["sha256"]) or
                type(row.get("sourceNodes")) is not int or row["sourceNodes"] < 1 or
                row.get("capture") is not None and row["capture"] not in CAPTURES):
            raise ValueError(f"Invalid or duplicate selection: {path}")
        rows.append(row)
        guids.add(guid)
        paths.add(path.casefold())
    if not 1 <= len(rows) <= 100000:
        raise ValueError("Expected 1..100000 selected roots")
    return rows


def copy_inputs(project, target):
    # Copy just the authoring inputs. Links to outside projects and linked files
    # must never let the Editor write through the private copy to the caller.
    for name in ("Assets","Packages","ProjectSettings"):
        base = project/name
        if base.is_symlink() or not base.is_dir():
            raise ValueError(f"Missing or linked Unity input: {name}")
        for folder, subdirs, files in os.walk(base, followlinks=False):
            dest = target/Path(folder).relative_to(project)
            dest.mkdir(parents=True, exist_ok=True)
            for child in (*subdirs,*files):
                path = Path(folder)/child
                if path.is_symlink():
                    raise ValueError(f"Linked Unity input: {path}")
            for child in files:
                path = Path(folder)/child
                if not path.is_file():
                    raise ValueError(f"Unity input is not a regular file: {path}")
                shutil.copyfile(path,dest/child)


def freeze_expectations(project, rows, output):
    with (output/"roots.tsv").open("x",encoding="utf-8") as roots, (output/"references.tsv").open("x",encoding="utf-8") as refs:
        for row in rows:
            path = project/row["assetPath"]
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise ValueError(f"Prefab bytes differ from selection: {path}")
            meta = re.search(rb"^guid:\s*([a-f0-9]{32})\s*$",Path(str(path)+".meta").read_bytes(),re.M)
            if not meta or meta.group(1).decode()!=row["guid"]:
                raise ValueError(f"Prefab meta GUID differs: {path}")
            heads = list(HEADER.finditer(raw))
            ids = [int(h[2]) for h in heads]
            if len(set(ids))!=len(ids) or sum(h[1]==b"1" for h in heads)!=row["sourceNodes"]:
                raise ValueError(f"Source node count or local IDs differ: {path}")
            owned, instances = [], []
            for index, head in enumerate(heads):
                if head[1] == b"1001":
                    block = raw[head.end():heads[index+1].start() if index+1<len(heads) else len(raw)]
                    origin = re.search(rb"(?m)^  m_SourcePrefab: \{fileID: 100100000, guid: ([a-f0-9]{32}), type: 3\}", block)
                    if not origin:
                        raise ValueError(f"Unidentified nested Prefab instance in {path}")
                    instances.append(f"{int(head[2])}:{origin[1].decode()}")
                elif not head[0].rstrip().endswith(b"stripped"):
                    owned.append(int(head[2]))
            roots.write("\t".join((row["guid"],row["assetPath"],str(row["sourceNodes"]),
                                  ",".join(map(str,sorted(owned))),row.get("capture") or "",",".join(instances)))+"\n")
            for index, head in enumerate(heads):
                data = raw[head.end():heads[index+1].start() if index+1<len(heads) else len(raw)]
                if head[1] == b"1001" or head[0].rstrip().endswith(b"stripped"):
                    # Instance modifications are serialized on the handle. Check their
                    # source link natively and preserve the entire override block byte-for-byte.
                    continue
                tokens = sorted({f"{int(head[2])}:{guid.decode().lower()}:{int(local)}"
                                 for local,guid in REFERENCE.findall(data) if int(local)!=0})
                for token in tokens:
                    refs.write(row["guid"]+"\t"+token+"\n")


def phase_results(output, phase, rows, expected_version):
    completion = json.loads((output/(phase+"-completion.json")).read_text(encoding="utf-8"))
    if completion.get("editor") != expected_version or completion.get("roots")!=len(rows):
        raise ValueError(f"{phase}: Editor version or root count differs")
    result = {}
    with (output/(phase+".tsv")).open(encoding="utf-8") as stream:
        for line in stream:
            cells = line.rstrip("\r\n").split("\t")
            if len(cells)!=len(COLUMNS) or cells[0] in result:
                raise ValueError(f"{phase}: invalid or duplicate native receipt")
            result[cells[0]] = dict(zip(COLUMNS,cells))
    if result.keys()!={r["guid"] for r in rows}:
        raise ValueError(f"{phase}: missing or unexpected native roots")
    return result


def run(args):
    project = canonical_path(args.project)
    editor = canonical_path(args.unity_editor)
    source = canonical_path(args.selection)
    output = disjoint(args.output,project,source)
    if not editor.is_file() or not os.access(editor,os.X_OK) or not 30<=args.budget_seconds<=7200:
        raise ValueError("Expected a matching Unity executable and a 30..7200 second phase budget")
    if not DIGEST.fullmatch(args.expected_selection) or hash_file(source,max_bytes=128*1024**2)["sha256"]!=args.expected_selection:
        raise ValueError("Selection hash differs")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=args.expected_selection:
        raise ValueError("Selection changed before parsing")
    rows = selection_rows(raw)
    output.mkdir()
    (output/"selection.jsonl").write_bytes(raw)
    work = output/"Unity"
    copy_inputs(project,work)
    version_text = (work/"ProjectSettings/ProjectVersion.txt").read_text(encoding="utf-8")
    version = re.search(r"^m_EditorVersion: (\S+)$",version_text,re.M)
    if not version or not version[1].startswith("6000."):
        raise ValueError("Expected a Unity 6 project version")
    freeze_expectations(work,rows,output)
    scripts = work/"Assets/Editor/GreaStaticSet"
    scripts.mkdir(parents=True,exist_ok=False)
    template = Path(__file__).with_name("StaticSetProbe.cs.txt")
    shutil.copyfile(template,scripts/"StaticSetProbe.cs")
    shutil.copyfile(Path(__file__).with_name("StaticSetCapture.cs.txt"),scripts/"StaticSetCapture.cs")
    (output/"images").mkdir()
    receipts = {}
    has_images = any(row.get("capture") for row in rows)
    for phase in ("save","cold","repeat"):
        command = [str(editor),"-batchmode","-projectPath",str(work),"-executeMethod","Grea.StaticVerification.StaticSetProbe.Run",
                   "-logFile",str(output/(phase+".log"))]
        if not has_images or phase=="repeat":
            command.append("-nographics")
        env = dict(os.environ,GREA_STATIC_SET_RUN=str(output),GREA_STATIC_SET_PHASE=phase)
        try:
            with (output/(phase+"-console.log")).open("xb") as console:
                proc = subprocess.run(command,env=env,timeout=args.budget_seconds,check=False,stdout=console,stderr=subprocess.STDOUT)
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f"{phase}: Unity exceeded the {args.budget_seconds} second budget; inspect {output}/{phase}.log") from exc
        if proc.returncode not in (0,3):
            raise ValueError(f"{phase}: Unity exited {proc.returncode}; see {output}/{phase}.log")
        receipts[phase] = phase_results(output,phase,rows,version[1])
    failed = 0
    with (output/"results.jsonl").open("x",encoding="utf-8") as dest:
        for row in rows:
            observed = [receipts[p][row["guid"]] for p in ("save","cold","repeat")]
            errors = {r["error"] for r in observed if r["error"]}
            if observed[0]!=observed[1] or observed[1]!=observed[2]:
                errors.add("native save/cold/reimport observations differ")
            if observed[-1]["persistedSha256"]!=row["sha256"]:
                errors.add("persisted Prefab bytes differ from the frozen candidate")
            failed += bool(errors)
            dest.write(json.dumps(dict(**row,observed=observed[-1],status="partial" if errors else "verified",
                                       diagnostics=sorted(errors)),ensure_ascii=False)+"\n")
    summary = dict(schemaVersion=1,selectionSha256=args.expected_selection,editor=version[1],roots=len(rows),
                   verified=len(rows)-failed,partial=failed,phases=list(receipts),nativeProbeSha256=hash_file(template)["sha256"],
                   captureProbeSha256=hash_file(scripts/"StaticSetCapture.cs")["sha256"],
                   captures=sum(bool(r.get("capture")) for r in rows),gameplay="not_run",adoption="not_run")
    (output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary))
    return int(bool(failed))


def main(argv=None):
    args = build_parser().parse_args(argv)
    return run(args)
