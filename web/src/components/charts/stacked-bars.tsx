import { formatMoney } from "@/components/money";

export type StackRow = { label: string; value: number; pct: number; color: string };

/** "This month" Income / Spending / Saved rows: label + value, with a thin
 *  progress track beneath each. (Reference .ln / .bar.) */
export function StackedBars({ rows }: { rows: StackRow[] }) {
  return (
    <div>
      {rows.map((r) => (
        <div key={r.label} style={{ margin: "11px 0" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 12.5 }}>
            <span style={{ display: "flex", alignItems: "center", gap: 8, color: "#4B5059" }}>
              <span style={{ width: 9, height: 9, borderRadius: 3, background: r.color }} />
              {r.label}
            </span>
            <span style={{ fontWeight: 800, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" }}>
              {formatMoney(r.value)}
            </span>
          </div>
          <div style={{ height: 6, borderRadius: 99, background: "#EEF0F3", overflow: "hidden", marginTop: 5 }}>
            <div
              style={{
                height: "100%",
                borderRadius: 99,
                width: `${Math.max(0, Math.min(100, Math.round(r.pct)))}%`,
                background: r.color,
                transition: "width 240ms ease",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
