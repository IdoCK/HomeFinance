import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { pillStyle as pill } from "@/lib/ui";
import { getNetWorth, addAccount, updateAccountBalance, deleteAccount, getReconciliation, getAccountHistory, getAccountImports, recordAccountSnapshot, populateFromStatements, type Account, type AccountSnapshot, type StatementImport, type NetWorthData, type ReconciliationResult, type StatementReconciliation } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { useCurrency } from "@/lib/currency";
import { Money, formatMoney } from "@/components/money";
import { Sparkline } from "@/components/charts/sparkline";
import { Loading } from "@/components/loading";

const KINDS = ["checking", "savings", "investment", "property", "credit_card", "loan", "other"];
const LIABILITY_KINDS = new Set(["credit_card", "loan"]);
const isAssetKind = (kind: string) => !LIABILITY_KINDS.has(kind);

const badge: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "2px 10px",
  fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--fl-muted)",
};

function AccountRow({ a, onSave, onRemove, onChanged }: {
  a: Account; onSave: (a: Account, v: string) => void; onRemove: (a: Account) => void; onChanged: () => void;
}) {
  const asset = !!a.is_asset;
  const [history, setHistory] = useState<AccountSnapshot[] | null>(null);
  const [managing, setManaging] = useState(false);
  // Refetch when the balance changes — committing a balance writes a new snapshot.
  useEffect(() => {
    let alive = true;
    getAccountHistory(a.id).then((d) => alive && setHistory(d.snapshots)).catch(() => alive && setHistory([]));
    return () => { alive = false; };
  }, [a.id, a.balance]);

  return (
    <section className="frosted-card" style={{ padding: 16, display: "grid", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ fontWeight: 700 }}>{a.name}</span>
        <span style={badge}>{a.kind.replace("_", " ")}</span>
        <span style={{ ...badge, color: asset ? "var(--pos)" : "var(--neg)", borderColor: "currentColor" }}>
          {asset ? "asset" : "liability"}
        </span>
        {history && history.length >= 2 && (
          <span style={{ width: 110, height: 28, flex: "none" }}>
            <Sparkline values={history.map((s) => s.balance)} height={28} accent={asset ? "var(--pos)" : "var(--neg)"} ariaLabel={`${a.name} balance history`} />
          </span>
        )}
        <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <input
            type="number"
            defaultValue={a.balance}
            aria-label={`Balance for ${a.name}`}
            onBlur={(e) => onSave(a, e.target.value)}
            style={{ ...pill, width: 130, padding: "4px 10px", textAlign: "right" }}
          />
          <button
            onClick={() => setManaging((m) => !m)}
            aria-label={`Manage ${a.name}`}
            aria-expanded={managing}
            style={{ ...pill, color: "var(--fl-muted)", padding: "4px 10px" }}
          >
            Manage
          </button>
          <button
            onClick={() => onRemove(a)}
            aria-label={`Remove ${a.name} account`}
            style={{ border: "none", background: "none", color: "var(--fl-muted)", cursor: "pointer", fontSize: 16, lineHeight: 1 }}
          >
            ✕
          </button>
        </span>
      </div>
      {managing && <ManagePanel a={a} onDone={() => { setManaging(false); onChanged(); }} />}
    </section>
  );
}

/** The old per-account "Manage" popover: record a balance as of a date (for
 *  investments with no statement) and populate month-end balances from imported
 *  bank statements (using each statement's running-balance column). */
