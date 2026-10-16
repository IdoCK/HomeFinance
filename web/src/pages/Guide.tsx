import { useEffect, useState } from "react";
import "./Guide.css";

// Sections drive the app-native sub-menu; clicking one smooth-scrolls the page
// to that section, and a scroll-spy keeps the active item in sync while reading.
// The content below is rendered natively (no iframe) so it flows in the app's
// normal page scroll — one scroll region, no inner frame. The standalone,
// portable copy still lives at docs/USER_GUIDE.html (served at /api/guide).
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

export default function Guide() {
  const [active, setActive] = useState<string>(SECTIONS[0].id);

  const goTo = (id: string) => {
    setActive(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // Scroll-spy: as the reader scrolls, highlight the section currently sitting
  // near the top of the viewport so the sub-menu always reflects their place.
  // rootMargin's -72% bottom inset makes a section "active" once it crosses into
  // the top band, which feels right as you read downward.
  useEffect(() => {
    const els = SECTIONS.map((s) => document.getElementById(s.id)).filter(
      (el): el is HTMLElement => el != null,
    );
    if (!els.length) return;
    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length) setActive(visible[0].target.id);
      },
      { rootMargin: "0px 0px -72% 0px", threshold: 0 },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  return (
    <div style={{ display: "flex", gap: 16, alignItems: "stretch", minWidth: 0 }}>
      {/* Section sub-menu */}
      <nav
        aria-label="Guide sections"
        style={{
          flex: "none", width: 184, display: "flex", flexDirection: "column", gap: 2,
          alignSelf: "flex-start", position: "sticky", top: 0,
        }}
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

      {/* Guide content — native page content, no iframe. */}
      <div className="guide-doc" style={{ flex: 1, minWidth: 0 }}>
        <div className="hero">
          <h1>User Guide</h1>
          <p>
            A private, local finance dashboard for two people. Upload your bank,
            credit-card and Amazon exports; the app sorts every transaction, draws
            charts, and tracks budgets, goals and net worth.
          </p>
          <span className="lock">
            🔒 Everything stays on your machine — nothing is uploaded unless you ask for AI insights.
          </span>
        </div>

        <section id="start">
          <h2><span className="dot" />Starting the app</h2>
          <div className="card">
            <p>
              Open a terminal in the project folder, start the server, then open the
              address in your browser:
            </p>
            <p><code>python run_api.py</code>{" → "}<code>http://localhost:8000</code></p>
            <p className="lead">
              If the page doesn't load, whoever set up the app needs to build the web
              frontend once with <code>npm --prefix web run build</code>.
            </p>
          </div>
        </section>

        <section id="switches">
          <h2><span className="dot" />The basics: person &amp; currency</h2>
          <p className="lead">Every page reacts to two switches at the top of the left sidebar.</p>
          <div className="grid">
            <div className="card">
              <h3>Person</h3>
              <p>
                Switch between <span className="pill you">Ido</span>{" "}
                <span className="pill spouse">Aviv</span>{" "}
                <span className="pill joint">Joint</span>. Pick a person to see only
                their money; <strong>Joint</strong> merges both for shared spending,
                savings, goals and net worth.
              </p>
              <p className="lead">"Ido" and "Aviv" are defaults — rename them on Settings.</p>
            </div>
            <div className="card">
              <h3>Display currency</h3>
              <p>
                Toggle <span className="pill">$ USD</span> <span className="pill">₪ ILS</span>.
                Every number on screen switches currency using stored exchange rates. This
                only changes the <em>display</em> — your original amounts are never altered.
              </p>
              <p className="lead">A light / dark mode toggle sits at the bottom of the sidebar.</p>
            </div>
          </div>
        </section>

        <section id="overview">
          <h2><span className="dot" />Overview</h2>
          <div className="card">
            <p>
              Your home screen. Shows this month's income, spending and savings rate, a
              cash-flow chart (toggle between <strong>Net</strong> per month and a longer
              <strong> Trend</strong> of income vs. spend with cumulative savings), and your
              top spending categories. Use the arrows to step between months — the current,
              incomplete month is flagged so you don't misread a partial month as a drop.
            </p>
          </div>
        </section>

        <section id="transactions">
          <h2><span className="dot" />Transactions</h2>
          <div className="card">
            <p>The full, searchable list of every transaction for the selected person.</p>
            <ul>
              <li>
                <strong>Search</strong> by description; filter by category, by
                included/excluded, or by currency.
              </li>
              <li>Click a transaction's category to <strong>recategorize</strong> it.</li>
              <li>
                Toggle a row's <strong>included</strong> flag to keep it in the list but
                exclude it from all totals — used automatically for things like credit-card
                bill payments, which would otherwise double-count.
              </li>
            </ul>
          </div>
        </section>

        <section id="analysis">
          <h2><span className="dot" />Analysis</h2>
          <div className="card">
            <p>Deeper slicing of your spending, in three tabs:</p>
            <ul>
              <li>
                <strong>Explore</strong> — drill down from parent groups → categories →
                individual vendors. Vendor groups collapse merchant-name variants
                (<code>AMAZON MKTPL</code>, <code>Amazon.com</code> → "Amazon") into one line.
              </li>
              <li>
                <strong>Compare</strong> — put two slices side by side (two time windows,
                weekdays vs. weekends, or two events).
              </li>
              <li><strong>People</strong> — see where Ido and Aviv overlap and differ.</li>
            </ul>
            <p className="lead">You can also filter this page by Events (below).</p>
          </div>
        </section>

        <section id="budgets">
          <h2><span className="dot" />Budgets</h2>
          <div className="card">
            <p>
              Set a <strong>monthly cap</strong> per category. The page shows how much
              you've budgeted this month and how actual spending tracks against each cap.
              Budgets can be per-person or household (Joint).
            </p>
          </div>
        </section>

        <section id="recurring">
          <h2><span className="dot" />Recurring</h2>
          <div className="card">
            <p>
              Automatically detects <strong>recurring charges</strong> (subscriptions,
              rent, bills) from your history, each with a confidence indicator. Shows what's
              <strong> committed each month</strong>, which bills are <strong>due this
              month</strong>, and flags <strong>anomalies</strong> — a recurring charge that
              came in higher than usual.
            </p>
          </div>
        </section>

        <section id="goals">
          <h2><span className="dot" />Goals</h2>
          <div className="card">
            <p>
              Savings goals, each with a target amount, optional target date, a
              <strong> short-</strong> or <strong>long-term</strong> horizon, and optional
              private notes. Each goal shows percent complete and how much you'd need to save
              per month to hit the target on time. Goals can be personal or shared (Joint).
            </p>
          </div>
        </section>

        <section id="networth">
          <h2><span className="dot" />Net Worth</h2>
          <div className="card">
            <p>
              Tracks <strong>accounts</strong> (checking, savings, investments, property =
              assets; credit cards, loans = liabilities) and your net worth over time.
            </p>
            <ul>
              <li><strong>Add an account</strong> with its current balance.</li>
              <li><strong>Record a balance</strong> as of any date to build a history.</li>
              <li>
                <strong>Populate</strong> balance history automatically from a bank
                statement you've already imported (uses its running-balance column).
              </li>
              <li>
                Includes a simple <strong>projection</strong> of future net worth from your
                savings rate and an assumed annual return.
              </li>
            </ul>
          </div>
        </section>

        <section id="events">
          <h2><span className="dot" />Events</h2>
          <div className="card">
            <p>Label spans of time or sets of transactions so you can analyze them. Three kinds:</p>
            <ul>
              <li><strong>Window</strong> — a date range (a vacation, a move).</li>
              <li><strong>Recurring</strong> — a rule (paydays, birthdays).</li>
              <li><strong>Tagged</strong> — a hand-picked set of transactions.</li>
            </ul>
            <p>
              Once an event exists you can filter the Analysis page by it, and manually tag
              individual transactions to catch stragglers outside the date window.
            </p>
          </div>
        </section>

        <section id="import">
          <h2><span className="dot" />Import — getting data in</h2>
          <div className="card">
            <p>The Import page is how data gets into the app:</p>
            <ul>
              <li>Switch to the <strong>person</strong> the file belongs to.</li>
              <li>
                Choose the <strong>source</strong> (Amazon / credit card / bank), pick the
                <strong> file</strong>, and confirm the <strong>statement currency</strong>.
              </li>
              <li>
                The app shows the <strong>parsed rows</strong> for review — then
                <strong> commit</strong> to save them.
              </li>
            </ul>
          </div>
          <div className="grid">
            <div className="card compact">
              <h3>Where to get the files</h3>
              <ul>
                <li><strong>Amazon</strong> — Order Reports → "Items" report → download CSV.</li>
                <li>
                  <strong>Credit card / bank</strong> — export transactions as CSV from your
                  provider's site.
                </li>
              </ul>
            </div>
            <div className="card compact">
              <h3>It handles any layout</h3>
              <p>
                A local AI helper running entirely on your machine (no internet) figures out
                each file's columns, date format, separators and sign convention on its own.
                The page shows a 🟢/🔴 dot for whether it's ready; if red, files matching a
                known format still import.
              </p>
            </div>
          </div>
          <div className="note">
            <strong>Duplicates are caught.</strong> Re-uploading the same file won't import it
            twice. You can delete a previously imported file (and its transactions) from the
            import history. <strong>Internal transfers</strong> like a credit-card bill payment
            are imported but automatically excluded from totals (shown dimmed) so they don't
            double-count — you can re-include any row.
          </div>
        </section>

        <section id="insights">
          <h2><span className="dot" />AI Insights</h2>
          <div className="card">
            <p>Optional. Generates personal-finance coaching from your data.</p>
            <div className="note privacy">
              <p>
                <strong>What is sent:</strong> only anonymized aggregates — category totals,
                monthly spend/savings, month-over-month percentages, and goal-progress
                percentages. People are labeled "Person A / Person B / Household".
              </p>
              <p style={{ margin: "8px 0 0" }}>
                <strong>What is never sent:</strong> raw transactions, merchant names, item
                descriptions, purchase dates, account numbers, real names, or goal notes.
              </p>
            </div>
            <p>
              Before anything is sent, the page shows you the <strong>exact payload</strong>.
              With no API key configured the page still works — it just shows that preview
              instead of calling out.
            </p>
          </div>
        </section>

        <section id="settings">
          <h2><span className="dot" />Settings</h2>
          <div className="card">
            <ul>
              <li><strong>People</strong> — rename the two household members.</li>
              <li><strong>Money</strong> — set your default display currency.</li>
              <li>
                <strong>Categories</strong> — define per-person categories with
                comma-separated <strong>keywords</strong> (e.g.{" "}
                <code>Groceries → whole foods, trader joe, grocery</code>). Imports auto-tag
                any transaction whose description contains a keyword. Group categories under a
                <strong> parent</strong> for rollup totals.
              </li>
              <li>
                <strong>Vendor groups</strong> — same idea, used to collapse merchant-name
                variants in the Analysis drill-down.
              </li>
            </ul>
            <p className="lead">
              The app seeds starter categories and vendor groups for each person, so your
              first import already gets sorted. Everything is editable, and re-running an
              import re-tags by your current rules.
            </p>
          </div>
        </section>

        <section id="data">
          <h2><span className="dot" />How your data is organized</h2>
          <div className="card">
            <p>Everything is stored locally in a single file, <code>data/finance.db</code>:</p>
            <table>
              <thead>
                <tr><th>What</th><th>Holds</th></tr>
              </thead>
              <tbody>
                <tr><td><strong>People</strong></td><td>the two household members</td></tr>
                <tr>
                  <td><strong>Transactions</strong></td>
                  <td>
                    date, description, amount (negative = spend, positive = income), category,
                    source, currency, and an <em>included</em> flag
                  </td>
                </tr>
                <tr><td><strong>Categories / Vendor groups</strong></td><td>your keyword rules, per person</td></tr>
                <tr><td><strong>Budgets</strong></td><td>a monthly cap per category</td></tr>
                <tr><td><strong>Goals</strong></td><td>savings targets with progress</td></tr>
                <tr><td><strong>Accounts / Snapshots</strong></td><td>net-worth ledger and its history</td></tr>
                <tr><td><strong>Events</strong></td><td>labeled time windows or transaction sets</td></tr>
                <tr><td><strong>Imported files</strong></td><td>a record of every file imported (for dedup)</td></tr>
              </tbody>
            </table>
            <p className="lead" style={{ marginTop: 12 }}>
              Refunds are handled intelligently: a credit on a card or Amazon feed reduces that
              category's spending rather than counting as income.
            </p>
          </div>
          <div className="footer">🔒 Household Finance · all data stays local</div>
        </section>
      </div>
    </div>
  );
}
