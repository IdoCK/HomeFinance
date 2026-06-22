import { useCurrency, type Currency } from "@/lib/currency";

const FMT_CACHE: Partial<Record<string, Intl.NumberFormat>> = {};
function fmt(currency: Currency, cents: boolean): Intl.NumberFormat {
  const key = `${currency}-${cents}`;
  return (FMT_CACHE[key] ??= new Intl.NumberFormat("en-US", {
    style: "currency", currency,
    minimumFractionDigits: cents ? 2 : 0, maximumFractionDigits: cents ? 2 : 0,
  }));
}

export function formatMoney(n: number, currency: Currency = "USD"): string {
  return fmt(currency, true).format(n);
}

/** Ledger figure. `colored` tints by sign; `accent` uses the persona color.
 *  Renders in the active display currency (via CurrencyProvider). `original`
 *  surfaces an entered-in-another-currency marker. Tabular-nums for alignment. */
export function Money({
  value, colored = false, accent = false, cents = true,
  original,
}: {
  value: number; colored?: boolean; accent?: boolean; cents?: boolean;
  original?: { amount: number; currency: Currency };
}) {
  const { currency } = useCurrency();
  const color = accent
    ? "var(--persona-solid)"
    : !colored ? undefined
      : value > 0 ? "var(--pos)" : value < 0 ? "var(--neg)" : undefined;
  const showOriginal = original && original.currency !== currency;
  return (
    <span style={{ fontVariantNumeric: "tabular-nums", color }}>
      {fmt(currency, cents).format(value)}
      {showOriginal && (
        <span
          title={`Originally ${formatMoney(original!.amount, original!.currency)}`}
          style={{ color: "var(--fl-muted)", fontSize: "0.82em", marginLeft: 4 }}
        >
          ≈
        </span>
      )}
    </span>
  );
}
