"""Household Finance Dashboard — local, two-person, AI-assisted.

Run with:  streamlit run app.py
All data is stored locally in data/finance.db. Only anonymized aggregates are
sent for AI insights, and only when you click the insights button.
"""

import os
import json
import math
import hashlib
from datetime import datetime

import streamlit as st
import pandas as pd
import altair as alt

from modules import database as db
from modules import parsing
from modules import agent_parser
from modules import formats
from modules import analytics
from modules import ai_insights
from modules import keywords

st.set_page_config(page_title="Household Finance", page_icon="💰", layout="wide")
db.init_db()

# ---------------------------------------------------------------- sidebar / view
people = db.list_people()
name_to_id = {p["name"]: p["id"] for p in people}
id_to_name = {p["id"]: p["name"] for p in people}

st.sidebar.title("💰 Household Finance")
st.sidebar.subheader("Viewing")
view = st.sidebar.radio(
    "View",
    [id_to_name[people[0]["id"]], id_to_name[people[1]["id"]], "Household"],
    label_visibility="collapsed",
)
st.sidebar.divider()
with st.sidebar.popover("🔒 Privacy"):
    st.write("Local-only. Your data never leaves this machine except the "
             "anonymized aggregates you choose to send for AI insights.")


def person_id_for_view(view):
    return None if view == "Household" else name_to_id[view]


def transactions_for_view(view):
    if view == "Household":
        return db.get_transactions()  # everyone
    return db.get_transactions(name_to_id[view])


def goals_for_view(view):
    if view == "Household":
        return db.get_goals("all")
    return db.get_goals(name_to_id[view])


# Net-worth ledger, scoped like goals: a person sees their own accounts, the
# Household view sees everyone's plus shared.
def accounts_for_view(view):
    return db.list_accounts("all" if view == "Household" else name_to_id[view])


def snapshots_for_view(view):
    return db.get_snapshots("all" if view == "Household" else name_to_id[view])


# Account kinds and their default asset/liability classification.
_ACCOUNT_KINDS = ["checking", "savings", "investment", "property",
                  "credit_card", "loan", "other"]


def _is_asset_default(kind):
    return kind not in ("credit_card", "loan")


def _category_rules(person_id):
    return [(c["name"], (c["keywords"] or "").split(","))
            for c in db.get_categories(person_id)]


def _category_names(person_id):
    return [c["name"] for c in db.get_categories(person_id)]


def _uncategorized_merchant_keys(rows):
    """Merchant keys (via _keyword_from_desc) for the still-Uncategorized, included
    rows — one entry per distinct merchant rather than per transaction-id variant."""
    keys = {}
    for r in rows:
        if (r["category"] == "Uncategorized" and r["description"].strip()
                and r.get("included", True)):
            keys.setdefault(_keyword_from_desc(r["description"]), r["description"])
    return keys


def _ai_categorize_uncategorized(rows, person_id, progress_cb=None):
    """Fill still-Uncategorized rows with the local LLM (mutates rows in place).
    Returns (n_filled, warning_or_None).

    Collapses rows to merchant keys first, so the model classifies each MERCHANT
    once (e.g. all 'AMAZON MKTPL*…' rows → one call) instead of every distinct
    description. The result is mapped back to every row sharing that key."""
    names = _category_names(person_id)
    if not names or not rows:
        return 0, None
    uncats = [r["description"] for r in rows
              if r["category"] == "Uncategorized" and r["description"].strip()
              and r.get("included", True)]
    if not uncats:
        return 0, None
    try:
        desc_to_cat = keywords.classify_descriptions(
            uncats, names, agent_parser.categorize_with_agent, progress_cb=progress_cb)
    except Exception as e:
        return 0, f"AI categorization unavailable ({e})"
    filled = 0
    for r in rows:
        if r["category"] == "Uncategorized" and r.get("included", True):
            new = desc_to_cat.get(r["description"], "Uncategorized")
            if new != "Uncategorized":
                r["category"] = new
                filled += 1
    return filled, None


def build_preview(file_bytes, filename, person_id, use_llm, progress_cb=None):
    """Detect a file's format from the registry, parse it deterministically, and
    categorize it (keyword rules first, then local-LLM inference for the rest).

    Returns a dict describing the result for the Import UI to render.
    """
    raw = agent_parser._read_raw_table(file_bytes, filename)
    text = file_bytes.decode("utf-8-sig", errors="replace")
    fmt, hdr = formats.match_format(raw, text, formats.load_formats())
    if not fmt:
        return {"matched": False, "raw_preview": raw.head(15)}

    source = fmt.get("source", "generic")
    rows, skipped, statement_balance = formats.parse_with_format(
        raw, fmt, hdr, source, parsing.categorize, _category_rules(person_id),
        progress_cb=progress_cb,
    )

    warnings = []
    if use_llm:
        _, warn = _ai_categorize_uncategorized(rows, person_id)
        if warn:
            warnings.append(warn + "; kept keyword rules — use 🔁 Retry below.")

    return {
        "matched": True, "identifier": fmt["identifier"], "source": source,
        "rows": rows, "skipped": skipped, "warnings": warnings,
        "statement_balance": statement_balance,  # {amount,date} or None
        # Snapshot of categories as first parsed, so we can later tell which rows
        # the user re-categorized by hand (used to learn keyword rules).
        "original_cats": [r["category"] for r in rows],
    }


