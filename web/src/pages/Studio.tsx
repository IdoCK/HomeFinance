import { useEffect, useMemo, useState } from "react";
import { getOverview, getNetWorth, getCategoryTrend, type Overview, type NetWorthData, type CategoryTrend } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { useCurrency } from "@/lib/currency";
import { pillStyle as pill } from "@/lib/ui";
import { Pill } from "@/components/ui/pill";
import { ChartRenderer } from "@/components/charts/chart-renderer";
import {
  METRICS, METRIC_ORDER, WINDOW_OPTIONS, defaultKind, summarize,
  type ChartKind, type ChartMetric, type ChartSpec,
} from "@/lib/chart-spec";
import { addChart, loadCharts, moveChart, newId, removeChart } from "@/lib/chart-store";

const KIND_LABEL: Record<ChartKind, string> = { line: "Line", area: "Area", bar: "Bar", donut: "Donut" };
const ALL_KINDS: ChartKind[] = ["line", "area", "bar", "donut"];

export default function Studio() {
  const { personId, label } = usePersona();
  const { currency } = useCurrency();

  // Sources — loaded once, shared by the live preview and every saved chart.
  const [overview, setOverview] = useState<Overview | null>(null);
  const [networth, setNetworth] = useState<NetWorthData | null>(null);
  const [categoryTrend, setCategoryTrend] = useState<CategoryTrend | null>(null);

  useEffect(() => {
    let alive = true;
    getOverview({ personId, display: currency }).then((d) => alive && setOverview(d)).catch(() => alive && setOverview(null));
    getNetWorth({ personId, display: currency }).then((d) => alive && setNetworth(d)).catch(() => alive && setNetworth(null));
    getCategoryTrend({ personId, display: currency }).then((d) => alive && setCategoryTrend(d)).catch(() => alive && setCategoryTrend(null));
    return () => { alive = false; };
  }, [personId, currency]);

  const sources = useMemo(() => ({ overview, networth, categoryTrend }), [overview, networth, categoryTrend]);

  // Draft spec being built.
  const [metric, setMetric] = useState<ChartMetric>("net");
  const [kind, setKind] = useState<ChartKind>("area");
  const [months, setMonths] = useState(12);
  const [title, setTitle] = useState("");

  const def = METRICS[metric];
  const draft: ChartSpec = { id: "draft", title: title.trim() || "", metric, kind, months };
  const sentence = summarize(draft);

  // Switching metric snaps the chart kind to one the metric supports.
  const chooseMetric = (m: ChartMetric) => {
    setMetric(m);
    if (!METRICS[m].kinds.includes(kind)) setKind(defaultKind(m));
  };

  const [saved, setSaved] = useState<ChartSpec[]>(() => loadCharts());

  const pin = () => {
    const spec: ChartSpec = { ...draft, id: newId(), title: title.trim() || sentence.replace(/ — as .*/, "") };
    setSaved(addChart(spec));
    setTitle("");
  };

  return (
    <div style={{ display: "grid", gap: 18 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Studio · {label}</h1>
        <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>build a chart, then pin it to your board</span>
      </header>

      {/* Builder */}
      <section className="frosted-card" style={{ padding: 18, display: "grid", gap: 16 }}>
        {/* Signature: the spec as one plain-English sentence. */}
        <p aria-live="polite" style={{ margin: 0, fontSize: 17, fontWeight: 600, letterSpacing: "-0.01em", color: "var(--fl-ink)" }}>
          {sentence}
        </p>

        <div style={{ display: "grid", gap: 18, gridTemplateColumns: "minmax(220px, 280px) 1fr", alignItems: "start" }}>
          {/* Config rail */}
          <div style={{ display: "grid", gap: 14 }}>
            <Field label="Measure">
              <select aria-label="Measure" value={metric} onChange={(e) => chooseMetric(e.target.value as ChartMetric)} style={{ ...pill, width: "100%" }}>
                {METRIC_ORDER.map((m) => <option key={m} value={m}>{METRICS[m].label}</option>)}
              </select>
            </Field>

            <Field label="Chart type">
              <div role="group" aria-label="Chart type" style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {ALL_KINDS.map((k) => {
                  const ok = def.kinds.includes(k);
                  return (
                    <Pill
                      key={k}
                      active={kind === k}
                      disabled={!ok}
                      onClick={() => ok && setKind(k)}
                      title={ok ? undefined : `${KIND_LABEL[k]} doesn't suit ${def.label.toLowerCase()}`}
                    >
                      {KIND_LABEL[k]}
                    </Pill>
                  );
                })}
              </div>
            </Field>

            <Field label="Time range">
              <div role="group" aria-label="Time range" style={{ display: "flex", flexWrap: "wrap", gap: 6, opacity: def.windowed ? 1 : 0.4, pointerEvents: def.windowed ? "auto" : "none" }}>
                {WINDOW_OPTIONS.map((m) => (
                  <Pill key={m} active={months === m} onClick={() => setMonths(m)}>{m} mo</Pill>
                ))}
              </div>
              {!def.windowed && <span style={{ fontSize: 11.5, color: "var(--fl-muted)" }}>This measure is a single-month snapshot.</span>}
            </Field>

            <Field label="Title (optional)">
              <input
                aria-label="Chart title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={sentence.replace(/ — as .*/, "")}
                style={{ ...pill, width: "100%" }}
              />
            </Field>

            <button onClick={pin} style={{ ...pill, justifySelf: "start", fontWeight: 700, color: "#fff", background: "var(--persona-solid)", border: "none", cursor: "pointer", padding: "8px 16px" }}>
              ＋ Pin to My Charts
            </button>
          </div>

          {/* Live preview */}
          <div className="frosted-card" style={{ padding: 16, background: "var(--fl-frame)", minWidth: 0 }}>
            <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--fl-muted)", marginBottom: 10 }}>
              Live preview
            </div>
            <ChartRenderer spec={draft} sources={sources} height={240} />
          </div>
        </div>
      </section>

      {/* Saved board */}
      <section style={{ display: "grid", gap: 12 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--fl-muted)", margin: 0 }}>
          My Charts
        </h2>
        {saved.length === 0 ? (
          <section className="frosted-card" style={{ padding: 28, textAlign: "center", color: "var(--fl-muted)", fontSize: 13 }}>
            No saved charts yet. Build one above and pin it here.
          </section>
        ) : (
          <div className="fl-row-2-board" style={{ display: "grid", gap: 14, gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))" }}>
            {saved.map((spec, i) => (
              <section key={spec.id} className="frosted-card" style={{ padding: 16, display: "grid", gap: 10, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: "var(--fl-ink)", flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {spec.title}
                  </span>
                  <button aria-label={`Move ${spec.title} earlier`} disabled={i === 0} onClick={() => setSaved(moveChart(spec.id, -1))} style={iconBtn}>↑</button>
                  <button aria-label={`Move ${spec.title} later`} disabled={i === saved.length - 1} onClick={() => setSaved(moveChart(spec.id, 1))} style={iconBtn}>↓</button>
                  <button aria-label={`Remove ${spec.title}`} onClick={() => setSaved(removeChart(spec.id))} style={{ ...iconBtn, color: "var(--fl-muted)" }}>✕</button>
                </div>
                <ChartRenderer spec={spec} sources={sources} height={200} />
              </section>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

const iconBtn: React.CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 8, background: "transparent",
  color: "var(--fl-ink)", cursor: "pointer", width: 26, height: 26, lineHeight: 1, flex: "none",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: "grid", gap: 6 }}>
      <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--fl-muted)" }}>{label}</span>
      {children}
    </label>
  );
}
