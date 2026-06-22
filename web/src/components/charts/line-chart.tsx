import { categoryColor, layoutShared, toPath } from "./_svg";
import { formatMoney } from "@/components/money";

export type LineSeries = { name: string; values: number[]; color?: string; total?: number };

/** Multi-series line chart on one shared y-domain — spending-by-category over
 *  time (the old Analysis trend). Hand-rolled SVG like AreaChart; one stroked
 *  line per series in the brand category ramp, with month ticks beneath and a
 *  legend of bold totals (matching DotMatrix). Stretches to container width. */
export function LineChart({
  series,
  labels,
  height = 150,
  mode = "smooth",
  legend = true,
  ariaLabel = "Spending by category over time",
}: {
  series: LineSeries[];
  /** x-axis tick labels (one per data point); rendered beneath the plot. */
  labels: string[];
  height?: number;
  mode?: "smooth" | "linear";
  legend?: boolean;
  ariaLabel?: string;
}) {
  const w = 600;
  const h = height;
  const pad = 8;
  const colored = series.map((s, i) => ({ ...s, color: s.color ?? categoryColor(i) }));
  const pts = layoutShared(colored.map((s) => s.values), w, h, pad);

  if (series.length === 0 || labels.length === 0) {
    return <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>No spending in range.</div>;
  }

  return (
    <div>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        style={{ display: "block", width: "100%", height }}
        role="img"
        aria-label={ariaLabel}
      >
        {colored.map((s, i) => (
          <path
            key={s.name}
            d={toPath(pts[i], mode === "smooth")}
            fill="none"
            stroke={s.color}
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 9.5, fontWeight: 600, color: "var(--fl-muted)" }}>
        {labels.map((l, i) => (
          <span key={`${l}-${i}`} style={{ flex: 1, textAlign: i === 0 ? "left" : i === labels.length - 1 ? "right" : "center" }}>
            {l.length > 7 ? l.slice(5) : l}
          </span>
        ))}
      </div>
      {legend && (
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 10, fontSize: 11.5, color: "var(--fl-muted)" }}>
          {colored.map((s) => (
            <span key={s.name} style={{ display: "inline-flex", alignItems: "center" }}>
              <span style={{ display: "inline-block", width: 9, height: 9, borderRadius: "50%", background: s.color, marginRight: 6 }} />
              {s.name}
              {s.total != null && (
                <b style={{ color: "var(--fl-ink)", fontWeight: 800, marginLeft: 5 }}>{formatMoney(s.total)}</b>
              )}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