# Merchant-key derivation now lives in modules/keywords.py (testable, and shared
# with the Categories-tab auto-categorize path). Aliased so call sites read the same.
_keyword_from_desc = keywords.keyword_from_desc


def _learn_keyword(person_id, category, desc):
    """Append a description-derived keyword to a category (deduped). Returns True
    only when a genuinely new keyword was added."""
    token = _keyword_from_desc(desc)
    if not token or category == "Uncategorized":
        return False
    cats = {c["name"]: c for c in db.get_categories(person_id)}
    c = cats.get(category)
    if not c:
        return False
    kws = [k.strip() for k in (c["keywords"] or "").split(",") if k.strip()]
    if token not in [k.lower() for k in kws]:
        kws.append(token)
        db.upsert_category(person_id, category, ",".join(kws))
        return True
    return False


def _style_amounts(df):
    """Green for money in (positive), red for money out (negative). Rows with an
    "Include" column set False are dimmed (excluded from calculations)."""
    def colorize(col):
        out = []
        for v in col:
            if v > 0:
                out.append("background-color:#16653420;color:#15803d;font-weight:600")
            elif v < 0:
                out.append("background-color:#7f1d1d20;color:#b91c1c;font-weight:600")
            else:
                out.append("")
        return out

    sty = df.style.apply(colorize, subset=["Amount"]).format({"Amount": "${:,.2f}"})
    if "Include" in df.columns:
        def dim(row):
            if not bool(row["Include"]):
                return ["opacity:0.45;color:#9ca3af" for _ in row]
            return ["" for _ in row]
        sty = sty.apply(dim, axis=1)
    return sty


def _manage_files_section(view, pid):
    """Imported-file list + legacy untracked-row cleanup. Lives in the Import tab."""
    st.subheader("🗂️ Imported files")
    imports = db.list_imports(pid)
    if imports:
        for imp in imports:
            label = f"**{imp['filename']}**"
            if view == "Household":
                label += f" · {imp['person']}"
            c1, c2, c3 = st.columns([5, 2, 1])
            c1.write(label)
            c2.caption(f"{imp['live_count']}/{imp['count']} rows · {imp['imported_at']}")
            if c3.button("Delete", key=f"delimp::{imp['person_id']}::{imp['file_hash']}",
                         help="Remove this file's transactions and its import record"):
                n = db.delete_import(imp["person_id"], imp["file_hash"])
                st.toast(f"Deleted {n} transaction(s) from {imp['filename']}.", icon="🗑️")
                st.rerun()
    else:
        st.caption("No tracked imported files yet. Files you import from now on "
                   "appear here and can be deleted individually.")

    # Legacy cleanup: rows imported before file-tracking (no file_hash) can't be
    # tied to a file above and may contain whole-file duplicates. Safest fix:
    # delete them and re-import once (now tracked + duplicate-blocked).
    unt_people = list(name_to_id.values()) if view == "Household" else [pid]
    unt_total = sum(db.count_untracked_transactions(p) for p in unt_people)
    if unt_total:
        st.caption(
            f"{unt_total} transaction(s) were imported before file-tracking and "
            "aren't tied to any file above — they may include duplicates. "
            "Recommended: delete them, then re-import the file(s) (re-imports are "
            "tracked and can't be duplicated)."
        )
        if st.button(f"🧹 Delete {unt_total} untracked transaction(s)"):
            removed = sum(db.clear_untracked_transactions(p) for p in unt_people)
            st.toast(f"Deleted {removed} untracked transaction(s). Re-import for "
                     "a clean, tracked copy.", icon="🧹")
            st.rerun()


pid = person_id_for_view(view)
txns = transactions_for_view(view)
goals = goals_for_view(view)

st.title(f"{view} — Overview")

tab_dash, tab_import, tab_cats, tab_goals, tab_networth, tab_ai = st.tabs(
    ["📊 Dashboard", "📥 Import", "🏷️ Categories", "🎯 Goals", "💵 Net Worth",
     "🤖 AI Insights"]
)

