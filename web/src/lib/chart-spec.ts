// The chart "language" behind Studio: a small, declarative ChartSpec that both
// the builder and the saved-board render from, plus the pure resolver that turns
// a spec + the already-fetched data sources into a renderable shape. Keeping this
// pure (no React, no fetching) makes the builder's live preview and the board
// share exactly one code path.
import type { Overview, NetWorthData, CategoryTrend } from "@/lib/api";
import type { LineSeries } from "@/components/charts/chart-kit";
import { formatMoney } from "@/components/money";

export type ChartMetric =
  | "net"
  | "income_spend"
  | "savings_rate"
  | "net_worth"
  | "category_trend"
  | "category_share";

export type ChartKind = "line" | "area" | "bar" | "donut";

export type ChartSpec = {
  id: string;
  title: string;
  metric: ChartMetric;
  kind: ChartKind;
  /** Trailing window in months (ignored by single-period metrics). */
  months: number;
};

type MetricDef = {
  label: string;
  shape: "time" | "category";
  kinds: ChartKind[];
  percent?: boolean;
  /** Single-period metrics hide the time-window control. */
  windowed: boolean;
};

export const METRICS: Record<ChartMetric, MetricDef> = {
  net: { label: "Net saved", shape: "time", kinds: ["area", "line", "bar"], windowed: true },
  income_spend: { label: "Income vs spending", shape: "time", kinds: ["line", "bar"], windowed: true },
  savings_rate: { label: "Savings rate", shape: "time", kinds: ["line", "bar"], percent: true, windowed: true },
  net_worth: { label: "Net worth", shape: "time", kinds: ["area", "line"], windowed: true },
  category_trend: { label: "Spending by category", shape: "time", kinds: ["line", "bar"], windowed: true },
  category_share: { label: "Category share", shape: "category", kinds: ["donut", "bar"], windowed: false },
};

export const METRIC_ORDER: ChartMetric[] = [
  "net", "income_spend", "savings_rate", "net_worth", "category_trend", "category_share",
];

export const WINDOW_OPTIONS = [3, 6, 12, 24];

export function defaultKind(metric: ChartMetric): ChartKind {
  return METRICS[metric].kinds[0];
}

/** A chart spec compiles to one plain-English sentence — the builder's signature
 *  readout and the default title. */
export function summarize(spec: ChartSpec): string {
  const m = METRICS[spec.metric];
  const kindPhrase: Record<ChartKind, string> = {
    line: "a line chart",
    area: "an area chart",
    bar: "a bar chart",
    donut: "a donut",
  };
  const when = m.windowed ? `, last ${spec.months} months` : ", this month";
  return `${m.label}${when} — as ${kindPhrase[spec.kind]}.`;
}

export function pctFormat(n: number): string {
  return `${Math.round(n)}%`;
}

export function valueFormatFor(metric: ChartMetric): (n: number) => string {
  return METRICS[metric].percent ? pctFormat : formatMoney;
}

export type ChartSources = {
  overview: Overview | null;
  networth: NetWorthData | null;
  categoryTrend: CategoryTrend | null;
};

export type ResolvedChart =
  | { shape: "time"; labels: string[]; series: LineSeries[]; partial?: boolean[]; empty: boolean }
  | { shape: "category"; items: { name: string; value: number }[]; empty: boolean };

const MAX_CATEGORY_SERIES = 8;

function tail<T>(arr: T[], n: number): T[] {
  return n > 0 && arr.length > n ? arr.slice(arr.length - n) : arr;
}

/** Pure: turn a spec + fetched sources into a renderable shape. Never throws;
 *  returns `empty: true` when the data isn't there yet. */
export function resolveChart(spec: ChartSpec, sources: ChartSources): ResolvedChart {
  const { overview, networth, categoryTrend } = sources;
  const n = spec.months;

  switch (spec.metric) {
    case "net": {
      const s = tail(overview?.series ?? [], n);
      return {
        shape: "time",
        labels: s.map((p) => p.month),
        series: [{ name: "Net saved", values: s.map((p) => p.net), color: "var(--persona-solid)", total: s.reduce((a, p) => a + p.net, 0) }],
        partial: s.map((p) => !p.complete),
        empty: s.length === 0,
      };
    }
    case "income_spend": {
      const s = tail(overview?.series ?? [], n);
      return {
        shape: "time",
        labels: s.map((p) => p.month),
        series: [
          { name: "Income", values: s.map((p) => p.income), color: "var(--pos)", total: s.reduce((a, p) => a + p.income, 0) },
          { name: "Spending", values: s.map((p) => p.spend), color: "var(--neg)", total: s.reduce((a, p) => a + p.spend, 0) },
        ],
        partial: s.map((p) => !p.complete),
        empty: s.length === 0,
      };
    }
    case "savings_rate": {
      const s = tail(overview?.series ?? [], n);
      return {
        shape: "time",
        labels: s.map((p) => p.month),
        series: [{ name: "Savings rate", values: s.map((p) => Math.round((p.savings_rate ?? 0) * 100)), color: "var(--persona-spouse)" }],
        partial: s.map((p) => !p.complete),
        empty: s.length === 0,
      };
    }
    case "net_worth": {
      const t = tail(networth?.trend ?? [], n);
      return {
        shape: "time",
        labels: t.map((p) => p.date.slice(0, 7)),
        series: [{ name: "Net worth", values: t.map((p) => p.net), color: "var(--persona-solid)" }],
        empty: t.length < 2,
      };
    }
    case "category_trend": {
      const months = tail(categoryTrend?.months ?? [], n);
      const offset = (categoryTrend?.months.length ?? 0) - months.length;
      const series = (categoryTrend?.series ?? [])
        .slice(0, MAX_CATEGORY_SERIES)
        .map((s) => ({ name: s.name, values: s.values.slice(offset), total: s.total }));
      return { shape: "time", labels: months, series, empty: series.length === 0 || months.length === 0 };
    }
    case "category_share": {
      const items = Object.entries(overview?.by_category ?? {})
        .map(([name, value]) => ({ name, value }))
        .filter((d) => d.value > 0)
        .sort((a, b) => b.value - a.value)
        .slice(0, MAX_CATEGORY_SERIES);
      return { shape: "category", items, empty: items.length === 0 };
    }
  }
}
