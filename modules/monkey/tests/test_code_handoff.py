import tempfile,unittest
from pathlib import Path
from test_package import wxpackage,files
from monkey.package import convert_package
from monkey.cocos_code_handoff import enrich
from monkey.io import read,load,sha,write_json
from monkey.sources.compiled import ParseError


class CodeHandoffLayoutTests(unittest.TestCase):
    def convert(self,root):
        source=root/'game.wxapkg';source.write_bytes(wxpackage(files()))
        convert_package(source,'unity',root/'out')
        project=root/'out/UnityProject'
        modules=[m for m in load(read(project/'Analysis/Code/code-index.json'))['modules'] if m.get('entryType')=='module_candidate']
        facts=root/'facts.json'
        write_json(facts,dict(records=[dict(id=m['sourceId'],sha256=m['sha256'],members=dict(fields=[],functions=[],
            methods=[dict(name='onOpen',parameters=[],static=False,ownerAlias='t',sourceBytes=dict(start=0,end=1),sourceSha256='0'*64)])) for m in modules]))
        return project,modules,facts

    def test_named_draft_replaces_the_generated_stub_in_place(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,modules,facts=self.convert(root)
            self.assertTrue(modules)
            for m in modules:
                self.assertTrue(m['draft'].startswith('SourceRecovery/Code/Drafts/CSharp/'),m['draft'])
                self.assertNotIn('Recovered.',read(project/m['draft']).decode())
            before=sha(read(project/'manifest.json'))
            result=enrich(project,root/'handoff',expected_manifest=before,apply=True,reuse_facts=facts,expected_facts=sha(read(facts)))
            self.assertTrue(result['applied'])
            manifest=load(read(project/'manifest.json'));owned={f['path']:f for f in manifest['files']}
            for m in modules:
                body=read(project/m['draft']).decode()
                self.assertIn('onOpen',body);self.assertIn('namespace '+m['namespace']+' {',body)
                self.assertEqual(owned[m['draft']]['sha256'],sha(body.encode()))
            self.assertFalse((project/'SourceRecovery/CodeDrafts').exists())
            self.assertIn('Docs/CODE-STATUS.md',owned)

    def test_hand_edited_draft_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();project,modules,facts=self.convert(root)
            draft=project/modules[0]['draft'];draft.write_text(draft.read_text()+'// human note\n')
            with self.assertRaisesRegex(ParseError,'CODE_HANDOFF_TARGET_CHANGED'):
                enrich(project,root/'handoff',expected_manifest=sha(read(project/'manifest.json')),apply=True,reuse_facts=facts,expected_facts=sha(read(facts)))
            self.assertIn('// human note',draft.read_text())


if __name__=='__main__':
    unittest.main()
