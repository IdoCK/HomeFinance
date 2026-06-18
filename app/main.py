"""FastAPI layer over the existing finance engine. Thin: routers call modules/."""
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from modules import database as db
from app.api import overview, people, transactions

DIST_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"

health = APIRouter()


@health.get("/health")
def health_check():
    return {"status": "ok"}


def create_app() -> FastAPI:
    db.init_db()
    app = FastAPI(title="HomeFinance API")

    # Dev only: the Vite dev server runs on :5173 and calls the API on :8000.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health, prefix="/api")
    app.include_router(people.router, prefix="/api")
    app.include_router(transactions.router, prefix="/api")
    app.include_router(overview.router, prefix="/api")

    # Production: serve the built SPA from web/dist when it exists. Absent in dev.
    if DIST_DIR.is_dir():
        app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="spa")

    return app


# uvicorn imports this module-level `app` (target "app.main:app"). Note: importing
# app.main therefore calls create_app() -> db.init_db() against the real data/finance.db.
# Tests must monkeypatch database.DB_PATH (and reload this module) BEFORE importing it.
app = create_app()
