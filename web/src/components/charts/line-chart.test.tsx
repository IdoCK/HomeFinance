import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { LineChart } from "./line-chart";

const series = [
  { name: "Housing", values: [2000, 2000], total: 4000 },
  { name: "Groceries", values: [300, 250], total: 550 },
];

// Domain: min=0, max=2000  →  axisTicks(0, 2000) = [0, 2000] (2 ticks)
// gridlines: 2 <line> elements
// tick labels: 2 <text> for ticks  + 2 value labels (last point per series) = 4 texts
const EXPECTED_GRIDLINES = 2;
const EXPECTED_TEXTS = 4; // 2 tick labels + 2 series last-point labels

test("renders one path per series plus a legend with totals", () => {
  const { container } = render(<LineChart series={series} labels={["2026-04", "2026-05"]} />);
  expect(container.querySelectorAll("path")).toHaveLength(2);
  expect(screen.getByText("Housing")).toBeInTheDocument();
  expect(screen.getByText("$4,000.00")).toBeInTheDocument();
});

test("shows an empty state with no series", () => {
  render(<LineChart series={[]} labels={[]} />);
  expect(screen.getByText(/No spending in range/)).toBeInTheDocument();
});

test("renders exact count of y-axis gridlines as <line> elements when showAxis=true", () => {
  const { container } = render(
    <LineChart series={series} labels={["2026-04", "2026-05"]} showAxis />
  );
  // gridlines must be <line> elements, not <path>, so path count stays equal to series count
  const lines = container.querySelectorAll("line");
  expect(lines).toHaveLength(EXPECTED_GRIDLINES);
});

test("renders exact count of text elements (tick labels + value labels) when showAxis=true", () => {
  const { container } = render(
    <LineChart series={series} labels={["2026-04", "2026-05"]} showAxis />
  );
  const texts = container.querySelectorAll("text");
  expect(texts).toHaveLength(EXPECTED_TEXTS);
});

test("renders zero gridline when showAxis=true (domain includes 0)", () => {
  const { container } = render(
    <LineChart series={series} labels={["2026-04", "2026-05"]} showAxis />
  );
  // The zero tick label must exist (domain min=0, so 0 is the bottom tick)
  const texts = Array.from(container.querySelectorAll("text"));
  const hasZeroLabel = texts.some((t) => {
    const content = t.textContent ?? "";
    return content === "$0.00" || content === "0" || content === "$0";
  });
  expect(hasZeroLabel).toBe(true);
  // If zero were dropped from axisTicks, this fails — confirming it catches the case
  expect(container.querySelectorAll("line")).toHaveLength(EXPECTED_GRIDLINES);
});

test("renders last-point value label when showAxis=true", () => {
  const { container } = render(
    <LineChart series={series} labels={["2026-04", "2026-05"]} showAxis />
  );
  const texts = container.querySelectorAll("text");
  expect(texts).toHaveLength(EXPECTED_TEXTS);
});

test("path count stays equal to series count even with showAxis=true", () => {
  const { container } = render(
    <LineChart series={series} labels={["2026-04", "2026-05"]} showAxis />
  );
  expect(container.querySelectorAll("path")).toHaveLength(2);
});

// ── Partial (in-progress month) marker ─────────────────────────────────────

test("renders dashed partial segments when the last point is partial", () => {
  const { container } = render(
    <LineChart series={series} labels={["2026-04", "2026-05"]} partial={[false, true]} />
  );
  const dashed = Array.from(container.querySelectorAll("path")).filter((p) =>
    p.getAttribute("stroke-dasharray")
  );
  expect(dashed.length).toBeGreaterThan(0);
});

test("partial column label surfaces a (so far) affordance", () => {
  render(
    <LineChart series={series} labels={["2026-04", "2026-05"]} partial={[false, true]} />
  );
  expect(screen.getByText(/so far/i)).toBeInTheDocument();
});

test("no dashed partial paths when partial omitted (path count = series count)", () => {
  const { container } = render(
    <LineChart series={series} labels={["2026-04", "2026-05"]} />
  );
  const dashed = Array.from(container.querySelectorAll("path")).filter((p) =>
    p.getAttribute("stroke-dasharray")
  );
  expect(dashed).toHaveLength(0);
  expect(container.querySelectorAll("path")).toHaveLength(2);
});

test("does not render gridlines or tick labels when showAxis=false", () => {
  const { container } = render(
    <LineChart series={series} labels={["2026-04", "2026-05"]} showAxis={false} />
  );
  // No gridline <line> elements and no axis <text> elements when showAxis is off
  expect(container.querySelectorAll("line")).toHaveLength(0);
  expect(container.querySelectorAll("text")).toHaveLength(0);
  // Series paths are still rendered
  expect(container.querySelectorAll("path")).toHaveLength(2);
});
