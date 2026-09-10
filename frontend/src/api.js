/**
 * api.js — Frontend API helpers for Glass.
 * All calls go through the FastAPI backend at localhost:8000.
 */

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

// ─── Batches ─────────────────────────────────────────────────────────────────
export const fetchBatches = () => apiFetch("/api/batches");

// ─── Markets ─────────────────────────────────────────────────────────────────
export const fetchSyncStatus = (batchId, topicType = "btc") =>
  apiFetch(`/api/markets/sync-status?batch_id=${batchId}&topic_type=${topicType}`);

export const triggerSync = (batchId, topicType = "btc") =>
  apiFetch(`/api/markets/sync?batch_id=${batchId}&topic_type=${topicType}`, {
    method: "POST",
  });

export const fetchResolvedMarkets = (batchId, topicType = "btc") =>
  apiFetch(`/api/markets/resolved?batch_id=${batchId}&topic_type=${topicType}`);

export const fetchActiveMarkets = (batchId, page = 1, pageSize = 20) =>
  apiFetch(
    `/api/markets/active?batch_id=${batchId}&page=${page}&page_size=${pageSize}`
  );

export const fetchMarketQuotes = (topicId) =>
  apiFetch(`/api/markets/quotes/${topicId}`);

// ─── Calibration ─────────────────────────────────────────────────────────────
export const fetchCalibration = (batchId, topicType = "btc", useCache = true) =>
  apiFetch(
    `/api/calibration/compute?batch_id=${batchId}&topic_type=${topicType}&use_cache=${useCache}`
  );

export const fetchCalibrationSummary = (batchId, topicType = "btc") =>
  apiFetch(
    `/api/calibration/summary?batch_id=${batchId}&topic_type=${topicType}`
  );

export const clearCalibrationCache = (batchId, topicType) =>
  apiFetch(
    `/api/calibration/cache?batch_id=${batchId}${topicType ? `&topic_type=${topicType}` : ""}`,
    { method: "DELETE" }
  );

// ─── Health ───────────────────────────────────────────────────────────────────
export const fetchHealth = () => apiFetch("/api/health");

// ─── Signals (Layer 2) ────────────────────────────────────────────────────────
export const fetchSignals = (batchId, topicType = "btc", minScore = 0.05, topN = 20) =>
  apiFetch(
    `/api/markets/signals?batch_id=${batchId}&topic_type=${topicType}&min_score=${minScore}&top_n=${topN}`
  );

// ─── Trader (Layer 3) ─────────────────────────────────────────────────────────
export const evaluateSignal = (payload) =>
  apiFetch("/api/trader/evaluate", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const executeSignal = (payload) =>
  apiFetch("/api/trader/execute", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const fetchTradeHistory = (limit = 50) =>
  apiFetch(`/api/trader/history?limit=${limit}`);

export const saveApiKey = (apiKey) =>
  apiFetch("/api/settings/key", {
    method: "POST",
    body: JSON.stringify({ api_key: apiKey }),
  });

