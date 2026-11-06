"""Bounded offline native audio decoding for explicitly supported Cocos M4A AudioClips."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
try:
    import resource
except ImportError:  # pragma: no cover - exercised only on non-POSIX hosts
    resource = None


MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
MAX_TIMEOUT_SECONDS = 120.0
MAX_PROVIDER_BYTES = 256 * 1024 * 1024
VERSION_OUTPUT_BYTES = 4096


class AudioDecodeError(ValueError):
    """A stable, user-facing native-audio diagnostic."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _sha_file(path: Path, *, max_bytes: int = MAX_PROVIDER_BYTES) -> str:
    digest = hashlib.sha256()
    total = 0
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            total += len(chunk)
            if total > max_bytes:
                raise AudioDecodeError('AUDIO_PROVIDER_INVALID', 'ffmpeg binary exceeded its hash byte budget')
            digest.update(chunk)
    return digest.hexdigest()


def _file_size_limit(limit: int):
    """Return a child-only file-size limit used for bounded ffmpeg output files."""
    def apply():
        if resource is None:
            return
        soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
        ceiling = hard if hard != resource.RLIM_INFINITY else limit
        bounded = min(limit, ceiling)
        resource.setrlimit(resource.RLIMIT_FSIZE, (bounded, hard))
    return apply


def _child_isolation(limit: int | None = None) -> dict:
    if os.name == 'posix':
        return {'start_new_session': True,
                'preexec_fn': _file_size_limit(limit) if limit is not None else None}
    return {'creationflags': getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)}