# ---------------------------------------------------------------- DASHBOARD
with tab_dash:
    if not txns:
        st.info("No transactions yet. Add some in the **Import** tab.")
    else:
        savings = analytics.monthly_savings(txns)

        # --- KPIs: lead with the latest COMPLETE calendar month so partial
        #     statement cycles don't drive misleading headlines/deltas.
        with st.container(border=True):
            if savings.empty:
                st.caption("Not enough data yet for monthly metrics.")
            else:
                complete = savings[savings["complete"]]
                use = complete if not complete.empty else savings
                partial = complete.empty
                month = use.index[-1]
                row = use.iloc[-1]
                prev_row = use.iloc[-2] if len(use) >= 2 else None

                if partial:
                    st.markdown(f"**Latest cycle · {month}**")
                    st.caption("⚠️ This statement cycle doesn't cover a full calendar "
                               "month — figures are partial and not yet comparable.")
                else:
                    st.markdown(f"**Latest complete month · {month}**")

                def _delta(key, money=True):
                    if partial or prev_row is None:
                        return None
                    cur, prv = row[key], prev_row[key]
                    if pd.isna(cur) or pd.isna(prv):
                        return None
                    d = cur - prv
                    return f"{d:+,.0f}" if money else f"{d:+.0%}"

                # Net worth: point-in-time wealth (independent of the month), shown
                # alongside the monthly flows. Delta = change since prior snapshot.
                dash_nw = analytics.net_worth(accounts_for_view(view))
                dash_trend = analytics.net_worth_trend(snapshots_for_view(view))
                dash_nw_delta = (dash_nw["net"] - float(dash_trend.iloc[-2]["net"])
                                 if len(dash_trend) >= 2 else None)

                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Income", f"${row['income']:,.0f}", delta=_delta("income"),
                          help="Money in this month (salary, rewards, reimbursements).")
                c2.metric("Spend", f"${row['spend']:,.0f}", delta=_delta("spend"),
                          delta_color="inverse", help="Money out this month.")
                c3.metric("Savings", f"${row['savings']:,.0f}", delta=_delta("savings"),
                          help="Income minus spend this month.")
                rate = row["savings_rate"]
                c4.metric("Savings rate",
                          "—" if pd.isna(rate) else f"{rate:.0%}",
                          delta=_delta("savings_rate", money=False),
                          help="Savings as a share of income — the headline health metric.")
                c5.metric("Net worth", f"${dash_nw['net']:,.0f}",
                          delta=None if dash_nw_delta is None else f"{dash_nw_delta:+,.0f}",
                          help="Assets minus liabilities — see the 💵 Net Worth tab.")

        # --- Monthly savings trend
        with st.container(border=True):
            st.subheader("Monthly savings")
            if not savings.empty:
                sav = savings.reset_index()  # month, income, spend, savings, complete
                base = alt.Chart(sav).encode(x=alt.X("month:N", title=None))
                bars = base.mark_bar().encode(
                    y=alt.Y("savings:Q", title=None, axis=alt.Axis(format="$,.0f")),
                    color=alt.condition(alt.datum.savings >= 0,
                                        alt.value("#0F766E"), alt.value("#C0584E")),
                    # partial (incomplete) months are rendered faded so they read
                    # as "not a full month" rather than a real dip/spike.
                    opacity=alt.condition(alt.datum.complete, alt.value(1.0), alt.value(0.35)),
                    tooltip=[alt.Tooltip("month:N", title="Month"),
                             alt.Tooltip("savings:Q", title="Savings", format="$,.2f"),
                             alt.Tooltip("complete:N", title="Full month?")],
                )
                zero = base.mark_rule(color="#9CA3AF").encode(y=alt.datum(0))
                st.altair_chart(bars + zero, use_container_width=True)
                if not bool(sav["complete"].all()):
                    st.caption("Faded bars are partial statement cycles, not full months.")
            else:
                st.caption("No data yet.")

        # --- Spending by category over time (stacked area)
        with st.container(border=True):
            st.subheader("Spending by category over time")
            pivot = analytics.spending_by_category_over_time(txns)
            if not pivot.empty:
                long = pivot.reset_index().melt(
                    "month", var_name="category", value_name="spend")
                area = alt.Chart(long).mark_area().encode(
                    x=alt.X("month:N", title=None),
                    y=alt.Y("spend:Q", stack=True, title=None,
                            axis=alt.Axis(format="$,.0f")),
                    color=alt.Color("category:N", title="Category"),
                    tooltip=[alt.Tooltip("month:N", title="Month"),
                             alt.Tooltip("category:N", title="Category"),
                             alt.Tooltip("spend:Q", title="Spend", format="$,.2f")],
                )
                st.altair_chart(area, use_container_width=True)
            else:
                st.caption("No spending (negative-amount) transactions yet.")

        # --- Category breakdown (horizontal bars)
        def _cat_bar(data, value, color):
            d = pd.DataFrame({"category": list(data), value: list(data.values())})
            return alt.Chart(d).mark_bar(color=color).encode(
                x=alt.X(f"{value}:Q", title=None, axis=alt.Axis(format="$,.0f")),
                y=alt.Y("category:N", sort="-x", title=None),
                tooltip=[alt.Tooltip("category:N", title="Category"),
                         alt.Tooltip(f"{value}:Q", title=value.title(), format="$,.2f")],
            )

        with st.container(border=True):
            col_sp, col_in = st.columns(2)
            with col_sp:
                st.subheader("Spending by category")
                totals = analytics.category_totals(txns)
                if totals:
                    st.altair_chart(_cat_bar(totals, "spend", "#C0584E"),
                                    use_container_width=True)
                else:
                    st.caption("No spending to categorize.")
            with col_in:
                st.subheader("Income by category")
                inc = analytics.income_by_category(txns)
                if inc:
                    st.altair_chart(_cat_bar(inc, "income", "#0F766E"),
                                    use_container_width=True)
                else:
                    st.caption("No income to categorize.")

        # --- Transactions with per-row include/exclude toggle
        with st.container(border=True):
            st.subheader("Transactions")
            st.caption("Uncheck **Include** to drop a row from every total and chart "
                       "(e.g. a credit-card payment). Excluded rows are dimmed; "
                       "changes save immediately.")
            tdf = pd.DataFrame(txns)
            disp = pd.DataFrame({
                "Date": tdf["date"],
                "Description": tdf["description"],
                "Amount": tdf["amount"].astype(float),
                "Category": tdf["category"],
                "Include": (tdf["included"].astype(bool)
                            if "included" in tdf.columns else True),
            })
            tx_key = f"txntable::{view}"
            edited_tx = st.data_editor(
                _style_amounts(disp), use_container_width=True, hide_index=True,
                key=tx_key, disabled=["Date", "Description", "Amount", "Category"],
                column_config={
                    "Include": st.column_config.CheckboxColumn(
                        "Include", help="Counts toward all totals and charts"),
                },
            )
            new_inc = edited_tx["Include"].astype(bool).tolist()
            old_inc = disp["Include"].astype(bool).tolist()
            ids = tdf["id"].tolist()
            changed = [(ids[i], new_inc[i])
                       for i in range(len(ids)) if new_inc[i] != old_inc[i]]
            if changed:
                for tid, val in changed:
                    db.set_transaction_included(tid, val)
                st.session_state.pop(tx_key, None)  # rebuild editor from fresh data
                st.rerun()

