import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from monkey import stage_contracts as contracts
from monkey.signatures import phase_signatures
from monkey.io import write_json,read,load
from monkey.package import convert_package
from fixtures import fixture


class StageContractTests(unittest.TestCase):
    def test_layout_tool_version_and_inventory_policy_do_not_invalidate_readers(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();shutil.copytree(contracts.ROOT,root/'source');base=root/'source'
            with patch.object(contracts,'ROOT',base):
                old=contracts.source_contracts()
                (base/'__init__.py').write_text('__version__="99.0.0"')
                (base/'layout/standard.py').write_text('# changed naming only')
                p=base/'io.py';p.write_text(p.read_text().replace('    from .output_limits import digest_file, check_inventory','    from .output_limits import digest_file, check_inventory\n    output_inventory_revision = 99'))
                self.assertEqual(contracts.source_contracts(),old)
                p=base/'sources/compiled.py';p.write_text(p.read_text()+'\n# reader changed\n')
                self.assertFalse(contracts.compatible(old,contracts.source_contracts(),'inspect'))
                p=base/'io.py';p.write_text(p.read_text().replace('max_depth=96','max_depth=95'))
                self.assertFalse(contracts.compatible(old,contracts.source_contracts(),'normalize'))

    def test_legacy_contracts_cannot_be_accepted_without_exact_known_io(self):
        current=contracts.source_contracts()
        saved={k:dict(files=dict(v['files'],**{'io.py':'0'*64})) for k,v in current.items()}
        self.assertFalse(contracts.compatible(saved,current,'inspect'))
        for v in saved.values():v['files']['io.py']=contracts.LEGACY_IO
        self.assertTrue(contracts.compatible(saved,current,'inspect'))
        saved['inspect']['files']['sources/compiled.py']='1'*64
        self.assertFalse(contracts.compatible(saved,current,'inspect'))

    def test_changed_source_byte_budget_invalidates_both_saved_reader_stages(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();shutil.copytree(contracts.ROOT,root/'source');base=root/'source'
            with patch.object(contracts,'ROOT',base):
                saved=contracts.source_contracts()
                p=base/'io.py';text=p.read_text()
                # Change the original declaration, as a real reader-budget revision would.
                p.write_text(text.replace('MAX_BYTES = 32 * 1024 * 1024','MAX_BYTES = 16 * 1024 * 1024'))
                self.assertNotEqual(p.read_text(),text)
                current=contracts.source_contracts()
                for stage in ('inspect','normalize'):
                    self.assertFalse(contracts.compatible(saved,current,stage))

    def test_replan_reuses_checked_ir_without_source_reader_or_texture_decoder(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();source=root/'source';fixture(source)
            spec=root/'inputs.json';write_json(spec,dict(schemaVersion=1,sourceProfile='cocos-2.4.15-bundle',inputs=[dict(id='main',path=str(source),config='config.json')]))
            # fixture() produces a bundle with its config at its root.
            first=convert_package(None,'unity',root/'first',namespace='reuse',offline=True,input_set_path=spec)
            self.assertNotEqual(first['structuredRecovery']['status'],'failed')
            with patch('monkey.sources.bundle.inspect',side_effect=AssertionError('source reader executed')),patch('monkey.normalize.open_texture',side_effect=AssertionError('pixel decoder executed')):
                second=convert_package(None,'unity',root/'second',namespace='reuse',offline=True,input_set_path=spec,reuse_source_stages=root/'first')
            self.assertNotEqual(second['structuredRecovery']['status'],'failed',second['structuredRecovery'])
            self.assertFalse(second['sourceStageReuse']['sourceReaderExecuted'])
            self.assertEqual({r['stage'] for r in second['structuredRecovery']['reused']},{'inspect','normalize'})
            # Reused media are independent files, so editing an output never changes the frozen input.
            media=next(p for p in (root/'second/Structured/normalize').rglob('*.png'))
            original=root/'first/Structured/normalize'/media.relative_to(root/'second/Structured/normalize')
            self.assertNotEqual(media.stat().st_ino,original.stat().st_ino)