function ManagePanel({ a, onDone }: { a: Account; onDone: () => void }) {
  const [snapDate, setSnapDate] = useState("");
  const [snapBal, setSnapBal] = useState("");
  const [imports, setImports] = useState<StatementImport[]>([]);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getAccountImports(a.id).then((d) => alive && setImports(d.imports)).catch(() => alive && setImports([]));
    return () => { alive = false; };
  }, [a.id]);

  const saveSnapshot = () => {
    const bal = Number(snapBal);
    if (snapDate && Number.isFinite(bal)) {
      recordAccountSnapshot(a.id, snapDate, bal).then(onDone);
    }
  };
  const togglePick = (h: string) =>
    setPicked((s) => { const n = new Set(s); n.has(h) ? n.delete(h) : n.add(h); return n; });
  const populate = () => {
    if (picked.size === 0) return;
    populateFromStatements(a.id, [...picked]).then((r) => {
      if (r.recorded === 0) setNote("Those files have no running-balance data. Re-import the bank statement (its balance column powers this).");
      else onDone();
    });
  };

  return (
    <div style={{ display: "grid", gap: 16, borderTop: "1px solid var(--fl-line)", paddingTop: 12 }}>
      <div style={{ display: "grid", gap: 8 }}>
        <span style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--fl-muted)" }}>Record a balance as of a date</span>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input type="date" aria-label={`Snapshot date for ${a.name}`} value={snapDate} onChange={(e) => setSnapDate(e.target.value)} style={pill} />
          <input type="number" placeholder="Balance" aria-label={`Snapshot balance for ${a.name}`} value={snapBal} onChange={(e) => setSnapBal(e.target.value)} style={{ ...pill, width: 140 }} />
          <button onClick={saveSnapshot} style={{ ...pill, fontWeight: 700, color: "var(--persona-solid)" }}>Record balance</button>
        </div>
      </div>

      <div style={{ display: "grid", gap: 8 }}>
        <span style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--fl-muted)" }}>Populate month-end balances from statements</span>
        {imports.length === 0 ? (
          <span style={{ fontSize: 12.5, color: "var(--fl-muted)" }}>No imported files for this owner yet.</span>
        ) : (
          <>
            <div style={{ display: "grid", gap: 4 }}>
              {imports.map((im) => (
                <label key={im.file_hash} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                  <input type="checkbox" checked={picked.has(im.file_hash)} aria-label={`Use ${im.filename}`} onChange={() => togglePick(im.file_hash)} />
                  <span>{im.filename}</span>
                  <span style={{ color: "var(--fl-muted)" }}>· {im.count} rows</span>
                </label>
              ))}
            </div>
            <button onClick={populate} disabled={picked.size === 0} style={{ ...pill, justifySelf: "start", fontWeight: 700, color: "var(--persona-solid)" }}>Populate</button>
            {note && <span style={{ fontSize: 12, color: "var(--neg)" }}>{note}</span>}
          </>
        )}
      </div>
    </div>
  );
}

