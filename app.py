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


def _hbar(data, value_name, color="#0F766E", value_title=None):
    """Horizontal bar chart from a {label: amount} dict, sorted by value."""
    d = pd.DataFrame({"label": list(data), value_name: list(data.values())})
    return alt.Chart(d).mark_bar(color=color).encode(
        x=alt.X(f"{value_name}:Q", title=None, axis=alt.Axis(format="$,.0f")),
        y=alt.Y("label:N", sort="-x", title=None),
        tooltip=[alt.Tooltip("label:N", title="Category"),
                 alt.Tooltip(f"{value_name}:Q", title=value_title or value_name,
                             format="$,.2f")],
    )


def _view_category_names(view):
    """Category names available in the current view (union across people for the
    Household view)."""
    if view == "Household":
        names = set()
        for p in name_to_id.values():
            names |= set(_category_names(p))
        return sorted(names)
    return sorted(_category_names(name_to_id[view]))


def _view_vendor_rules(view):
    """Vendor rules [(name, [keywords])] for the view (union across people in the
    Household view). Used to collapse merchant variants in the drill-down."""
    people_ids = (list(name_to_id.values()) if view == "Household"
                  else [name_to_id[view]])
    rules = []
    for p in people_ids:
        for v in db.get_vendors(p):
            rules.append((v["name"], (v["keywords"] or "").split(",")))
    return rules


def _vendor_manager(view, key_prefix):
    """Add / edit / delete vendor groups for the current person. Shared by the
    Categories tab and the Analysis drill-down. Vendor groups collapse merchant
    name variants (Amazon.com / AMAZON MKTPL / AMAZON PRIME → 'Amazon') in the
    drill-down. Editable per person; the Household view is read-only here."""
    if view == "Household":
        st.info("Switch to a person's view to edit their vendor groups. "
                "(The Analysis drill-down uses both people's groups.)")
        return
    pid_ = name_to_id[view]
    st.caption("A transaction joins the **first** vendor whose keyword appears in "
               "its description; unmatched merchants keep their auto-detected name.")
    with st.form(f"addvendor::{key_prefix}::{view}"):
        c1, c2 = st.columns(2)
        vn = c1.text_input("Vendor name", placeholder="Amazon")
        vk = c2.text_input("Keywords (comma-separated)", placeholder="amazon, amzn")
        if st.form_submit_button("Save vendor") and vn.strip():
            db.upsert_vendor(pid_, vn.strip(), vk.strip())
            st.rerun()
    for v in db.get_vendors(pid_):
        vc1, vc2 = st.columns([4, 1])
        vc1.write(f"**{v['name']}** — {v['keywords'] or '_no keywords_'}")
        if vc2.button("Delete", key=f"{key_prefix}delvendor{v['id']}"):
            db.delete_vendor(v["id"])
            st.rerun()


def _editable_txn_table(rows, key, cat_options):
    """Editable table over PERSISTED transactions (each row dict has an 'id'):
    pick Category from a dropdown and toggle Include. Edits persist to the DB and
    rerun so every chart updates. Excluded rows are dimmed. Used on the Dashboard
    and in the Analysis drill-down so categories are editable from any table."""
    if not rows:
        st.caption("No transactions.")
        return
    tdf = pd.DataFrame(rows)
    opts = sorted(set(cat_options) | set(tdf["category"]) | {"Uncategorized"})
    disp = pd.DataFrame({
        "Date": tdf["date"], "Description": tdf["description"],
        "Amount": tdf["amount"].astype(float), "Category": tdf["category"],
        "Include": (tdf["included"].astype(bool)
                    if "included" in tdf.columns else True),
    })
    edited = st.data_editor(
        _style_amounts(disp), width="stretch", hide_index=True, key=key,
        disabled=["Date", "Description", "Amount"],
        column_config={
            "Category": st.column_config.SelectboxColumn("Category", options=opts),
            "Include": st.column_config.CheckboxColumn(
                "Include", help="Counts toward all totals and charts"),
        },
    )
    ids = tdf["id"].tolist()
    nc, oc = edited["Category"].tolist(), disp["Category"].tolist()
    ni, oi = (edited["Include"].astype(bool).tolist(),
              disp["Include"].astype(bool).tolist())
    changed = False
    for i in range(len(ids)):
        if nc[i] != oc[i]:
            db.set_transaction_category(ids[i], nc[i])
            changed = True
        if ni[i] != oi[i]:
            db.set_transaction_included(ids[i], bool(ni[i]))
            changed = True
    if changed:
        st.session_state.pop(key, None)  # rebuild from fresh data
        st.rerun()


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


