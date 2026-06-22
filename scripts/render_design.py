"""Render the UI-rewrite design specs into one self-contained DESIGN.html.

Stdlib only (no markdown dependency). Handles exactly the markdown our design
docs use: ATX headings, fenced code, tables, ordered/unordered lists, blockquote,
horizontal rules, bold, inline code, and paragraphs. Output is themed in the
Frosted Ledger palette so the design book reflects the design it describes.
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "docs" / "superpowers" / "specs"

# The master "init design" first, then each page-level addendum in build order.
DOCS = [
    ("The initial design", "2026-06-18-finance-ui-rewrite-design.md"),
    ("Transactions page", "2026-06-19-transactions-page-design.md"),
    ("Budgets page", "2026-06-19-budgets-page-design.md"),
    ("Goals page", "2026-06-19-goals-page-design.md"),
    ("Net Worth page", "2026-06-19-networth-page-design.md"),
    ("Recurring page", "2026-06-19-recurring-page-design.md"),
    ("Settings page", "2026-06-19-settings-page-design.md"),
    ("AI Insights page", "2026-06-19-insights-page-design.md"),
    ("Import wizard", "2026-06-19-import-page-design.md"),
]


def inline(text):
    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return text


def render(md):
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            i += 1
            block = []
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(html.escape(lines[i]))
                i += 1
            out.append("<pre><code>" + "\n".join(block) + "</code></pre>")
            i += 1
            continue
        if line.startswith("|") and "|" in line[1:]:
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i]); i += 1
            cells = [[c.strip() for c in r.strip("|").split("|")] for r in rows]
            body = [r for r in cells if not all(set(c) <= set("-: ") for c in r)]
            head, rest = body[0], body[1:]
            t = ["<table><thead><tr>"] + [f"<th>{inline(c)}</th>" for c in head] + ["</tr></thead><tbody>"]
            for r in rest:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            continue
        m = re.match(r"(#{1,4})\s+(.*)", line)
        if m:
            lvl = len(m.group(1)); out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>"); i += 1; continue
        if re.match(r"\s*[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"\s*[-*]\s+", lines[i]):
                items.append("<li>" + inline(re.sub(r"\s*[-*]\s+", "", lines[i], count=1)) + "</li>"); i += 1
            out.append("<ul>" + "".join(items) + "</ul>"); continue
        if re.match(r"\s*\d+\.\s+", line):
            items = []
            while i < len(lines) and re.match(r"\s*\d+\.\s+", lines[i]):
                items.append("<li>" + inline(re.sub(r"\s*\d+\.\s+", "", lines[i], count=1)) + "</li>"); i += 1
            out.append("<ol>" + "".join(items) + "</ol>"); continue
        if line.startswith(">"):
            out.append("<blockquote>" + inline(line.lstrip("> ")) + "</blockquote>"); i += 1; continue
        if line.strip() in ("---", "***", "___"):
            out.append("<hr>"); i += 1; continue
        if line.strip() == "":
            i += 1; continue
        para = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"(#{1,4}\s|```|\||\s*[-*]\s|\s*\d+\.\s|>)", lines[i]):
            para.append(lines[i]); i += 1
        out.append("<p>" + inline(" ".join(para)) + "</p>")
    return "\n".join(out)


CSS = """
:root{--canvas:#E5E6EA;--card:#fff;--line:#ECEDF0;--ink:#16181D;--muted:#8A8F98;
--you:#3B82F6;--spouse:#EC4899;--showpiece:linear-gradient(120deg,#FDBA74,#F472B6,#A855F7,#3B82F6);}
*{box-sizing:border-box}
body{margin:0;background:var(--canvas);color:var(--ink);
font-family:"Plus Jakarta Sans",system-ui,-apple-system,Segoe UI,sans-serif;line-height:1.6;}
.wrap{max-width:880px;margin:0 auto;padding:48px 24px 96px;}
.masthead{background:var(--showpiece);color:#fff;border-radius:24px;padding:40px 32px;margin-bottom:32px;
box-shadow:0 24px 70px -30px rgba(168,85,247,.6);}
.masthead h1{margin:0 0 8px;font-size:38px;font-weight:800;letter-spacing:-.03em;}
.masthead p{margin:0;opacity:.92;max-width:620px;}
nav.toc{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px 24px;margin-bottom:32px;}
nav.toc strong{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:10px;}
nav.toc a{display:inline-block;margin:3px 14px 3px 0;color:var(--you);text-decoration:none;font-weight:600;font-size:14px;}
section.doc{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:8px 32px 28px;margin-bottom:24px;}
h1,h2,h3,h4{letter-spacing:-.02em;line-height:1.25;}
h1{font-size:28px;border-bottom:2px solid var(--line);padding-bottom:8px;margin-top:28px;}
h2{font-size:21px;margin-top:28px;}
h3{font-size:17px;color:#33363d;}
h4{font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);}
code{background:#F2F3F5;padding:1px 6px;border-radius:6px;font-size:.88em;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;}
pre{background:#16181D;color:#E8EAED;border-radius:14px;padding:16px 18px;overflow-x:auto;}
pre code{background:none;color:inherit;padding:0;font-size:13px;line-height:1.5;}
table{border-collapse:collapse;width:100%;margin:16px 0;font-size:14px;}
th,td{border:1px solid var(--line);padding:8px 11px;text-align:left;vertical-align:top;}
th{background:#FAFBFC;font-weight:700;}
blockquote{border-left:3px solid var(--you);margin:14px 0;padding:6px 16px;color:var(--muted);background:#FAFBFC;border-radius:0 10px 10px 0;}
hr{border:none;border-top:1px solid var(--line);margin:24px 0;}
strong{font-weight:700;}
.persona-key{display:flex;gap:18px;margin-top:18px;font-size:13px;}
.dot{display:inline-block;width:11px;height:11px;border-radius:999px;vertical-align:middle;margin-right:6px;}
"""


def main():
    parts = [f"<!doctype html><html lang=en><head><meta charset=utf-8>",
             "<meta name=viewport content='width=device-width,initial-scale=1'>",
             "<title>HomeFinance — Frosted Ledger Design</title>",
             f"<style>{CSS}</style></head><body><div class=wrap>"]
    parts.append(
        "<div class=masthead><h1>Frosted Ledger</h1>"
        "<p>The design book for the HomeFinance UI rewrite — the initial design that "
        "drove the build, plus every page-level addendum. A soft, airy, two-person "
        "household ledger: <strong>You</strong>, <strong>Spouse</strong>, and "
        "<strong>Joint</strong>.</p>"
        "<div class=persona-key>"
        "<span><span class=dot style='background:#3B82F6'></span>You</span>"
        "<span><span class=dot style='background:#EC4899'></span>Spouse</span>"
        "<span><span class=dot style='background:linear-gradient(90deg,#3B82F6,#EC4899)'></span>Joint</span>"
        "</div></div>")

    present = [(t, SPECS / f) for t, f in DOCS if (SPECS / f).exists()]
    parts.append("<nav class=toc><strong>Contents</strong>")
    for idx, (title, _) in enumerate(present):
        parts.append(f"<a href='#d{idx}'>{html.escape(title)}</a>")
    parts.append("</nav>")

    for idx, (title, path) in enumerate(present):
        parts.append(f"<section class=doc id='d{idx}'>")
        parts.append(render(path.read_text(encoding="utf-8")))
        parts.append("</section>")

    parts.append("</div></body></html>")
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "DESIGN.html"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {out}  ({len(present)} design docs)")


if __name__ == "__main__":
    main()
