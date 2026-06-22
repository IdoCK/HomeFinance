import { useId } from "react";
import { layout, toPath } from "./_svg";

export type AreaPoint = { label?: string; value: number };

/** Hatched cash-flow area chart (the Overview Row-1 signature visual): a gradient
 *  fill + a 45° hatch overlay + a stroked line. Stretches to its container width. */
export function AreaChart({
  points,
  accent = "var(--persona-solid)",
  height = 120,
  mode = "smooth",
  area = true,
  ariaLabel = "Cash flow trend",
  className,
}: {
  points: AreaPoint[];
  accent?: string;
  height?: number;
  mode?: "smooth" | "linear";
  /** Render the gradient + hatch fill. Set false for a bare line (sparkline). */
  area?: boolean;
  ariaLabel?: string;
  className?: string;
}) {
  const w = 600;
  const h = height;
  const pad = 6;
  const pts = layout(points.map((p) => p.value), w, h, pad);
  const line = toPath(pts, mode === "smooth");
  const areaPath =
    area && pts.length > 1
      ? `${line} L ${pts[pts.length - 1].x} ${h} L ${pts[0].x} ${h} Z`
      : "";
  const uid = useId().replace(/:/g, "");
  const fillId = `area-fill-${uid}`;
  const hatchId = `area-hatch-${uid}`;

  return (
    <svg
      className={className}
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
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
      {areaPath && <path d={areaPath} fill={`url(#${fillId})`} />}
      {areaPath && <path d={areaPath} fill={`url(#${hatchId})`} />}
      {line && (
        <path
          d={line}
          fill="none"
          stroke={accent}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
      )}
    </svg>
  );
}
