import { useCallback, useEffect, useState, type CSSProperties } from "react";
import {
  getPeople, renamePerson,
  getCategories, upsertCategory, deleteCategory,
  getVendors, upsertVendor, deleteVendor,
  type Person, type Category, type Vendor,
} from "@/lib/api";
import { usePersona } from "@/lib/persona";

const pill: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "6px 12px",
  fontSize: 13, background: "transparent", color: "var(--fl-ink)",
};
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
  const [people, setPeople] = useState<Person[]>([]);
  const [selected, setSelected] = useState<number | null>(activePersonId ?? null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);

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
