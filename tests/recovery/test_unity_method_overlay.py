import hashlib
import json
from pathlib import Path

import pytest

from grea.recovery.unity_method_overlay import apply, function_table, lift_bool_accessor
from .test_wasm_code_sources import fixture_metadata, fixture_module, section


def test_bool_accessors_require_complete_instructions_and_source_field_types():
    fields = {12:'gray', 20:'dirty'}
    assert lift_bool_accessor(bytes.fromhex('0020002d000c0f0b'), fields, 'bool get_Gray()') == 'return gray;'
    assert lift_bool_accessor(bytes.fromhex('00200020013a00140b'), fields, 'void set_Dirty(bool value)') == 'dirty=value;'
    body = bytes.fromhex('00200120002d000c470440200041013a0014200020013a000c0b0b')
    assert lift_bool_accessor(body, fields, 'void set_Gray(bool value)') == 'if(value!=gray){dirty=true;gray=value;}'
    for raw in (body+b'\0', body[:-1], body.replace(b'\x41\x01', b'\x41\x00')):
        with pytest.raises(ValueError):
            lift_bool_accessor(raw, fields, 'void set_Gray(bool value)')
    with pytest.raises(ValueError):
        lift_bool_accessor(body, {12:'gray'}, 'void set_Gray(bool value)')


def test_table_offsets_and_later_active_segments():
    header = b'\0asm\x01\0\0\0'
    assert function_table(header + section(9, bytes.fromhex('020041030b0205070041040b0109'))) == {3:5,4:9}
    for payload in ('010141000b0101','0100417f0b0101'):
        with pytest.raises(ValueError):
            function_table(header + section(9, bytes.fromhex(payload)))


def test_overlay_checks_full_batch_before_writes_and_can_retry(tmp_path):
    def sha(raw):
        return hashlib.sha256(raw).hexdigest()
    def pin(name, raw):
        (tmp_path/name).write_bytes(raw)
        return dict(path=name, sha256=sha(raw))
    wasm,body,index,_ = fixture_module()
    at = wasm.index(section(10, bytes((1,len(body)))+body))
    wasm = wasm[:at]+section(9,bytes.fromhex('010041030b0100'))+wasm[at:]
    segments=[pin('segment',wasm)]
    metadata=pin('meta', fixture_metadata())
    dump=pin('dump',b'// Namespace: BattleCore\npublic class FP // TypeDefIndex: 0\n{\n// RVA: 0x3 Offset: 0x3\npublic static FP op_Addition(FP x, FP y) { }\n}\n')
    project=tmp_path/'candidate';target=project/'Assets/FP.cs';target.parent.mkdir(parents=True)
    original=b'public class FP {}';new=b'public class FP { /* reviewed */ }'
    target.write_bytes(original);(tmp_path/'trans').write_bytes(new)
    guid='a'*32;Path(str(target)+'.meta').write_text('guid: '+guid+'\n')
    method=dict(signature='public static FP op_Addition(FP x, FP y) { }', slot=3, metadataMethodIndex=0,
                sha256=sha(body), token='0x06000001', segmentSha256=sha(wasm), functionIndex=0)
    row=dict(asset='Assets/FP.cs',guid=guid,type='BattleCore.FP',typeIndex=0,translation='trans',
             before=sha(original),after=sha(new),methods=[method])
    manifest=tmp_path/'manifest.json'
    def write(scripts):
        manifest.write_text(json.dumps(dict(dump=dump,metadata=metadata,segments=segments,scripts=scripts)))
    write([row,dict(row,asset='Assets/missing/FP.cs')])
    with pytest.raises((ValueError, FileNotFoundError)):apply(project,manifest)
    assert target.read_bytes()==original
    for bad in (dict(method,slot=4),dict(method,token='0x06000002'),dict(method,sha256='0'*64),dict(method,segmentSha256='1'*64),dict(method,functionIndex=1)):
        write([dict(row,methods=[bad])])
        with pytest.raises(ValueError):apply(project,manifest)
        assert target.read_bytes()==original
    write([row]);assert apply(project,manifest)==apply(project,manifest)=={'scripts':1,'methods':1}
    assert target.read_bytes()==new
    target.write_text('local edit')
    with pytest.raises(ValueError):apply(project,manifest)
    assert target.read_text()=='local edit'


