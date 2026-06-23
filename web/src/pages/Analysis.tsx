import { useEffect, useState } from "react";
import {
  getFilterOptions, getCategoryTrend,
  type AnalysisFilters, type FilterOptions, type CategoryTrend,
} from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Pill } from "@/components/ui/pill";
import { CardHeaderRow } from "@/components/ui/card";
import { FilterBar } from "@/components/filter-bar";
import { LineChart } from "@/components/charts/line-chart";
import { DrillDown } from "@/components/analysis/drill-down";
import { CompareTab } from "@/components/analysis/compare-tab";
import { Loading } from "@/components/loading";

const CARD: React.CSSProperties = { padding: 16 };
const MAX_LINES = 8; // one per palette color; busier than this is unreadable

function ExploreTab({ personId, filters }: { personId?: number; filters: AnalysisFilters }) {
  const [rollup, setRollup] = useState(false);
  const [trend, setTrend] = useState<CategoryTrend | null>(null);

  useEffect(() => {
    let alive = true;
    setTrend(null);
    getCategoryTrend({ personId, rollup, filters })
      .then((d) => alive && setTrend(d))
      .catch(() => alive && setTrend({ months: [], series: [] }));
    return () => { alive = false; };
  }, [personId, rollup, filters]);

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <section className="frosted-card" style={CARD}>
        <CardHeaderRow
          action={
            <Pill active={rollup} onClick={() => setRollup((r) => !r)}>
              {rollup ? "Grouped" : "Roll up to groups"}
            </Pill>
          }
        >
          Spending by category over time
        </CardHeaderRow>
        {trend == null ? (
          <Loading rows={2} />
        ) : (
          <LineChart
            labels={trend.months}
            series={trend.series.slice(0, MAX_LINES).map((s) => ({ name: s.name, values: s.values, total: s.total }))}
          />
        )}
        {trend && trend.series.length > MAX_LINES && (
          <div style={{ marginTop: 8, fontSize: 11.5, color: "var(--fl-muted)" }}>
            Showing the {MAX_LINES} biggest categories. Use the Categories filter to focus on others.
          </div>
        )}
      </section>

      <section className="frosted-card" style={CARD}>
        <CardHeaderRow>Drill down</CardHeaderRow>
        <DrillDown personId={personId} filters={filters} />
      </section>
    </div>
  );
}

function ComingSoon({ what }: { what: string }) {
  return (
    <section className="frosted-card" style={{ ...CARD, color: "var(--fl-muted)", fontSize: 13 }}>
      {what}
    </section>
  );
}

export default function Analysis() {
  const { personId, label, persona } = usePersona();
  const [options, setOptions] = useState<FilterOptions | null>(null);
  const [filters, setFilters] = useState<AnalysisFilters>({});
  const [tab, setTab] = useState("explore");

  useEffect(() => {
    let alive = true;
    setFilters({}); // persona switch resets filters (categories/events are per-person)
    getFilterOptions(personId)
      .then((o) => alive && setOptions(o))
      .catch(() => alive && setOptions({ months: [], categories: [], events: [] }));
    return () => { alive = false; };
  }, [personId]);

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <header style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>
          Analysis · {label}
        </h1>
      </header>

      {options == null ? (
        <Loading rows={4} />
      ) : (
        <>
          <FilterBar options={options} value={filters} onChange={setFilters} />
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="explore">Explore</TabsTrigger>
              <TabsTrigger value="compare">Compare</TabsTrigger>
              <TabsTrigger value="people">People</TabsTrigger>
            </TabsList>
            <TabsContent value="explore" style={{ marginTop: 12 }}>
              <ExploreTab personId={personId} filters={filters} />
            </TabsContent>
            <TabsContent value="compare" style={{ marginTop: 12 }}>
              <CompareTab personId={personId} filters={filters} />
            </TabsContent>
            <TabsContent value="people" style={{ marginTop: 12 }}>
              {persona === "joint"
                ? <ComingSoon what="Per-person breakdown and mutual spending — coming next." />
                : <ComingSoon what="Switch to the Joint view to compare both people." />}
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
