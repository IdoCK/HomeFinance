import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { pillStyle as pill } from "@/lib/ui";
import {
  getEvents, createEvent, deleteEvent, getEventTransactions, setEventTags,
  getTransactions, type FinanceEvent, type Transaction,
} from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Money, formatMoney } from "@/components/money";

const KINDS = ["trip", "project", "event", "celebration", "other"];

const badge: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "2px 10px",
  fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--fl-muted)",
};

export default function Events() {
  const { personId, label } = usePersona();
  const [events, setEvents] = useState<FinanceEvent[]>([]);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("trip");
  const [editing, setEditing] = useState<number | null>(null);
  const [txns, setTxns] = useState<Transaction[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const load = useCallback(
    () => getEvents(personId).then(setEvents).catch(() => setEvents([])),
    [personId],
  );
  useEffect(() => { load(); }, [load]);

  const add = () => {
    if (name.trim()) createEvent({ personId, name: name.trim(), kind }).then(() => { setName(""); load(); });
  };
  const remove = (id: number) => deleteEvent(id).then(() => { if (editing === id) setEditing(null); load(); });

  const openEditor = async (id: number) => {
    setEditing(id);
    const [all, tagged] = await Promise.all([getTransactions({ personId }), getEventTransactions(id)]);
    setTxns(all);
    setSelected(new Set(tagged));
  };
  const toggle = (id: number) =>
    setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const saveMembers = async () => {
    if (editing != null) { await setEventTags(editing, [...selected]); setEditing(null); load(); }
  };

  return (
    <div style={{ display: "grid", gap: 16, maxWidth: 820 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", fontSize: 24, margin: 0 }}>Events · {label}</h1>
        <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>tag spending to trips, projects & occasions</span>
      </header>

      <section className="frosted-card" style={{ padding: 16, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <input placeholder="New event name" value={name} onChange={(e) => setName(e.target.value)} style={{ ...pill, width: 200 }} />
        <select aria-label="Event kind" value={kind} onChange={(e) => setKind(e.target.value)} style={pill}>
          {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <button onClick={add} style={{ ...pill, fontWeight: 700, color: "var(--persona-solid)" }}>Add event</button>
      </section>

      {events.length === 0 && (
        <section className="frosted-card" style={{ padding: 32, textAlign: "center", color: "var(--fl-muted)" }}>
          No events yet. Create one, then tag the transactions that belong to it.
        </section>
      )}

      <div style={{ display: "grid", gap: 10 }}>
        {events.map((e) => (
          <section key={e.id} className="frosted-card" style={{ padding: 18, display: "grid", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span style={{ fontWeight: 700, fontSize: 16 }}>{e.name}</span>
              <span style={badge}>{e.kind}</span>
              <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>
                {e.txn_count} transaction{e.txn_count === 1 ? "" : "s"} · <Money value={e.total} colored />
              </span>
              <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                <button onClick={() => openEditor(e.id)} aria-label={`Tag transactions for ${e.name}`}
                  style={{ ...pill, fontWeight: 700, color: "var(--persona-solid)" }}>
                  Tag transactions
                </button>
                <button onClick={() => remove(e.id)} aria-label={`Delete ${e.name}`}
                  style={{ border: "none", background: "none", color: "var(--fl-muted)", cursor: "pointer", fontSize: 16, lineHeight: 1 }}>✕</button>
              </span>
            </div>

            {editing === e.id && (
              <div style={{ display: "grid", gap: 6, borderTop: "1px solid var(--fl-line)", paddingTop: 12 }}>
                {txns.length === 0 && <div style={{ color: "var(--fl-muted)", fontSize: 13 }}>No transactions to tag yet.</div>}
                <div style={{ maxHeight: 280, overflowY: "auto", display: "grid", gap: 4 }}>
                  {txns.map((t) => (
                    <label key={t.id} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, padding: "2px 0" }}>
                      <input type="checkbox" checked={selected.has(t.id)} aria-label={`Tag ${t.description}`} onChange={() => toggle(t.id)} />
                      <span style={{ color: "var(--fl-muted)", fontVariantNumeric: "tabular-nums", minWidth: 86 }}>{t.date}</span>
                      <span style={{ flex: 1 }}>{t.description}</span>
                      <span style={{ fontVariantNumeric: "tabular-nums" }}>{formatMoney(t.amount)}</span>
                    </label>
                  ))}
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                  <button onClick={saveMembers} style={{ ...pill, fontWeight: 700, color: "var(--persona-solid)" }}>Save members</button>
                  <button onClick={() => setEditing(null)} style={{ ...pill, color: "var(--fl-muted)" }}>Cancel</button>
                </div>
              </div>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}
