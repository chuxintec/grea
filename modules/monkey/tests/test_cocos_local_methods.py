import hashlib
import json

import pytest

from monkey.cocos_local_methods import export


def test_local_method_contract_exports_only_complete_supported_bodies(tmp_path):
    source = tmp_path / 'input.js'
    bodies = [
        'T.prototype.empty=function(x){}',
        'T.prototype.forward=function(){this.notify();}',
        'T.prototype.copy=function(){this.value=this.key;}',
        'T.prototype.mixed=function(){this.notify();external();}',
        'T.prototype.param=function(x=external()){}',
        'T.prototype.clear=function(){this.node&&(this.node.active=!1),this.img&&(this.img.node.active=false,this.img.spriteFrame=null);}',
        'T.prototype.wrong=function(){this.node&&(this.other.active=!1);}',
        'T.prototype.outOfRange=function(){this.alpha&&(this.alpha.opacity=300);}',
    ]
    source.write_text(';'.join(bodies))
    digest = lambda data: hashlib.sha256(data).hexdigest()
    methods = [dict(id='method@'+str(source.read_bytes().index(body.encode())),
                    sha256=digest(body.encode()), returns='void', voidCalls=['notify'],
                    members={'value':'string','key':'string'},
                    visualFields={'node':'GameObject','img':'Image','alpha':'CanvasGroup'}) for body in bodies]
    manifest = tmp_path/'contract.json'
    spec = dict(sourceSha256=digest(source.read_bytes()),methods=methods)
    manifest.write_text(json.dumps(spec))
    result = export(source,manifest,tmp_path/'out')
    rows = json.loads((tmp_path/'out/local-methods.json').read_text())['methods']
    assert result['lowered']==4
    assert [r['body'] for r in rows]==['return;', 'this.@notify();',
                                       'this.@value = this.@key;', None, None,
                                       'if (this.@node) { this.@node.SetActive(false); }\n'
                                       'if (this.@img) { this.@img.gameObject.SetActive(false); this.@img.sprite = null; }',
                                       None, None]
    methods[0]['sha256']='0'*64
    manifest.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match='source hash'):
        export(source,manifest,tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_templates_reject_missing_duplicate_or_unlowered_methods(tmp_path):
    from monkey.cocos_local_methods import render_scripts
    raw = b'public class Sample { public void Go() { /*monkey:method@10*/ } }'
    (tmp_path/'Sample.cs').write_bytes(raw)
    template = dict(file='Sample.cs',sha256=hashlib.sha256(raw).hexdigest(),ids=['method@10'])
    bodies = {'method@10':'return;'}
    scripts = dict(render_scripts(tmp_path,[template],bodies))
    assert scripts['Sample.cs'] == raw.replace(b'/*monkey:method@10*/',b'return;')
    for bad in (dict(template,file='../Sample.cs'), dict(template,sha256='0'*64),
                dict(template,ids=[]), dict(template,ids=['method@10','method@10'])):
        with pytest.raises(ValueError):
            render_scripts(tmp_path,[bad],bodies)
    with pytest.raises(ValueError):
        render_scripts(tmp_path,[template],{'method@10':None})


def test_call_contract_cannot_authorize_a_method_by_substring():
    from monkey.cocos_local_methods import validate_contract
    with pytest.raises(ValueError, match='array'):
        validate_contract(dict(id='method@12',sha256='a'*64,voidCalls='notifyAll',members={}))


def test_forward_return_requires_exact_single_receiver_and_parameter(tmp_path):
    from monkey.cocos_local_methods import export
    bodies = ['T.prototype.'+name+'=function(e){'+body+'}' for name,body in [
        ('match','return this.list.find(e);'), ('wrong','return this.other.find(e);'),
        ('extra','this.log();return this.list.find(e);'), ('computed','return this.list["find"](e);'),
        ('changed','return this.list.find(e+1);'), ('missing','return;'),
    ]]
    source=tmp_path/'input.js'
    source.write_text(';'.join(bodies))
    digest=lambda value:hashlib.sha256(value).hexdigest()
    rows=[dict(id='method@'+str(source.read_bytes().index(b.encode())),sha256=digest(b.encode()),
               returns='GameObject',members={},voidCalls=[],returnCall=dict(field='list',method='find')) for b in bodies]
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps(dict(sourceSha256=digest(source.read_bytes()),methods=rows)))
    result=export(source,manifest,tmp_path/'generated')
    assert result['lowered']==1
    emitted=json.loads((tmp_path/'generated/local-methods.json').read_text())['methods']
    assert [r['body'] for r in emitted]==['return this.@list.@find(@e);']+[None]*5


def test_position_and_sum_require_explicit_axis_and_numeric_members(tmp_path):
    from monkey.cocos_local_methods import export
    bodies = ['T.prototype.'+name+'=function(){'+body+'}' for name,body in [
        ('init','this.start=this.node.y,this.end=this.start+this.offset;'),
        ('world','this.start=this.node.worldPosition.y;'),
        ('unmapped','this.start=this.node.x;'),
        ('mixed','this.start=this.node.y,external();'),
        ('stringAdd','this.end=this.label+this.offset;'),
    ]]
    source=tmp_path/'input.js';source.write_text(';'.join(bodies))
    digest=lambda raw:hashlib.sha256(raw).hexdigest()
    rows=[dict(id='method@'+str(source.read_bytes().index(body.encode())),sha256=digest(body.encode()),
               returns='void',voidCalls=[],members={'start':'double','end':'double','offset':'double','label':'string'},
               localPositionAxes=['y']) for body in bodies]
    manifest=tmp_path/'spec.json';manifest.write_text(json.dumps(dict(sourceSha256=digest(source.read_bytes()),methods=rows)))
    report=export(source,manifest,tmp_path/'out')
    emitted=json.loads((tmp_path/'out/local-methods.json').read_text())['methods']
    assert report['lowered']==1
    assert [r['body'] for r in emitted]==['this.@start = this.transform.localPosition.y;\nthis.@end = this.@start + this.@offset;',None,None,None,None]
