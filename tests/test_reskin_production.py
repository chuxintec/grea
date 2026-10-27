"""Owned production declarations and PNGs; no media service, Spine or Unity run."""
import copy,hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from grea.application import dispatch
from grea.change_contracts import validate,validate_ledger,RESKIN_STAGES
from grea.common import GreaError
from grea.tools.theme_assets import inspect,create
import test_theme_assets as fixtures

ROOT=Path(__file__).resolve().parents[1]

def ledger():
    return json.loads((ROOT/'plugin/skills/grea/references/examples/art-ledger.example.json').read_text())

def production_contract(stage='style_sample',state='candidate'):
    value=fixtures.contract(state=state)
    value['allowed_changes']=['visual_style']
    value['art_production']=dict(stage=stage,ledger=dict(reference='art-ledger.json',sha256='c'*64))
    return value

class ReskinProduction(unittest.TestCase):
    def test_tuning_waits_for_full_reskin_without_changing_legacy_contract(self):
        self.assertEqual(validate(fixtures.contract())['allowed_changes'],['visual_style','layout'])
        for stage in RESKIN_STAGES[:-1]:
            c=production_contract(stage,'approved');c['allowed_changes'].append('navigation')
            with self.subTest(stage=stage),self.assertRaises(GreaError) as caught:validate(c)
            self.assertEqual(caught.exception.code,'RESKIN_LAYOUT_FROZEN')
        for stage in ('full_reskin','game_tuning'):
            with self.assertRaises(GreaError) as caught:validate(production_contract(stage))
            self.assertEqual(caught.exception.code,'RESKIN_STYLE_UNAPPROVED')
        c=production_contract('game_tuning','approved');c['allowed_changes']+=['layout','navigation']
        with self.assertRaises(GreaError) as caught:validate(c)
        self.assertEqual(caught.exception.code,'RESKIN_NOT_COMPLETE')
        c['art_production']['reskin_complete']=dict(reference='reskin-bug-fixes.json',sha256='d'*64)
        result=dispatch('plan_workflow',dict(mode='evolve',source_engine='unity',change_contract=c))
        self.assertEqual(result['status'],'ok',result)
        self.assertEqual([x['stage'] for x in result['result']['reskin_sequence']],RESKIN_STAGES)
        self.assertTrue(all(not x['executed'] for x in result['result']['reskin_sequence']))
        self.assertEqual(result['result']['art_production']['stage'],'game_tuning')
        # Case admission shares the same semantic guard; no metadata is created on failure.
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'baseline';source.write_bytes(b'own original')
            bad=production_contract('sample_replace');bad['baseline_sha256']=hashlib.sha256(source.read_bytes()).hexdigest();bad['allowed_changes']+=['layout']
            r=dispatch('init_case',dict(project_dir=td,source=str(source),mode='evolve',source_engine='unity',change_contract=bad))
            self.assertEqual(r['error']['code'],'RESKIN_LAYOUT_FROZEN')
            self.assertFalse((Path(td)/'.grea').exists())

    def test_shared_ledger_is_a_declaration_not_spine_or_style_acceptance(self):
        value=ledger();result=validate_ledger(value)
        self.assertEqual(result['selection'],dict(interfaces=10,characters=1,monsters=2))
        self.assertEqual(result['status'],'validated_declared_art_ledger')
        self.assertEqual(result['declared_states']['verified'],0)
        # Scope is project-specific: no fixed ten-interface gate.
        value['selection']['interfaces']=value['selection']['interfaces'][:1]
        self.assertEqual(validate_ledger(value)['selection']['interfaces'],1)
        for mutate in [lambda x:x['records'].append(copy.deepcopy(x['records'][0])),lambda x:x['selection']['characters'].append('screen-main'),lambda x:x['selection']['monsters'].append('not-created')]:
            bad=ledger();mutate(bad)
            with self.assertRaises(ValueError):validate_ledger(bad)

    def test_static_png_cannot_close_spine_production_and_exports_need_real_fields(self):
        value=ledger();row=next(x for x in value['records'] if x['kind']=='character')
        row['state']='produced'
        for state in ('pending','authored'):
            row['spine']['state']=state
            with self.assertRaises(ValueError):validate_ledger(value)
        row['spine']={'state':'exported'}
        with self.assertRaises(ValueError):validate_ledger(value)
        row['spine'].update(editor_version='owned-example-version',runtime_version='owned-runtime-version',skeleton='Exports/hero.json',attachments=['body'],animations=['idle','attack'],events=[],atlas=['Exports/hero.atlas.txt'],textures=['Exports/hero.png'],exports=['Exports/hero.json','Exports/hero.atlas.txt','Exports/hero.png'])
        self.assertEqual(validate_ledger(value)['declared_states']['produced'],1)
        row['spine'].pop('events')
        with self.assertRaises(ValueError):validate_ledger(value)
        row['spine']['events']=[];row['spine']['state']='integrated'
        with self.assertRaises(ValueError):validate_ledger(value)
        row['targets']=['Assets/Actors/Hero.prefab'];row['state']='integrated'
        self.assertEqual(validate_ledger(value)['declared_states']['integrated'],1)
        row['spine']['state']='verified'
        with self.assertRaises(ValueError):validate_ledger(value)
        row['spine']['evidence']=['Evidence/spine-runtime.json'];row['state']='verified'
        with self.assertRaises(ValueError):validate_ledger(value)
        row['evidence']=['Evidence/hero-runtime.json']
        self.assertEqual(validate_ledger(value)['declared_states']['verified'],1) # Still declarations, no file exists/read.

    def test_png_ledger_binding_preserves_original_and_refuses_stale_or_actor_links(self):
        f=fixtures.ThemeFixtures();f.setUp();self.addCleanup(f.doCleanups)
        value=ledger();value['records'][0]['targets']=[f.mapping['assets'][0]['asset']]
        file=f.root/'art-ledger.json';file.write_text(json.dumps(value))
        f.mapping['change_contract']=production_contract();f.mapping['change_contract']['art_production']['ledger']['sha256']=f.sha(file)
        f.mapping['assets'][0]['ledger_record']='screen-main';f.save()
        before=f.target.read_bytes();meta=f.meta.read_bytes()
        result=create(f.project,f.art,f.manifest,f.root/'linked-bundle')
        self.assertEqual(result['art_ledger']['selection']['interfaces'],10)
        self.assertEqual(result['bundle'][0]['ledger_record'],'screen-main')
        self.assertEqual(f.target.read_bytes(),before);self.assertEqual(f.meta.read_bytes(),meta)
        f.mapping['assets'][0]['ledger_record']='hero-a';f.save()
        with self.assertRaises(ValueError):inspect(f.project,f.art,f.manifest)
        f.mapping['assets'][0]['ledger_record']='screen-main';f.save()
        file.write_text(json.dumps(value)+'\n')
        with self.assertRaises(ValueError):create(f.project,f.art,f.manifest,f.root/'stale-output')
        self.assertFalse((f.root/'stale-output').exists())
        f.mapping['change_contract']['art_production']['ledger'].update(reference='../escape.json',sha256='c'*64);f.save()
        with self.assertRaises(ValueError):inspect(f.project,f.art,f.manifest)

    def test_ledger_cli_requires_no_project_or_media_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'art-ledger.json';source.write_text(json.dumps(ledger()));before=source.read_bytes();output=root/'report.json'
            cmd=[sys.executable,str(ROOT/'launch_tool.py'),'theme_assets','validate-ledger','--manifest',str(source),'--output',str(output)]
            r=subprocess.run(cmd,cwd=root,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertEqual(json.loads(output.read_text())['status'],'validated_declared_art_ledger')
            self.assertEqual(source.read_bytes(),before)
            report=output.read_bytes();r=subprocess.run(cmd,cwd=root,capture_output=True,text=True)
            self.assertEqual(r.returncode,2);self.assertEqual(output.read_bytes(),report)
