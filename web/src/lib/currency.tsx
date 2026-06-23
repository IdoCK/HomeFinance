import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type Currency = "USD" | "ILS";
const SYMBOL: Record<Currency, string> = { USD: "$", ILS: "₪" };

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
