import json
from pathlib import Path
import tempfile
import unittest

from grea.development.batch import plan, validate
from grea.development.errors import BeaverError
from grea.development.io import write_json
from .test_intake import _project, _write_asset


def event_step(expected_count=1):
    return dict(
        kind='prefab.event.inspect',
        assetPath='Assets/UI/Panel.prefab',
        path='Buttons/Confirm',
        targetNode='PanelController',
        targetComponent='Game.UI.PanelController',
        method='Confirm',
        buttonLocalId=1002,
        buttonNodeLocalId=1001,
        targetLocalId=2002,
        targetNodeLocalId=2001,
        prefabGuid='a'*32,
        targetAssembly='Game.Runtime',
        scriptGuid='b'*32,
        expectedCount=expected_count,
    )


class PrefabEventInspectTests(unittest.TestCase):
    def test_step_is_read_only_and_pins_asset_and_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project=_project(root/'project')
            _write_asset(project,'Assets/UI/Panel.prefab',b'%YAML 1.1\n--- !u!1 &1\nGameObject: {}\n','a'*32)
            spec=root/'spec.json';write_json(spec,dict(schemaVersion=2,operation='batch',steps=[event_step()]))
            result=plan(project,spec,root/'out')
            doc=json.loads(Path(result['report']).read_text())
            self.assertEqual(doc['writeSet'],[])
            self.assertIn('Assets/UI/Panel.prefab',doc['before'])
            self.assertIn('Assets/UI/Panel.prefab.meta',doc['before'])
            self.assertEqual(doc['spec']['steps'][0],event_step())
            self.assertEqual(result['metrics']['editorStarts'],0)

    def test_empty_expectation_is_supported_and_exact(self):
        validate(dict(schemaVersion=2,operation='batch',steps=[event_step(0)]))
        validate(dict(schemaVersion=2,operation='batch',steps=[event_step(1)]))
        validate(dict(schemaVersion=2,operation='batch',steps=[dict(event_step(),requireInteractable=True)]))

    def test_local_ids_accept_nonzero_signed_int64(self):
        row=event_step()
        row.update(buttonLocalId=-1,buttonNodeLocalId=-(1<<63),targetLocalId=(1<<63)-1,targetNodeLocalId=-42)
        validate(dict(schemaVersion=2,operation='batch',steps=[row]))

    def test_rejects_unbounded_or_ambiguous_identity_inputs(self):
        invalid=[]
        invalid.append(dict(event_step(),expectedCount=2))
        invalid.append(dict(event_step(),expectedCount=True))
        invalid.append(dict(event_step(),prefabGuid='A'*32))
        invalid.append(dict(event_step(),scriptGuid='bad'))
        invalid.append(dict(event_step(),buttonLocalId=0))
        invalid.append(dict(event_step(),buttonLocalId=-(1<<63)-1))
        invalid.append(dict(event_step(),targetNodeLocalId=1<<63))
        invalid.append(dict(event_step(),path='../Confirm'))
        invalid.append(dict(event_step(),targetNode='Panel//Controller'))
        invalid.append(dict(event_step(),method='PanelController.Confirm'))
        invalid.append(dict(event_step(),targetAssembly='Game/Runtime'))
        invalid.append(dict(event_step(),requireInteractable=1))
        invalid.append(dict(event_step(),unexpected='write'))
        for step in invalid:
            with self.subTest(step=step),self.assertRaises(BeaverError):
                validate(dict(schemaVersion=2,operation='batch',steps=[step]))

    def test_explicit_event_enable_reuses_binding_event_action_shape(self):
        common=dict(path='Submit',component='UnityEngine.UI.Button',property='onClick',value='empty',
                    targetNode='Panel',targetComponent='Game.UI.Panel',method='Confirm')
        for kind in ('binding.event','binding.event.enable'):
            with self.subTest(kind=kind):
                action=dict(kind=kind,**common)
                validate(dict(schemaVersion=2,operation='batch',steps=[dict(kind='prefab.patch',assetPath='Assets/UI/Panel.prefab',actions=[action])]))


if __name__=='__main__':
    unittest.main()
