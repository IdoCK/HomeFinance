const FMT = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function formatMoney(n: number): string {
  return FMT.format(n);
}

/** Ledger figure. `colored` tints by sign (income/spend); `accent` renders in
 *  the active persona color. Always tabular-nums for column alignment. */
export function Money({
  value,
  colored = false,
  accent = false,
}: {
  value: number;
  colored?: boolean;
  accent?: boolean;
}) {
  const color = accent
    ? "var(--persona-solid)"
    : !colored
      ? undefined
      : value > 0
        ? "var(--pos)"
        : value < 0
          ? "var(--neg)"
          : undefined;
  return (
    <span style={{ fontVariantNumeric: "tabular-nums", color }}>{formatMoney(value)}</span>
  );
}
