import type { CSSProperties } from "react";
import { allocateDots } from "./_svg";
import { formatMoney } from "@/components/money";

export type Segment = { value: number; color: string; label: string };

// Per-segment SHAPE — a non-color cue so a colorblind reader can still tell whose
// dots are whose (and map them to the legend). Cycles if there are >4 segments.
const SHAPES: CSSProperties[] = [
  { borderRadius: "50%" },                          // circle
  { borderRadius: 2 },                              // square
  { borderRadius: 2, transform: "rotate(45deg)" },  // diamond
  { borderRadius: "2px 9px 2px 9px" },              // leaf
];
const shapeOf = (i: number): CSSProperties => SHAPES[i % SHAPES.length];

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
  // Accessible text alternative for the (decorative) shape/color encoding.
  const ariaLabel = `Spending split: ${segments.map((s) => `${s.label} ${formatMoney(s.value)}`).join(", ")}`;

  return (
    <div>
      {variant === "matrix" ? (
        <div role="img" aria-label={ariaLabel} style={{ display: "flex", flexWrap: "wrap", gap: 5, margin: "4px 0 12px", maxWidth: 200 }}>
          {segments.flatMap((s, si) =>
            Array.from({ length: counts[si] }, (_, di) => (
              <span
                key={`${si}-${di}`}
                title={s.label}
                style={{ width: 11, height: 11, background: s.color, ...shapeOf(si) }}
              />
            )),
          )}
        </div>
      ) : (
        <div role="img" aria-label={ariaLabel} style={{ display: "flex", height: 26, borderRadius: 8, overflow: "hidden", margin: "4px 0 10px" }}>
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
            <span data-swatch style={{ display: "inline-block", width: 9, height: 9, background: s.color, marginRight: 6, ...shapeOf(si) }} />
            {s.label} <b style={{ color: "var(--fl-ink)", fontWeight: 800, marginLeft: 5 }}>{formatMoney(s.value)}</b>
          </span>
        ))}
      </div>
    </div>
  );
}
