"""Recheck a frozen candidate through the fixed provider's existing verify command.

The provider parses native evidence; GREA binds identities and preserves results.
No Editor process is requested and no generated manifest is rewritten.
"""
import re
from grea import runner
from grea.common import GreaError, hash_file, write_new
from grea.safe_paths import canonical_path, disjoint
from .identity import pinned, read
from .pipeline import DEV1_VERSION, STABLE_VERSION, probe


def verify(config, candidate, output, level, expected_manifest, expected_readback=None):
    if level not in ('static', 'editor'):
        raise ValueError('Expected static or editor verification level')
    if not isinstance(expected_manifest, str) or not re.fullmatch('[a-f0-9]{64}', expected_manifest):
        raise ValueError('Explicit expected-manifest SHA256 required')
    if (level == 'editor') != (expected_readback is not None):
        raise ValueError('expected-readback is required only for editor-level saved evidence')
    if expected_readback is not None and not re.fullmatch('[a-f0-9]{64}', expected_readback):
        raise ValueError('Expected readback SHA256')
    candidate = canonical_path(candidate)
    cfg = pinned(config)
    if cfg['schema_version'] != 2 or cfg['version'] not in (DEV1_VERSION,STABLE_VERSION):
        raise ValueError('Exact supported launcher-bound lock required for this audit level')
    inputs = [hash_file(config), hash_file(candidate / 'manifest.json', 128*1024**2)]
    if inputs[-1]['sha256'] != expected_manifest:
        raise ValueError('Candidate generated manifest differs from expected identity')
    if expected_readback is not None:
        inputs.append(hash_file(candidate / 'Analysis/Readback/editor-readback.json', 128*1024**2))
        if inputs[-1]['sha256'] != expected_readback:
            raise ValueError('Saved readback differs from expected identity')
    out = disjoint(output, candidate, config, *[x['path'] for x in cfg['identity_files']])
    if out.exists() or not out.parent.is_dir():
        raise ValueError('Use a fresh audit output with existing parent')
    out.mkdir()
    executed = False
    try:
        probe(config, out / 'capabilities')
        receipt, _, error = runner.execute('monkey', ['verify', '--candidate', str(candidate),
            '--level', level, '--out', str(out / 'provider-output')], out / 'execution',
            timeout_seconds=300, max_output_bytes=1024**2, max_inline_bytes=1024**2)
        executed = True
        pinned(config)
        if any(hash_file(x['path'], 128*1024**2) != x for x in inputs):
            raise ValueError('Manifest, readback or provider lock changed during recheck')
        if error or not receipt.get('capture_complete'):
            raise ValueError('Provider verification failed; retain original process receipt')
        actual = receipt.get('parsed_stdout')
        report_path = out / 'provider-output/verification.json'
        report_identity = hash_file(report_path, 128*1024**2)
        report = read(report_path, 128*1024**2)
        if (not isinstance(actual, dict) or actual.get('status') not in ('partial', 'candidate')
                or receipt.get('exit_code') != (1 if actual['status'] == 'partial' else 0)
                or report.get('schemaVersion') != 1 or report.get('toolVersion') != cfg['version']
                or report.get('candidateManifestSha256') != expected_manifest):
            raise ValueError('Provider verification result identity/status mismatch')
        # Preserve partial/conflict and original diagnostics; no dynamic success is inferred.
        result = dict(schema_version=1, status='needs_action', provider_version=cfg['version'],
            identity_stage='native-saved' if level == 'editor' else 'generated',
            provider_status=actual['status'], provider_exit_code=receipt['exit_code'],
            executed=True, editor_started=False, input_identities=inputs,
            verification=report, verification_artifact=report_identity,
            provider_receipt=str(out / 'execution/run.json'),
            native_validation='recorded_provider_evidence_rechecked' if level == 'editor' else 'not_run',
            business_validation='not_run', handoff_ready=False,
            limitations=['Existing saved evidence rechecked by the exact provider; no new native run or independent authentication.',
                         'Static/editor/dynamic/visual/business fields remain separate; this is not project adoption or gameplay acceptance.'])
        write_new(out / 'result.json', result)
        return result
    except (OSError, ValueError, KeyError, TypeError, GreaError) as error:
        write_new(out / 'failure.json', dict(status='failed', message=str(error), executed=executed,
            editor_started=False, partial_output_preserved=True))
        raise
