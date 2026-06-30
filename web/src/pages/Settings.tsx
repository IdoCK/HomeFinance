import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { pillStyle as pill } from "@/lib/ui";
import {
  getPeople, renamePerson,
  getCategories, upsertCategory, deleteCategory,
  getVendors, upsertVendor, deleteVendor,
  getDisplayRate, setDisplayRate, refreshDisplayRate, getUntrackedCount,
  type Person, type Category, type Vendor, type DisplayRate,
} from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { useCurrency, type Currency } from "@/lib/currency";
import { getAssumedReturn, setAssumedReturn } from "@/lib/prefs";
import { Banner } from "@/components/ui/banner";

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
      <p style={{ margin: 0, fontSize: 12, color: "var(--fl-muted)" }}>Shared across everyone</p>
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
  const [rate, setRate] = useState<DisplayRate | null>(null);
  const [fxMsg, setFxMsg] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const loadRate = useCallback(() => getDisplayRate("ILS").then(setRate).catch(() => setRate(null)), []);
  useEffect(() => { loadRate(); }, [loadRate]);

  const saveRate = (v: number) => {
    if (Number.isFinite(v) && v > 0 && v !== rate?.rate) {
      setDisplayRate("ILS", v).then(() => { setFxMsg(null); loadRate(); }).catch(() => {});
    }
  };
  const refreshRate = () => {
    setRefreshing(true);
    setFxMsg(null);
    refreshDisplayRate("ILS")
      .then((r) => setFxMsg(r.ok ? "Updated from the internet." : "Couldn't reach the rate service — set the rate manually below."))
      .catch(() => setFxMsg("Refresh failed — set the rate manually below."))
      .finally(() => { setRefreshing(false); loadRate(); });
  };
  // Legacy rows imported before file-tracking can't be tied to a statement and
  // may hide whole-file duplicates — surface the count as an audit banner.
  const [untracked, setUntracked] = useState(0);
  useEffect(() => {
    getUntrackedCount(activePersonId ?? undefined).then((r) => setUntracked(r.count)).catch(() => setUntracked(0));
  }, [activePersonId]);
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

      {untracked > 0 && (
        <Banner tone="warn" icon={<span style={{ fontWeight: 800 }}>!</span>}>
          <strong style={{ fontWeight: 700 }}>{untracked.toLocaleString()}</strong> {untracked === 1 ? "transaction predates" : "transactions predate"} file tracking and aren't tied to a statement — they may include duplicates. Re-import those statements to track and de-duplicate them.
        </Banner>
      )}

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
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", borderTop: "1px solid var(--fl-line)", paddingTop: 12 }}>
          <span style={{ fontSize: 13, color: "var(--fl-muted)" }}>Exchange rate</span>
          <span style={{ fontSize: 13, fontVariantNumeric: "tabular-nums" }}>1&nbsp;$&nbsp;=</span>
          <input
            type="number"
            step="0.01"
            min="0"
            aria-label="US dollar to shekel exchange rate"
            key={rate?.rate ?? "none"}
            defaultValue={rate?.rate ?? ""}
            placeholder="3.70"
            onBlur={(e) => saveRate(Number(e.target.value))}
            style={{ ...pill, width: 90, textAlign: "right" }}
          />
          <span style={{ fontSize: 13 }}>₪</span>
          <button onClick={refreshRate} disabled={refreshing} style={{ ...pill, fontWeight: 600, opacity: refreshing ? 0.6 : 1 }}>
            {refreshing ? "Refreshing…" : "Refresh from internet"}
          </button>
        </div>
        <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>
          {rate?.rate != null
            ? `Every figure converts at this rate when ₪ is selected · source: ${rate.source ?? "—"}`
            : "No rate set — enter one so the ₪ view converts."}
          {fxMsg ? ` · ${fxMsg}` : ""}
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
