# Glass — A Calibration & Conviction Engine for Glimpse Markets

> Built for the **Glimpse Trading Hackathon**.  
> Evaluates prediction market crowd wisdom, computes Brier reliability curves, and detects probability miscalibrations using **real production data** from Glimpse (`https://main.bpmapi.io`).

---

## 1. Problem & Core Thesis

Prediction markets claim to provide accurate forecasts by aggregating crowd beliefs into market prices. However, across various betting domains, market prices often suffer from systematic biases:
- **Favorite-longshot bias / Overconfidence**: Extreme probabilities (e.g., >80%) may resolve true significantly less often than priced.
- **Noise / Under-separation**: In multi-outcome combinatorial or price-bin markets, liquidity may be too diffuse, failing to assign decisive probability mass to the true outcome.

**Glass** answers the empirical question:
> *"When the Glimpse market assigns an implied probability $P$ to an outcome, how often does that outcome actually happen?"*

By plotting the **realized frequency vs. implied probability** (a reliability/calibration curve) and computing the **Brier score**, Glass quantifies crowd accuracy with zero synthetic or fabricated data.

---

## 2. Calibration Methodology

### Implied Probability Proxy
Glimpse price-bin markets (such as *Hourly Bitcoin Prediction Markets*) define multiple discrete price ranges (e.g., up to 500 outcome bins). 

Because the Glimpse API does not retain continuous historical tick-by-tick orderbook snapshots for past markets, the **closing liquidity distribution** represents the final collective bet of the crowd prior to settlement:

$$\text{Implied Probability}(o_i) = \frac{\text{shares}(o_i)}{\sum_{j=1}^{N} \text{shares}(o_j)}$$

For each resolved market, Glass extracts:
- `resolved_option_id`: The winning outcome bin.
- $\text{shares}_{\text{winner}}$: Outstanding shares on the winning outcome.
- $\sum \text{shares}$: Total outstanding shares across all options in the market.

This gives the final market probability assigned to the winning outcome.

### Discretization & Reliability Diagram
Markets are partitioned into 10 equal-width bins:
$[0\%, 10\%), [10\%, 20\%), \dots, [90\%, 100\%]$.

For each bin $k$:
- **Predicted Probability**: The mean implied probability $\bar{P}_k$ of markets within the bin.
- **Realized Frequency**: The empirical frequency of the winning outcome ($1.0$ for the resolved outcomes in this framing, evaluated against expected confidence).
- **Sample Size ($N_k$)**: Total resolved markets falling into the bucket.
- **Confidence Flag**: If $N_k < 10$, the bucket is explicitly flagged as **Low Sample Size** to prevent statistical over-interpretation.

### Brier Score
The overall forecasting accuracy across $M$ resolved markets is computed as:

$$\text{BS} = \frac{1}{M} \sum_{m=1}^{M} (1 - P_{\text{implied}, m})^2$$

- **Range**: $[0, 1]$
- **0.0**: Perfect calibration (market assigned 100% confidence to the true winner at close).
- **0.25**: Baseline equivalent to uninformative 50/50 guessing.

---

## 3. Production API Audit & Discrepancies

Glass is built strictly against the live Glimpse API (`https://main.bpmapi.io`). During our pre-build audit, the following architectural details and discrepancies were identified:

| Component | Documented Behavior | Observed Reality / Implementation |
| :--- | :--- | :--- |
| **Authentication Flow** | Documentation states the API key redirects auth and acts directly as a JWT with ~24h TTL. | There is **no separate token exchange endpoint**. The API key is passed directly in the `Authorization` header. |
| **Auth Header Syntax Discrepancy** | `GET /api/v1/nmarket/batches/{id}/active-markets` specifies `Authorization: <RAW_JWT>` (no `Bearer ` prefix), while `POST /api/v1/nmarket/trades` specifies `Authorization: Bearer <token>`. | Glass implements an **Auth Prober** (`GlimpseClient._probe_auth`) that probes both headers on startup against `/api/v1/portfolio` and selects the working convention. |
| **Historical Price Snapshots** | Prediction market research typically samples prices 1h or 24h before close. | The Glimpse `/resolved-markets` endpoints return only final outcome shares and `resolved_option_id`, **not** historical price snapshots. Glass transparently uses the final shares distribution proxy and documents this constraint. |
| **Pagination** | `GET /api/v1/nmarket/v2/batches/{batch_id}/resolved-markets` provides `has_more` and `next_offset`. | Drained cleanly with polite 200ms rate-limiting intervals to avoid hitting server-side rate limits. |

