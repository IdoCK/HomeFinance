"""Resolve filesystem paths consistently in a dev checkout and in a frozen exe.

PyInstaller unpacks the app into a temporary folder at runtime and points
``__file__`` there, so the old ``Path(__file__).parent.parent`` trick would put
the database in a temp dir that's wiped on exit. These helpers give two stable
anchors instead:

* ``bundle_dir()`` -- read-only resources shipped *with* the app (web/dist, docs).
  Dev: the project root. Frozen: PyInstaller's extraction dir (``sys._MEIPASS``).
* ``data_dir()``   -- the writable home for finance.db. Dev: the project's
  ``data/`` folder. Frozen: a ``data/`` folder *next to the .exe*, so the user's
  data is portable and survives replacing the executable.
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    """True when running inside a PyInstaller-built executable."""
    return getattr(sys, "frozen", False)


def bundle_dir() -> Path:
    """Directory holding bundled, read-only resources (web/dist, docs)."""
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return _PROJECT_ROOT


def data_dir() -> Path:
    """Writable directory for the SQLite database. Not created here -- callers
    (init_db) mkdir it; keeping import side-effect-free matters for the tests
    that monkeypatch DB_PATH."""
    if is_frozen():
        return Path(sys.executable).resolve().parent / "data"
    return _PROJECT_ROOT / "data"