# ---------------------------------------------------------------- IMPORT
with tab_import:
    if view == "Household":
        st.info("Switch to a person's view to import their files.")
    else:
        ok, msg = agent_parser.check_ollama()
        if ok:
            st.success(f"🟢 Local parsing agent ready — {msg}")
        else:
            st.warning(f"🔴 {msg}")
            st.caption("The app reads files with a local AI agent (Ollama). "
                       "Install it and pull qwen2.5, then this turns green. "
                       "Nothing is sent to the web.")

        st.caption("Upload CSV or Excel exports, review the preview, then import.")
        with st.expander("How importing works"):
            st.write(
                "Each file is matched against a known **format** in "
                "`csv_formats.md` and parsed with its rules — consistent every "
                "time. Known formats parse offline; the local AI is used only to "
                "infer categories and to learn new file types.")
        # One-shot confirmation after a completed import (survives the rerun).
        done = st.session_state.pop("import_done_msg", None)
        if done:
            st.success(done, icon="✅")

        files = st.file_uploader(
            "Files", type=["csv", "xlsx", "xls"], accept_multiple_files=True
        )

        for f in files or []:
            file_bytes = f.getvalue()
            file_hash = hashlib.sha256(file_bytes).hexdigest()
            cache_key = f"prev::{pid}::{f.name}::{len(file_bytes)}"
            st.divider()
            st.markdown(f"### 📄 {f.name}")

            # Already imported? Don't re-parse and don't allow a second import.
            existing = db.get_import(pid, file_hash)
            if existing:
                st.info(
                    f"✓ Already imported — {existing['count']} transactions on "
                    f"{existing['imported_at']}. This exact file can't be imported "
                    "again (clear this person's transactions to re-enable)."
                )
                continue

            if st.button("🔄 Re-parse", key=f"reparse::{cache_key}"):
                st.session_state.pop(cache_key, None)

            if cache_key not in st.session_state:
                # Fast, non-blocking parse only (format match + deterministic
                # columns + keyword rules). The slow LLM categorization is NOT
                # run here — it would block the whole app (Streamlit runs one
                # script at a time per session) and freeze every tab, including
                # adding categories. AI categorization is on-demand below.
                with st.status(f"Parsing {f.name}…", expanded=True) as status:
                    bar = st.progress(0, text="Detecting format…")

                    def _parse_cb(done, total, _bar=bar):
                        pct = (done / total) if total else 0
                        _bar.progress(pct, text=f"{done:,} / {total:,} rows  ({pct:.0%})")

                    try:
                        prev = build_preview(
                            file_bytes, f.name, pid, use_llm=False,
                            progress_cb=_parse_cb,
                        )
                        st.session_state[cache_key] = prev
                        if prev.get("matched"):
                            n = len(prev["rows"])
                            bar.progress(
                                1.0,
                                text=f"{n:,} transactions · {prev.get('skipped', 0)} skipped",
                            )
                            status.update(
                                label=f"Parsed {n:,} transactions from {f.name}",
                                state="complete", expanded=False,
                            )
                        else:
                            status.update(
                                label=f"No known format matched {f.name}",
                                state="error", expanded=False,
                            )
                    except Exception as e:
                        status.update(label=f"Failed to parse {f.name}",
                                      state="error", expanded=True)
                        st.error(f"Error: {e}")
                        continue
            prev = st.session_state[cache_key]

            # ---- unmatched: warn + offer to learn a new format
            if not prev.get("matched"):
                st.warning(
                    "No format in the registry matches this file. Add it as a "
                    "new file type below so it (and future files like it) parse "
                    "automatically."
                )
                with st.expander("➕ Add this as a new file type"):
                    st.caption("Preview of the raw file:")
                    st.dataframe(prev["raw_preview"], use_container_width=True,
                                 hide_index=True)
                    prop_key = f"prop::{cache_key}"
                    if st.button("🔍 Analyze with local agent", key=f"an::{cache_key}",
                                 disabled=not ok):
                        with st.spinner("Local agent inferring layout…"):
                            try:
                                proposal, _, _ = agent_parser.propose_format(
                                    file_bytes, f.name
                                )
                                st.session_state[prop_key] = proposal
                            except Exception as e:
                                st.error(f"Could not analyze: {e}")
                    if prop_key in st.session_state:
                        proposal = st.session_state[prop_key]
                        ident = st.text_input(
                            "Identifier (what to call this file type)",
                            value=proposal.get("identifier", f.name),
                            key=f"id::{cache_key}",
                        )
                        src = st.selectbox(
                            "Source", ["bank", "credit_card", "amazon", "generic"],
                            index=["bank", "credit_card", "amazon", "generic"].index(
                                proposal.get("source", "bank")),
                            key=f"src::{cache_key}",
                        )
                        st.caption("Detected rules (edit the JSON if needed):")
                        edited = st.text_area(
                            "Rules (JSON: match + parse)",
                            value=json.dumps(
                                {"match": proposal["match"], "parse": proposal["parse"]},
                                indent=2),
                            height=320, key=f"json::{cache_key}",
                        )
                        if st.button("💾 Save new file type", key=f"save::{cache_key}"):
                            try:
                                body = json.loads(edited)
                                formats.add_format(
                                    {"identifier": ident, "source": src,
                                     "match": body["match"], "parse": body["parse"]}
                                )
                                st.session_state.pop(cache_key, None)
                                st.session_state.pop(prop_key, None)
                                st.success(f"Saved format '{ident}'. Re-parsing…")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Invalid rules JSON: {e}")
                continue

            # ---- matched: show identifier, editable categories, highlighted view
            st.success(
                f"Matched format: **{prev['identifier']}**  ·  source "
                f"`{prev['source']}`  ·  {len(prev['rows'])} transactions"
            )
            for w in prev.get("warnings", []):
                st.warning(w)
            if prev.get("skipped"):
                st.caption(f"Skipped {prev['skipped']} non-transaction/summary row(s).")

            df = pd.DataFrame(prev["rows"])[
                ["date", "description", "amount", "category", "included"]]
            df.columns = ["Date", "Description", "Amount", "Category", "Include"]
            df["Include"] = df["Include"].astype(bool)

            options = sorted(set(_category_names(pid)) | {"Uncategorized"}
                             | set(df["Category"]))
            st.caption(
                "Edit categories and toggle **Include** (detected transfers start "
                "excluded and dimmed), then click **Import** to apply all changes "
                "at once.  🟢 money in · 🔴 money out"
            )

            # Counts/metrics reflect the last-applied state. Edits are batched in a
            # form below and only commit when a button is pressed, so these don't
            # churn (and nothing is saved) while you are still editing. Excluded
            # rows are left out of metrics and of the AI's work.
            n_unique = len(_uncategorized_merchant_keys(prev["rows"]))
            n_uncat = sum(1 for r in prev["rows"]
                          if r["category"] == "Uncategorized" and r.get("included", True))
            n_batches = max(1, math.ceil(n_unique / agent_parser.CATEGORIZE_BATCH))
            inc_mask = df["Include"]
            net = df.loc[inc_mask, "Amount"].sum()
            spent = df.loc[inc_mask & (df["Amount"] < 0), "Amount"].sum()
            recv = df.loc[inc_mask & (df["Amount"] > 0), "Amount"].sum()

            # ---- statement ending balance → optionally refresh a Net Worth
            #      account. Reactive (outside the form) so the "create new" fields
            #      can appear; the choice is applied when Import is pressed below.
            sb = prev.get("statement_balance")
            sb_accounts = db.list_accounts(pid)
            sb_opts, sb_choice, sb_new_name, sb_new_kind = [], None, None, None
            if sb:
                with st.container(border=True):
                    st.markdown(
                        f"**💵 Statement ending balance ${sb['amount']:,.2f}** "
                        f"as of {sb['date']}")
                    sb_opts = (["(don't update)"]
                               + [f"{a['name']} — ${a['balance']:,.0f}" for a in sb_accounts]
                               + ["➕ create new account"])
                    sb_choice = st.selectbox(
                        "Update an account balance for Net Worth?", sb_opts,
                        key=f"sbacct::{cache_key}")
                    if sb_choice == "➕ create new account":
                        c_n, c_k = st.columns(2)
                        sb_new_name = c_n.text_input(
                            "New account name", value=prev["identifier"],
                            key=f"sbname::{cache_key}")
                        sb_new_kind = c_k.selectbox(
                            "Kind", _ACCOUNT_KINDS, key=f"sbkind::{cache_key}")

            # A form batches all edits: changing Category cells does nothing — no
            # rerun, no save — until a submit button below is pressed.
            with st.form(f"editform::{cache_key}", border=False):
                # One table: red/green amount cells (Styler) AND an editable
                # Category dropdown. Colors are display-only; Category stays editable.
                edited = st.data_editor(
                    _style_amounts(df), use_container_width=True, hide_index=True,
                    key=f"edit::{cache_key}",
                    disabled=["Date", "Description", "Amount"],
                    column_config={
                        "Category": st.column_config.SelectboxColumn(
                            "Category", options=options,
                            help="Inferred from the description — change if wrong."),
                        "Include": st.column_config.CheckboxColumn(
                            "Include",
                            help="Counts toward totals. Detected transfers (e.g. "
                                 "credit-card payments) start excluded."),
                    },
                )

                m1, m2, m3 = st.columns(3)
                m1.metric("Money in", f"${recv:,.2f}")
                m2.metric("Money out", f"${-spent:,.2f}")
                m3.metric("Net", f"${net:,.2f}")

                # On-demand AI categorization. Kept separate from parsing so the
                # upload stays responsive (the LLM call blocks the whole session).
                if n_uncat:
                    st.caption(
                        f"{n_unique} unique merchant(s) still uncategorized "
                        f"({n_uncat} rows). The AI classifies each merchant once. "
                        "Define categories in the 🏷️ Categories tab first."
                    )
                cols = st.columns([1, 1])
                do_import = cols[0].form_submit_button(
                    f"✅ Import {len(df)} transactions", type="primary",
                    use_container_width=True)
                do_ai = cols[1].form_submit_button(
                    f"🤖 Auto-categorize with AI ({n_uncat} left)",
                    disabled=not ok or n_uncat == 0, use_container_width=True,
                    help="Runs the local model on the still-uncategorized rows "
                         "(may take a while); the app is busy during this call.")

            # ---- Auto-categorize: apply the current edits first, then let the
            #      model fill only the rows still left Uncategorized.
            if do_ai:
                for row, cat, inc in zip(prev["rows"], edited["Category"].tolist(),
                                         edited["Include"].astype(bool).tolist()):
                    row["category"] = cat
                    row["included"] = inc
                before = [r["category"] for r in prev["rows"]]
                with st.status("Running AI categorization…", expanded=True) as ai_status:
                    ai_bar = st.progress(
                        0, text=f"0 / {n_unique} merchants · batch 1 of {n_batches}")

                    def _ai_cb(done, total, _bar=ai_bar, _nb=n_batches):
                        pct = (done / total) if total else 0
                        bn = min(_nb, math.ceil(done / agent_parser.CATEGORIZE_BATCH)) if done else 1
                        _bar.progress(
                            pct,
                            text=f"{done} / {total} merchants  ({pct:.0%}) · "
                                 f"batch {bn} of {_nb}")

                    filled, warn = _ai_categorize_uncategorized(
                        prev["rows"], pid, progress_cb=_ai_cb)
                    if warn:
                        ai_status.update(label="AI categorization failed",
                                         state="error", expanded=True)
                        st.error(
                            f"Could not reach the local model: {warn}. Make sure "
                            "Ollama is running and try again.")
                    elif filled == 0:
                        ai_status.update(label="No new categories found",
                                         state="complete", expanded=True)
                        st.info(
                            "The model couldn't confidently categorize the "
                            "remaining transactions. Try defining more specific "
                            "categories in the 🏷️ Categories tab first.")
                    else:
                        ai_bar.progress(1.0, text=f"{n_unique} / {n_unique} (100%)")
                        ai_status.update(label=f"Categorized {filled} transaction(s)",
                                         state="complete", expanded=False)

                if not warn and filled:
                    # AI-assigned categories are baseline (not user edits): sync
                    # the snapshot only for rows the AI just filled, so manual
                    # edits are still learned as keywords on import.
                    oc = prev.get("original_cats") or list(before)
                    for i, r in enumerate(prev["rows"]):
                        if (i < len(oc) and before[i] == "Uncategorized"
                                and r["category"] != "Uncategorized"):
                            oc[i] = r["category"]
                    prev["original_cats"] = oc
                    st.session_state.pop(f"edit::{cache_key}", None)  # rebuild editor
                    st.toast(f"Categorized {filled} transaction(s). Review and "
                             "import when ready.", icon="✅")
                    st.rerun()

            # ---- Import: save all rows and their categories at once.
            if do_import:
                final_cats = edited["Category"].tolist()
                rows = []
                learned = 0
                for i, (_, r) in enumerate(edited.iterrows()):
                    cat = final_cats[i]
                    included = bool(r["Include"])
                    # Learn a keyword for every included, categorized row (however it
                    # was categorized — keyword, AI, or hand-edit) so the same
                    # merchant auto-tags next time. Excluded rows (transfers) don't
                    # teach rules. _learn_keyword dedupes and counts only new rules.
                    if (included and cat != "Uncategorized"
                            and _learn_keyword(pid, cat, r["Description"])):
                        learned += 1
                    rows.append({
                        "date": r["Date"], "description": r["Description"],
                        "amount": float(r["Amount"]), "category": cat,
                        "source": prev["source"], "included": included,
                    })
                db.add_transactions(pid, rows, file_hash=file_hash)
                # Record the import so this exact file can't be imported twice,
                # so the rerun below shows the "already imported" state instead
                # of re-parsing, and so it appears in the Dashboard's file list.
                db.record_import(pid, file_hash, f.name, len(rows),
                                 datetime.now().strftime("%Y-%m-%d %H:%M"))
                st.session_state.pop(cache_key, None)
                msg = f"✅ Imported {len(rows)} transactions from {f.name}."
                if learned:
                    msg += f" Learned {learned} new keyword rule(s) for next time."
                # Refresh / create a Net Worth account from the statement balance.
                if sb and sb_choice and sb_choice != "(don't update)":
                    if sb_choice == "➕ create new account" and sb_new_name:
                        aid = db.add_account(pid, sb_new_name, sb_new_kind,
                                             _is_asset_default(sb_new_kind), sb["amount"])
                        db.write_snapshot(aid, sb["date"], sb["amount"])
                        msg += f" Created account '{sb_new_name}' at ${sb['amount']:,.0f}."
                    elif sb_choice in sb_opts and sb_choice != "➕ create new account":
                        chosen = sb_accounts[sb_opts.index(sb_choice) - 1]
                        db.update_account_balance(chosen["id"], sb["amount"],
                                                  snapshot_date=sb["date"])
                        msg += f" Updated '{chosen['name']}' to ${sb['amount']:,.0f}."
                st.session_state["import_done_msg"] = msg
                st.rerun()

        st.divider()
        if txns and st.button("⚠️ Clear all of this person's transactions"):
            db.clear_transactions(pid)
            st.rerun()

    with st.expander("🗂️ Manage imported files"):
        _manage_files_section(view, pid)

