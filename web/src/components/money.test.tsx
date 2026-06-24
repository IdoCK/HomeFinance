import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Money, formatMoney } from "./money";
import { CurrencyProvider } from "@/lib/currency";

const wrap = (ui: React.ReactNode) => render(<CurrencyProvider>{ui}</CurrencyProvider>);

test("formatMoney formats USD by default", () => {
  expect(formatMoney(1234.5)).toBe("$1,234.50");
  expect(formatMoney(-99)).toBe("-$99.00");
});

test("formatMoney formats ILS when asked", () => {
  expect(formatMoney(1234.5, "ILS")).toContain("₪");
});

test("Money colors negatives (USD default)", () => {
  wrap(<Money value={-10} colored />);
  // Uses the text-legible "ink" shade, not the vibrant chart-fill token.
  expect(screen.getByText("-$10.00")).toHaveStyle({ color: "var(--neg-ink)" });
});

test("Money colors positives with the legible ink shade", () => {
  wrap(<Money value={10} colored />);
  expect(screen.getByText("$10.00")).toHaveStyle({ color: "var(--pos-ink)" });
});

test("Money flags a missing rate with a muted affordance", () => {
  wrap(<Money value={400} rateMissing />);
  expect(screen.getByText(/no rate/i)).toBeInTheDocument();
});
