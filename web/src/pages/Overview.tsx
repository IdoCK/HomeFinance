import { useEffect, useMemo, useState } from "react";
import { getOverview, type Overview as OverviewData } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Money, formatMoney } from "@/components/money";

export default function Overview() {
  const { personId, label } = usePersona();
  const [data, setData] = useState<OverviewData | null>(null);
  const [month, setMonth] = useState<string | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    getOverview({ personId, month }).then((d) => alive && setData(d)).catch(() => alive && setData(null));
    return () => { alive = false; };
  }, [personId, month]);

  const cats = useMemo(
    () => Object.entries(data?.by_category ?? {}).sort((a, b) => b[1] - a[1]),
    [data],
  );
  const maxCat = cats.length ? cats[0][1] : 1;

  if (!data) return <div style={{ color: "var(--fl-muted)" }}>Loading…</div>;

  const rate = data.savings_rate;
  const idx = data.months.indexOf(data.month ?? "");
  const step = (delta: number) => {
    const next = data.months[idx + delta];
    if (next) setMonth(next);
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Overview · {label}</h1>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <button onClick={() => step(-1)} disabled={idx <= 0} aria-label="Previous month">‹</button>
          <span style={{ fontWeight: 700 }}>{data.month ?? "—"}</span>
          <button onClick={() => step(1)} disabled={idx < 0 || idx >= data.months.length - 1} aria-label="Next month">›</button>
        </div>
      </header>

      <section className="frosted-card" style={{ padding: 24, display: "flex", gap: 32 }}>
        <Kpi label="Income" testId="income"><Money value={data.income} /></Kpi>
        <Kpi label="Spending" testId="spend"><Money value={data.spend} /></Kpi>
        <Kpi label="Net" testId="net" big><Money value={data.net} colored /></Kpi>
        <Kpi label="Savings rate" testId="savings">
          {rate == null ? "—" : `${Math.round(rate * 100)}%`}
        </Kpi>
      </section>

      <section className="frosted-card" style={{ padding: 24 }}>
        <h2 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--fl-muted)" }}>By category</h2>
        <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
          {cats.map(([name, amount]) => (
            <div key={name} style={{ display: "grid", gridTemplateColumns: "140px 1fr 90px", alignItems: "center", gap: 12 }}>
              <span>{name}</span>
              <div style={{ height: 10, borderRadius: 999, background: "var(--fl-line)" }}>
                <div style={{ height: 10, borderRadius: 999, width: `${(amount / maxCat) * 100}%`, background: "var(--persona)" }} />
              </div>
              <span style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{formatMoney(amount)}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function Kpi({ label, testId, big = false, children }: { label: string; testId: string; big?: boolean; children: React.ReactNode }) {
  return (
    <div style={{ display: "grid", gap: 4 }}>
      <span style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--fl-muted)" }}>{label}</span>
      <span
        data-testid={testId}
        style={big ? { fontSize: 32, fontWeight: 800, letterSpacing: "-0.03em" } : { fontSize: 18, fontWeight: 700 }}
      >
        {children}
      </span>
    </div>
  );
}
