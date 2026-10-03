"""Tile - split a raw YouTube title into artist / title / extras.

    from Tile import parse_title

    parse_title("Marshmello - Alone (Official Music Video)")
    # {'artist': 'Marshmello', 'title': 'Alone', 'extras': ['Official Music Video']}

The engine lives in ``main.py`` at the repository root, and the wheel ships
that same file as ``Tile/main.py`` so it installs inside the package. Both
layouts are supported, so the checkout and an installed copy behave the same:

    checkout   Tile/__init__.py  +  ../main.py  +  ../assets/
    installed  Tile/__init__.py  +  Tile/main.py  +  Tile/assets/

Swap in your own data files with ``get_context``:

    from Tile import get_context, parse_title

    ctx = get_context("~/my-ignore.txt", "~/my-artists.txt")
    parse_title(raw, ctx)

A context is cached and reloaded whenever either file's mtime changes, so
editing ``assets/artist.txt`` takes effect immediately.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent

if (_HERE / "main.py").exists():
    from . import main as _engine            # installed wheel
else:
    sys.path.insert(0, str(_HERE.parent))    # repo checkout
    import main as _engine  # type: ignore[no-redef]
    # pretend the root file is the submodule, so `from Tile.main import ...`
    # works in the checkout exactly as it does once installed
    sys.modules[f"{__name__}.main"] = _engine

__version__ = "1.0.0"

# The engine module itself, reachable as `Tile.main` in both layouts: the real
# submodule once installed, the repo's root main.py in a checkout.
main = _engine

DEFAULT_IGNORE_FILE = _engine.DEFAULT_IGNORE_FILE
DEFAULT_ARTIST_FILE = _engine.DEFAULT_ARTIST_FILE
Context = _engine.Context
Segment = _engine.Segment
Token = _engine.Token
build_context = _engine.build_context
get_context = _engine.get_context
parse_title = _engine.parse_title

__all__ = [
    "DEFAULT_ARTIST_FILE",
    "DEFAULT_IGNORE_FILE",
    "Context",
    "Segment",
    "Token",
    "build_context",
    "get_context",
    "parse_title",
    "__version__",
]