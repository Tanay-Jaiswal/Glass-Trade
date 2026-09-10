/** InsightCard.jsx — Plain-language calibration insight */
export default function InsightCard({ insight, methodologyNote }) {
  if (!insight) return null;
  return (
    <div
      className="card animate-in animate-delay-2"
      style={{ borderColor: "rgba(245, 197, 66, 0.2)", background: "rgba(16, 24, 44, 0.85)" }}
    >
      <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
        <div
          style={{
            flexShrink: 0,
            width: 36,
            height: 36,
            borderRadius: "50%",
            background: "var(--gold-dim)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 18,
          }}
        >
          💡
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ color: "var(--gold)", marginBottom: 6 }}>Calibration Insight</h3>
          <p style={{ color: "var(--text-primary)", lineHeight: 1.65 }}>{insight}</p>

          {methodologyNote && (
            <details style={{ marginTop: 12 }}>
              <summary
                style={{
                  cursor: "pointer",
                  fontSize: "0.75rem",
                  color: "var(--text-dim)",
                  userSelect: "none",
                }}
              >
                Methodology note ▸
              </summary>
              <p
                style={{
                  marginTop: 8,
                  fontSize: "0.78rem",
                  color: "var(--text-secondary)",
                  lineHeight: 1.6,
                  padding: "8px 0",
                }}
              >
                {methodologyNote}
              </p>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}
