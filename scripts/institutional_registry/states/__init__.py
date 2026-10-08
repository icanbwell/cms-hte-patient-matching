"""Per-state assisted-living fetchers.

Every module here except `common` is one state: it defines STATE, SOURCE and
`fetch(session)` (see common.py), and may set BROKEN = "<reason>" when the source can't
currently be used. `state_modules()` discovers them, so adding a state is adding a file.
"""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import List


def state_modules() -> List[ModuleType]:
    """All state modules, sorted by state code."""
    modules = [
        importlib.import_module(f"{__name__}.{info.name}")
        for info in pkgutil.iter_modules(__path__)
        if info.name != "common"
    ]
    return sorted(modules, key=lambda m: m.STATE)
