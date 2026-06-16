"""AI-generated insights with a privacy/anonymization layer.

What leaves the machine: ONLY aggregated numbers — category totals, monthly
spend/savings, month-over-month percentages, and goal progress percentages.

What never leaves: raw transactions, merchant names, item descriptions, account
numbers, dates of individual purchases, or either person's real name. The two
people are sent as generic labels ("Person A" / "Person B" / "Household").

The API key is read from the ANTHROPIC_API_KEY environment variable so it is
never written into the code or the database.
"""

import os
import json

MODEL = "claude-opus-4-8"  # adjust to whatever model you have access to


def build_anonymized_summary(label, transactions, goals, analytics):
    """Turn one person's (or the household's) data into an aggregate-only dict.

    `analytics` is the analytics module, passed in to avoid a circular import.
    """
    cat_totals = analytics.category_totals(transactions)
    savings = analytics.monthly_savings(transactions)
    mom = analytics.month_over_month_change(transactions)
    progress = analytics.goal_progress(goals)

    savings_summary = {}
    if not savings.empty:
        savings_summary = {
            "months_tracked": len(savings),
            "avg_monthly_income": round(float(savings["income"].mean()), 2),
            "avg_monthly_spend": round(float(savings["spend"].mean()), 2),
            "avg_monthly_savings": round(float(savings["savings"].mean()), 2),
            "latest_month_savings": round(float(savings["savings"].iloc[-1]), 2),
        }

    # Goals carry only name + progress numbers, never notes (notes may be personal).
    goal_summary = [
        {
            "name": g["name"],
            "horizon": g["horizon"],
            "percent_complete": g["percent"],
            "monthly_needed_to_hit_target": (
                round(g["monthly_needed"], 2) if g["monthly_needed"] is not None else None
            ),
        }
        for g in progress
    ]

    return {
        "who": label,  # generic label only
        "spending_by_category": {k: round(v, 2) for k, v in cat_totals.items()},
        "month_over_month_pct_change": {
            k: (round(v, 1) if v is not None else None) for k, v in mom.items()
        },
        "savings": savings_summary,
        "goals": goal_summary,
    }


SYSTEM_PROMPT = (
    "You are a personal-finance coach. You will receive ANONYMIZED, aggregated "
    "financial summaries for members of a household. There are no merchant names "
    "or raw transactions. Give concrete, encouraging, specific insights: where "
    "spending is trending, how each savings goal is progressing, and 3-5 "
    "actionable tips to reach the goals faster and cut costs. Be specific with "
    "the numbers provided. Keep it concise and skimmable."
)


def get_insights(summaries):
    """summaries: list of anonymized summary dicts. Returns insight text.

    Requires the `anthropic` package and ANTHROPIC_API_KEY env var.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return (
            "⚠️ No ANTHROPIC_API_KEY set. Set it in your environment to enable AI "
            "insights. (Your data stays local until you do — and even then only the "
            "anonymized aggregates below are sent.)\n\n"
            "Preview of what *would* be sent:\n```json\n"
            + json.dumps(summaries, indent=2)
            + "\n```"
        )

    try:
        import anthropic
    except ImportError:
        return "The `anthropic` package isn't installed. Run: pip install anthropic"

    client = anthropic.Anthropic(api_key=api_key)
    user_content = (
        "Here are the anonymized household finance summaries. Provide insights and "
        "tips:\n\n```json\n" + json.dumps(summaries, indent=2) + "\n```"
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def preview_payload(summaries):
    """Exactly what would be transmitted — show this to the user for transparency."""
    return json.dumps(summaries, indent=2)
