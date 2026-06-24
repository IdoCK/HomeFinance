import type { CSSProperties } from "react";
import { formatMoney } from "@/components/money";

/** Non-color shape cues so a legend stays readable without color (and so a
 *  swatch can be matched to its mark in a colorblind-safe chart). */
export type LegendShape = "dot" | "square" | "diamond" | "leaf";

const SHAPE_STYLE: Record<LegendShape, CSSProperties> = {
  dot: { borderRadius: "50%" },
  square: { borderRadius: 2 },
  diamond: { borderRadius: 2, transform: "rotate(45deg)" },
  leaf: { borderRadius: "2px 9px 2px 9px" },
};

const SHAPE_ORDER: LegendShape[] = ["dot", "square", "diamond", "leaf"];

/** The shape style for a named shape — exported so a chart's marks (e.g. the
 *  DotMatrix dots) can be kept in sync with their legend swatch. */
export function shapeStyle(shape: LegendShape): CSSProperties {
  return SHAPE_STYLE[shape];
}

/** A stable shape for the i-th series, cycling through the shape set. */
export function shapeAt(i: number): LegendShape {
  return SHAPE_ORDER[i % SHAPE_ORDER.length];
}

export type LegendItem = {
  label: string;
  color: string;
  /** Optional bold total shown after the label. */
  total?: number;
  /** Non-color cue. Defaults to a dot. */
  shape?: LegendShape;
};

/** Shared horizontal legend: a shaped swatch + label (+ optional bold total) per
 *  item. Replaces the four near-identical legend blocks the charts grew. */
export function Legend({
  items,
  size = 9,
  gap = 16,
  justify = "flex-start",
  format = formatMoney,
}: {
  items: LegendItem[];
  /** Swatch edge length in px. */
  size?: number;
  gap?: number;
  justify?: CSSProperties["justifyContent"];
  format?: (n: number) => string;
}) {
  return (
    <div style={{ display: "flex", gap, flexWrap: "wrap", justifyContent: justify, fontSize: 11.5, color: "var(--fl-muted)" }}>
      {items.map((it, i) => (
        <span key={`${it.label}-${i}`} style={{ display: "inline-flex", alignItems: "center" }}>
          <span
            data-swatch
            style={{ display: "inline-block", width: size, height: size, background: it.color, marginRight: 6, ...SHAPE_STYLE[it.shape ?? "dot"] }}
          />
          {it.label}
          {it.total != null && (
            <b style={{ color: "var(--fl-ink)", fontWeight: 800, marginLeft: 5 }}>{format(it.total)}</b>
          )}
        </span>
      ))}
    </div>
  );
}
