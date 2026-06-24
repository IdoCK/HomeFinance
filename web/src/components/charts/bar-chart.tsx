import type { CSSProperties } from "react";

export type BarDatum = { label: string; value: number; highlight?: boolean };

/** Savings-rate style vertical bar history. One bar may be highlighted (the
 *  current month). X-axis labels render beneath.
 *
 *  Signed domain: positive values grow UP from the zero baseline; negative
 *  values grow DOWN. A visible zero line separates the two halves.
 *  All-positive series behave like the original (baseline sits at the bottom,
 *  all bars above it). */
export function BarChart({
  series,
  color = "var(--persona-solid)",
  highlightColor,
  height = 96,
  negativeColor = "var(--neg)",
  partial,
}: {
  series: BarDatum[];
  color?: string;
  highlightColor?: string;
  height?: number;
  /** Color for negative-value bars. Defaults to `var(--neg)`. */
  negativeColor?: string;
  /** Per-bar in-progress flag. A `true` bar renders hatched + dashed (the month
   *  is still accumulating) instead of a solid fill. Defaults to all-complete. */
  partial?: boolean[];
}) {
  const hi = highlightColor ?? color;

  // A partial (in-progress) bar reads as provisional: a 45° hatch over a dashed
  // outline rather than a solid fill — the Frosted Ledger "not yet settled" cue.
  const fillStyle = (bg: string, isPartial: boolean): CSSProperties =>
    isPartial
      ? {
          background: "transparent",
          backgroundImage: `repeating-linear-gradient(45deg, ${bg} 0, ${bg} 2px, transparent 2px, transparent 6px)`,
          outline: `1px dashed ${bg}`,
          outlineOffset: -1,
        }
      : { background: bg };

  // Signed domain: max absolute value across the full series.
  const max = Math.max(1, ...series.map((d) => Math.abs(d.value)));

  // Fraction of total height dedicated to the positive half vs. negative half.
  // For an all-positive series: maxPos === max, maxNeg === 0 → posH === height.
  const maxPos = Math.max(0, ...series.map((d) => d.value));
  const maxNeg = Math.max(0, ...series.map((d) => -d.value));
  const totalDomain = maxPos + maxNeg || 1;

  const posH = Math.round((maxPos / totalDomain) * height); // px for positive half
  const negH = height - posH;                               // px for negative half

  return (
    <div>
      {/*
        Layout: a row of per-datum columns.
        Each column is a flex-column with:
          [spacer to push bar to bottom] [bar] [zero line gap] [bar] [spacer]
        We achieve "bars grow from center" by flexing each column.
      */}
      <div style={{ display: "flex", gap: 7, height: height + 1 /* +1 for zero line */ }}>
        {series.map((d, i) => {
          const isNeg = d.value < 0;
          const sign: "neg" | "pos" = isNeg ? "neg" : "pos";
          const isPartial = partial?.[i] ?? false;
          const barPct = Math.round((Math.abs(d.value) / max) * 100);
          const barPx = Math.round((Math.abs(d.value) / max) * (isNeg ? negH : posH));
          const bg = d.highlight ? hi : isNeg ? negativeColor : color;
          const partialAttr = isPartial ? "true" : undefined;
          const titleText = `${d.label}: ${d.value}${isPartial ? " (so far)" : ""}`;

          return (
            <div
              key={`${d.label}-${i}`}
              style={{ flex: 1, display: "flex", flexDirection: "column" }}
            >
              {/* Positive half: spacer + bar aligned to baseline */}
              <div style={{ height: posH, display: "flex", flexDirection: "column", justifyContent: "flex-end" }}>
                {!isNeg && barPct > 0 && (
                  <div
                    data-sign={sign}
                    data-partial={partialAttr}
                    title={titleText}
                    style={{
                      height: barPx,
                      minHeight: 2,
                      borderRadius: "6px 6px 3px 3px",
                      ...fillStyle(bg, isPartial),
                      opacity: d.highlight ? 1 : 0.55,
                      transition: "height 240ms ease",
                    }}
                  />
                )}
                {/* Zero-value positive placeholder keeps data-sign consistent */}
                {!isNeg && barPct === 0 && (
                  <div data-sign="pos" style={{ height: 0 }} />
                )}
              </div>

              {/* Zero line pixel */}
              <div data-zero-line style={{ height: 1, background: "var(--fl-muted, #888)", opacity: 0.4 }} />

              {/* Negative half: bar grows downward from baseline */}
              <div style={{ height: negH, display: "flex", flexDirection: "column", justifyContent: "flex-start" }}>
                {isNeg && barPct > 0 && (
                  <div
                    data-sign={sign}
                    data-partial={partialAttr}
                    title={titleText}
                    style={{
                      height: barPx,
                      minHeight: 2,
                      borderRadius: "3px 3px 6px 6px",
                      ...fillStyle(bg, isPartial),
                      opacity: d.highlight ? 1 : 0.55,
                      transition: "height 240ms ease",
                    }}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* X-axis labels */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginTop: 6,
          fontSize: 9.5,
          fontWeight: 600,
          color: "var(--fl-muted)",
        }}
      >
        {series.map((d, i) => (
          <span key={`${d.label}-x-${i}`} style={{ flex: 1, textAlign: "center" }}>
            {d.label}
            {(partial?.[i] ?? false) && (
              <span style={{ display: "block", fontSize: 8, fontStyle: "italic", opacity: 0.85 }}>
                so far
              </span>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}
