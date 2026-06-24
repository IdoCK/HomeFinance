import { useCurrency, getActiveCurrency, type Currency } from "@/lib/currency";

const FMT_CACHE: Partial<Record<string, Intl.NumberFormat>> = {};
function fmt(currency: Currency, cents: boolean): Intl.NumberFormat {
  const key = `${currency}-${cents}`;
  return (FMT_CACHE[key] ??= new Intl.NumberFormat("en-US", {
    style: "currency", currency,
    minimumFractionDigits: cents ? 2 : 0, maximumFractionDigits: cents ? 2 : 0,
  }));
}

/** Format a figure in a currency. Defaults to the active display currency so
 *  chart labels / aria strings track the USD↔ILS toggle; pass an explicit
 *  currency to pin a value to a specific one (e.g. a statement's own currency).
 *  Guards the helper call so unit tests that mock out @/lib/currency still get
 *  a sane USD default. */
export function formatMoney(n: number, currency?: Currency): string {
  const c = currency ?? (typeof getActiveCurrency === "function" ? getActiveCurrency() : "USD");
  return fmt(c, true).format(n);
}

/** Ledger figure. `colored` tints by sign; `accent` uses the persona color.
 *  Renders in the active display currency (via CurrencyProvider) unless
 *  `currency` is provided explicitly, which overrides the display toggle —
 *  use this for statement-scoped figures that must stay in the statement's
 *  own currency. `original` surfaces an entered-in-another-currency marker.
 *  Tabular-nums for alignment. */
export function Money({
  value, colored = false, accent = false, cents = true,
  currency: currencyProp, original, rateMissing = false,
}: {
  value: number; colored?: boolean; accent?: boolean; cents?: boolean;
  /** Override the display-toggle currency with a fixed one (e.g. statement currency). */
  currency?: Currency;
  original?: { amount: number; currency: Currency };
  rateMissing?: boolean;
}) {
  const { currency: displayCurrency } = useCurrency();
  const currency = currencyProp ?? displayCurrency;
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
      {rateMissing && (
        <span title="No exchange rate for this date — showing the original amount"
              style={{ color: "var(--fl-muted)", fontSize: "0.78em", marginLeft: 4 }}>
          (no rate)
        </span>
      )}
    </span>
  );
}
