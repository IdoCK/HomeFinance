import { allocateDots } from "./_svg";
import { formatMoney } from "@/components/money";

export type Segment = { value: number; color: string; label: string };

/** "Who spent what" — the Joint signature. Allocates `dots` proportionally
 *  across segments (largest-remainder, so counts sum to `dots`) and renders a
 *  flex-wrap dot grid + a legend with bold totals. `variant="bar"` falls back
 *  to a single split bar (single-persona / narrow contexts). */
export function DotMatrix({
  segments,
  dots = 21,
  variant = "matrix",
}: {
  segments: Segment[];
  dots?: number;
  variant?: "matrix" | "bar";
}) {
  const counts = allocateDots(segments.map((s) => s.value), dots);
  const total = segments.reduce((a, s) => a + Math.max(0, s.value), 0);

  return (
    <div>
      {variant === "matrix" ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5, margin: "4px 0 12px", maxWidth: 200 }}>
          {segments.flatMap((s, si) =>
            Array.from({ length: counts[si] }, (_, di) => (
              <span
                key={`${si}-${di}`}
                title={s.label}
                style={{ width: 11, height: 11, borderRadius: "50%", background: s.color }}
              />
            )),
          )}
        </div>
      ) : (
        <div style={{ display: "flex", height: 26, borderRadius: 8, overflow: "hidden", margin: "4px 0 10px" }}>
          {segments.map((s, si) => (
            <div
              key={si}
              title={s.label}
              style={{
                width: total > 0 ? `${(Math.max(0, s.value) / total) * 100}%` : "0%",
                background: s.color,
              }}
            />
          ))}
        </div>
      )}
      <div style={{ display: "flex", gap: 18, fontSize: 11.5, color: "var(--fl-muted)", flexWrap: "wrap" }}>
        {segments.map((s, si) => (
          <span key={si} style={{ display: "inline-flex", alignItems: "center" }}>
            <span style={{ display: "inline-block", width: 9, height: 9, borderRadius: "50%", background: s.color, marginRight: 6 }} />
            {s.label} <b style={{ color: "var(--fl-ink)", fontWeight: 800, marginLeft: 5 }}>{formatMoney(s.value)}</b>
          </span>
        ))}
      </div>
    </div>
  );
}
