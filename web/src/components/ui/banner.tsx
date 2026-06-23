import type { CSSProperties, ReactNode } from "react";

export type BannerTone = "info" | "warn" | "good" | "bad";

const TONE_COLOR: Record<BannerTone, string> = {
  info: "var(--fl-muted)",
  warn: "#F59E0B",
  good: "var(--pos)",
  bad: "var(--neg)",
};

/** A full-width frosted callout for page-level state (partial-month notices, the
 *  monthly verdict). A `dashed` left accent reuses the charts' "in progress"
 *  vocabulary so a partial/provisional state reads consistently across the app. */
export function Banner({
  tone = "info",
  icon,
  children,
  dashed = false,
  style,
}: {
  tone?: BannerTone;
  icon?: ReactNode;
  children: ReactNode;
  dashed?: boolean;
  style?: CSSProperties;
}) {
  const color = TONE_COLOR[tone];
  return (
    <div
      role="note"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 14px",
        borderRadius: 12,
        background: "var(--fl-frame)",
        border: "1px solid var(--fl-line)",
        borderLeft: `3px ${dashed ? "dashed" : "solid"} ${color}`,
        fontSize: 13,
        color: "var(--fl-ink)",
        ...style,
      }}
    >
      {icon != null && (
        <span aria-hidden style={{ color, flex: "none", display: "inline-flex", alignItems: "center" }}>
          {icon}
        </span>
      )}
      <span>{children}</span>
    </div>
  );
}
