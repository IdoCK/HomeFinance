import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatMoney } from "@/components/money";
import { Legend } from "./legend";
import { LedgerTooltip, colorize, monthLabel, zeroBaselineDomain, type LineSeries } from "./chart-kit";

/** Recharts grouped/single bar chart, themed to the Frosted Ledger. Shares the
 *  LineSeries shape with the line chart, so one bucket/category = one bar group.
 *  Horizontal layout (category names down the side) suits category comparisons;
 *  vertical suits months across the bottom. Ledger-slip hover tooltip, bold-total
 *  legend, zero-baseline domain, formatMoney labels. */
export function BarChartR({
  series,
  labels,
  height = 180,
  horizontal = false,
  legend = true,
  ariaLabel = "Comparison",
  valueFormat = formatMoney,
}: {
  series: LineSeries[];
  /** One label per category/month (the x — or y, when horizontal). */
  labels: string[];
  height?: number;
  /** Bars grow rightward with categories stacked down the side. */
  horizontal?: boolean;
  legend?: boolean;
  ariaLabel?: string;
  valueFormat?: (n: number) => string;
}) {
  if (series.length === 0 || labels.length === 0) {
    return <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>No data in range.</div>;
  }

  const colored = colorize(series);
  const [domainMin, domainMax] = zeroBaselineDomain(series.flatMap((s) => s.values));
  const rows = labels.map((x, i) => {
    const row: Record<string, string | number> = { x };
    for (const s of colored) row[s.name] = s.values[i] ?? 0;
    return row;
  });

  const valueAxis = (
    <YAxis
      type={horizontal ? "category" : "number"}
      {...(horizontal
        ? { dataKey: "x", width: 96, tick: { fontSize: 10, fill: "var(--fl-ink)" } }
        : { domain: [domainMin, domainMax], tickFormatter: (v: number) => valueFormat(v), width: 48, tick: { fontSize: 9, fill: "var(--fl-muted)" } })}
      tickLine={false}
      axisLine={false}
    />
  );
  const catAxis = (
    <XAxis
      type={horizontal ? "number" : "category"}
      {...(horizontal
        ? { domain: [domainMin, domainMax], tickFormatter: (v: number) => valueFormat(v), tick: { fontSize: 9, fill: "var(--fl-muted)" } }
        : { dataKey: "x", tick: { fontSize: 9.5, fontWeight: 600, fill: "var(--fl-muted)" }, interval: "preserveStartEnd" as const, minTickGap: 8 })}
      tickLine={false}
      axisLine={false}
    />
  );

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart
          data={rows}
          layout={horizontal ? "vertical" : "horizontal"}
          margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
          barCategoryGap={horizontal ? "22%" : "28%"}
          accessibilityLayer
          aria-label={ariaLabel}
        >
          <CartesianGrid stroke="var(--fl-line)" strokeOpacity={0.5} {...(horizontal ? { horizontal: false } : { vertical: false })} />
          {catAxis}
          {valueAxis}
          <Tooltip cursor={{ fill: "var(--fl-line)", fillOpacity: 0.35 }} content={<LedgerTooltip valueFormat={valueFormat} />} />
          {colored.map((s) => (
            <Bar key={s.name} dataKey={s.name} name={s.name} fill={s.color} radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]} isAnimationActive={false} />
          ))}
        </BarChart>
      </ResponsiveContainer>
      {legend && (
        <div style={{ marginTop: 10 }}>
          <Legend items={colored.map((s) => ({ label: s.name, color: s.color, total: s.total }))} />
        </div>
      )}
      <table style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)", whiteSpace: "nowrap", border: 0 }}>
        <caption>{ariaLabel}</caption>
        <thead>
          <tr>
            <th scope="col">Category</th>
            {colored.map((s) => <th key={s.name} scope="col">{s.name}</th>)}
          </tr>
        </thead>
        <tbody>
          {labels.map((lab, i) => (
            <tr key={lab}>
              <th scope="row">{monthLabel(lab)}</th>
              {colored.map((s) => <td key={s.name}>{valueFormat(s.values[i] ?? 0)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
