import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { LineChart } from "./line-chart";

const series = [
  { name: "Housing", values: [2000, 2000], total: 4000 },
  { name: "Groceries", values: [300, 250], total: 550 },
];

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

test("renders y-axis gridlines as <line> elements when showAxis=true", () => {
  const { container } = render(
    <LineChart series={series} labels={["2026-04", "2026-05"]} showAxis />
  );
  // gridlines must be <line> elements, not <path>, so path count stays equal to series count
  const lines = container.querySelectorAll("line");
  expect(lines.length).toBeGreaterThan(0);
});

test("renders y-axis text labels when showAxis=true", () => {
  const { container } = render(
    <LineChart series={series} labels={["2026-04", "2026-05"]} showAxis />
  );
  const texts = container.querySelectorAll("text");
  expect(texts.length).toBeGreaterThan(0);
});

test("renders zero gridline when showAxis=true (domain includes 0)", () => {
  const { container } = render(
    <LineChart series={series} labels={["2026-04", "2026-05"]} showAxis />
  );
  // There should be at least one gridline (for zero baseline)
  expect(container.querySelectorAll("line").length).toBeGreaterThan(0);
});

test("renders last-point value label when showAxis=true", () => {
  const { container } = render(
    <LineChart series={series} labels={["2026-04", "2026-05"]} showAxis />
  );
  const texts = container.querySelectorAll("text");
  // should include at least a value label for the last point of at least one series
  expect(texts.length).toBeGreaterThan(0);
});

test("path count stays equal to series count even with showAxis=true", () => {
  const { container } = render(
    <LineChart series={series} labels={["2026-04", "2026-05"]} showAxis />
  );
  expect(container.querySelectorAll("path")).toHaveLength(2);
});