# ---------------------------------------------------------------- CATEGORIES
with tab_cats:
    if view == "Household":
        st.info("Categories are managed per person.")
    else:
        st.write("Define categories with keywords. When importing, any "
                 "transaction whose description contains a keyword is auto-tagged.")
        with st.form("add_cat"):
            cname = st.text_input("Category name")
            ckeys = st.text_input("Keywords (comma-separated)",
                                  placeholder="whole foods, trader joe, grocery")
            if st.form_submit_button("Save category") and cname:
                db.upsert_category(pid, cname, ckeys)
                st.rerun()
        for c in db.get_categories(pid):
            col1, col2 = st.columns([4, 1])
            col1.write(f"**{c['name']}** — {c['keywords'] or '_no keywords_'}")
            if col2.button("Delete", key=f"delcat{c['id']}"):
                db.delete_category(c["id"])
                st.rerun()

        st.divider()
        st.subheader("Auto-categorize with the local agent")
        unknown = db.get_uncategorized_descriptions(pid)
        n_merchants = len({keywords.keyword_from_desc(d) for d in unknown})
        st.caption(f"{n_merchants} uncategorized merchant(s) across {len(unknown)} "
                   "description(s). The local AI agent recognizes common merchants "
                   "(Chewy → Dog, Chipotle → Eating Out) by name — runs on-machine, "
                   "nothing sent to the web. Each merchant is classified once.")
        if unknown and st.button("Auto-categorize uncategorized"):
            cat_names = [c["name"] for c in db.get_categories(pid)]
            if not cat_names:
                st.warning("Define at least one category first.")
            else:
                try:
                    with st.spinner("Local agent categorizing…"):
                        mapping = keywords.classify_descriptions(
                            unknown, cat_names, agent_parser.categorize_with_agent)
                        db.apply_category_mapping(pid, mapping)
                    applied = sum(1 for c in mapping.values() if c != "Uncategorized")
                    st.success(f"Categorized {applied} of {len(mapping)} description(s).")
                    st.rerun()
                except Exception as e:
                    st.error(f"Auto-categorize failed: {e}")