def test_numeric_accessors_check_types_and_preserve_mirrored_index():
    from grea.recovery.unity_method_overlay import lift_numeric_accessor
    fields = {12: ('float', 'Index'), 20: ('int', 'mItemIndex'), 44: ('float', 'mPadding')}
    body = bytes.fromhex('002000200136021420002001b238020c0b')
    assert lift_numeric_accessor(body, fields, 'void set_ItemIndex(int value)') == 'mItemIndex=value;Index=value;'
    assert lift_numeric_accessor(bytes.fromhex('0020002a022c0f0b'), fields, 'float get_Padding()') == 'return mPadding;'
    for bad in (body+b'\0', body.replace(b'\xb2',b'\xb3'), body.replace(b'\x38\x02\x0c',b'\x38\x02\x14')):
        with pytest.raises(ValueError):
            lift_numeric_accessor(bad, fields, 'void set_ItemIndex(int value)')


def test_nested_delegate_owner_and_compiler_backing_field_are_checked():
    from grea.recovery.unity_method_overlay import declarations, owner_names
    types = [
        dict(index=0, byvalTypeIndex=39, declaringIl2CppTypeIndex=-1, namespace='Game', name='Frames'),
        dict(index=1, byvalTypeIndex=75, declaringIl2CppTypeIndex=39, namespace='', name='<>c'),
    ]
    selected = owner_names(types, [0, 1])
    assert selected[1] == ('Game','Frames.<>c')
    dump = ('// Namespace: Game\npublic class Frames // TypeDefIndex: 0\n{\n'
            'private float <Height>k__BackingField; // 0x88\n}\n'
            '// Namespace: \nprivate sealed class Frames.<>c // TypeDefIndex: 1\n{\n'
            '// RVA: 0x65 Offset: 0x65\ninternal int <Sort>b__0(Sprite a, Sprite b) { }\n}\n')
    methods, fields = declarations(dump, selected)
    assert methods['Game.Frames.<>c',1,'internal int <Sort>b__0(Sprite a, Sprite b) { }'] == (101,0)
    assert fields['Game.Frames',0][136] == ('float','recoveredBacking_Height')
    with pytest.raises(ValueError, match='disagrees'):
        declarations(dump.replace('Frames.<>c','Other.<>c'), selected)
    types[0]['declaringIl2CppTypeIndex'] = 75
    with pytest.raises(ValueError, match='Cycle'):
        owner_names(types,[1])


def test_inventory_distinguishes_addressed_review_from_missing_slot(tmp_path):
    from grea.recovery.unity_method_overlay import inventory
    wasm,body,_,_ = fixture_module()
    at=wasm.index(section(10,bytes((1,len(body)))+body))
    wasm=wasm[:at]+section(9,bytes.fromhex('010041030b0100'))+wasm[at:]
    def pin(filename, data):
        (tmp_path/filename).write_bytes(data)
        return {'path':filename,'sha256':hashlib.sha256(data).hexdigest()}
    request=tmp_path/'request.json'
    spec=dict(metadata=pin('meta',fixture_metadata()),segments=[pin('module',wasm)],
              types=[dict(type='BattleCore.FP',typeIndex=0)])
    for slot,status in [('0x3','needs-review'),('0x4','unresolved')]:
        spec['dump']=pin('dump',f'// Namespace: BattleCore\npublic class FP // TypeDefIndex: 0\n{{\n// RVA: {slot} Offset: 0x3\npublic static FP op_Addition(FP x, FP y) {{ }}\n}}\n'.encode())
        request.write_text(json.dumps(spec));out=tmp_path/(slot+'.json')
        summary=inventory(request,out,include_body_bytes=True)
        assert summary['automatic']==0
        record=json.loads(out.read_text())['methods'][0]
        assert record['status']==status and record['token']=='0x06000001'
        if status=='needs-review':
            assert record['sha256']==hashlib.sha256(body).hexdigest()
            assert bytes.fromhex(record['bodyHex'])==body
            assert wasm[record['bodyOffset']:record['bodyOffset']+len(body)]==body
        else:
            assert 'sha256' not in record and 'bodyHex' not in record


