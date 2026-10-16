import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useId } from "react";
import { formatMoney } from "@/components/money";
import { LedgerTooltip, firstPartialIndex, kCompact, zeroBaselineDomain } from "./chart-kit";

export type AreaPoint = { label?: string; value: number };

/** Recharts replacement for the hand-rolled AreaChart: the Frosted-Ledger
 *  cash-flow signature (gradient fill + 45° hatch overlay + stroked line) with a
 *  dashed in-progress tail, milestone reference lines, and now a crosshair + the
 *  "ledger slip" hover tooltip. `area=false` gives a bare line (the sparkline).
 *  Preserves: zero-baseline domain, formatMoney labels, the partial "so far" tail. */
export function AreaChart({
  points,
  accent = "var(--persona-solid)",
  height = 120,
  mode = "smooth",
  area = true,
  ariaLabel = "Cash flow trend",
  seriesName = "",
  showAxis = area,
  interactive = true,
  valueFormat = formatMoney,
  partial,
  xLabels,
  milestones,
}: {
  points: AreaPoint[];
  accent?: string;
  height?: number;
  mode?: "smooth" | "linear";
  /** Render the gradient + hatch fill. Set false for a bare line (sparkline). */
  area?: boolean;
  ariaLabel?: string;
  /** Label for the single series in the hover tooltip (e.g. "Net saved"). */
  seriesName?: string;
  showAxis?: boolean;
  /** Crosshair + hover tooltip. Off for tiny inline sparklines. */
  interactive?: boolean;
  valueFormat?: (n: number) => string;
  partial?: boolean[];
  xLabels?: string[];
  milestones?: number[];
}) {
  const uid = useId().replace(/:/g, "");
  const fillId = `fill-${uid}`;
  const hatchId = `hatch-${uid}`;
  const curve = mode === "smooth" ? "monotone" : "linear";

  if (points.length === 0) {
    return <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>No data in range.</div>;
  }

  const values = points.map((p) => p.value);
  const [domainMin, domainMax] = zeroBaselineDomain(values);

  // Split the stroke into a settled prefix and a dashed in-progress tail that share
  // a join point (same contract as the hand-rolled splitPartialPath).
  const fp = firstPartialIndex(partial);
  const solidEnd = fp === -1 ? values.length - 1 : fp - 1;
  const dashStart = fp === -1 ? Number.POSITIVE_INFINITY : Math.max(0, fp - 1);
  const rows = points.map((p, i) => ({
    x: xLabels?.[i] ?? p.label ?? String(i),
    __partial: partial?.[i] ?? false,
    __v: p.value,
    __s: i <= solidEnd ? p.value : null,
    __d: i >= dashStart ? p.value : null,
  }));

  return (
    <div role={interactive ? undefined : "img"} aria-label={ariaLabel} style={{ width: "100%" }}>
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={rows} margin={{ top: 8, right: area ? 8 : 0, bottom: 0, left: 0 }} accessibilityLayer>
        <defs>
          <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={accent} stopOpacity={0.28} />
            <stop offset="100%" stopColor={accent} stopOpacity={0} />
          </linearGradient>
          <pattern id={hatchId} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke={accent} strokeWidth={1} strokeOpacity={0.14} />
          </pattern>
        </defs>

        {showAxis && <CartesianGrid vertical={false} stroke="var(--fl-line)" strokeOpacity={0.5} />}
        {(xLabels?.length ?? 0) > 0 && (
          <XAxis
            dataKey="x"
            tick={{ fontSize: 9.5, fontWeight: 600, fill: "var(--fl-muted)" }}
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
            minTickGap={12}
          />
        )}
        {showAxis && (
          <YAxis
            domain={[domainMin, domainMax]}
            tickFormatter={(v: number) => valueFormat(v)}
            tick={{ fontSize: 9, fill: "var(--fl-muted)" }}
            tickLine={false}
            axisLine={false}
            width={46}
          />
        )}
        {domainMin < 0 && <ReferenceLine y={0} stroke="var(--fl-ink)" strokeOpacity={0.5} strokeWidth={1.5} />}

        {(milestones ?? [])
          .filter((m) => m > domainMin && m <= domainMax)
          .map((m) => (
            <ReferenceLine
              key={`ms-${m}`}
              y={m}
              stroke="var(--saved)"
              strokeWidth={1}
              strokeOpacity={0.5}
              strokeDasharray="6 4"
              label={{ value: kCompact(m), position: "right", fontSize: 9, fontWeight: 600, fill: "var(--saved)" }}
            />
          ))}

        {area && <Area dataKey="__v" type={curve} stroke="none" fill={`url(#${fillId})`} isAnimationActive={false} />}
        {area && <Area dataKey="__v" type={curve} stroke="none" fill={`url(#${hatchId})`} isAnimationActive={false} />}

        <Line name={seriesName} dataKey="__s" type={curve} stroke={accent} strokeWidth={2} dot={false} activeDot={{ r: 3 }} connectNulls={false} isAnimationActive={false} />
        <Line name={seriesName} dataKey="__d" type={curve} stroke={accent} strokeWidth={2} strokeDasharray="5 4" strokeOpacity={0.85} dot={false} activeDot={{ r: 3 }} connectNulls={false} isAnimationActive={false} />

        {interactive && (
          <Tooltip cursor={{ stroke: "var(--fl-line)", strokeWidth: 1 }} content={<LedgerTooltip valueFormat={valueFormat} />} />
        )}
      </ComposedChart>
    </ResponsiveContainer>
    </div>
  );
}