# ---------------------------------------------------------------- GOALS
with tab_goals:
    st.caption("Track short- and long-term goals. Shared goals show in the "
               "Household view.")
    with st.expander("➕ Add a goal"):
        with st.form("add_goal"):
            gname = st.text_input("Goal name")
            col1, col2, col3 = st.columns(3)
            target = col1.number_input("Target $", min_value=0.0, step=100.0)
            saved = col2.number_input("Saved so far $", min_value=0.0, step=100.0)
            tdate = col3.date_input("Target date")
            col4, col5 = st.columns(2)
            horizon = col4.selectbox("Horizon", ["short", "long"])
            owner = col5.selectbox(
                "Owner",
                ["Shared"] + [p["name"] for p in people],
            )
            notes = st.text_area("Notes (kept local, never sent to AI)")
            if st.form_submit_button("Add goal") and gname:
                owner_id = None if owner == "Shared" else name_to_id[owner]
                db.add_goal(owner_id, gname, target, saved,
                            tdate.isoformat(), horizon, notes)
                st.rerun()

    goals_list = analytics.goal_progress(goals_for_view(view))
    if not goals_list:
        st.info("No goals yet — add one above.")
    for g in goals_list:
        with st.container(border=True):
            top, edit = st.columns([5, 1])
            with top:
                pct = min(g["percent"] / 100, 1.0)
                st.markdown(f"**{g['name']}**  ·  _{g['horizon']}-term_")
                st.progress(
                    pct,
                    text=f"{g['percent']:.0f}% — ${g['saved_amount']:,.0f} of "
                         f"${g['target_amount']:,.0f}")
                if g["monthly_needed"] is not None:
                    st.caption(
                        f"Need ~${g['monthly_needed']:,.0f}/month to hit the target date.")
            with edit:
                with st.popover("Edit"):
                    new_saved = st.number_input(
                        "Saved amount", min_value=0.0, value=float(g["saved_amount"]),
                        step=100.0, key=f"save{g['id']}")
                    if st.button("Update", key=f"upd{g['id']}"):
                        db.update_goal_saved(g["id"], new_saved)
                        st.rerun()
                    if st.button("🗑️ Delete", key=f"delgoal{g['id']}"):
                        db.delete_goal(g["id"])
                        st.rerun()

