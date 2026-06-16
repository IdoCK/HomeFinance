"""Household Finance Dashboard — local, two-person, AI-assisted.

Run with:  streamlit run app.py
All data is stored locally in data/finance.db. Only anonymized aggregates are
sent for AI insights, and only when you click the insights button.
"""

import json
import math
import hashlib
from datetime import datetime

import streamlit as st
import pandas as pd

from modules import database as db
from modules import parsing
from modules import agent_parser
from modules import formats
from modules import analytics
from modules import ai_insights

st.set_page_config(page_title="Household Finance", page_icon="💰", layout="wide")
db.init_db()

# ---------------------------------------------------------------- sidebar / view
people = db.list_people()
name_to_id = {p["name"]: p["id"] for p in people}
id_to_name = {p["id"]: p["name"] for p in people}

st.sidebar.title("💰 Household Finance")
view = st.sidebar.radio(
    "View",
    [id_to_name[people[0]["id"]], id_to_name[people[1]["id"]], "Household"],
)
st.sidebar.caption("Local-only. Your data never leaves this machine except "
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


def _category_rules(person_id):
    return [(c["name"], (c["keywords"] or "").split(","))
            for c in db.get_categories(person_id)]


def _category_names(person_id):
    return [c["name"] for c in db.get_categories(person_id)]


def _ai_categorize_uncategorized(rows, person_id, progress_cb=None):
    """Fill still-Uncategorized rows with the local LLM (mutates rows in place).
    Returns (n_filled, warning_or_None)."""
    names = _category_names(person_id)
    if not names or not rows:
        return 0, None
    unknown = sorted({
        r["description"] for r in rows
        if r["category"] == "Uncategorized" and r["description"].strip()
    })
    if not unknown:
        return 0, None
    try:
        mapping = agent_parser.categorize_with_agent(
            unknown, names, progress_cb=progress_cb)
    except Exception as e:
        return 0, f"AI categorization unavailable ({e})"
    filled = 0
    for r in rows:
        if r["category"] == "Uncategorized":
            new = mapping.get(r["description"], "Uncategorized")
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
    rows, skipped = formats.parse_with_format(
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
        # Snapshot of categories as first parsed, so we can later tell which rows
        # the user re-categorized by hand (used to learn keyword rules).
        "original_cats": [r["category"] for r in rows],
    }


import re as _re


def _keyword_from_desc(desc):
    """Derive a short, reusable keyword from a transaction description so the
    same merchant auto-categorizes next time. Takes the leading words before any
    ':' (which usually carries the merchant), lowercased."""
    head = (desc or "").split(":")[0]
    words = _re.findall(r"[A-Za-z]+", head)
    token = " ".join(words[:3]).lower().strip()
    return token or (desc or "").strip().lower()[:30]


def _learn_keyword(person_id, category, desc):
    """Append a description-derived keyword to a category (deduped)."""
    token = _keyword_from_desc(desc)
    if not token or category == "Uncategorized":
        return
    cats = {c["name"]: c for c in db.get_categories(person_id)}
    c = cats.get(category)
    if not c:
        return
    kws = [k.strip() for k in (c["keywords"] or "").split(",") if k.strip()]
    if token not in [k.lower() for k in kws]:
        kws.append(token)
        db.upsert_category(person_id, category, ",".join(kws))


def _style_amounts(df):
    """Green background for money in (positive), red for money out (negative)."""
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
    return df.style.apply(colorize, subset=["Amount"]).format({"Amount": "{:,.2f}"})


pid = person_id_for_view(view)
txns = transactions_for_view(view)
goals = goals_for_view(view)

st.title(f"{view} — Overview")

tab_dash, tab_import, tab_cats, tab_goals, tab_ai = st.tabs(
    ["📊 Dashboard", "📥 Import", "🏷️ Categories", "🎯 Goals", "🤖 AI Insights"]
)

# ---------------------------------------------------------------- DASHBOARD
with tab_dash:
    if not txns:
        st.info("No transactions yet. Add some in the **Import** tab.")
    else:
        savings = analytics.monthly_savings(txns)
        if not savings.empty:
            latest = savings.iloc[-1]
            c1, c2, c3 = st.columns(3)
            c1.metric("Latest month income", f"${latest['income']:,.0f}")
            c2.metric("Latest month spend", f"${latest['spend']:,.0f}")
            c3.metric("Latest month savings", f"${latest['savings']:,.0f}")

        st.subheader("Spending by category over time")
        pivot = analytics.spending_by_category_over_time(txns)
        if not pivot.empty:
            st.area_chart(pivot)
        else:
            st.caption("No spending (negative-amount) transactions yet.")

        st.subheader("Monthly savings")
        if not savings.empty:
            st.bar_chart(savings["savings"])

        col_sp, col_in = st.columns(2)
        with col_sp:
            st.subheader("Spending by category")
            totals = analytics.category_totals(txns)
            if totals:
                st.bar_chart(pd.Series(totals, name="spend"))
            else:
                st.caption("No spending to categorize.")
        with col_in:
            st.subheader("Income by category")
            inc = analytics.income_by_category(txns)
            if inc:
                st.bar_chart(pd.Series(inc, name="income"))
            else:
                st.caption("No income to categorize.")

        # ---- Imported files + duplicate cleanup
        st.divider()
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
                if c3.button("🗑️ Delete", key=f"delimp::{imp['person_id']}::{imp['file_hash']}",
                             help="Remove this file's transactions and its import record"):
                    n = db.delete_import(imp["person_id"], imp["file_hash"])
                    st.toast(f"Deleted {n} transaction(s) from {imp['filename']}.", icon="🗑️")
                    st.rerun()
        else:
            st.caption("No tracked imported files yet. Files you import from now on "
                       "appear here and can be deleted individually.")

        # Legacy cleanup: rows imported before file-tracking (no file_hash) can't
        # be tied to a file above and may contain whole-file duplicates from
        # importing the same file twice. Safest fix: delete them and re-import
        # once (now tracked + duplicate-blocked). We avoid auto-merging "exact
        # duplicates" because a statement can legitimately repeat a row.
        unt_people = list(name_to_id.values()) if view == "Household" else [pid]
        unt_total = sum(db.count_untracked_transactions(p) for p in unt_people)
        if unt_total:
            st.warning(
                f"**{unt_total}** transaction(s) were imported before file-tracking "
                "and aren't tied to any file above — these may include duplicates "
                "from importing a file more than once."
            )
            st.caption("Recommended: delete them here, then re-import the file(s) "
                       "in the 📥 Import tab. Re-imports are tracked and can't be "
                       "duplicated, and will then appear in the list above.")
            if st.button(f"🧹 Delete {unt_total} untracked transaction(s)"):
                removed = sum(db.clear_untracked_transactions(p) for p in unt_people)
                st.toast(f"Deleted {removed} untracked transaction(s). Re-import for "
                         "a clean, tracked copy.", icon="🧹")
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

        st.write("Upload CSV or Excel exports. Each file is matched against a "
                 "known **format** in `csv_formats.md` and parsed with its rules "
                 "— consistent every time. Known formats parse offline; the "
                 "local AI is used only to infer categories and to learn new "
                 "file types. Review the highlighted preview, adjust any "
                 "categories, then import.")
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

            df = pd.DataFrame(prev["rows"])[["date", "description", "amount", "category"]]
            df.columns = ["Date", "Description", "Amount", "Category"]

            options = sorted(set(_category_names(pid)) | {"Uncategorized"}
                             | set(df["Category"]))
            st.caption("Edit any category in the table.  🟢 money in · 🔴 money out")
            # One table: red/green amount cells (Styler) AND an editable Category
            # dropdown. The colors are display-only; Category stays editable.
            edited = st.data_editor(
                _style_amounts(df), use_container_width=True, hide_index=True,
                key=f"edit::{cache_key}",
                disabled=["Date", "Description", "Amount"],
                column_config={
                    "Category": st.column_config.SelectboxColumn(
                        "Category", options=options,
                        help="Inferred from the description — change if wrong."),
                },
            )

            # Persist edits back into the cached preview so they survive reruns
            # and tab switches (Streamlit re-executes every tab on each rerun).
            for row, cat in zip(prev["rows"], edited["Category"].tolist()):
                row["category"] = cat

            net = edited["Amount"].sum()
            spent = edited.loc[edited["Amount"] < 0, "Amount"].sum()
            recv = edited.loc[edited["Amount"] > 0, "Amount"].sum()
            m1, m2, m3 = st.columns(3)
            m1.metric("Money in", f"${recv:,.2f}")
            m2.metric("Money out", f"${-spent:,.2f}")
            m3.metric("Net", f"${net:,.2f}")

            # On-demand AI categorization. Kept separate from parsing so the
            # upload stays responsive (the LLM call blocks the whole session).
            # Define your categories first, then run this. Operates on the
            # current edits without re-parsing.
            n_uncat = int((edited["Category"] == "Uncategorized").sum())
            n_unique = len({
                r["description"] for r in prev["rows"]
                if r["category"] == "Uncategorized" and r["description"].strip()
            })
            n_batches = max(1, math.ceil(n_unique / 20))
            if n_uncat:
                st.caption(
                    f"{n_unique} unique merchant description(s) to classify "
                    f"({n_uncat} rows) · typically 10–40 s with the local model. "
                    "Define categories in the 🏷️ Categories tab first."
                )
            cols = st.columns([1, 1])
            if cols[1].button(
                f"🤖 Auto-categorize with AI ({n_uncat} left)",
                key=f"retry_ai::{cache_key}", disabled=not ok or n_uncat == 0,
                help="Runs the local model now (may take a while); the app is "
                     "busy during this call.",
            ):
                before = [r["category"] for r in prev["rows"]]
                with st.status("Running AI categorization…", expanded=True) as ai_status:
                    ai_bar = st.progress(
                        0, text=f"0 / {n_unique} descriptions · batch 1 of {n_batches}")

                    def _ai_cb(done, total, _bar=ai_bar, _nb=n_batches):
                        pct = (done / total) if total else 0
                        bn = min(_nb, math.ceil(done / 20)) if done else 1
                        _bar.progress(
                            pct,
                            text=f"{done} / {total} descriptions  ({pct:.0%}) · "
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

            if cols[0].button(f"✅ Import {len(edited)} transactions", key=f"imp::{cache_key}"):
                final_cats = edited["Category"].tolist()
                original = prev.get("original_cats", final_cats)
                rows = []
                learned = 0
                for i, (_, r) in enumerate(edited.iterrows()):
                    cat = final_cats[i]
                    # Learn a keyword for rows the user hand-recategorized, so
                    # the same merchant auto-tags next time.
                    if i < len(original) and cat != original[i] and cat != "Uncategorized":
                        _learn_keyword(pid, cat, r["Description"])
                        learned += 1
                    rows.append({
                        "date": r["Date"], "description": r["Description"],
                        "amount": float(r["Amount"]), "category": cat,
                        "source": prev["source"],
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
                    msg += f" Learned {learned} new keyword rule(s) from your edits."
                st.session_state["import_done_msg"] = msg
                st.rerun()

        st.divider()
        if txns and st.button("⚠️ Clear all of this person's transactions"):
            db.clear_transactions(pid)
            st.rerun()

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
        st.caption(f"{len(unknown)} uncategorized merchant(s). The local AI agent "
                   "recognizes common merchants (Chewy → Dog, Chipotle → Eating "
                   "Out) by name — runs on-machine, nothing sent to the web.")
        if unknown and st.button("Auto-categorize uncategorized"):
            cat_names = [c["name"] for c in db.get_categories(pid)]
            if not cat_names:
                st.warning("Define at least one category first.")
            else:
                try:
                    with st.spinner("Local agent categorizing…"):
                        mapping = agent_parser.categorize_with_agent(unknown, cat_names)
                        db.apply_category_mapping(pid, mapping)
                    st.success(f"Categorized {len(mapping)} merchant(s).")
                    st.rerun()
                except Exception as e:
                    st.error(f"Auto-categorize failed: {e}")

# ---------------------------------------------------------------- GOALS
with tab_goals:
    st.write("Track short- and long-term goals. Shared goals show in the "
             "Household view.")
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

    for g in analytics.goal_progress(goals_for_view(view)):
        st.markdown(f"### {g['name']}  ·  _{g['horizon']}-term_")
        st.progress(min(g["percent"] / 100, 1.0),
                    text=f"{g['percent']:.0f}% — ${g['saved_amount']:,.0f} of ${g['target_amount']:,.0f}")
        if g["monthly_needed"] is not None:
            st.caption(f"Need ~${g['monthly_needed']:,.0f}/month to hit the target date.")
        c1, c2 = st.columns([3, 1])
        new_saved = c1.number_input(
            "Update saved amount", min_value=0.0, value=float(g["saved_amount"]),
            step=100.0, key=f"save{g['id']}",
        )
        if c1.button("Update", key=f"upd{g['id']}"):
            db.update_goal_saved(g["id"], new_saved)
            st.rerun()
        if c2.button("Delete", key=f"delgoal{g['id']}"):
            db.delete_goal(g["id"])
            st.rerun()

# ---------------------------------------------------------------- AI INSIGHTS
with tab_ai:
    st.write("Generate AI insights from **anonymized aggregates only**. "
             "No merchants, raw transactions, names, or notes are sent.")

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

    if st.button("Generate insights"):
        with st.spinner("Thinking..."):
            st.markdown(ai_insights.get_insights(summaries))
