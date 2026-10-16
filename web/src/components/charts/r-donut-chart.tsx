import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { formatMoney } from "@/components/money";
import { categoryColor } from "./_svg";
import { Legend, shapeAt } from "./legend";
import { monthLabel } from "./chart-kit";

export type DonutSlice = { name: string; value: number; color?: string };

/** Recharts donut for a part-of-whole breakdown (e.g. spending share by category).
 *  Center shows the total. Persona-excluding category ramp, ledger-slip tooltip
 *  with each slice's share, bold-total legend with non-color shape cues. */
export function DonutChart({
  slices,
  height = 200,
  ariaLabel = "Breakdown",
  valueFormat = formatMoney,
}: {
  slices: DonutSlice[];
  height?: number;
  ariaLabel?: string;
  valueFormat?: (n: number) => string;
}) {
  const data = slices.filter((s) => s.value > 0).map((s, i) => ({ ...s, color: s.color ?? categoryColor(i) }));
  if (data.length === 0) {
    return <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>No data in range.</div>;
  }
  const total = data.reduce((a, s) => a + s.value, 0);

  return (
    <div>
      <div style={{ position: "relative" }}>
        <ResponsiveContainer width="100%" height={height}>
          <PieChart accessibilityLayer aria-label={ariaLabel}>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius="62%"
              outerRadius="92%"
              paddingAngle={1.5}
              stroke="var(--fl-card)"
              strokeWidth={2}
              isAnimationActive={false}
            >
              {data.map((s) => <Cell key={s.name} fill={s.color} />)}
            </Pie>
            <Tooltip content={<DonutTooltip total={total} valueFormat={valueFormat} />} />
          </PieChart>
        </ResponsiveContainer>
        {/* Center total — absolutely centered over the donut hole. */}
        <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", pointerEvents: "none" }}>
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--fl-muted)" }}>Total</span>
          <span style={{ fontSize: 20, fontWeight: 800, fontVariantNumeric: "tabular-nums", color: "var(--fl-ink)" }}>{valueFormat(total)}</span>
        </div>
      </div>
      <div style={{ marginTop: 10 }}>
        <Legend
          justify="center"
          items={data.map((s, i) => ({ label: s.name, color: s.color, total: s.value, shape: shapeAt(i) }))}
          format={valueFormat}
        />
      </div>
    </div>
  );
}

function DonutTooltip({
  active,
  payload,
  total,
  valueFormat,
}: {
  active?: boolean;
  payload?: { name?: string; value?: number; payload?: { color?: string } }[];
  total: number;
  valueFormat: (n: number) => string;
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0];
  if (p.value == null) return null;
  const pct = total > 0 ? Math.round((p.value / total) * 100) : 0;
  return (
    <div style={{ background: "var(--fl-card)", border: "1px solid var(--fl-line)", borderRadius: 12, boxShadow: "0 12px 28px -14px rgba(22,24,29,.45)", padding: "9px 11px", fontSize: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 8, height: 8, borderRadius: "50%", background: p.payload?.color ?? "var(--fl-ink)", flex: "none" }} />
        <span style={{ color: "var(--fl-ink)" }}>{monthLabel(p.name ?? "")}</span>
        <span style={{ marginLeft: 12, fontWeight: 800, fontVariantNumeric: "tabular-nums", color: "var(--fl-ink)" }}>{valueFormat(p.value)}</span>
        <span style={{ marginLeft: 6, color: "var(--fl-muted)" }}>· {pct}%</span>
      </div>
    </div>
  );
}
