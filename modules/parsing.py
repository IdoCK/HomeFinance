"""Keyword categorization shared by every import path.

Transactions flow through a common schema (one dict per row):
    date         ISO 'YYYY-MM-DD'
    description  free text (merchant / item)
    amount       float, negative = spend, positive = income
    category     auto-assigned from the person's category keyword rules
    source       'amazon' | 'credit_card' | 'bank' | 'generic'
    included     bool, False = excluded from all calculations

Actual file parsing lives in the format registry (modules/formats.py +
modules/agent_parser.py); this module only holds the keyword categorizer they
all call.
"""


def categorize(description, category_rules):
    """category_rules: list of (name, [keywords]). First keyword match wins."""
    text = (description or "").lower()
    for name, keywords in category_rules:
        for kw in keywords:
            if kw and kw.lower().strip() in text:
                return name
    return "Uncategorized"
