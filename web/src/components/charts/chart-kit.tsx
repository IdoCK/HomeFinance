// Shared Recharts plumbing for the chart platform. The hand-rolled SVG charts are
// being migrated onto Recharts (see docs/chart-platform/); this kit holds the house
// conventions every migrated chart must honour, in ONE place:
//   - the "ledger slip" frosted tooltip (the signature interactive readout)
//   - the partial-month split (solid settled prefix + dashed in-progress tail)
//   - zero-baseline y-domain
//   - persona-safe category colours + formatMoney passthrough
import type { ReactNode } from "react";
import { categoryColor } from "./_svg";

/** One named line/area series on a shared y-domain. `total` drives the bold
 *  legend figure; `color` defaults to the persona-excluding category ramp. */
export type LineSeries = { name: string; values: number[]; color?: string; total?: number };

/** Resolve each series' colour, defaulting to the persona-excluding category ramp
 *  so a generic category can never render in a person's hue. */
export function colorize(series: LineSeries[]): (LineSeries & { color: string })[] {
  return series.map((s, i) => ({ ...s, color: s.color ?? categoryColor(i) }));
}

/** Always include 0 so positive/negative read honestly and axes are never truncated. */
export function zeroBaselineDomain(values: number[]): [number, number] {
  return [Math.min(0, ...values), Math.max(0, ...values)];
}

/** Index of the first in-progress (partial) month, or -1 when all settled. */
export function firstPartialIndex(partial?: boolean[]): number {
  return partial ? partial.findIndex(Boolean) : -1;
}

/** Row-oriented data for Recharts. Each series is split into a solid `${name}__s`
 *  key (settled prefix) and a dashed `${name}__d` key (in-progress tail) that share
 *  one join point, so the dashed "so far" continuation connects gap-free — the same
 *  contract as the hand-rolled splitPartialPath. */
export function toRows(
  labels: string[],
  series: { name: string; values: number[] }[],
  partial?: boolean[],
): Record<string, string | number | boolean | null>[] {
  const fp = firstPartialIndex(partial);
  const solidEnd = fp === -1 ? labels.length - 1 : fp - 1;
  const dashStart = fp === -1 ? Number.POSITIVE_INFINITY : Math.max(0, fp - 1);
  return labels.map((x, i) => {
    const row: Record<string, string | number | boolean | null> = {
      x,
      __partial: partial?.[i] ?? false,
    };
    for (const s of series) {
      const v = s.values[i] ?? null;
      row[`${s.name}__s`] = i <= solidEnd ? v : null;
      row[`${s.name}__d`] = i >= dashStart ? v : null;
    }
    return row;
  });
}

/** Compact money for axis/milestone labels: $1.2M / $250k / $80. */
export function kCompact(n: number): string {
  const a = Math.abs(n);
  if (a >= 1_000_000) return `$${Math.round(n / 100_000) / 10}M`;
  if (a >= 1000) return `$${Math.round(n / 1000)}k`;
  return `$${Math.round(n)}`;
}

/** "2026-03" → "Mar 2026"; anything else passes through unchanged. */
export function monthLabel(raw: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(raw);
  if (!m) return raw;
  const month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][
    Number(m[2]) - 1
  ];
  return `${month ?? m[2]} ${m[1]}`;
}

type SlipRow = { name: string; color: string; value: number };

/** The "ledger slip": a frosted card readout for a hovered x. Collapses the
 *  solid/dashed split back to one row per real series, sorts by value, and prints
 *  every figure through `valueFormat` (formatMoney by default) so the currency
 *  toggle stays consistent. Used as Recharts `<Tooltip content={...}>`. */
export function LedgerTooltip({
  active,
  payload,
  label,
  valueFormat,
}: {
  active?: boolean;
  // Recharts hands us a loosely-typed payload; narrow what we read.
  payload?: { name?: string; value?: number | null; color?: string; payload?: { __partial?: boolean } }[];
  label?: string;
  valueFormat: (n: number) => string;
}): ReactNode {
  if (!active || !payload?.length) return null;
  const partialMonth = Boolean(payload[0]?.payload?.__partial);

  const seen = new Map<string, SlipRow>();
  for (const p of payload) {
    if (p.value == null) continue;
    const key = p.name || "__value";
    if (!seen.has(key)) seen.set(key, { name: p.name ?? "", color: p.color ?? "var(--fl-ink)", value: p.value });
  }
  const rows = [...seen.values()].sort((a, b) => b.value - a.value);
  if (rows.length === 0) return null;

  return (
    <div
      role="status"
      style={{
        background: "var(--fl-card)",
        border: "1px solid var(--fl-line)",
        borderRadius: 12,
        boxShadow: "0 12px 28px -14px rgba(22,24,29,.45)",
        padding: "9px 11px",
        minWidth: 148,
        fontSize: 12,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 10,
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "var(--fl-muted)",
          marginBottom: 6,
        }}
      >
        <span>{monthLabel(label ?? "")}</span>
        {partialMonth && (
          <span style={{ color: "var(--saved)", fontStyle: "italic", letterSpacing: 0, textTransform: "none" }}>
            so far
          </span>
        )}
      </div>
      <div style={{ height: 1, background: "var(--fl-line)", margin: "0 -11px 7px" }} />
      <div style={{ display: "grid", gap: 4 }}>
        {rows.map((r) => (
          <div key={r.name || "value"} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: r.color, flex: "none" }} />
            {r.name && <span style={{ flex: 1, color: "var(--fl-ink)", whiteSpace: "nowrap" }}>{r.name}</span>}
            <span style={{ flex: r.name ? "none" : 1, textAlign: r.name ? "right" : "left", fontWeight: 800, fontVariantNumeric: "tabular-nums", color: "var(--fl-ink)" }}>
              {valueFormat(r.value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** A visually-hidden data table mirroring the chart, so screen readers (and tests)
 *  can read the underlying numbers a stroked path can't expose. */
export function SrDataTable({
  caption,
  labels,
  series,
  valueFormat,
}: {
  caption: string;
  labels: string[];
  series: LineSeries[];
  valueFormat: (n: number) => string;
}): ReactNode {
  return (
    <table style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)", whiteSpace: "nowrap", border: 0 }}>
      <caption>{caption}</caption>
      <thead>
        <tr>
          <th scope="col">Month</th>
          {series.map((s) => (
            <th key={s.name} scope="col">{s.name}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {labels.map((lab, i) => (
          <tr key={lab}>
            <th scope="row">{monthLabel(lab)}</th>
            {series.map((s) => (
              <td key={s.name}>{valueFormat(s.values[i] ?? 0)}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
