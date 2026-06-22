import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { getNetWorth, addAccount, updateAccountBalance, deleteAccount, getReconciliation, type Account, type NetWorthData, type Reconciliation } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Money, formatMoney } from "@/components/money";
import { AreaChart } from "@/components/charts/area-chart";
import { Loading } from "@/components/loading";

const KINDS = ["checking", "savings", "investment", "property", "credit_card", "loan", "other"];
const LIABILITY_KINDS = new Set(["credit_card", "loan"]);
const isAssetKind = (kind: string) => !LIABILITY_KINDS.has(kind);

const pill: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "6px 12px",
  fontSize: 13, background: "transparent", color: "var(--fl-ink)",
};
const badge: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "2px 10px",
  fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--fl-muted)",
};

function AccountRow({ a, onSave, onRemove }: {
  a: Account; onSave: (a: Account, v: string) => void; onRemove: (a: Account) => void;
}) {
  const asset = !!a.is_asset;
  return (
    <section className="frosted-card" style={{ padding: 16, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
      <span style={{ fontWeight: 700 }}>{a.name}</span>
      <span style={badge}>{a.kind.replace("_", " ")}</span>
      <span style={{ ...badge, color: asset ? "var(--pos)" : "var(--neg)", borderColor: "currentColor" }}>
        {asset ? "asset" : "liability"}
      </span>
      <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
        <input
          type="number"
          defaultValue={a.balance}
          aria-label={`Balance for ${a.name}`}
          onBlur={(e) => onSave(a, e.target.value)}
          style={{ ...pill, width: 130, padding: "4px 10px", textAlign: "right" }}
        />
        <button
          onClick={() => onRemove(a)}
          aria-label={`Remove ${a.name} account`}
          style={{ border: "none", background: "none", color: "var(--fl-muted)", cursor: "pointer", fontSize: 16, lineHeight: 1 }}
        >
          ✕
        </button>
      </span>
    </section>
  );
}

export default function NetWorth() {
  const { personId, label } = usePersona();
  const [data, setData] = useState<NetWorthData | null>(null);
  const [recon, setRecon] = useState<Reconciliation | null>(null);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("checking");
  const [balance, setBalance] = useState("");

  const load = useCallback(
    () => getNetWorth({ personId }).then(setData).catch(() => setData(null)),
    [personId],
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
        {trend.length >= 2
          ? <AreaChart points={trend.map((p) => ({ value: p.net }))} area={false} mode="linear" height={64} accent="var(--persona-solid)" ariaLabel="Net worth trend" />
          : <div style={{ color: "var(--fl-muted)", fontSize: 13 }}>Add a second snapshot to see a trend.</div>}
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

      {recon && recon.reconcilable && (
        <section className="frosted-card" aria-label="Statement reconciliation" style={{ padding: 20, display: "grid", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--fl-muted)" }}>
              Statement reconciliation
            </span>
            <span style={{
              fontWeight: 700, fontSize: 13,
              color: recon.ok ? "#22C55E" : "#EF4444",
            }}>
              {recon.ok ? "✓ Statements tie out" : `⚠ Off by ${formatMoney(Math.abs(recon.discrepancy))}`}
            </span>
          </div>
          <div style={{ color: "var(--fl-muted)", fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
            {formatMoney(recon.begin)} opening → {formatMoney(recon.end)} ending across {recon.n} rows
            {recon.chain_breaks > 0 && `; ${recon.chain_breaks} balance break${recon.chain_breaks === 1 ? "" : "s"}`}
          </div>
        </section>
      )}

      {accounts.length === 0 && !adding && (
        <section className="frosted-card" style={{ padding: 32, textAlign: "center", color: "var(--fl-muted)" }}>
          No accounts yet. Add one to start tracking net worth.
        </section>
      )}

      <div style={{ display: "grid", gap: 10 }}>
        {accounts.map((a) => <AccountRow key={a.id} a={a} onSave={commitBalance} onRemove={remove} />)}
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
