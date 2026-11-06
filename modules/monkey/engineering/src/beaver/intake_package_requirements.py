"""Explicit, read-only package resolution context for existing intake plans."""
from .candidate_snapshot import snapshot, verify
from .adoption import project_requirements
from .intake import pinned
from .io import safe, new_output, write_json
from .output_limits import digest_file


def preview(candidate, target, source_project, editor_path, evidence, expected_evidence, output):
    incoming,manifest,files,manifest_sha=snapshot(candidate);verify(incoming,files)
    source,target,editor=safe(source_project),safe(target),safe(editor_path)
    proof=pinned(evidence,expected_evidence)
    context=dict(contract='beaver-unity-package-resolution/1',sourceProject=str(source),editorPath=str(editor),evidence=dict(path=str(proof),sha256=expected_evidence))
    requirements,conflicts=project_requirements(incoming,target,manifest['targetProfile'],resolution=context)
    out=new_output(output,[incoming,target,source,editor,proof])
    write_json(out/'package-resolution.json',context)
    report=dict(status='blocked' if conflicts else 'verified',candidateManifestSha256=manifest_sha,requirements=requirements,conflicts=conflicts,native='not_run',targetWrites=False)
    write_json(out/'package-requirements.json',report)
    return dict(status=report['status'],report=str(out/'package-requirements.json'),context=str(out/'package-resolution.json'),contextSha256=digest_file(out/'package-resolution.json'),native='not_run',targetWrites=False)
