"""Single authority for generated project paths and names: monkey-project/2.0.0 (docs/PROJECT-SPEC.md)."""
from .standard import VERSION,locate
from .allocate import LayoutPlanner
from .overrides import load_overrides
