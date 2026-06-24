import { beforeEach, expect, test } from "vitest";
import { addChart, loadCharts, moveChart, newId, removeChart } from "./chart-store";
import type { ChartSpec } from "./chart-spec";

const mk = (id: string): ChartSpec => ({ id, title: id, metric: "net", kind: "area", months: 12 });

beforeEach(() => localStorage.clear());

test("starts empty", () => {
  expect(loadCharts()).toEqual([]);
});

test("add then load round-trips, removing tolerates a missing id", () => {
  addChart(mk("a"));
  addChart(mk("b"));
  expect(loadCharts().map((c) => c.id)).toEqual(["a", "b"]);
  removeChart("a");
  expect(loadCharts().map((c) => c.id)).toEqual(["b"]);
  expect(() => removeChart("nope")).not.toThrow();
});

test("moveChart reorders and clamps at the ends", () => {
  addChart(mk("a")); addChart(mk("b")); addChart(mk("c"));
  expect(moveChart("c", -1).map((c) => c.id)).toEqual(["a", "c", "b"]);
  // "a" is already first — moving earlier is a no-op.
  expect(moveChart("a", -1).map((c) => c.id)).toEqual(["a", "c", "b"]);
});

test("newId produces distinct ids", () => {
  expect(newId()).not.toBe(newId());
});

test("corrupt storage degrades to empty", () => {
  localStorage.setItem("homefinance.studio_charts", "{not json");
  expect(loadCharts()).toEqual([]);
});
