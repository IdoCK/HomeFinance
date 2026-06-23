import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import { AreaChart } from "./area-chart";

const points = [
  { value: 0 },
  { value: 1500 },
  { value: -200 },
  { value: 900 },
];

// axisTicks(-200, 1500) → [-200, 0, 1500] (3 ticks)
// gridlines: 3 <line> elements outside defs
// tick labels: 3 <text> elements for the ticks
// last-point value label: 1 additional <text> element  → total 4 texts
const EXPECTED_GRIDLINES = 3;
const EXPECTED_TEXTS = 4; // 3 tick labels + 1 value label

test("renders without crashing (basic smoke test)", () => {
  const { container } = render(<AreaChart points={points} />);
  expect(container.querySelector("svg")).not.toBeNull();
});

test("renders exact count of y-axis gridlines when showAxis=true", () => {
  const { container } = render(<AreaChart points={points} showAxis />);
  const gridLines = Array.from(container.querySelectorAll("line")).filter(
    (el) => !el.closest("defs") && !el.closest("pattern")
  );
  expect(gridLines).toHaveLength(EXPECTED_GRIDLINES);
});

test("renders exact count of text elements (tick labels + value label) when showAxis=true", () => {
  const { container } = render(<AreaChart points={points} showAxis />);
  const texts = container.querySelectorAll("text");
  expect(texts).toHaveLength(EXPECTED_TEXTS);
});

test("renders zero gridline when domain spans negative to positive", () => {
  const { container } = render(<AreaChart points={points} showAxis />);
  // The zero tick label must exist
  const texts = Array.from(container.querySelectorAll("text"));
  const hasZeroLabel = texts.some((t) => {
    const content = t.textContent ?? "";
    // formatMoney(0) → "$0.00" or similar; also catch custom formatters that emit "0"
    return content === "$0.00" || content === "0" || content === "$0";
  });
  expect(hasZeroLabel).toBe(true);
});

test("renders last-point value label when showAxis=true", () => {
  const { container } = render(<AreaChart points={points} showAxis />);
  const texts = container.querySelectorAll("text");
  expect(texts).toHaveLength(EXPECTED_TEXTS);
});

test("does not render axis elements when showAxis=false (default for sparklines)", () => {
  const { container } = render(<AreaChart points={points} area={false} />);
  // default showAxis should be false when area=false (sparkline usage)
  const svgLines = Array.from(container.querySelectorAll("line")).filter(
    (el) => !el.closest("defs") && !el.closest("pattern")
  );
  expect(svgLines).toHaveLength(0);
  // No text labels either
  expect(container.querySelectorAll("text")).toHaveLength(0);
});

test("accepts custom valueFormat prop", () => {
  const { container } = render(
    <AreaChart points={points} showAxis valueFormat={(n) => `€${n}`} />
  );
  const texts = Array.from(container.querySelectorAll("text"));
  const textContents = texts.map((t) => t.textContent);
  expect(textContents.some((t) => t?.startsWith("€"))).toBe(true);
});

// ── All-equal-values alignment regression ──────────────────────────────────
// When all data values are identical (e.g. [100, 100]), AreaChart computes:
//   min = Math.min(0, 100) = 0,  max = Math.max(0, 100) = 100
// So the domain is [0, 100], and axisTicks(0, 100) returns [0, 100] — 2 ticks.
// layout() calls scale(100, 0, 100, inner) = inner → y = h - pad - inner = pad.
// tickY(100) must call scale(100, 0, 100, inner) identically — the removed
// `max===min ? max+1 : max` guard was only triggered when ALL values equal AND
// those values equal 0 (since min anchors at 0). The real divergence case is
// ALL-ZERO values: min=0, max=0, where the guard previously used max+1=1.
//
// This test uses the all-zero series to exercise the actual degenerate case:
// scale(0, 0, 0, inner) = inner/2 (midpoint). The removed guard would have
// produced scale(0, 0, 1, inner) = 0 (bottom), causing misalignment.
test("all-equal zero values: gridline y aligns with data point y", () => {
  const equalPoints = [{ value: 0 }, { value: 0 }];
  const { container } = render(<AreaChart points={equalPoints} showAxis />);

  // min=0, max=0 → axisTicks(0, 0) returns [0] — one gridline
  const gridLines = Array.from(container.querySelectorAll("line")).filter(
    (el) => !el.closest("defs") && !el.closest("pattern")
  );
  expect(gridLines).toHaveLength(1);

  // The SVG line element: y1 attribute holds the gridline y
  const gridlineY = Number(gridLines[0].getAttribute("y1"));

  // scale(0, 0, 0, inner) = inner/2  →  y = h - pad - inner/2
  // With defaults h=120, pad=6: inner=108, y = 120-6-54 = 60
  const h = 120;
  const pad = 6;
  const inner = h - pad * 2; // 108
  const expectedY = Math.round(h - pad - inner / 2); // 60

  expect(gridlineY).toBe(expectedY);
  // If the old max+1 guard were present, tickY(0) = scale(0,0,1,108)=0 → y=114 ≠ 60

  // The data path must also be rendered without crash
  const paths = container.querySelectorAll("path");
  expect(paths.length).toBeGreaterThan(0);
});
