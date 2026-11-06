import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from monkey import incremental as inc
from monkey.io import write_json, finish, read, load, sha
from monkey.sources.compiled import ParseError


def candidate(root, files, profile='cocos-3.8.8', namespace='fixture'):
    root.mkdir(parents=True)
    for name,content in files.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
    (root/'Analysis').mkdir(exist_ok=True)
    write_json(root/'Analysis/Mappings/source-map.json',dict(assets=[dict(path='assets/generated/a.txt',sourceId='original:42')],sourceRoots={}))
    finish(root,dict(schemaVersion=1,targetProfile=profile,namespace=namespace,diagnostics=[]))
    return root


class IncrementalTests(unittest.TestCase):
    def test_preview_apply_preserves_manual_and_retains_removed_files(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve()
            before=candidate(w/'outputs/old',{'assets/generated/a.txt':b'old','assets/generated/removed.txt':b'keep'})
            after=candidate(w/'outputs/new',{'assets/generated/a.txt':b'new','assets/generated/added.txt':b'add'})
            inc.register(before,w);expected=sha(read(before/'manifest.json'))
            (before/'assets/manual').mkdir();(before/'assets/manual/human.ts').write_text('human')
            d=inc.diff_data(before,after)
            self.assertEqual(d['counts'],dict(added=1,changed=1,removed=1,unchanged=1,manual=0))
            item=next(x for x in d['entries'] if x['path']=='assets/generated/a.txt')
            self.assertEqual(item['sourceIds'],['original:42']);self.assertNotEqual(item['beforeSha256'],item['afterSha256'])
            with self.assertRaises(ParseError):inc.apply(before,after,expected,w/'no-preview',w,True)
            inc.apply(before,after,expected,w/'dry',w)
            self.assertEqual(read(before/'assets/generated/a.txt'),b'old')
            result=inc.apply(before,after,expected,w/'applied',w,True,w/'dry/application.json')
            self.assertEqual(result['application'],'applied')
            self.assertEqual(read(before/'assets/generated/a.txt'),b'new')
            self.assertEqual(read(before/'assets/generated/removed.txt'),b'keep')
            self.assertEqual(read(before/'assets/manual/human.ts'),b'human')
            m=load(read(before/'manifest.json'))
            self.assertEqual(next(f['owner'] for f in m['files'] if f['path'].endswith('removed.txt')),'retained')
            self.assertEqual(inc.registry_load(w)['outputs'][str(before)]['manifestSha256'],sha(read(before/'manifest.json')))
            # A retained asset cannot later be overwritten by a new generation.
            third=candidate(w/'outputs/third',{'assets/generated/removed.txt':b'reintroduced'})
            self.assertTrue(any(c['reason']=='manual-or-retained-owner' for c in inc.diff_data(before,third)['manualConflicts']))

    def test_conflicts_stale_preview_and_unregistered_roots_never_write(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();a=candidate(w/'outputs/a',{'assets/generated/a.txt':b'a'});b=candidate(w/'outputs/b',{'assets/generated/a.txt':b'b'})
            expected=sha(read(a/'manifest.json'))
            with self.assertRaises(ParseError):inc.apply(a,b,expected,w/'none',w)
            inc.register(a,w);inc.apply(a,b,expected,w/'dry',w)
            (a/'assets/generated/a.txt').write_bytes(b'human')
            self.assertTrue(inc.diff_data(a,b)['manualConflicts'])
            blocked=inc.apply(a,b,expected,w/'blocked',w);self.assertEqual(blocked['application'],'blocked')
            with self.assertRaises(ParseError):inc.apply(a,b,expected,w/'write',w,True,w/'dry/application.json')
            self.assertEqual(read(a/'assets/generated/a.txt'),b'human')
            with self.assertRaises(ParseError):inc.apply(a,b,'0'*64,w/'wrong',w)
            outside=candidate(w/'game',{'assets/generated/a.txt':b'game'})
            with self.assertRaises(ParseError):inc.register(outside,w)

    def test_missing_added_collision_symlink_and_profile_boundaries(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();a=candidate(w/'outputs/a',{'assets/generated/a.txt':b'a'});b=candidate(w/'outputs/b',{'assets/generated/new.txt':b'new'})
            (a/'assets/generated/new.txt').write_bytes(b'human')
            self.assertTrue(any(c['reason']=='untracked-destination' for c in inc.diff_data(a,b)['manualConflicts']))
            (a/'assets/generated/a.txt').unlink()
            self.assertTrue(any(c['reason']=='modified-or-missing' for c in inc.diff_data(a,b)['manualConflicts']))
            (a/'assets/generated/new.txt').unlink();(a/'assets/generated/new.txt').symlink_to(b/'assets/generated/new.txt')
            with self.assertRaises(ParseError):inc.diff_data(a,b)
            different=candidate(w/'outputs/different',{'Assets/Generated/a.txt':b'x'},profile='unity-6000.6.2f1-ugui')
            with self.assertRaises(ParseError):inc.diff_data(b,different)

    def test_mid_apply_failure_rolls_back_and_records_recoverable_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();a=candidate(w/'outputs/a',{'assets/generated/a.txt':b'a','assets/generated/b.txt':b'b'})
            b=candidate(w/'outputs/b',{'assets/generated/a.txt':b'A','assets/generated/b.txt':b'B'})
            inc.register(a,w);expected=sha(read(a/'manifest.json'));inc.apply(a,b,expected,w/'dry',w)
            real_copy=inc.copy_verified;failed=False
            def interrupted(source,path,expected,size):
                nonlocal failed
                if path==a/'assets/generated/b.txt' and expected==sha(b'B') and not failed:
                    failed=True;raise OSError('simulated disk write failure')
                return real_copy(source,path,expected,size)
            with patch.object(inc,'copy_verified',interrupted):
                with self.assertRaises(OSError):inc.apply(a,b,expected,w/'write',w,True,w/'dry/application.json')
            self.assertEqual(read(a/'assets/generated/a.txt'),b'a');self.assertEqual(read(a/'assets/generated/b.txt'),b'b')
            self.assertEqual(sha(read(a/'manifest.json')),expected)
            journal=load(read(next((w/'.monkey/transactions').glob('*/journal.json'))))
            self.assertEqual(journal['state'],'rolled-back')
            self.assertEqual(inc.registry_load(w)['outputs'][str(a)]['manifestSha256'],expected)

    def test_manual_manifest_incoming_tamper_and_preview_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();a=candidate(w/'outputs/a',{'assets/generated/a.txt':b'a'});b=candidate(w/'outputs/b',{'assets/generated/a.txt':b'b'})
            inc.register(a,w);expected=sha(read(a/'manifest.json'));inc.apply(a,b,expected,w/'dry',w)
            preview=w/'dry/application.json';preview.write_bytes(b'{}')
            with self.assertRaises(ParseError):inc.apply(a,b,expected,w/'write',w,True,preview)
            (b/'assets/generated/a.txt').write_bytes(b'changed after export')
            self.assertTrue(any(c['reason'].startswith('incoming-') for c in inc.diff_data(a,b)['manualConflicts']))
            m=load(read(b/'manifest.json'));m['files'][0]['path']='assets/manual/bad.ts';write_json(b/'manifest.json',m)
            with self.assertRaises(ParseError):inc.diff_data(a,b)

    def test_unity_manual_scaffold_is_never_overwritten_or_adopted(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve()
            a=candidate(w/'outputs/a',{'Assets/Generated/a.txt':b'a','Assets/Manual/README.md':b'original'},profile='unity-6000.6.2f1-ugui')
            b=candidate(w/'outputs/b',{'Assets/Generated/a.txt':b'b','Assets/Manual/README.md':b'new template'},profile='unity-6000.6.2f1-ugui')
            inc.register(a,w);expected=sha(read(a/'manifest.json'))
            (a/'Assets/Manual/README.md').write_bytes(b'human work')
            inc.apply(a,b,expected,w/'dry',w)
            inc.apply(a,b,expected,w/'write',w,True,w/'dry/application.json')
            self.assertEqual(read(a/'Assets/Manual/README.md'),b'human work')
            self.assertEqual(read(a/'Assets/Generated/a.txt'),b'b')

    def test_noncanonical_paths_cannot_alias_manual_area(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();a=candidate(w/'outputs/a',{'assets/generated/a.txt':b'a'})
            m=load(read(a/'manifest.json'));m['files'][0]['path']='assets/generated/../manual/a.txt';write_json(a/'manifest.json',m)
            with self.assertRaises(ParseError) as caught:inc.snapshot(a)
            self.assertEqual(caught.exception.code,'UNSAFE_PATH')

    def test_declared_manual_owner_cannot_bypass_generated_integrity(self):
        with tempfile.TemporaryDirectory() as temp:
            w=Path(temp).resolve();a=candidate(w/'outputs/a',{'assets/generated/a.txt':b'a'})
            m=load(read(a/'manifest.json'));next(f for f in m['files'] if f['path']=='assets/generated/a.txt')['owner']='manual'
            write_json(a/'manifest.json',m)
            with self.assertRaises(ParseError) as caught:inc.register(a,w)
            self.assertEqual(caught.exception.code,'MANUAL_BOUNDARY')
