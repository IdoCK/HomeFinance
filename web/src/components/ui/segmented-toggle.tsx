import * as React from "react";
import { cn } from "@/lib/utils";

// Brand color tokens are bridged through multi-hop var() chains that
// `@theme inline` can't resolve into bg-*/border-* utilities, so we use
// arbitrary-value utilities (bg-[var(--…)]) here — same approach as Pill.

type Option<T extends string> = { value: T; label: React.ReactNode };

/** Modern segmented control — a single pill-track with the active segment
 *  filled in the persona color. Replaces stacks of separate toggle Pills for a
 *  more deliberate "switch" affordance. Controlled. */
export function SegmentedToggle<T extends string>({
  value,
  onChange,
  options,
  ariaLabel,
  className,
}: {
  value: T;
  onChange: (value: T) => void;
  options: readonly Option<T>[];
  ariaLabel?: string;
  className?: string;
}) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center gap-0.5 rounded-full border border-[var(--fl-line)] bg-[var(--fl-frame)] p-0.5",
        className,
      )}
    >
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            data-active={active}
            onClick={() => onChange(o.value)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-semibold transition-colors",
              active
                ? "bg-[var(--persona-solid)] text-white shadow-sm"
                : "text-[#4B5059] hover:text-[var(--fl-ink)]",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
