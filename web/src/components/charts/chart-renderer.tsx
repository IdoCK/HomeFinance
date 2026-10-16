import { AreaChart } from "./r-area-chart";
import { LineChart } from "./r-line-chart";
import { BarChartR } from "./r-bar-chart";
import { DonutChart } from "./r-donut-chart";
import {
  METRICS,
  resolveChart,
  summarize,
  valueFormatFor,
  type ChartSources,
  type ChartSpec,
} from "@/lib/chart-spec";

/** Renders any ChartSpec by resolving it against the loaded sources and picking
 *  the matching Recharts chart. The single render path shared by Studio's live
 *  preview and the saved "My Charts" board. */
export function ChartRenderer({ spec, sources, height = 220 }: { spec: ChartSpec; sources: ChartSources; height?: number }) {
  const resolved = resolveChart(spec, sources);
  const valueFormat = valueFormatFor(spec.metric);
  const ariaLabel = summarize(spec).replace(/ — as .*/, "");

  if (resolved.empty) {
    return (
      <div style={{ height, display: "grid", placeItems: "center", color: "var(--fl-muted)", fontSize: 13, textAlign: "center" }}>
        Not enough data yet for “{METRICS[spec.metric].label}”.
      </div>
    );
  }

  if (resolved.shape === "category") {
    if (spec.kind === "donut") {
      return <DonutChart slices={resolved.items} height={height} ariaLabel={ariaLabel} valueFormat={valueFormat} />;
    }
    return (
      <BarChartR
        labels={resolved.items.map((d) => d.name)}
        series={[{ name: METRICS[spec.metric].label, values: resolved.items.map((d) => d.value) }]}
        horizontal
        legend={false}
        height={Math.max(height, resolved.items.length * 40)}
        ariaLabel={ariaLabel}
        valueFormat={valueFormat}
      />
    );
  }

  // time-series
  switch (spec.kind) {
    case "area":
      return (
        <AreaChart
          points={resolved.series[0].values.map((value) => ({ value }))}
          xLabels={resolved.labels}
          partial={resolved.partial}
          accent={resolved.series[0].color}
          seriesName={resolved.series[0].name}
          height={height}
          ariaLabel={ariaLabel}
          valueFormat={valueFormat}
        />
      );
    case "bar":
      return (
        <BarChartR
          labels={resolved.labels}
          series={resolved.series}
          height={height}
          ariaLabel={ariaLabel}
          valueFormat={valueFormat}
        />
      );
    case "line":
    default:
      return (
        <LineChart
          labels={resolved.labels}
          series={resolved.series}
          partial={resolved.partial}
          height={height}
          ariaLabel={ariaLabel}
          valueFormat={valueFormat}
        />
      );
  }
}
