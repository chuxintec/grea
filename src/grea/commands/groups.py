"""Compatibility names. Feature declarations are the sole ownership authority."""

from grea.features.catalog import MODULES, core_owners, helper_owners


def __getattr__(name):
    if name == "CORE_MODULE":
        return core_owners()
    if name == "HELPER_MODULE":
        return helper_owners()
    raise AttributeError(name)