export default function NetWorth() {
  const { personId, label } = usePersona();
  const { currency } = useCurrency();
  const [data, setData] = useState<NetWorthData | null>(null);
  const [recon, setRecon] = useState<ReconciliationResult | null>(null);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("checking");
  const [balance, setBalance] = useState("");

  const load = useCallback(
    () => getNetWorth({ personId, display: currency }).then(setData).catch(() => setData(null)),
    [personId, currency],
  );
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    getReconciliation(personId).then(setRecon).catch(() => setRecon(null));
  }, [personId]);

  const commitBalance = (a: Account, value: string) => {
    const next = Number(value);
    if (Number.isFinite(next) && next >= 0 && next !== a.balance) {
      updateAccountBalance(a.id, next).then(load);
    }
  };
  const remove = (a: Account) => deleteAccount(a.id).then(load);
  const submit = () => {
    const bal = Number(balance);
    const nm = name.trim();
    if (nm && Number.isFinite(bal) && bal >= 0) {
      addAccount({ personId, name: nm, kind, isAsset: isAssetKind(kind), balance: bal }).then(() => {
        setName(""); setKind("checking"); setBalance(""); setAdding(false); load();
      });
    }
  };

  if (!data) return <Loading />;

  const { summary, delta, accounts, trend, split } = data;
  const deltaColor = delta == null ? "var(--fl-muted)" : delta > 0 ? "var(--pos)" : delta < 0 ? "var(--neg)" : "var(--fl-muted)";

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", fontSize: 24, margin: 0 }}>Net Worth · {label}</h1>
        <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>assets minus liabilities</span>
      </header>

      <section className="frosted-card" style={{ padding: 28, display: "grid", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 16, flexWrap: "wrap" }}>
          <div>
            {delta != null && (
              <div style={{ fontSize: 13, fontWeight: 700, color: deltaColor }}>
                {delta > 0 ? "▲" : delta < 0 ? "▼" : ""} {formatMoney(Math.abs(delta))} since last snapshot
              </div>
            )}
            <div data-testid="networth-total" style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.03em" }}>
              {formatMoney(summary.net)}
            </div>
          </div>
          <div style={{ marginLeft: "auto", textAlign: "right", color: "var(--fl-muted)", fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
            <div><Money value={summary.assets} /> assets</div>
            <div><Money value={summary.liabilities} /> liabilities</div>
          </div>
        </div>
        <Sparkline
          values={trend.map((p) => p.net)}
          height={64}
          ariaLabel="Net worth trend"
          emptyLabel="Add a second snapshot to see a trend."
        />
      </section>

      {personId == null && split && split.length > 0 && (
        <section className="frosted-card" aria-label="Household breakdown" style={{ padding: 20, display: "grid", gap: 10 }}>
          <span style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--fl-muted)", fontWeight: 700 }}>
            Household breakdown
          </span>
          {split.map((s) => {
            const color = s.name === "Ido" ? "var(--persona-you)" : s.name === "Aviv" ? "var(--persona-spouse)" : "var(--fl-muted)";
            return (
              <div key={s.name} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}>
                <span style={{ width: 9, height: 9, borderRadius: "50%", background: color }} />
                <span style={{ fontWeight: 600 }}>{s.name}</span>
                <span style={{ marginLeft: "auto", fontWeight: 700, fontVariantNumeric: "tabular-nums" }}><Money value={s.net} colored /></span>
              </div>
            );
          })}
        </section>
      )}

      {recon && recon.statements.length > 0 && recon.statements.map((stmt: StatementReconciliation) => (
        <section key={stmt.filename} className="frosted-card" aria-label={`Statement reconciliation: ${stmt.filename}`} style={{ padding: 20, display: "grid", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--fl-muted)" }}>
              Statement reconciliation · {stmt.filename}
            </span>
            <span style={{
              fontWeight: 700, fontSize: 13,
              color: stmt.ok ? "#22C55E" : "#EF4444",
            }}>
              {stmt.ok ? "✓ Ties out" : <><span>⚠ Off by </span><Money value={Math.abs(stmt.discrepancy)} currency={stmt.currency} /></>}
            </span>
          </div>
          <div style={{ color: "var(--fl-muted)", fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
            <Money value={stmt.begin} currency={stmt.currency} /> opening → <Money value={stmt.end} currency={stmt.currency} /> ending across {stmt.n} rows
            {stmt.chain_breaks > 0 && `; ${stmt.chain_breaks} balance break${stmt.chain_breaks === 1 ? "" : "s"}`}
          </div>
        </section>
      ))}

      {accounts.length === 0 && !adding && (
        <section className="frosted-card" style={{ padding: 32, textAlign: "center", color: "var(--fl-muted)" }}>
          No accounts yet. Add one to start tracking net worth.
        </section>
      )}

      <div style={{ display: "grid", gap: 10 }}>
        {accounts.map((a) => <AccountRow key={a.id} a={a} onSave={commitBalance} onRemove={remove} onChanged={load} />)}
      </div>

      {adding ? (
        <section className="frosted-card" style={{ padding: 20, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input placeholder="Account name" value={name} onChange={(e) => setName(e.target.value)} style={pill} />
          <select aria-label="Kind" value={kind} onChange={(e) => setKind(e.target.value)} style={pill}>
            {KINDS.map((k) => <option key={k} value={k}>{k.replace("_", " ")}</option>)}
          </select>
          <input type="number" placeholder="Balance" value={balance} onChange={(e) => setBalance(e.target.value)} style={{ ...pill, width: 140 }} />
          <span style={{ ...badge, color: isAssetKind(kind) ? "var(--pos)" : "var(--neg)", borderColor: "currentColor" }}>
            {isAssetKind(kind) ? "asset" : "liability"}
          </span>
          <button onClick={submit} style={{ ...pill, fontWeight: 700, color: "var(--persona-solid)" }}>Add account</button>
          <button onClick={() => setAdding(false)} style={{ ...pill, color: "var(--fl-muted)" }}>Cancel</button>
        </section>
      ) : (
        <button onClick={() => setAdding(true)} style={{ ...pill, justifySelf: "start", color: "var(--persona-solid)" }}>＋ Add an account</button>
      )}
    </div>
  );
}
