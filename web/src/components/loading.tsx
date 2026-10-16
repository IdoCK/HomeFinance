import { Skeleton } from "@/components/ui/skeleton";

/** Shared loading placeholder for data pages — `rows` shimmer cards matching
 *  the frosted-card grid. role="status" so it's announced to screen readers. */
export function Loading({ rows = 3 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading" style={{ display: "grid", gap: 12 }}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-20 w-full rounded-[var(--radius-card)]" />
      ))}
    </div>
  );
}
