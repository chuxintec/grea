"""Exact PPtr closure regressions, without Editor or serialized-asset mutation."""
import tempfile
import unittest
from pathlib import Path
from beaver.errors import BeaverError
from beaver.intake import build_plan,preview
from beaver.intake_engine import expected_reference
from test_intake import _project,_candidate,_spec,_write_spec,ASSET_GUID

G='0000000000000000e000000000000000'
ROW=dict(guid=G,localId=10210,type='UnityEngine.Mesh',assembly='UnityEngine.CoreModule',name='Quad',assetPath='Library/unity default resources')
P=f'{{fileID: 10210, guid: {G}, type: 0}}\n'.encode()

class EnginePlanTests(unittest.TestCase):
 def fixture(self,root,raw=P,rows=None,version=4):
  root=root.resolve()
  candidate=_candidate(root/'candidate', [('Assets/Candidate/Panel.txt',raw,ASSET_GUID)])
  target=_project(root/'target');doc=_spec(candidate);doc.update(schemaVersion=version,externalAssets=[],packageScripts=[])
  if version>=3:doc['newScripts']=[]
  if version==4:doc['engineObjects']=[dict(ROW)] if rows is None else rows
  spec=_write_spec(root/'spec.json',doc)
  return candidate,target,spec
 def test_explicit_exact_tuple_plans_without_native_claim(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp).resolve();c,t,s=self.fixture(r);p=build_plan(c,t,s)
   self.assertEqual(p['contract'],'beaver-additive-intake/4');self.assertEqual(p['engineObjects'],[ROW]);self.assertEqual(p['native'],'not_run')
   x=preview(c,t,s,r/'out');self.assertEqual(x['engineObjects'],1);self.assertEqual(x['maximumNativePhases'],3)
 def test_no_engine_guid_wide_or_malformed_or_importer_exemption(self):
  cases=[('undeclared',P,[],4),('legacy',P,None,2),('same-guid-other-id',P+P.replace(b'10210',b'10202'),None,4),('wrong-pptr-type',P.replace(b'type: 0',b'type: 3'),None,4),('bare-guid',f'guid: {G}\n'.encode(),None,4)]
  for name,raw,rows,version in cases:
   with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
    c,t,s=self.fixture(Path(tmp),raw,rows,version)
    with self.assertRaises(BeaverError) as e:build_plan(c,t,s)
    self.assertEqual(e.exception.code,'INTAKE_DEPENDENCY_CLOSURE')
  with tempfile.TemporaryDirectory() as tmp:
   c,t,s=self.fixture(Path(tmp));meta=c/'Assets/Candidate/Panel.txt.meta';meta.write_bytes(meta.read_bytes()+b'external: '+P)
   # Re-seal only the synthetic static candidate, never a native asset.
   from helpers import finish
   finish(c,dict(schemaVersion=1,targetProfile='unity-6000.6.2f1-ugui',namespace='test-game',projectLayout='monkey-project/2.0.0',scopeMode='whole-input',diagnostics=[]))
   from beaver.io import load,write_json,sha
   doc=load(s.read_bytes());doc['candidateManifestSha256']=sha((c/'manifest.json').read_bytes());write_json(s,doc)
   with self.assertRaises(BeaverError) as e:build_plan(c,t,s)
   self.assertEqual(e.exception.code,'INTAKE_IMPORTER_REFERENCE')
 def test_unused_and_asset_domain_overlap_refuse(self):
  with tempfile.TemporaryDirectory() as tmp:
   c,t,s=self.fixture(Path(tmp),rows=[ROW,dict(ROW,localId=10202,name='Cube')])
   with self.assertRaises(BeaverError) as e:build_plan(c,t,s)
   self.assertEqual(e.exception.code,'INTAKE_ENGINE_UNUSED')
  from beaver.intake_engine import declarations
  with self.assertRaises(BeaverError):declarations([ROW],{G})
 def test_expected_field_type_and_assembly_are_bound(self):
  good={k:ROW[k] for k in ['guid','localId','type','assembly']}
  expected_reference(good,'m_Mesh',set(),{(G,10210):ROW})
  for key,value in [('localId',10202),('type','UnityEngine.Material'),('assembly','Assembly-CSharp')]:
   with self.subTest(key=key),self.assertRaises(BeaverError):expected_reference(dict(good,**{key:value}),'m_Mesh',set(),{(G,10210):ROW})
 def test_importer_observation_must_equal_independent_preflight(self):
  from beaver.intake_native import _engine_stage
  before={'engineObjects':[ROW]};_engine_stage(before,{'engineObjectsBefore':[ROW],'engineObjectsAfter':[ROW]},'target')
  for key in ['engineObjectsBefore','engineObjectsAfter']:
   with self.subTest(key=key),self.assertRaises(BeaverError):_engine_stage(before,dict(engineObjectsBefore=[ROW],engineObjectsAfter=[ROW],**{})|{key:[dict(ROW,name='Other')]},'target')

 def test_spec4_rejects_noncanonical_or_nonnull_zero_guid_without_weakening_legacy(self):
  bad=[(b'{fileID: 10210, guid: '+b'0'*32+b', type: 3}\n',[],4,'INTAKE_DEPENDENCY_CLOSURE'),(P+P.replace(G.encode(),G.upper().encode()),None,4,'INTAKE_REFERENCE_CANONICAL'),(P+b'{fileID: 10210, guid: deadbeef, type: 0}\n',None,4,'INTAKE_REFERENCE_CANONICAL')]
  for raw,rows,version,code in bad:
   with tempfile.TemporaryDirectory() as tmp:
    c,t,s=self.fixture(Path(tmp),raw,rows,version)
    with self.assertRaises(BeaverError) as e:build_plan(c,t,s)
    self.assertEqual(e.exception.code,code)
  for version,raw in [(4,b'{fileID: 0, guid: '+b'0'*32+b', type: 0}\n'),(2,b'{fileID: 10210, guid: '+b'0'*32+b', type: 3}\n')]:
   with tempfile.TemporaryDirectory() as tmp:
    c,t,s=self.fixture(Path(tmp),raw,[],version);build_plan(c,t,s)
