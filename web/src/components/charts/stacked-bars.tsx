import { formatMoney } from "@/components/money";
import { Legend } from "./legend";

export type StackSegment = { label: string; value: number; color: string };
export type StackRow = {
  label: string;
  value: number;
  pct: number;
  color: string;
  /** Optional sub-composition of this row (e.g. committed vs discretionary). The
   *  track renders one fill per segment (widths proportional to the row total, so
   *  the filled width still equals `pct`), with a small legend beneath. */
  segments?: StackSegment[];
};

/** "This month" Income / Spending / Saved rows: label + value, with a thin
 *  progress track beneath each. A row may carry `segments` to break its track
 *  into a labeled composition. (Reference .ln / .bar.) */
export function StackedBars({ rows }: { rows: StackRow[] }) {
  return (
    <div>
      {rows.map((r) => {
        const hasSegments = r.segments != null && r.segments.length > 0;
        return (
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
            <div style={{ height: 6, borderRadius: 99, background: "#EEF0F3", overflow: "hidden", marginTop: 5, display: "flex" }}>
              {hasSegments ? (
                r.segments!.map((s, i) => (
                  <div
                    key={`${s.label}-${i}`}
                    data-segment
                    title={`${s.label}: ${formatMoney(s.value)}`}
                    style={{
                      height: "100%",
                      width: `${Math.max(0, Math.min(100, (s.value / (r.value || 1)) * r.pct))}%`,
                      background: s.color,
                      transition: "width 240ms ease",
                    }}
                  />
                ))
              ) : (
                <div
                  style={{
                    height: "100%",
                    borderRadius: 99,
                    width: `${Math.max(0, Math.min(100, Math.round(r.pct)))}%`,
                    background: r.color,
                    transition: "width 240ms ease",
                  }}
                />
              )}
            </div>
            {hasSegments && (
              <div style={{ marginTop: 5 }}>
                <Legend
                  size={8}
                  gap={12}
                  items={r.segments!.map((s) => ({ label: s.label, color: s.color, total: s.value }))}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
