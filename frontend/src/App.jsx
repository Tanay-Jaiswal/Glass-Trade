import React, { useState, useEffect, useCallback } from "react";
import {
  fetchBatches,
  fetchCalibration,
  triggerSync,
  fetchSyncStatus,
  fetchHealth,
  fetchSignals,
  fetchTradeHistory,
} from "./api";
import CalibrationChart from "./components/CalibrationChart";
import BrierScore from "./components/BrierScore";
import InsightCard from "./components/InsightCard";
import MarketTable from "./components/MarketTable";
import ErrorState from "./components/ErrorState";
import LoadingSpinner from "./components/LoadingSpinner";
import SignalFeed from "./components/SignalFeed";
import TradePanel from "./components/TradePanel";
import TradeHistory from "./components/TradeHistory";

const TABS = [
  { id: "calibration", label: "📊 Calibration" },
  { id: "signals", label: "⚡ Signals & Trade" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("calibration");

  // ── Shared state ─────────────────────────────────────────────────────────
  const [batches, setBatches] = useState([]);
  const [selectedBatchId, setSelectedBatchId] = useState("");
  const [topicType, setTopicType] = useState("btc");
  const [apiConfigured, setApiConfigured] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // ── Calibration tab state ─────────────────────────────────────────────────
  const [calibrationData, setCalibrationData] = useState(null);
  const [cachedCount, setCachedCount] = useState(0);
  const [syncing, setSyncing] = useState(false);

  // ── Signals tab state ─────────────────────────────────────────────────────
  const [signals, setSignals] = useState([]);
  const [signalSummary, setSignalSummary] = useState({});
  const [signalsLoading, setSignalsLoading] = useState(false);
  const [signalsError, setSignalsError] = useState(null);
  const [minScore, setMinScore] = useState(0.05);

  // ── Trade panel state ─────────────────────────────────────────────────────
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [trades, setTrades] = useState([]);
  const [tradesLoading, setTradesLoading] = useState(false);

  // ── Init ─────────────────────────────────────────────────────────────────
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

        if (batchList.length > 0) {
          const btcBatch = batchList.find(
            (b) =>
              b.main_topic_title?.toLowerCase().includes("btc") ||
              b.main_topic_title?.toLowerCase().includes("bitcoin")
          );
          setSelectedBatchId(btcBatch ? btcBatch.batch_id : batchList[0].batch_id);
        }
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  // ── Load calibration when batch/type changes ──────────────────────────────
  useEffect(() => {
    if (!selectedBatchId) return;
    let isMounted = true;
    async function loadCalibration() {
      try {
        setError(null);
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
        if (isMounted) setError(err);
      }
    }
    loadCalibration();
    return () => { isMounted = false; };
  }, [selectedBatchId, topicType]);

  // ── Load signals when signals tab is active ───────────────────────────────
  useEffect(() => {
    if (activeTab !== "signals" || !selectedBatchId || cachedCount === 0) return;
    loadSignals();
  }, [activeTab, selectedBatchId, topicType, minScore]);

  // ── Load trade history when signals tab is active ─────────────────────────
  useEffect(() => {
    if (activeTab !== "signals") return;
    loadTradeHistory();
  }, [activeTab]);

  const loadSignals = useCallback(async () => {
    if (!selectedBatchId) return;
    setSignalsLoading(true);
    setSignalsError(null);
    try {
      const res = await fetchSignals(selectedBatchId, topicType, minScore);
      setSignals(res.signals || []);
      setSignalSummary(res.summary || {});
    } catch (err) {
      setSignalsError(err.message);
    } finally {
      setSignalsLoading(false);
    }
  }, [selectedBatchId, topicType, minScore]);

  const loadTradeHistory = useCallback(async () => {
    setTradesLoading(true);
    try {
      const res = await fetchTradeHistory(50);
      setTrades(res.trades || []);
    } catch (_) {}
    finally { setTradesLoading(false); }
  }, []);

  // ── Sync handler ──────────────────────────────────────────────────────────
  const handleSync = async () => {
    if (!selectedBatchId) return;
    try {
      setSyncing(true);
      setError(null);
      await triggerSync(selectedBatchId, topicType);
      setTimeout(async () => {
        try {
          const statusRes = await fetchSyncStatus(selectedBatchId, topicType);
          setCachedCount(statusRes.cached_count || 0);
          const calRes = await fetchCalibration(selectedBatchId, topicType, false);
          setCalibrationData(calRes);
        } catch (_) {}
        finally { setSyncing(false); }
      }, 3500);
    } catch (err) {
      setError(err);
      setSyncing(false);
    }
  };

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: "32px 24px", minHeight: "100vh" }}>
      {/* ── Top Header ─────────────────────────────────────────────────────── */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
          marginBottom: 24,
          paddingBottom: 20,
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
            <span style={{ fontSize: "1.75rem" }}>🔮</span>
            <h1
              style={{
                display: "inline",
                background: "linear-gradient(135deg, #fff, #90b8ff)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Glass
            </h1>
            <span className="badge badge-gold">Glimpse Hackathon</span>
            <span className="badge badge-blue">Layer 1+2+3</span>
          </div>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
            Calibration · Conviction Scoring · Trade Execution Engine
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "0.7rem", color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
              API Status
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, justifyContent: "flex-end" }}>
              <span
                style={{
                  width: 8, height: 8, borderRadius: "50%",
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

      {/* ── Controls Bar ───────────────────────────────────────────────────── */}
      <div
        className="card"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
          padding: "14px 20px",
          marginBottom: 20,
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
            <span className="badge badge-dim">{cachedCount} resolved markets cached</span>
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

      {/* ── Tabs ───────────────────────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          gap: 4,
          marginBottom: 24,
          borderBottom: "1px solid var(--border)",
          paddingBottom: 0,
        }}
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "8px 18px",
              border: "none",
              borderBottom: activeTab === tab.id ? "2px solid #90b8ff" : "2px solid transparent",
              background: "none",
              color: activeTab === tab.id ? "#90b8ff" : "var(--text-dim)",
              fontWeight: activeTab === tab.id ? 700 : 400,
              fontSize: "0.875rem",
              cursor: "pointer",
              transition: "color 0.15s, border-color 0.15s",
              marginBottom: -1,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Main Content ───────────────────────────────────────────────────── */}
      {error ? (
        <ErrorState error={error} onRetry={() => setSelectedBatchId(selectedBatchId)} />
      ) : loading ? (
        <div style={{ padding: 60, display: "flex", justifyContent: "center" }}>
          <LoadingSpinner size={32} label="Connecting to Glimpse calibration backend..." />
        </div>
      ) : activeTab === "calibration" ? (
        /* ── Calibration Tab ─────────────────────────────────────────────── */
        cachedCount === 0 && !calibrationData ? (
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
            <CalibrationChart buckets={calibrationData?.buckets || []} />
            <MarketTable buckets={calibrationData?.buckets || []} />
          </div>
        )
      ) : (
        /* ── Signals & Trade Tab ─────────────────────────────────────────── */
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {/* Signals controls */}
          <div
            className="card"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 20,
              padding: "14px 20px",
              flexWrap: "wrap",
            }}
          >
            <div>
              <label style={{ fontSize: "0.72rem", color: "var(--text-dim)", textTransform: "uppercase", display: "block", marginBottom: 4 }}>
                Min Conviction Score
              </label>
              <select
                value={minScore}
                onChange={(e) => setMinScore(parseFloat(e.target.value))}
                style={{ minWidth: 120 }}
              >
                <option value={0.0}>All signals (0%)</option>
                <option value={0.05}>5%+ edge</option>
                <option value={0.10}>10%+ edge</option>
                <option value={0.15}>15%+ edge</option>
                <option value={0.20}>20%+ edge (strong)</option>
              </select>
            </div>
            <button
              className="btn btn-primary"
              onClick={loadSignals}
              disabled={signalsLoading || cachedCount === 0}
              style={{ alignSelf: "flex-end" }}
            >
              {signalsLoading ? (
                <>
                  <LoadingSpinner size={14} label="" />
                  <span>Scanning...</span>
                </>
              ) : (
                "🔍 Scan Live Markets"
              )}
            </button>
            {cachedCount === 0 && (
              <span style={{ fontSize: "0.78rem", color: "var(--warning, #facc15)" }}>
                ⚠ Sync resolved markets first (Calibration tab)
              </span>
            )}
            {signalsError && (
              <span style={{ fontSize: "0.78rem", color: "#f87171" }}>
                ⚠ {signalsError}
              </span>
            )}
          </div>

          {/* Signal feed */}
          <SignalFeed
            signals={signals}
            summary={signalSummary}
            loading={signalsLoading}
            onEvaluate={(sig) => setSelectedSignal(sig)}
          />

          {/* Trade history */}
          <TradeHistory
            trades={trades}
            loading={tradesLoading}
            onRefresh={loadTradeHistory}
          />
        </div>
      )}

      {/* ── Trade Panel Modal ───────────────────────────────────────────────── */}
      {selectedSignal && (
        <TradePanel
          signal={selectedSignal}
          calibrationBuckets={calibrationData?.buckets || []}
          onClose={() => setSelectedSignal(null)}
          onTradeLogged={() => {
            setSelectedSignal(null);
            loadTradeHistory();
          }}
        />
      )}

      {/* ── Footer ──────────────────────────────────────────────────────────── */}
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
        <div>Glass · Calibration & Conviction Engine · Glimpse Trading Hackathon</div>
        <div>
          Layer 1: Calibration · Layer 2: Signals · Layer 3: Trade Execution · Zero Synthetic Data
        </div>
      </footer>
    </div>
  );
}
