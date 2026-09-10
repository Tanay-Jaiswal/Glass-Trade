"""
main.py — Glass FastAPI application entry point.

Startup sequence:
  1. Load .env if present.
  2. Prompt for GLIMPSE_API_KEY if not set (per user request — terminal prompt on startup).
  3. Initialise SQLite database.
  4. Mount all route modules.
  5. Serve.
"""

import getpass
import logging
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import database as db
from routes.markets import router as markets_router, batches_router
from routes.calibration import router as calibration_router
from routes.portfolio import router as portfolio_router
from routes.trader import router as trader_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("glass")

# Load .env from cwd or parent dir if present
load_dotenv()
_parent_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
if os.path.exists(_parent_env):
    load_dotenv(_parent_env)

def _ensure_api_key() -> None:
    """
    If GLIMPSE_API_KEY is not set in the environment, prompt for it in the terminal
    if running in an interactive TTY. If running non-interactively or in the background,
    proceed without hanging.
    """
    if os.getenv("GLIMPSE_API_KEY"):
        logger.info("GLIMPSE_API_KEY loaded from environment.")
        return

    is_interactive = hasattr(sys.stdin, "isatty") and sys.stdin.isatty()
    if not is_interactive:
        logger.warning(
            "GLIMPSE_API_KEY is not set and terminal is non-interactive. "
            "Running without API key (live sync will return 503 until set in .env)."
        )
        return

    print("\n" + "=" * 60)
    print("  Glass — Calibration Engine for Glimpse Markets")
    print("=" * 60)
    print("\nGLIMPSE_API_KEY is not set.")
    print("You can find your API key at: https://glimpse.markets/settings")
    print("(Or add it to a .env file — see .env.example)\n")

    try:
        key = getpass.getpass("Enter your Glimpse API key: ").strip()
    except (EOFError, KeyboardInterrupt, Exception):
        print("\nNo API key provided. Some endpoints will return 503.")
        return

    if key:
        os.environ["GLIMPSE_API_KEY"] = key
        logger.info("GLIMPSE_API_KEY set from terminal prompt.")
    else:
        print("Empty key — some endpoints will return 503.")


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_api_key()
    db.init_db()
    logger.info("Glass backend ready. Docs at http://localhost:8000/docs")
    yield
    logger.info("Glass backend shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Glass — Glimpse Calibration & Conviction Engine",
    description=(
        "Calibration, conviction scoring, and trade execution engine for Glimpse prediction markets. "
        "Layer 1: Brier scores & reliability diagrams. "
        "Layer 2: Live signal scoring. "
        "Layer 3: Risk-gated trade execution."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(batches_router)
app.include_router(markets_router)
app.include_router(calibration_router)
app.include_router(portfolio_router)
app.include_router(trader_router)


@app.get("/api/health")
async def health():
    """Health check."""
    key = os.getenv("GLIMPSE_API_KEY", "")
    api_key_set = bool(key and key != "paste_your_key_here")
    db_path = os.getenv("DB_PATH", "glass.db")
    return {
        "status": "ok",
        "api_key_configured": api_key_set,
        "db_path": db_path,
        "demo_mode": not api_key_set,
    }


@app.post("/api/settings/key")
async def save_api_key(body: dict):
    """Save or update the Glimpse API key."""
    key = body.get("api_key", "").strip()
    if not key:
        return {"success": False, "message": "API key cannot be empty."}
    os.environ["GLIMPSE_API_KEY"] = key
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"GLIMPSE_API_KEY={key}\nDB_PATH=glass.db\nMAX_RESOLVED_PAGES=20\n")
        logger.info("Saved GLIMPSE_API_KEY to %s", env_path)
    except Exception as exc:
        logger.warning("Could not persist key to .env: %s", exc)

    return {"success": True, "api_key_configured": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
