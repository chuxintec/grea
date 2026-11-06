import json,unittest,tempfile,subprocess
from pathlib import Path
from monkey.code_model import inspect
from monkey.code_emit import emit
from monkey.sources.compiled import ParseError


class CodeEmitTests(unittest.TestCase):
    def test_real_state_methods_preserve_uninitialized_nan_signed_zero_and_instances(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();source=root/'source.js'
            source.write_text('function Meter(){}; Meter.prototype.initValue=function(e){this.value=e;}; Meter.prototype.getValue=function(){return this.value;}; Meter.prototype.asyncValue=async function(e){this.value=e;}; Meter.prototype.arrow=()=>this.value; process.exit(91);')
            inspect(source,root/'model','Meter')
            result=emit(source,root/'model/code-model.json',root/'emit',['value'],'js')
            self.assertEqual((result['implementedMethods'],result['pendingMethods']),(2,2))
            # Only generated code runs. Engine stub checks adapter interaction, not native registration.
            runtime=root/'emit/Cocos';(runtime/'package.json').write_text('{"type":"module"}')
            cc=runtime/'node_modules/cc';cc.mkdir(parents=True)
            (cc/'package.json').write_text('{"type":"module","exports":"./index.js"}')
            (cc/'index.js').write_text('export class Label { string="untouched"; }; export const _decorator={ccclass:name=>ctor=>ctor};')
            test=runtime/'test.mjs';test.write_text('''import assert from 'node:assert/strict';
import { Meter } from './assets/Game/Domain/State/Meter.js';
const a=new Meter(),b=new Meter(); assert.equal(a.getValue(),undefined);
for(const value of [0,-0,1,Number.MAX_VALUE,NaN,Infinity,-Infinity]) { a.initValue(value); assert.ok(Object.is(a.getValue(),value)); assert.equal(b.getValue(),undefined); assert.equal(a.string,undefined); }
assert.equal(typeof a.asyncValue,'undefined');assert.equal(typeof a.arrow,'undefined');''')
            run=subprocess.run(['node',str(test)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)

    def test_label_lifecycle_setter_is_not_bound_as_a_numeric_method(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();source=root/'source.js'
            source.write_text('cc._RF.push({},"rf-meter","Meter");(function(Base){function M(){};return extend(M,Base),M.prototype.initValue=function(e){this.value=e;},M.prototype.getValue=function(){return this.value;},M.prototype.onEnable=function(e){this.value=e;};})(cc.Label);')
            inspect(source,root/'model','Meter');result=emit(source,root/'model/code-model.json',root/'emit',['value'])
            self.assertEqual((result['implementedMethods'],result['pendingMethods']),(2,1));code=(root/'emit/Cocos/assets/Game/Presentation/UI/Meter.ts').read_text();self.assertNotIn('onEnable',code)
            self.assertIn('namespace Game.Presentation.UI {',(root/'emit/Unity/Assets/Game/Presentation/UI/Meter.cs').read_text())
            contract=json.loads((root/'emit/Analysis/Code/code-contract.json').read_text());self.assertEqual(contract['presentation']['kind'],'label-adapter');self.assertEqual(contract['pendingMethods'][0]['targetStatus'],'pending-engine-lifecycle-contract')

    def test_modified_facts_and_conflicting_type_contract_are_rejected_before_output(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp).resolve();source=root/'source.js';source.write_text('function Box(){}; Box.prototype.set=function(x){this.value=x;};')
            inspect(source,root/'model','Box');model=root/'model/code-model.json'
            with self.assertRaises(ParseError):emit(source,model,root/'bad',['unknown'])
            self.assertFalse((root/'bad').exists())
            facts=json.loads(model.read_text());facts['methods'][0]['semantic']['field']='another';model.write_text(json.dumps(facts))
            with self.assertRaises(ParseError)as error:emit(source,model,root/'changed',['another'])
            self.assertEqual(error.exception.code,'CODE_EMIT_MODEL_CHANGED');self.assertFalse((root/'changed').exists())


if __name__=='__main__':unittest.main()
