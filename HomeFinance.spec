# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build of the standalone HomeFinance app.

Produces a single dist/HomeFinance.exe that bundles Python, the FastAPI backend,
and the pre-built React SPA. Build with:

    python build.py            # builds the frontend first, then this spec
    # or, if web/dist already exists:
    pyinstaller HomeFinance.spec

The user's data (finance.db) is NOT bundled -- it's created in a data/ folder
next to the .exe at first run (see modules/paths.data_dir).
"""

from PyInstaller.utils.hooks import collect_submodules

# uvicorn loads its event-loop/protocol backends by dynamic import, so static
# analysis misses them -- pull every submodule in explicitly. Same for our own
# packages, whose routers are imported lazily.
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("backend")
    + collect_submodules("modules")
    + ["h11", "httptools", "websockets", "anyio", "email_validator"]
)

# Read-only resources shipped inside the exe (extracted to sys._MEIPASS at run).
datas = [
    ("web/dist", "web/dist"),
    ("docs/USER_GUIDE.html", "docs"),
]

# Exclusions. The app's only heavy runtime dep is pandas (+numpy) for analytics;
# everything below is either the legacy Streamlit stack or large ML/science
# libraries that merely happen to be installed globally. PyInstaller's static
# analysis follows optional/conditional `import torch`-style branches into them,
# which ballooned the exe to ~2.3 GB. Verified at runtime that importing the app
# loads NONE of these, so dropping them is safe.
excludes = [
    "streamlit", "altair", "pytest", "tkinter",
    "torch", "torchvision", "torchaudio",
    "scipy", "sklearn", "scikit_learn", "transformers",
    "sympy", "networkx", "numba", "tensorflow",
    "matplotlib", "IPython", "notebook", "jupyter",
    "pyarrow", "cv2",
]


a = Analysis(
    ["run_app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="HomeFinance",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # console=True keeps a terminal window that shows the URL and lets you Ctrl+C
    # to stop. Set to False for a windowless launch (errors become invisible).
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="homefinancelogo.ico",
)
