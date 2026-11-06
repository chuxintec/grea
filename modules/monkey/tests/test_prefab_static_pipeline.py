import contextlib
import io as stdio
import json
import tempfile
import unittest
from pathlib import Path
from monkey import io
from monkey.prefab_static_pipeline import attach_static_fields, project_ir
from monkey.sources.compiled import ParseError


class StaticPipelineTests(unittest.TestCase):
    def prepare(self, root):
        source = root / 'inspect'; source.mkdir()
        manifest = dict(sourceProfile='cocos-2.4.15-bundle', assets=[dict(
            sourceId='bundle:panel', kind='cc.Prefab', bundle='bundle', document=dict(instances=[
                {'__type__': 'cc.Prefab', 'data': {'__id__': 1}},
                {'__type__': 'cc.Node', '_components': [{'__id__': 2}]},
                {'__type__': 'NeutralPanel', 'node': {'__id__': 1}, 'caption': 'source text', 'owner': {'__id__': 1}}
            ]))])
        io.write_json(source / 'source-manifest.json', manifest)
        io.finish(source, dict(sourceProfile=manifest['sourceProfile'], diagnostics=[]))
        stage = root / 'normalize'; stage.mkdir()
        ir = dict(schemaVersion=1, sourceProfile=manifest['sourceProfile'],
                  sourceManifestSha256=io.sha((source / 'source-manifest.json').read_bytes()),
                  diagnostics=[], assets=[], nodes=[dict(sourceId='bundle:panel#1')],
                  components=[dict(sourceId='bundle:panel#2', node='bundle:panel#1', type='NeutralPanel', supported=False)])
        (stage / 'resource.bin').write_bytes(b'preserved resource')
        io.write_json(stage / 'ir.json', ir); io.finish(stage, dict(ir))
        return source / 'source-manifest.json', stage / 'ir.json'

    def test_cli_reuses_resources_without_promoting_native_support(self):
        from monkey.cli import main
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve(); source, ir = self.prepare(root)
            before = ir.read_bytes()
            with contextlib.redirect_stdout(stdio.StringIO()):
                code = main(['prefab-static-fields', '--manifest', str(source), '--ir', str(ir), '--out', str(root / 'derived')])
            self.assertEqual(code, 0)
            derived = io.stage_document(root / 'derived/ir.json')
            self.assertFalse(derived['components'][0]['supported'])
            row = derived['components'][0]['staticFieldSnapshot']
            self.assertEqual(row['native'], 'not_run')
            self.assertEqual(row['fields'][0]['name'], 'caption')
            self.assertEqual(derived['staticFieldPreservation']['serializedFieldCount'], 2)
            self.assertEqual((root / 'derived/resource.bin').read_bytes(), b'preserved resource')
            self.assertEqual(ir.read_bytes(), before)
            second = project_ir(source, root / 'derived/ir.json', root / 'derived-again')
            self.assertEqual(second['components'], derived['components'])
            with self.assertRaises(ParseError): project_ir(source, ir, root / 'derived')

    def test_changed_resource_and_source_binding_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve(); source, ir = self.prepare(root)
            (ir.parent / 'resource.bin').write_bytes(b'changed')
            with self.assertRaises(ParseError): project_ir(source, ir, root / 'rejected')
            (ir.parent / 'resource.bin').write_bytes(b'preserved resource')
            manifest = json.loads(source.read_text()); manifest['extra'] = 'different source'
            io.write_json(source, manifest); io.finish(source.parent, dict(sourceProfile=manifest['sourceProfile'], diagnostics=[]))
            with self.assertRaises(ParseError): project_ir(source, ir, root / 'mismatch')
            self.assertFalse((root / 'mismatch').exists())


if __name__ == '__main__': unittest.main()
