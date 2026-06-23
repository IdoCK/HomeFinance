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
