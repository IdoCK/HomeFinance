// Tiny shared helpers for the hand-rolled SVG chart primitives. No deps —
// data volumes are tiny (≤~12 months, a handful of categories), so a charting
// library would cost bundle size and still not draw the bespoke visuals
// (45° hatch fill, proportional dot-matrix). See docs/ui-fix-plan/02-frontend.md §4.

export type Pt = { x: number; y: number };

export function round(n: number): number {
  return Math.round(n * 100) / 100;
}

/** Map `value` within [min,max] onto [0,size] (0 = bottom of an SVG box). */
export function scale(value: number, min: number, max: number, size: number): number {
  if (max === min) return size / 2;
  return ((value - min) / (max - min)) * size;
}

/** Lay a numeric series out as evenly-spaced x positions with y inverted for
 *  SVG (top-left origin). The baseline includes 0 so positive/negative read
 *  correctly. `pad` reserves vertical space top & bottom. */
export function layout(values: number[], w: number, h: number, pad = 4): Pt[] {
  if (values.length === 0) return [];
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const span = values.length > 1 ? values.length - 1 : 1;
  const inner = h - pad * 2;
  return values.map((v, i) => ({
    x: round((i / span) * w),
    y: round(h - pad - scale(v, min, max, inner)),
  }));
}

/** Lay out several series on ONE shared y-domain, so lines are comparable across
 *  series (e.g. spend-by-category over the same months). All series must share the
 *  same length (x positions line up). The domain includes 0 so a baseline reads
 *  correctly. Returns one Pt[] per input series. */
export function layoutShared(series: number[][], w: number, h: number, pad = 4): Pt[][] {
  const all = series.flat();
  if (all.length === 0) return series.map(() => []);
  const min = Math.min(0, ...all);
  const max = Math.max(0, ...all);
  const inner = h - pad * 2;
  return series.map((vals) => {
    const span = vals.length > 1 ? vals.length - 1 : 1;
    return vals.map((v, i) => ({
      x: round((i / span) * w),
      y: round(h - pad - scale(v, min, max, inner)),
    }));
  });
}

/** Categorical color ramp for multi-series charts. Fixed, well-separated hues
 *  drawn from the brand palette. Deliberately NOT persona-relative: a category's
 *  color must stay stable when you switch persona. The two PERSONA hues
 *  (#3B82F6 blue = you, #EC4899 pink = spouse) are intentionally EXCLUDED so a
 *  generic category can never masquerade as a person in a chart. Wraps when there
 *  are more series than colors. */
export const CATEGORY_COLORS = [
  "#A855F7", // violet
  "#F59E0B", // amber
  "#06B6D4", // cyan
  "#10B981", // emerald
  "#F43F5E", // rose
  "#64748B", // slate
];

export function categoryColor(i: number): string {
  return CATEGORY_COLORS[i % CATEGORY_COLORS.length];
}

/** Percentage width [0,100] of `value` against a shared `max` — for the div-based
 *  grouped/diverging bars. Negative values use their magnitude; clamps to the track. */
export function barPct(value: number, max: number): number {
  if (max <= 0) return 0;
  return round(Math.max(0, Math.min(1, Math.abs(value) / max)) * 100);
}

/** Split a signed value into the two halves of a diverging (tornado) bar around a
 *  center axis: negative grows the left half, positive the right, each [0,100] of
 *  its half-track. Used by the People per-category breakdown. */
export function divergingWidths(value: number, max: number): { left: number; right: number } {
  const pct = barPct(value, max);
  return value < 0 ? { left: pct, right: 0 } : { left: 0, right: pct };
}

/** SVG path through points. `smooth` uses Catmull-Rom→cubic-bezier for a gentle
 *  curve; otherwise straight segments. */
export function toPath(points: Pt[], smooth = false): string {
  if (points.length === 0) return "";
  if (!smooth || points.length < 3) {
    return points.map((p, i) => `${i === 0 ? "M" : "L"} ${round(p.x)} ${round(p.y)}`).join(" ");
  }
  const d = [`M ${round(points[0].x)} ${round(points[0].y)}`];
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] ?? points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d.push(`C ${round(c1x)} ${round(c1y)}, ${round(c2x)} ${round(c2y)}, ${round(p2.x)} ${round(p2.y)}`);
  }
  return d.join(" ");
}

/** Return the y-axis tick values to label: always includes min, max, and 0 when
 *  it falls within the domain. Deduplicates so min===0 or max===0 don't double-
 *  emit zero. Returns values sorted ascending. */
export function axisTicks(min: number, max: number): number[] {
  if (min === max) return [min];
  const set = new Set<number>([min, max]);
  if (0 >= min && 0 <= max) set.add(0);
  return Array.from(set).sort((a, b) => a - b);
}

/** Split a points path into the settled (complete) prefix and the in-progress
 *  (partial) suffix, for the dashed "month still in progress" treatment. A point
 *  flagged partial marks the segment ARRIVING at it as in-progress; the suffix
 *  therefore starts one point earlier so the dashed segment connects to the solid
 *  line with no gap. With no flags (or none true) everything is solid. */
export function splitPartialPath(
  pts: Pt[],
  partial?: boolean[],
): { solid: Pt[]; partial: Pt[] } {
  if (!partial || pts.length === 0) return { solid: pts, partial: [] };
  const first = partial.findIndex(Boolean);
  if (first === -1) return { solid: pts, partial: [] };
  if (first === 0) return { solid: [], partial: pts };
  return { solid: pts.slice(0, first), partial: pts.slice(first - 1) };
}

/** Largest-remainder apportionment: split `dots` across `values` proportionally,
 *  guaranteeing the result sums to `dots` exactly (when the total is positive). */
export function allocateDots(values: number[], dots: number): number[] {
  const sum = values.reduce((a, b) => a + Math.max(0, b), 0);
  if (sum <= 0) return values.map(() => 0);
  const raw = values.map((v) => (Math.max(0, v) / sum) * dots);
  const floored = raw.map((r) => Math.floor(r));
  let remaining = dots - floored.reduce((a, b) => a + b, 0);
  const order = raw
    .map((r, i) => ({ i, frac: r - Math.floor(r) }))
    .sort((a, b) => b.frac - a.frac);
  for (let k = 0; k < order.length && remaining > 0; k++, remaining--) {
    floored[order[k].i]++;
  }
  return floored;
}
