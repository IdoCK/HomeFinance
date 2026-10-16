import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getOverview, getCategoryTrend, type Overview as OverviewData, type CategoryTrend } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { useCurrency } from "@/lib/currency";
import { Money, formatMoney } from "@/components/money";
import { Kpi } from "@/components/kpi";
import { Stepper } from "@/components/ui/stepper";
import { CardHeaderRow } from "@/components/ui/card";
import { GradientCard } from "@/components/gradient-card";
import { LineChart } from "@/components/charts/r-line-chart";
import { StackedBars } from "@/components/charts/stacked-bars";
import { DotMatrix, type Segment } from "@/components/charts/dot-matrix";
import { Banner } from "@/components/ui/banner";
import { Loading } from "@/components/loading";

const CARD: React.CSSProperties = { padding: 16 };
const CAT_PALETTE = ["var(--persona-solid)", "var(--persona-spouse)", "var(--saved)", "var(--fl-muted)"];
const MAX_CAT_LINES = 8; // one per palette color; matches Analysis › category trend

function personColor(name: string): string {
  return name === "Ido" ? "var(--persona-you)" : name === "Aviv" ? "var(--persona-spouse)" : "var(--persona-solid)";
}

export default function Overview() {
  const { personId, label } = usePersona();
  const { currency } = useCurrency();
  const [data, setData] = useState<OverviewData | null>(null);
  const [month, setMonth] = useState<string | undefined>(undefined);
  // Category-over-time trend (all months) — mirrors Analysis › Spending by
  // category over time, surfaced on Overview as the default all-months view.
  const [catTrend, setCatTrend] = useState<CategoryTrend | null>(null);

  useEffect(() => {
    let alive = true;
    getOverview({ personId, month, display: currency }).then((d) => alive && setData(d)).catch(() => alive && setData(null));
    return () => { alive = false; };
  }, [personId, month, currency]);

  useEffect(() => {
    let alive = true;
    setCatTrend(null);
    getCategoryTrend({ personId, filters: {}, display: currency })
      .then((d) => alive && setCatTrend(d))
      .catch(() => alive && setCatTrend({ months: [], series: [] }));
    return () => { alive = false; };
  }, [personId, currency]);

  // Rent dwarfs everything and isn't a discretionary lever, so it's hidden from
  // the Overview category views (Top categories + Spending by category over time).
  const HIDDEN_CATS = ["rent"];
  const isHiddenCat = (name: string) => HIDDEN_CATS.includes(name.trim().toLowerCase());

  const cats = useMemo(
    () =>
      Object.entries(data?.by_category ?? {})
        .filter(([name]) => !isHiddenCat(name))
        .sort((a, b) => b[1] - a[1]),
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
  // Cash-flow trend: income, spending, and net saved — each PER MONTH (not
  // cumulative) so all three lines read on the same monthly basis.
  const trendLabels = series.map((s) => s.month);
  const trendSeries = [
    { name: "Income", values: series.map((s) => s.income), color: "var(--pos)", total: series.reduce((a, s) => a + s.income, 0) },
    { name: "Spending", values: series.map((s) => s.spend), color: "var(--neg)", total: series.reduce((a, s) => a + s.spend, 0) },
    { name: "Saved", values: series.map((s) => s.net), color: "var(--saved)", total: series.reduce((a, s) => a + s.net, 0) },
  ];
  // Savings-rate trajectory: a rolling 3-month average smooths statement-cycle
  // noise, read against the 20% (solid) and 50% (FIRE) benchmarks.
  const ratePct = series.map((s) => Math.round((s.savings_rate ?? 0) * 100));
  const rolling3 = ratePct.map((_, i) => {
    const window = ratePct.slice(Math.max(0, i - 2), i + 1);
    return Math.round(window.reduce((a, b) => a + b, 0) / window.length);
  });

  const latestRoll = rolling3.length ? rolling3[rolling3.length - 1] : null;
  const savingsVerdict =
    latestRoll == null ? null
    : latestRoll >= 50 ? "FIRE pace — saving about half your income."
    : latestRoll >= 20 ? "Above the 20% savings guideline."
    : latestRoll >= 0 ? "Below the 20% savings guideline."
    : "Spending more than you earn.";

  // This-month stacked rows (Income / Spending / Saved), scaled to the largest.
  const denom = Math.max(data.income, data.spend, Math.abs(data.net), 1);
  const stackRows = [
    { label: "Income", value: data.income, pct: (data.income / denom) * 100, color: "var(--pos)" },
    {
      label: "Spending", value: data.spend, pct: (data.spend / denom) * 100, color: "var(--neg)",
      // Committed (recurring bills) is the locked-in floor; discretionary is the
      // part you can actually steer. Solid vs. lightened so the floor reads first.
      segments: [
        { label: "Committed", value: data.committed_spent, color: "var(--neg)" },
        { label: "Discretionary", value: data.discretionary_spent, color: "color-mix(in srgb, var(--neg) 40%, transparent)" },
      ],
    },
    { label: "Saved", value: data.net, pct: (Math.abs(data.net) / denom) * 100, color: "var(--saved)" },
  ];

  // Delta vs previous month's net (for the "this month" headline). A MoM delta is
  // only trustworthy when BOTH months are complete — comparing a partial month to
  // a full one (or two partials) is misleading, so we show "(partial)" instead.
  const prevPoint = idx > 0 ? series.find((s) => s.month === months[idx - 1]) : undefined;
  const prevNet = prevPoint?.net;
  const delta = prevNet != null ? data.net - prevNet : undefined;
  const deltaTrustworthy = delta != null && data.complete && !!prevPoint?.complete;

  // Partial-month notice: the month still in progress (current calendar month) or
  // a month whose data simply doesn't span the full calendar (statement cycles).
  const now = new Date();
  const ym = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  // Parse as a LOCAL date (y, m-1, 1) — `new Date("2026-05-01")` is UTC midnight
  // and shifts to the previous month in timezones behind UTC.
  const [mY, mM] = (data.month ?? "").split("-").map(Number);
  const monthName = data.month
    ? new Date(mY, mM - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" })
    : "This month";
  const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  const partialNote = data.complete
    ? null
    : data.month === ym(now)
      ? `${monthName} is still in progress — day ${now.getDate()} of ${daysInMonth}. These figures will keep changing.`
      : `${monthName} is a partial month — the data doesn't cover the full calendar month, so totals understate it.`;

  // The "are we okay this month?" verdict — promoted from a buried footnote to a
  // prominent, color+icon status line.
  const verdict = rate == null
    ? { tone: "info" as const, icon: "•", text: "Add a full month of data to see where you stand." }
    : data.net >= 0
      ? { tone: "good" as const, icon: "✓", text: `You're in the black${!data.complete ? " so far" : ""} — saving ${Math.round(rate * 100)}% of income.` }
      : { tone: "bad" as const, icon: "!", text: `Spending is outpacing income${!data.complete ? " so far" : ""} this month.` };

  // Who-spent-what is a Joint-only question: the dot-matrix splits the month's
  // spend by person. In a single-persona view there's no "who", so we show a
  // compact ranked bar of that person's top categories instead (and leave the
  // category-over-time drill-down to Analysis).
  const personaSegments: Segment[] =
    data.split != null
      ? data.split.map((s) => ({ value: s.spend, color: personColor(s.name), label: s.name }))
      : [];
  const maxCat = cats[0]?.[1] ?? 1;
  const catRows = cats.slice(0, 5).map(([name, value], i) => ({
    label: name, value, pct: (value / maxCat) * 100, color: CAT_PALETTE[i % CAT_PALETTE.length],
  }));

  // AI-Insights teaser: lead with a genuine insight (the month's biggest spending
  // shift, else the top category) rather than a third copy of the net number.
  const topAlert = data.alerts[0];
  const topCat = cats[0];
  const aiHeadline = topAlert?.category ?? (topCat ? topCat[0] : undefined);
  const aiBody =
    rate == null
      ? "Import a full month to unlock insights. Only anonymized aggregates ever leave this device."
      : topAlert
        ? `${topAlert.category} is ${topAlert.direction === "up" ? "up" : "down"}${topAlert.pct != null ? ` ${Math.abs(topAlert.pct)}%` : ""} versus your usual — your biggest shift this month. Tap AI Insights for the anonymized breakdown.`
        : topCat
          ? `${topCat[0]} led your spending at ${formatMoney(topCat[1])} this month. Tap AI Insights for the anonymized breakdown.`
          : `You saved ${Math.round(rate * 100)}% of income this month. Tap AI Insights to see the anonymized breakdown before sending.`;

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <header style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>
          Overview · {label}
        </h1>
      </header>

      <Banner tone={verdict.tone} icon={<span style={{ fontWeight: 800, fontSize: 14, lineHeight: 1 }}>{verdict.icon}</span>}>
        <strong style={{ fontWeight: 700 }}>{verdict.text}</strong>
      </Banner>

      {partialNote && (
        <Banner
          tone="warn"
          dashed
          icon={<span style={{ width: 12, height: 12, borderRadius: 3, border: "1.5px dashed currentColor", display: "inline-block" }} />}
        >
          {partialNote}
        </Banner>
      )}

      {data.safe_to_spend != null && (
        <section className="frosted-card" aria-label="Safe to spend" style={{ padding: 18, display: "grid", gap: 8 }}>
          {/* The month stepper lives here and drives every month-specific block on
              the page (Safe to spend, the verdict, alerts, This month, Top
              categories). The all-months charts ignore it. */}
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--fl-muted)" }}>
              Safe to spend{!data.complete ? " (so far)" : ""}
            </span>
            <div style={{ marginLeft: "auto" }}>
              <Stepper
                label={data.month ?? "—"}
                onPrev={() => step(-1)}
                onNext={() => step(1)}
                prevDisabled={idx <= 0}
                nextDisabled={idx < 0 || idx >= months.length - 1}
                prevLabel="Previous month"
                nextLabel="Next month"
              />
            </div>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "baseline", gap: "6px 20px" }}>
            <span data-testid="safe-to-spend" style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.04em", lineHeight: 1 }}>
              <Money value={data.safe_to_spend} colored />
            </span>
            <span style={{ fontSize: 12.5, color: "var(--fl-muted)", marginLeft: "auto" }}>
              <Money value={data.income} /> in − <Money value={data.committed} /> committed − <Money value={data.discretionary_spent} /> spent
            </span>
          </div>
          {data.bills_due && data.bills_due.count > 0 && (
            <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>
              {data.bills_due.count} {data.bills_due.count === 1 ? "bill" : "bills"} (~<Money value={data.bills_due.amount} />) still due this month
            </div>
          )}
        </section>
      )}

      {data.uncategorized && data.uncategorized.count > 0 && (
        <Link
          to="/transactions?category=Uncategorized"
          style={{
            justifySelf: "start", width: "fit-content", display: "inline-flex", alignItems: "center", gap: 6,
            fontSize: 12.5, fontWeight: 600, textDecoration: "none",
            padding: "6px 12px", borderRadius: 999, border: "1px solid var(--fl-line)",
            background: "var(--fl-frame)", color: "var(--fl-ink)",
          }}
        >
          <Money value={data.uncategorized.amount} /> across {data.uncategorized.count} uncategorized →
        </Link>
      )}

      {data.alerts.length > 0 && (
        <section aria-label="Spending alerts" style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {data.alerts.map((a) => {
            const up = a.direction === "up";
            const color = up ? "var(--neg-ink)" : "var(--pos-ink)";
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

      {/* Row 1: cash-flow trend (all months, wide) + this month */}
      <div className="fl-row-2">
        <section className="frosted-card" style={CARD}>
          <CardHeaderRow>Cash flow</CardHeaderRow>
          {/* In/Out are the selected month's totals (the trend below is all
              months), so the month is labelled right here next to them. */}
          <div style={{ display: "flex", alignItems: "baseline", gap: 26, marginBottom: 8 }}>
            <Kpi label="In" testId="income"><Money value={data.income} /></Kpi>
            <Kpi label="Out" testId="spend"><Money value={data.spend} /></Kpi>
            <span style={{ marginLeft: "auto", fontSize: 12, fontWeight: 600, color: "var(--fl-muted)" }}>{monthName}</span>
          </div>
          <LineChart labels={trendLabels} series={trendSeries} ariaLabel="Income, spending and net saved per month" />
          {/* Overview shows the all-months trend; deeper month/category
              comparison lives in Analysis. Redirect rather than duplicate it. */}
          <Link to="/analysis" style={{ display: "inline-block", marginTop: 12, fontSize: 12, fontWeight: 600, color: "var(--persona-solid)", textDecoration: "none" }}>
            Compare months & categories in Analysis →
          </Link>
        </section>

        <section className="frosted-card" style={CARD}>
          <CardHeaderRow>{monthName}</CardHeaderRow>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, margin: "2px 0 6px" }}>
            <span data-testid="net" style={{ fontSize: 40, fontWeight: 800, letterSpacing: "-0.04em", lineHeight: 1 }}>
              <Money value={data.net} colored />
            </span>
            {delta != null && (deltaTrustworthy ? (
              <span style={{ fontSize: 11, fontWeight: 700, color: delta >= 0 ? "var(--pos-ink)" : "var(--neg-ink)", background: `color-mix(in srgb, ${delta >= 0 ? "var(--pos)" : "var(--neg)"} 12%, transparent)`, padding: "2px 7px", borderRadius: 999 }}>
                {delta >= 0 ? "▲" : "▼"} {Math.abs(Math.round(delta)).toLocaleString()}
              </span>
            ) : (
              <span title="A month in this comparison is incomplete" style={{ fontSize: 11, fontWeight: 700, color: "var(--fl-muted)", background: "var(--fl-frame)", padding: "2px 7px", borderRadius: 999, border: "1px dashed var(--fl-line)" }}>
                vs last month (partial)
              </span>
            ))}
          </div>
          <StackedBars rows={stackRows} />
        </section>
      </div>

      {/* All-months category trend — mirrors Analysis › Spending by category
          over time, surfaced here as the default all-months category view. */}
      <section className="frosted-card" style={CARD}>
        <CardHeaderRow action={<span style={{ fontSize: 11, fontWeight: 600, color: "var(--fl-muted)" }}>All months</span>}>
          Spending by category over time
        </CardHeaderRow>
        {(() => {
          if (catTrend == null) return <Loading rows={2} />;
          const series = catTrend.series.filter((s) => !isHiddenCat(s.name));
          if (series.length === 0)
            return <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>No spending history yet.</div>;
          return (
            <LineChart
              labels={catTrend.months}
              series={series.slice(0, MAX_CAT_LINES).map((s) => ({ name: s.name, values: s.values, total: s.total }))}
              ariaLabel="Spending by category over time, across all months"
            />
          );
        })()}
        <Link to="/analysis" style={{ display: "inline-block", marginTop: 12, fontSize: 12, fontWeight: 600, color: "var(--persona-solid)", textDecoration: "none" }}>
          Compare months & categories in Analysis →
        </Link>
      </section>

      {/* Row 2: savings rate + who spent what + AI insights */}
      <div className="fl-row-3">
        <section className="frosted-card" style={CARD}>
          <CardHeaderRow action={<span style={{ fontSize: 18, fontWeight: 800 }}>{rate == null ? "—" : `${Math.round(rate * 100)}%`}</span>}>
            Savings rate
          </CardHeaderRow>
          {rolling3.length > 0 ? (
            <>
              <LineChart
                labels={trendLabels}
                series={[{ name: "3-mo avg", values: rolling3, color: "var(--persona-spouse)" }]}
                refLines={[
                  { value: 20, label: "20%", color: "var(--fl-muted)" },
                  { value: 50, label: "50% FIRE", color: "var(--saved)" },
                ]}
                valueFormat={(n) => `${Math.round(n)}%`}
                legend={false}
                height={120}
                ariaLabel="Savings-rate trajectory (3-month average) against 20% and 50% benchmarks"
              />
              {savingsVerdict && <div style={{ marginTop: 8, fontSize: 12, color: "var(--fl-muted)" }}>{savingsVerdict}</div>}
            </>
          ) : (
            <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>No history yet.</div>
          )}
        </section>

        <section className="frosted-card" style={CARD}>
          <CardHeaderRow action={<span style={{ fontSize: 11, fontWeight: 600, color: "var(--fl-muted)" }}>{monthName}</span>}>
            {data.split != null ? "Who spent what" : "Top categories"}
          </CardHeaderRow>
          {data.split != null
            ? (personaSegments.length > 0
                ? <DotMatrix segments={personaSegments} />
                : <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>No spending yet.</div>)
            : (catRows.length > 0
                ? <StackedBars rows={catRows} />
                : <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>No spending yet.</div>)}
        </section>

        <GradientCard
          ariaLabel="AI insights"
          tag={<><span aria-hidden>✦</span> AI Insights</>}
          headline={aiHeadline}
        >
          {aiBody}
        </GradientCard>
      </div>
    </div>
  );
}
