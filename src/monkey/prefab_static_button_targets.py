"""Keep unsupported ColorTint target renderers from aborting independent roots.

The source target and color fields remain intact. An unavailable renderer is
an explicit component handoff, never an invented Image or a null substitution.
"""
from pathlib import Path
from . import io
from .output_limits import copy_verified


def apply(plan):
    graphics = {}
    for component in plan['components']:
        if component['type'] in ('cc.Sprite', 'cc.Label', 'cc.RichText'):
            graphics.setdefault(component['node'], []).append(component)
    blocked = []
    for button in plan['components']:
        if (button['type'] != 'cc.Button' or button.get('transition') != 1 or
                not button.get('convertible') or
                not (button.get('staticButtonBinding') or {}).get('renderReady')):
            continue
        target = button.get('target') or button['node']
        renderers = graphics.get(target, [])
        # A grouping node with no source renderer legitimately has no Graphic.
        # Only the source-declared renderer dependency is relevant here.
        if renderers and not any(c.get('convertible') is True for c in renderers):
            button['convertible'] = False
            evidence = dict(sourceComponentId=button['sourceId'], targetNodeSourceId=target,
                            targetRendererSourceIds=[c['sourceId'] for c in renderers],
                            status='blocked-source-target-renderer', native='not_run')
            blocked.append(evidence)
            plan.setdefault('diagnostics', []).append(io.diagnostic(
                'BUTTON_TARGET_RENDERER_HANDOFF', button['sourceId'],
                'Source color-transition target renderer is outside the native subset; '
                'target identity and fields retained, no substitute Graphic created', button['sourceId']))
    return blocked


def prepare(plan_path, output):
    """Make a fresh hash-owned continuation for existing frozen plans."""
    source = io.safe(plan_path)
    plan = io.stage_document(source)
    parent_sha = io.sha(io.stage_bytes(source))
    blocked = apply(plan)
    out = io.new_output(output, [source.parent])
    for item in io.stage_manifest(source.parent)['files']:
        if item['path'] != source.name:
            copy_verified(io.inside(source.parent, item['path']), io.inside(out, item['path']),
                          item['sha256'], item['bytes'])
    plan['staticButtonTargetReadiness'] = dict(schema='monkey-static-button-target-readiness/1',
                                              parentPlanSha256=parent_sha, blocked=blocked)
    io.write_json(out / 'plan.json', plan)
    return io.finish(out, plan)