---

## 4. Project Architecture

```
glass/
├── backend/
│   ├── main.py                  # FastAPI application, CORS, lifespan initialization
│   ├── api_client.py            # Async httpx client, auth probe, retry, backoff
│   ├── calibration.py           # Implied prob math, Brier score, bucketing, plain insights
│   ├── database.py              # SQLite storage for resolved markets & calibration cache
│   ├── requirements.txt         # Backend dependencies
│   ├── routes/
│   │   ├── markets.py           # Batches, resolved markets sync, active market quotes
│   │   ├── calibration.py       # Compute & summary endpoints
│   │   └── portfolio.py         # Portfolio & P&L endpoints (Layer 3 prep)
│   └── tests/
│       └── test_calibration.py  # 27 unit tests (dual pytest & unittest compatible)
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main dashboard view
│   │   ├── index.css            # Dark glassmorphism design system (Inter font)
│   │   ├── api.js               # Typed client fetch helpers
│   │   └── components/
│   │       ├── CalibrationChart.jsx # Recharts reliability diagram with ideal reference line
│   │       ├── BrierScore.jsx       # Animated metric card with quality indicators
│   │       ├── InsightCard.jsx      # Plain-language statistical insight
│   │       ├── MarketTable.jsx      # Per-bucket sample and deviation breakdown
│   │       ├── LoadingSpinner.jsx   # Micro-animation spinner
│   │       └── ErrorState.jsx       # Graceful degradation error panel
│   └── package.json
├── .env.example
└── README.md
```

---

## 5. Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- A valid Glimpse API key (from [glimpse.markets/settings](https://glimpse.markets/settings))

### Backend Setup
1. Navigate to `backend`:
   ```bash
   cd glass/backend
   ```
2. Create and activate a virtual environment:
   ```bash
   # Windows
   python -m venv .venv
   .\.venv\Scripts\activate

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure your `.env` file:
   ```bash
   cp ../.env.example .env
   ```
   Edit `.env` and set:
   ```env
   GLIMPSE_API_KEY=your_actual_glimpse_api_key
   ```
   *(If you run without setting `GLIMPSE_API_KEY`, the backend will interactively prompt you for it in the terminal at startup).*

5. Run unit tests:
   ```bash
   python -m unittest discover -s tests -p "test_*.py" -v
   ```
6. Start the FastAPI server:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   Interactive Swagger docs will be live at `http://localhost:8000/docs`.

### Frontend Setup
1. In another terminal, navigate to `frontend`:
   ```bash
   cd glass/frontend
   ```
2. Install dependencies (if not already installed):
   ```bash
   npm install
   ```
3. Launch the development server:
   ```bash
   npm run dev
   ```
4. Open your browser at `http://localhost:5173`.

---

## 6. Honest Limitations & Transparency

- **Closing Proxy vs. Intra-Market Snapshot**: Because historical quote snapshots are not recorded in Glimpse's resolved market payload, the calibration curve reflects **closing liquidity conviction**, not mid-market pricing.
- **Sample Size Sensitivity**: Prediction markets on smaller batches or newer assets (e.g. Gold or SOL) may have fewer than 20 resolved markets. The engine explicitly tags small buckets as `Low Sample Size` rather than asserting false certainty.
- **Directional Signal**: Statistical calibration provides an edge in expectation over large samples; it does not guarantee the outcome of any single discrete market.
