import { useRef, useState, useEffect } from "react";
import { axisTicks, categoryColor, layoutShared, scale, toPath } from "./_svg";
import { formatMoney } from "@/components/money";

export type LineSeries = { name: string; values: number[]; color?: string; total?: number };

/** Multi-series line chart on one shared y-domain — spending-by-category over
 *  time (the old Analysis trend). Hand-rolled SVG like AreaChart; one stroked
 *  line per series in the brand category ramp, with month ticks beneath and a
 *  legend of bold totals (matching DotMatrix). Stretches to container width.
 *
 *  Aspect-ratio fix: uses ResizeObserver to measure the real container width so
 *  viewBox x-pixels match displayed pixels and slopes are truthful. Falls back
 *  to 600 in jsdom / SSR where ResizeObserver is absent.
 */
export function LineChart({
  series,
  labels,
  height = 150,
  mode = "smooth",
  legend = true,
  ariaLabel = "Spending by category over time",
  showAxis = true,
  valueFormat = formatMoney,
}: {
  series: LineSeries[];
  /** x-axis tick labels (one per data point); rendered beneath the plot. */
  labels: string[];
  height?: number;
  mode?: "smooth" | "linear";
  legend?: boolean;
  ariaLabel?: string;
  /** Show y-axis gridlines and value labels. Defaults to true. */
  showAxis?: boolean;
  /** Format a numeric tick/value label. Defaults to formatMoney. */
  valueFormat?: (n: number) => string;
}) {
  const containerRef = useRef<SVGSVGElement>(null);
  const [measuredW, setMeasuredW] = useState<number>(600);

  useEffect(() => {
    if (typeof ResizeObserver === "undefined" || !containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w && w > 0) setMeasuredW(Math.round(w));
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const w = measuredW;
  const h = height;
  const pad = 8;

  const colored = series.map((s, i) => ({ ...s, color: s.color ?? categoryColor(i) }));
  const pts = layoutShared(colored.map((s) => s.values), w, h, pad);

  if (series.length === 0 || labels.length === 0) {
    return <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>No spending in range.</div>;
  }

  // Shared domain (same as layoutShared uses).
  // `scale()` already returns size/2 when domainMax===domainMin, so no effectiveMax
  // guard — diverging guards here would misalign ticks from layoutShared's data points.
  const allVals = series.flatMap((s) => s.values);
  const domainMin = Math.min(0, ...allVals);
  const domainMax = Math.max(0, ...allVals);
  const inner = h - pad * 2;

  const ticks = showAxis ? axisTicks(domainMin, domainMax) : [];
  const tickY = (v: number) =>
    Math.round(h - pad - scale(v, domainMin, domainMax, inner));

  return (
    <div>
      <svg
        ref={containerRef}
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="xMidYMid meet"
        style={{ display: "block", width: "100%", height }}
        role="img"
        aria-label={ariaLabel}
      >
        {/* y-axis gridlines — <line> elements so path count = series count */}
        {ticks.map((v) => {
          const y = tickY(v);
          return (
            <line
              key={`grid-${v}`}
              x1={0}
              y1={y}
              x2={w}
              y2={y}
              stroke="var(--fl-line, #e2e8f0)"
              strokeWidth={v === 0 ? 1.5 : 1}
              strokeOpacity={v === 0 ? 0.7 : 0.4}
              strokeDasharray={v === 0 ? undefined : "3 3"}
            />
          );
        })}

        {/* y-axis tick labels */}
        {ticks.map((v) => {
          const y = tickY(v);
          return (
            <text
              key={`label-${v}`}
              x={4}
              y={y - 3}
              fontSize={9}
              fill="var(--fl-muted, #94a3b8)"
              fontFamily="inherit"
              dominantBaseline="auto"
            >
              {valueFormat(v)}
            </text>
          );
        })}

        {/* Series paths — one <path> per series; must stay as paths for the
            existing test assertion path count === series count */}
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

        {/* Last-point value labels, one per series */}
        {showAxis &&
          colored.map((s, i) => {
            const seriesPts = pts[i];
            if (!seriesPts || seriesPts.length === 0) return null;
            const lastPt = seriesPts[seriesPts.length - 1];
            const lastVal = s.values[s.values.length - 1];
            return (
              <text
                key={`val-${s.name}`}
                x={Math.min(lastPt.x, w - 4)}
                y={lastPt.y - 6}
                fontSize={9}
                fill={s.color}
                textAnchor="end"
                fontWeight="600"
                fontFamily="inherit"
              >
                {valueFormat(lastVal)}
              </text>
            );
          })}
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
