"""Merchant-keyword derivation and the shared AI-categorization collapser.

Both import-time categorization and the Categories-tab "auto-categorize" button
go through `classify_descriptions`, so a merchant is always classified the same
way and only once per run.
"""

import re


def keyword_from_desc(desc):
    """Derive a short, reusable keyword from a transaction description so the
    same merchant auto-categorizes next time.

    Statement descriptions fuse a merchant with per-transaction noise: order ids
    ('Amazon.com*NN6BD0FE3'), store/phone numbers, and a trailing city/state.
    We keep the leading merchant tokens and drop that noise, while keeping the
    result a literal substring of the original (categorize() matches by
    substring), so it re-matches next month."""
    head = (desc or "").split(":")[0].lower().strip()
    out = []
    for tok in head.split():
        if "*" in tok:
            pre, post = tok.split("*", 1)
            # A '*' followed by an id: keep the merchant text around it and stop,
            # since the id comes next in the original and breaks substring-ness.
            # 'amazon.com*nn6bd0fe3' -> 'amazon.com'    (post is pure id)
            # 'wf' + '*wayfair4641067361' -> 'wf *wayfair' (post leads with name)
            if any(ch.isdigit() for ch in post):
                if not any(ch.isdigit() for ch in pre):
                    lead = re.match(r"[a-z]+", post)
                    name = lead.group(0) if lead else ""
                    piece = pre + "*" + name if len(name) >= 4 else pre
                    if piece:
                        out.append(piece)
                break
        # noisy token (store #, phone, zip, date, amount): skip it while it's
        # leading junk, but stop once we've started a contiguous merchant run.
        if any(ch.isdigit() for ch in tok):
            if out:
                break
            continue
        out.append(tok)
        if len(out) >= 3:
            break
    token = " ".join(out).strip(" -*")
    return token if len(token) >= 3 else head[:30]


def classify_descriptions(descriptions, category_names, classify_fn, progress_cb=None):
    """Map each description -> category, classifying each MERCHANT once.

    Statement descriptions vary per transaction (order ids, store numbers), so
    naively classifying every distinct string wastes calls and can give one
    merchant different categories. We collapse descriptions to merchant keys
    (keyword_from_desc), ask `classify_fn` about one representative per merchant,
    then expand the answer back to every description sharing that key.

    `classify_fn(representatives, category_names, progress_cb=...) -> {rep: cat}`
    is injected — the local-LLM agent in the app, a stub in tests.

    Returns {description: category}; merchants the model can't place map to
    'Uncategorized'.
    """
    key_to_rep = {}     # merchant_key -> representative description
    desc_to_key = {}    # description -> merchant_key
    for d in descriptions:
        if not d or not d.strip():
            continue
        k = keyword_from_desc(d)
        key_to_rep.setdefault(k, d)
        desc_to_key[d] = k
    if not key_to_rep:
        return {}
    reps = sorted(set(key_to_rep.values()))
    mapping = classify_fn(reps, category_names, progress_cb=progress_cb)
    key_to_cat = {k: mapping.get(rep, "Uncategorized") for k, rep in key_to_rep.items()}
    return {d: key_to_cat.get(k, "Uncategorized") for d, k in desc_to_key.items()}
