import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Legend } from "./legend";

test("renders a labeled swatch per item", () => {
  render(
    <Legend items={[{ label: "Income", color: "var(--pos)" }, { label: "Spend", color: "var(--neg)" }]} />,
  );
  expect(screen.getByText("Income")).toBeInTheDocument();
  expect(screen.getByText("Spend")).toBeInTheDocument();
});

test("renders a bold total when provided", () => {
  render(<Legend items={[{ label: "Housing", color: "#A855F7", total: 4000 }]} />);
  expect(screen.getByText("$4,000.00")).toBeInTheDocument();
});

test("distinct shapes produce distinct swatch border-radius (colorblind-safe)", () => {
  const { container } = render(
    <Legend items={[{ label: "A", color: "#000", shape: "dot" }, { label: "B", color: "#111", shape: "square" }]} />,
  );
  const sw = Array.from(container.querySelectorAll("[data-swatch]")) as HTMLElement[];
  expect(sw).toHaveLength(2);
  expect(sw[0].style.borderRadius).not.toBe(sw[1].style.borderRadius);
});
