import json,os,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from grea.integrations.monkey import local,release_install
from grea.common import hash_file

class ReadinessTests(unittest.TestCase):
    def test_missing_discovery_never_executes_or_writes(self):
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'HOME':t,'PATH':'','GREA_PROVIDER_STATE_DIR':t+'/state'}),patch.object(local.subprocess,'run')as run:
            self.assertEqual(local.discover()['status'],'not_installed');run.assert_not_called();self.assertFalse((Path(t)/'state').exists())

    def test_known_and_path_launchers_deduplicate_or_report_ambiguity(self):
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'HOME':t,'GREA_PROVIDER_STATE_DIR':t+'/state'}):
            r=Path(t);binary=r/'release/monkey';binary.parent.mkdir();binary.write_text('#!/bin/python');binary.chmod(0o755)
            p=r/'.local/bin/monkey';p.parent.mkdir(parents=True);p.symlink_to(binary)
            with patch.object(local.shutil,'which',return_value=str(binary)):
                self.assertEqual(local.discover()['candidates'],[str(binary.resolve())])
            other=r/'other';other.write_text('other');other.chmod(0o755)
            with patch.object(local.shutil,'which',return_value=str(other)):
                self.assertEqual(local.discover()['status'],'ambiguous')

    def test_stale_binding_never_silently_falls_back(self):
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'GREA_PROVIDER_STATE_DIR':t}):
            state=local.state_root();state.mkdir();(state/'binding.json').write_text(json.dumps(dict(schema_version=1,command=[str(state/'missing')],version='0.4.0',lock='lock')))
            with patch.object(local.shutil,'which')as which:
                self.assertEqual(local.discover()['status'],'bound_missing');which.assert_not_called()

    def test_check_and_ensure_without_flag_cannot_install(self):
        for ensure in (False,True):
            with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'GREA_PROVIDER_STATE_DIR':t+'/state'}),patch.object(local,'discover',return_value={'status':'not_installed','candidates':[]}),patch.object(release_install,'install_latest')as install:
                with patch.dict(os.environ,{},clear=True):
                    os.environ['GREA_PROVIDER_STATE_DIR']=t+'/state'
                    v=local.readiness(Path(t)/'check',ensure=ensure)
                self.assertFalse(v['ready']);install.assert_not_called()

    def test_explicit_missing_install_requires_verified_supported_version(self):
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{},clear=True):
            os.environ['GREA_PROVIDER_STATE_DIR']=t+'/state'
            with patch.object(local,'discover',return_value={'status':'not_installed','candidates':[]}),patch.object(release_install,'install_latest',return_value={'command':'/owned/monkey'})as install,patch.object(local,'probe_installation',return_value={'version':'99.0.0','command':['/owned/monkey']}):
                v=local.readiness(Path(t)/'ensure',ensure=True,install_missing=True)
            install.assert_called_once();self.assertFalse(v['ready']);self.assertFalse((Path(t)/'state/monkey/binding.json').exists())

    def test_conflict_does_not_install_or_overwrite(self):
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{},clear=True),patch.object(local,'discover',return_value={'status':'ambiguous','candidates':['a','b']}),patch.object(release_install,'install_latest')as install:
            os.environ['GREA_PROVIDER_STATE_DIR']=t+'/state';v=local.readiness(Path(t)/'ensure',ensure=True,install_missing=True)
            self.assertFalse(v['ready']);install.assert_not_called()

    def test_registry_respects_explicit_provider_override(self):
        from grea import registry
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'providers.json';p.write_text(json.dumps({'schema_version':1,'providers':{'monkey':{'command':['/explicit/monkey'],'probe':['/explicit/monkey','capabilities','--json'],'systems':['Darwin']}}}))
            with patch.dict(os.environ,{'GREA_PROVIDERS':str(p)}),patch.object(local,'provider_override')as auto:
                entry=registry.tool('monkey');self.assertEqual(entry['execution']['command'],['/explicit/monkey']);auto.assert_not_called()

