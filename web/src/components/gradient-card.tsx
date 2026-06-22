import type { ReactNode } from "react";

/** The AI-Insights showpiece — the ONE place the --showpiece gradient is used
 *  (the design spends its boldness here and nowhere else). Glassy highlight
 *  overlay, white text, optional pill tag + headline. */
export function GradientCard({
  tag,
  headline,
  children,
}: {
  tag?: ReactNode;
  headline?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div
      style={{
        position: "relative",
        borderRadius: "var(--radius-card)",
        padding: 18,
        color: "#fff",
        overflow: "hidden",
        background: "var(--showpiece)",
        boxShadow: "0 18px 40px -20px rgba(168,85,247,.5)",
      }}
    >
      <div
        aria-hidden
        style={{ position: "absolute", inset: 0, background: "radial-gradient(80% 60% at 20% 100%, rgba(255,255,255,.19), transparent)" }}
      />
      {tag && (
        <span
          style={{
            position: "relative", display: "inline-flex", alignItems: "center", gap: 6,
            fontSize: 10.5, fontWeight: 700, background: "rgba(255,255,255,.18)",
            padding: "4px 9px", borderRadius: 999, marginBottom: 24,
          }}
        >
          {tag}
        </span>
      )}
      {headline != null && (
        <div style={{ position: "relative", fontSize: 38, fontWeight: 800, letterSpacing: "-0.03em", lineHeight: 1 }}>
          {headline}
        </div>
      )}
      {children != null && (
        <div style={{ position: "relative", fontSize: 11.5, lineHeight: 1.5, marginTop: 8, color: "rgba(255,255,255,.9)" }}>
          {children}
        </div>
      )}
    </div>
  );
}
