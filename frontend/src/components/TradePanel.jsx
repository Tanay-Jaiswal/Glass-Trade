import React, { useState } from "react";
import { evaluateSignal, executeSignal } from "../api";

export default function TradePanel({ signal, calibrationBuckets, onClose, onTradeLogged }) {
  const [step, setStep] = useState("idle"); // idle | evaluating | evaluated | confirming | executing | done | error
  const [decision, setDecision] = useState(null);
  const [contracts, setContracts] = useState(1);
  const [dryRun, setDryRun] = useState(true);
  const [error, setError] = useState(null);

  if (!signal) return null;

  const isOverlay = true;
  const direction = signal.direction || "neutral";
  const prediction = direction === "fade" ? "no" : "yes";
  const directionColor = direction === "fade" ? "#f87171" : direction === "ride" ? "#4ade80" : "#6b7280";

  const handleEvaluate = async () => {
    setStep("evaluating");
    setError(null);
    try {
      const res = await evaluateSignal({
        topic_id: signal.topic_id,
        option_id: signal.option_id,
        topic_title: signal.topic_title,
        option_title: signal.option_title,
        live_implied_prob: signal.live_implied_prob,
        calibration_buckets: calibrationBuckets || [],
        contracts,
        min_conviction: 0.05,
        min_bucket_count: 5,
        max_contracts: 10,
      });
      setDecision(res.decision);
      setStep("evaluated");
    } catch (err) {
      setError(err.message);
      setStep("error");
    }
  };

  const handleExecute = async () => {
    setStep("executing");
    setError(null);
    try {
      const res = await executeSignal({
        topic_id: signal.topic_id,
        option_id: signal.option_id,
        topic_title: signal.topic_title,
        option_title: signal.option_title,
        live_implied_prob: signal.live_implied_prob,
        calibration_buckets: calibrationBuckets || [],
        contracts,
        dry_run: dryRun,
        min_conviction: 0.05,
        min_bucket_count: 5,
        max_contracts: 10,
      });
      setDecision(res.decision);
      setStep("done");
      if (onTradeLogged) onTradeLogged();
    } catch (err) {
      setError(err.message);
      setStep("error");
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(0,0,0,0.70)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        backdropFilter: "blur(4px)",
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="card"
        style={{
          width: "100%",
          maxWidth: 560,
          padding: 28,
          background: "var(--surface, #1a1f2e)",
          border: "1px solid var(--border)",
          borderRadius: 16,
          boxShadow: "0 24px 80px rgba(0,0,0,0.6)",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: "1.1rem" }}>🎯 Trade Evaluation</h2>
            <p style={{ margin: "4px 0 0", fontSize: "0.78rem", color: "var(--text-dim)" }}>
              Review signal, preview cost, then optionally execute
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "var(--text-dim)",
              cursor: "pointer",
              fontSize: "1.2rem",
              padding: 4,
            }}
          >
            ✕
          </button>
        </div>

        {/* Signal summary */}
        <div
          style={{
            background: "rgba(255,255,255,0.04)",
            border: "1px solid var(--border)",
            borderRadius: 10,
            padding: "14px 16px",
            marginBottom: 20,
          }}
        >
          <div style={{ fontSize: "0.78rem", color: "var(--text-dim)", marginBottom: 6 }}>Signal</div>
          <div style={{ fontWeight: 700, marginBottom: 4, fontSize: "0.95rem" }}>
            {signal.topic_title}
          </div>
          <div style={{ color: "var(--text-secondary)", fontSize: "0.82rem", marginBottom: 12 }}>
            {signal.option_title}
          </div>
          <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
            <InfoPair label="Live Price" value={`${(signal.live_implied_prob * 100).toFixed(1)}%`} />
            <InfoPair label="Hist. Realized" value={`${(signal.historical_realized_freq * 100).toFixed(1)}%`} />
            <InfoPair label="Gap" value={`${(signal.gap * 100).toFixed(1)}%`} />
            <InfoPair
              label="Direction"
              value={`${direction === "fade" ? "📉 FADE" : "📈 RIDE"} (buy ${prediction.toUpperCase()})`}
              valueColor={directionColor}
            />
            <InfoPair label="Conviction" value={`${(signal.conviction_score * 100).toFixed(1)}%`} />
          </div>
          <div
            style={{
              marginTop: 12,
              fontSize: "0.72rem",
              color: "var(--text-dim)",
              fontStyle: "italic",
              lineHeight: 1.5,
            }}
          >
            {signal.reasoning}
          </div>
        </div>

        {/* Controls */}
        {step === "idle" || step === "error" ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label style={{ fontSize: "0.72rem", color: "var(--text-dim)", display: "block", marginBottom: 6, textTransform: "uppercase" }}>
                Contracts
              </label>
              <input
                type="number"
                min={1}
                max={10}
                value={contracts}
                onChange={(e) => setContracts(Math.max(1, Math.min(10, parseInt(e.target.value) || 1)))}
                style={{
                  width: 80,
                  padding: "6px 10px",
                  borderRadius: 6,
                  border: "1px solid var(--border)",
                  background: "rgba(255,255,255,0.05)",
                  color: "var(--text-primary)",
                  fontSize: "0.9rem",
                }}
              />
            </div>
            {error && (
              <div style={{ color: "#f87171", fontSize: "0.82rem", background: "rgba(248,113,113,0.1)", padding: "8px 12px", borderRadius: 6 }}>
                ⚠ {error}
              </div>
            )}
            <button
              className="btn btn-primary"
              onClick={handleEvaluate}
              style={{ alignSelf: "flex-start" }}
            >
              🔍 Evaluate (Preview Cost)
            </button>
          </div>
        ) : step === "evaluating" || step === "executing" ? (
          <div style={{ textAlign: "center", padding: "20px 0", color: "var(--text-dim)" }}>
            <div style={{ fontSize: "1.5rem", marginBottom: 8 }}>
              {step === "executing" ? "⚡" : "🔍"}
            </div>
            <div>{step === "executing" ? "Executing trade..." : "Fetching cost estimate..."}</div>
          </div>
        ) : step === "evaluated" ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Cost estimate result */}
            <DecisionSummary decision={decision} />

            {/* Dry run toggle + execute */}
            <div
              style={{
                background: dryRun ? "rgba(74,222,128,0.06)" : "rgba(248,113,113,0.08)",
                border: `1px solid ${dryRun ? "rgba(74,222,128,0.25)" : "rgba(248,113,113,0.35)"}`,
                borderRadius: 8,
                padding: "12px 16px",
              }}
            >
              <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
                <input
                  type="checkbox"
                  checked={!dryRun}
                  onChange={(e) => setDryRun(!e.target.checked)}
                  style={{ width: 16, height: 16, accentColor: "#f87171" }}
                />
                <div>
                  <div style={{ fontWeight: 700, fontSize: "0.82rem", color: dryRun ? "#4ade80" : "#f87171" }}>
                    {dryRun ? "✅ Dry Run Mode (safe)" : "🔴 Live Execution Mode"}
                  </div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-dim)" }}>
                    {dryRun
                      ? "Will log the decision but NOT execute a real trade."
                      : "Will execute a REAL trade on Glimpse. Real money involved."}
                  </div>
                </div>
              </label>
            </div>

            <div style={{ display: "flex", gap: 10 }}>
              <button
                className="btn btn-primary"
                onClick={handleExecute}
                style={{
                  background: dryRun ? undefined : "rgba(248,113,113,0.2)",
                  border: dryRun ? undefined : "1px solid rgba(248,113,113,0.5)",
                }}
              >
                {dryRun ? "📋 Log Dry Run" : "🔴 Execute Real Trade"}
              </button>
              <button
                className="btn"
                onClick={() => setStep("idle")}
                style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}
              >
                Back
              </button>
            </div>
          </div>
        ) : step === "done" ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div
              style={{
                textAlign: "center",
                padding: "16px 0",
                color: decision?.executed ? "#4ade80" : "var(--text-primary)",
              }}
            >
              <div style={{ fontSize: "2rem", marginBottom: 8 }}>
                {decision?.executed ? "✅" : "📋"}
              </div>
              <div style={{ fontWeight: 700 }}>
                {decision?.executed
                  ? "Trade Executed Successfully"
                  : `Dry Run Logged (Trade ID #${decision?.trade_id})`}
              </div>
              <div style={{ fontSize: "0.78rem", color: "var(--text-dim)", marginTop: 4 }}>
                {decision?.executed
                  ? "Trade has been sent to Glimpse"
                  : "Decision saved to trade history — no real money spent"}
              </div>
            </div>
            <DecisionSummary decision={decision} />
            <button className="btn btn-primary" onClick={onClose} style={{ alignSelf: "center" }}>
              Close
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function InfoPair({ label, value, valueColor }) {
  return (
    <div>
      <div style={{ fontSize: "0.62rem", color: "var(--text-dim)", textTransform: "uppercase", marginBottom: 2 }}>
        {label}
      </div>
      <div style={{ fontSize: "0.85rem", fontWeight: 700, color: valueColor || "var(--text-primary)" }}>
        {value}
      </div>
    </div>
  );
}

