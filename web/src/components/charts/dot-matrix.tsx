import { allocateDots } from "./_svg";
import { formatMoney } from "@/components/money";
import { Legend, shapeAt, shapeStyle } from "./legend";

export type Segment = { value: number; color: string; label: string };

// Per-segment SHAPE (shared with the legend) — a non-color cue so a colorblind
// reader can still tell whose dots are whose and map them to the legend swatch.

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
                style={{ width: 11, height: 11, background: s.color, ...shapeStyle(shapeAt(si)) }}
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
      <Legend
        gap={18}
        items={segments.map((s, si) => ({ label: s.label, color: s.color, total: s.value, shape: shapeAt(si) }))}
      />
    </div>
  );
}
