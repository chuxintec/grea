"""Portable plugins must not depend on the checkout or trust archive paths."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


class PluginBundleTests(unittest.TestCase):
    def source_fixture(self):
        # Works both in a checkout and in a Git-free source release extraction.
        names = ['LICENSE','registry.json','launch.py','launch_tool.py','src/grea/cli.py','src/grea/mcp_server.py',
                 'plugin/version.json','plugin/.codex-plugin/plugin.json','plugin/.claude-plugin/plugin.json',
                 'plugin/.mcp.json','plugin/launcher/grea','plugin/launcher/start.py',
                 'plugin/skills/grea/references/工具选择与调用.md','schemas/operations.json','schemas/unity-project.schema.json']
        for directory in ['tools/unity/framework/packages','tests/unity/reference-project']:
            names.append(next(p.relative_to(ROOT).as_posix() for p in (ROOT/directory).rglob('*') if p.is_file()))
        names.extend(p.relative_to(ROOT).as_posix() for p in (ROOT/'plugin/assets').rglob('*') if p.is_file())
        return {name:((ROOT/name).read_bytes(), 0o100755 if (ROOT/name).stat().st_mode & 0o111 else 0o100644) for name in names}

    def module(self):
        self.assertTrue((ROOT / 'scripts/plugin_bundle.py').is_file(),
                        'Portable plugin builder has not been implemented')
        import plugin_bundle
        return plugin_bundle

    def tar(self, root, entries):
        path = root / 'python.tar.gz'
        with tarfile.open(path, 'w:gz') as archive:
            for name, value in entries:
                item = tarfile.TarInfo(name)
                if isinstance(value, tuple):
                    item.type = tarfile.SYMTYPE
                    item.linkname = value[0]
                    archive.addfile(item)
                else:
                    item.size = len(value)
                    item.mode = 0o755 if '/bin/' in name else 0o644
                    archive.addfile(item, io.BytesIO(value))
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_failed_acceptance_preserves_a_nonpassing_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'invalid.zip';archive.write_bytes(b'not a zip')
            report=root/'failure.json'
            result=subprocess.run([sys.executable,str(ROOT/'scripts/verify_plugin.py'),'--bundle',str(archive),'--report',str(report)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            value=json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(value['status'],'fail');self.assertTrue(value['error']['message'])
            self.assertEqual(value['archive_sha256'],hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_runtime_hash_and_archive_escape_rejected_before_install(self):
        module = self.module()
        for entries in [[('../escape', b'bad')], [('python/bin/python3', ('../../../escape',))]]:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                archive, checksum = self.tar(root, entries)
                with self.assertRaises(ValueError):
                    module.extract_runtime(archive, root/'runtime', checksum)
                self.assertFalse((root/'runtime').exists())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, _ = self.tar(root, [('python/bin/python3', b'python')])
            with self.assertRaises(ValueError):
                module.extract_runtime(archive, root/'runtime', '0'*64)
            self.assertFalse((root/'runtime').exists())

    def test_internal_runtime_links_become_relocatable_regular_files(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive, checksum = self.tar(root, [('python/bin/python3', ('python3.12',)),
                                               ('python/bin/python3.12', b'python')])
            module.extract_runtime(archive, root/'runtime', checksum)
            python = root/'runtime/bin/python3'
            self.assertFalse(python.is_symlink())
            self.assertEqual(python.read_bytes(), b'python')
            if os.name!='nt':self.assertTrue(python.stat().st_mode & 0o111)

    def test_bundle_reproducibility_permissions_and_tamper(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tree = root/'grea'; tree.mkdir()
            (tree/'entry').write_bytes(b'#!/bin/sh\nexit 0\n')
            (tree/'entry').chmod(0o755)
            (tree/'中文.json').write_text('{}')
            manifest = {'schemaVersion':1, 'files':module.inventory(tree)}
            (tree/'plugin-manifest.json').write_text(json.dumps(manifest))
            module.write_archive(tree, root/'a.zip', 1760000000)
            module.write_archive(tree, root/'b.zip', 1760000000)
            self.assertEqual((root/'a.zip').read_bytes(), (root/'b.zip').read_bytes())
            module.verify_archive(root/'a.zip', root/'moved path')
            if os.name!='nt':self.assertTrue((root/'moved path/grea/entry').stat().st_mode & 0o111)
            with zipfile.ZipFile(root/'a.zip', 'a') as archive:
                archive.writestr('grea/unlisted', b'tampered')
            with self.assertRaises(ValueError):
                module.verify_archive(root/'a.zip', root/'unsafe')
            self.assertFalse((root/'unsafe').exists())

    def test_clean_source_rejects_dirty_preview_records_actual_bytes(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.check_output(['git','-C',str(root),*args], stderr=subprocess.PIPE)
            git('init','-q'); git('config','user.name','Fixture'); git('config','user.email','fixture@example.com')
            (root/'LICENSE').write_text('original')
            (root/'.gitignore').write_text('.private/\n')
            git('add','.'); git('-c','commit.gpgsign=false','commit','-qm','fixture')
            (root/'LICENSE').write_text('preview')
            (root/'new.py').write_text('value = 1\n')
            (root/'.private').mkdir(); (root/'.private/secret').write_text('excluded')
            with self.assertRaises(ValueError): module.read_source(root)
            files, identity = module.read_source(root, worktree=True)
            self.assertEqual(files['LICENSE'][0], b'preview')
            self.assertIn('new.py', files)
            self.assertFalse(any('.private' in name for name in files))
            self.assertTrue(identity['source_dirty'])
            self.assertEqual(len(identity['source_tree_sha256']), 64)

    def test_client_manifests_and_launchers_are_bundled(self):
        self.module()
        for name in ['plugin/.mcp.json','plugin/launcher/grea','plugin/launcher/start.py','plugin/runtime-lock.json']:
            self.assertTrue((ROOT/name).is_file(), name)
        codex=json.loads((ROOT/'plugin/.codex-plugin/plugin.json').read_text())
        claude=json.loads((ROOT/'plugin/.claude-plugin/plugin.json').read_text())
        self.assertEqual(codex['mcpServers'], './.mcp.json')
        self.assertIn('${CLAUDE_PLUGIN_ROOT}', claude['mcpServers']['grea']['command'])
        self.assertEqual(json.loads((ROOT/'plugin/.mcp.json').read_text())['mcpServers']['grea']['cwd'], '.')

    def test_product_resource_closure_and_manifest_paths(self):
        self.assertTrue((ROOT/'scripts/build_plugin.py').is_file(), 'Complete plugin assembly is missing')
        import build_plugin
        files = self.source_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            tree=Path(tmp)/'grea'
            build_plugin.write_product(files, tree)
            for name in ['registry.json','launch.py','launch_tool.py','src/grea/mcp_server.py',
                         'schemas/unity-project.schema.json','plugin/skills/grea/references/工具选择与调用.md',
                         'tools/unity/framework/packages','tests/unity/reference-project']:
                self.assertTrue((tree/name).exists(), name)
            for client in ('.codex-plugin', '.claude-plugin'):
                manifest=json.loads((tree/client/'plugin.json').read_text())
                self.assertEqual(manifest['skills'], './plugin/skills/')
            self.assertEqual(json.loads((tree/'.agents/plugins/marketplace.json').read_text())['plugins'][0]['source']['path'], './')
            self.assertEqual(json.loads((tree/'.claude-plugin/marketplace.json').read_text())['plugins'][0]['source'], './')
            self.assertFalse((tree/'.venv').exists())
            self.assertFalse((tree/'.private').exists())

    def test_verifier_resolves_both_client_paths_without_checkout(self):
        self.assertTrue((ROOT/'scripts/verify_plugin.py').is_file(), 'Clean installation verifier is missing')
        import verify_plugin
        import build_plugin
        files = self.source_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            tree=Path(tmp).resolve()/'moved 插件'
            build_plugin.write_product(files, tree)
            commands=[verify_plugin.client_command(tree, client)[0] for client in ['codex','claude']]
            self.assertEqual(commands[0], commands[1])
            self.assertEqual(commands[0], [str(tree/'plugin/launcher/grea'), 'mcp'])

    def test_removed_console_wrappers_do_not_leak_random_build_identity(self):
        import build_plugin
        self.assertTrue(callable(getattr(build_plugin,'normalize_records',None)), 'Removed files still survive in wheel RECORDs')
        results=[]
        with tempfile.TemporaryDirectory() as tmp:
            for number in (1,2):
                runtime=Path(tmp)/str(number);site=runtime/'lib/site-packages'
                info=site/'fixture.dist-info';info.mkdir(parents=True)
                (site/'fixture.py').write_text('same code')
                record=info/'RECORD'
                record.write_text('bin/fixture,sha256=random-'+str(number)+',200\nfixture.py,,\nfixture.dist-info/RECORD,,\n')
                build_plugin.normalize_records(site,runtime)
                results.append(record.read_bytes())
            self.assertEqual(results[0],results[1])
            self.assertNotIn(b'bin/fixture',results[0])
            record.write_text('missing-runtime-module.py,,\nfixture.dist-info/RECORD,,\n')
            with self.assertRaises(ValueError):build_plugin.normalize_records(site,runtime)

    def test_stripped_upstream_record_requires_unchanged_verified_archive_bytes(self):
        import build_plugin
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Path(tmp).resolve();site=runtime/'lib/site-packages';info=site/'pip.dist-info'
            info.mkdir(parents=True);payload=site/'stripped.exe';payload.write_bytes(b'verified upstream bytes')
            record=info/'RECORD';record.write_text('stripped.exe,sha256=pre-strip-record,999\npip.dist-info/RECORD,,\n')
            upstream=self.module().inventory(runtime)
            self.assertTrue('upstream_files' in __import__('inspect').signature(build_plugin.normalize_records).parameters,
                            'Stripped upstream metadata has no verified provenance exception')
            notes=build_plugin.normalize_records(site,runtime,upstream_files=upstream)
            self.assertEqual(len(notes),1)
            payload.write_bytes(b'modified after verified extraction')
            with self.assertRaises(ValueError):build_plugin.normalize_records(site,runtime,upstream_files=upstream)


if __name__ == '__main__': unittest.main()
