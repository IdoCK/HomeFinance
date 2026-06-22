import { Pill } from "@/components/ui/pill";
import { SectionTitle } from "@/components/kpi";
import type { AnalysisFilters, FilterOptions } from "@/lib/api";

/** Shared deep-dive filter bar (the old Analysis filter row). Controlled: holds
 *  no state of its own — parent owns the AnalysisFilters and re-fetches on change.
 *  All conditions AND together in the engine's filter_transactions. */
export function FilterBar({
  options,
  value,
  onChange,
}: {
  options: FilterOptions;
  value: AnalysisFilters;
  onChange: (next: AnalysisFilters) => void;
}) {
  const set = (patch: Partial<AnalysisFilters>) => onChange({ ...value, ...patch });

  const toggle = (key: "months" | "categories", item: string) => {
    const cur = value[key] ?? [];
    const next = cur.includes(item) ? cur.filter((x) => x !== item) : [...cur, item];
    set({ [key]: next.length ? next : undefined });
  };

  const dirty =
    Boolean(value.dateFrom || value.dateTo || value.dayType || value.eventId) ||
    Boolean(value.months?.length) ||
    Boolean(value.categories?.length) ||
    Boolean(value.dow?.length);

  const dateInput: React.CSSProperties = {
    border: "1px solid var(--fl-line)", borderRadius: 10, padding: "5px 9px",
    fontSize: 12.5, background: "var(--fl-card)", color: "var(--fl-ink)",
  };

  return (
    <section className="frosted-card" aria-label="Filters" style={{ padding: 14, display: "grid", gap: 12 }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 14 }}>
        <label style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, color: "var(--fl-muted)" }}>
          From
          <input type="date" aria-label="From date" style={dateInput}
            value={value.dateFrom ?? ""}
            onChange={(e) => set({ dateFrom: e.target.value || undefined })} />
        </label>
        <label style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, color: "var(--fl-muted)" }}>
          To
          <input type="date" aria-label="To date" style={dateInput}
            value={value.dateTo ?? ""}
            onChange={(e) => set({ dateTo: e.target.value || undefined })} />
        </label>

        <div role="group" aria-label="Day type" style={{ display: "inline-flex", gap: 6 }}>
          <Pill active={!value.dayType} onClick={() => set({ dayType: undefined })}>All days</Pill>
          <Pill active={value.dayType === "weekday"} onClick={() => set({ dayType: "weekday" })}>Weekdays</Pill>
          <Pill active={value.dayType === "weekend"} onClick={() => set({ dayType: "weekend" })}>Weekends</Pill>
        </div>

        {options.events.length > 0 && (
          <label style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, color: "var(--fl-muted)" }}>
            Event
            <select aria-label="Event" style={dateInput}
              value={value.eventId ?? ""}
              onChange={(e) => set({ eventId: e.target.value ? Number(e.target.value) : undefined })}>
              <option value="">None</option>
              {options.events.map((ev) => <option key={ev.id} value={ev.id}>{ev.name}</option>)}
            </select>
          </label>
        )}

        {dirty && (
          <Pill onClick={() => onChange({})} style={{ marginLeft: "auto" }} aria-label="Clear filters">Clear</Pill>
        )}
      </div>

      {options.months.length > 1 && (
        <div style={{ display: "grid", gap: 6 }}>
          <SectionTitle>Months</SectionTitle>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {options.months.map((m) => (
              <Pill key={m} active={(value.months ?? []).includes(m)} onClick={() => toggle("months", m)}>{m}</Pill>
            ))}
          </div>
        </div>
      )}

      {options.categories.length > 0 && (
        <div style={{ display: "grid", gap: 6 }}>
          <SectionTitle>Categories</SectionTitle>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, maxHeight: 92, overflowY: "auto" }}>
            {options.categories.map((c) => (
              <Pill key={c} active={(value.categories ?? []).includes(c)} onClick={() => toggle("categories", c)}>{c}</Pill>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