def _kill_child(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        process.wait()
        return
    if os.name == 'posix':
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, AttributeError):
            try:
                process.kill()
            except ProcessLookupError:
                pass
    else:
        process.kill()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _bounded_version(executable: Path, *, timeout: float = 5.0) -> str:
    with tempfile.TemporaryFile() as output:
        try:
            process = subprocess.Popen(
                [str(executable), '-version'], stdin=subprocess.DEVNULL, stdout=output,
                stderr=subprocess.DEVNULL, close_fds=True,
                **_child_isolation(VERSION_OUTPUT_BYTES),
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise AudioDecodeError('AUDIO_PROVIDER_INVALID', 'ffmpeg version probe could not start') from error
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            _kill_child(process)
            raise AudioDecodeError('AUDIO_PROVIDER_TIMEOUT', 'ffmpeg version probe exceeded its time limit') from error
        output_size = os.fstat(output.fileno()).st_size
        if output_size <= 0 or output_size > VERSION_OUTPUT_BYTES:
            raise AudioDecodeError('AUDIO_PROVIDER_INVALID', 'ffmpeg returned no bounded version identity')
        output.seek(0)
        first_line = output.readline(512).decode('utf-8', errors='replace').strip()
    if process.returncode != 0 or not first_line.startswith('ffmpeg version '):
        raise AudioDecodeError('AUDIO_PROVIDER_INVALID', 'Selected executable did not identify as ffmpeg')
    return first_line


def provider_identity(provider: str | os.PathLike | None = None) -> dict:
    """Resolve the optional local ffmpeg provider and pin its exact executable bytes."""
    candidate = str(provider) if provider is not None else shutil.which('ffmpeg')
    if not candidate:
        raise AudioDecodeError('AUDIO_DECODER_MISSING', 'ffmpeg was not found on PATH; M4A source is retained without a target WAV')
    path = Path(candidate).expanduser()
    try:
        path = path.resolve(strict=True)
        stat = path.stat()
    except OSError as error:
        raise AudioDecodeError('AUDIO_DECODER_MISSING', 'Selected ffmpeg executable is unavailable') from error
    if not path.is_file() or not os.access(path, os.X_OK) or stat.st_size <= 0 or stat.st_size > MAX_PROVIDER_BYTES:
        raise AudioDecodeError('AUDIO_PROVIDER_INVALID', 'Selected ffmpeg executable is not a bounded executable file')
    try:
        version = _bounded_version(path)
        binary_sha = _sha_file(path)
        final_size = path.stat().st_size
    except OSError as error:
        raise AudioDecodeError('AUDIO_PROVIDER_INVALID', 'Selected ffmpeg executable changed or became unreadable') from error
    if final_size != stat.st_size or final_size > MAX_PROVIDER_BYTES:
        raise AudioDecodeError('AUDIO_PROVIDER_INVALID', 'Selected ffmpeg executable changed during identity pinning')
    return {'path': str(path), 'version': version, 'sha256': binary_sha, 'bytes': stat.st_size}


def validate_pcm_wav(raw: bytes, *, max_bytes: int = MAX_OUTPUT_BYTES) -> dict:
    """Validate a strict RIFF/WAVE PCM16 output and return its measured stream shape."""
    if not isinstance(raw, bytes) or len(raw) < 44 or len(raw) > max_bytes:
        raise AudioDecodeError('AUDIO_INVALID_WAV', 'Decoder output is outside the valid WAV byte budget')
    if raw[:4] != b'RIFF' or raw[8:12] != b'WAVE':
        raise AudioDecodeError('AUDIO_INVALID_WAV', 'Decoder output is not a RIFF/WAVE file')
    declared_size = int.from_bytes(raw[4:8], 'little') + 8
    if declared_size != len(raw):
        raise AudioDecodeError('AUDIO_INVALID_WAV', 'WAV RIFF length does not match output bytes')
    offset = 12
    fmt = None
    data_size = None
    chunks = 0
    while offset + 8 <= len(raw):
        chunks += 1
        if chunks > 8192:
            raise AudioDecodeError('AUDIO_INVALID_WAV', 'WAV contains too many chunks for the structural budget')
        tag = raw[offset:offset + 4]
        size = int.from_bytes(raw[offset + 4:offset + 8], 'little')
        chunk_start = offset + 8
        chunk_end = chunk_start + size
        padded_end = chunk_end + (size & 1)
        if chunk_end > len(raw) or padded_end > len(raw):
            raise AudioDecodeError('AUDIO_INVALID_WAV', 'WAV chunk exceeds the declared file bounds')
        if tag == b'fmt ':
            if fmt is not None or size < 16:
                raise AudioDecodeError('AUDIO_INVALID_WAV', 'WAV format chunk is missing, duplicate, or incomplete')
            fmt = raw[chunk_start:chunk_start + 16]
        elif tag == b'data':
            if data_size is not None:
                raise AudioDecodeError('AUDIO_INVALID_WAV', 'WAV has duplicate data chunks')
            data_size = size
        offset = padded_end
    if offset != len(raw) or fmt is None or data_size is None:
        raise AudioDecodeError('AUDIO_INVALID_WAV', 'WAV is missing a complete format or data chunk')
    format_tag = int.from_bytes(fmt[0:2], 'little')
    channels = int.from_bytes(fmt[2:4], 'little')
    sample_rate = int.from_bytes(fmt[4:8], 'little')
    byte_rate = int.from_bytes(fmt[8:12], 'little')
    block_align = int.from_bytes(fmt[12:14], 'little')
    bits_per_sample = int.from_bytes(fmt[14:16], 'little')
    if (format_tag != 1 or not 1 <= channels <= 8 or not 1 <= sample_rate <= 384000 or
            bits_per_sample != 16 or block_align != channels * 2 or byte_rate != sample_rate * block_align or
            data_size <= 0 or data_size % block_align):
        raise AudioDecodeError('AUDIO_INVALID_WAV', 'WAV must contain finite PCM16 audio with valid channel/rate alignment')
    frames = data_size // block_align
    return {'container': 'wav', 'codec': 'pcm_s16le', 'channels': channels,
            'sampleRateHz': sample_rate, 'bitsPerSample': bits_per_sample,
            'frames': frames, 'durationSeconds': frames / sample_rate}


def _validate_timeout(timeout_seconds: float) -> float:
    if type(timeout_seconds) not in (float, int) or not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise AudioDecodeError('AUDIO_INVALID_LIMIT', 'Audio decode timeout must be within the 120-second limit')
    return float(timeout_seconds)


def decode_m4a(raw: bytes, *, provider: str | os.PathLike | None = None,
               timeout_seconds: float = 30.0, max_input_bytes: int = MAX_INPUT_BYTES,
               max_output_bytes: int = MAX_OUTPUT_BYTES) -> tuple[bytes, dict]:
    """Decode one pinned M4A byte stream into bounded PCM16 WAV using local ffmpeg only."""
    if not isinstance(raw, bytes) or not raw:
        raise AudioDecodeError('AUDIO_INVALID_INPUT', 'Expected non-empty M4A bytes')
    if type(max_input_bytes) is not int or max_input_bytes <= 0 or max_input_bytes > MAX_INPUT_BYTES:
        raise AudioDecodeError('AUDIO_INVALID_LIMIT', 'Audio input budget must be within the 8 MiB limit')
    if len(raw) > max_input_bytes:
        raise AudioDecodeError('AUDIO_INPUT_EXCEEDED', 'M4A input exceeds the declared byte budget')
    if type(max_output_bytes) is not int or max_output_bytes < 44 or max_output_bytes > MAX_OUTPUT_BYTES:
        raise AudioDecodeError('AUDIO_INVALID_LIMIT', 'Audio output budget must be between 44 bytes and 16 MiB')
    timeout = _validate_timeout(timeout_seconds)
    provider_info = provider_identity(provider)
    input_sha = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory(prefix='monkey-m4a-') as tmp:
        root = Path(tmp)
        input_path, output_path = root / 'input.m4a', root / 'decoded.wav'
        input_path.write_bytes(raw)
        command = [provider_info['path'], '-nostdin', '-v', 'error', '-protocol_whitelist', 'file',
                   '-threads', '1', '-max_alloc', '67108864',
                   '-f', 'mov', '-i', str(input_path),
                   '-map', '0:a:0', '-map_metadata', '-1', '-vn', '-sn', '-dn',
                   '-c:a', 'pcm_s16le', '-f', 'wav', '-fs', str(max_output_bytes), str(output_path)]
        try:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, close_fds=True,
                                       **_child_isolation(max_output_bytes))
        except (OSError, subprocess.SubprocessError) as error:
            raise AudioDecodeError('AUDIO_DECODE_FAILED', 'ffmpeg could not start the bounded audio decode') from error
        try:
            deadline = time.monotonic() + timeout
            while True:
                returncode = process.poll()
                output_size = output_path.stat().st_size if output_path.exists() else 0
                if output_size >= max_output_bytes:
                    raise AudioDecodeError('AUDIO_OUTPUT_EXCEEDED', 'Decoded WAV reached the output byte budget')
                if returncode is not None:
                    break
                if time.monotonic() >= deadline:
                    raise AudioDecodeError('AUDIO_DECODE_TIMEOUT', 'ffmpeg exceeded the audio decode time limit')
                time.sleep(min(0.025, max(0.001, deadline - time.monotonic())))
        except OSError as error:
            raise AudioDecodeError('AUDIO_DECODE_FAILED', 'ffmpeg could not process the bounded M4A input') from error
        finally:
            _kill_child(process)
        output_size = output_path.stat().st_size if output_path.exists() else 0
        if output_size >= max_output_bytes:
            raise AudioDecodeError('AUDIO_OUTPUT_EXCEEDED', 'Decoded WAV reached the output byte budget')
        if returncode != 0 or output_size == 0:
            raise AudioDecodeError('AUDIO_DECODE_FAILED', 'ffmpeg could not decode the supplied M4A stream')
        if output_size > max_output_bytes:
            raise AudioDecodeError('AUDIO_OUTPUT_EXCEEDED', 'Decoded WAV exceeds the output byte budget')
        wav = output_path.read_bytes()
        shape = validate_pcm_wav(wav, max_bytes=max_output_bytes)
    evidence = dict(inputBytes=len(raw), inputSha256=input_sha,
                    provider=provider_info, outputBytes=len(wav),
                    outputSha256=hashlib.sha256(wav).hexdigest(), **shape)
    return wav, evidence
