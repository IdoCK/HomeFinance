import { useEffect, useState, type CSSProperties } from "react";
import { getRecurring, type RecurringAnomaly, type RecurringCharge, type RecurringData } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { useCurrency } from "@/lib/currency";
import { formatMoney } from "@/components/money";
import { Loading } from "@/components/loading";

const ANOMALY: Record<RecurringAnomaly["type"], { label: string; color: string }> = {
  price_change: { label: "price change", color: "#F59E0B" },
  possibly_canceled: { label: "maybe canceled", color: "var(--fl-muted)" },
  new: { label: "new", color: "var(--persona-solid)" },
};

const badge: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "2px 10px",
  fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--fl-muted)",
};

function ChargeRow({ c }: { c: RecurringCharge }) {
  return (
    <section className="frosted-card" style={{ padding: 18, display: "grid", gridTemplateColumns: "1fr auto", gap: 8, alignItems: "center" }}>
      <div style={{ display: "grid", gap: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 700 }}>{c.vendor}</span>
          <span style={badge}>{c.cadence}</span>
          <span style={{ ...badge, color: c.kind === "fixed" ? "var(--fl-muted)" : "#F59E0B" }}>{c.kind}</span>
          {c.category && <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>{c.category}</span>}
        </div>
        <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>next ~{c.next_expected} · {c.count} charges</div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 20, fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>
          {formatMoney(c.monthly_cost)}<span style={{ fontSize: 12, fontWeight: 500, color: "var(--fl-muted)" }}>/mo</span>
        </div>
        <div style={{ fontSize: 12, color: "var(--fl-muted)", fontVariantNumeric: "tabular-nums" }}>{formatMoney(c.annual_cost)}/yr</div>
        <div title={`${Math.round(c.confidence * 100)}% confidence`} style={{ marginTop: 6, height: 4, width: 80, marginLeft: "auto", borderRadius: 999, background: "var(--fl-line)" }}>
          <div style={{ height: 4, width: `${Math.round(c.confidence * 100)}%`, borderRadius: 999, background: "var(--persona)" }} />
        </div>
      </div>
    </section>
  );
}

export default function Recurring() {
  const { personId, label } = usePersona();
  const { currency } = useCurrency();
  const [data, setData] = useState<RecurringData | null>(null);

  useEffect(() => {
    let alive = true;
    getRecurring({ personId, display: currency }).then((d) => alive && setData(d)).catch(() => alive && setData(null));
    return () => { alive = false; };
  }, [personId, currency]);

  if (!data) return <Loading />;

  const { charges, committed, anomalies } = data;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", fontSize: 24, margin: 0 }}>Recurring · {label}</h1>
        <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>subscriptions & regular bills</span>
      </header>

      <section className="frosted-card" style={{ padding: 28, display: "flex", alignItems: "baseline", gap: 16, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--fl-muted)" }}>Committed each month</div>
          <div data-testid="committed-total" style={{ fontSize: 40, fontWeight: 800, letterSpacing: "-0.03em" }}>{formatMoney(committed.total)}</div>
          <div style={{ color: "var(--fl-muted)", fontVariantNumeric: "tabular-nums" }}>· {formatMoney(committed.total * 12)} / yr</div>
        </div>
        <div style={{ marginLeft: "auto", textAlign: "right", color: "var(--fl-muted)", fontSize: 13 }}>
          <div>{charges.length} active {charges.length === 1 ? "charge" : "charges"}</div>
          <div>{formatMoney(committed.fixed)} fixed · {formatMoney(committed.variable)} variable</div>
        </div>
      </section>

      {anomalies.length > 0 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {anomalies.map((a, i) => (
            <span key={`${a.vendor}-${a.type}-${i}`} style={{ ...badge, color: ANOMALY[a.type].color, borderColor: "currentColor" }}>
              {a.vendor} · {ANOMALY[a.type].label}
            </span>
          ))}
        </div>
      )}

      {charges.length === 0 ? (
        <section className="frosted-card" style={{ padding: 32, textAlign: "center", color: "var(--fl-muted)" }}>
          No recurring charges yet. They appear once a vendor bills at a steady cadence three or more times.
        </section>
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {charges.map((c) => <ChargeRow key={c.vendor} c={c} />)}
        </div>
      )}
    </div>
  );
}
