from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .auth import hash_password
from .database import Base, SessionLocal, engine
from .models import User
from .routers import ai, analysis, auth_routes, indicators, markets, news, portfolio, research, scan, stocks, thesis, tracking

def _heal_legacy_tables() -> None:
    """Older experiment runs created 'watchlist'/'alerts' with different
    columns (created_at / condition). create_all won't alter tables, so a
    stale swinglens.db yields 500s. These are new low-value tables - detect
    the mismatch and rebuild them cleanly."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    expected = {"watchlist": "added_at", "alerts": "direction"}
    with engine.begin() as conn:
        for table, required_col in expected.items():
            if table in insp.get_table_names():
                cols = {c["name"] for c in insp.get_columns(table)}
                if required_col not in cols:
                    conn.execute(text(f"DROP TABLE {table}"))


_heal_legacy_tables()
Base.metadata.create_all(bind=engine)


def seed_demo_user() -> None:
    """DEMO_MODE: make sure the one-click demo account exists."""
    if not config.DEMO_MODE:
        return
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == config.DEMO_EMAIL).first():
            db.add(User(username="demo_trader", email=config.DEMO_EMAIL,
                        password_hash=hash_password(config.DEMO_PASSWORD)))
            db.commit()
    finally:
        db.close()


seed_demo_user()

app = FastAPI(
    title="SwingLens API",
    version="0.2.0",
    description="Phase 2 — the Analyst Engine: annotated setups, verified narration.",
)

# Local development: the Vite dev server proxies /api to us, but we also
# allow direct browser calls from any LAN device. Tightened in the SaaS phase.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(stocks.router)
app.include_router(ai.router)
app.include_router(analysis.router)
app.include_router(indicators.router)
app.include_router(markets.router)
app.include_router(news.router)
app.include_router(scan.router)
app.include_router(portfolio.router)
app.include_router(tracking.router)
app.include_router(research.router)
app.include_router(thesis.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "SwingLens", "demo": config.DEMO_MODE}


# ---- Showcase mode: serve the built frontend from this same server -------
# If frontend/dist exists (Docker image / `npm run build`), the whole app is
# one origin on one port - deployable to any free host as a single service.
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_DIST / "index.html")
