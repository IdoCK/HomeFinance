import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { getGoals, addGoal, updateGoalSaved, deleteGoal, type Goal } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Money, formatMoney } from "@/components/money";

const pill: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "6px 12px",
  fontSize: 13, background: "transparent", color: "var(--fl-ink)",
};

function GoalCard({ g, onSave, onRemove }: {
  g: Goal; onSave: (g: Goal, v: string) => void; onRemove: (g: Goal) => void;
}) {
  const pct = Math.min(Math.max(g.percent, 0), 100);
  const done = g.percent >= 100;
  return (
    <section className="frosted-card" style={{ padding: 20, display: "grid", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <span style={{ fontWeight: 700 }}>{g.name}</span>
        {g.target_date && <span style={{ color: "var(--fl-muted)", fontSize: 12 }}>by {g.target_date}</span>}
        <span style={{ marginLeft: "auto", fontVariantNumeric: "tabular-nums" }}>
          <input
            type="number"
            defaultValue={g.saved_amount}
            aria-label={`Saved toward ${g.name}`}
            onBlur={(e) => onSave(g, e.target.value)}
            style={{ ...pill, width: 110, padding: "4px 10px", textAlign: "right" }}
          />{" "}
          <span style={{ color: "var(--fl-muted)" }}>/ <Money value={g.target_amount} /></span>
        </span>
        <button
          onClick={() => onRemove(g)}
          aria-label={`Remove ${g.name} goal`}
          style={{ border: "none", background: "none", color: "var(--fl-muted)", cursor: "pointer", fontSize: 16, lineHeight: 1 }}
        >
          ✕
        </button>
      </div>
      <div style={{ height: 10, borderRadius: 999, background: "var(--fl-line)" }}>
        <div style={{ height: 10, width: `${pct}%`, borderRadius: 999, background: done ? "var(--pos)" : "var(--persona)", transition: "width .4s ease" }} />
      </div>
      <div style={{ display: "flex", gap: 8, fontSize: 12, color: "var(--fl-muted)" }}>
        <span style={{ fontWeight: 600, color: done ? "var(--pos)" : "var(--persona)" }}>
          {done ? "reached 🎉" : `${Math.round(g.percent)}%`}
        </span>
        {!done && g.monthly_needed != null && (
          <span>· {formatMoney(g.monthly_needed)}/mo to stay on track</span>
        )}
      </div>
    </section>
  );
}

export default function Goals() {
  const { personId, label } = usePersona();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [horizon, setHorizon] = useState("short");

  const load = useCallback(
    () => getGoals({ personId }).then(setGoals).catch(() => setGoals([])),
    [personId],
  );
  useEffect(() => { load(); }, [load]);

  const commitSaved = (g: Goal, value: string) => {
    const amount = Number(value);
    if (Number.isFinite(amount) && amount >= 0 && amount !== g.saved_amount) {
      updateGoalSaved(g.id, amount).then(load);
    }
  };
  const remove = (g: Goal) => deleteGoal(g.id).then(load);
  const submit = () => {
    const targetAmount = Number(target);
    const nm = name.trim();
    if (nm && Number.isFinite(targetAmount) && targetAmount > 0) {
      addGoal({ personId, name: nm, targetAmount, targetDate: targetDate || undefined, horizon }).then(() => {
        setName(""); setTarget(""); setTargetDate(""); setHorizon("short"); setAdding(false); load();
      });
    }
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Goals · {label}</h1>
        <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>savings targets</span>
      </header>

      {goals.length === 0 && !adding && (
        <section className="frosted-card" style={{ padding: 32, textAlign: "center", color: "var(--fl-muted)" }}>
          No goals yet. Add a savings target to track your progress.
        </section>
      )}

      <div style={{ display: "grid", gap: 12 }}>
        {goals.map((g) => <GoalCard key={g.id} g={g} onSave={commitSaved} onRemove={remove} />)}
      </div>

      {adding ? (
        <section className="frosted-card" style={{ padding: 20, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input placeholder="Goal name" value={name} onChange={(e) => setName(e.target.value)} style={pill} />
          <input type="number" placeholder="Target amount" value={target} onChange={(e) => setTarget(e.target.value)} style={{ ...pill, width: 140 }} />
          <input type="date" aria-label="Target date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} style={pill} />
          <select aria-label="Horizon" value={horizon} onChange={(e) => setHorizon(e.target.value)} style={pill}>
            <option value="short">Short-term</option>
            <option value="long">Long-term</option>
          </select>
          <button onClick={submit} style={{ ...pill, fontWeight: 700, color: "var(--persona)" }}>Add goal</button>
          <button onClick={() => setAdding(false)} style={{ ...pill, color: "var(--fl-muted)" }}>Cancel</button>
        </section>
      ) : (
        <button onClick={() => setAdding(true)} style={{ ...pill, justifySelf: "start", color: "var(--persona)" }}>＋ Add a goal</button>
      )}
    </div>
  );
}
