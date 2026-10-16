import { useCallback, useEffect, useState } from "react";
import { pillStyle as pill } from "@/lib/ui";
import { getBudgets, getBudgetSummary, setBudget, deleteBudget, type Budget, type BudgetSummary } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { useCurrency } from "@/lib/currency";
import { Money } from "@/components/money";

const STATUS_COLOR: Record<Budget["status"], string> = {
  on_track: "var(--persona)",
  ahead: "#F59E0B",
  over: "var(--neg)",
};
const STATUS_LABEL: Record<Budget["status"], string> = {
  on_track: "on pace",
  ahead: "running hot",
  over: "over budget",
};


/** Pace bar: fill = used %, with a vertical tick at the pace-expected % (where
 *  you "should" be today). `color` carries the status. Shared shape between the
 *  per-budget meter and the household roll-up. */
function Meter({ fillPct, tickPct, color }: { fillPct: number; tickPct: number; color: string }) {
  return (
    <div style={{ position: "relative", height: 10, borderRadius: 999, background: "var(--fl-line)" }}>
      <div style={{ position: "absolute", top: 0, left: 0, height: "100%", width: `${Math.min(fillPct, 100)}%`, background: color, borderRadius: 999, transition: "width .4s ease" }} />
      <div style={{ position: "absolute", top: -2, bottom: -2, left: `${Math.min(tickPct, 100)}%`, width: 2, borderRadius: 2, background: "var(--fl-ink)", opacity: 0.5 }} aria-hidden />
    </div>
  );
}

function PaceMeter({ b }: { b: Budget }) {
  const fillPct = b.budget > 0 ? (b.spent / b.budget) * 100 : 0;
  const tickPct = b.budget > 0 ? (b.expected_to_date / b.budget) * 100 : 0;
  return <Meter fillPct={fillPct} tickPct={tickPct} color={STATUS_COLOR[b.status]} />;
}

function Rollup({ summary }: { summary: BudgetSummary }) {
  const { total_budgeted, total_spent, unbudgeted_spent } = summary;
  const now = new Date();
  const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  const paceFrac = now.getDate() / daysInMonth;
  const fillPct = total_budgeted > 0 ? (total_spent / total_budgeted) * 100 : 0;
  const color =
    total_spent > total_budgeted ? "var(--neg)"
    : total_spent > total_budgeted * paceFrac ? "#F59E0B"
    : "var(--persona)";
  return (
    <section className="frosted-card" aria-label="Budget roll-up" style={{ padding: 20, display: "grid", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--fl-muted)" }}>Budgeted this month</span>
        <span data-testid="budget-rollup" style={{ fontSize: 30, fontWeight: 800, letterSpacing: "-0.03em" }}>
          <Money value={total_spent} /> <span style={{ fontSize: 15, color: "var(--fl-muted)" }}>/ <Money value={total_budgeted} /></span>
        </span>
        {unbudgeted_spent > 0 && (
          <span style={{ marginLeft: "auto", fontSize: 12.5, color: "var(--fl-muted)" }}>
            +<Money value={unbudgeted_spent} /> unbudgeted
          </span>
        )}
      </div>
      <Meter fillPct={fillPct} tickPct={paceFrac * 100} color={color} />
    </section>
  );
}

export default function Budgets() {
  const { personId, label } = usePersona();
  const { currency } = useCurrency();
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [summary, setSummary] = useState<BudgetSummary | null>(null);
  const [adding, setAdding] = useState(false);
  const [newCat, setNewCat] = useState("");
  const [newAmt, setNewAmt] = useState("");

  const load = useCallback(
    () => {
      getBudgets({ personId, display: currency }).then(setBudgets).catch(() => setBudgets([]));
      getBudgetSummary({ personId, display: currency }).then(setSummary).catch(() => setSummary(null));
    },
    [personId, currency],
  );
  useEffect(() => { load(); }, [load]);

  const commitCap = (b: Budget, value: string) => {
    const amount = Number(value);
    if (Number.isFinite(amount) && amount >= 0 && amount !== b.budget) {
      setBudget({ personId, category: b.category, amount }).then(load);
    }
  };

  const remove = (b: Budget) => deleteBudget(b.id).then(load);

  const addBudget = () => {
    const amount = Number(newAmt);
    const category = newCat.trim();
    if (category && Number.isFinite(amount) && amount >= 0) {
      setBudget({ personId, category, amount }).then(() => {
        setNewCat(""); setNewAmt(""); setAdding(false); load();
      });
    }
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", fontSize: 24, margin: 0 }}>Budgets · {label}</h1>
        <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>this month, paced to today</span>
      </header>

      {summary && summary.total_budgeted > 0 && <Rollup summary={summary} />}

      {budgets.length === 0 && !adding && (
        <section className="frosted-card" style={{ padding: 32, textAlign: "center", color: "var(--fl-muted)" }}>
          No budgets yet. Set a monthly cap for a category to track it.
        </section>
      )}

      <div style={{ display: "grid", gap: 12 }}>
        {budgets.map((b) => (
          <section key={b.id} className="frosted-card" style={{ padding: 20, display: "grid", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
              <span style={{ fontWeight: 700 }}>{b.category}</span>
              <span style={{ marginLeft: "auto", fontVariantNumeric: "tabular-nums" }}>
                <Money value={b.spent} /> <span style={{ color: "var(--fl-muted)" }}>/</span>{" "}
                <input
                  type="number"
                  defaultValue={b.budget}
                  aria-label={`Monthly cap for ${b.category}`}
                  onBlur={(e) => commitCap(b, e.target.value)}
                  style={{ ...pill, width: 96, padding: "4px 10px", textAlign: "right" }}
                />
              </span>
              <button
                onClick={() => remove(b)}
                aria-label={`Remove ${b.category} budget`}
                style={{ border: "none", background: "none", color: "var(--fl-muted)", cursor: "pointer", fontSize: 16, lineHeight: 1 }}
              >
                ✕
              </button>
            </div>
            <PaceMeter b={b} />
            <div style={{ display: "flex", gap: 8, fontSize: 12, color: STATUS_COLOR[b.status] }}>
              <span style={{ fontWeight: 600 }}>{STATUS_LABEL[b.status]}</span>
              <span style={{ color: "var(--fl-muted)" }}>
                · {Math.round(b.pct * 100)}% used · ~<Money value={b.projected_eom} /> projected
              </span>
            </div>
          </section>
        ))}
      </div>

      {adding ? (
        <section className="frosted-card" style={{ padding: 20, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input placeholder="Category" value={newCat} onChange={(e) => setNewCat(e.target.value)} style={pill} />
          <input type="number" placeholder="Monthly cap" value={newAmt} onChange={(e) => setNewAmt(e.target.value)} style={{ ...pill, width: 130 }} />
          <button onClick={addBudget} style={{ ...pill, fontWeight: 700, color: "var(--persona-solid)" }}>Add budget</button>
          <button onClick={() => setAdding(false)} style={{ ...pill, color: "var(--fl-muted)" }}>Cancel</button>
        </section>
      ) : (
        <button onClick={() => setAdding(true)} style={{ ...pill, justifySelf: "start", color: "var(--persona-solid)" }}>＋ Add a budget</button>
      )}
    </div>
  );
}
