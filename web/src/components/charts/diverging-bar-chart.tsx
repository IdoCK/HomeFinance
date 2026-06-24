import { formatMoney } from "@/components/money";
import { barPct } from "./_svg";
import { Legend } from "./legend";

export type DivergingRow = { category: string; a: number; b: number; shared?: boolean };

/** Per-category diverging (tornado) bar: person A grows left from a center axis,
 *  person B grows right, on one shared scale — so who-spends-more-on-what reads at
 *  a glance (the old People tab). Shared categories (both spent) get a dot marker. */
export function DivergingBarChart({
  rows,
  labelA,
  labelB,
  format = formatMoney,
}: {
  rows: DivergingRow[];
  labelA: string;
  labelB: string;
  format?: (n: number) => string;
}) {
  const colorA = "var(--persona-you)"; // you / blue
  const colorB = "var(--persona-spouse)"; // spouse / pink
  const max = Math.max(1, ...rows.flatMap((r) => [Math.abs(r.a), Math.abs(r.b)]));

  if (rows.length === 0) {
    return <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>No spending in range.</div>;
  }

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Legend
          justify="center"
          gap={18}
          items={[{ label: labelA, color: colorA, shape: "square" }, { label: labelB, color: colorB, shape: "dot" }]}
        />
      </div>
      <div style={{ display: "grid", gap: 10 }}>
        {rows.map((r) => (
          <div key={r.category} style={{ display: "grid", gap: 4 }}>
            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 6, fontSize: 12 }}>
              {r.category}
              {r.shared && (
                <span aria-label="Shared category" title="Both spent here"
                  style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--fl-muted)" }} />
              )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <b style={{ width: 72, textAlign: "right", fontSize: 11.5, fontWeight: 800, color: colorA, fontVariantNumeric: "tabular-nums" }}>
                {r.a ? format(r.a) : ""}
              </b>
              <div style={{ flex: 1, display: "flex", justifyContent: "flex-end", height: 9, background: "var(--fl-frame)", borderRadius: "99px 3px 3px 99px", overflow: "hidden" }}>
                <span style={{ width: `${barPct(r.a, max)}%`, background: colorA, borderRadius: "99px 3px 3px 99px", transition: "width 240ms ease" }} />
              </div>
              <span style={{ width: 1, alignSelf: "stretch", background: "var(--fl-line)" }} />
              <div style={{ flex: 1, display: "flex", justifyContent: "flex-start", height: 9, background: "var(--fl-frame)", borderRadius: "3px 99px 99px 3px", overflow: "hidden" }}>
                <span style={{ width: `${barPct(r.b, max)}%`, background: colorB, borderRadius: "3px 99px 99px 3px", transition: "width 240ms ease" }} />
              </div>
              <b style={{ width: 72, textAlign: "left", fontSize: 11.5, fontWeight: 800, color: colorB, fontVariantNumeric: "tabular-nums" }}>
                {r.b ? format(r.b) : ""}
              </b>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