class ReleaseTests(unittest.TestCase):
    def release(self):
        prefix='https://github.com/chuxintec/monkey/releases/download/v0.4.0/'
        return dict(tag_name='v0.4.0',draft=False,prerelease=False,assets=[dict(name=n,browser_download_url=prefix+n) for n in ['monkey_native-0.4.0-py3-none-any.whl','SHA256SUMS']])

    def test_only_expected_stable_repository_assets(self):
        self.assertEqual(release_install.select_assets(self.release())[0],'0.4.0')
        for change in ({'draft':True},{'prerelease':True},{'tag_name':'v0.4.0rc1'},{'assets':[]}):
            with self.assertRaises(ValueError):release_install.select_assets(dict(self.release(),**change))
        d=self.release();d['assets'][0]['browser_download_url']='https://github.com/other/repo/releases/download/v0.4.0/x'
        with self.assertRaises(ValueError):release_install.select_assets(d)
        for url in ['http://github.com/file','https://evil.example/asset','https://user@github.com/file']:
            with self.assertRaises(ValueError):release_install.validate_url(url)

    def test_checksum_absence_duplicate_and_corruption(self):
        name='monkey_native-0.4.0-py3-none-any.whl';line='a'*64+'  '+name
        self.assertEqual(release_install.wheel_digest(line,name),'a'*64)
        for text in ('',line+'\n'+line):
            with self.assertRaises(ValueError):release_install.wheel_digest(text,name)
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/name;p.write_bytes(b'bad')
            with self.assertRaises(ValueError):release_install.verify_wheel(p,'a'*64,'0.4.0')

    def test_wheel_metadata_and_dependency_versions_are_fixed(self):
        for requirement,valid in [('Pillow==12.2.0',True),('Pillow>=12',False),('Pillow @ https://evil.example/x',False)]:
            with tempfile.TemporaryDirectory() as t:
                p=Path(t)/'candidate.whl'
                with zipfile.ZipFile(p,'w')as z:z.writestr('monkey_native-0.4.0.dist-info/METADATA','Metadata-Version: 2.1\nName: monkey-native\nVersion: 0.4.0\nRequires-Dist: '+requirement+'\n')
                if valid:self.assertEqual(release_install.verify_wheel(p,hash_file(p)['sha256'],'0.4.0')['version'],'0.4.0')
                else:
                    with self.assertRaises(ValueError):release_install.verify_wheel(p,hash_file(p)['sha256'],'0.4.0')

if __name__=='__main__':unittest.main()

class DownloadFallbackTests(unittest.TestCase):
    def test_rate_limit_uses_only_official_stable_html_assets(self):
        import urllib.error
        with tempfile.TemporaryDirectory() as t:
            r=Path(t)
            def fetch(url,path,limit):
                if url==release_install.LATEST:raise urllib.error.HTTPError(url,403,'rate limit',{},None)
                if url.endswith('/latest'):
                    path.write_text('Release');return {'final_url':'https://github.com/chuxintec/monkey/releases/tag/v0.4.0'}
                path.write_text('<a href="/chuxintec/monkey/releases/download/v0.4.0/monkey_native-0.4.0-py3-none-any.whl">wheel</a><a href="/chuxintec/monkey/releases/download/v0.4.0/SHA256SUMS">hashes</a>')
                return {}
            with patch.object(release_install,'download',side_effect=fetch):d=release_install.latest_release(r)
            self.assertEqual(release_install.select_assets(d)[0],'0.4.0');self.assertEqual(d['fallback_reason'],'github_api_http_403')

    def test_http_not_found_is_not_hidden_by_fallback(self):
        import urllib.error
        with tempfile.TemporaryDirectory() as t,patch.object(release_install,'download',side_effect=urllib.error.HTTPError('url',404,'missing',{},None))as fetch:
            with self.assertRaises(urllib.error.HTTPError):release_install.latest_release(Path(t))
            self.assertEqual(fetch.call_count,1)