function DecisionSummary({ decision }) {
  if (!decision) return null;
  const costEst = decision.cost_estimate;
  const riskGateColor = decision.passed_risk_gate ? "#4ade80" : "#f87171";

  return (
    <div
      style={{
        background: "rgba(255,255,255,0.03)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: "12px 16px",
        fontSize: "0.8rem",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ color: "var(--text-dim)" }}>Risk Gate</span>
        <span style={{ color: riskGateColor, fontWeight: 700 }}>
          {decision.passed_risk_gate ? "✅ PASSED" : "❌ REJECTED"}
        </span>
      </div>
      {!decision.passed_risk_gate && (
        <div style={{ color: "#f87171", fontSize: "0.72rem", marginBottom: 8 }}>
          {decision.risk_gate_reason}
        </div>
      )}
      {costEst && !costEst.error && (
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={{ color: "var(--text-dim)" }}>Cost Estimate</span>
          <span style={{ fontWeight: 700 }}>
            {costEst.total_cost ?? costEst.cost ?? costEst.amount ?? JSON.stringify(costEst)}
          </span>
        </div>
      )}
      {costEst?.error && (
        <div style={{ color: "#facc15", fontSize: "0.72rem" }}>
          ⚠ Estimate unavailable: {costEst.error}
        </div>
      )}
      {decision.trade_id && (
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
          <span style={{ color: "var(--text-dim)" }}>Trade ID</span>
          <span style={{ fontFamily: "monospace" }}>#{decision.trade_id}</span>
        </div>
      )}
    </div>
  );
}
