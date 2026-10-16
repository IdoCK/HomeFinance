"""One-command launcher for HomeFinance.

Serves the API and the built React SPA together on a single port, then opens
your browser at it. This is the single entry point for everyone:

    python run_app.py        # run from a checkout
    HomeFinance.exe          # double-click the packaged build (same code path)

In a dev checkout, if the frontend hasn't been built yet (no web/dist), this
builds it once via npm before starting. The frozen .exe already ships web/dist,
so it starts immediately. Use run_api.py instead for the hot-reload dev workflow
(API on :8000 + `npm run dev` on :5173).
"""

import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

from modules.paths import bundle_dir, is_frozen

HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def _dist_exists() -> bool:
    return (bundle_dir() / "web" / "dist" / "index.html").is_file()


def ensure_frontend() -> None:
    """Build the SPA if it's missing. Dev-checkout only -- the frozen exe always
    ships web/dist, so this is a no-op there."""
    if is_frozen() or _dist_exists():
        return
    npm = shutil.which("npm")
    web = bundle_dir() / "web"
    if npm is None:
        sys.exit(
            "The frontend isn't built yet and npm wasn't found.\n"
            "Install Node.js (https://nodejs.org), then either:\n"
            "  cd web && npm install && npm run build   (then re-run this)\n"
            "  -- or run  python build.py  to produce the standalone exe."
        )
    if not (web / "node_modules").is_dir():
        print("Installing frontend dependencies (one-time, ~1-2 min)...")
        subprocess.run([npm, "install"], cwd=web, check=True)
    print("Building the frontend (one-time)...")
    subprocess.run([npm, "run", "build"], cwd=web, check=True)


def _choose_port(preferred: int) -> int:
    """Use the preferred port, or any free one if it's taken."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, preferred))
            return preferred
        except OSError:
            s.bind((HOST, 0))
            return s.getsockname()[1]


def _open_when_ready(url: str) -> None:
    """Poll the health endpoint, then open the browser once the server is up."""
    health = url + "/api/health"
    for _ in range(100):  # ~20s budget
        try:
            with urllib.request.urlopen(health, timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.2)
    webbrowser.open(url)


def main() -> None:
    ensure_frontend()
    port = _choose_port(DEFAULT_PORT)
    url = f"http://{HOST}:{port}"

    # Import AFTER the SPA is built: backend.main decides at import time whether
    # to mount the static files (web/dist) or fall back to the API docs.
    import uvicorn
    from backend.main import app

    print(f"\n  HomeFinance is running at {url}")
    print("  Your browser will open automatically. Press Ctrl+C here to stop.\n")
    threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
    uvicorn.run(app, host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