def _recurring_section(view_txns, view):
    """Recurring / subscription panel: detected charges + committed monthly total +
    anomalies. Scans the FULL history for the active view (cadence detection needs
    several months), so the Analysis filter bar deliberately doesn't apply here."""
    rec = analytics.recurring_charges(view_txns, _view_vendor_rules(view))
    if not rec:
        st.caption("No recurring charges detected yet — a merchant needs at least "
                   "three charges at a regular cadence (weekly/monthly/yearly).")
        return
    cm = analytics.committed_monthly(rec)
    c1, c2, c3 = st.columns(3)
    c1.metric("Committed / mo", f"${cm['total']:,.0f}",
              help="Estimated recurring monthly spend (subscriptions + regular bills).")
    c2.metric("Fixed / mo", f"${cm['fixed']:,.0f}",
              help="Steady-amount subscriptions (Netflix, gym…).")
    c3.metric("Variable / mo", f"${cm['variable']:,.0f}",
              help="Regular but usage-based bills (phone, electric…).")

    min_conf = st.slider("Min confidence", 0.0, 1.0, 0.5, 0.05,
                         key=f"rec_conf::{view}",
                         help="Hide low-confidence guesses. Higher = stricter.")
    shown = [r for r in rec if r["confidence"] >= min_conf]
    if not shown:
        st.caption("Nothing above this confidence — lower the slider to see more.")
    else:
        df = pd.DataFrame([{
            "Vendor": r["vendor"], "Category": r["category"], "Cadence": r["cadence"],
            "Type": r["kind"], "Typical": r["typical_amount"],
            "Monthly": r["monthly_cost"], "Annual": r["annual_cost"],
            "Last charge": r["last_date"], "Next ~": r["next_expected"],
            "Seen": r["count"], "Confidence": r["confidence"],
        } for r in shown])
        st.dataframe(df, width="stretch", hide_index=True, column_config={
            "Typical": st.column_config.NumberColumn(format="$%.2f"),
            "Monthly": st.column_config.NumberColumn(format="$%.2f"),
            "Annual": st.column_config.NumberColumn(format="$%.2f"),
            "Confidence": st.column_config.ProgressColumn(
                min_value=0.0, max_value=1.0, format="%.2f"),
        })

    anoms = analytics.recurring_anomalies(rec)
    if anoms:
        st.markdown("**⚠️ Anomalies**")
        label = {"price_change": "💵 Price change",
                 "possibly_canceled": "🛑 Possibly canceled", "new": "🆕 New"}
        st.dataframe(pd.DataFrame([{
            "Vendor": a["vendor"], "What": label.get(a["type"], a["type"]),
            "Detail": a["detail"]} for a in anoms]),
            width="stretch", hide_index=True)


pid = person_id_for_view(view)
txns = transactions_for_view(view)
goals = goals_for_view(view)

st.title(f"{view} — Overview")

