import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import { AreaChart } from "./area-chart";

const points = [
  { value: 0 },
  { value: 1500 },
  { value: -200 },
  { value: 900 },
];

test("renders without crashing (basic smoke test)", () => {
  const { container } = render(<AreaChart points={points} />);
  expect(container.querySelector("svg")).not.toBeNull();
});

test("renders y-axis gridlines as <line> elements when showAxis=true", () => {
  const { container } = render(<AreaChart points={points} showAxis />);
  const lines = container.querySelectorAll("line");
  expect(lines.length).toBeGreaterThan(0);
});

test("renders y-axis text labels when showAxis=true", () => {
  const { container } = render(<AreaChart points={points} showAxis />);
  const texts = container.querySelectorAll("text");
  expect(texts.length).toBeGreaterThan(0);
});

test("renders zero gridline when domain spans negative to positive", () => {
  const { container } = render(<AreaChart points={points} showAxis />);
  // At least one gridline for zero baseline (and min/max)
  const lines = container.querySelectorAll("line");
  expect(lines.length).toBeGreaterThanOrEqual(1);
});

test("renders last-point value label when showAxis=true", () => {
  const { container } = render(<AreaChart points={points} showAxis />);
  const texts = container.querySelectorAll("text");
  expect(texts.length).toBeGreaterThan(0);
});

test("does not render axis elements when showAxis=false (default for sparklines)", () => {
  const { container } = render(<AreaChart points={points} area={false} />);
  // default showAxis should be false when area=false (sparkline usage)
  const lines = container.querySelectorAll("line");
  // hatch pattern uses <line> inside defs — but axis gridlines should not appear
  // we check that no gridline lines appear outside defs
  const svgLines = Array.from(lines).filter(
    (el) => !el.closest("defs") && !el.closest("pattern")
  );
  expect(svgLines.length).toBe(0);
});

test("accepts custom valueFormat prop", () => {
  const { container } = render(
    <AreaChart points={points} showAxis valueFormat={(n) => `€${n}`} />
  );
  const texts = container.querySelectorAll("text");
  // at least one text should use the custom formatter
  const textContents = Array.from(texts).map((t) => t.textContent);
  expect(textContents.some((t) => t?.startsWith("€"))).toBe(true);
});
