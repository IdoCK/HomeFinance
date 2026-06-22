import { useEffect, useState, type CSSProperties } from "react";
import { getOllamaStatus, parseImport, commitImport, type ImportRow, type OllamaStatus } from "@/lib/api";
import { usePersona } from "@/lib/persona";

const POS = "#22C55E";
const NEG = "#EF4444";

const pill: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "6px 12px",
  fontSize: 13, background: "transparent", color: "var(--fl-ink)",
};
const primaryBtn: CSSProperties = {
  border: "none", borderRadius: 999, padding: "9px 18px", fontWeight: 700,
  fontSize: 14, cursor: "pointer", background: "var(--persona)", color: "#fff",
};
const h2: CSSProperties = { fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--fl-muted)", margin: 0 };
const cell: CSSProperties = { padding: "8px 10px", borderBottom: "1px solid var(--fl-line)", fontSize: 13, textAlign: "left" };

const SOURCES: [string, string][] = [
  ["auto", "Auto-detect"], ["amazon", "Amazon"], ["card", "Credit card"], ["bank", "Bank"],
];
type Step = "upload" | "review" | "done";

function Stepper({ step }: { step: Step }) {
  const steps: [Step, string][] = [["upload", "Drop file"], ["review", "Review"], ["done", "Done"]];
  const order: Step[] = ["upload", "review", "done"];
  const at = order.indexOf(step);
  return (
    <div style={{ display: "flex", gap: 14, alignItems: "center", marginBottom: 4 }}>
      {steps.map(([key, txt], i) => (
        <span key={key} style={{
          display: "flex", alignItems: "center", gap: 6, fontSize: 13,
          fontWeight: i === at ? 700 : 500,
          color: i <= at ? "var(--persona)" : "var(--fl-muted)",
        }}>
          <span style={{
            width: 20, height: 20, borderRadius: 999, display: "grid", placeItems: "center",
            fontSize: 11, color: "#fff",
            background: i <= at ? "var(--persona)" : "var(--fl-muted)",
          }}>{i + 1}</span>
          {txt}
        </span>
      ))}
    </div>
  );
}

