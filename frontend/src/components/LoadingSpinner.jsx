/** LoadingSpinner.jsx */
export default function LoadingSpinner({ size = 24, label = "Loading…" }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, color: "var(--text-secondary)" }}>
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        style={{ animation: "spin 0.9s linear infinite" }}
      >
        <circle cx="12" cy="12" r="10" stroke="var(--border)" strokeWidth="2.5" />
        <path
          d="M12 2a10 10 0 0 1 10 10"
          stroke="var(--accent)"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
      </svg>
      {label && <span style={{ fontSize: "0.82rem" }}>{label}</span>}
    </div>
  );
}
