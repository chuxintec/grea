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

    def test_metadata_deterministic_no_source_or_skill_packages(self):
        a=release.prepare(self.tag,self.out,True)
        other=self.out.with_name('other');b=release.prepare(self.tag,other,True)
        self.assertEqual(a,b)
        self.assertEqual({p.name for p in self.out.iterdir()},{'release-manifest.json','SHA256SUMS','release-notes.md'})
        release.verify(self.tag,self.out,complete=False)
        with self.assertRaises(ValueError):release.verify(self.tag,self.out)
        with self.assertRaises(FileExistsError):release.prepare(self.tag,self.out)

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

    def test_manifest_tamper_and_extra_installers_rejected(self):
        release.prepare(self.tag,self.out)
        (self.out/'unexpected.zip').write_bytes(b'bad')
        with self.assertRaises(ValueError):release.verify(self.tag,self.out,complete=False)
        (self.out/'unexpected.zip').unlink()
        p=self.out/'release-manifest.json';value=json.loads(p.read_text());value['source_revision']='a'*40;release.write_manifest(self.out,value)
        with self.assertRaises(ValueError):release.verify(self.tag,self.out,complete=False)

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

    def test_exact_target_set_and_reports_required(self):
        release.prepare(self.tag,self.out)
        for targets in [['macos-arm64'],['windows-x64'],['windows-x64','windows-x64'],['linux-x64']]:
            value=json.loads((self.out/'release-manifest.json').read_text());value['plugin_targets']=targets
            (self.out/'release-manifest.json').write_text(json.dumps(value))
            with self.assertRaises(ValueError):release.verify(self.tag,self.out)


    def test_two_real_projected_plugin_archives_and_report_binding(self):
        import plugin_bundle,build_plugin,plugin_release
        # Small runtime placeholders exercise byte identity gates, not runtime acceptance.
        values={'plugin/.mcp.json':'{}','plugin/runtime-lock.json':'{}',
                'plugin/runtime-windows-x64.lock.json':'{}','plugin/launcher/grea':'#!/bin/sh\n',
                'plugin/launcher/start.py':'# fixture','src/grea/cli.py':'# fixture',
                'registry.json':'{}','launch.py':'# fixture','launch_tool.py':'# fixture',
                'schemas/operations.json':'{}','schemas/unity-project.schema.json':'{}'}
        for name,text in values.items():
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
        self.git('add','.');self.git('-c','commit.gpgsign=false','commit','-qm','runtime fixtures')
        release.prepare(self.tag,self.out)
        source,identity=plugin_bundle.read_source(self.root)
        for target in release.TARGETS:
            staging=self.out.with_name(target);tree=staging/'grea';build_plugin.write_product(source,tree,target,identity['source_revision'])
            (tree/'runtime').mkdir();(tree/'runtime/python').write_bytes(b'placeholder')
            requirements=b'locked fixture';(tree/'runtime-requirements.txt').write_bytes(requirements)
            runtime={'python':{},'uvLockSha256':release.hashlib.sha256(source['uv.lock'][0]).hexdigest(),
                     'requirementsSha256':release.hashlib.sha256(requirements).hexdigest()}
            (tree/'runtime-manifest.json').write_bytes(plugin_bundle.encoded(runtime))
            manifest={'schemaVersion':1,'kind':'complete-plugin','version':'2026.10.13rc1','target':target,
                      **identity,'runtime':runtime,'files':plugin_bundle.inventory(tree,target)}
            (tree/'plugin-manifest.json').write_bytes(plugin_bundle.encoded(manifest))
            from plugin_targets import archive_name
            archive=staging/archive_name(target);plugin_bundle.write_archive(tree,archive,identity['source_timestamp'])
            report={'status':'pass','version':'2026.10.13rc1','source_kind':'commit','target':target,'archive_sha256':plugin_bundle.sha256(archive),
                    'source_tree_sha256':identity['source_tree_sha256'],
                    'clients':{c:{'status':'pass'} for c in ('codex','claude')},
                    'isolation':{key:True for key in plugin_release.ISOLATION}}
            (staging/'plugin-acceptance.json').write_bytes(plugin_bundle.encoded(report))
            layers={k:{'status':'pass'} for k in ('version','entrypoint','install','registration','initialize','skills','tools','installed_session')}
            layers['skills']['count']=8;layers['tools']['count']=21
            layers['installed_session']['version']='2026.10.13rc1'
            client={'target':target,'temporary_directory_removed':True,'isolation':{'independent_child_configuration':True,'credential_environment_inherited':False},'status':'pass','archive_sha256':report['archive_sha256'],'version':'2026.10.13rc1',
                    'source_tree_sha256':identity['source_tree_sha256'],'model_requests_sent':0,
                    'clients':{'codex':{'status':'pass','layers':layers}}}
            (staging/'client-acceptance.json').write_bytes(plugin_bundle.encoded(client))
            for key,bad in [('status','blocked'),('archive_sha256','bad'),('source_tree_sha256','bad'),('target','wrong'),('version','old'),('source_kind','worktree-preview')]:
                altered=dict(report);altered[key]=bad;(staging/'bad.json').write_bytes(plugin_bundle.encoded(altered))
                with self.assertRaises(ValueError):plugin_release.validate(archive,staging/'bad.json',source,'2026.10.13rc1',identity['source_revision'])
            for key,bad in [('version','old'),('archive_sha256','bad'),('source_tree_sha256','bad'),('model_requests_sent',1)]:
                altered=dict(client);altered[key]=bad;(staging/'bad-client.json').write_bytes(plugin_bundle.encoded(altered))
                with self.assertRaises(ValueError):plugin_release.validate_client(staging/'bad-client.json',archive,target,'2026.10.13rc1')
            release.attach_plugin(self.tag,self.out,staging,target)
            with self.assertRaises(ValueError):release.attach_plugin(self.tag,self.out,staging,target)
        names=release.verify(self.tag,self.out)
        self.assertEqual(len(names),8)
        self.assertFalse(any('skill-' in n for n in names))
        (self.out/'grea-plugin-windows-x64.zip').write_bytes(b'corrupt')
        with self.assertRaises((ValueError,zipfile.BadZipFile)):release.verify(self.tag,self.out)


class PublishTests(unittest.TestCase):
    def scenario(self, prerelease=True, existing=None, fail_upload=False, corrupt_download=False, remote_sha='source'):
        temp = tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        out = Path(temp.name)
        names = ['grea-plugin-macos-arm64.zip', 'grea-plugin-windows-x64.zip', 'release-manifest.json', 'SHA256SUMS']
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
        s=self.scenario(existing=existing(True,['grea-plugin-macos-arm64.zip']))
        self.assertEqual(s['uploads'],['grea-plugin-windows-x64.zip','release-manifest.json','SHA256SUMS'])
        s=self.scenario(existing=existing(False,['grea-plugin-macos-arm64.zip','grea-plugin-windows-x64.zip','release-manifest.json','SHA256SUMS']))
        self.assertEqual(s['uploads'],[]);self.assertEqual(s['patches'],[])
        with self.assertRaises(ValueError):self.scenario(existing=existing(False,['grea-plugin-macos-arm64.zip']))
        with self.assertRaises(ValueError):self.scenario(existing=existing(True,['unrecognized']))


if __name__ == '__main__':
    unittest.main()
