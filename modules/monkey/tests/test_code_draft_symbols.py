import tempfile
import unittest
from pathlib import Path
from monkey.code_graph import draft_records
from monkey.code_draft_symbols import DraftSymbols
from monkey.code_drafts import _class_records,_identifier

SOURCE='''var Rules=(function(){function C(){}
C.cookware2Recipe=null;
C.foo=function(x){return x;};
C.Foo=function(x){return x+1;};
C._findRecipesWith=function(x){return C.cookware2Recipe;};
C.find=function(x){return this._findRecipesWith(x)+C.foo(x)+C.Foo(x);};
C.shadow=function(C){return C.foo(1);};
C.arrow=function(){return ()=>this.foo(1);};
C.normal=function(){return function(){return this.foo(1);};};
C.closure=function(v){var e=v;return [1].map(function(x){return e+x;});};
return C;})(); throw new Error("must never execute source");'''


def nodes(ast):
    stack=[ast]
    while stack:
        n=stack.pop()
        if isinstance(n,dict):
            yield n
            stack.extend(v for k,v in n.items()if not k.startswith('_draft')and isinstance(v,(dict,list)))
        elif isinstance(n,list):stack.extend(n)


class DraftSymbolTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'own.js';self.path.write_text(SOURCE)
        self.rows=list(draft_records(self.path));self.header=self.rows[0]
        _,_,names=_class_records(self.header);self.planner=DraftSymbols(self.header,names,_identifier)
        self.methods={r['method']['name']:r for r in self.rows if r.get('record')=='function' and r['kind']=='indexed_method'}

    def test_declarations_calls_fields_and_case_collision_share_exact_symbol_mapping(self):
        foo=self.planner.target_name(self.methods['foo']['method']);upper=self.planner.target_name(self.methods['Foo']['method'])
        self.assertNotEqual(foo,upper)
        row=self.methods['find'];self.planner.annotate(row['ast'],row['method'])
        mapped=[n['_draftMember']for n in nodes(row['ast'])if '_draftMember'in n]
        self.assertEqual({n['name']for n in mapped},{foo,upper,self.planner.target_name(self.methods['_findRecipesWith']['method'])})
        self.assertTrue(all(n['receiver']=='static_owner'for n in mapped))
        row=self.methods['_findRecipesWith'];self.planner.annotate(row['ast'],row['method'])
        field=next(n['_draftMember']for n in nodes(row['ast'])if '_draftMember'in n)
        self.assertEqual(field['name'],'Cookware2Recipe')

    def test_parameter_shadowing_and_normal_function_this_are_not_rewritten(self):
        row=self.methods['shadow'];self.planner.annotate(row['ast'],row['method'])
        member=next(n for n in nodes(row['ast'])if n.get('type')=='MemberExpression')
        self.assertNotIn('_draftMember',member);self.assertEqual(member['_draftUnresolvedMember']['reason'],'unknown_receiver_type')
        self.assertNotIn('_draftIdentifierTarget',member['object'])
        normal=self.methods['normal'];self.planner.annotate(normal['ast'],normal['method'])
        inner=next(n for n in nodes(normal['ast'])if n.get('type')=='ThisExpression')
        self.assertNotIn('thisOwnerBindingId',inner)
        arrow=self.methods['arrow'];self.planner.annotate(arrow['ast'],arrow['method'])
        member=next(n for n in nodes(arrow['ast'])if n.get('type')=='MemberExpression')
        self.assertIn('_draftMember',member)

    def test_nested_capture_identity_and_function_parent_survive(self):
        outer=self.methods['closure']['method'];inner=next(r for r in self.rows if r.get('record')=='function' and r['kind']=='auxiliary_function'and r['method'].get('parentFunctionId')==outer['id'])
        captures=self.planner.capture_parameters(inner['method']);capture=next(c for c in captures if c['sourceName']=='e')
        self.assertTrue(capture['targetName'].startswith('__capture_e_'))
        self.planner.annotate(inner['ast'],inner['method'],captures)
        refs=[n for n in nodes(inner['ast'])if n.get('type')=='Identifier'and n.get('bindingId')==capture['bindingId']]
        self.assertTrue(refs);self.assertTrue(all(n.get('_draftIdentifierTarget')==capture['targetName']for n in refs))
        self.assertEqual(inner['ast']['draftFunctionId'],inner['method']['id'])

    def test_mutated_constructor_binding_retains_uncertainty(self):
        bid=self.methods['foo']['method']['ownerBindingId'];header=dict(self.header,draftMutatedBindings=[bid])
        _,_,names=_class_records(header);planner=DraftSymbols(header,names,_identifier)
        row=self.methods['find'];planner.annotate(row['ast'],row['method'])
        members=[n for n in nodes(row['ast'])if n.get('type')=='MemberExpression']
        self.assertTrue(members);self.assertTrue(all('_draftMember'not in n for n in members))
        self.assertTrue(all(n['_draftUnresolvedMember']['reason']=='mutated_owner_binding'for n in members))

    def test_global_adapters_remain_available_but_shadowed_receivers_are_uncertain(self):
        for receiver in ('Math', 'cc'):
            prop='abs' if receiver=='Math' else 'v2'
            obj=dict(type='Identifier',name=receiver,bindingId=None)
            member=dict(type='MemberExpression',object=obj,property=dict(type='Identifier',name=prop),computed=False)
            self.planner.annotate(member,{})
            self.assertNotIn('_draftUnresolvedMember',member)
            obj['bindingId']='parameter:shadow'
            self.planner.annotate(member,{})
            self.assertEqual(member['_draftUnresolvedMember']['reason'],'unknown_receiver_type')

    def test_known_static_owner_keeps_unknown_member_name_and_diagnostic(self):
        bid=self.methods['foo']['method']['ownerBindingId']
        obj=dict(type='ThisExpression',thisOwnerBindingId=bid,thisStatic=True)
        member=dict(type='MemberExpression',object=obj,property=dict(type='Identifier',name='unknownGetter'),computed=False)
        self.planner.annotate(member,{})
        self.assertNotIn('_draftMember',member)
        self.assertEqual(member['_draftUnresolvedMember']['sourceName'],'unknownGetter')
        self.assertTrue(obj['_draftStaticThisOwner'])
