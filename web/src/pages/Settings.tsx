import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { pillStyle as pill } from "@/lib/ui";
import {
  getPeople, renamePerson,
  getCategories, upsertCategory, deleteCategory,
  getVendors, upsertVendor, deleteVendor,
  getFxRates,
  type Person, type Category, type Vendor, type FxRatesInfo,
} from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { useCurrency, type Currency } from "@/lib/currency";
import { getAssumedReturn, setAssumedReturn } from "@/lib/prefs";

const h2: CSSProperties = { fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--fl-muted)", margin: 0 };

type Rule = { id: number; name: string; keywords: string; parent?: string | null };

function RuleSection({ kind, items, onSave, onAdd, onRemove, onSaveParent }: {
  kind: "category" | "vendor";
  items: Rule[];
  onSave: (r: Rule, keywords: string) => void;
  onAdd: (name: string, keywords: string) => void;
  onRemove: (r: Rule) => void;
  onSaveParent?: (r: Rule, parent: string) => void;
}) {
  const [name, setName] = useState("");
  const [keywords, setKeywords] = useState("");
  const Title = kind === "category" ? "Categories" : "Vendor groups";
  const namePh = kind === "category" ? "New category name" : "New vendor name";
  const kwPh = kind === "category" ? "Category keywords" : "Vendor keywords";
  const addLabel = kind === "category" ? "Add category" : "Add vendor";

  const add = () => {
    if (name.trim()) { onAdd(name.trim(), keywords); setName(""); setKeywords(""); }
  };

  return (
    <section className="frosted-card" style={{ padding: 20, display: "grid", gap: 10 }}>
      <h2 style={h2}>{Title}</h2>
      {items.length === 0 && <div style={{ color: "var(--fl-muted)", fontSize: 13 }}>None yet.</div>}
      {items.map((r) => (
        <div key={r.id} style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 700, minWidth: 120 }}>{r.name}</span>
          <input
            defaultValue={r.keywords}
            aria-label={`Keywords for ${kind} ${r.name}`}
            onBlur={(e) => onSave(r, e.target.value)}
            placeholder="comma-separated keywords"
            style={{ ...pill, flex: 1, minWidth: 160 }}
          />
          {kind === "category" && onSaveParent && (
            <input
              defaultValue={r.parent ?? ""}
              aria-label={`Parent group for category ${r.name}`}
              onBlur={(e) => onSaveParent(r, e.target.value)}
              placeholder="parent group"
              style={{ ...pill, width: 130 }}
            />
          )}
          <button onClick={() => onRemove(r)} aria-label={`Remove ${kind} ${r.name}`}
            style={{ border: "none", background: "none", color: "var(--fl-muted)", cursor: "pointer", fontSize: 16, lineHeight: 1 }}>✕</button>
        </div>
      ))}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", borderTop: "1px solid var(--fl-line)", paddingTop: 10 }}>
        <input placeholder={namePh} value={name} onChange={(e) => setName(e.target.value)} style={{ ...pill, width: 160 }} />
        <input placeholder={kwPh} value={keywords} onChange={(e) => setKeywords(e.target.value)} style={{ ...pill, flex: 1, minWidth: 160 }} />
        <button onClick={add} style={{ ...pill, fontWeight: 700, color: "var(--persona-solid)" }}>{addLabel}</button>
      </div>
    </section>
  );
}

