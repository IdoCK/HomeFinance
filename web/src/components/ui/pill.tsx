import * as React from "react";
import { cn } from "@/lib/utils";

const PILL =
  "inline-flex items-center gap-1.5 rounded-full border border-fl-line bg-fl-card px-3 py-1.5 " +
  "text-xs font-semibold text-[#4B5059] transition-colors hover:bg-fl-frame " +
  "disabled:opacity-40 disabled:pointer-events-none " +
  "data-[active=true]:bg-persona-solid data-[active=true]:text-white data-[active=true]:border-transparent";

type PillProps<E extends React.ElementType> = {
  as?: E;
  active?: boolean;
} & Omit<React.ComponentPropsWithoutRef<E>, "as">;

/** Rounded control used for the month stepper, filter selects, compare/
 *  granularity toggles. Polymorphic via `as` (button by default). */
export function Pill<E extends React.ElementType = "button">({
  as,
  active = false,
  className,
  ...props
}: PillProps<E>) {
  const Comp = (as ?? "button") as React.ElementType;
  return <Comp data-active={active} className={cn(PILL, className)} {...props} />;
}
