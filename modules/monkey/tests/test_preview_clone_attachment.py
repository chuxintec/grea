import json
import tempfile
import unittest
from pathlib import Path
from monkey import io
from monkey.prefab_preview_state import attach, attach_clones, replace_state, PreviewStateError
from monkey.prefab_preview_clones import prepare_clones
from test_prefab_preview_clones import fixture


class CloneAttachmentTests(unittest.TestCase):
    def test_exact_plan_and_state_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            fixture(root)
            plan_path=root/'stage/plan.json'
            plan=json.loads(plan_path.read_text())
            proof=root/'source-evidence.json'
            state={'schemaVersion':1,'id':'state','sourcePrefabId':plan['sourcePrefabs'][0]['sourceId'],
                'sourceManifestSha256':plan['sourceManifestSha256'],'sourceVersion':'source-1','referenceVersion':'fixture-1',
                'evidence':[{'id':'proof','path':proof.name,'sha256':io.sha(proof.read_bytes())}],
                'operations':[{'kind':'node.active','sourceId':plan['nodes'][0]['sourceId'],'expectedValue':True,'value':True,'evidenceId':'proof'}]}
            path=root/'state.json';io.write_json(path,state);digest=io.sha(path.read_bytes())
            attach(plan_path,path,digest,root/'state-plan')
            spec_path=root/'clone-spec.json'
            # Fixture returns its prepared input paths; discover the named clone
            # source from the bounded fixture directory, not a product sample.
            if not spec_path.exists():
                spec_path=next(p for p in root.glob('*.json') if json.loads(p.read_text()).get('schema')=='monkey-prefab-preview-clones/1')
            current=root/'state-plan/plan.json'
            prepare_clones(spec_path,io.sha(spec_path.read_bytes()),current,io.sha(current.read_bytes()),root,root/'prepared')
            batch=root/'prepared/clone-batch.json'
            attach_clones(current,digest,[batch],[io.sha(batch.read_bytes())],root/'cloned')
            actual=io.stage_document(root/'cloned/plan.json')
            self.assertEqual(actual['previewState']['stateSha256'],digest)
            self.assertEqual(len(actual['previewState']['cloneBatches'][0]['instances']),2)
            replacement=dict(state,id='new-state');replacement_path=root/'replacement.json';io.write_json(replacement_path,replacement)
            parent=root/'cloned/plan.json'
            replace_state(parent,io.sha(parent.read_bytes()),digest,replacement_path,io.sha(replacement_path.read_bytes()),root/'replaced')
            replaced=io.stage_document(root/'replaced/plan.json')
            self.assertEqual(replaced['previewState']['stateId'],'new-state')
            self.assertEqual(replaced['previewState']['cloneBatches'],actual['previewState']['cloneBatches'])
            self.assertEqual(io.stage_document(parent)['previewState']['stateId'],'state')
            with self.assertRaises(PreviewStateError):
                attach_clones(root/'cloned/plan.json',digest,[batch],[io.sha(batch.read_bytes())],root/'duplicate')
            with self.assertRaises(PreviewStateError):
                attach_clones(current,digest,[batch],['0'*64],root/'tampered')
