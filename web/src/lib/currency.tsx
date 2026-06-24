import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type Currency = "USD" | "ILS";
const SYMBOL: Record<Currency, string> = { USD: "$", ILS: "₪" };

// Module-level mirror of the active display currency. The CurrencyProvider keeps
// this in sync so the non-React `formatMoney` helper (used for chart axis labels,
// tooltips, aria strings, etc.) can format in the selected currency without
// every call site threading the currency through. Defaults to the persisted
// choice, else USD.
let activeCurrency: Currency =
  (typeof localStorage !== "undefined" && (localStorage.getItem("hf-currency") as Currency)) || "USD";
export function getActiveCurrency(): Currency {
  return activeCurrency;
}

type Ctx = {
  currency: Currency;
  setCurrency: (c: Currency) => void;
  symbol: string;
  format: (n: number, opts?: { cents?: boolean; signed?: boolean }) => string;
};
const CurrencyCtx = createContext<Ctx | null>(null);

export function CurrencyProvider({ children }: { children: React.ReactNode }) {
  const [currency, setCurrency] = useState<Currency>(
    () => (localStorage.getItem("hf-currency") as Currency) || "USD",
  );
  // Keep the module-level mirror in sync synchronously on render so the first
  // paint after a toggle already formats labels in the new currency.
  activeCurrency = currency;
  useEffect(() => {
    localStorage.setItem("hf-currency", currency);
    document.documentElement.dataset.currency = currency;
  }, [currency]);

  const value = useMemo<Ctx>(() => {
    const fmt = (cents: boolean) =>
      new Intl.NumberFormat("en-US", {
        style: "currency", currency,
        minimumFractionDigits: cents ? 2 : 0, maximumFractionDigits: cents ? 2 : 0,
      });
    return {
      currency, setCurrency, symbol: SYMBOL[currency],
      format: (n, opts) => {
        const s = fmt(opts?.cents ?? true).format(n);
        return opts?.signed && n > 0 ? `+${s}` : s;
      },
    };
  }, [currency]);

  return <CurrencyCtx.Provider value={value}>{children}</CurrencyCtx.Provider>;
}

export function useCurrency() {
  const v = useContext(CurrencyCtx);
  if (!v) throw new Error("useCurrency must be used within <CurrencyProvider>");
  return v;
}
