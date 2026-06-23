import type { ReactNode } from "react";
import { AreaChart } from "./area-chart";

/** A bare trend line — the AreaChart in line-only mode — with a built-in
 *  ≥2-point gate (a single point is a dot, not a trend, and reads as a flat lie).
 *  Under the gate it renders `emptyLabel` (nothing by default). */
export function Sparkline({
  values,
  height = 28,
  accent = "var(--persona-solid)",
  mode = "linear",
  ariaLabel = "Trend",
  emptyLabel,
}: {
  values: number[];
  height?: number;
  accent?: string;
  mode?: "smooth" | "linear";
  ariaLabel?: string;
  /** Shown when there are fewer than 2 points. Omit to render nothing. */
  emptyLabel?: ReactNode;
}) {
  if (values.length < 2) {
    return emptyLabel != null
      ? <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>{emptyLabel}</span>
      : null;
  }
  return (
    <AreaChart
      points={values.map((value) => ({ value }))}
      area={false}
      mode={mode}
      height={height}
      accent={accent}
      ariaLabel={ariaLabel}
    />
  );
}
