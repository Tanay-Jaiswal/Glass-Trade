"""
api_client.py — Async Glimpse API client.

Design decisions:
  - Uses httpx.AsyncClient for non-blocking I/O in FastAPI.
  - Auth probe: the index docs say "API key IS the JWT, no separate token exchange."
    The active-markets v1 endpoint docs say raw key (no Bearer prefix); the trades
    endpoint docs say Bearer prefix. We probe both on first authenticated call and
    persist the result in memory for the process lifetime. Discrepancy is noted in README.
  - Retry: exponential backoff on 5xx/timeout, up to 3 attempts.
  - Rate limiting: conservative 200ms sleep between paginated requests.
  - All methods raise GlimpseAPIError on unrecoverable failure; callers handle gracefully.
"""

import asyncio
import logging
import os
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("GLIMPSE_BASE_URL", "https://main.bpmapi.io")
PAGE_SIZE = 50           # market pages — reasonable chunk size
REQUEST_TIMEOUT = 20.0   # seconds
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.5  # seconds

# Resolved-market fetch cap (0 = unlimited).  Set via env MAX_RESOLVED_PAGES.
MAX_PAGES = int(os.getenv("MAX_RESOLVED_PAGES", "20"))


class GlimpseAPIError(Exception):
    """Raised when the Glimpse API returns an unrecoverable error."""

    def __init__(self, message: str, status_code: Optional[int] = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class GlimpseClient:
    """
    Async client for the Glimpse prediction market API.

    Usage:
        client = GlimpseClient(api_key="...")
        async with client:
            batches = await client.get_batches()
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("GLIMPSE_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "GLIMPSE_API_KEY is not set. "
                "Copy .env.example to .env and add your key."
            )
        self._http: Optional[httpx.AsyncClient] = None
        # Resolved at runtime: "raw" | "bearer"
        self._auth_style: Optional[str] = None

    async def __aenter__(self):
        self._http = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=REQUEST_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, *_):
        if self._http:
            await self._http.aclose()

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _auth_headers(self, style: str) -> dict:
        if style == "bearer":
            return {"Authorization": f"Bearer {self._api_key}"}
        return {"Authorization": self._api_key}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        auth_required: bool = False,
        json_body=None,
        params=None,
    ) -> dict:
        """
        Make an HTTP request with retry logic.
        If auth_required and auth style unknown, probes raw then bearer.
        """
        if auth_required and self._auth_style is None:
            await self._probe_auth(path)

        headers = {}
        if auth_required:
            headers = self._auth_headers(self._auth_style or "bearer")

        for attempt in range(MAX_RETRIES):
            try:
                resp = await self._http.request(
                    method,
                    path,
                    headers=headers,
                    params=params,
                    json=json_body,
                )

                if resp.status_code == 401 and auth_required and self._auth_style == "raw":
                    # Try bearer on 401
                    logger.warning("Raw auth returned 401, switching to Bearer style")
                    self._auth_style = "bearer"
                    headers = self._auth_headers("bearer")
                    continue

                if resp.status_code >= 500:
                    wait = RETRY_BACKOFF_BASE ** attempt
                    logger.warning(
                        "5xx from %s %s (attempt %d/%d), retrying in %.1fs",
                        method, path, attempt + 1, MAX_RETRIES, wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                if resp.status_code >= 400:
                    raise GlimpseAPIError(
                        f"HTTP {resp.status_code} from {path}",
                        status_code=resp.status_code,
                        body=resp.text[:500],
                    )

                return resp.json()

            except httpx.TimeoutException:
                wait = RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    "Timeout on %s %s (attempt %d/%d), retrying in %.1fs",
                    method, path, attempt + 1, MAX_RETRIES, wait,
                )
                await asyncio.sleep(wait)

            except httpx.RequestError as exc:
                raise GlimpseAPIError(f"Network error: {exc}") from exc

        raise GlimpseAPIError(
            f"Failed after {MAX_RETRIES} attempts: {method} {path}"
        )

    async def _probe_auth(self, hint_path: str = "") -> None:
        """
        Determine which auth header format the server accepts.

        The docs are inconsistent:
          - active-markets v1: raw JWT (no Bearer prefix)
          - trades: Bearer <token>
        We try raw first (most restrictive), then fall back to Bearer.
        Result is cached for the process lifetime and logged.

        NOTE: This probe uses the portfolio endpoint since it's always auth-required
        and won't cause any side effects.
        """
        probe_path = "/api/v1/portfolio"

        for style in ("raw", "bearer"):
            headers = self._auth_headers(style)
            try:
                resp = await self._http.get(
                    probe_path,
                    headers=headers,
                    timeout=10.0,
                )
                if resp.status_code not in (401, 403):
                    self._auth_style = style
                    logger.info(
                        "Auth probe: using '%s' style (HTTP %d on %s)",
                        style, resp.status_code, probe_path,
                    )
                    return
            except httpx.RequestError:
                continue

        # Default to bearer if probe inconclusive
        self._auth_style = "bearer"
        logger.warning(
            "Auth probe inconclusive — defaulting to Bearer style. "
            "See README for discrepancy notes."
        )

    # -----------------------------------------------------------------------
    # Public API methods
    # -----------------------------------------------------------------------

    async def get_batches(self) -> list[dict]:
        """GET /api/v1/nmarket/batches — public, returns list of batch objects."""
        data = await self._request("GET", "/api/v1/nmarket/batches")
        # Docs say returns an array directly
        if isinstance(data, list):
            return data
        # Some wrappers might envelope it
        return data.get("batches", data.get("data", []))

    async def get_resolved_markets_page(
        self,
        batch_id: str,
        page: int = 1,
        page_size: int = PAGE_SIZE,
    ) -> dict:
        """
        GET /api/v1/nmarket/v2/batches/{batch_id}/resolved-markets
        Returns full response dict including pagination metadata.
        """
        data = await self._request(
            "GET",
            f"/api/v1/nmarket/v2/batches/{batch_id}/resolved-markets",
            params={"page": page, "page_size": page_size},
        )
        return data

    async def get_all_resolved_markets(
        self,
        batch_id: str,
        topic_type_filter: Optional[str] = None,
        progress_callback=None,
    ) -> list[dict]:
        """
        Drain all pages of resolved markets for a batch.
        Optionally filter by topic_type client-side (e.g., 'btc').
        Respects MAX_PAGES env cap.
        Returns a flat list of market dicts.
        """
        all_markets: list[dict] = []
        page = 1
        max_pages = MAX_PAGES if MAX_PAGES > 0 else 99999

        while page <= max_pages:
            data = await self.get_resolved_markets_page(batch_id, page=page)
            markets = data.get("markets", [])

            if topic_type_filter:
                markets = [
                    m for m in markets
                    if m.get("topic_type", "").lower() == topic_type_filter.lower()
                ]

            all_markets.extend(markets)

            if progress_callback:
                total = data.get("total", 0)
                progress_callback(len(all_markets), total)

            has_more = data.get("has_more", False)
            if not has_more or not data.get("markets"):
                break

            page += 1
            # Polite rate limiting between pages
            await asyncio.sleep(0.2)

        logger.info(
            "Fetched %d resolved markets for batch %s (pages: %d)",
            len(all_markets), batch_id, page - 1,
        )
        return all_markets

    async def get_market_quotes(self, topic_id: int) -> dict:
        """
        GET /api/v1/nmarket/markets/{topic_id}/quotes — public.
        Returns live quotes including per-outcome yes_price / no_price.
        """
        return await self._request("GET", f"/api/v1/nmarket/markets/{topic_id}/quotes")

    async def get_active_markets_v2(
        self,
        batch_id: str,
        page: int = 1,
        page_size: int = PAGE_SIZE,
    ) -> dict:
        """
        GET /api/v1/nmarket/v2/batches/{batch_id}/active-markets — public.
        Returns slim market list with pagination.
        """
        return await self._request(
            "GET",
            f"/api/v1/nmarket/v2/batches/{batch_id}/active-markets",
            params={"page": page, "page_size": page_size},
        )

    async def get_portfolio(self) -> dict:
        """GET /api/v1/portfolio — requires auth."""
        return await self._request("GET", "/api/v1/portfolio", auth_required=True)

    async def get_consolidated_portfolio(self) -> dict:
        """GET /api/v1/consolidated-portfolio — requires auth."""
        return await self._request(
            "GET", "/api/v1/consolidated-portfolio", auth_required=True
        )

    async def get_pnl_stats(self) -> dict:
        """GET /api/v1/pnl-stats — requires auth."""
        return await self._request("GET", "/api/v1/pnl-stats", auth_required=True)

    async def estimate_trade(
        self,
        topic_id: int,
        option_id: int,
        contracts: int,
        prediction: str = "yes",
        trade_type: str = "buy",
    ) -> dict:
        """
        POST /api/v1/nmarket/trades/estimate — public.
        Returns cost estimate without executing.
        """
        return await self._request(
            "POST",
            "/api/v1/nmarket/trades/estimate",
            json_body={
                "topic_id": topic_id,
                "trade_type": trade_type,
                "legs": [
                    {
                        "option_id": option_id,
                        "contracts": contracts,
                        "prediction": prediction,
                    }
                ],
            },
        )

    async def execute_trade(
        self,
        topic_id: int,
        option_id: int,
        contracts: int,
        prediction: str = "yes",
        trade_type: str = "buy",
    ) -> dict:
        """
        POST /api/v1/nmarket/trades — requires auth.
        Executes a real trade. Use with extreme caution.
        """
        return await self._request(
            "POST",
            "/api/v1/nmarket/trades",
            auth_required=True,
            json_body={
                "topic_id": topic_id,
                "trade_type": trade_type,
                "legs": [
                    {
                        "option_id": option_id,
                        "contracts": contracts,
                        "prediction": prediction,
                    }
                ],
            },
        )
