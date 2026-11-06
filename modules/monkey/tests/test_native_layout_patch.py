import unittest
import json
import tempfile
import contextlib
import io
from pathlib import Path
from unittest.mock import patch
from monkey.native_layout_patch import classify,serialized_layout_ids,aggregate_node_ids,object_headers,finish,execute
from monkey.io import sha
from monkey.normalize import component_ir
from monkey.sources.compiled import ParseError


class NativeLayoutPatchTests(unittest.TestCase):
    def spec(self,**kwargs):
        row=dict(sourceId='grid',startAxis=0,constraint=0,affectedByScale=False,resize=1,cellSize=[40,40],enabled=True,horizontalDirection=0,verticalDirection=1,padding=[0,10,0,10],spacingXY=[20,20])
        return dict(row,**kwargs)
    def test_uniform_cells_choose_unity_grid_without_source_arrangement(self):
        row=classify(self.spec(),dict(size=[500,300]),[dict(size=[100,100]),dict(size=[100,100])])
        self.assertEqual(row['mode'],'unity-content-grid');self.assertEqual(row['cellSize'],[100,100]);self.assertTrue(row['fitVertical'])
    def test_heterogeneous_authored_single_row_is_horizontal_but_unknown_wrap_is_refused(self):
        children=[dict(size=[39,39]),dict(size=[520,170.4])]
        self.assertEqual(classify(self.spec(spacingXY=[5,5]),dict(size=[569,180.4]),children)['mode'],'unity-horizontal-row')
        with self.assertRaises(ParseError):classify(self.spec(spacingXY=[5,5]),dict(size=[300,180.4]),children)
    def test_missing_nested_dimensions_use_only_exact_template_size(self):
        row=classify(self.spec(),dict(size=[674,0]),[dict(size=[0,0])],[186,250],[186,250]);self.assertEqual(row['cellSize'],[186,250])
        with self.assertRaises(ParseError):classify(self.spec(),dict(size=[674,0]),[dict(size=[0,0])])
        with self.assertRaises(ParseError):classify(self.spec(),dict(size=[674,0]),[dict(size=[0,0])],[40,40],[186,250])
    def test_disabled_and_source_sizing_are_preserved_without_enabling_old_behavior(self):
        row=classify(self.spec(resize=2,enabled=False),dict(size=[500,500]),[dict(size=[85,85])],[85,85]);self.assertEqual(row['cellSize'],[85,85]);self.assertFalse(row['enabled']);self.assertTrue(row['staticAuthoredRects'])
        with self.assertRaises(ParseError):classify(self.spec(affectedByScale=True),dict(size=[500,500]),[dict(size=[100,100])])
    def test_original_cell_size_alias_and_conflicts_are_not_defaulted(self):
        obj=dict(__type__='cc.Layout',node={'__id__':1},**{'_N$layoutType':3,'_resize':2,'_N$cellSize':{'__value_type__':5,'values':[85,85]}})
        value,_=component_ir('sample',0,obj);self.assertEqual(value['cellSize'],[85,85]);self.assertTrue(value['cellSizeFromSource'])
        obj['_cellSize']={'width':40,'height':40}
        with self.assertRaises(ParseError):component_ir('sample',0,obj)

    def test_retirement_requires_exact_owned_slot_and_refuses_incoming_local_references(self):
        guid='a'*32
        body=('--- !u!1 &10\nGameObject:\n  m_Component:\n  - component: {fileID: 30}\n'
              '--- !u!114 &30\nMonoBehaviour:\n  m_GameObject: {fileID: 10}\n  m_Script: {fileID: 11500000, guid: '+guid+', type: 3}\n').encode()
        cases=[dict(sourceId='source#1/components/0',node='source#1')]
        ids={'source#1':dict(gameObjectFileId='10')}
        self.assertEqual(serialized_layout_ids(body,guid,ids,cases)[0]['oldComponentFileId'],'30')
        with self.assertRaises(ParseError):serialized_layout_ids(body+b'  manualReference: {fileID: 30}\n',guid,ids,cases)
        with self.assertRaises(ParseError):serialized_layout_ids(body,guid,ids,[])

    def test_aggregate_mapping_uses_exact_ordinals_and_rejects_changed_graph(self):
        def block(kind,fid,lines):return ('--- !u!'+str(kind)+' &'+str(fid)+'\nObject:\n'+lines).encode()
        body=block(1,1,'  m_Name: Candidate\n')+block(1,2,'  m_Name: DesignRoot\n')+block(1,3,'  m_Name: UntrustedName\n')
        body+=block(224,11,'  m_GameObject: {fileID: 1}\n  m_Father: {fileID: 0}\n  m_Children:\n  - {fileID: 12}\n')
        body+=block(224,12,'  m_GameObject: {fileID: 2}\n  m_Father: {fileID: 11}\n  m_Children:\n  - {fileID: 13}\n')
        body+=block(224,13,'  m_GameObject: {fileID: 3}\n  m_Father: {fileID: 12}\n  m_Children: []\n')
        plan=dict(roots=['real#1'],nodes=[dict(sourceId='real#1',children=[])])
        self.assertEqual(aggregate_node_ids(body,plan)['real#1']['gameObjectFileId'],'3')
        plan['nodes'][0]['children']=['missing#2']
        with self.assertRaises(ParseError):aggregate_node_ids(body,plan)

    def test_object_identity_reader_keeps_unrelated_owner_and_script_and_refuses_duplicate_ids(self):
        raw=b'--- !u!114 &30\nMonoBehaviour:\n  m_GameObject: {fileID: 10}\n  m_Script: {fileID: 11500000, guid: '+b'a'*32+b', type: 3}\n'
        self.assertEqual(object_headers(raw)['30'],dict(classId=114,scriptGuid='a'*32,gameObjectFileId='10'))
        with self.assertRaises(ParseError):object_headers(raw+raw)

    def test_partial_native_evidence_cannot_be_frozen(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);(root/'execution-result.json').write_text(json.dumps(dict(status='partial',processExited=True,exitCode=1)))
            with self.assertRaises(ParseError):finish(root,root/'out')
            self.assertFalse((root/'out').exists())

    def test_changed_prepared_helper_is_rejected_before_any_child_launch(self):
        with tempfile.TemporaryDirectory()as tmp:
            prepared=Path(tmp)/'prepared';root=prepared/'UnityProject';source=Path(tmp)/'source';source.mkdir();(root/'Analysis').mkdir(parents=True);(root/'Assets/Editor').mkdir(parents=True)
            raw=b'{"schemaVersion":1}'
            (root/'Analysis/layout-patch-plan.json').write_bytes(raw)
            (root/'Analysis/output-paths.json').write_text(json.dumps(dict(plan='Assets/Editor/import-plan.json')))
            (root/'Assets/Editor/UnityLayoutPatch.cs').write_text('changed')
            (prepared/'preparation.json').write_text(json.dumps(dict(status='prepared',candidate=str(root),source=str(source),patchPlanSha256=sha(raw),helperSha256=sha(b'original'))))
            with patch('monkey.native_layout_patch.subprocess.Popen',side_effect=AssertionError('must not launch')):
                with self.assertRaises(ParseError):execute(prepared,Path(tmp)/'out','/missing/editor',900,'2026-10-24T18:32:00Z','2026-10-24T18:35:00Z',True)
            self.assertFalse((Path(tmp)/'out').exists())

    def test_cli_partial_native_execution_is_not_a_success_exit(self):
        from monkey.cli import main
        args=['native-layout-patch','--preparation','unused','--out','unused','--editor','unused','--deadline-utc','2026-10-24T18:42:00Z','--window-end-utc','2026-10-24T18:45:00Z','--execute']
        with patch('monkey.native_layout_patch.execute',return_value=dict(status='partial',processExited=True,exitCode=-15)),contextlib.redirect_stdout(io.StringIO())as output:
            self.assertEqual(main(args),2)
        self.assertEqual(json.loads(output.getvalue())['status'],'partial')


if __name__=='__main__':unittest.main()
