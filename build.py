"""Build the standalone HomeFinance.exe.

Two steps:
  1. Build the React frontend  (npm install + npm run build  ->  web/dist)
  2. Bundle Python + backend + frontend into one exe via PyInstaller

Run:

    python build.py

Output: dist/HomeFinance.exe  (on Windows). Ship that single file; on first run
it creates a data/ folder beside itself for the database.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"


def _run(cmd, **kw):
    print(">", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, **kw)


def build_frontend() -> None:
    npm = shutil.which("npm")
    if npm is None:
        sys.exit("npm not found. Install Node.js (https://nodejs.org) and retry.")
    if not (WEB / "node_modules").is_dir():
        _run([npm, "install"], cwd=WEB)
    _run([npm, "run", "build"], cwd=WEB)
    if not (WEB / "dist" / "index.html").is_file():
        sys.exit("Frontend build did not produce web/dist/index.html -- aborting.")


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        _run([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build_exe() -> None:
    ensure_pyinstaller()
    _run([sys.executable, "-m", "PyInstaller", "--noconfirm", "HomeFinance.spec"], cwd=ROOT)
    name = "HomeFinance.exe" if sys.platform == "win32" else "HomeFinance"
    exe = ROOT / "dist" / name
    print(f"\nBuild complete: {exe}")
    print("Double-click it (or run it) to launch HomeFinance.")


if __name__ == "__main__":
    build_frontend()
    build_exe()
