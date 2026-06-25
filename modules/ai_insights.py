"""AI-generated insights with a privacy/anonymization layer.

What leaves the machine: ONLY aggregated numbers — category totals, monthly
spend/savings, month-over-month percentages, and goal progress percentages.

What never leaves: raw transactions, merchant names, item descriptions, account
numbers, dates of individual purchases, or either person's real name. The two
people are sent as generic labels ("Person A" / "Person B" / "Household").

Insights run through the locally-installed Claude Code CLI in headless mode
(`claude -p ...`), which bills against the machine's Claude subscription. No
Anthropic API key is involved. The binary name is configurable via the
CLAUDE_BIN env var (default "claude").
"""

import os
import json
import shutil
import subprocess

CLI_TIMEOUT = 120  # seconds


def _claude_bin():
    """Configurable binary name; read at call time so env changes are honored."""
    return os.environ.get("CLAUDE_BIN", "claude")


def ai_available():
    """Whether the Claude Code CLI is resolvable on this machine."""
    return shutil.which(_claude_bin()) is not None


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


_INSTALL_HINT = (
    "Claude Code isn't installed (or isn't on PATH). Install Claude Code to enable "
    "live insights — it runs on your Claude subscription, no API key needed. "
    "See https://docs.claude.com/claude-code"
)


def get_insights(summaries):
    """summaries: list of anonymized summary dicts. Returns insight text.

    Runs the locally-installed Claude Code CLI in headless mode. The CLI has no
    separate system-prompt arg, so the coaching instructions are prepended into a
    single prompt string alongside the anonymized aggregates.
    """
    binary = _claude_bin()
    resolved = shutil.which(binary)
    if resolved is None:
        return _INSTALL_HINT

    prompt = (
        SYSTEM_PROMPT
        + "\n\nHere are the anonymized household finance summaries. Provide insights "
        "and tips:\n\n```json\n"
        + json.dumps(summaries, indent=2)
        + "\n```"
    )

    try:
        result = subprocess.run(
            [binary, "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT,
        )
    except FileNotFoundError:
        return _INSTALL_HINT
    except subprocess.TimeoutExpired:
        return (
            f"⚠️ Claude Code timed out after {CLI_TIMEOUT}s. Try again, or check that "
            "the CLI is responsive."
        )

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        return f"⚠️ Claude Code exited with an error:\n{stderr}"

    return result.stdout.strip()


def preview_payload(summaries):
    """Exactly what would be transmitted — show this to the user for transparency."""
    return json.dumps(summaries, indent=2)
