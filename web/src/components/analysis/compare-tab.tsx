import { useEffect, useState } from "react";
import {
  getCompare,
  type AnalysisFilters, type CompareResult, type ComparePreset, type CompareMetric,
} from "@/lib/api";
import { Pill } from "@/components/ui/pill";
import { Kpi } from "@/components/kpi";
import { formatMoney } from "@/components/money";
import { useCurrency } from "@/lib/currency";
import { BarChartR } from "@/components/charts/r-bar-chart";
import { Loading } from "@/components/loading";

/** Compare tab: split the filtered universe into two buckets (weekday/weekend or
 *  the two most recent months) and rank categories side-by-side. The measure
 *  toggle switches between bucket totals and per-day normalization, which makes
 *  windows of unequal length comparable (the old Compare tab's two controls). */
export function CompareTab({ personId, filters }: { personId?: number; filters: AnalysisFilters }) {
  const { currency } = useCurrency();
  const [preset, setPreset] = useState<ComparePreset>("weekdays_weekends");
  const [metric, setMetric] = useState<CompareMetric>("spend");
  const [data, setData] = useState<CompareResult | null>(null);

  useEffect(() => {
    let alive = true;
    setData(null);
    getCompare({ personId, preset, metric, filters, display: currency })
      .then((d) => alive && setData(d))
      .catch(() => alive && setData(null));
    return () => { alive = false; };
  }, [personId, filters, preset, metric, currency]);

  const bucketValue = (b: { total: number; per_day: number }) => (metric === "per_day" ? b.per_day : b.total);

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <section className="frosted-card" style={{ padding: 14, display: "flex", flexWrap: "wrap", gap: 14, alignItems: "center" }}>
        <div role="group" aria-label="Comparison" style={{ display: "inline-flex", gap: 6 }}>
          <Pill active={preset === "weekdays_weekends"} onClick={() => setPreset("weekdays_weekends")}>Weekdays vs weekends</Pill>
          <Pill active={preset === "month_vs_month"} onClick={() => setPreset("month_vs_month")}>This vs last month</Pill>
        </div>
        <div role="group" aria-label="Measure" style={{ display: "inline-flex", gap: 6, marginLeft: "auto" }}>
          <Pill active={metric === "spend"} onClick={() => setMetric("spend")}>Total</Pill>
          <Pill active={metric === "per_day"} onClick={() => setMetric("per_day")}>Per day</Pill>
        </div>
      </section>

      <section className="frosted-card" style={{ padding: 16, display: "grid", gap: 16 }}>
        {data == null ? (
          <Loading rows={3} />
        ) : (
          <>
            <div style={{ display: "flex", gap: 28, flexWrap: "wrap" }}>
              {data.buckets.map((b) => (
                <Kpi key={b.label} label={b.label === "—" ? "No data" : b.label}>
                  {formatMoney(bucketValue(b))}
                  {metric === "per_day" && (
                    <span style={{ fontSize: 11.5, fontWeight: 600, color: "var(--fl-muted)", marginLeft: 6 }}>
                      /day · {b.n_days}d
                    </span>
                  )}
                </Kpi>
              ))}
            </div>
            <BarChartR
              labels={data.categories.map((c) => c.name)}
              series={[
                { name: data.labels.a, values: data.categories.map((c) => c.a) },
                { name: data.labels.b, values: data.categories.map((c) => c.b) },
              ]}
              horizontal
              height={Math.max(160, data.categories.length * 46)}
              ariaLabel={`${data.labels.a} versus ${data.labels.b} by category`}
            />
          </>
        )}
      </section>
    </div>
  );
}
