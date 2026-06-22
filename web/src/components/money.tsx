const FMT = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function formatMoney(n: number): string {
  return FMT.format(n);
}

export function Money({ value, colored = false }: { value: number; colored?: boolean }) {
  const color = !colored ? undefined : value > 0 ? "var(--pos)" : value < 0 ? "var(--neg)" : undefined;
  return (
    <span style={{ fontVariantNumeric: "tabular-nums", color }}>{formatMoney(value)}</span>
  );
}
