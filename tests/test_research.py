import hashlib,json,tempfile,unittest
from pathlib import Path
from grea.tools.research_report import normalize,report
class Research(unittest.TestCase):
 def test_count_direction_stage_unknown_and_source_integrity(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);f=p/'source.txt';f.write_text('owned example')
   v=dict(schema_version=1,game='Example',sources=[dict(id='s',path='source.txt',sha256=hashlib.sha256(f.read_bytes()).hexdigest())],items=[dict(id='p',kind='prefab',stage='parsed',source_id='s')]*2,protocols=[dict(name='Start',direction=d,kind=k,source_id='s') for d,k in [('client_to_server','rpc'),('client_to_server','rpc'),('server_to_client','rpc'),('client_to_server','field')]])
   i=p/'input.json';i.write_text(json.dumps(v));r=normalize(i)
   self.assertEqual(r['metrics']['prefab']['parsed'],1);self.assertIsNone(r['metrics']['prefab']['runtime']);self.assertIsNone(r['metrics']['level']['unique_observed']);self.assertEqual(r['protocols']['client_to_server']['rpc'],1);self.assertEqual(r['protocols']['server_to_client']['rpc'],1)
   report(i,p/'new');self.assertTrue((p/'new/report.md').is_file())
   with self.assertRaises(ValueError):report(i,p/'new')
   f.write_text('changed')
   with self.assertRaises(ValueError):normalize(i)
 def test_play_claims_remain_separate_from_static_counts(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);f=p/'source.txt';f.write_text('owned media fixture, not decoded gameplay')
   v=dict(schema_version=1,game='Example',sources=[dict(id='s',path='source.txt',sha256=hashlib.sha256(f.read_bytes()).hexdigest())],items=[dict(id='x',kind='system',stage='runtime',source_id='s')],protocols=[])
   i=p/'input.json'
   def check():
    i.write_text(json.dumps(v));return normalize(i)
   self.assertEqual(check()['play_verification'],'not_provided')
   self.assertEqual(len(check()['play_coverage_gaps']),4)
   row=dict(area='core_loop',system='Example loop',status='played',identity='v1 / first loop / 750x1334',operator='analyst',entry='start',actions='play',result='settlement',understanding='analyst hypothesis',next_step='review other systems',media=[])
   v['play_coverage']=[row]
   with self.assertRaises(ValueError):check()
   row['media']=[dict(kind='video',source_id='s')]
   with self.assertRaises(ValueError):check()
   row['media'][0]['timecode']='00:00-00:10'
   result=check()
   self.assertEqual(result['play_verification'],'analyst_reported_not_semantically_verified')
   self.assertEqual(len(result['play_coverage_gaps']),3)
   row['media'][0]['source_id']='unknown'
   with self.assertRaises(ValueError):check()
