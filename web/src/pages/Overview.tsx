import { useEffect, useMemo, useState } from "react";
import { getOverview, type Overview as OverviewData } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Money } from "@/components/money";
import { Kpi } from "@/components/kpi";
import { Pill } from "@/components/ui/pill";
import { CardHeaderRow } from "@/components/ui/card";
import { GradientCard } from "@/components/gradient-card";
import { AreaChart } from "@/components/charts/area-chart";
import { LineChart } from "@/components/charts/line-chart";
import { BarChart } from "@/components/charts/bar-chart";
import { StackedBars } from "@/components/charts/stacked-bars";
import { DotMatrix, type Segment } from "@/components/charts/dot-matrix";
import { Loading } from "@/components/loading";

const CARD: React.CSSProperties = { padding: 16 };
const CAT_PALETTE = ["var(--persona-solid)", "var(--persona-spouse)", "var(--saved)", "var(--fl-muted)"];

function personColor(name: string): string {
  return name === "Ido" ? "var(--persona-you)" : name === "Aviv" ? "var(--persona-spouse)" : "var(--persona-solid)";
}

export default function Overview() {
  const { personId, label } = usePersona();
  const [data, setData] = useState<OverviewData | null>(null);
  const [month, setMonth] = useState<string | undefined>(undefined);
  const [cashView, setCashView] = useState<"net" | "trend">("net");

  useEffect(() => {
    let alive = true;
    getOverview({ personId, month }).then((d) => alive && setData(d)).catch(() => alive && setData(null));
    return () => { alive = false; };
  }, [personId, month]);

  const cats = useMemo(
    () => Object.entries(data?.by_category ?? {}).sort((a, b) => b[1] - a[1]),
    [data],
  );

  if (!data) return <Loading rows={4} />;

  const rate = data.savings_rate;
  const months = data.months;
  const idx = months.indexOf(data.month ?? "");
  const step = (delta: number) => {
    const next = months[idx + delta];
    if (next) setMonth(next);
  };

  const series = data.series ?? [];
  // Cash-flow area = net per month; savings-rate bars = savings_rate % per month.
  const areaPoints = series.map((s) => ({ label: s.month, value: s.net }));

  // Trend view: income vs spend dual line (#9) + cumulative saved (#8). Cumulative
  // is the running sum of monthly net — the savings trajectory.
  let run = 0;
  const cumulative = series.map((s) => (run += s.net));
  const trendLabels = series.map((s) => s.month);
  const trendSeries = [
    { name: "Income", values: series.map((s) => s.income), color: "var(--pos)", total: series.reduce((a, s) => a + s.income, 0) },
    { name: "Spending", values: series.map((s) => s.spend), color: "var(--neg)", total: series.reduce((a, s) => a + s.spend, 0) },
    { name: "Saved (cumulative)", values: cumulative, color: "var(--saved)", total: cumulative[cumulative.length - 1] ?? 0 },
  ];
  const rateBars = series.map((s) => ({
    label: s.month.slice(5),
    value: Math.round((s.savings_rate ?? 0) * 100),
    highlight: s.month === data.month,
  }));

  // This-month stacked rows (Income / Spending / Saved), scaled to the largest.
  const denom = Math.max(data.income, data.spend, Math.abs(data.net), 1);
  const stackRows = [
    { label: "Income", value: data.income, pct: (data.income / denom) * 100, color: "var(--pos)" },
    { label: "Spending", value: data.spend, pct: (data.spend / denom) * 100, color: "var(--neg)" },
    { label: "Saved", value: data.net, pct: (Math.abs(data.net) / denom) * 100, color: "var(--saved)" },
  ];

  // Delta vs previous month's net (for the "this month" headline).
  const prevNet = idx > 0 ? series.find((s) => s.month === months[idx - 1])?.net : undefined;
  const delta = prevNet != null ? data.net - prevNet : undefined;

  // Who-spent-what: Joint → per-person split; single-persona → top category split.
  const segments: Segment[] =
    data.split != null
      ? data.split.map((s) => ({ value: s.spend, color: personColor(s.name), label: s.name }))
      : cats.slice(0, 4).map(([name, value], i) => ({ value, color: CAT_PALETTE[i % CAT_PALETTE.length], label: name }));

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <header style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>
          Overview · {label}
        </h1>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <Pill onClick={() => step(-1)} disabled={idx <= 0} aria-label="Previous month">‹</Pill>
          <Pill active>{data.month ?? "—"}</Pill>
          <Pill onClick={() => step(1)} disabled={idx < 0 || idx >= months.length - 1} aria-label="Next month">›</Pill>
        </div>
      </header>

      {data.alerts.length > 0 && (
        <section aria-label="Spending alerts" style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {data.alerts.map((a) => {
            const up = a.direction === "up";
            const color = up ? "var(--neg)" : "var(--pos)";
            const detail = a.new ? "new this month" : `${up ? "↑" : "↓"} ${Math.abs(a.pct ?? 0)}% vs usual`;
            return (
              <span key={a.category} style={{
                display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13,
                padding: "6px 12px", borderRadius: 999,
                background: `color-mix(in srgb, ${color} 12%, transparent)`, color,
              }}>
                <strong style={{ fontWeight: 700 }}>{a.category}</strong> {detail}
              </span>
            );
          })}
        </section>
      )}

      {/* Row 1: cash flow (wide) + this month */}
      <div className="fl-row-2">
        <section className="frosted-card" style={CARD}>
          <CardHeaderRow
            action={
              <div role="group" aria-label="Cash-flow view" style={{ display: "inline-flex", gap: 6 }}>
                <Pill active={cashView === "net"} onClick={() => setCashView("net")}>Net</Pill>
                <Pill active={cashView === "trend"} onClick={() => setCashView("trend")}>Trend</Pill>
              </div>
            }
          >
            Cash flow
          </CardHeaderRow>
          <div style={{ display: "flex", gap: 26, marginBottom: 8 }}>
            <Kpi label="In" testId="income"><Money value={data.income} /></Kpi>
            <Kpi label="Out" testId="spend"><Money value={data.spend} /></Kpi>
            <Kpi label="Net" testId="net" big><Money value={data.net} colored /></Kpi>
          </div>
          {cashView === "net"
            ? <AreaChart points={areaPoints} />
            : <LineChart labels={trendLabels} series={trendSeries} ariaLabel="Income, spending and cumulative savings over time" />}
          <div style={{ marginTop: 10, border: "1px solid var(--fl-line)", background: "var(--fl-frame)", borderRadius: 11, padding: "9px 11px", fontSize: 12, color: "var(--fl-muted)", display: "flex", alignItems: "center", gap: 8 }}>
            <span aria-hidden style={{ width: 14, height: 14, borderRadius: 4, background: "var(--showpiece)", flex: "none" }} />
            {rate == null ? "Add a full month of data to see trends." : `Net ${data.net >= 0 ? "positive" : "negative"} this month — saving ${Math.round(rate * 100)}% of income.`}
          </div>
        </section>

        <section className="frosted-card" style={CARD}>
          <CardHeaderRow>This month</CardHeaderRow>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, margin: "2px 0 6px" }}>
            <span style={{ fontSize: 40, fontWeight: 800, letterSpacing: "-0.04em", lineHeight: 1 }}>
              <Money value={data.net} colored />
            </span>
            {delta != null && (
              <span style={{ fontSize: 11, fontWeight: 700, color: delta >= 0 ? "var(--pos)" : "var(--neg)", background: `color-mix(in srgb, ${delta >= 0 ? "var(--pos)" : "var(--neg)"} 12%, transparent)`, padding: "2px 7px", borderRadius: 999 }}>
                {delta >= 0 ? "▲" : "▼"} {Math.abs(Math.round(delta)).toLocaleString()}
              </span>
            )}
          </div>
          <StackedBars rows={stackRows} />
        </section>
      </div>

      {/* Row 2: savings rate + who spent what + AI insights */}
      <div className="fl-row-3">
        <section className="frosted-card" style={CARD}>
          <CardHeaderRow action={<span style={{ fontSize: 18, fontWeight: 800 }}>{rate == null ? "—" : `${Math.round(rate * 100)}%`}</span>}>
            Savings rate
          </CardHeaderRow>
          {rateBars.length > 0
            ? <BarChart series={rateBars} color="var(--persona-spouse)" highlightColor="var(--persona-spouse)" />
            : <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>No history yet.</div>}
        </section>

        <section className="frosted-card" style={CARD}>
          <CardHeaderRow>{data.split != null ? "Who spent what" : "Top categories"}</CardHeaderRow>
          {segments.length > 0
            ? <DotMatrix segments={segments} />
            : <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>No spending yet.</div>}
        </section>

        <GradientCard
          tag={<><span aria-hidden>✦</span> AI Insights</>}
          headline={<Money value={data.net} />}
        >
          {rate == null
            ? "Import a full month to unlock insights. Only anonymized aggregates ever leave this device."
            : `You saved ${Math.round(rate * 100)}% of income this month. Tap AI Insights to see the anonymized breakdown before sending.`}
        </GradientCard>
      </div>
    </div>
  );
}
