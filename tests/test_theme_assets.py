"""Own PNG fixtures only. No real project assets or Unity process is touched."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from PIL import Image
from grea.change_contracts import INVARIANTS, validate
from grea.common import GreaError
from jsonschema.exceptions import ValidationError
from grea.tools.theme_assets import inspect,create

def contract(sha='a'*64,state='candidate'):
    return dict(schema_version=1,scope='ui_ux',baseline_sha256=sha,product_id='Derived',baseline_product_id='Original',save_namespace='derived-test',baseline_save_namespace='original-test',design=dict(state=state,reference='own-design-v1',sha256='b'*64),allowed_changes=['visual_style','layout'],invariants=INVARIANTS[:],ui_ux_budget='overall page/flow scope; no per-page or pixel quota')

class ThemeFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve()
        self.project=self.root/'Project';self.art=self.root/'Art';self.art.mkdir();self.target=self.project/'Assets/UI/button.png';self.target.parent.mkdir(parents=True)
        Image.new('RGBA',(16,16),(230,20,10,150)).save(self.target)
        Image.new('RGBA',(16,16),(10,210,150,170)).save(self.art/'new.png')
        self.meta=Path(str(self.target)+'.meta');self.meta.write_text('guid: '+'1'*32+'\n')
        self.mapping=dict(schema_version=1,change_contract=contract(),assets=[dict(usage='ui_sprite',alpha_required=False,asset='Assets/UI/button.png',replacement='new.png',source_sha256=self.sha(self.target),replacement_sha256=self.sha(self.art/'new.png'),meta_sha256=self.sha(self.meta),guid='1'*32,sprite=dict(mode='single',width=16,height=16,pivot=[0.5,0.5],border=[2,2,2,2],pixels_per_unit=100,file_id=21300000))])
        self.manifest=self.root/'mapping.json';self.save()
    def sha(self,p):return hashlib.sha256(p.read_bytes()).hexdigest()
    def save(self):self.manifest.write_text(json.dumps(self.mapping))
    def test_preview_bundle_incremental_and_inputs_unchanged(self):
        original=self.target.read_bytes();meta=self.meta.read_bytes()
        result=create(self.project,self.art,self.manifest,self.root/'preview',True)
        self.assertTrue((self.root/'preview/preview.png').is_file())
        bundle=create(self.project,self.art,self.manifest,self.root/'bundle')
        self.assertEqual(bundle['plan_id'],result['plan_id']);self.assertEqual(len(bundle['bundle']),1)
        row=bundle['bundle'][0];self.assertEqual(self.sha(self.root/'bundle'/row['before']),row['source_sha256']);self.assertEqual(self.sha(self.root/'bundle'/row['after']),row['replacement_sha256'])
        self.assertEqual(self.target.read_bytes(),original);self.assertEqual(self.meta.read_bytes(),meta)
        with self.assertRaises(ValueError):create(self.project,self.art,self.manifest,self.root/'bundle')
        self.mapping['assets'][0].update(replacement_sha256=self.sha(self.target));(self.art/'new.png').write_bytes(original);self.save()
        self.assertEqual(create(self.project,self.art,self.manifest,self.root/'noop')['bundle'],[])
    def test_cli_from_unrelated_cwd_for_two_layouts(self):
        import subprocess,sys
        script=Path(__file__).resolve().parents[1]/'launch_tool.py'
        cwd=self.root/'Elsewhere';cwd.mkdir()
        for index,(name,size,pivot,border) in enumerate([('Assets/UI/button.png',(16,16),[0.5,0.5],[2,2,2,2]),('Assets/Hud/图标.png',(8,20),[0.25,0.1],[1,2,1,2])]):
            target=self.project/name;target.parent.mkdir(parents=True,exist_ok=True)
            Image.new('RGBA',size,(30,40,70,255)).save(target)
            Path(str(target)+'.meta').write_text('guid: '+'2'*32+'\n')
            Image.new('RGBA',size,(10,80,120,200)).save(self.art/'new.png')
            row=self.mapping['assets'][0];row.update(asset=name,source_sha256=self.sha(target),replacement_sha256=self.sha(self.art/'new.png'),meta_sha256=self.sha(Path(str(target)+'.meta')),guid='2'*32,sprite=dict(mode='single',width=size[0],height=size[1],pivot=pivot,border=border,pixels_per_unit=48,file_id=21300000))
            self.save();output=self.root/f'cli-{index}.json'
            result=subprocess.run([sys.executable,str(script),'theme_assets','validate','--project',str(self.project),'--replacements',str(self.art),'--manifest',str(self.manifest),'--output',str(output)],cwd=cwd,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads(output.read_text())['status'],'validated_declared_mapping')
            repeated=subprocess.run([sys.executable,str(script),'theme_assets','validate','--project',str(self.project),'--replacements',str(self.art),'--manifest',str(self.manifest),'--output',str(output)],cwd=cwd,capture_output=True,text=True)
            self.assertEqual(repeated.returncode,2)

    def test_stale_meta_input_and_project_overlap_never_write(self):
        self.meta.write_text('edited')
        with self.assertRaises(ValueError):create(self.project,self.art,self.manifest,self.root/'bad')
        self.assertFalse((self.root/'bad').exists())
        self.mapping['assets'][0]['meta_sha256']=self.sha(self.meta);self.save()
        with self.assertRaises(ValueError):create(self.project,self.art,self.manifest,self.project/'output')
    def test_dimension_multi_sprite_traversal_and_alias_rejected(self):
        original=copy.deepcopy(self.mapping)
        for name,change in [('skeleton',lambda x:x['assets'][0].update(usage='skeleton_atlas')),('alpha',lambda x:x['assets'][0].update(alpha_required=True)),('multi',lambda x:x['assets'][0]['sprite'].update(mode='multiple')),('escape',lambda x:x['assets'][0].update(asset='../outside.png')),('border',lambda x:x['assets'][0]['sprite'].update(border=[10,0,10,0])),('alias',lambda x:x['assets'].append(dict(x['assets'][0],asset='assets/ui/BUTTON.png')))]:
            with self.subTest(name=name):
                self.mapping=copy.deepcopy(original);change(self.mapping);self.save()
                with self.assertRaises((ValueError,ValidationError)) as raised:inspect(self.project,self.art,self.manifest)
                self.assertIsNotNone(raised.exception)
        self.mapping=copy.deepcopy(original);Image.new('RGBA',(17,16),'red').save(self.art/'new.png');self.mapping['assets'][0]['replacement_sha256']=self.sha(self.art/'new.png');self.save()
        with self.assertRaises(ValueError):inspect(self.project,self.art,self.manifest)
    def test_identity_collision_and_nonfinite_contract(self):
        value=contract();value['save_namespace']=value['baseline_save_namespace']
        with self.assertRaises(GreaError):validate(value)
        self.mapping['assets'][0]['sprite']['pivot']=[float('nan'),0.5];self.save()
        with self.assertRaises(ValueError):inspect(self.project,self.art,self.manifest)
