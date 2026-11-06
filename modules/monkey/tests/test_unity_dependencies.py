import unittest
from monkey.unity_dependencies import closure
from monkey.sources.compiled import ParseError


def file(name,*dependencies):return dict(name=name,externals=[dict(path='archive:/'+d+'/'+d)for d in dependencies])


def fixture(specs):
    rows=[];files=[]
    for i,(digest,serialized)in enumerate(specs):
        source=dict(path='/explicit/'+str(i)+'.bundle',bytes=1,sha256=digest*64)
        files.append(source);rows.append(dict(status='indexed',source={k:source[k]for k in ('bytes','sha256')},files=serialized))
    return dict(containers=rows),dict(sourceManifestSha256='f'*64,files=files)


class DependencyClosureTests(unittest.TestCase):
    def test_transitive_cycle_uses_exact_names_and_returns_to_primary_without_pool_entry(self):
        primary=dict(source={'sha256':'a'*64},files=[file('CAB-a','CAB-b')])
        index,pool=fixture([('b',[file('CAB-b','CAB-c','CAB-a')]),('c',[file('CAB-c','CAB-b')]),('d',[file('unrelated')])])
        result=closure(primary,index,pool)
        self.assertEqual(result['status'],'resolved')
        self.assertEqual({r['sha256']for r in result['dependencies']},{'b'*64,'c'*64})
        self.assertFalse(result['sourceCodeExecuted']);self.assertEqual(result['lookupFiles'],3)

    def test_similar_name_is_missing_and_conflicting_exact_name_is_rejected(self):
        primary=dict(source={'sha256':'a'*64},files=[file('CAB-a','CAB-b')])
        index,pool=fixture([('b',[file('CAB-b-new')])])
        result=closure(primary,index,pool);self.assertEqual(result['status'],'partial');self.assertEqual(result['dependencies'],[])
        index,pool=fixture([('b',[file('CAB-b')]),('c',[file('CAB-b')])])
        with self.assertRaisesRegex(ParseError,'AMBIGUOUS'):closure(primary,index,pool)

    def test_only_byte_identical_aliases_are_equivalent_and_failed_index_is_not_skipped(self):
        primary=dict(source={'sha256':'a'*64},files=[file('CAB-a','CAB-b')])
        index,pool=fixture([('b',[file('CAB-b')]),('b',[file('CAB-b')])])
        result=closure(primary,index,pool);self.assertEqual(len(result['dependencies']),1)
        self.assertEqual(len(result['equivalentAliases']),1)
        index['containers'][1]['status']='failed'
        with self.assertRaisesRegex(ParseError,'INDEX'):closure(primary,index,pool)


if __name__=='__main__':unittest.main()