export default function Settings() {
  const { personId: activePersonId } = usePersona();
  const { currency, setCurrency } = useCurrency();
  const [people, setPeople] = useState<Person[]>([]);
  const [selected, setSelected] = useState<number | null>(activePersonId ?? null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [fx, setFx] = useState<FxRatesInfo | null>(null);
  useEffect(() => { getFxRates().then(setFx).catch(() => setFx(null)); }, []);
  const CUR: { key: Currency; label: string }[] = [{ key: "USD", label: "$ USD" }, { key: "ILS", label: "₪ ILS" }];

  const loadPeople = useCallback(() => getPeople().then(setPeople).catch(() => setPeople([])), []);
  useEffect(() => { loadPeople(); }, [loadPeople]);

  // Default the selected person once people arrive (e.g. Joint -> first person).
  useEffect(() => {
    if (selected == null && people.length > 0) setSelected(people[0].id);
  }, [people, selected]);

  const loadRules = useCallback(() => {
    if (selected == null) return;
    getCategories(selected).then(setCategories).catch(() => setCategories([]));
    getVendors(selected).then(setVendors).catch(() => setVendors([]));
  }, [selected]);
  useEffect(() => { loadRules(); }, [loadRules]);

  const rename = (p: Person, value: string) => {
    const name = value.trim();
    if (name && name !== p.name) renamePerson(p.id, name).then(loadPeople);
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", fontSize: 24, margin: 0 }}>Settings</h1>
        <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>people, categories & vendor groups</span>
      </header>

      <section className="frosted-card" style={{ padding: 20, display: "grid", gap: 10 }}>
        <h2 style={h2}>People</h2>
        {people.map((p) => (
          <div key={p.id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              defaultValue={p.name}
              aria-label={`Name for person ${p.id}`}
              onBlur={(e) => rename(p, e.target.value)}
              style={{ ...pill, width: 220 }}
            />
          </div>
        ))}
      </section>

      <section className="frosted-card" style={{ padding: 20, display: "grid", gap: 12 }}>
        <h2 style={h2}>Money</h2>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, color: "var(--fl-muted)" }}>Default display currency</span>
          {CUR.map((c) => (
            <button key={c.key} onClick={() => setCurrency(c.key)} aria-pressed={currency === c.key}
              style={{ ...pill, fontWeight: currency === c.key ? 700 : 500,
                       background: currency === c.key ? "var(--persona)" : "transparent",
                       color: currency === c.key ? "#fff" : "var(--fl-ink)" }}>
              {c.label}
            </button>
          ))}
        </div>
        <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>
          {fx && fx.count > 0
            ? `Rates: ${fx.source ?? "—"}, last fetched ${fx.last_fetched ?? "never"} · ${fx.count} cached`
            : "No exchange rates cached yet. Importing a non-USD statement fetches the rate it needs."}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", borderTop: "1px solid var(--fl-line)", paddingTop: 12 }}>
          <span style={{ fontSize: 13, color: "var(--fl-muted)" }}>Assumed annual return (net-worth projection)</span>
          <input
            type="number"
            aria-label="Assumed annual return percent"
            defaultValue={Math.round(getAssumedReturn() * 100)}
            onBlur={(e) => {
              const pct = Number(e.target.value);
              if (Number.isFinite(pct) && pct >= 0) setAssumedReturn(pct / 100);
            }}
            style={{ ...pill, width: 80, textAlign: "right" }}
          />
          <span style={{ fontSize: 13, color: "var(--fl-muted)" }}>% · an estimate, not a guarantee</span>
        </div>
      </section>

      <section className="frosted-card" style={{ padding: 16, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span style={h2}>Editing rules for</span>
        {people.map((p) => (
          <button
            key={p.id}
            onClick={() => setSelected(p.id)}
            aria-pressed={selected === p.id}
            style={{ ...pill, fontWeight: selected === p.id ? 700 : 500, background: selected === p.id ? "var(--persona)" : "transparent", color: selected === p.id ? "#fff" : "var(--fl-ink)" }}
          >
            {p.name}
          </button>
        ))}
      </section>

      <RuleSection
        kind="category"
        items={categories}
        onSave={(r, keywords) => { if (selected != null && keywords !== r.keywords) upsertCategory({ personId: selected, name: r.name, keywords }).then(loadRules); }}
        onAdd={(name, keywords) => { if (selected != null) upsertCategory({ personId: selected, name, keywords }).then(loadRules); }}
        onRemove={(r) => deleteCategory(r.id).then(loadRules)}
        onSaveParent={(r, parent) => { if (selected != null && parent !== (r.parent ?? "")) upsertCategory({ personId: selected, name: r.name, keywords: r.keywords ?? "", parent }).then(loadRules); }}
      />

      <RuleSection
        kind="vendor"
        items={vendors}
        onSave={(r, keywords) => { if (selected != null && keywords !== r.keywords) upsertVendor({ personId: selected, name: r.name, keywords }).then(loadRules); }}
        onAdd={(name, keywords) => { if (selected != null) upsertVendor({ personId: selected, name, keywords }).then(loadRules); }}
        onRemove={(r) => deleteVendor(r.id).then(loadRules)}
      />
    </div>
  );
}
