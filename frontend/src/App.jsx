import React, { useState, useEffect } from "react";
import {
  fetchBatches,
  fetchCalibration,
  triggerSync,
  fetchSyncStatus,
  fetchHealth,
} from "./api";
import CalibrationChart from "./components/CalibrationChart";
import BrierScore from "./components/BrierScore";
import InsightCard from "./components/InsightCard";
import MarketTable from "./components/MarketTable";
import ErrorState from "./components/ErrorState";
import LoadingSpinner from "./components/LoadingSpinner";

export default function App() {
  const [batches, setBatches] = useState([]);
  const [selectedBatchId, setSelectedBatchId] = useState("");
  const [topicType, setTopicType] = useState("btc");

  const [calibrationData, setCalibrationData] = useState(null);
  const [cachedCount, setCachedCount] = useState(0);

  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState(null);
  const [apiConfigured, setApiConfigured] = useState(true);

  // Initial load: check health & fetch batches
  useEffect(() => {
    async function init() {
      try {
        setLoading(true);
        setError(null);

        const health = await fetchHealth();
        setApiConfigured(health.api_key_configured);

        const batchRes = await fetchBatches();
        const batchList = batchRes.batches || [];
        setBatches(batchList);

        // Find default batch (e.g. BTC hourly/weekly)
        if (batchList.length > 0) {
          const btcBatch = batchList.find(
            (b) =>
              b.main_topic_title?.toLowerCase().includes("btc") ||
              b.main_topic_title?.toLowerCase().includes("bitcoin")
          );
          setSelectedBatchId(btcBatch ? btcBatch.batch_id : batchList[0].batch_id);
        }
      } catch (err) {
        console.error("Initialization failed:", err);
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  // When selectedBatchId or topicType changes, fetch sync status & calibration
  useEffect(() => {
    if (!selectedBatchId) return;

    let isMounted = true;
    async function loadData() {
      try {
        setError(null);
        // Check how many markets are cached
        const statusRes = await fetchSyncStatus(selectedBatchId, topicType);
        if (!isMounted) return;
        setCachedCount(statusRes.cached_count || 0);

        if (statusRes.cached_count > 0) {
          const calRes = await fetchCalibration(selectedBatchId, topicType, true);
          if (isMounted) setCalibrationData(calRes);
        } else {
          setCalibrationData(null);
        }
      } catch (err) {
        console.error("Failed to load calibration data:", err);
        if (isMounted) setError(err);
      }
    }

    loadData();
    return () => {
      isMounted = false;
    };
  }, [selectedBatchId, topicType]);

  // Handle manual sync
  const handleSync = async () => {
    if (!selectedBatchId) return;
    try {
      setSyncing(true);
      setError(null);
      await triggerSync(selectedBatchId, topicType);

      // Poll sync status briefly or fetch calibration
      setTimeout(async () => {
        try {
          const statusRes = await fetchSyncStatus(selectedBatchId, topicType);
          setCachedCount(statusRes.cached_count || 0);

          const calRes = await fetchCalibration(selectedBatchId, topicType, false);
          setCalibrationData(calRes);
        } catch (pollErr) {
          console.error("Post-sync fetch error:", pollErr);
        } finally {
          setSyncing(false);
        }
      }, 3500);
    } catch (err) {
      console.error("Sync trigger error:", err);
      setError(err);
      setSyncing(false);
    }
  };

  return (
    <div style={{ maxWidth: 1240, margin: "0 auto", padding: "32px 24px", minHeight: "100vh" }}>
      {/* ── Top Header ─────────────────────────────────────────── */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
          marginBottom: 32,
          paddingBottom: 20,
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
            <span style={{ fontSize: "1.75rem" }}>🔮</span>
            <h1 style={{ display: "inline", background: "linear-gradient(135deg, #fff, #90b8ff)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              Glass
            </h1>
            <span className="badge badge-gold">Glimpse Hackathon</span>
            <span className="badge badge-blue">Layer 1: Calibration</span>
          </div>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
            Real-time market probability calibration &amp; conviction engine for Glimpse Bitcoin prediction markets
          </p>
        </div>

        {/* Status Indicators */}
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "0.7rem", color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
              API Status
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "flex-end" }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: apiConfigured ? "var(--success)" : "var(--warning)",
                }}
              />
              <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>
                {apiConfigured ? "Live Production API" : "Key Needed"}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* ── Controls Bar ───────────────────────────────────────── */}
      <div
        className="card"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
          padding: "16px 20px",
          marginBottom: 28,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          <div>
            <label style={{ display: "block", fontSize: "0.72rem", color: "var(--text-dim)", marginBottom: 4, textTransform: "uppercase" }}>
              Market Batch
            </label>
            <select
              value={selectedBatchId}
              onChange={(e) => setSelectedBatchId(e.target.value)}
              disabled={loading || batches.length === 0}
            >
              {batches.map((b) => (
                <option key={b.batch_id} value={b.batch_id}>
                  {b.main_topic_title || b.batch_id} ({b.topic_count} topics)
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: "block", fontSize: "0.72rem", color: "var(--text-dim)", marginBottom: 4, textTransform: "uppercase" }}>
              Asset Type
            </label>
            <select value={topicType} onChange={(e) => setTopicType(e.target.value)}>
              <option value="btc">Bitcoin (BTC)</option>
              <option value="eth">Ethereum (ETH)</option>
              <option value="sol">Solana (SOL)</option>
              <option value="gold">Gold (PAXG)</option>
            </select>
          </div>

          <div style={{ paddingLeft: 8 }}>
            <span className="badge badge-dim">
              {cachedCount} resolved markets cached locally
            </span>
          </div>
        </div>

        <button
          className="btn btn-primary"
          onClick={handleSync}
          disabled={syncing || !selectedBatchId}
        >
          {syncing ? (
            <>
              <LoadingSpinner size={16} label="" />
              <span>Syncing from Glimpse...</span>
            </>
          ) : (
            <>
              <span>⚡</span>
              <span>Sync Resolved Markets</span>
            </>
          )}
        </button>
      </div>

      {/* ── Main View ──────────────────────────────────────────── */}
      {error ? (
        <ErrorState error={error} onRetry={() => setSelectedBatchId(selectedBatchId)} />
      ) : loading ? (
        <div style={{ padding: 60, display: "flex", justifyContent: "center" }}>
          <LoadingSpinner size={32} label="Connecting to Glimpse calibration backend..." />
        </div>
      ) : cachedCount === 0 && !calibrationData ? (
        <div className="card text-center" style={{ padding: "60px 24px" }}>
          <span style={{ fontSize: "2.5rem", display: "block", marginBottom: 12 }}>📥</span>
          <h3 style={{ marginBottom: 8 }}>No Cached Resolved Markets Yet</h3>
          <p style={{ color: "var(--text-secondary)", maxWidth: 500, margin: "0 auto 20px" }}>
            Click <strong>Sync Resolved Markets</strong> above to ingest historical closed markets
            directly from the live Glimpse API and compute the reliability curve.
          </p>
          <button className="btn btn-primary" onClick={handleSync} disabled={syncing}>
            {syncing ? "Syncing..." : "Ingest Market Data Now"}
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {/* Top Row: Brier Score & Plain Language Insight */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 24 }}>
            <BrierScore
              score={calibrationData?.brier_score}
              marketsAnalysed={calibrationData?.markets_with_data}
              marketsTotal={calibrationData?.total_markets || cachedCount}
            />
            <InsightCard
              insight={calibrationData?.insight}
              methodologyNote={calibrationData?.methodology_note}
            />
          </div>

          {/* Middle Row: Reliability Diagram Chart */}
          <CalibrationChart buckets={calibrationData?.buckets || []} />

          {/* Bottom Row: Detailed Probability Bucket Table */}
          <MarketTable buckets={calibrationData?.buckets || []} />
        </div>
      )}

      {/* ── Footer ─────────────────────────────────────────────── */}
      <footer
        style={{
          marginTop: 48,
          paddingTop: 20,
          borderTop: "1px solid var(--border)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
          fontSize: "0.78rem",
          color: "var(--text-dim)",
        }}
      >
        <div>
          Glass · Calibration &amp; Conviction Engine for Glimpse Trading Hackathon
        </div>
        <div>
          Pure transparent statistics · Zero synthetic data · Real Glimpse Production API
        </div>
      </footer>
    </div>
  );
}
