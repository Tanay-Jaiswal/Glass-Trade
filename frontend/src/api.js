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
