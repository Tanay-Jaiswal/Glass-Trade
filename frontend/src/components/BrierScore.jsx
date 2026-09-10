/** BrierScore.jsx — Animated metric card for the Brier score */
export default function BrierScore({ score, marketsAnalysed, marketsTotal }) {
  const pct = score != null ? Math.round((1 - score) * 100) : null;
  const quality =
    score == null
      ? null
      : score < 0.05
      ? { label: "Excellent", color: "var(--success)" }
      : score < 0.15
      ? { label: "Good", color: "var(--accent)" }
      : score < 0.25
      ? { label: "Moderate", color: "var(--warning)" }
      : { label: "Weak", color: "var(--danger)" };

  return (
    <div className="card animate-in" style={{ minWidth: 200 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div>
          <h4 style={{ marginBottom: 4 }}>Brier Score</h4>
          <p style={{ fontSize: "0.75rem", color: "var(--text-dim)", lineHeight: 1.4 }}>
            0 = perfect · 0.25 = coin flip · lower is better
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "flex-end", gap: 12 }}>
          <span
            style={{
              fontSize: "3rem",
              fontWeight: 800,
              lineHeight: 1,
              letterSpacing: "-0.04em",
              color: quality?.color || "var(--text-dim)",
            }}
          >
            {score != null ? score.toFixed(4) : "—"}
          </span>
          {quality && (
            <span
              className="badge badge-blue"
              style={{
                background: quality.color + "22",
                color: quality.color,
                borderColor: quality.color + "44",
                marginBottom: 6,
              }}
            >
              {quality.label}
            </span>
          )}
        </div>

        {score != null && (
          <div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: 4,
                fontSize: "0.72rem",
                color: "var(--text-dim)",
              }}
            >
              <span>Worse (1.0)</span>
              <span>Better (0.0)</span>
            </div>
            <div className="progress-bar">
              <div
                className="fill"
                style={{
                  width: `${100 - score * 400}%`,
                  background: `linear-gradient(90deg, ${quality?.color || "var(--accent)"}, var(--accent))`,
                }}
              />
            </div>
          </div>
        )}

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            paddingTop: 8,
            borderTop: "1px solid var(--border)",
          }}
        >
          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
              With Data
            </div>
            <div style={{ fontWeight: 700, fontSize: "1.1rem" }}>
              {marketsAnalysed ?? "—"}
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "0.7rem", color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Total Cached
            </div>
            <div style={{ fontWeight: 700, fontSize: "1.1rem" }}>
              {marketsTotal ?? "—"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
