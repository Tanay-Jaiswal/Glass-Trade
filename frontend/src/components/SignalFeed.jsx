import React from "react";

const DIRECTION_CONFIG = {
  fade: {
    label: "FADE",
    color: "var(--error, #f87171)",
    bg: "rgba(248,113,113,0.10)",
    border: "rgba(248,113,113,0.30)",
    emoji: "📉",
    tip: "Crowd is overconfident — historical win rate lower than implied odds",
  },
  ride: {
    label: "RIDE",
    color: "var(--success, #4ade80)",
    bg: "rgba(74,222,128,0.10)",
    border: "rgba(74,222,128,0.30)",
    emoji: "📈",
    tip: "Crowd is underconfident — historical win rate higher than implied odds",
  },
  neutral: {
    label: "NEUTRAL",
    color: "var(--text-dim, #6b7280)",
    bg: "rgba(107,114,128,0.08)",
    border: "rgba(107,114,128,0.20)",
    emoji: "⚖️",
    tip: "No significant miscalibration detected",
  },
};

function ConvictionBar({ score }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 20 ? "var(--success, #4ade80)"
    : pct >= 10 ? "#facc15"
    : "var(--text-dim, #6b7280)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 120 }}>
      <div
        style={{
          flex: 1,
          height: 6,
          borderRadius: 3,
          background: "rgba(255,255,255,0.08)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${Math.min(pct * 3, 100)}%`,
            background: color,
            borderRadius: 3,
            transition: "width 0.4s ease",
          }}
        />
      </div>
      <span style={{ fontSize: "0.72rem", fontWeight: 700, color, minWidth: 30 }}>
        {pct}%
      </span>
    </div>
  );
}

export default function SignalFeed({ signals = [], summary = {}, loading, onEvaluate }) {
  if (loading) {
    return (
      <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--text-dim)" }}>
        <div style={{ fontSize: "1.5rem", marginBottom: 8 }}>🔍</div>
        <div>Scanning live markets for miscalibrations...</div>
      </div>
    );
  }

  if (!signals.length) {
    return (
      <div className="card" style={{ padding: 40, textAlign: "center" }}>
        <div style={{ fontSize: "2rem", marginBottom: 12 }}>🎯</div>
        <h3 style={{ marginBottom: 8, color: "var(--text-primary)" }}>No Signals Above Threshold</h3>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", maxWidth: 420, margin: "0 auto" }}>
          No live markets have a meaningful calibration gap right now.
          Sync more resolved markets or lower the min conviction threshold to see more opportunities.
        </p>
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
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div>
          <h3 style={{ margin: 0, fontSize: "1rem" }}>⚡ Live Conviction Signals</h3>
          <p style={{ margin: "4px 0 0", fontSize: "0.78rem", color: "var(--text-dim)" }}>
            Ranked by calibration edge — historical miscalibration gaps vs current market pricing
          </p>
        </div>
        {summary.count > 0 && (
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <Stat label="Signals" value={summary.count} />
            <Stat label="Fade" value={summary.fade_count} color="var(--error, #f87171)" />
            <Stat label="Ride" value={summary.ride_count} color="var(--success, #4ade80)" />
            <Stat label="Avg Edge" value={`${(summary.avg_conviction * 100).toFixed(1)}%`} />
          </div>
        )}
      </div>

      {/* Column headers */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "2fr 1fr 1fr 1fr 1.4fr 80px",
          gap: 8,
          padding: "8px 20px",
          fontSize: "0.65rem",
          fontWeight: 700,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "var(--text-dim)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <span>Market / Outcome</span>
        <span>Live Price</span>
        <span>Hist. Freq</span>
        <span>Direction</span>
        <span>Conviction</span>
        <span />
      </div>

      {/* Signal rows */}
      {signals.map((sig, i) => {
        const cfg = DIRECTION_CONFIG[sig.direction] || DIRECTION_CONFIG.neutral;
        return (
          <div
            key={`${sig.topic_id}-${sig.option_id}`}
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 1fr 1fr 1fr 1.4fr 80px",
              gap: 8,
              padding: "12px 20px",
              borderBottom: i < signals.length - 1 ? "1px solid var(--border)" : "none",
              alignItems: "center",
              transition: "background 0.15s",
              cursor: "default",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.03)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            {/* Market info */}
            <div>
              <div
                style={{
                  fontSize: "0.8rem",
                  fontWeight: 600,
                  color: "var(--text-primary)",
                  marginBottom: 2,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={sig.topic_title}
              >
                {sig.topic_title}
              </div>
              <div
                style={{
                  fontSize: "0.72rem",
                  color: "var(--text-dim)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={sig.option_title}
              >
                {sig.option_title}
              </div>
              {sig.low_confidence && (
                <span
                  style={{
                    fontSize: "0.6rem",
                    color: "#facc15",
                    background: "rgba(250,204,21,0.12)",
                    padding: "1px 5px",
                    borderRadius: 3,
                    marginTop: 3,
                    display: "inline-block",
                  }}
                >
                  ⚠ Low sample ({sig.bucket_count})
                </span>
              )}
            </div>

            {/* Live implied prob */}
            <div style={{ fontWeight: 700, fontSize: "0.88rem" }}>
              {(sig.live_implied_prob * 100).toFixed(1)}%
              <div style={{ fontSize: "0.65rem", color: "var(--text-dim)", fontWeight: 400 }}>
                {sig.bucket_label}
              </div>
            </div>

            {/* Historical realized freq */}
            <div style={{ fontWeight: 700, fontSize: "0.88rem" }}>
              {sig.historical_realized_freq != null
                ? `${(sig.historical_realized_freq * 100).toFixed(1)}%`
                : "—"}
              <div style={{ fontSize: "0.65rem", color: "var(--text-dim)", fontWeight: 400 }}>
                realized
              </div>
            </div>

            {/* Direction badge */}
            <div>
              <span
                style={{
                  fontSize: "0.7rem",
                  fontWeight: 700,
                  padding: "3px 8px",
                  borderRadius: 4,
                  color: cfg.color,
                  background: cfg.bg,
                  border: `1px solid ${cfg.border}`,
                }}
              >
                {cfg.emoji} {cfg.label}
              </span>
            </div>

            {/* Conviction bar */}
            <ConvictionBar score={sig.conviction_score} />

            {/* Evaluate button */}
            <div>
              {onEvaluate && (
                <button
                  className="btn"
                  style={{
                    fontSize: "0.7rem",
                    padding: "4px 10px",
                    background: "rgba(144,184,255,0.12)",
                    border: "1px solid rgba(144,184,255,0.3)",
                    color: "#90b8ff",
                    borderRadius: 6,
                    cursor: "pointer",
                    whiteSpace: "nowrap",
                  }}
                  onClick={() => onEvaluate(sig)}
                >
                  Evaluate
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div
        style={{
          fontSize: "1rem",
          fontWeight: 700,
          color: color || "var(--text-primary)",
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: "0.62rem", color: "var(--text-dim)", textTransform: "uppercase" }}>
        {label}
      </div>
    </div>
  );
}
