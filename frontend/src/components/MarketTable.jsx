import React from "react";

export default function MarketTable({ buckets = [] }) {
  if (!buckets || buckets.length === 0) return null;

  return (
    <div className="card animate-in animate-delay-3" style={{ overflowX: "auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <h3>Probability Bucket Breakdown</h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.8rem" }}>
            Statistical details and sample confidence per interval
          </p>
        </div>
        <span className="badge badge-dim">{buckets.length} Buckets</span>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)", textAlign: "left", color: "var(--text-dim)" }}>
            <th style={{ padding: "8px 12px" }}>Bucket</th>
            <th style={{ padding: "8px 12px" }}>Avg Implied Prob</th>
            <th style={{ padding: "8px 12px" }}>Realized Freq</th>
            <th style={{ padding: "8px 12px" }}>Deviation</th>
            <th style={{ padding: "8px 12px" }}>Sample Size</th>
            <th style={{ padding: "8px 12px" }}>Confidence Status</th>
          </tr>
        </thead>
        <tbody>
          {buckets.map((b, idx) => {
            const predPct = b.predicted_prob != null ? b.predicted_prob * 100 : null;
            const realPct = b.realized_freq != null ? b.realized_freq * 100 : null;
            const diff = predPct != null && realPct != null ? (realPct - predPct).toFixed(1) : null;

            return (
              <tr
                key={idx}
                style={{
                  borderBottom: "1px solid rgba(56, 100, 200, 0.08)",
                  background: idx % 2 === 0 ? "rgba(255, 255, 255, 0.01)" : "transparent",
                }}
              >
                <td style={{ padding: "10px 12px", fontWeight: 600 }}>{b.bucket_label}</td>
                <td style={{ padding: "10px 12px" }} className="font-mono">
                  {predPct != null ? `${predPct.toFixed(1)}%` : "—"}
                </td>
                <td style={{ padding: "10px 12px" }} className="font-mono">
                  {realPct != null ? `${realPct.toFixed(1)}%` : "—"}
                </td>
                <td style={{ padding: "10px 12px" }} className="font-mono">
                  {diff != null ? (
                    <span style={{ color: Number(diff) >= 0 ? "var(--success)" : "var(--danger)" }}>
                      {Number(diff) > 0 ? `+${diff}%` : `${diff}%`}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td style={{ padding: "10px 12px" }} className="font-mono">
                  {b.count}
                </td>
                <td style={{ padding: "10px 12px" }}>
                  {b.count === 0 ? (
                    <span className="badge badge-dim">Empty</span>
                  ) : b.low_confidence ? (
                    <span className="badge badge-warn">Low Sample (&lt;10)</span>
                  ) : (
                    <span className="badge badge-blue">Robust</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