def test_hidden_return_vector_copy_requires_both_words_and_exact_field():
    from grea.recovery.unity_method_overlay import lift_struct_getter
    body = bytes.fromhex('01017e2001280240ad2001280244ad42208684210320002003a736020020002003422088a73602040b')
    fields = {64: ('Vector2', 'size')}
    assert lift_struct_getter(body, fields, 'Vector2 get_Size()') == 'return size;'
    for invalid in (body + b'\x00', body.replace(b'\x28\x02\x44', b'\x28\x02\x48'),
                    body.replace(b'\x36\x02\x04', b'\x36\x02\x00')):
        with pytest.raises(ValueError):
            lift_struct_getter(invalid, fields, 'Vector2 get_Size()')
    with pytest.raises(ValueError):
        lift_struct_getter(body, {64: ('Color', 'tint')}, 'Vector2 get_Size()')


def test_color_getter_requires_four_words_in_destination_order():
    from grea.recovery.unity_method_overlay import lift_struct_getter
    body = bytes.fromhex(
        '01017e2001280210ad2001280214ad42208684210320002003a736020020002003422088a7360204'
        '2001280218ad200128021cad42208684210320002003a736020820002003422088a736020c0b'
    )
    fields = {16: ('Color', 'tint')}
    assert lift_struct_getter(body, fields, 'Color get_Tint()') == 'return tint;'
    for invalid in (body[:43] + b'\x0b', body.replace(b'\x36\x02\x0c', b'\x36\x02\x08')):
        with pytest.raises(ValueError):
            lift_struct_getter(invalid, fields, 'Color get_Tint()')
    with pytest.raises(ValueError):
        lift_struct_getter(body, fields, 'static Color get_Tint()')


def test_exclude_overlays_deduplicates_and_refuses_changed_source_or_body(tmp_path):
    from grea.recovery.unity_method_overlay import _exclude_overlays
    pins = dict(metadata={'sha256':'m'}, dump={'sha256':'d'}, segments=[{'sha256':'w'}])
    record = dict(type='C',typeIndex=1,metadataMethodIndex=8,token='tok',signature='void F()',
                  slot=4,segmentSha256='w',functionIndex=5,sha256='body')
    spec = dict(**pins, types=[{'typeIndex':1}])
    overlay = dict(**pins, scripts=[dict(type='C',typeIndex=1,methods=[dict(record)])])
    file = tmp_path/'prior.json'
    file.write_text(json.dumps(overlay))
    other = dict(record, metadataMethodIndex=9)
    assert _exclude_overlays(spec, [record,other], [file,file]) == [other]
    overlay['scripts'][0]['methods'][0]['sha256']='wrong'
    file.write_text(json.dumps(overlay))
    with pytest.raises(ValueError, match='identity differs'):
        _exclude_overlays(spec,[record],[file])
    file.write_text(json.dumps(dict(overlay,segments=[])))
    with pytest.raises(ValueError, match='different source'):
        _exclude_overlays(spec,[record],[file])