tab_dash, tab_analysis, tab_import, tab_cats, tab_goals, tab_networth, tab_ai = st.tabs(
    ["📊 Dashboard", "📈 Analysis", "📥 Import", "🏷️ Categories", "🎯 Goals",
     "💵 Net Worth", "🤖 AI Insights"]
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

        # --- Committed recurring spend: a compact read on fixed obligations, with
        #     an alert count. Full breakdown lives in 📈 Analysis › Recurring.
        dash_rec = analytics.recurring_charges(txns, _view_vendor_rules(view))
        if dash_rec:
            with st.container(border=True):
                cm = analytics.committed_monthly(dash_rec)
                anoms = analytics.recurring_anomalies(dash_rec)
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Committed / mo", f"${cm['total']:,.0f}",
                           help="Recurring monthly spend (subscriptions + regular "
                                "bills). Details in 📈 Analysis › Recurring.")
                rc2.metric("Fixed vs variable",
                           f"${cm['fixed']:,.0f} / ${cm['variable']:,.0f}",
                           help="Steady subscriptions vs usage-based bills.")
                rc3.metric("Recurring alerts",
                           f"⚠️ {len(anoms)}" if anoms else "0",
                           help="Price changes, likely cancellations, or new "
                                "subscriptions — see 📈 Analysis › Recurring.")

        # --- Trends across all imported months. A month-range slider focuses the
        #     charts; each chart is also .interactive() (drag to pan, scroll to
        #     zoom) on its temporal x-axis.
        if savings.empty:
            st.caption("Import a month or two to see trends.")
        else:
            months = list(savings.index)            # sorted 'YYYY-MM'
            lo, hi = months[0], months[-1]
            if len(months) >= 2:
                lo, hi = st.select_slider(
                    "Month range", options=months, value=(months[0], months[-1]),
                    key="dash_range",
                    help="Focus the charts on a span of months. You can also drag to "
                         "pan and scroll to zoom inside each chart.")
            in_range = [m for m in months if lo <= m <= hi]

            def _month_dt(df):
                df = df.copy()
                df["date"] = pd.to_datetime(df["month"] + "-01")
                return df

            # 1) Overall spend vs income per month
            with st.container(border=True):
                st.subheader("Spend vs income by month")
                sav = savings.reset_index()
                sav = _month_dt(sav[sav["month"].isin(in_range)])
                flow = sav.melt(["month", "date"], value_vars=["income", "spend"],
                                var_name="flow", value_name="amount")
                st.altair_chart(alt.Chart(flow).mark_line(point=True).encode(
                    x=alt.X("date:T", title=None,
                            axis=alt.Axis(format="%b %Y", tickCount="month")),
                    y=alt.Y("amount:Q", title=None, axis=alt.Axis(format="$,.0f")),
                    color=alt.Color("flow:N", title=None, scale=alt.Scale(
                        domain=["income", "spend"], range=["#0F766E", "#C0584E"])),
                    tooltip=[alt.Tooltip("month:N", title="Month"), "flow:N",
                             alt.Tooltip("amount:Q", title="Amount", format="$,.2f")],
                ).interactive(), width="stretch")

            # 2) Spending per category per month (one line per category)
            with st.container(border=True):
                st.subheader("Spending by category by month")
                pivot = analytics.spending_by_category_over_time(txns)
                if pivot.empty:
                    st.caption("No spending (negative-amount) transactions yet.")
                else:
                    cats_present = sorted(pivot.columns)
                    pick = st.multiselect("Categories (blank = all)", cats_present,
                                          key="dash_cats")
                    long = pivot.reset_index().melt(
                        "month", var_name="category", value_name="spend")
                    long = long[long["month"].isin(in_range)]
                    if pick:
                        long = long[long["category"].isin(pick)]
                    long = _month_dt(long)
                    st.altair_chart(alt.Chart(long).mark_line(point=True).encode(
                        x=alt.X("date:T", title=None,
                            axis=alt.Axis(format="%b %Y", tickCount="month")),
                        y=alt.Y("spend:Q", title=None, axis=alt.Axis(format="$,.0f")),
                        color=alt.Color("category:N", title="Category"),
                        tooltip=[alt.Tooltip("month:N", title="Month"),
                                 alt.Tooltip("category:N", title="Category"),
                                 alt.Tooltip("spend:Q", title="Spend", format="$,.2f")],
                    ).interactive(), width="stretch")

        # --- Transactions: edit Category (dropdown) and toggle Include inline
        with st.container(border=True):
            st.subheader("Transactions")
            st.caption("Change a row's **Category** or uncheck **Include** to drop it "
                       "from every total and chart. Excluded rows are dimmed; changes "
                       "save immediately.")
            # View by source file (the imported statement a row came from).
            fmap = {}  # label -> file_hash
            for im in db.list_imports(pid):
                lbl = im["filename"]
                if view == "Household":
                    lbl += f" · {im['person']}"
                if lbl in fmap:
                    lbl += f" ({im['file_hash'][:6]})"
                fmap[lbl] = im["file_hash"]
            has_untracked = any(t.get("file_hash") is None for t in txns)
            file_opts = (["All files"] + list(fmap)
                         + (["Untracked"] if has_untracked else []))
            pick_file = st.selectbox("View file", file_opts, key=f"txnfile::{view}")
            if pick_file == "All files":
                shown = txns
            elif pick_file == "Untracked":
                shown = [t for t in txns if t.get("file_hash") is None]
            else:
                fh = fmap[pick_file]
                shown = [t for t in txns if t.get("file_hash") == fh]
            _editable_txn_table(shown, f"txntable::{view}::{pick_file}",
                                _view_category_names(view))

