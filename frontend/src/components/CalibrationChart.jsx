import React from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
} from "recharts";

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0]?.payload;
    return (
      <div className="custom-tooltip card" style={{ padding: "12px 16px", minWidth: 220 }}>
        <p style={{ fontWeight: 700, color: "var(--text-primary)", marginBottom: 6 }}>
          Bucket: {data.bucket_label}
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: "0.8rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ color: "var(--text-dim)" }}>Predicted (Avg):</span>
            <span className="font-mono">{(data.predicted_prob * 100).toFixed(1)}%</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ color: "var(--text-dim)" }}>Realized Freq:</span>
            <span className="font-mono" style={{ color: "var(--accent)" }}>
              {data.realized_freq != null ? `${(data.realized_freq * 100).toFixed(1)}%` : "N/A"}
            </span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span style={{ color: "var(--text-dim)" }}>Markets Count:</span>
            <span className="font-mono">{data.count}</span>
          </div>
          {data.low_confidence && (
            <div style={{ marginTop: 4, color: "var(--warning)", fontSize: "0.75rem" }}>
              ⚠️ Low sample size (&lt; 10 markets)
            </div>
          )}
        </div>
      </div>
    );
  }
  return null;
};

export default function CalibrationChart({ buckets = [] }) {
  if (!buckets || buckets.length === 0) {
    return (
      <div className="card text-center" style={{ padding: "40px" }}>
        <p className="text-muted">No bucket data available. Sync market data first.</p>
      </div>
    );
  }

  // Format chart data with percentage points
  const chartData = buckets.map((b) => ({
    ...b,
    predictedPct: b.predicted_prob != null ? b.predicted_prob * 100 : null,
    realizedPct: b.realized_freq != null ? b.realized_freq * 100 : null,
    idealPct: b.predicted_prob != null ? b.predicted_prob * 100 : null,
  }));

  return (
    <div className="card animate-in" style={{ width: "100%", height: "460px", display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <h2>Reliability Diagram</h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.82rem" }}>
            Predicted Implied Probability vs. Realized Frequency
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="badge badge-blue">10-Bin Discretization</span>
          <span className="badge badge-dim">Real Glimpse Markets</span>
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 20, right: 20, bottom: 20, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(56, 100, 200, 0.15)" />
            <XAxis
              dataKey="bucket_label"
              stroke="var(--text-dim)"
              fontSize={11}
              tickLine={false}
            />
            <YAxis
              domain={[0, 100]}
              stroke="var(--text-dim)"
              fontSize={11}
              unit="%"
              tickLine={false}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: "0.8rem", paddingTop: "12px" }}
              formatter={(value) => <span style={{ color: "var(--text-secondary)" }}>{value}</span>}
            />

            {/* Ideal diagonal calibration reference line */}
            <ReferenceLine
              segment={[
                { x: chartData[0]?.bucket_label, y: 5 },
                { x: chartData[chartData.length - 1]?.bucket_label, y: 95 },
              ]}
              stroke="var(--chart-perfect)"
              strokeDasharray="4 4"
              label={{
                value: "Perfect Calibration (x=y)",
                fill: "var(--chart-perfect)",
                position: "insideTopLeft",
                fontSize: 11,
              }}
            />

            {/* Market count represented as volume bars */}
            <Bar
              dataKey="count"
              name="Sample Size (Markets)"
              fill="rgba(79, 143, 255, 0.2)"
              radius={[4, 4, 0, 0]}
              yAxisId={0}
            />

            {/* Realized frequency curve */}
            <Line
              type="monotone"
              dataKey="realizedPct"
              name="Realized Frequency (%)"
              stroke="var(--accent)"
              strokeWidth={3}
              dot={{ fill: "var(--accent)", r: 5 }}
              activeDot={{ r: 7, stroke: "#fff", strokeWidth: 2 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div
        style={{
          marginTop: 12,
          paddingTop: 10,
          borderTop: "1px solid var(--border)",
          display: "flex",
          justifyContent: "space-between",
          fontSize: "0.75rem",
          color: "var(--text-dim)",
        }}
      >
        <span>Points above diagonal = Underconfident · Points below = Overconfident</span>
        <span>Muted bars denote bucket sample size</span>
      </div>
    </div>
  );
}
