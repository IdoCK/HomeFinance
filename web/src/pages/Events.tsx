import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { pillStyle as pill } from "@/lib/ui";
import {
  getEvents, createEvent, deleteEvent, getEventTransactions, setEventTags,
  getTransactions, type FinanceEvent, type Transaction,
} from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { useCurrency } from "@/lib/currency";
import { Money, formatMoney } from "@/components/money";

// Engine membership kinds (event_mask): a date window, a repeating day-rule, or
// pure manual tagging. Any kind also unions in hand-tagged stragglers.
const KINDS = [
  { value: "tagged", label: "Manual" },
  { value: "window", label: "Date window" },
  { value: "recurring", label: "Repeating days" },
];
const DOW = [
  { d: 0, label: "Mo" }, { d: 1, label: "Tu" }, { d: 2, label: "We" },
  { d: 3, label: "Th" }, { d: 4, label: "Fr" }, { d: 5, label: "Sa" }, { d: 6, label: "Su" },
];
const DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const badge: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "2px 10px",
  fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--fl-muted)",
};

/** Human description of an event's rule-based membership (window range or repeating
 *  days), or null for pure manual-tag events. `rule` arrives as a JSON string. */
function membershipLabel(e: FinanceEvent): string | null {
  if (e.kind === "window" && e.start_date && e.end_date) return `${e.start_date} → ${e.end_date}`;
  if (e.kind === "recurring" && e.rule) {
    try {
      const r = JSON.parse(e.rule) as { dow?: number[] };
      if (r.dow?.length) return r.dow.map((d) => DOW_NAMES[d]).join(", ");
    } catch { /* malformed rule → no label */ }
  }
  return null;
}

export default function Events() {
  const { personId, label } = usePersona();
  const { currency } = useCurrency();
  const [events, setEvents] = useState<FinanceEvent[]>([]);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("tagged");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [dow, setDow] = useState<number[]>([]);
  const [editing, setEditing] = useState<number | null>(null);
  const [txns, setTxns] = useState<Transaction[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const load = useCallback(
    () => getEvents({ personId, display: currency }).then(setEvents).catch(() => setEvents([])),
    [personId, currency],
  );
  useEffect(() => { load(); }, [load]);

  const toggleDow = (d: number) =>
    setDow((cur) => (cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d]));

  const add = () => {
    const nm = name.trim();
    if (!nm) return;
    const payload: Parameters<typeof createEvent>[0] = { personId, name: nm, kind };
    if (kind === "window") { payload.startDate = startDate || undefined; payload.endDate = endDate || undefined; }
    if (kind === "recurring") { payload.rule = { dow: [...dow].sort((a, b) => a - b) }; }
    createEvent(payload).then(() => {
      setName(""); setKind("tagged"); setStartDate(""); setEndDate(""); setDow([]); load();
    });
  };
  const remove = (id: number) => deleteEvent(id).then(() => { if (editing === id) setEditing(null); load(); });

  const openEditor = async (id: number) => {
    setEditing(id);
    const [all, tagged] = await Promise.all([getTransactions({ personId, display: currency }), getEventTransactions(id)]);
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
        <select aria-label="Membership" value={kind} onChange={(e) => setKind(e.target.value)} style={pill}>
          {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
        </select>
        {kind === "window" && (
          <>
            <input type="date" aria-label="Start date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={pill} />
            <input type="date" aria-label="End date" value={endDate} onChange={(e) => setEndDate(e.target.value)} style={pill} />
          </>
        )}
        {kind === "recurring" && (
          <span role="group" aria-label="Repeating days" style={{ display: "inline-flex", gap: 4 }}>
            {DOW.map(({ d, label }) => (
              <button key={d} onClick={() => toggleDow(d)} aria-label={`Day ${label}`} aria-pressed={dow.includes(d)}
                style={{ ...pill, padding: "4px 8px", fontWeight: dow.includes(d) ? 700 : 400, color: dow.includes(d) ? "var(--persona-solid)" : "var(--fl-muted)" }}>
                {label}
              </button>
            ))}
          </span>
        )}
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
              {membershipLabel(e) && (
                <span style={{ color: "var(--fl-muted)", fontSize: 12.5, fontVariantNumeric: "tabular-nums" }}>
                  {membershipLabel(e)}
                </span>
              )}
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