def test_static_float_expression_requires_one_result_and_no_side_effects():
    from grea.recovery.unity_method_overlay import lift_float_expression
    body = bytes.fromhex('0020012000932002942002942000920b')
    sig = 'public static float Curve(float start, float end, float ratio) { }'
    assert lift_float_expression(body, {}, sig) == 'return ((((end - start) * ratio) * ratio) + start);'
    for invalid in (body[:-1], body + b'\x00', body.replace(b'\x20\x02',b'\x20\x03'),
                    bytes.fromhex('00200020010b'), bytes.fromhex('00200010010b'),
                    bytes.fromhex('00200020013802000b'), bytes.fromhex('00920b')):
        with pytest.raises(ValueError):
            lift_float_expression(invalid, {}, sig)
    with pytest.raises(ValueError):
        lift_float_expression(body, {}, sig.replace('static ', ''))


def test_native_signature_preserves_generic_arguments_and_ref_direction():
    from grea.recovery.unity_method_overlay import native_signature
    script = {'guid':'f'*32, 'type':'Game.Motion'}
    method = {'metadataMethodIndex':17, 'signature':
        'internal static Dictionary<int, string> Run(Action<Color, object> callback, '
        'ref Vector3 point, int[,] layout, string message = "two, words") { }'}
    row = native_signature(script, method)
    assert row['isStatic'] and row['index']==17 and row['name']=='Run'
    assert row['result']=='Dictionary<int,string>'
    assert row['parameters']==['Action<Color,object>','ref Vector3','int[,]','string']
    with pytest.raises(ValueError):
        native_signature(script,dict(method,signature='static Run { }'))


def test_native_signatures_extend_an_immutable_baseline_and_preflight_retries(tmp_path):
    from grea.recovery.unity_method_overlay import write_native_signatures
    first = dict(scriptGuid='b'*32, index=8, parameters=['Vector2'])
    second = dict(first,index=9,parameters=['Vector3'])
    write_native_signatures(tmp_path,[first])
    baseline = tmp_path/'expected-method-signatures.json'
    original = baseline.read_bytes()
    write_native_signatures(tmp_path,[first,second,second])
    write_native_signatures(tmp_path,[second])
    files = list((tmp_path/'expected-method-signatures.d').glob('*.json'))
    assert len(files)==1 and json.loads(files[0].read_text())['methods']==[second]
    with pytest.raises(ValueError,match='Conflicting'):
        write_native_signatures(tmp_path,[dict(first,index=10),dict(second,parameters=['int'])])
    assert list((tmp_path/'expected-method-signatures.d').glob('*.json'))==files
    with pytest.raises(ValueError,match='Conflicting'):
        write_native_signatures(tmp_path,[dict(first,parameters=['string'])])
    assert baseline.read_bytes()==original
    baseline.unlink()
    with pytest.raises(ValueError,match='Missing baseline'):
        write_native_signatures(tmp_path,[first])

def test_void_noop_requires_complete_body_and_void_declaration():
    from grea.recovery.unity_method_overlay import lift_void_noop
    signature = 'public override void ModifyMesh(VertexHelper vh) { }'
    for body in (b'\x00\x0b', b'\x00\x01\x01\x0b'):
        assert lift_void_noop(body, {}, signature) == 'return;'
    for body in (b'', b'\x00\x01', b'\x00\x10\x01\x0b', b'\x00\x0b\x01'):
        with pytest.raises(ValueError):
            lift_void_noop(body, {}, signature)
    for declaration in ('public void .ctor() { }', 'public void Read(out int x) { }', 'public int Read() { }', 'void Read'):
        with pytest.raises(ValueError):
            lift_void_noop(b'\x00\x0b', {}, declaration)


def test_native_signature_preserves_unnamed_display_class_parameter():
    from grea.recovery.unity_method_overlay import native_signature
    signature = 'internal static int <Merge>g__Add|25_0(UIVertex vertex, ref Flip.<>c__DisplayClass25_0 ) { }'
    record = native_signature({'type': 'Flip', 'guid': '1' * 32}, {'signature': signature, 'metadataMethodIndex': 3})
    assert record['name'] == '<Merge>g__Add|25_0'
    assert record['parameters'] == ['UIVertex', 'ref Flip.<>c__DisplayClass25_0']
