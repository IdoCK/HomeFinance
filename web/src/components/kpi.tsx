import type { ReactNode } from "react";

/** Tiny uppercase section/label text used across cards. */
export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <span style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--fl-muted)", fontWeight: 700 }}>
      {children}
    </span>
  );
}

/** Labelled metric: uppercase label above a bold tabular value. `big` for the
 *  hero figure (e.g. Net), `colored` to tint by sign via <Money colored>. */
export function Kpi({
  label,
  big = false,
  testId,
  children,
}: {
  label: string;
  big?: boolean;
  testId?: string;
  children: ReactNode;
}) {
  return (
    <div style={{ display: "grid", gap: 4 }}>
      <SectionTitle>{label}</SectionTitle>
      <span
        data-testid={testId}
        style={big ? { fontSize: 32, fontWeight: 800, letterSpacing: "-0.03em" } : { fontSize: 18, fontWeight: 700 }}
      >
        {children}
      </span>
    </div>
  );
}
