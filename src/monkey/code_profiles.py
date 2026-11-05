"""Generic, explicit loader for packaged source-contract extensions."""
from __future__ import annotations

import re
from importlib import import_module
from importlib.resources import files
from pathlib import PurePosixPath

from .io import encoded, load, read, safe, sha
from .sources.compiled import fail

_MAX_PROFILE_BYTES = 128 * 1024
_MAX_EXTENSION_BYTES = 128 * 1024
_MAX_SOURCE_BYTES = 16 * 1024 * 1024
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_EXTENSION_ID = re.compile(r'[a-z][a-z0-9_]{0,63}\Z')


def _extension_manifests():
    """Enumerate package metadata; extensions are inert until explicitly named."""
    try:
        extensions = files('monkey.extensions')
    except (ModuleNotFoundError, TypeError):
        return
    for extension in sorted((item for item in extensions.iterdir() if item.is_dir()), key=lambda item: item.name):
        extension_id = extension.name
        metadata_path = extension.joinpath('extension.json')
        if not metadata_path.is_file():
            continue
        if not _EXTENSION_ID.fullmatch(extension_id):
            fail('CODE_EXTENSION_ID', extension_id, 'Invalid packaged extension directory name')
        metadata_raw = metadata_path.read_bytes()
        if len(metadata_raw) > _MAX_EXTENSION_BYTES:
            fail('CODE_EXTENSION_BUDGET', extension_id, 'Extension metadata exceeds size limit')
        metadata = load(metadata_raw, max_nodes=20_000, max_depth=48)
        if encoded(metadata) != metadata_raw:
            fail('CODE_EXTENSION_CANONICAL', extension_id, 'Extension metadata is not canonical JSON')
        if metadata.get('schemaVersion') != 1 or metadata.get('extensionId') != extension_id:
            fail('CODE_EXTENSION_SCHEMA', extension_id, 'Extension identity or schema version mismatch')
        profiles = metadata.get('profiles', [])
        if not isinstance(profiles, list):
            fail('CODE_EXTENSION_SCHEMA', extension_id, 'Extension profiles must be a list')
        yield extension, metadata


def load_profile(profile_name: str, source_path) -> bytes:
    """Load an explicitly selected profile from an optional packaged extension.

    Neither a source project name nor its contents activate an extension. The
    caller must select the profile identifier; metadata and profile resource
    bytes are checked before the pinned source is read.
    """
    if not isinstance(profile_name, str) or not profile_name:
        fail('CODE_PROFILE_UNKNOWN', str(profile_name), 'Unknown packaged profile name')
    matches = []
    for extension, metadata in _extension_manifests():
        for row in metadata.get('profiles', []):
            if isinstance(row, dict) and row.get('profileName') == profile_name:
                matches.append((extension, metadata, row))
    if len(matches) != 1:
        fail('CODE_PROFILE_UNKNOWN', profile_name, 'Expected one explicitly selected packaged profile')
    extension, metadata, row = matches[0]
    if row.get('extensionId', metadata['extensionId']) != metadata['extensionId']:
        fail('CODE_PROFILE_SCHEMA', profile_name, 'Profile extension identity mismatch')
    resource_name = row.get('resource')
    if not isinstance(resource_name, str):
        fail('CODE_PROFILE_SCHEMA', profile_name, 'Profile resource path is missing')
    relative = PurePosixPath(resource_name)
    if relative.is_absolute() or not relative.parts or any(part in ('', '.', '..') for part in relative.parts) or '\\' in resource_name:
        fail('CODE_PROFILE_SCHEMA', profile_name, 'Profile resource path must remain within its extension')
    resource = extension.joinpath(*relative.parts)
    profile_raw = resource.read_bytes()
    if len(profile_raw) > _MAX_PROFILE_BYTES or type(row.get('bytes')) is not int or len(profile_raw) != row['bytes']:
        fail('CODE_PROFILE_BUDGET', profile_name, 'Packaged profile size differs from extension metadata or budget')
    expected_resource_sha = row.get('sha256')
    if not isinstance(expected_resource_sha, str) or not _HEX.fullmatch(expected_resource_sha) or sha(profile_raw) != expected_resource_sha:
        fail('CODE_PROFILE_RESOURCE_IDENTITY', profile_name, 'Packaged profile bytes differ from extension metadata')
    profile = load(profile_raw, max_nodes=20_000, max_depth=48)
    if encoded(profile) != profile_raw:
        fail('CODE_PROFILE_CANONICAL', profile_name, 'Packaged profile is not canonical JSON')
    if profile.get('profileName') != profile_name or profile.get('schemaVersion') != 1:
        fail('CODE_PROFILE_SCHEMA', profile_name, 'Profile identity or schema version mismatch')
    expected_source_sha = profile.get('sourceSha256')
    expected_source_bytes = profile.get('sourceBytes')
    if not isinstance(expected_source_sha, str) or not _HEX.fullmatch(expected_source_sha) or \
       type(expected_source_bytes) is not int or not 0 < expected_source_bytes <= _MAX_SOURCE_BYTES:
        fail('CODE_PROFILE_SCHEMA', profile_name, 'Invalid pinned source identity')
    source = safe(source_path)
    source_raw = read(source, max_bytes=_MAX_SOURCE_BYTES)
    if len(source_raw) != expected_source_bytes or sha(source_raw) != expected_source_sha:
        fail('CODE_PROFILE_SOURCE_IDENTITY', str(source), 'Source bytes do not match the selected exact profile')
    return profile_raw


