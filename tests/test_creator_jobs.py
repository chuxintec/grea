import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'),'Node unavailable')
class CreatorJobTests(unittest.TestCase):
    def run_js(self,script):
        adapter=Path(__file__).resolve().parents[1]/'src/monkey/targets/CreatorJobs.js'
        result=subprocess.run(['node','-e',script,str(adapter)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr[:3000])

    def test_short_rpc_can_poll_long_work_then_consume_result_once(self):
        self.run_js(r'''
const jobs=require(process.argv[1]),assert=require('assert');
(async()=>{
let release,started=false;const barrier=new Promise(r=>release=r);
const handlers={assemble:async()=>{started=true;await barrier;return {serialized:'native scene'};}};
const begun=jobs.begin('assemble',[{nativeDeadlineMs:Date.now()+60000}],handlers);
assert.strictEqual(started,false);assert.strictEqual(jobs.status(begun.jobId).status,'running');
assert.throws(()=>jobs.begin('assemble',[{}],handlers),/ALREADY_EXISTS/);
await new Promise(r=>setImmediate(r));assert.strictEqual(started,true);
jobs.progress('hierarchy',12,30);
assert.strictEqual(jobs.status(begun.jobId).processed,12);
assert.throws(()=>jobs.take(begun.jobId),/NOT_COMPLETE/);
assert.throws(()=>jobs.status('foreign job'),/ID_MISMATCH/);
release();await new Promise(r=>setImmediate(r));
assert.strictEqual(jobs.status(begun.jobId).status,'completed');
assert.deepStrictEqual(jobs.take(begun.jobId),{serialized:'native scene'});
assert.throws(()=>jobs.take(begun.jobId),/ID_MISMATCH/);
})().catch(e=>{console.error(e);process.exitCode=1;});
''')

    def test_deadline_and_method_whitelist_remain_enforced(self):
        self.run_js(r'''
const jobs=require(process.argv[1]),assert=require('assert');
(async()=>{
const handlers={assemble:async()=>new Promise(()=>{})};
assert.throws(()=>jobs.begin('arbitrary-code',[{}],handlers),/METHOD_INVALID/);
assert.throws(()=>jobs.begin('assemble',[{nativeDeadlineMs:Date.now()-1}],handlers),/BUDGET_EXHAUSTED/);
const original=Date.now;let instant=original();Date.now=()=>instant;
const begun=jobs.begin('assemble',[{nativeDeadlineMs:instant+100}],handlers);
instant+=101;
assert.strictEqual(jobs.status(begun.jobId).status,'failed');
assert.strictEqual(jobs.status(begun.jobId).error,'NATIVE_BUDGET_EXHAUSTED');
assert.throws(()=>jobs.take(begun.jobId),/BUDGET_EXHAUSTED/);
Date.now=original;
})().catch(e=>{console.error(e);process.exitCode=1;});
''')

    def test_first_native_error_is_recorded_without_source_argument_dump(self):
        self.run_js(r'''
const jobs=require(process.argv[1]),assert=require('assert');
(async()=>{
const begun=jobs.begin('readSaved',['scene',{nativeDeadlineMs:Date.now()+60000}],{readSaved:async()=>{throw Error('missing original font\nlarge source argument dump');}});
await new Promise(r=>setImmediate(r));
const state=jobs.status(begun.jobId);assert.strictEqual(state.status,'failed');assert.strictEqual(state.error,'missing original font');
assert.throws(()=>jobs.take(begun.jobId),/missing original font/);
})().catch(e=>{console.error(e);process.exitCode=1;});
''')

    def test_native_comparison_details_are_retained_with_a_bounded_error(self):
        self.run_js(r'''
const jobs=require(process.argv[1]),assert=require('assert');
(async()=>{
const details='STATIC_REFERENCE_COMPARISON:'+JSON.stringify({expected:'a'.repeat(1800),actual:'b'.repeat(1800)});
const begun=jobs.begin('readSaved',['scene',{}],{readSaved:async()=>{throw Error(details+'x'.repeat(20000)+'\nprivate argument dump');}});
await new Promise(r=>setImmediate(r));
const message=jobs.status(begun.jobId).error;
assert(message.startsWith(details));assert.strictEqual(message.length,16*1024);
assert(!message.includes('private argument dump'));
})().catch(e=>{console.error(e);process.exitCode=1;});
''')
