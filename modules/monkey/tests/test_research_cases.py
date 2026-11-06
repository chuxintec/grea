import json,tempfile,unittest
from pathlib import Path
from monkey.research_cases import discover
from monkey.sources.compiled import ParseError


class ResearchCasesTests(unittest.TestCase):
    def test_dynamic_unknown_and_missing_sources_remain_denominator(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();games=root/'games';games.mkdir()
            for name in ['Known','Missing','NewUnknown','_comparison','.hidden']:(games/name).mkdir()
            (games/'Known/RESEARCH.json').write_text(json.dumps({'identity':{'sourceEngine':'Unity 2022.3.34f1c1 / WebGL-Wasm','originalSource':'/must/not/follow'}}))
            source=games/'Known/Evidence/source/cache-1';source.mkdir(parents=True);(source/'manifest.json').write_text('{}')
            out=root/'matrix';summary=discover(games,out);cases=json.loads((out/'cases.json').read_text())['cases']
            self.assertEqual(summary['denominator'],3)
            known=next(c for c in cases if c['name']=='Known');self.assertEqual(known['engineHint']['version'],'2022.3.34f1c1')
            self.assertEqual(known['engineHint']['confidence'],'metadata_hint_only')
            self.assertTrue(all(c['stages']['export']=='not_run' for c in cases))
            self.assertEqual(sum(c['availability']=='blocked_source' for c in cases),2)
            (games/'AddedLater').mkdir();self.assertEqual(discover(games,root/'matrix2')['denominator'],4)
            with self.assertRaises(ParseError):discover(games,out)

    def test_link_and_bad_metadata_do_not_hide_games_or_read_external_data(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();games=root/'games';games.mkdir();(games/'Broken').mkdir();(games/'Broken/RESEARCH.json').write_text('{bad')
            (games/'Link').symlink_to(root/'unavailable',target_is_directory=True)
            summary=discover(games,root/'out');self.assertEqual(summary['denominator'],2)
            cases=json.loads((root/'out/cases.json').read_text())['cases'];self.assertEqual({c['name'] for c in cases},{'Broken','Link'})
            self.assertTrue(all(c['conversion']=='not_run' for c in cases))


if __name__=='__main__':unittest.main()
