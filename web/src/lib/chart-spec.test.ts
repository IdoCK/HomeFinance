import { describe, expect, test } from "vitest";
import { METRICS, resolveChart, summarize, valueFormatFor, type ChartSources, type ChartSpec } from "./chart-spec";

const spec = (over: Partial<ChartSpec> = {}): ChartSpec => ({ id: "d", title: "", metric: "net", kind: "area", months: 12, ...over });

const sources: ChartSources = {
  overview: {
    month: "2026-06", months: ["2026-04", "2026-05", "2026-06"], income: 0, spend: 0, net: 0, savings_rate: 0.2,
    complete: false, by_category: { Housing: 2000, Groceries: 500, Empty: 0 }, alerts: [],
    series: [
      { month: "2026-04", income: 5000, spend: 4000, net: 1000, savings_rate: 0.2, complete: true },
      { month: "2026-05", income: 5000, spend: 3000, net: 2000, savings_rate: 0.4, complete: true },
      { month: "2026-06", income: 5000, spend: 4500, net: 500, savings_rate: 0.1, complete: false },
    ],
    split: null, uncategorized: { count: 0, amount: 0 }, safe_to_spend: 0, committed: 0,
    committed_spent: 0, discretionary_spent: 0, bills_due: { count: 0, amount: 0 },
  } as ChartSources["overview"],
  networth: { summary: { assets: 0, liabilities: 0, net: 0 }, delta: null, accounts: [], split: null,
    trend: [{ date: "2026-05-31", assets: 0, liabilities: 0, net: 20000 }, { date: "2026-06-30", assets: 0, liabilities: 0, net: 22000 }],
  } as ChartSources["networth"],
  categoryTrend: { months: ["2026-04", "2026-05", "2026-06"], series: [{ name: "Housing", values: [2000, 2000, 2000], total: 6000 }] },
};

describe("summarize", () => {
  test("compiles a windowed time metric into one sentence", () => {
    expect(summarize(spec({ metric: "net", kind: "area", months: 6 }))).toBe("Net saved, last 6 months — as an area chart.");
  });
  test("uses 'this month' for single-period metrics", () => {
    expect(summarize(spec({ metric: "category_share", kind: "donut" }))).toBe("Category share, this month — as a donut.");
  });
});

describe("resolveChart", () => {
  test("net: one series with a per-month partial flag", () => {
    const r = resolveChart(spec({ metric: "net" }), sources);
    expect(r.shape).toBe("time");
    if (r.shape !== "time") return;
    expect(r.series).toHaveLength(1);
    expect(r.series[0].values).toEqual([1000, 2000, 500]);
    expect(r.partial).toEqual([false, false, true]); // June is incomplete
  });

  test("savings_rate: percent points and percent formatter", () => {
    const r = resolveChart(spec({ metric: "savings_rate", kind: "line" }), sources);
    if (r.shape !== "time") throw new Error("expected time");
    expect(r.series[0].values).toEqual([20, 40, 10]);
    expect(valueFormatFor("savings_rate")(40)).toBe("40%");
  });

  test("category_share: positive slices only, sorted desc", () => {
    const r = resolveChart(spec({ metric: "category_share", kind: "donut" }), sources);
    if (r.shape !== "category") throw new Error("expected category");
    expect(r.items.map((i) => i.name)).toEqual(["Housing", "Groceries"]); // zero "Empty" dropped
  });

  test("net_worth needs two snapshots", () => {
    const r = resolveChart(spec({ metric: "net_worth" }), { ...sources, networth: { ...sources.networth!, trend: [sources.networth!.trend[0]] } });
    expect(r.empty).toBe(true);
  });

  test("window slices the trailing months", () => {
    const r = resolveChart(spec({ metric: "net", months: 2 }), sources);
    if (r.shape !== "time") throw new Error("expected time");
    expect(r.labels).toEqual(["2026-05", "2026-06"]);
  });

  test("every metric declares a valid default kind", () => {
    for (const [, def] of Object.entries(METRICS)) {
      expect(def.kinds.length).toBeGreaterThan(0);
    }
  });
});
