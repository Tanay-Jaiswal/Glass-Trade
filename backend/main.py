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

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("glass")

# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------
load_dotenv()  # reads .env in cwd; silently no-ops if absent

def _ensure_api_key() -> None:
    """
    If GLIMPSE_API_KEY is not set in the environment, prompt for it in the terminal.
    The key is stored in the process environment for the session only — never persisted.
    """
    if os.getenv("GLIMPSE_API_KEY"):
        logger.info("GLIMPSE_API_KEY loaded from environment.")
        return

    print("\n" + "=" * 60)
    print("  Glass — Calibration Engine for Glimpse Markets")
    print("=" * 60)
    print("\nGLIMPSE_API_KEY is not set.")
    print("You can find your API key at: https://glimpse.markets/settings")
    print("(Or add it to a .env file in this directory — see .env.example)\n")

    try:
        key = getpass.getpass("Enter your Glimpse API key: ").strip()
    except (EOFError, KeyboardInterrupt):
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
    title="Glass — Glimpse Calibration Engine",
    description=(
        "Calibration and conviction engine for Glimpse Bitcoin prediction markets. "
        "Computes Brier scores and reliability diagrams from real resolved market data."
    ),
    version="1.0.0",
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


@app.get("/api/health")
async def health():
    """Health check."""
    api_key_set = bool(os.getenv("GLIMPSE_API_KEY"))
    db_path = os.getenv("DB_PATH", "glass.db")
    return {
        "status": "ok",
        "api_key_configured": api_key_set,
        "db_path": db_path,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
