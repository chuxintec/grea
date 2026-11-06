import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from monkey.assets.audio import (MAX_INPUT_BYTES, AudioDecodeError, decode_m4a,
                                 provider_identity, validate_pcm_wav)
from monkey.io import finish, load, read, write_json
from monkey.normalize import normalize
from monkey.targets.unity import export as unity_export, plan as unity_plan


FFMPEG = '/opt/homebrew/bin/ffmpeg'


def make_m4a(path: Path) -> bytes:
    executable = FFMPEG if Path(FFMPEG).is_file() else 'ffmpeg'
    subprocess.run([executable, '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                    'sine=frequency=440:sample_rate=22050:duration=0.08',
                    '-c:a', 'aac', '-b:a', '64k', '-y', str(path)],
                   check=True, capture_output=True, timeout=15)
    return path.read_bytes()


def make_audio_manifest_stage(root: Path, raw: bytes) -> tuple[Path, Path]:
    source_root = root / 'source'
    source_root.mkdir()
    source = source_root / 'clip.m4a'
    source.write_bytes(raw)
    manifest = {
        'schemaVersion': 1, 'sourceProfile': 'cocos-2.4.15-bundle',
        'bundle': 'fixture', 'sourceRoot': str(source_root),
        'sourceRoots': {'fixture': str(source_root)},
        'inputs': [{'bundle': 'fixture', 'path': source.name,
                    'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}],
        'evidenceFiles': [], 'diagnostics': [], 'scopeMode': 'asset-selection',
        'assets': [{'sourceId': 'fixture:audio', 'bundle': 'fixture', 'kind': 'cc.AudioClip',
                    'native': source.name, 'logicalPath': 'Audio/sfx/clip',
                    'importPath': 'import/clip.json', 'references': [],
                    'document': {'root': 0, 'instances': [{'__type__': 'cc.AudioClip'}]}}],
    }
    stage = root / 'stage'
    stage.mkdir()
    write_json(stage / 'source-manifest.json', manifest)
    finish(stage, {'schemaVersion': 1, 'stage': 'inspect', 'diagnostics': []})
    return stage / 'source-manifest.json', source


class AudioDecoderTests(unittest.TestCase):
    def test_missing_optional_provider_is_an_explicit_diagnostic(self):
        with patch('monkey.assets.audio.shutil.which', return_value=None):
            with self.assertRaises(AudioDecodeError) as error:
                decode_m4a(b'not executed input')
        self.assertEqual(error.exception.code, 'AUDIO_DECODER_MISSING')

    def test_input_budget_is_checked_before_provider_discovery(self):
        with patch('monkey.assets.audio.shutil.which') as locate:
            with self.assertRaises(AudioDecodeError) as error:
                decode_m4a(b'12345', max_input_bytes=4)
        self.assertEqual(error.exception.code, 'AUDIO_INPUT_EXCEEDED')
        locate.assert_not_called()

    def test_caller_cannot_raise_input_budget_above_module_hard_cap(self):
        with patch('monkey.assets.audio.shutil.which') as locate:
            with self.assertRaises(AudioDecodeError) as error:
                decode_m4a(b'bounded', max_input_bytes=MAX_INPUT_BYTES + 1)
        self.assertEqual(error.exception.code, 'AUDIO_INVALID_LIMIT')
        locate.assert_not_called()

    def test_invalid_wav_is_rejected_without_accepting_a_fake_header(self):
        with self.assertRaises(AudioDecodeError) as error:
            validate_pcm_wav(b'RIFF' + (40).to_bytes(4, 'little') + b'WAVE' + b'0' * 32)
        self.assertEqual(error.exception.code, 'AUDIO_INVALID_WAV')

    def test_normalizer_keeps_source_m4a_and_marks_missing_provider_as_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            raw = b'original bounded M4A payload'
            manifest_path, source = make_audio_manifest_stage(root, raw)
            result = normalize(manifest_path, root / 'normalize',
                               audio_provider='/missing/local/ffmpeg')
            self.assertEqual(result['assets'], [])
            self.assertEqual(result['diagnostics'][0]['code'], 'AUDIO_DECODER_MISSING')
            self.assertEqual(result['diagnostics'][0]['severity'], 'error')
            self.assertEqual(source.read_bytes(), raw)
            self.assertFalse(any((root / 'normalize/assets').glob('*.wav')))

    @unittest.skipUnless(Path(FFMPEG).exists(), 'local Homebrew ffmpeg unavailable')
    def test_normalizer_keeps_corrupt_m4a_and_reports_failed_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            raw = b'corrupt m4a bytes; no decodable audio stream'
            manifest_path, source = make_audio_manifest_stage(root, raw)
            result = normalize(manifest_path, root / 'normalize', audio_provider=FFMPEG)
            self.assertEqual(result['assets'], [])
            self.assertTrue(any(row['code'] == 'AUDIO_DECODE_FAILED' and row['severity'] == 'error'
                                for row in result['diagnostics']))
            self.assertEqual(source.read_bytes(), raw)
            self.assertFalse(any((root / 'normalize/assets').glob('*.wav')))

    def test_decode_timeout_kills_the_owned_child_and_reports_failure(self):
        child = MagicMock()
        child.pid = 43210
        child.poll.return_value = None
        child.wait.return_value = -9
        with tempfile.TemporaryDirectory() as tmp:
            with patch('monkey.assets.audio.provider_identity', return_value={
                    'path': '/verified/ffmpeg', 'version': 'ffmpeg version fixture',
                    'sha256': 'a' * 64, 'bytes': 1}), \
                 patch('monkey.assets.audio.subprocess.Popen', return_value=child), \
                 patch('monkey.assets.audio.os.killpg') as kill_group:
                with self.assertRaises(AudioDecodeError) as error:
                    decode_m4a(b'bounded', timeout_seconds=0.01)
        self.assertEqual(error.exception.code, 'AUDIO_DECODE_TIMEOUT')
        kill_group.assert_called_once()

    def test_keyboard_interrupt_reaps_the_owned_child(self):
        child = MagicMock()
        child.pid = 43211
        child.poll.return_value = None
        child.wait.return_value = -9
        with patch('monkey.assets.audio.provider_identity', return_value={
                    'path': '/verified/ffmpeg', 'version': 'ffmpeg version fixture',
                    'sha256': 'a' * 64, 'bytes': 1}), \
             patch('monkey.assets.audio.subprocess.Popen', return_value=child), \
             patch('monkey.assets.audio.os.killpg') as kill_group, \
             patch('monkey.assets.audio.time.sleep', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                decode_m4a(b'bounded')
        kill_group.assert_called_once()
        child.wait.assert_called_once_with(timeout=2)

    @classmethod
    def setUpClass(cls):
        try:
            cls.ffmpeg = provider_identity()
        except AudioDecodeError:
            cls.ffmpeg = None

    @unittest.skipUnless(Path(FFMPEG).exists(), 'local Homebrew ffmpeg unavailable')
    def test_corrupt_m4a_and_truncated_output_are_not_reported_as_audio(self):
        with self.assertRaises(AudioDecodeError) as error:
            decode_m4a(b'not a valid ISO-BMFF audio file')
        self.assertEqual(error.exception.code, 'AUDIO_DECODE_FAILED')
        with tempfile.TemporaryDirectory() as tmp:
            encoded = make_m4a(Path(tmp) / 'fixture.m4a')
            with patch('monkey.assets.audio.resource', None):
                with self.assertRaises(AudioDecodeError) as error:
                    decode_m4a(encoded, max_output_bytes=128)
        self.assertEqual(error.exception.code, 'AUDIO_OUTPUT_EXCEEDED')

    @unittest.skipUnless(Path(FFMPEG).exists(), 'local Homebrew ffmpeg unavailable')
    def test_public_normalize_plan_export_emits_a_provenance_bound_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source_root = root / 'source'
            source_root.mkdir()
            source = source_root / 'fireworks.m4a'
            m4a = make_m4a(source)
            source_id = 'miniGameRes:63310199-382b-5e30-b8da-9ba0daf2d48a'
            manifest = {
                'schemaVersion': 1, 'sourceProfile': 'cocos-2.4.15-bundle',
                'bundle': 'miniGameRes', 'sourceRoot': str(source_root),
                'sourceRoots': {'miniGameRes': str(source_root)},
                'inputs': [{'bundle': 'miniGameRes', 'path': source.name,
                            'bytes': len(m4a), 'sha256': hashlib.sha256(m4a).hexdigest()}],
                'evidenceFiles': [], 'diagnostics': [], 'scopeMode': 'asset-selection',
                'assets': [{'sourceId': source_id, 'bundle': 'miniGameRes', 'kind': 'cc.AudioClip',
                            'native': source.name, 'logicalPath': 'Texture/garden/resources/audio/fireworks',
                            'importPath': 'import/0b/0b12f6c70.fe500.json', 'references': [],
                            'document': {'root': 0, 'instances': [
                                {'__type__': 'cc.AudioClip', '_name': 'fireworks', '_native': '.m4a',
                                 'duration': 2.742}]}}],
            }
            manifest_stage = root / 'source-manifest-stage'
            manifest_stage.mkdir()
            write_json(manifest_stage / 'source-manifest.json', manifest)
            finish(manifest_stage, {'schemaVersion': 1, 'stage': 'inspect', 'diagnostics': []})

            normalized = normalize(manifest_stage / 'source-manifest.json', root / 'normalize')
            self.assertEqual(len(normalized['assets']), 1)
            asset = normalized['assets'][0]
            self.assertEqual(asset['kind'], 'cc.AudioClip')
            self.assertEqual(asset['audioDecode']['inputSha256'], hashlib.sha256(m4a).hexdigest())
            self.assertEqual(asset['audioDecode']['inputBytes'], len(m4a))
            self.assertGreater(asset['audioDecode']['frames'], 0)
            self.assertEqual(asset['audioDecode']['container'], 'wav')

            plan = unity_plan(root / 'normalize' / 'ir.json', 'AudioFixture', root / 'plan')
            planned = next(row for row in plan['assets'] if row['id'] == source_id)
            self.assertEqual(planned['kind'], 'cc.AudioClip')
            self.assertEqual(Path(planned['path']).suffix, '.wav')
            candidate = unity_export(root / 'plan' / 'plan.json', root / 'candidate')
            exported = root / 'candidate' / planned['path']
            self.assertTrue(exported.is_file())
            self.assertEqual(hashlib.sha256(exported.read_bytes()).hexdigest(),
                             asset['audioDecode']['outputSha256'])
            output_manifest = load(read(root / 'candidate' / 'manifest.json'))
            self.assertTrue(any(row['path'] == planned['path'] and row['sha256'] == asset['audioDecode']['outputSha256']
                                for row in output_manifest['files']))


if __name__ == '__main__':
    unittest.main()
