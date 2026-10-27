"""Run tests against the exact monkey/beaver wheels pinned in modules.lock.json.

Wheels come from GREA_TEST_MODULE_WHEELS or .cache/modules (scripts/fetch_modules.py fills it).
Without them, tests that need a delegated tool are skipped rather than run against a stand-in.
"""
import atexit
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from grea import modules

ROOT = Path(__file__).resolve().parents[1]
_STATE = {}


def wheel_dir():
    return Path(os.environ.get('GREA_TEST_MODULE_WHEELS') or ROOT/'.cache/modules')


def providers_config():
    """Path of a GREA_PROVIDERS file whose monkey/beaver commands run the locked wheels; cached per process."""
    if 'config' in _STATE: return _STATE['config']
    folder = Path(tempfile.mkdtemp(prefix='grea-test-modules-'))
    atexit.register(shutil.rmtree, folder, True)
    providers = {}
    for entry in modules.load_lock(ROOT)['modules']:
        wheel = wheel_dir()/entry['wheel']['file']
        try: modules.verify_wheel(wheel, entry)
        except ValueError as error:
            _STATE['config'] = None; _STATE['reason'] = str(error); return None
        site = folder/('site-' + entry['name']); modules._extract(wheel, site)
        launcher = folder/(entry['name'] + '_launch.py')
        module_name, function = entry['entry'].split(':')
        launcher.write_text(f'import sys\nsys.path.insert(0, {str(site)!r})\nfrom {module_name} import {function}\nsys.exit({function}())\n', encoding='utf-8')
        command = [sys.executable, str(launcher)]
        providers[entry['name']] = dict(command=command, probe=command + entry['capabilitiesProbe'], systems=['Darwin', 'Windows', 'Linux'])
    path = folder/'providers.json'
    path.write_text(json.dumps({'schema_version': 1, 'providers': providers}), encoding='utf-8')
    _STATE['config'] = str(path)
    return _STATE['config']


def with_modules(test):
    """Decorator: run one test with delegated tool IDs routed to the locked module wheels."""
    import functools, inspect

    def enter():
        config = providers_config()
        if not config: raise unittest.SkipTest('Locked module wheels unavailable: ' + _STATE.get('reason', ''))
        previous = os.environ.get('GREA_PROVIDERS'); os.environ['GREA_PROVIDERS'] = config
        return previous

    def leave(previous):
        if previous is None: os.environ.pop('GREA_PROVIDERS', None)
        else: os.environ['GREA_PROVIDERS'] = previous

    if inspect.iscoroutinefunction(test):
        @functools.wraps(test)
        async def run_async(*args, **kwargs):
            previous = enter()
            try: return await test(*args, **kwargs)
            finally: leave(previous)
        return run_async

    @functools.wraps(test)
    def run(*args, **kwargs):
        previous = enter()
        try: return test(*args, **kwargs)
        finally: leave(previous)
    return run
