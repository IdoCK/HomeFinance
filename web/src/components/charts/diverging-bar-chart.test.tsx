import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { DivergingBarChart } from "./diverging-bar-chart";

const rows = [{ category: "Food", a: 100, b: 60, shared: true }];

test("renders both person labels (a non-color, positional encoding)", () => {
  render(<DivergingBarChart rows={rows} labelA="Ido" labelB="Aviv" />);
  expect(screen.getByText("Ido")).toBeInTheDocument();
  expect(screen.getByText("Aviv")).toBeInTheDocument();
});

test("uses the persona color tokens, not hardcoded hex", () => {
  const { container } = render(<DivergingBarChart rows={rows} labelA="Ido" labelB="Aviv" />);
  const html = container.innerHTML;
  expect(html).toContain("--persona-you");
  expect(html).toContain("--persona-spouse");
  // No raw persona hex should leak into the markup.
  expect(html).not.toContain("#3B82F6");
  expect(html).not.toContain("#EC4899");
});

test("empty rows show an empty state", () => {
  render(<DivergingBarChart rows={[]} labelA="Ido" labelB="Aviv" />);
  expect(screen.getByText(/No spending in range/)).toBeInTheDocument();
});
