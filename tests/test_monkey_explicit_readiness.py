import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from grea.integrations.monkey import local

class ExplicitLockReadinessTests(unittest.TestCase):
 def test_explicit_fixed_lock_uses_identity_probe_without_install_introspection(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);lock=r/'lock.json';lock.write_text('{}');cfg=dict(version='0.8.0.dev7',command=['/fixed/shell-launcher'],identity_root='/fixed/package')
   with patch.dict(os.environ,dict(GREA_MONKEY_LOCK=str(lock),GREA_PROVIDERS=str(r/'providers'),GREA_PROVIDER_STATE_DIR=str(r/'state'))),patch('grea.integrations.monkey.pipeline.probe',return_value=(cfg,{})) as probe,patch.object(local,'probe_installation') as automatic,patch.object(local,'discover',return_value={'status':'not_installed'}):
    result=local.readiness(r/'out',ensure=True,install_missing=True)
    self.assertTrue(result['ready']);self.assertFalse(result['installed']);probe.assert_called_once();automatic.assert_not_called();self.assertFalse((r/'state').exists())
 def test_invalid_explicit_lock_fails_closed_without_fallback(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);lock=r/'lock';lock.write_text('{}')
   with patch.dict(os.environ,dict(GREA_MONKEY_LOCK=str(lock),GREA_PROVIDERS='explicit',GREA_PROVIDER_STATE_DIR=str(r/'state'))),patch('grea.integrations.monkey.pipeline.probe',side_effect=ValueError('Provider launcher changed')),patch.object(local,'probe_installation') as automatic:
    with self.assertRaisesRegex(ValueError,'launcher changed'):local.readiness(r/'out')
    automatic.assert_not_called();self.assertFalse((r/'state').exists())
 def test_lock_drift_during_probe_refuses_readiness(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp);lock=r/'lock';lock.write_text('{}')
   def change(*args):lock.write_text('{"changed":true}');return dict(version='0.8.0.dev7',command=['/fixed'],identity_root='/fixed'),{}
   with patch.dict(os.environ,dict(GREA_MONKEY_LOCK=str(lock),GREA_PROVIDERS='explicit',GREA_PROVIDER_STATE_DIR=str(r/'state'))),patch('grea.integrations.monkey.pipeline.probe',side_effect=change):
    with self.assertRaisesRegex(ValueError,'changed during'):local.readiness(r/'out')
 def test_lock_requires_explicit_provider_config(self):
  with tempfile.TemporaryDirectory() as tmp:
   r=Path(tmp)
   with patch.dict(os.environ,dict(GREA_MONKEY_LOCK=str(r/'lock'),GREA_PROVIDERS='',GREA_PROVIDER_STATE_DIR=str(r/'state'))):
    with self.assertRaisesRegex(ValueError,'matching GREA_PROVIDERS'):local.readiness(r/'out')
