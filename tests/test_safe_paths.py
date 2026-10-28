"""Portable path identity must remain independent of manifest ordering."""
import unittest
from grea.safe_paths import unique_paths


class UniquePathsTests(unittest.TestCase):
    def test_shared_directories_and_prefix_lookalikes_are_valid(self):
        names = ['Tree/a.txt', 'Tree/branch/b.txt', 'Tree/branch/c.txt',
                 'Treehouse/a.txt', 'Tree.txt', 'é/a.txt', 'é/b.txt']
        self.assertIsNone(unique_paths(iter(names)))
        self.assertIsNone(unique_paths(reversed(names)))

    def test_duplicates_aliases_and_file_directory_conflicts_in_both_orders(self):
        pairs = [
            ('same', 'same'), ('Name', 'name'), ('é', 'e\u0301'),
            ('parent', 'parent/child'), ('parent', 'parent/branch/child'),
            ('Root/Parent', 'root/parent/child'),
            ('Directory/first', 'directory/second'),
            ('Root/Branch/first', 'Root/branch/second'),
            ('é/first', 'e\u0301/second'), ('Straße/first', 'STRASSE/second'),
        ]
        for first, second in pairs:
            for names in ((first, second), (second, first)):
                with self.subTest(names=names), self.assertRaises(ValueError):
                    unique_paths(iter(names))

    def test_conflict_does_not_consume_later_generator_entries(self):
        consumed = []
        def names():
            for name in ('a/b', 'a', 'unrelated'):
                consumed.append(name)
                yield name
        with self.assertRaisesRegex(ValueError, 'File/directory output conflict'):
            unique_paths(names())
        self.assertEqual(consumed, ['a/b', 'a'])
