import { useEffect, useState } from "react";
import { getOverlap, type AnalysisFilters, type OverlapResult } from "@/lib/api";
import { Kpi } from "@/components/kpi";
import { formatMoney } from "@/components/money";
import { DivergingBarChart } from "@/components/charts/diverging-bar-chart";
import { Loading } from "@/components/loading";

/** People tab (Joint only): per-category spend for both people as a diverging
 *  tornado, plus per-person totals and the count of mutually-spent categories.
 *  Wraps the engine's user_overlap; gated to the Joint view by the parent. */
export function PeopleTab({ filters }: { filters: AnalysisFilters }) {
  const [data, setData] = useState<OverlapResult | null>(null);

  useEffect(() => {
    let alive = true;
    setData(null);
    getOverlap({ filters })
      .then((d) => alive && setData(d))
      .catch(() => alive && setData(null));
    return () => { alive = false; };
  }, [filters]);

  if (data == null) {
    return (
      <section className="frosted-card" style={{ padding: 16 }}>
        <Loading rows={3} />
      </section>
    );
  }

  if (!data.available || !data.a || !data.b) {
    return (
      <section className="frosted-card" style={{ padding: 16, color: "var(--fl-muted)", fontSize: 13 }}>
        Need two people to compare.
      </section>
    );
  }

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <section className="frosted-card" style={{ padding: 16, display: "flex", gap: 28, flexWrap: "wrap" }}>
        <Kpi label={`${data.a.name} spent`}>{formatMoney(data.a.spend)}</Kpi>
        <Kpi label={`${data.b.name} spent`}>{formatMoney(data.b.spend)}</Kpi>
        <Kpi label="Shared categories">{data.shared}</Kpi>
      </section>

      <section className="frosted-card" style={{ padding: 16 }}>
        <DivergingBarChart rows={data.rows} labelA={data.a.name} labelB={data.b.name} format={formatMoney} />
      </section>
    </div>
  );
}
