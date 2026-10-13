#!/usr/bin/env python3
"""Run Node test files sequentially with V8 limits and an external RSS watchdog.

RSS is sampled every 50 ms across the dedicated process group; it is not an
OS-enforced byte-exact ceiling. V8's heap limit is independent of this guard.
No shell is involved, and a failed monitor stops the owned test group.
"""
import argparse
import glob
import json
import os
from pathlib import Path
import resource
import selectors
import shutil
import signal
import subprocess
import sys
import time

ROOT = None
PROBE = Path(__file__).resolve().with_name('test-memory-probe.mjs')


def groups():
    result = subprocess.run(['ps', '-axo', 'pid=,pgid=,rss='], capture_output=True, text=True, timeout=2, check=True)
    return [tuple(map(int, line.split())) for line in result.stdout.splitlines() if line.strip()]


def kill_group(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_one(path, args, folder, index):
    command = [args.python, str(path)] if args.python else [shutil.which('node'), f'--max-old-space-size={args.heap_mb}', '--max-semi-space-size=8',
               '--import', str(PROBE), '--test', '--test-concurrency=1',
               f'--test-timeout={args.timeout_seconds * 1000}', str(path)]
    started = time.monotonic()
    log_path = folder / f'{index:03d}-{path.stem}.log'
    peak = 0
    samples = []
    output = bytearray()
    reason = None
    # Do not write crash core dumps on a deliberately bounded OOM test.
    def no_core():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    proc = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            start_new_session=True, preexec_fn=no_core)
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    next_sample = 0
    try:
        while True:
            now = time.monotonic()
            if now >= next_sample:
                members = [(pid, rss) for pid, group, rss in groups() if group == proc.pid]
                rss = sum(rss for _, rss in members)
                peak = max(peak, rss)
                samples.append({'seconds': round(now - started, 3), 'rssKiB': rss, 'pids': [pid for pid, _ in members]})
                next_sample = time.monotonic() + .05
                if rss > args.rss_mb * 1024:
                    reason = 'rss-limit'
                elif now - started > args.timeout_seconds:
                    reason = 'wall-time-limit'
                if reason:
                    kill_group(proc.pid)
                    break
                if proc.poll() is not None and not members and not selector.get_map():
                    break
            for key, _ in selector.select(timeout=.01):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                else:
                    remaining = args.output_kib * 1024 - len(output)
                    output.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        reason = 'output-limit'
                        kill_group(proc.pid)
                        break
            if reason:
                break
    except (Exception, KeyboardInterrupt) as exc:
        reason = f'monitor-error: {type(exc).__name__}: {exc}'
    finally:
        kill_group(proc.pid)
        proc.wait(timeout=5)
        selector.close()
        proc.stdout.close()
    log_path.write_bytes(output)
    telemetry = []
    for line in output.decode(errors='replace').splitlines():
        # Node TAP reporters may prefix child stderr with '# '.
        marker = line.find('TEST_MEMORY ')
        if marker >= 0:
            try:
                value = json.loads(line[marker + len('TEST_MEMORY '):])
                if isinstance(value.get('maxRSSKiB'), (int, float)):
                    telemetry.append(value)
            except (ValueError, AttributeError):
                pass
    result = {'file': str(path.relative_to(ROOT)), 'returncode': proc.returncode,
              'stopReason': reason, 'seconds': round(time.monotonic() - started, 3),
              'peakGroupRSSKiB': peak, 'processExitMemory': telemetry,
              'outputBytes': len(output), 'log': str(log_path), 'samples': samples}
    print(f"{path.name}: {'PASS' if proc.returncode == 0 and reason is None else 'FAIL'} "
          f"peak group RSS={peak / 1024:.1f} MiB, {result['seconds']}s, stop={reason}", flush=True)
    if proc.returncode != 0 or reason:
        print(output[-4000:].decode(errors='replace'), flush=True)
    return result


def main():
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True, help='Explicit project directory')
    parser.add_argument('files', nargs='+', help='Test paths or glob patterns relative to project root')
    parser.add_argument('--heap-mb', type=int, default=192)
    parser.add_argument('--rss-mb', type=int, default=384)
    parser.add_argument('--timeout-seconds', type=int, default=20)
    parser.add_argument('--output-kib', type=int, default=1024)
    parser.add_argument('--report-dir', type=Path)
    parser.add_argument('--python', help='Run a project Python probe under the same process-group watchdog instead of Node tests')
    args = parser.parse_args()
    ROOT = args.project.resolve()
    if not ROOT.is_dir(): parser.error("project directory missing")
    if min(args.heap_mb, args.rss_mb, args.timeout_seconds, args.output_kib) <= 0:
        parser.error('limits must be positive')
    if not args.python and not shutil.which('node'):
        parser.error('node executable is unavailable')
    expanded = [glob.glob(str(ROOT / pattern)) for pattern in args.files]
    if any(not matches for matches in expanded):
        parser.error('a requested test path/pattern has no matches')
    paths = sorted({Path(p).resolve() for matches in expanded for p in matches})
    if not paths or any(not p.is_relative_to(ROOT) or not p.is_file() for p in paths):
        parser.error('no matching tests or a path is outside this project')
    # Fail closed BEFORE Node starts when the sandbox does not permit ps.
    try:
        groups()
    except Exception as exc:
        sys.exit(f'RSS monitor unavailable; no tests started: {exc}')
    folder = args.report_dir or ROOT / 'output/test-monitor' / (time.strftime('%Y%m%d-%H%M%S') + f'-{time.time_ns() % 1000000000:09d}')
    folder.mkdir(parents=True, exist_ok=False)
    results = []
    report = folder / 'report.json'
    for index, path in enumerate(paths):
        result = run_one(path, args, folder, index)
        results.append(result)
        report.write_text(json.dumps({'limits': {'oldSpaceMiB': None if args.python else args.heap_mb, 'groupRSSMiB': args.rss_mb,
                                                'wallSecondsPerFile': args.timeout_seconds, 'outputKiBPerFile': args.output_kib},
                                     'results': results}, indent=2) + '\n')
        if result['returncode'] != 0 or result['stopReason']:
            break
    print(f'Report: {report}', flush=True)
    return 0 if len(results) == len(paths) and all(r['returncode'] == 0 and r['stopReason'] is None for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
