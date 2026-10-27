"""Versioned output normalization. File integrity is not native or gameplay proof."""
from pathlib import Path
from grea.common import hash_file
from grea.safe_paths import canonical_path, relative_name, unique_paths
from .identity import read


def audit(workspace, version):
    root=canonical_path(workspace)
    report=read(root/'conversion-result.json',128*1024**2)
    if report.get('schemaVersion')!=1 or report.get('toolVersion')!=version:
        raise ValueError('Conversion report identity mismatch')
    rows=report.get('projects',[])
    if not isinstance(rows,list) or len(rows)>2:raise ValueError('Invalid project list')
    projects=[];total=0;count=0;project_names=set()
    for row in rows:
        name=relative_name(row['path']).as_posix()
        if name in project_names:raise ValueError('Duplicate target project')
        project_names.add(name);project=root/name
        manifest_path=project/('manifest.json' if 'manifestSha256' in row else 'recovery-manifest.json')
        identity=hash_file(manifest_path,128*1024**2)
        if 'manifestSha256' in row and row['manifestSha256']!=identity['sha256']:raise ValueError('Manifest changed')
        manifest=read(manifest_path,128*1024**2)
        if manifest.get('schemaVersion')!=1 or manifest.get('toolVersion')!=version:raise ValueError('Project version mismatch')
        files=manifest['files'];unique_paths([f['path'] for f in files]);names=set()
        for item in files:
            path=project/relative_name(item['path'])
            if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('Linked candidate output')
            actual=hash_file(path,32*1024**3-total);total+=actual['bytes'];count+=1
            if count>200000:raise ValueError('Output file budget exceeded')
            if actual['sha256']!=item['sha256'] or actual['bytes']!=item['bytes']:raise ValueError('Candidate file changed: '+item['path'])
            names.add(item['path'])
        # Unlisted source/config files can change the project and cannot be silently ignored.
        actual_names=set()
        unity=row.get('targetProfile','').startswith('unity') or 'targetVersion' in row
        directories=('Assets','Packages','ProjectSettings') if unity else ('assets','settings','extensions')
        for directory in (*directories,'Docs','Analysis','SourceRecovery'):
            base=project/directory
            if base.exists():
                import os
                for folder,dirs,leafs in os.walk(base,followlinks=False):
                    if any((Path(folder)/d).is_symlink() for d in dirs):raise ValueError('Linked project directory')
                    for leaf in leafs:actual_names.add((Path(folder)/leaf).relative_to(project).as_posix())
        if actual_names-names:raise ValueError('Unlisted project files require a new manifest')
        marker='ProjectSettings/ProjectVersion.txt' if unity else 'package.json'
        if marker not in names:raise ValueError('Editable engine project marker missing')
        entry='Docs/START-HERE.md'
        if entry not in names:raise ValueError('AI entry missing from verified files')
        projects.append(dict(path=name,manifest=identity,files=len(files),entry=entry,
                             native_graph_files=sum(n.endswith(('.prefab','.unity','.scene')) for n in names),
                             provider_validation=manifest.get('validation',{})))
    status=report.get('workflowStatus',report.get('status'))
    if status not in ('partial','needs_action','blocked','failed','success'):raise ValueError('Unknown provider status')
    return dict(schema_version=1,provider_version=version,status='needs_action',provider_status=status,
                projects=projects,verified_files=count,verified_bytes=total,
                report=hash_file(root/'conversion-result.json'),native_validation='not_run',
                business_validation='not_run',handoff_ready=False,
                next_action='Audit full input dispositions, actual native references/importer identities and byte-bound Editor receipts before business handoff.',
                limitations=['A byte-complete exported project is not all-object recovery, native acceptance or a playable game.'])
