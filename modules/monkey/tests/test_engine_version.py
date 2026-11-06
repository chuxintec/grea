import tempfile,unittest
from pathlib import Path
from fixtures import fixture
from monkey.io import read,write_json,load,sha
from monkey.sources.engine_facts import inspect
from monkey.package import convert_package


class EngineVersionTests(unittest.TestCase):
    def test_literals_in_comments_strings_or_other_objects_do_not_prove_cc_engine_version(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();p=root/'source.js'
            p.write_text('const text="cc.ENGINE_VERSION=\\\"2.4.11\\\""; /* cc.ENGINE_VERSION="2.4.11"; */ other.ENGINE_VERSION="2.4.11"; throw Error("never execute");')
            self.assertEqual(inspect(p)['facts'],[])
            p.write_text('const label="中文"; wrapper.CocosEngine=cc.ENGINE_VERSION="2.4.11"; throw Error("never execute");')
            result=inspect(p);self.assertFalse(result['sourceCodeExecuted']);self.assertEqual(len(result['facts']),1)
            fact=result['facts'][0];span=fact['sourceBytes'];self.assertEqual(sha(read(p)[span['start']:span['end']]),fact['sha256'])
            self.assertEqual(fact['version'],'2.4.11')

    def test_legacy_settings_are_literal_ast_data_and_calls_are_rejected(self):
        with tempfile.TemporaryDirectory()as t:
            p=Path(t).resolve()/'source.js'
            p.write_text('cc.ENGINE_VERSION="2.1.2";window._CCSettings={platform:"wechatgame",flag:!0,values:[-2,3,null]};throw Error("never execute");')
            result=inspect(p,True)
            self.assertEqual(result['settings'][0]['data'],{'platform':'wechatgame','flag':True,'values':[-2,3,None]})
            self.assertFalse(result['sourceCodeExecuted'])
            p.write_text('cc.ENGINE_VERSION="2.1.2";window._CCSettings={value:doNotCall()};')
            with self.assertRaises(ValueError):inspect(p,True)

    def test_version_evidence_is_consumed_by_auto_package_source_profile(self):
        with tempfile.TemporaryDirectory()as t:
            root=Path(t).resolve();config=fixture(root/'source');data=load(read(config));data.pop('engineVersion');write_json(config,data)
            (config.parent/'game.js').write_text('cc.ENGINE_VERSION="2.4.11"; throw Error("never execute");')
            report=convert_package(config.parent,'both',root/'out')
            self.assertTrue(report['sourceCodeParserExecuted']);self.assertEqual(report['structuredRecovery']['sourceProfile'],'cocos-2.4.11-bundle')
            self.assertNotEqual(report['structuredRecovery']['status'],'failed',report['structuredRecovery'])
            inspected=load(read(root/'out/Structured/inspect/source-manifest.json'));self.assertEqual(inspected['sourceVersion'],'2.4.11')
            self.assertTrue(all((root/'out'/p/'manifest.json').exists()for p in ('UnityProject','CocosProject')))


if __name__=='__main__':unittest.main()
