import { expect, test } from "vitest";
import { allocateDots, barPct, categoryColor, divergingWidths, layout, layoutShared, scale, toPath } from "./_svg";

test("scale maps value within range onto pixel size", () => {
  expect(scale(0, 0, 10, 100)).toBe(0);
  expect(scale(10, 0, 10, 100)).toBe(100);
  expect(scale(5, 0, 10, 100)).toBe(50);
  // degenerate range → midpoint
  expect(scale(5, 5, 5, 100)).toBe(50);
});

test("layout spaces points evenly and inverts y for SVG", () => {
  const pts = layout([0, 10], 600, 100, 0);
  expect(pts).toHaveLength(2);
  expect(pts[0].x).toBe(0);
  expect(pts[1].x).toBe(600);
  // higher value sits higher on screen → smaller y
  expect(pts[1].y).toBeLessThan(pts[0].y);
});

test("toPath emits a move then line segments", () => {
  expect(toPath([{ x: 0, y: 0 }, { x: 10, y: 20 }])).toBe("M 0 0 L 10 20");
  expect(toPath([])).toBe("");
});

test("toPath smooth emits cubic beziers for 3+ points", () => {
  const d = toPath([{ x: 0, y: 0 }, { x: 10, y: 10 }, { x: 20, y: 0 }], true);
  expect(d.startsWith("M 0 0")).toBe(true);
  expect(d).toContain("C ");
});

test("layoutShared puts all series on one domain so equal values share a y", () => {
  const [a, b] = layoutShared([[0, 10], [0, 5]], 600, 100, 0);
  // x positions line up across series
  expect(a[0].x).toBe(b[0].x);
  expect(a[1].x).toBe(b[1].x);
  // the global max (10) sits at the top (y≈0); 5 is halfway down
  expect(a[1].y).toBeCloseTo(0, 1);
  expect(b[1].y).toBeCloseTo(50, 1);
  // a value of 0 sits at the bottom in both
  expect(a[0].y).toBe(b[0].y);
});

test("layoutShared handles empty input", () => {
  expect(layoutShared([], 600, 100)).toEqual([]);
});

test("categoryColor cycles through the palette and is persona-independent", () => {
  expect(categoryColor(0)).toBe("#3B82F6");
  expect(categoryColor(1)).not.toBe(categoryColor(0)); // adjacent series differ
  expect(categoryColor(8)).toBe(categoryColor(0)); // wraps
});

test("allocateDots apportions proportionally and sums to total", () => {
  const out = allocateDots([58, 42], 21);
  expect(out.reduce((a, b) => a + b, 0)).toBe(21);
  expect(out[0]).toBeGreaterThan(out[1]); // 58% gets more dots than 42%
});

test("allocateDots handles all-zero / negative input without NaN", () => {
  expect(allocateDots([0, 0], 21)).toEqual([0, 0]);
  expect(allocateDots([-5, 0], 10)).toEqual([0, 0]);
});

test("barPct scales magnitude against a shared max and clamps", () => {
  expect(barPct(50, 100)).toBe(50);
  expect(barPct(-50, 100)).toBe(50); // magnitude
  expect(barPct(200, 100)).toBe(100); // clamped
  expect(barPct(5, 0)).toBe(0); // degenerate max
});

test("divergingWidths grows the correct half around the center axis", () => {
  expect(divergingWidths(40, 100)).toEqual({ left: 0, right: 40 });
  expect(divergingWidths(-40, 100)).toEqual({ left: 40, right: 0 });
  expect(divergingWidths(0, 100)).toEqual({ left: 0, right: 0 });
});
