import type { CSSProperties } from "react";

/** Shared rounded "pill" style for inline-styled controls (add-buttons, inputs,
 *  selects) across the data pages — centralizes the byte-identical per-page
 *  copies that had been duplicated in 7 files.
 *
 *  Note: this is distinct from the `Pill` *component* (`components/ui/pill.tsx`),
 *  a Tailwind-class button used on newer surfaces (e.g. the Overview month
 *  stepper). The component is intentionally lighter (12px, muted text, white
 *  fill); this constant preserves the exact look of the existing inline-styled
 *  controls so the dedup introduces no visual drift. */
export const pillStyle: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "6px 12px",
  fontSize: 13, background: "transparent", color: "var(--fl-ink)",
};
