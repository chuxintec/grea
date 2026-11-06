import tempfile
import unittest
from pathlib import Path
from monkey.unity_handoff import reference_gaps


class ReferenceGapsTests(unittest.TestCase):
    def test_quarantined_code_and_unavailable_assets_are_counted_separately(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();assets=root/'Assets';assets.mkdir()
            known='1'*32;script='2'*32;missing='3'*32
            (assets/'Texture.png.meta').write_text('guid: '+known+'\n')
            quarantine=root/'SourceRecovery/Code/Provider/Assets/Scripts';quarantine.mkdir(parents=True)
            (quarantine/'Unknown.cs.meta').write_text('guid: '+script+'\n')
            refs=[known,script,script,missing,'0'*32,'0'*16+'f'+'0'*15,'0'*16+'e'+'0'*15]
            (assets/'View.prefab').write_text('%YAML 1.1\n'+''.join('  value: {fileID: 1, guid: '+g+', type: 3}\n' for g in refs))
            # Binary assets and metadata GUID definitions are not references.
            (assets/'Opaque.asset').write_bytes(('guid: '+missing).encode())
            rows=reference_gaps(root)
            self.assertEqual([(r['guid'],r['references'],r['reason']) for r in rows],[(script,2,'quarantined-provider-code'),(missing,1,'unavailable-asset-or-package')])
            self.assertTrue(rows[0]['retainedMeta'].endswith('Unknown.cs.meta'))
            self.assertEqual(rows[0]['paths'],[{'path':'Assets/View.prefab','references':2}])
            self.assertIsNone(rows[1]['retainedMeta'])
            (assets/'Restored.cs.meta').write_text('guid: '+script+'\n')
            self.assertEqual([r['guid'] for r in reference_gaps(root)],[missing])
