import json,tempfile,hashlib,unittest
from pathlib import Path
from test_prefab_preview_state import fixture
from monkey.prefab_preview_state import prepare,PreviewStateError

class NumericPreviewTests(unittest.TestCase):
    def test_source_numbers_and_nullable_sprite_are_verified_before_projection(self):
        with tempfile.TemporaryDirectory()as temp:
            p,_,plan,state,_=fixture(Path(temp));label=plan['components'][0];label.update(fontSize=30,lineHeight=42)
            plan['nodes'][0]['opacity']=255
            state['operations']=[dict(kind='label.fontSize',sourceId=label['sourceId'],expectedValue=30,value=40,evidenceId='capture-1'),dict(kind='label.lineHeight',sourceId=label['sourceId'],expectedValue=42,value=50,evidenceId='capture-1'),dict(kind='node.opacity',sourceId=plan['nodes'][0]['sourceId'],expectedValue=255,value=0,evidenceId='capture-1'),dict(kind='sprite.asset',sourceId=plan['components'][1]['sourceId'],expectedValue='bundle:sprite-old',value=None,evidenceId='capture-1')]
            p.write_text(json.dumps(state));h=hashlib.sha256(p.read_bytes()).hexdigest();result=prepare(p,h,plan,Path(temp).resolve()/'good')
            self.assertEqual([o.get('numberValue')for o in result['operations'][:3]],[40,50,0]);self.assertFalse(result['operations'][-1]['sourceEnabled'])
            state['operations'][0]['expectedValue']=31;p.write_text(json.dumps(state));h=hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaises(PreviewStateError):prepare(p,h,plan,Path(temp).resolve()/'bad')
