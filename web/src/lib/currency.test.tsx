import { render, screen, act } from "@testing-library/react";
import { expect, test, beforeEach } from "vitest";
import { CurrencyProvider, useCurrency } from "./currency";

function Probe() {
  const { currency, symbol, setCurrency, format } = useCurrency();
  return (
    <div>
      <span data-testid="cur">{currency}</span>
      <span data-testid="sym">{symbol}</span>
      <span data-testid="fmt">{format(1234.5)}</span>
      <button onClick={() => setCurrency("ILS")}>ils</button>
    </div>
  );
}

beforeEach(() => localStorage.clear());

test("defaults to USD and formats with $", () => {
  render(<CurrencyProvider><Probe /></CurrencyProvider>);
  expect(screen.getByTestId("cur").textContent).toBe("USD");
  expect(screen.getByTestId("sym").textContent).toBe("$");
  expect(screen.getByTestId("fmt").textContent).toBe("$1,234.50");
});

test("switching to ILS persists and reformats", () => {
  render(<CurrencyProvider><Probe /></CurrencyProvider>);
  act(() => screen.getByText("ils").click());
  expect(screen.getByTestId("cur").textContent).toBe("ILS");
  expect(localStorage.getItem("hf-currency")).toBe("ILS");
  expect(screen.getByTestId("fmt").textContent).toContain("₪");
});
