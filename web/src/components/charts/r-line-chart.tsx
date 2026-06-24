import {
  CartesianGrid,
  Line,
  LineChart as RLineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Fragment } from "react";
import { formatMoney } from "@/components/money";
import { Legend } from "./legend";
import type { LineSeries } from "./line-chart";
import {
  LedgerTooltip,
  SrDataTable,
  colorize,
  monthLabel,
  toRows,
  zeroBaselineDomain,
} from "./chart-kit";

/** Recharts replacement for the hand-rolled LineChart. Same props, but with real
 *  interactivity: a crosshair cursor, the "ledger slip" hover tooltip, keyboard
 *  navigation (Recharts accessibilityLayer), and a screen-reader data table.
 *  Preserves the house conventions — zero-baseline domain, formatMoney labels, the
 *  persona-excluding category ramp, the dashed partial-month "so far" tail, and
 *  horizontal reference/benchmark lines. */
export function LineChart({
  series,
  labels,
  height = 150,
  mode = "smooth",
  legend = true,
  ariaLabel = "Spending by category over time",
  showAxis = true,
  valueFormat = formatMoney,
  partial,
  refLines,
}: {
  series: LineSeries[];
  labels: string[];
  height?: number;
  mode?: "smooth" | "linear";
  legend?: boolean;
  ariaLabel?: string;
  showAxis?: boolean;
  valueFormat?: (n: number) => string;
  partial?: boolean[];
  refLines?: { value: number; label?: string; color?: string }[];
}) {
  if (series.length === 0 || labels.length === 0) {
    return <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>No spending in range.</div>;
  }

  const colored = colorize(series);
  const [domainMin, domainMax] = zeroBaselineDomain(series.flatMap((s) => s.values));
  const rows = toRows(labels, colored, partial);
  const curve = mode === "smooth" ? "monotone" : "linear";

  return (
    <div>
      <div style={{ position: "relative" }}>
        <ResponsiveContainer width="100%" height={height}>
          <RLineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} accessibilityLayer>
            <CartesianGrid vertical={false} stroke="var(--fl-line)" strokeOpacity={0.5} />
            <XAxis
              dataKey="x"
              tickFormatter={(v: string) => (v.length > 7 ? v.slice(5) : v)}
              tick={{ fontSize: 9.5, fontWeight: 600, fill: "var(--fl-muted)" }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
              minTickGap={16}
            />
            {showAxis && (
              <YAxis
                domain={[domainMin, domainMax]}
                tickFormatter={(v: number) => valueFormat(v)}
                tick={{ fontSize: 9, fill: "var(--fl-muted)" }}
                tickLine={false}
                axisLine={false}
                width={48}
              />
            )}
            {/* Heavier zero baseline — never truncate the axis to exaggerate a trend. */}
            {domainMin < 0 && <ReferenceLine y={0} stroke="var(--fl-line)" strokeWidth={1.5} />}

            {(refLines ?? [])
              .filter((r) => r.value > domainMin && r.value <= domainMax)
              .map((r) => (
                <ReferenceLine
                  key={`ref-${r.value}`}
                  y={r.value}
                  stroke={r.color ?? "var(--fl-muted)"}
                  strokeWidth={1}
                  strokeOpacity={0.6}
                  strokeDasharray="5 4"
                  label={
                    r.label
                      ? { value: r.label, position: "right", fontSize: 9, fontWeight: 600, fill: r.color ?? "var(--fl-muted)" }
                      : undefined
                  }
                />
              ))}

            <Tooltip
              cursor={{ stroke: "var(--fl-line)", strokeWidth: 1 }}
              content={<LedgerTooltip valueFormat={valueFormat} />}
            />

            {colored.map((s) => (
              <Fragment key={s.name}>
                <Line
                  name={s.name}
                  dataKey={`${s.name}__s`}
                  type={curve}
                  stroke={s.color}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 3 }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
                <Line
                  name={s.name}
                  dataKey={`${s.name}__d`}
                  type={curve}
                  stroke={s.color}
                  strokeWidth={2}
                  strokeDasharray="5 4"
                  strokeOpacity={0.85}
                  dot={false}
                  activeDot={{ r: 3 }}
                  connectNulls={false}
                  isAnimationActive={false}
                  legendType="none"
                />
              </Fragment>
            ))}
          </RLineChart>
        </ResponsiveContainer>
      </div>

      {/* x-axis "so far" annotation for partial months, mirroring the hand-rolled chart. */}
      {partial?.some(Boolean) && (
        <div style={{ marginTop: 2, fontSize: 9, fontStyle: "italic", color: "var(--fl-muted)", textAlign: "right" }}>
          dashed = {monthLabel(labels[firstTrue(partial)])} onward, still in progress
        </div>
      )}

      {legend && (
        <div style={{ marginTop: 10 }}>
          <Legend items={colored.map((s) => ({ label: s.name, color: s.color, total: s.total }))} />
        </div>
      )}

      <SrDataTable caption={ariaLabel} labels={labels} series={colored} valueFormat={valueFormat} />
    </div>
  );
}

function firstTrue(flags: boolean[]): number {
  const i = flags.findIndex(Boolean);
  return i === -1 ? 0 : i;
}
