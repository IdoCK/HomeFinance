import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { DonutChart } from "./r-donut-chart";

const slices = [
  { name: "Housing", value: 2000 },
  { name: "Groceries", value: 500 },
];

test("empty state when all slices are zero", () => {
  render(<DonutChart slices={[{ name: "x", value: 0 }]} />);
  expect(screen.getByText(/No data in range/)).toBeInTheDocument();
});

test("shows the center total and a legend with each slice", () => {
  render(<DonutChart slices={slices} />);
  expect(screen.getByText("Total")).toBeInTheDocument();
  expect(screen.getByText("$2,500.00")).toBeInTheDocument(); // total
  expect(screen.getByText("Housing")).toBeInTheDocument();
  expect(screen.getByText("Groceries")).toBeInTheDocument();
});
