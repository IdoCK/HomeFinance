import { useId, useRef, useState, useEffect } from "react";
import { axisTicks, layout, scale, splitPartialPath, toPath } from "./_svg";
import { formatMoney } from "@/components/money";

export type AreaPoint = { label?: string; value: number };

/** Hatched cash-flow area chart (the Overview Row-1 signature visual): a gradient
 *  fill + a 45° hatch overlay + a stroked line. Stretches to its container width.
 *
 *  Aspect-ratio fix: We use a ResizeObserver to measure the container's actual
 *  pixel width and set the SVG viewBox to match. This means every pixel maps
 *  1:1 in x and y, so trend slopes are truthful. When ResizeObserver is absent
 *  (jsdom, SSR) we fall back to w=600 so tests and SSR don't crash. We keep
 *  preserveAspectRatio="xMidYMid meet" (letterbox default) as a safety net for
 *  the brief window before the first measurement fires.
 */
export function AreaChart({
  points,
  accent = "var(--persona-solid)",
  height = 120,
  mode = "smooth",
  area = true,
  ariaLabel = "Cash flow trend",
  className,
  showAxis = area,
  valueFormat = formatMoney,
  partial,
}: {
  points: AreaPoint[];
  accent?: string;
  height?: number;
  mode?: "smooth" | "linear";
  /** Render the gradient + hatch fill. Set false for a bare line (sparkline). */
  area?: boolean;
  ariaLabel?: string;
  className?: string;
  /** Show y-axis gridlines and value labels. Defaults to `area` (true for
   *  the full chart, false for bare-line sparklines). */
  showAxis?: boolean;
  /** Format a numeric tick/value label. Defaults to formatMoney. */
  valueFormat?: (n: number) => string;
  /** Per-point in-progress flag. The trailing run of `true` points renders as a
   *  dashed segment ("this month isn't settled yet"). Defaults to all-complete. */
  partial?: boolean[];
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
  const pad = 6;

  const values = points.map((p) => p.value);
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);

  const pts = layout(values, w, h, pad);
  const smooth = mode === "smooth";
  const line = toPath(pts, smooth);
  // Split the stroked line so the in-progress tail draws dashed.
  const { solid: solidPts, partial: partialPts } = splitPartialPath(pts, partial);
  const solidLine = toPath(solidPts, smooth);
  const partialLine = toPath(partialPts, smooth);
  const lastIsPartial = (partial?.[values.length - 1] ?? false) && values.length > 0;
  const areaPath =
    area && pts.length > 1
      ? `${line} L ${pts[pts.length - 1].x} ${h} L ${pts[0].x} ${h} Z`
      : "";
  const uid = useId().replace(/:/g, "");
  const fillId = `area-fill-${uid}`;
  const hatchId = `area-hatch-${uid}`;

  // Compute y-axis tick screen positions.
  // `scale()` already returns size/2 when max===min, so no inline guard needed here —
  // using max+1 would cause gridlines to land at a different y than the data points.
  const inner = h - pad * 2;
  const ticks = showAxis && values.length > 0 ? axisTicks(min, max) : [];
  const tickY = (v: number) =>
    Math.round(h - pad - scale(v, min, max, inner));

  // Last point value label
  const lastPt = pts[pts.length - 1];
  const lastVal = values[values.length - 1];

  return (
    <svg
      ref={containerRef}
      className={className}
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="xMidYMid meet"
      style={{ display: "block", width: "100%", height }}
      role="img"
      aria-label={ariaLabel}
    >
      <defs>
        <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={accent} stopOpacity="0.28" />
          <stop offset="100%" stopColor={accent} stopOpacity="0" />
        </linearGradient>
        <pattern id={hatchId} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke={accent} strokeWidth="1" strokeOpacity="0.14" />
        </pattern>
      </defs>

      {/* y-axis gridlines — rendered as <line> elements, NOT <path>, so the path
          count stays equal to the number of data series (1 for AreaChart) */}
      {ticks.map((v) => {
        const y = tickY(v);
        return (
          <line
            key={`grid-${v}`}
            x1={0}
            y1={y}
            x2={w}
            y2={y}
            stroke={v === 0 ? "var(--fl-ink, #334155)" : "var(--fl-line, #e2e8f0)"}
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

      {areaPath && <path d={areaPath} fill={`url(#${fillId})`} />}
      {areaPath && <path d={areaPath} fill={`url(#${hatchId})`} />}
      {solidLine && (
        <path
          d={solidLine}
          fill="none"
          stroke={accent}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      )}
      {/* In-progress tail: dashed so the month-not-yet-settled reads at a glance */}
      {partialLine && (
        <path
          d={partialLine}
          fill="none"
          stroke={accent}
          strokeWidth="2"
          strokeDasharray="5 4"
          strokeOpacity={0.85}
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      )}

      {/* Last-point value label */}
      {showAxis && lastPt && values.length > 0 && (
        <text
          x={Math.min(lastPt.x, w - 4)}
          y={lastPt.y - 6}
          fontSize={10}
          fill={accent}
          textAnchor="end"
          fontWeight="600"
          fontFamily="inherit"
        >
          {valueFormat(lastVal)}{lastIsPartial ? " (so far)" : ""}
        </text>
      )}
    </svg>
  );
}
