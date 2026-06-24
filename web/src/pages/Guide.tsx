import { useRef, useState } from "react";

// Sections mirror the ids in docs/USER_GUIDE.html. They drive the app-native
// sub-menu; clicking one scrolls the embedded guide to that anchor.
const SECTIONS: { id: string; label: string }[] = [
  { id: "start", label: "Starting the app" },
  { id: "switches", label: "Person & currency" },
  { id: "overview", label: "Overview" },
  { id: "transactions", label: "Transactions" },
  { id: "analysis", label: "Analysis" },
  { id: "budgets", label: "Budgets" },
  { id: "recurring", label: "Recurring" },
  { id: "goals", label: "Goals" },
  { id: "networth", label: "Net Worth" },
  { id: "events", label: "Events" },
  { id: "import", label: "Import" },
  { id: "insights", label: "AI Insights" },
  { id: "settings", label: "Settings" },
  { id: "data", label: "Your data" },
];

// The guide HTML is served by the API (proxied in dev). ?embed hides its own
// standalone chrome so it sits cleanly inside the app.
const GUIDE_SRC = "/api/guide?embed=1";

export default function Guide() {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [active, setActive] = useState<string>(SECTIONS[0].id);

  const goTo = (id: string) => {
    setActive(id);
    // Same-origin iframe — set its hash to scroll to the section without a reload.
    try {
      const win = iframeRef.current?.contentWindow;
      if (win) win.location.hash = `#${id}`;
    } catch {
      // Cross-origin guard (shouldn't happen same-origin) — fall back to a src nav.
      if (iframeRef.current) iframeRef.current.src = `${GUIDE_SRC}#${id}`;
    }
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", fontSize: 24, margin: 0 }}>User Guide</h1>
        <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>how everything works — jump to a section</span>
      </header>

      <div style={{ display: "flex", gap: 16, alignItems: "stretch", minWidth: 0 }}>
        {/* Section sub-menu */}
        <nav
          aria-label="Guide sections"
          style={{ flex: "none", width: 184, display: "flex", flexDirection: "column", gap: 2, alignSelf: "flex-start", position: "sticky", top: 0 }}
        >
          {SECTIONS.map((s) => {
            const on = active === s.id;
            return (
              <button
                key={s.id}
                onClick={() => goTo(s.id)}
                aria-current={on ? "true" : undefined}
                style={{
                  textAlign: "left", fontSize: 13, padding: "8px 11px", borderRadius: 10,
                  border: "none", cursor: "pointer", fontWeight: on ? 700 : 500,
                  background: on ? "var(--fl-ink)" : "transparent",
                  color: on ? "#fff" : "#4B5059",
                }}
              >
                {s.label}
              </button>
            );
          })}
        </nav>

        {/* Embedded guide content (its own scroll region, decoupled from the app) */}
        <section className="frosted-card" style={{ flex: 1, minWidth: 0, padding: 0, overflow: "hidden" }}>
          <iframe
            ref={iframeRef}
            src={GUIDE_SRC}
            title="User Guide"
            style={{ display: "block", width: "100%", height: "calc(100vh - 130px)", border: "none", borderRadius: "inherit" }}
          />
        </section>
      </div>
    </div>
  );
}
