import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from monkey import code_architecture_pipeline as pipeline
from monkey.io import encoded,sha
from monkey.sources.compiled import ParseError


class NativePipelineTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.output=self.base/'Pipeline'
        self.stage=dict(root=self.base/'Architecture',request=dict(sourceRoot=str(self.base/'Frozen')),
            pins=dict(sourceManifestSha256='a'*64,architectureSha256='b'*64,validationSha256='c'*64),
            plan=dict(classes=[dict(id='state',module='Core',typeDependencies=[]),dict(id='view',module='UI',typeDependencies=['state'])],
                      modules=[dict(id='UI',classIds=['view']),dict(id='Core',classIds=['state'])]))

    def prepare(self):
        with patch.object(pipeline.modules,'_pin_stage',return_value=self.stage):
            return pipeline.prepare(self.stage['root'],self.output)

    def test_type_dependencies_precede_consumers_and_cycles_do_not_drop_modules(self):
        order,cycles=pipeline.module_order(self.stage['plan'])
        self.assertEqual(order,['Core','UI']);self.assertEqual(cycles,[])
        self.stage['plan']['classes'][0]['typeDependencies']=['view']
        order,cycles=pipeline.module_order(self.stage['plan'])
        self.assertEqual(set(order),{'Core','UI'});self.assertEqual(len(order),2)
        self.assertTrue(cycles);self.assertTrue(cycles[0]['pendingTypeModules'])

    def test_permission_block_preserves_pending_work_and_never_assembles(self):
        self.prepare()
        def prepare(*args,**kwargs):Path(args[2]).mkdir(parents=True)
        with patch.object(pipeline.modules,'_pin_stage',return_value=self.stage), \
             patch.object(pipeline.modules,'prepare',side_effect=prepare)as preparing, \
             patch.object(pipeline.modules,'status',return_value=dict(status='prepared')), \
             patch.object(pipeline.modules,'run',return_value=dict(status='blocked',blocker='permission')), \
             patch.object(pipeline,'_collect')as collecting:
            report=pipeline.run(self.output)
        self.assertEqual(report['status'],'blocked');self.assertEqual(report['blocker'],'permission')
        self.assertEqual(report['modules'][1]['status'],'pending');self.assertEqual(preparing.call_count,1)
        collecting.assert_not_called();self.assertEqual(report['runtime'],'not_run')

    def test_preparation_failure_is_durable_and_does_not_launch_any_model(self):
        self.prepare()
        with patch.object(pipeline.modules,'_pin_stage',return_value=self.stage), \
             patch.object(pipeline.modules,'prepare',side_effect=OSError('Pinned context is unavailable')), \
             patch.object(pipeline.modules,'run')as running:
            with self.assertRaises(OSError):pipeline.run(self.output)
        report=pipeline.status(self.output)
        self.assertEqual(report['status'],'blocked');self.assertEqual(report['modules'][0]['status'],'blocked')
        self.assertEqual(report['modules'][1]['status'],'pending');running.assert_not_called()

    def test_checkpoint_resumes_exact_session_and_finished_queue_is_not_rerun(self):
        self.prepare();calls=[]
        def prepare(*args,**kwargs):Path(args[2]).mkdir(parents=True)
        def run(root,*,session_id):
            calls.append((root.name,session_id))
            if len(calls)==1:return dict(status='checkpoint',sessionId='exact-saved-session')
            return dict(status='generated_unreviewed',manifestSha256='d'*64)
        def assemble(*args,**kwargs):
            target=Path(args[8]);target.mkdir();(target/'manifest.json').write_bytes(encoded(dict(status='partial')))
            return dict(status='partial')
        with patch.object(pipeline.modules,'_pin_stage',return_value=self.stage), \
             patch.object(pipeline.modules,'prepare',side_effect=prepare), \
             patch.object(pipeline.modules,'status',return_value=dict(status='prepared')), \
             patch.object(pipeline.modules,'run',side_effect=run)as running, \
             patch.object(pipeline,'_collect',return_value=(self.output/'Implementation','d'*64)), \
             patch('monkey.code_architecture_candidate.assemble_native_candidate',side_effect=assemble):
            report=pipeline.run(self.output);count=running.call_count
            repeated=pipeline.run(self.output)
        self.assertEqual(calls[1][1],'exact-saved-session');self.assertEqual(count,3)
        self.assertEqual(running.call_count,count);self.assertEqual(report['status'],'candidate_assembled_unvalidated')
        self.assertEqual(repeated['runtime'],'not_run');self.assertEqual(repeated['compilation'],'not_run')

    def test_assembly_failure_preserves_terminal_modules_and_records_stopped_state(self):
        self.prepare()
        from monkey.io import load
        state=load((self.output/'state.json').read_bytes())
        for row in state['modules']:
            row.update(status='generated_unreviewed',manifestSha256='d'*64)
        state['activeModule']='UI'
        pipeline.modules._save(self.output/'state.json',state)
        with patch.object(pipeline.modules,'_pin_stage',return_value=self.stage), \
             patch.object(pipeline.modules,'run') as running, \
             patch.object(pipeline,'_collect',return_value=(self.output/'Implementation','d'*64)), \
             patch('monkey.code_architecture_candidate.assemble_native_candidate',side_effect=OSError('assembly failed')):
            with self.assertRaises(OSError):pipeline.run(self.output)
        report=pipeline.status(self.output)
        self.assertEqual(report['status'],'blocked')
        self.assertEqual(report['blocker'],'assembly-execution-error')
        self.assertNotIn('activeModule',report)
        self.assertTrue(all(row['status']=='generated_unreviewed' for row in report['modules']))
        running.assert_not_called()

    def test_changed_global_plan_is_rejected_before_model_invocation(self):
        self.prepare();self.stage['pins']['architectureSha256']='e'*64
        with patch.object(pipeline.modules,'_pin_stage',return_value=self.stage),patch.object(pipeline.modules,'run')as running:
            with self.assertRaises(ParseError)as error:pipeline.run(self.output)
        self.assertEqual(error.exception.code,'CODE_NATIVE_SOURCE');running.assert_not_called()

    def test_continuation_reuses_exact_terminal_receipts_without_mutating_predecessor(self):
        self.prepare()
        old_request=(self.output/'request.json').read_bytes()
        from monkey.io import load
        state=load((self.output/'state.json').read_bytes())
        terminal=self.output/state['modules'][0]['task'];terminal.mkdir(parents=True)
        raw=encoded({'moduleId':'Core'});(terminal/pipeline.modules.MANIFEST).write_bytes(raw)
        state['modules'][0].update(status='generated_unreviewed',manifestSha256=sha(raw))
        state['status']='blocked';pipeline.modules._save(self.output/'state.json',state)
        old_state=(self.output/'state.json').read_bytes();next_root=self.base/'Continuation'
        with patch.object(pipeline.modules,'_pin_stage',return_value=self.stage), \
             patch.object(pipeline.modules,'status',return_value=dict(status='generated_unreviewed',manifestSha256=sha(raw))), \
             patch.object(pipeline.modules,'run') as running:
            report=pipeline.continue_run(self.output,next_root,['UI'],stop_after_module='UI')
            request=load((next_root/'request.json').read_bytes())
            self.assertEqual(pipeline.task_root(next_root,report['modules'][0],request),terminal)
            self.assertEqual(report['modules'][1]['status'],'pending')
            self.assertEqual(request['moduleOrder'],['Core','UI'])
            self.assertEqual(request['stopAfterModule'],'UI')
            running.assert_not_called()
            (terminal/pipeline.modules.MANIFEST).write_bytes(b'changed')
            with self.assertRaises(ParseError):pipeline.task_root(next_root,report['modules'][0],request)
        self.assertEqual((self.output/'request.json').read_bytes(),old_request)
        self.assertEqual((self.output/'state.json').read_bytes(),old_state)

    def test_continuation_rejects_running_predecessor_and_invalid_priorities(self):
        self.prepare()
        from monkey.io import load
        state=load((self.output/'state.json').read_bytes());state['status']='running'
        pipeline.modules._save(self.output/'state.json',state)
        with patch.object(pipeline.modules,'_pin_stage',return_value=self.stage):
            with self.assertRaises(ParseError):pipeline.continue_run(self.output,self.base/'New',['UI'])
            state['status']='blocked';pipeline.modules._save(self.output/'state.json',state)
            for priority in (['UI','UI'],['absent']):
                with self.assertRaises(ParseError):pipeline.continue_run(self.output,self.base/'New',priority)
        self.assertFalse((self.base/'New').exists())

    def test_nested_continuation_rejects_changed_earlier_ancestor(self):
        self.prepare()
        from monkey.io import load
        second=self.base/'Second';third=self.base/'Third'
        with patch.object(pipeline.modules,'_pin_stage',return_value=self.stage):
            pipeline.continue_run(self.output,second,['UI'])
            pipeline.continue_run(second,third,['Core'])
            request=load((third/'request.json').read_bytes())
            pipeline._stage(third,request)
            old=load((self.output/'state.json').read_bytes());old['status']='changed'
            pipeline.modules._save(self.output/'state.json',old)
            with self.assertRaises(ParseError) as error:pipeline._stage(third,request)
        self.assertEqual(error.exception.code,'CODE_NATIVE_REUSE')

    def test_core_integration_checkpoint_stops_between_modules_then_resumes_full_scope(self):
        self.prepare()
        from monkey.io import load
        request=load((self.output/'request.json').read_bytes());request['stopAfterModule']='Core'
        pipeline.modules._save(self.output/'request.json',request)
        def preparing(*args,**kwargs):Path(args[2]).mkdir(parents=True)
        with patch.object(pipeline.modules,'_pin_stage',return_value=self.stage), \
             patch.object(pipeline.modules,'prepare',side_effect=preparing), \
             patch.object(pipeline.modules,'status',return_value=dict(status='prepared')), \
             patch.object(pipeline.modules,'run',return_value=dict(status='generated_unreviewed',manifestSha256='d'*64)) as running, \
             patch.object(pipeline,'_collect') as collecting:
            report=pipeline.run(self.output)
            self.assertEqual(report['status'],'integration_checkpoint')
            self.assertEqual(running.call_count,1);collecting.assert_not_called()
            self.assertEqual(report['modules'][1]['status'],'pending')
        # The stop marker belongs to the completed module, so the next run does
        # not replay it or stop before starting the remaining full scope.
        def assemble(*args,**kwargs):
            target=Path(args[8]);target.mkdir();(target/'manifest.json').write_bytes(encoded(dict(status='partial')))
            return dict(status='partial')
        with patch.object(pipeline.modules,'_pin_stage',return_value=self.stage), \
             patch.object(pipeline.modules,'prepare',side_effect=preparing), \
             patch.object(pipeline.modules,'status',return_value=dict(status='prepared')), \
             patch.object(pipeline.modules,'run',return_value=dict(status='generated_unreviewed',manifestSha256='e'*64)) as running, \
             patch.object(pipeline,'_collect',return_value=(self.output/'Implementation','d'*64)), \
             patch('monkey.code_architecture_candidate.assemble_native_candidate',side_effect=assemble):
            report=pipeline.run(self.output)
            self.assertEqual(running.call_count,1)
            self.assertEqual(report['status'],'candidate_assembled_unvalidated')
