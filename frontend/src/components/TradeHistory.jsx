import React from "react";

function formatTime(unixSec) {
  if (!unixSec) return "—";
  const d = new Date(unixSec * 1000);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Badge({ label, color, bg, border }) {
  return (
    <span
      style={{
        fontSize: "0.65rem",
        fontWeight: 700,
        padding: "2px 7px",
        borderRadius: 4,
        color,
        background: bg,
        border: `1px solid ${border || "transparent"}`,
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}

export default function TradeHistory({ trades = [], loading, onRefresh }) {
  if (loading) {
    return (
      <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--text-dim)" }}>
        <div style={{ fontSize: "1.5rem", marginBottom: 8 }}>📜</div>
        <div>Loading trade history...</div>
      </div>
    );
  }

  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      {/* Header */}
      <div
        style={{
          padding: "16px 20px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <h3 style={{ margin: 0, fontSize: "1rem" }}>📜 Trade History</h3>
          <p style={{ margin: "4px 0 0", fontSize: "0.78rem", color: "var(--text-dim)" }}>
            All evaluated and executed signals — full audit trail
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="badge badge-dim">{trades.length} records</span>
          {onRefresh && (
            <button
              className="btn"
              onClick={onRefresh}
              style={{ fontSize: "0.75rem", padding: "4px 10px", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
            >
              ↻ Refresh
            </button>
          )}
        </div>
      </div>

      {trades.length === 0 ? (
        <div style={{ padding: "48px 24px", textAlign: "center" }}>
          <div style={{ fontSize: "2rem", marginBottom: 12 }}>📋</div>
          <h3 style={{ marginBottom: 8, color: "var(--text-primary)" }}>No Trades Yet</h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", maxWidth: 380, margin: "0 auto" }}>
            Go to the Signals tab, click Evaluate on a signal, and log a dry-run to see it appear here.
          </p>
        </div>
      ) : (
        <>
          {/* Column headers */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "140px 2fr 1fr 80px 80px 80px 80px",
              gap: 8,
              padding: "8px 20px",
              fontSize: "0.62rem",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--text-dim)",
              borderBottom: "1px solid var(--border)",
            }}
          >
            <span>Time</span>
            <span>Market / Outcome</span>
            <span>Direction</span>
            <span>Contracts</span>
            <span>Conviction</span>
            <span>Mode</span>
            <span>Status</span>
          </div>

          {trades.map((t) => {
            const directionColor =
              t.direction === "fade" ? "#f87171"
              : t.direction === "ride" ? "#4ade80"
              : "var(--text-dim)";

            return (
              <div
                key={t.trade_id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "140px 2fr 1fr 80px 80px 80px 80px",
                  gap: 8,
                  padding: "11px 20px",
                  borderBottom: "1px solid var(--border)",
                  alignItems: "center",
                  fontSize: "0.8rem",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.025)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                {/* Time */}
                <div style={{ fontSize: "0.72rem", color: "var(--text-dim)", fontFamily: "monospace" }}>
                  #{t.trade_id} · {formatTime(t.created_at)}
                </div>

                {/* Market */}
                <div>
                  <div
                    style={{
                      fontWeight: 600,
                      fontSize: "0.8rem",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={t.topic_title}
                  >
                    {t.topic_title || `Market #${t.topic_id}`}
                  </div>
                  <div
                    style={{
                      fontSize: "0.68rem",
                      color: "var(--text-dim)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={t.option_title}
                  >
                    {t.option_title || `Option #${t.option_id}`} · buy {t.prediction?.toUpperCase()}
                  </div>
                </div>

                {/* Direction */}
                <div style={{ fontWeight: 700, fontSize: "0.78rem", color: directionColor }}>
                  {t.direction === "fade" ? "📉 FADE" : t.direction === "ride" ? "📈 RIDE" : "—"}
                </div>

                {/* Contracts */}
                <div style={{ fontWeight: 600 }}>{t.contracts}×</div>

                {/* Conviction */}
                <div>
                  {t.conviction_score != null
                    ? `${(t.conviction_score * 100).toFixed(1)}%`
                    : "—"}
                </div>

                {/* Mode badge */}
                <div>
                  {t.dry_run ? (
                    <Badge label="DRY RUN" color="#4ade80" bg="rgba(74,222,128,0.08)" border="rgba(74,222,128,0.25)" />
                  ) : (
                    <Badge label="LIVE" color="#f87171" bg="rgba(248,113,113,0.08)" border="rgba(248,113,113,0.25)" />
                  )}
                </div>

                {/* Status */}
                <div>
                  {t.executed ? (
                    <Badge label="✅ DONE" color="#4ade80" bg="rgba(74,222,128,0.08)" />
                  ) : t.dry_run ? (
                    <Badge label="📋 LOGGED" color="#90b8ff" bg="rgba(144,184,255,0.08)" />
                  ) : (
                    <Badge label="❌ FAILED" color="#f87171" bg="rgba(248,113,113,0.08)" />
                  )}
                </div>
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
