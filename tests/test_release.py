import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('grea_release', SCRIPTS / 'release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve() / 'repo'
        self.root.mkdir()
        self.patch = patch.object(release, 'ROOT', self.root)
        self.patch.start()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.com')
        (self.root / 'src/grea').mkdir(parents=True)
        (self.root / 'src/grea/__init__.py').write_text('__version__ = "2026.10.13rc1"\n')
        (self.root / 'pyproject.toml').write_text('[project]\nname="grea"\nversion="2026.10.13rc1"\nrequires-python=">=3.10"\n')
        (self.root / 'uv.lock').write_text('[[package]]\nname="grea"\nversion="2026.10.13rc1"\n')
        (self.root / '中文.md').write_text('中文说明\n')
        (self.root / 'plugin/skills/grea').mkdir(parents=True)
        (self.root / 'plugin/skills/grea/SKILL.md').write_text('---\nname: grea\ndescription: Fixture\n---\n[说明](../../../中文.md)\n')
        (self.root / 'plugin/version.json').write_text(json.dumps({'version':'2026.10.13rc1','greaVersion':'2026.10.13rc1','requiredOperations':['session']}))
        for manifest in ('.codex-plugin', '.claude-plugin'):
            (self.root / 'plugin' / manifest).mkdir()
            (self.root / 'plugin' / manifest / 'plugin.json').write_text(json.dumps({'name':'grea','version':'2026.10.13rc1'}))
        (self.root / 'LICENSE').write_text('MIT fixture')
        (self.root / 'launcher').write_text('#!/bin/sh\nexit 0\n')
        (self.root / 'launcher').chmod(0o755)
        self.git('add', '.')
        self.git('-c', 'commit.gpgsign=false', 'commit', '-qm', 'fixture')
        self.git('tag', 'v2026.10.13-rc1')
        self.tag = 'v2026.10.13-rc1'
        self.out = Path(self.tmp.name).resolve() / 'out'

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.PIPE)

    def test_deterministic_bundle_unicode_permissions_and_exclusion(self):
        (self.root / 'untracked.txt').write_text('must not ship')
        a = release.prepare(self.tag, self.out, True)
        other = self.out.with_name('other')
        b = release.prepare(self.tag, other, True)
        self.assertEqual(a, b)
        self.assertEqual((self.out / a['artifacts'][0]['name']).read_bytes(), (other / b['artifacts'][0]['name']).read_bytes())
        dest = self.out.with_name('extract')
        release.verify(self.tag, self.out, dest, self.out.with_name('skill-extract'))
        self.assertTrue((self.out.with_name('skill-extract')/'grea/skills/grea/SKILL.md').is_file())
        self.assertEqual(a['artifacts'][1]['kind'],'skill')
        top = dest / ('grea-' + self.tag)
        self.assertEqual((top / '中文.md').read_text(), '中文说明\n')
        if os.name!='nt':self.assertTrue((top / 'launcher').stat().st_mode & 0o111)
        self.assertFalse((top / 'untracked.txt').exists())
        with self.assertRaises(FileExistsError):release.prepare(self.tag, self.out)

    def test_version_and_tag_mismatch_or_dirty_tree_rejected(self):
        with self.assertRaises(ValueError):release.prepare('v2026.10.13', self.out)
        (self.root / 'uv.lock').write_text('[[package]]\nname="grea"\nversion="1.0.0"\n')
        with self.assertRaises(ValueError):release.prepare(self.tag, self.out)
        self.git('checkout', '--', 'uv.lock')
        (self.root / '中文.md').write_text('edited')
        with self.assertRaises(ValueError):release.prepare(self.tag, self.out)
        self.git('add', '.')
        self.git('-c', 'commit.gpgsign=false', 'commit', '-qm', 'new')
        with self.assertRaises(ValueError):release.prepare(self.tag, self.out, True)

    def test_tampered_zip_and_path_injection_rejected(self):
        release.prepare(self.tag, self.out)
        archive = self.out / f'grea-{self.tag}.zip'
        with zipfile.ZipFile(archive, 'a') as z:z.writestr('../escaped', 'bad')
        with self.assertRaises(ValueError):release.verify(self.tag, self.out, self.out.with_name('extract'))
        self.assertFalse(self.out.with_name('escaped').exists())
        # Even consistent attacker-supplied checksums cannot add archive paths.
        p = self.out / 'release-manifest.json'
        manifest = json.loads(p.read_text())
        manifest['artifacts'][0].update(bytes=archive.stat().st_size, sha256=release.sha256(archive))
        p.write_text(json.dumps(manifest))
        (self.out / 'SHA256SUMS').write_text(''.join(release.sha256(f)+'  '+f.name+'\n' for f in [archive,p]))
        with self.assertRaises(ValueError):release.verify(self.tag, self.out, self.out.with_name('extract'))
        self.assertFalse(self.out.with_name('extract').exists())

    def test_sensitive_committed_file_rejected(self):
        (self.root / 'config.txt').write_text('gh' + 'p_' + 'a' * 36)
        self.git('add', '.')
        self.git('-c', 'commit.gpgsign=false', 'commit', '-qm', 'unsafe fixture')
        with self.assertRaises(ValueError):release.prepare(self.tag, self.out)
        self.assertFalse(self.out.exists())

    def test_version_syntax(self):
        self.assertEqual(release.version('v2026.10.13'), ('2026.10.13', False))
        self.assertEqual(release.version('v1.2.3-rc2'), ('1.2.3rc2', True))
        for tag in ['v1.2', 'v1.2.3-rc0', 'v1.2.3-beta1', 'v1.2.3;id', '../v1.2.3']:
            with self.assertRaises(ValueError):release.version(tag)

    def test_portable_plugin_attachment_identity_and_tamper(self):
        self.assertTrue(hasattr(release, 'attach_plugin'), 'Release has no portable plugin attachment gate')
        import plugin_bundle
        import build_plugin
        for name, value in {
            'plugin/.mcp.json':json.dumps({'mcpServers':{'grea':{'command':'./plugin/launcher/grea','args':['mcp'],'cwd':'.'}}}),
            'plugin/runtime-lock.json':'{}', 'plugin/launcher/grea':'#!/bin/sh\n',
            'plugin/launcher/start.py':'# fixture', 'src/grea/cli.py':'# fixture',
            'registry.json':'{}','launch.py':'# fixture','launch_tool.py':'# fixture',
            'schemas/operations.json':'{}','schemas/unity-project.schema.json':'{}',
        }.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value)
        self.git('add','.');self.git('-c','commit.gpgsign=false','commit','-qm','plugin fixture')
        release.prepare(self.tag,self.out)
        source, identity=plugin_bundle.read_source(self.root)
        staging=self.out.with_name('plugin')
        tree=staging/'grea';build_plugin.write_product(source,tree)
        (tree/'runtime').mkdir();(tree/'runtime/python').write_text('fixture runtime')
        (tree/'runtime-requirements.txt').write_bytes(b'fixture requirements')
        runtime={'python':{},'uvLockSha256':release.hashlib.sha256(source['uv.lock'][0]).hexdigest(),
                 'requirementsSha256':release.hashlib.sha256(b'fixture requirements').hexdigest()}
        (tree/'runtime-manifest.json').write_bytes(plugin_bundle.encoded(runtime))
        manifest={'schemaVersion':1,'kind':'complete-plugin','version':'2026.10.13rc1','target':'macos-arm64',
                  **identity,'runtime':runtime,'files':plugin_bundle.inventory(tree)}
        (tree/'plugin-manifest.json').write_bytes(plugin_bundle.encoded(manifest))
        plugin_bundle.write_archive(tree,staging/build_plugin.ARCHIVE,identity['source_timestamp'])
        report={'status':'pass','target':'macos-arm64','archive_sha256':plugin_bundle.sha256(staging/build_plugin.ARCHIVE),
                'source_tree_sha256':identity['source_tree_sha256'],
                'clients':{client:{'status':'pass'} for client in ['codex','claude']},
                'isolation':{key:True for key in ['moved_unicode_space_path','independent_home','minimal_path',
                    'source_read_denied','network_denied','install_write_denied','installation_unchanged']}}
        (staging/'plugin-acceptance.json').write_bytes(plugin_bundle.encoded(report))
        release.attach_plugin(self.tag,self.out,staging)
        names=release.verify(self.tag,self.out)
        self.assertIn(build_plugin.ARCHIVE,names)
        self.assertIn('plugin-acceptance-macos-arm64.json',names)
        (self.out/build_plugin.ARCHIVE).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):release.verify(self.tag,self.out)


