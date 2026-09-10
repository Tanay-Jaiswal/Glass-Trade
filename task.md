# Glass — Layer 1 Build Tasks

## Backend
- [x] Scaffold project structure (`glass/backend/`, `glass/frontend/`)
- [x] `requirements.txt`
- [x] `backend/database.py` — SQLite schema + helpers
- [x] `backend/api_client.py` — GlimpseClient with auth probe, retry, pagination
- [x] `backend/calibration.py` — implied_prob, bucketing, Brier score, insight generator
- [x] `backend/routes/markets.py`
- [x] `backend/routes/calibration.py`
- [x] `backend/routes/portfolio.py`
- [x] `backend/main.py` — FastAPI app, startup key prompt
- [x] `backend/tests/test_calibration.py` — 27 unit tests (all passed!)

## Frontend
- [x] Init Vite + React project in `glass/frontend/`
- [x] `src/api.js` — fetch helpers
- [x] `src/components/CalibrationChart.jsx` — Recharts reliability diagram
- [x] `src/components/BrierScore.jsx`
- [x] `src/components/MarketTable.jsx`
- [x] `src/components/InsightCard.jsx`
- [x] `src/components/ErrorState.jsx`
- [x] `src/components/LoadingSpinner.jsx`
- [x] `src/App.jsx` — dark glassmorphism layout
- [x] `src/index.css` — design system
- [x] Verified frontend build (`npm run build`)

## Config & Documentation
- [x] `.env.example`
- [x] `README.md` (comprehensive hackathon documentation)

## Verification
- [x] Run unit tests (`unittest` / `pytest`) — 27/27 PASSED
- [x] Frontend build check — PASSED
- [x] Virtual environment setup & dependency installation
