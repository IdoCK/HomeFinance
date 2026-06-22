export type BarDatum = { label: string; value: number; highlight?: boolean };

/** Savings-rate style vertical bar history. One bar may be highlighted (the
 *  current month). X-axis labels render beneath. */
export function BarChart({
  series,
  color = "var(--persona-solid)",
  highlightColor,
  height = 96,
}: {
  series: BarDatum[];
  color?: string;
  highlightColor?: string;
  height?: number;
}) {
  const max = Math.max(1, ...series.map((d) => Math.abs(d.value)));
  const hi = highlightColor ?? color;
  return (
    <div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 7, height }}>
        {series.map((d, i) => {
          const pct = Math.round((Math.abs(d.value) / max) * 100);
          return (
            <div
              key={`${d.label}-${i}`}
              title={`${d.label}: ${d.value}`}
              style={{
                flex: 1,
                height: `${pct}%`,
                minHeight: 2,
                borderRadius: "6px 6px 3px 3px",
                background: d.highlight ? hi : color,
                opacity: d.highlight ? 1 : 0.55,
                transition: "height 240ms ease",
              }}
            />
          );
        })}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 9.5, fontWeight: 600, color: "var(--fl-muted)" }}>
        {series.map((d, i) => (
          <span key={`${d.label}-x-${i}`} style={{ flex: 1, textAlign: "center" }}>{d.label}</span>
        ))}
      </div>
    </div>
  );
}
