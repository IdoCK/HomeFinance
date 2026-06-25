import * as React from "react";
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";
import { cn } from "@/lib/utils";

// Arbitrary-value utilities (bg-[var(--…)]) for the same token-resolution
// reason documented in Pill / SegmentedToggle.

function ArrowButton({
  className,
  ...props
}: React.ComponentProps<"button">) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex size-7 items-center justify-center rounded-full text-[var(--fl-ink)] transition-colors",
        "hover:bg-[var(--fl-frame)] active:translate-y-px",
        "disabled:pointer-events-none disabled:opacity-35 [&_svg]:size-4",
        className,
      )}
      {...props}
    />
  );
}

/** Compact prev / label / next stepper with chevron arrow buttons in one
 *  rounded track. A modern replacement for three separate Pills. */
export function Stepper({
  label,
  onPrev,
  onNext,
  prevDisabled,
  nextDisabled,
  prevLabel = "Previous",
  nextLabel = "Next",
  className,
}: {
  label: React.ReactNode;
  onPrev: () => void;
  onNext: () => void;
  prevDisabled?: boolean;
  nextDisabled?: boolean;
  prevLabel?: string;
  nextLabel?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-0.5 rounded-full border border-[var(--fl-line)] bg-[var(--fl-card)] p-0.5",
        className,
      )}
    >
      <ArrowButton onClick={onPrev} disabled={prevDisabled} aria-label={prevLabel}>
        <ChevronLeftIcon />
      </ArrowButton>
      <span className="min-w-[68px] px-1 text-center text-xs font-semibold tabular-nums text-[var(--fl-ink)]">
        {label}
      </span>
      <ArrowButton onClick={onNext} disabled={nextDisabled} aria-label={nextLabel}>
        <ChevronRightIcon />
      </ArrowButton>
    </div>
  );
}