# ---------------------------------------------------------------- ANALYSIS
with tab_analysis:
    if not txns:
        st.info("No transactions yet — import some in the 📥 Import tab first.")
    else:
        _dts = sorted(t["date"] for t in txns)
        dmin = pd.to_datetime(_dts[0]).date()
        dmax = pd.to_datetime(_dts[-1]).date()
        cat_opts = sorted({t["category"] for t in txns})

        mode = st.radio("Mode", ["Explore", "Compare", "People", "Recurring"],
                        horizontal=True, label_visibility="collapsed")

        # ---- shared filter bar (control-driven; maps 1:1 to filter_transactions)
        with st.container(border=True):
            st.caption("Filters apply to the charts below.")
            fc1, fc2, fc3 = st.columns([2, 1, 1])
            dr = fc1.date_input("Date range", value=(dmin, dmax),
                                min_value=dmin, max_value=dmax, key="an_dr")
            daytype = fc2.radio("Days", ["All", "Weekdays", "Weekends"], key="an_daytype")
            ev_choice = fc3.selectbox("Event", ["(none)", "Workdays", "Weekends"],
                                      key="an_event")
            dow_sel = st.multiselect("Specific days of week", analytics.DOW_NAMES,
                                     key="an_dow")
            all_months = sorted({t["date"][:7] for t in txns})
            month_sel = st.multiselect("Months (blank = all)", all_months,
                                       key="an_months",
                                       help="Pick specific months — they don't have to "
                                            "be next to each other.")
            cat_sel = st.multiselect("Categories (blank = all)", cat_opts, key="an_cats")

        kw = {}
        if isinstance(dr, (list, tuple)) and len(dr) == 2:
            kw["date_range"] = (dr[0].isoformat(), dr[1].isoformat())
        if month_sel:
            kw["months"] = month_sel
        if daytype == "Weekdays":
            kw["day_types"] = ["weekday"]
        elif daytype == "Weekends":
            kw["day_types"] = ["weekend"]
        if dow_sel:
            kw["dow"] = [analytics.DOW_NAMES.index(d) for d in dow_sel]
        if ev_choice == "Workdays":
            kw["event"] = analytics.WORKDAYS
        elif ev_choice == "Weekends":
            kw["event"] = analytics.WEEKENDS
        if cat_sel:
            kw["categories"] = cat_sel
        fsel = analytics.filter_transactions(txns, **kw)

        if not fsel and mode != "Recurring":
            st.warning("No transactions match these filters.")
        elif mode == "Explore":
            cats = analytics.drill(fsel, "category")
            m1, m2 = st.columns(2)
            m1.metric("Spend (filtered)", f"${sum(cats.values()):,.0f}")
            m2.metric("Transactions", f"{len(fsel):,}")
            with st.container(border=True):
                st.subheader("Spending by category")
                if cats:
                    st.altair_chart(_hbar(cats, "spend", "#C0584E", "Spend"),
                                    width="stretch")
                # Drill: Total -> Category -> Vendor -> Rows (control-driven).
                # Vendor groups collapse merchant variants (all Amazon forms ->
                # "Amazon", all MTA -> "MTA"); manage them in the expander below.
                vrules = _view_vendor_rules(view)
                drill_cat = st.selectbox("🔎 Drill into a category",
                                         ["(all)"] + list(cats), key="an_drillcat")
                if drill_cat != "(all)":
                    vendors = analytics.drill(fsel, "vendor", parent=drill_cat,
                                              vendor_rules=vrules)
                    st.markdown(f"**{drill_cat} · by vendor**")
                    if vendors:
                        st.altair_chart(_hbar(vendors, "spend", "#C0584E", "Spend"),
                                        width="stretch")
                    drill_v = st.selectbox("🔎 Drill into a vendor",
                                           ["(all)"] + list(vendors), key="an_drillv")
                    cat_rows = [t for t in fsel if t["category"] == drill_cat]
                    rows = (analytics.drill(cat_rows, "rows", parent=drill_v,
                                            vendor_rules=vrules)
                            if drill_v != "(all)" else cat_rows)
                    st.caption("Edit a row's **Category** here too — it saves "
                               "immediately and re-categorizes that transaction.")
                    _editable_txn_table(rows, f"an_rows::{view}::{drill_cat}::{drill_v}",
                                        _view_category_names(view))
                # --- manage vendor groups (how merchants roll up)
                with st.expander("🏷️ Vendor groups — how merchants roll up"):
                    _vendor_manager(view, "an")
            with st.container(border=True):
                st.subheader("Spending over time (filtered)")
                pv = analytics.spending_by_category_over_time(fsel)
                if not pv.empty:
                    long = pv.reset_index().melt("month", var_name="category",
                                                 value_name="spend")
                    st.altair_chart(alt.Chart(long).mark_area().encode(
                        x=alt.X("month:N", title=None),
                        y=alt.Y("spend:Q", stack=True, title=None,
                                axis=alt.Axis(format="$,.0f")),
                        color=alt.Color("category:N", title="Category"),
                    ), width="stretch")
                else:
                    st.caption("No spending in range.")

        elif mode == "Compare":
            preset = st.selectbox("Comparison",
                                  ["Weekdays vs Weekends", "This month vs last month"],
                                  key="an_cmp")
            normalize = st.radio("Measure", ["Per day (fair)", "Totals"],
                                 horizontal=True, key="an_norm")
            base = {k: v for k, v in kw.items() if k not in ("day_types", "event")}
            ga = gb = None
            if preset == "Weekdays vs Weekends":
                ga = {**base, "label": "Weekdays", "day_types": ["weekday"]}
                gb = {**base, "label": "Weekends", "day_types": ["weekend"]}
            else:
                months = sorted({t["date"][:7] for t in txns})
                if len(months) < 2:
                    st.info("Need at least two months of data for month-over-month.")
                else:
                    import calendar as _cal

                    def _mrange(m):
                        y, mo = int(m[:4]), int(m[5:7])
                        return (f"{m}-01", f"{m}-{_cal.monthrange(y, mo)[1]:02d}")
                    ga = {"label": months[-2], "date_range": _mrange(months[-2])}
                    gb = {"label": months[-1], "date_range": _mrange(months[-1])}
            if ga and gb:
                cmp_df = analytics.compare(txns, ga, gb)
                if cmp_df.empty:
                    st.warning("Nothing to compare for these filters.")
                else:
                    yf = "per_day" if normalize.startswith("Per") else "total"
                    yt = "$/day" if yf == "per_day" else "Total $"
                    st.altair_chart(alt.Chart(cmp_df).mark_bar().encode(
                        x=alt.X("category:N", title=None, sort="-y"),
                        y=alt.Y(f"{yf}:Q", title=yt, axis=alt.Axis(format="$,.0f")),
                        color=alt.Color("bucket:N", title="Bucket"),
                        xOffset="bucket:N",
                        tooltip=["bucket:N", "category:N",
                                 alt.Tooltip(f"{yf}:Q", format="$,.2f")],
                    ), width="stretch")
                    tot = cmp_df.groupby("bucket")[yf].sum()
                    cols = st.columns(len(tot))
                    for col, (b, v) in zip(cols, tot.items()):
                        col.metric(str(b), f"${v:,.0f}"
                                   + ("/day" if yf == "per_day" else ""))

        elif mode == "People":
            if view != "Household":
                st.info("Switch to the **Household** view to compare people.")
            else:
                ids = list(name_to_id.values())
                a_id, b_id = ids[0], ids[1]
                a_name, b_name = id_to_name[a_id], id_to_name[b_id]
                rows = analytics.user_overlap(fsel, a_id, b_id)
                if not rows:
                    st.caption("No spending to compare.")
                else:
                    shared = [r for r in rows if r["shared"]]
                    m1, m2, m3 = st.columns(3)
                    m1.metric(f"{a_name} spend",
                              f"${sum(r['a_spend'] for r in rows):,.0f}")
                    m2.metric(f"{b_name} spend",
                              f"${sum(r['b_spend'] for r in rows):,.0f}")
                    m3.metric("Shared categories", f"{len(shared)}")
                    dd = []
                    for r in rows:
                        dd.append({"category": r["category"], "person": a_name,
                                   "amount": -r["a_spend"]})
                        dd.append({"category": r["category"], "person": b_name,
                                   "amount": r["b_spend"]})
                    st.altair_chart(alt.Chart(pd.DataFrame(dd)).mark_bar().encode(
                        y=alt.Y("category:N", title=None),
                        x=alt.X("amount:Q", title=f"← {a_name}   |   {b_name} →",
                                axis=alt.Axis(format="$,.0f")),
                        color=alt.Color("person:N", title="Person"),
                        tooltip=["person:N", "category:N",
                                 alt.Tooltip("amount:Q", format="$,.2f")],
                    ), width="stretch")
                    if shared:
                        st.markdown("**Mutual spending (both spent)**")
                        st.dataframe(pd.DataFrame([{
                            "Category": r["category"], a_name: round(r["a_spend"], 2),
                            b_name: round(r["b_spend"], 2)} for r in shared]),
                            width="stretch", hide_index=True)

        elif mode == "Recurring":
            st.caption("Recurring charges across your **full** history for this view "
                       "— the filter bar above doesn't apply here.")
            _recurring_section(txns, view)


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
                if file_hash in st.session_state.get("imported_now", set()):
                    # Just imported in this session; the file is still sitting in
                    # the uploader. Reassure rather than warn.
                    st.success(
                        f"✅ Imported — {existing['count']} transactions added. "
                        "You can remove this file from the uploader above; "
                        "re-uploading it won't import it twice.", icon="✅")
                else:
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
                    st.dataframe(prev["raw_preview"], width="stretch",
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

            existing_cats = sorted(_category_names(pid))
            cat_options = sorted(set(existing_cats) | {"Uncategorized"}
                                 | set(df["Category"]))
            # Quick category creator. It lives OUTSIDE the edit form (below), so
            # clicking Add takes effect immediately and the new name joins the
            # dropdown; the form keeps your in-progress edits across the rerun.
            ccap, cadd = st.columns([4, 1])
            ccap.caption(
                "Pick a category from each row's dropdown, or add a new one with "
                "**➕ New category** →. Toggle **Include** (detected transfers start "
                "excluded and dimmed), then click **Import**.  🟢 money in · 🔴 money out")
            with cadd.popover("➕ New category"):
                _nc = st.text_input("New category name", key=f"newcat::{cache_key}")
                if st.button("Add", key=f"addcat::{cache_key}"):
                    nm = (_nc or "").strip()
                    if not nm:
                        st.warning("Enter a name.")
                    elif nm in existing_cats:
                        st.info("That category already exists.")
                    else:
                        db.upsert_category(pid, nm, "")
                        st.toast(f"Added category '{nm}'.", icon="✅")
                        st.rerun()

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
                    _style_amounts(df), width="stretch", hide_index=True,
                    key=f"edit::{cache_key}",
                    disabled=["Date", "Description", "Amount"],
                    column_config={
                        "Category": st.column_config.SelectboxColumn(
                            "Category", options=cat_options,
                            help="Pick a category. Need a new one? Use "
                                 "➕ New category above the table."),
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
                    width="stretch")
                do_ai = cols[1].form_submit_button(
                    f"🤖 Auto-categorize with AI ({n_uncat} left)",
                    disabled=not ok or n_uncat == 0, width="stretch",
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
                known = set(_category_names(pid))
                rows = []
                learned = 0
                created = 0
                for i, (_, r) in enumerate(edited.iterrows()):
                    cat = (str(final_cats[i]) if final_cats[i] is not None else "").strip()
                    cat = cat or "Uncategorized"
                    included = bool(r["Include"])
                    # A category typed into the table that doesn't exist yet is
                    # created now, so it persists and can learn a keyword.
                    if included and cat != "Uncategorized" and cat not in known:
                        db.upsert_category(pid, cat, "")
                        known.add(cat)
                        created += 1
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
                if created:
                    msg += f" Created {created} new category(ies)."
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
                # Remember we imported THIS file this session, so the post-rerun
                # render (the file is still in the uploader) shows a positive
                # "just imported" note rather than the dedup warning.
                st.session_state.setdefault("imported_now", set()).add(file_hash)
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
        st.subheader("Vendor groups")
        st.caption("Collapse merchant-name variants (Amazon.com, AMAZON MKTPL, "
                   "AMAZON PRIME → one **Amazon**) into a single line in the Analysis "
                   "drill-down. Edit them here or in the Analysis tab.")
        _vendor_manager(view, "cat")

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
    st.caption("Assets minus liabilities. Add an account, then **Manage** it to "
               "populate month-end balances from your imported bank statements, or "
               "record balances by hand (investments, 401k, HSA…).")
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
            st.altair_chart(line, width="stretch")
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
            with st.container(border=True):
                top, edit = st.columns([5, 1])
                top.markdown(label)
                with edit:
                    with st.popover("Manage"):
                        # -- current balance + delete
                        nb = st.number_input("Current balance",
                                             value=float(a["balance"]), step=100.0,
                                             key=f"acctbal{a['id']}")
                        if st.button("Update balance", key=f"acctupd{a['id']}"):
                            db.update_account_balance(a["id"], nb)
                            st.rerun()

                        # -- populate month-end balances from imported statements
                        st.divider()
                        st.markdown("**Populate month-end balances from statements**")
                        imps = db.list_imports(a["person_id"])
                        opt_map = {}
                        for im in imps:
                            lbl = im["filename"]
                            if a["person_id"] is None:
                                lbl += f" · {im['person']}"
                            if lbl in opt_map:
                                lbl += f" ({im['file_hash'][:6]})"
                            opt_map[lbl] = im
                        if opt_map:
                            pick = st.multiselect(
                                "Bank statement file(s)", list(opt_map),
                                key=f"acctpick{a['id']}",
                                help="Uses each statement's running balance to record "
                                     "the balance at the end of every month it covers.")
                            if st.button("Populate", key=f"acctpop{a['id']}") and pick:
                                rows = []
                                for lbl in pick:
                                    im = opt_map[lbl]
                                    rows += db.transactions_for_file(
                                        im["person_id"], im["file_hash"])
                                meb = analytics.month_end_balances(rows)
                                if not meb:
                                    st.warning("Those files have no running-balance "
                                               "data. Re-import the bank statement "
                                               "(its 'Running Bal.' column powers this).")
                                else:
                                    for pt in meb:
                                        db.write_snapshot(a["id"], pt["date"], pt["balance"])
                                    last = meb[-1]
                                    db.update_account_balance(
                                        a["id"], last["balance"], snapshot_date=last["date"])
                                    st.toast(f"Recorded {len(meb)} month-end balance(s).",
                                             icon="✅")
                                    st.rerun()
                        else:
                            st.caption("No imported files for this owner yet.")

                        # -- record a manual balance point (investments, 401k, HSA…)
                        st.divider()
                        st.markdown("**Record a balance as of a date**")
                        md = st.date_input("As of", key=f"acctsnapdate{a['id']}")
                        mv = st.number_input("Balance on that date",
                                             value=float(a["balance"]), step=100.0,
                                             key=f"acctsnapval{a['id']}")
                        if st.button("Save balance point", key=f"acctsnapadd{a['id']}"):
                            db.write_snapshot(a["id"], md.isoformat(), mv)
                            st.toast("Saved.", icon="✅")
                            st.rerun()

                        st.divider()
                        if st.button("🗑️ Delete account", key=f"acctdel{a['id']}"):
                            db.delete_account(a["id"])
                            st.rerun()

                # -- per-account balance history (month-end points)
                snaps = db.account_snapshots(a["id"])
                if len(snaps) >= 2:
                    sdf = pd.DataFrame(snaps)
                    sdf["date"] = pd.to_datetime(sdf["date"])
                    st.altair_chart(alt.Chart(sdf).mark_line(point=True,
                                    color="#0F766E").encode(
                        x=alt.X("date:T", title=None),
                        y=alt.Y("balance:Q", title=None, axis=alt.Axis(format="$,.0f")),
                        tooltip=[alt.Tooltip("date:T", title="As of"),
                                 alt.Tooltip("balance:Q", title="Balance",
                                             format="$,.2f")],
                    ), width="stretch")

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
