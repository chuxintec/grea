import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from monkey.creator_readback_revision import RevisionError, select_current_revision


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class CreatorReadbackRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.readback_dir = self.root / 'Analysis/Readback'
        self.readback_dir.mkdir(parents=True)
        self.plan_path = self.root / 'extensions/monkey-import/import-plan.json'
        self.plan_path.parent.mkdir(parents=True)
        self.manifest_path = self.root / 'manifest.json'
        self.manifest_path.write_bytes(b'{"projectUuid":"project-1"}\n')
        self.plan_path.write_bytes(b'{"nodes":[]}\n')
        self.manifest_sha = digest(self.manifest_path.read_bytes())
        self.plan_sha = digest(self.plan_path.read_bytes())
        self.project_uuid = 'project-1'
        self.scene_uuid = 'scene-1'
        self.origin_path = 'Analysis/Readback/editor-readback.json'
        self.origin = {'projectUuid': self.project_uuid, 'sceneUuid': self.scene_uuid,
                       'manifestSha256': self.manifest_sha, 'creatorVersion': '3.8.8'}
        self.origin_raw = self._write_json(self.origin_path, self.origin)
        self.origin_sha = digest(self.origin_raw)

    def tearDown(self):
        self.temp.cleanup()

    def _write_json(self, relative: str, value: dict) -> bytes:
        raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return raw

    def _receipt(self, revision: int, previous_path: str, previous_sha: str,
                 *, manifest_sha=None, plan_sha=None, project_uuid=None, native_files=None) -> tuple[str, bytes]:
        path = f'Analysis/Readback/reopened-{revision}.json'
        metadata = {'schemaVersion': 1, 'revision': revision,
                    'previousReceiptPath': previous_path, 'previousReceiptSha256': previous_sha,
                    'originReceiptPath': self.origin_path, 'originReceiptSha256': self.origin_sha,
                    'manifestSha256': manifest_sha or self.manifest_sha,
                    'sourcePlanSha256': plan_sha or self.plan_sha,
                    'projectUuid': project_uuid or self.project_uuid, 'sceneUuid': self.scene_uuid,
                    'readSavedMethod': 'CreatorScene.readSaved'}
        receipt = {'projectUuid': project_uuid or self.project_uuid, 'sceneUuid': self.scene_uuid,
                   'manifestSha256': manifest_sha or self.manifest_sha,
                   'sourcePlanSha256': plan_sha or self.plan_sha, 'creatorVersion': '3.8.8',
                   'readbackRevision': metadata,
                   'nativeFiles': native_files if native_files is not None else [
                       {'path': 'assets/resources/Scenes/Preview/ContentPreview.scene',
                        'sha256': 'a' * 64}]}
        raw = self._write_json(path, receipt)
        return path, raw

    def _pointer(self, revision: int, receipt_path: str, receipt_raw: bytes,
                 previous_path: str, previous_sha: str, **overrides) -> None:
        pointer = {'schemaVersion': 1, 'kind': 'creator-reopen-readback-revision',
                   'revision': revision, 'readbackPath': receipt_path,
                   'readbackSha256': digest(receipt_raw),
                   'previousReceiptPath': previous_path,
                   'previousReceiptSha256': previous_sha,
                   'originReceiptPath': self.origin_path,
                   'originReceiptSha256': self.origin_sha,
                   'manifestSha256': self.manifest_sha,
                   'sourcePlanSha256': self.plan_sha,
                   'projectUuid': self.project_uuid, 'sceneUuid': self.scene_uuid}
        pointer.update(overrides)
        self._write_json('Analysis/Readback/current-revision.json', pointer)

    def select(self):
        return select_current_revision(self.root, self.manifest_sha, self.project_uuid,
                                       self.plan_sha, self.origin_path)

    def test_old_candidate_without_pointer_uses_legacy_path(self):
        self.assertIsNone(self.select())

    def test_valid_single_revision_is_selected_and_hash_bound(self):
        receipt_path, receipt_raw = self._receipt(1, self.origin_path, self.origin_sha)
        self._pointer(1, receipt_path, receipt_raw, self.origin_path, self.origin_sha)
        result = self.select()
        self.assertEqual(result['relativePath'], receipt_path)
        self.assertEqual(result['revision'], 1)
        self.assertEqual(result['raw'], receipt_raw)
        self.assertEqual(result['chainLength'], 1)

    def test_valid_revision_chain_links_to_immutable_origin(self):
        path1, raw1 = self._receipt(1, self.origin_path, self.origin_sha)
        path2, raw2 = self._receipt(2, path1, digest(raw1))
        self._pointer(2, path2, raw2, path1, digest(raw1))
        result = self.select()
        self.assertEqual(result['revision'], 2)
        self.assertEqual(result['chainLength'], 2)
        self.assertEqual(result['originReceiptSha256'], self.origin_sha)

    def test_bad_current_receipt_hash_fails_without_legacy_fallback(self):
        path, raw = self._receipt(1, self.origin_path, self.origin_sha)
        self._pointer(1, path, raw, self.origin_path, self.origin_sha,
                      readbackSha256='0' * 64)
        with self.assertRaisesRegex(RevisionError, 'RECEIPT_HASH_MISMATCH'):
            self.select()

    def test_broken_previous_hash_fails_chain_validation(self):
        path, raw = self._receipt(1, self.origin_path, self.origin_sha)
        self._pointer(1, path, raw, self.origin_path, '0' * 64)
        with self.assertRaisesRegex(RevisionError, 'POINTER_RECEIPT_MISMATCH|ORIGIN_LINK_MISMATCH'):
            self.select()

    def test_manifest_plan_and_project_identity_mismatch_fail(self):
        cases = [
            {'manifestSha256': '0' * 64},
            {'sourcePlanSha256': '0' * 64},
            {'projectUuid': 'other-project'},
        ]
        for override in cases:
            with self.subTest(override=override):
                path, raw = self._receipt(1, self.origin_path, self.origin_sha)
                self._pointer(1, path, raw, self.origin_path, self.origin_sha, **override)
                with self.assertRaises(RevisionError):
                    self.select()
                (self.readback_dir / 'current-revision.json').unlink()
                (self.readback_dir / path.rsplit('/', 1)[-1]).unlink()

    def test_revision_path_traversal_and_native_path_traversal_are_rejected(self):
        path, raw = self._receipt(1, self.origin_path, self.origin_sha)
        self._pointer(1, path, raw, self.origin_path, self.origin_sha,
                      readbackPath='Analysis/Readback/../../outside.json')
        with self.assertRaisesRegex(RevisionError, 'UNSAFE_PATH|PATH_NOT_ALLOWED'):
            self.select()

        (self.readback_dir / 'current-revision.json').unlink()
        self._write_json(path, {
            'projectUuid': self.project_uuid, 'sceneUuid': self.scene_uuid,
            'manifestSha256': self.manifest_sha, 'sourcePlanSha256': self.plan_sha,
            'readbackRevision': {'revision': 1, 'previousReceiptPath': self.origin_path,
                'previousReceiptSha256': self.origin_sha, 'originReceiptPath': self.origin_path,
                'originReceiptSha256': self.origin_sha, 'manifestSha256': self.manifest_sha,
                'sourcePlanSha256': self.plan_sha, 'projectUuid': self.project_uuid,
                'sceneUuid': self.scene_uuid, 'schemaVersion': 1,
                'readSavedMethod': 'CreatorScene.readSaved'},
            'nativeFiles': [{'path': '../outside', 'sha256': 'b' * 64}],
        })
        bad_raw = (self.root / path).read_bytes()
        self._pointer(1, path, bad_raw, self.origin_path, self.origin_sha)
        with self.assertRaisesRegex(RevisionError, 'NATIVE_FILE_PATH'):
            self.select()

    def test_symlink_receipt_cannot_escape_candidate(self):
        descriptor, temporary_path = tempfile.mkstemp()
        os.close(descriptor)
        outside = Path(temporary_path)
        try:
            path = 'Analysis/Readback/reopened-1.json'
            (self.root / path).symlink_to(outside)
            pointer = {'schemaVersion': 1, 'kind': 'creator-reopen-readback-revision',
                'revision': 1, 'readbackPath': path, 'readbackSha256': 'c' * 64,
                'previousReceiptPath': self.origin_path, 'previousReceiptSha256': self.origin_sha,
                'originReceiptPath': self.origin_path, 'originReceiptSha256': self.origin_sha,
                'manifestSha256': self.manifest_sha, 'sourcePlanSha256': self.plan_sha,
                'projectUuid': self.project_uuid, 'sceneUuid': self.scene_uuid}
            self._write_json('Analysis/Readback/current-revision.json', pointer)
            with self.assertRaisesRegex(RevisionError, 'PATH_ESCAPES|SYMLINK'):
                self.select()
        finally:
            outside.unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()
