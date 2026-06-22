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