def configuration_provider():
    """Resolve the sole declared legacy configuration provider on an opt-in call."""
    providers = []
    for extension, metadata in _extension_manifests():
        profile = metadata.get('configurationProfile')
        if profile is not None:
            if not isinstance(profile, dict) or not isinstance(profile.get('providerModule'), str):
                fail('CODE_CONFIG_EXTENSION_SCHEMA', metadata['extensionId'], 'Configuration provider metadata is invalid')
            providers.append((metadata['extensionId'], profile))
    if len(providers) != 1:
        fail('CODE_CONFIG_PROVIDER', 'configuration_table', 'Expected exactly one declared optional configuration provider')
    extension_id, profile = providers[0]
    module_name = profile['providerModule']
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', module_name):
        fail('CODE_CONFIG_EXTENSION_SCHEMA', extension_id, 'Provider module name is invalid')
    module = import_module(f'monkey.extensions.{extension_id}.{module_name}')
    if getattr(module, 'EXTENSION_ID', None) != extension_id:
        fail('CODE_CONFIG_PROVIDER', extension_id, 'Loaded provider identity differs from extension metadata')
    return module


def profile_capabilities() -> dict:
    """Report inert extension metadata without importing extension providers."""
    profiles = []
    extensions = []
    seen = set()
    for _, metadata in _extension_manifests():
        extension_id = metadata['extensionId']
        names = []
        for row in metadata.get('profiles', []):
            name = row.get('profileName') if isinstance(row, dict) else None
            if not isinstance(name, str) or not name or name in seen:
                fail('CODE_EXTENSION_SCHEMA', extension_id, 'Profile names must be unique, non-empty strings')
            seen.add(name)
            names.append(name)
        profiles.extend(names)
        config = metadata.get('configurationProfile')
        extensions.append({
            'extensionId': extension_id,
            'scope': metadata.get('scope', 'extension-specific'),
            'defaultEnabled': metadata.get('defaultEnabled') is True,
            'explicitOptIn': metadata.get('explicitOptIn') is True,
            'profileNames': sorted(names),
            'configurationProfileName': config.get('profileName') if isinstance(config, dict) else None,
        })
    return {'profiles': sorted(profiles), 'extensions': sorted(extensions, key=lambda row: row['extensionId'])}
