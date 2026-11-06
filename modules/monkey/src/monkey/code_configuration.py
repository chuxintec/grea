"""Compatibility adapter for explicitly requested legacy data extensions.

Core code emission does not load a business configuration by project name.
The existing ``--configuration-table`` route calls this adapter explicitly;
provider code and business-specific contracts live under ``extensions``.
"""
from __future__ import annotations

from .code_profiles import configuration_provider


def _provider():
    return configuration_provider()


def validate_module_binding(namespace, modules, context) -> dict:
    """Return extension-owned binding metadata after exact source checks."""
    return _provider().validate_module_binding(namespace, modules, context)


def map_payload(*args, **kwargs) -> dict:
    return _provider().map_payload(*args, **kwargs)


def map_element_multi_order_pool(*args, **kwargs) -> dict:
    return _provider().map_element_multi_order_pool(*args, **kwargs)


def prepare_assets(*args, **kwargs) -> dict:
    return _provider().prepare_assets(*args, **kwargs)


def __getattr__(name):
    """Keep historical constant reads working without keeping pins in core."""
    if name in {
        'SOURCE_SHA256', 'TABLE_SHA256', 'REPRESENTATIVE_ROOT_DISH_ID',
        'MAX_TABLE_BYTES', 'MAX_SOURCE_BYTES', 'MAX_ROWS',
        'MAX_INGREDIENTS_PER_ROW', 'MAX_SAFE_INTEGER', 'SOURCE_SPANS',
    }:
        return getattr(_provider(), name)
    raise AttributeError(name)
