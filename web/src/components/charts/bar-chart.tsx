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
}: {
  series: BarDatum[];
  color?: string;
  highlightColor?: string;
  height?: number;
  /** Color for negative-value bars. Defaults to `var(--neg)`. */
  negativeColor?: string;
}) {
  const hi = highlightColor ?? color;

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
          const barPct = Math.round((Math.abs(d.value) / max) * 100);
          const barPx = Math.round((Math.abs(d.value) / max) * (isNeg ? negH : posH));
          const bg = d.highlight ? hi : isNeg ? negativeColor : color;

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
                    title={`${d.label}: ${d.value}`}
                    style={{
                      height: barPx,
                      minHeight: 2,
                      borderRadius: "6px 6px 3px 3px",
                      background: bg,
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
                    title={`${d.label}: ${d.value}`}
                    style={{
                      height: barPx,
                      minHeight: 2,
                      borderRadius: "3px 3px 6px 6px",
                      background: bg,
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
          </span>
        ))}
      </div>
    </div>
  );
}
