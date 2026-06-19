export function PagePlaceholder({ title }: { title: string }) {
  return (
    <div className="frosted-card" style={{ padding: 32 }}>
      <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>{title}</h1>
      <p style={{ color: "var(--fl-muted)", marginTop: 8 }}>Coming soon — built in a later plan.</p>
    </div>
  );
}
