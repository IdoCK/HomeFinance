import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Money, formatMoney } from "./money";

test("formatMoney formats USD with separators", () => {
  expect(formatMoney(1234.5)).toBe("$1,234.50");
  expect(formatMoney(-99)).toBe("-$99.00");
});

test("Money colors negatives", () => {
  render(<Money value={-10} colored />);
  const el = screen.getByText("-$10.00");
  expect(el).toHaveStyle({ color: "var(--neg)" });
});