# ---------------------------------------------------------------- NET WORTH
with tab_networth:
    st.caption("Assets minus liabilities. Balances are a manual ledger; importing "
               "a bank statement can refresh an account (Import tab).")
    accounts = accounts_for_view(view)
    nw = analytics.net_worth(accounts)
    trend = analytics.net_worth_trend(snapshots_for_view(view))
    # Last trend point == current net (every change writes a same-day snapshot),
    # so the delta reads as the change since the previous snapshot date.
    nw_delta = (nw["net"] - float(trend.iloc[-2]["net"])) if len(trend) >= 2 else None

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Net worth", f"${nw['net']:,.0f}",
                  delta=None if nw_delta is None else f"{nw_delta:+,.0f}",
                  help="Total assets minus liabilities. Delta is the change since "
                       "the previous snapshot date.")
        c2.metric("Assets", f"${nw['assets']:,.0f}")
        c3.metric("Liabilities", f"${nw['liabilities']:,.0f}")

    with st.container(border=True):
        st.subheader("Net worth over time")
        if len(trend) >= 2:
            line = alt.Chart(trend).mark_line(point=True).encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("net:Q", title=None, axis=alt.Axis(format="$,.0f")),
                tooltip=[alt.Tooltip("date:T", title="Date"),
                         alt.Tooltip("net:Q", title="Net worth", format="$,.2f"),
                         alt.Tooltip("assets:Q", title="Assets", format="$,.2f"),
                         alt.Tooltip("liabilities:Q", title="Liabilities", format="$,.2f")],
            )
            st.altair_chart(line, use_container_width=True)
        else:
            st.caption("Update balances over time (or import statements) to see a trend.")

    with st.container(border=True):
        st.subheader("Accounts")
        if not accounts:
            st.caption("No accounts yet — add one below.")
        for a in accounts:
            tag = "asset" if a["is_asset"] else "liability"
            label = f"**{a['name']}**  ·  _{a['kind']}_  ·  {tag}  ·  ${a['balance']:,.0f}"
            if view == "Household":
                label += f"  ·  {id_to_name.get(a['person_id'], 'Shared')}"
            top, edit = st.columns([5, 1])
            top.markdown(label)
            with edit:
                with st.popover("Edit"):
                    nb = st.number_input("Balance", value=float(a["balance"]),
                                         step=100.0, key=f"acctbal{a['id']}")
                    if st.button("Update", key=f"acctupd{a['id']}"):
                        db.update_account_balance(a["id"], nb)
                        st.rerun()
                    if st.button("🗑️ Delete", key=f"acctdel{a['id']}"):
                        db.delete_account(a["id"])
                        st.rerun()

        with st.expander("➕ Add account"):
            # Picking a Kind re-derives Type (asset/liability), so a loan or card
            # never silently defaults to an asset and inflates net worth — but the
            # user can still override Type for an unusual case (it has its own key).
            def _sync_type():
                st.session_state.newacct_type = (
                    "asset" if _is_asset_default(st.session_state.newacct_kind)
                    else "liability")

            an = st.text_input("Account name", placeholder="BofA Checking",
                               key="newacct_name")
            cc1, cc2 = st.columns(2)
            cc1.selectbox("Kind", _ACCOUNT_KINDS, key="newacct_kind",
                          on_change=_sync_type)
            ab = cc2.number_input("Balance", min_value=0.0, step=100.0,
                                  key="newacct_bal")
            cc3, cc4 = st.columns(2)
            at = cc3.selectbox("Type", ["asset", "liability"], key="newacct_type")
            ao = cc4.selectbox("Owner", ["Shared"] + [p["name"] for p in people],
                               key="newacct_owner")
            if st.button("Add account", key="newacct_submit") and an:
                owner_id = None if ao == "Shared" else name_to_id[ao]
                db.add_account(owner_id, an, st.session_state.newacct_kind,
                               at == "asset", ab)
                for k in ("newacct_name", "newacct_kind", "newacct_bal",
                          "newacct_owner", "newacct_type"):
                    st.session_state.pop(k, None)
                st.rerun()


