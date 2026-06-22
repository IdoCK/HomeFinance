import { expect, test } from "vitest";
import { allocateDots, layout, scale, toPath } from "./_svg";

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

test("allocateDots apportions proportionally and sums to total", () => {
  const out = allocateDots([58, 42], 21);
  expect(out.reduce((a, b) => a + b, 0)).toBe(21);
  expect(out[0]).toBeGreaterThan(out[1]); // 58% gets more dots than 42%
});

test("allocateDots handles all-zero / negative input without NaN", () => {
  expect(allocateDots([0, 0], 21)).toEqual([0, 0]);
  expect(allocateDots([-5, 0], 10)).toEqual([0, 0]);
});
