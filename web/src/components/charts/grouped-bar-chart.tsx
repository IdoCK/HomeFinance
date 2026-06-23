import { formatMoney } from "@/components/money";
import { barPct, categoryColor } from "./_svg";

export type GroupedRow = { name: string; a: number; b: number };

/** Two-bucket grouped bar chart (the old Compare tab). Each category shows a pair
 *  of horizontal bars — bucket A then bucket B — on one shared scale, so the two
 *  buckets read as directly comparable. Div-based like the other hand-rolled bars;
 *  colors are persona-neutral so the two buckets stay distinct in every view. */
export function GroupedBarChart({
  rows,
  labelA,
  labelB,
  format = formatMoney,
}: {
  rows: GroupedRow[];
  labelA: string;
  labelB: string;
  format?: (n: number) => string;
}) {
  const colorA = categoryColor(0); // blue
  const colorB = categoryColor(3); // amber
  const max = Math.max(1, ...rows.flatMap((r) => [Math.abs(r.a), Math.abs(r.b)]));

  if (rows.length === 0) {
    return <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>No spending in range.</div>;
  }

  return (
    <div>
      <div style={{ display: "flex", gap: 16, fontSize: 11.5, color: "var(--fl-muted)", marginBottom: 12 }}>
        <Swatch color={colorA} label={labelA} />
        <Swatch color={colorB} label={labelB} />
      </div>
      <div style={{ display: "grid", gap: 12 }}>
        {rows.map((r) => (
          <div key={r.name} style={{ display: "grid", gap: 5 }}>
            <span style={{ fontSize: 12.5 }}>{r.name}</span>
            <Bar color={colorA} pct={barPct(r.a, max)} value={r.a} format={format} />
            <Bar color={colorB} pct={barPct(r.b, max)} value={r.b} format={format} />
          </div>
        ))}
      </div>
    </div>
  );
}

function Swatch({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{ width: 9, height: 9, borderRadius: 3, background: color }} />
      {label}
    </span>
  );
}

function Bar({ color, pct, value, format }: { color: string; pct: number; value: number; format: (n: number) => string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{ flex: 1, height: 8, borderRadius: 99, background: "var(--fl-frame)", overflow: "hidden" }}>
        <span style={{ display: "block", height: "100%", borderRadius: 99, width: `${pct}%`, background: color, transition: "width 240ms ease" }} />
      </span>
      <b style={{ width: 78, textAlign: "right", fontSize: 12, fontWeight: 800, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" }}>
        {format(value)}
      </b>
    </div>
  );
}