# ---------------------------------------------------------------- AI INSIGHTS
with tab_ai:
    st.caption("Generate AI insights from **anonymized aggregates only** — no "
               "merchants, raw transactions, names, or notes are sent.")

    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not has_key:
        st.info("No `ANTHROPIC_API_KEY` set — **preview mode**. You can see exactly "
                "what *would* be sent below; set the key to enable live insights.")

    # Build the summaries depending on the view.
    summaries = []
    if view == "Household":
        for i, p in enumerate(people):
            label = f"Person {chr(65 + i)}"  # Person A, Person B
            t = db.get_transactions(p["id"])
            g = db.get_goals(p["id"])
            summaries.append(
                ai_insights.build_anonymized_summary(label, t, g, analytics)
            )
        shared_goals = db.get_goals(None)
        summaries.append(
            ai_insights.build_anonymized_summary(
                "Household (shared goals)", db.get_transactions(), shared_goals, analytics
            )
        )
    else:
        summaries.append(
            ai_insights.build_anonymized_summary("Person A", txns, goals, analytics)
        )

    with st.expander("🔍 See exactly what would be sent"):
        st.code(ai_insights.preview_payload(summaries), language="json")

    if st.button("Generate insights", disabled=not has_key,
                 help=None if has_key else "Set ANTHROPIC_API_KEY to enable"):
        with st.spinner("Thinking..."):
            with st.container(border=True):
                st.markdown(ai_insights.get_insights(summaries))
                st.caption("Generated from anonymized aggregates only.")