export default function Import() {
  const { personId, label } = usePersona();
  const [status, setStatus] = useState<OllamaStatus | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("auto");
  const [step, setStep] = useState<Step>("upload");
  const [rows, setRows] = useState<ImportRow[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [parsed, setParsed] = useState<{ file_hash: string; filename: string; source: string } | null>(null);
  const [alreadyImported, setAlreadyImported] = useState(false);
  const [busy, setBusy] = useState(false);
  const [importedCount, setImportedCount] = useState(0);

  useEffect(() => { getOllamaStatus().then(setStatus).catch(() => setStatus(null)); }, []);

  // Transactions belong to one person; Joint has no owner to import into.
  if (personId == null) {
    return (
      <div style={{ display: "grid", gap: 12, maxWidth: 560 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", fontSize: 24, margin: 0 }}>Import</h1>
        <div className="frosted-card" style={{ padding: 24, color: "var(--fl-muted)" }}>
          Imports belong to one person. Switch to Ido or Aviv in the sidebar to import a file.
        </div>
      </div>
    );
  }

  const reset = () => {
    setFile(null); setRows([]); setWarnings([]); setParsed(null);
    setAlreadyImported(false); setImportedCount(0); setStep("upload");
  };

  const doParse = async () => {
    if (!file) return;
    setBusy(true); setAlreadyImported(false);
    try {
      const res = await parseImport(file, source, personId);
      if (res.already_imported) { setAlreadyImported(true); return; }
      setRows(res.rows); setWarnings(res.warnings);
      setParsed({ file_hash: res.file_hash, filename: res.filename, source: res.source });
      setStep("review");
    } finally { setBusy(false); }
  };

  const doCommit = async () => {
    if (!parsed) return;
    setBusy(true);
    try {
      const { imported } = await commitImport({
        personId, filename: parsed.filename, fileHash: parsed.file_hash,
        source: parsed.source, rows,
      });
      setImportedCount(imported); setStep("done");
    } finally { setBusy(false); }
  };

  const editRow = (i: number, patch: Partial<ImportRow>) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  const plural = (n: number) => (n === 1 ? "" : "s");

  return (
    <div style={{ display: "grid", gap: 16, maxWidth: 960 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", fontSize: 24, margin: 0 }}>Import</h1>
        <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>into {label}'s ledger</span>
      </header>
      <Stepper step={step} />

      {step === "upload" && (
        <section className="frosted-card" style={{ padding: 24, display: "grid", gap: 16 }}>
          <div style={{ fontSize: 13, color: status?.ok ? POS : NEG }}>
            {status == null ? "Checking the local agent…"
              : status.ok ? "🟢 Local agent ready — parsing stays on your machine."
              : `🔴 ${status.message}`}
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            <label style={h2} htmlFor="import-file">Statement file</label>
            <input
              id="import-file" type="file" aria-label="Choose file"
              accept=".csv,.tsv,.xlsx,.xls"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <label style={h2} htmlFor="import-source">Source</label>
            <select id="import-source" value={source} onChange={(e) => setSource(e.target.value)} style={pill}>
              {SOURCES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </div>
          {alreadyImported && (
            <div style={{ fontSize: 13, color: NEG }}>
              This file is already imported for {label} — nothing to do.
            </div>
          )}
          <div>
            <button onClick={doParse} disabled={!file || busy} style={{ ...primaryBtn, opacity: !file || busy ? 0.5 : 1, cursor: !file || busy ? "not-allowed" : "pointer" }}>
              {busy ? "Reading…" : "Parse file"}
            </button>
          </div>
        </section>
      )}

      {step === "review" && (
        <section className="frosted-card" style={{ padding: 20, display: "grid", gap: 12 }}>
          {warnings.length > 0 && (
            <div style={{ fontSize: 13, color: NEG, background: "color-mix(in srgb, #EF4444 8%, transparent)", borderRadius: 12, padding: "10px 14px" }}>
              {warnings.map((w, i) => <div key={i}>{w}</div>)}
            </div>
          )}
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Date", "Description", "Amount", "Category", "Include"].map((h) => (
                    <th key={h} style={{ ...cell, ...h2, borderBottom: "1px solid var(--fl-line)" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} style={{ opacity: r.included ? 1 : 0.45 }}>
                    <td style={{ ...cell, fontVariantNumeric: "tabular-nums" }}>{r.date}</td>
                    <td style={cell}>{r.description}</td>
                    <td style={{ ...cell, fontVariantNumeric: "tabular-nums", color: r.amount < 0 ? NEG : POS, fontWeight: 700 }}>
                      {r.amount < 0 ? "−" : "+"}${Math.abs(r.amount).toFixed(2)}
                    </td>
                    <td style={cell}>
                      <input
                        value={r.category}
                        aria-label={`Category for ${r.description}`}
                        onChange={(e) => editRow(i, { category: e.target.value })}
                        style={{ ...pill, padding: "4px 10px" }}
                      />
                    </td>
                    <td style={{ ...cell, textAlign: "center" }}>
                      <input
                        type="checkbox" checked={r.included}
                        aria-label={`Include ${r.description}`}
                        onChange={(e) => editRow(i, { included: e.target.checked })}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={doCommit} disabled={busy} style={{ ...primaryBtn, opacity: busy ? 0.5 : 1 }}>
              {busy ? "Importing…" : `Import ${rows.length} transaction${plural(rows.length)}`}
            </button>
            <button onClick={() => setStep("upload")} style={pill}>Back</button>
          </div>
        </section>
      )}

      {step === "done" && (
        <section className="frosted-card" style={{ padding: 24, display: "grid", gap: 14 }}>
          <div style={{ fontSize: 18, fontWeight: 700 }}>
            Imported {importedCount} transaction{plural(importedCount)} into {label}'s ledger.
          </div>
          <div>
            <button onClick={reset} style={primaryBtn}>Import another file</button>
          </div>
        </section>
      )}
    </div>
  );
}
