"""Byte limits for package inventory and Unity import instructions."""
from .sources.compiled import ParseError

MIB = 1024**2
BATCH_INPUT = 2048 * MIB
PACKAGE_FILE = 128 * MIB
UNITY_INSTRUCTION = 256 * MIB


def record(kind, limit, measured=None, *, basis=None):
    result = dict(object=kind, effectiveLimit=limit, unit='bytes', effectiveLimitMiB=limit / MIB)
    if measured is not None:
        result['measured'] = measured
    if basis:
        result['basis'] = basis
    return result


def defaults():
    return [record(kind, limit) for kind, limit in (
        ('batchInput', BATCH_INPUT), ('packageFile', PACKAGE_FILE),
        ('unityImportInstruction', UNITY_INSTRUCTION))]


def enforce(kind, measured, limit, location, code, *, basis):
    if measured > limit:
        detail = record(kind, limit, measured, basis=basis)
        error = ParseError(code, str(location),
                           f'{kind} ({basis}): measured={measured} bytes, effectiveLimit={limit} bytes ({limit / MIB:g} MiB)')
        error.byte_budget = detail
        raise error


def inventory_usage(rows, limit):
    return [record('batchInput', limit, sum(row['bytes'] for row in rows), basis='cumulative expanded input'),
            record('packageFile', PACKAGE_FILE, max((row['bytes'] for row in rows), default=0), basis='largest expanded entry')]