class PublishTests(unittest.TestCase):
    def scenario(self, prerelease=True, existing=None, fail_upload=False, corrupt_download=False, remote_sha='source'):
        temp = tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        out = Path(temp.name)
        names = ['bundle.zip', 'skill.zip', 'release-manifest.json', 'SHA256SUMS']
        for n in names:(out / n).write_text(n)
        (out / 'release-notes.md').write_text('notes')
        state = {'release': existing, 'patches': [], 'uploads': []}
        def api(repo, endpoint, method='GET', data=None):
            if endpoint.startswith('commits/'):return {'sha': remote_sha}
            if method == 'POST':
                state['release'] = {'id':1,'draft':True,'prerelease':data['prerelease'],'tag_name':'v1.2.3-rc1','assets':[],'html_url':'https://example.com/release'}
            elif method == 'PATCH':
                state['patches'].append(data);state['release'].update(data)
            return state['release']
        def gh(*args):
            if args[:2] == ('release', 'upload'):
                if fail_upload:raise RuntimeError('network failure')
                n = Path(args[3]).name
                state['uploads'].append(n)
                state['release']['assets'].append({'name':n,'size':(out/n).stat().st_size,'state':'uploaded'})
            elif args[:2] == ('release', 'download'):
                name = args[args.index('--pattern')+1]
                dest = Path(args[args.index('--dir')+1]) / name
                dest.write_bytes(b'corrupt' if corrupt_download else (out/name).read_bytes())
            else:raise AssertionError(args)
            return ''
        with patch.object(release, 'verify', return_value=names), patch.object(release, 'identity', return_value=('1.2.3rc1',prerelease,'source','>=3.10')), patch.object(release, 'release_state', side_effect=lambda *_:state['release']), patch.object(release, 'api', side_effect=api), patch.object(release, 'gh', side_effect=gh):
            if fail_upload:
                with self.assertRaises(RuntimeError):release.publish('v1.2.3-rc1',out,'example/repo')
            else:release.publish('v1.2.3-rc1',out,'example/repo')
        return state

    def test_rc_published_only_after_verified_uploads(self):
        state=self.scenario()
        self.assertEqual(len(state['uploads']),4)
        self.assertEqual(state['patches'],[{'draft':False,'prerelease':True,'make_latest':'false'}])

    def test_stable_release_classification(self):
        state=self.scenario(prerelease=False)
        self.assertEqual(state['patches'][0]['make_latest'],'legacy')
        self.assertFalse(state['patches'][0]['prerelease'])

    def test_failed_upload_stays_draft(self):
        state=self.scenario(fail_upload=True)
        self.assertTrue(state['release']['draft'])
        self.assertEqual(state['patches'],[])

    def test_bad_remote_content_or_moved_tag_blocks_publication(self):
        with self.assertRaises(ValueError):self.scenario(corrupt_download=True)
        with self.assertRaises(ValueError):self.scenario(remote_sha='moved')

    def test_partial_draft_resumes_and_published_release_is_immutable(self):
        def existing(draft, names):
            return {'id':1,'tag_name':'v1.2.3-rc1','draft':draft,'prerelease':True,'html_url':'https://example.com/release',
                    'assets':[{'name':n,'size':len(n),'state':'uploaded'} for n in names]}
        s=self.scenario(existing=existing(True,['bundle.zip']))
        self.assertEqual(s['uploads'],['skill.zip','release-manifest.json','SHA256SUMS'])
        s=self.scenario(existing=existing(False,['bundle.zip','skill.zip','release-manifest.json','SHA256SUMS']))
        self.assertEqual(s['uploads'],[]);self.assertEqual(s['patches'],[])
        with self.assertRaises(ValueError):self.scenario(existing=existing(False,['bundle.zip']))
        with self.assertRaises(ValueError):self.scenario(existing=existing(True,['unrecognized']))


if __name__ == '__main__':
    unittest.main()
