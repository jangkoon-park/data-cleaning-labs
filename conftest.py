"""Repository-wide test bootstrap.

Every lab is an independent folder that deliberately uses the same file names
(`src/clean.py`, `tests/test_clean.py`). That keeps the labs readable in
isolation, but it means a single pytest run over the whole repository would let
whichever `clean` module was imported first satisfy the import in every other
lab.

`load_lab_module` sidesteps the problem by loading a lab's module from its file
path under a unique name, so each test file gets its own code regardless of
collection order.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent


def load_lab_module(test_file: str | Path, module: str = "clean"):
    """Load `<lab>/src/<module>.py` for the lab that owns `test_file`."""
    lab_dir = Path(test_file).resolve().parents[1]
    alias = f"{lab_dir.name}__{module}"
    if alias in sys.modules:
        return sys.modules[alias]

    path = lab_dir / "src" / f"{module}.py"
    spec = importlib.util.spec_from_file_location(alias, path)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[alias] = loaded
    spec.loader.exec_module(loaded)
    return loaded
