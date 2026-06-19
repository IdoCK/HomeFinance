import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { getInsightsPreview, generateInsights, type InsightsPreview } from "@/lib/api";
import { usePersona } from "@/lib/persona";

// The one surface in the app allowed the showpiece gradient (design spec §3.3).
const hero: CSSProperties = {
  background: "var(--showpiece)",
  borderRadius: 24,
  padding: "32px 28px",
  color: "#fff",
  position: "relative",
  overflow: "hidden",
  boxShadow: "0 20px 60px -24px rgba(168,85,247,0.55)",
};

export default function Insights() {
  const { personId, label } = usePersona();
  const [preview, setPreview] = useState<InsightsPreview | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Reload the privacy preview whenever the persona changes — the payload differs
  // per person (and Joint sends the whole household).
  const loadPreview = useCallback(() => {
    setResult(null);
    getInsightsPreview(personId).then(setPreview).catch(() => setPreview(null));
  }, [personId]);
  useEffect(() => { loadPreview(); }, [loadPreview]);

  const hasKey = preview?.has_key ?? false;

  const generate = async () => {
    setLoading(true);
    try {
      const { text } = await generateInsights(personId);
      setResult(text);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "grid", gap: 16, maxWidth: 860 }}>
      <section style={hero}>
        <div style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.1em", opacity: 0.85 }}>
          AI Insights · {label}
        </div>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", fontSize: 34, margin: "8px 0 6px" }}>
          What the numbers say
        </h1>
        <p style={{ margin: 0, maxWidth: 560, lineHeight: 1.5, opacity: 0.92 }}>
          A coach reads your finances and suggests where to adjust. Only anonymized
          aggregates leave your machine — never merchants, transactions, names, or notes.
        </p>
        <div style={{ marginTop: 20, display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <button
            onClick={generate}
            disabled={!hasKey || loading}
            style={{
              border: "none", borderRadius: 999, padding: "10px 20px", fontWeight: 700,
              fontSize: 14, cursor: hasKey && !loading ? "pointer" : "not-allowed",
              background: "rgba(255,255,255,0.95)", color: "#16181D",
              opacity: hasKey ? 1 : 0.6,
            }}
          >
            {loading ? "Thinking…" : "Generate insights"}
          </button>
          {!hasKey && (
            <span style={{ fontSize: 13, opacity: 0.92 }}>
              Set ANTHROPIC_API_KEY to enable live insights.
            </span>
          )}
        </div>
      </section>

      <details className="frosted-card" style={{ padding: 16 }}>
        <summary style={{ cursor: "pointer", fontSize: 13, fontWeight: 600, color: "var(--fl-muted)" }}>
          See exactly what's sent
        </summary>
        <pre style={{
          marginTop: 12, fontSize: 12, lineHeight: 1.5, whiteSpace: "pre-wrap",
          wordBreak: "break-word", color: "var(--fl-ink)", fontFamily: "ui-monospace, monospace",
        }}>
          {preview?.payload ?? "Loading…"}
        </pre>
      </details>

      {result !== null && (
        <section className="frosted-card" style={{ padding: 24 }}>
          <div style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--fl-muted)", marginBottom: 12 }}>
            Your insights
          </div>
          <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.6, color: "var(--fl-ink)" }}>
            {result}
          </div>
          <div style={{ marginTop: 16, fontSize: 12, color: "var(--fl-muted)" }}>
            Generated from anonymized aggregates only.
          </div>
        </section>
      )}
    </div>
  );
}
