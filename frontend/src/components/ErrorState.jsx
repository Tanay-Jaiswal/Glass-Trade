/** ErrorState.jsx — Full-panel error display with optional retry button */
export default function ErrorState({ error, onRetry }) {
  return (
    <div
      className="card animate-in"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 16,
        padding: "40px 32px",
        textAlign: "center",
        borderColor: "rgba(255, 92, 92, 0.25)",
      }}
    >
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: "50%",
          background: "rgba(255, 92, 92, 0.12)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 22,
        }}
      >
        ⚠️
      </div>
      <div>
        <h3 style={{ color: "var(--danger)", marginBottom: 6 }}>Something went wrong</h3>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", maxWidth: 440 }}>
          {error?.message || String(error)}
        </p>
      </div>
      {onRetry && (
        <button className="btn btn-secondary" onClick={onRetry}>
          Try again
        </button>
      )}
      <p style={{ color: "var(--text-dim)", fontSize: "0.75rem" }}>
        Is the backend running? Start it with:{" "}
        <code className="mono">uvicorn main:app --reload</code>
      </p>
    </div>
  );
}
