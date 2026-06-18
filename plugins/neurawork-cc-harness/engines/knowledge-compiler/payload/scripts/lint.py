"""Health checks for the knowledge base: 7 checks, markdown report.

Structural checks are free and instant; the contradiction check uses the LLM.

Usage:
    uv run python scripts/lint.py                    # all checks
    uv run python scripts/lint.py --structural-only  # skip the LLM check
"""

from __future__ import annotations

import argparse
import asyncio

from config import KNOWLEDGE_DIR, REPORTS_DIR, ROOT_DIR, load_cfg, now_iso, today_iso
from utils import (
    count_inbound_links,
    extract_wikilinks,
    file_hash,
    get_article_word_count,
    list_raw_files,
    list_wiki_articles,
    load_state,
    read_all_wiki_content,
    save_state,
    wiki_article_exists,
)


def check_broken_links() -> list[dict]:
    issues = []
    for article in list_wiki_articles():
        rel = article.relative_to(KNOWLEDGE_DIR)
        for link in extract_wikilinks(article.read_text(encoding="utf-8")):
            if link.startswith("daily/"):
                continue
            if not wiki_article_exists(link):
                issues.append({"severity": "error", "check": "broken_link", "file": str(rel),
                               "detail": f"Broken link [[{link}]] — target missing"})
    return issues


def check_orphan_pages() -> list[dict]:
    issues = []
    for article in list_wiki_articles():
        rel = article.relative_to(KNOWLEDGE_DIR)
        target = str(rel).replace(".md", "").replace("\\", "/")
        if count_inbound_links(target) == 0:
            issues.append({"severity": "warning", "check": "orphan_page", "file": str(rel),
                           "detail": f"Orphan: nothing links to [[{target}]]"})
    return issues


def check_orphan_sources() -> list[dict]:
    ingested = load_state().get("ingested", {})
    return [{"severity": "warning", "check": "orphan_source", "file": f"daily/{p.name}",
             "detail": f"Uncompiled daily log: {p.name}"}
            for p in list_raw_files() if p.name not in ingested]


def check_stale_articles() -> list[dict]:
    ingested = load_state().get("ingested", {})
    issues = []
    for log_path in list_raw_files():
        prev = ingested.get(log_path.name)
        if prev and prev.get("hash", "") != file_hash(log_path):
            issues.append({"severity": "warning", "check": "stale_article",
                           "file": f"daily/{log_path.name}",
                           "detail": f"{log_path.name} changed since last compile"})
    return issues


def check_missing_backlinks() -> list[dict]:
    issues = []
    for article in list_wiki_articles():
        rel = article.relative_to(KNOWLEDGE_DIR)
        source = str(rel).replace(".md", "").replace("\\", "/")
        for link in extract_wikilinks(article.read_text(encoding="utf-8")):
            if link.startswith("daily/"):
                continue
            target = KNOWLEDGE_DIR / f"{link}.md"
            if target.exists() and f"[[{source}]]" not in target.read_text(encoding="utf-8"):
                issues.append({"severity": "suggestion", "check": "missing_backlink",
                               "file": str(rel), "auto_fixable": True,
                               "detail": f"[[{source}]] → [[{link}]] but not back"})
    return issues


def check_sparse_articles() -> list[dict]:
    issues = []
    for article in list_wiki_articles():
        wc = get_article_word_count(article)
        if wc < 200:
            issues.append({"severity": "suggestion", "check": "sparse_article",
                           "file": str(article.relative_to(KNOWLEDGE_DIR)),
                           "detail": f"Sparse: {wc} words (min 200)"})
    return issues


async def check_contradictions() -> list[dict]:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    cfg = load_cfg()
    prompt = f"""Review this knowledge base for contradictions or conflicting claims
across articles.

## Knowledge Base

{read_all_wiki_content()}

## Instructions

For each issue, output EXACTLY one line:
CONTRADICTION: [file1] vs [file2] - description
INCONSISTENCY: [file] - description

If none, output exactly: NO_ISSUES. Output nothing else."""

    response = ""
    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                cwd=str(ROOT_DIR),
                allowed_tools=[],
                max_turns=2,
                setting_sources=[],
                strict_mcp_config=True,
                model=(cfg.get("model") or None),
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response += block.text
            elif isinstance(message, ResultMessage):
                pass
    except Exception as e:
        return [{"severity": "error", "check": "contradiction", "file": "(system)",
                 "detail": f"LLM check failed: {e}"}]

    issues = []
    if "NO_ISSUES" not in response:
        for line in response.strip().splitlines():
            line = line.strip()
            if line.startswith(("CONTRADICTION:", "INCONSISTENCY:")):
                issues.append({"severity": "warning", "check": "contradiction",
                               "file": "(cross-article)", "detail": line})
    return issues


def generate_report(all_issues: list[dict]) -> str:
    buckets = {s: [i for i in all_issues if i["severity"] == s]
               for s in ("error", "warning", "suggestion")}
    lines = [f"# Lint Report — {today_iso()}", "",
             f"**Total:** {len(all_issues)} "
             f"(errors {len(buckets['error'])}, warnings {len(buckets['warning'])}, "
             f"suggestions {len(buckets['suggestion'])})", ""]
    for title, sev, marker in [("Errors", "error", "x"), ("Warnings", "warning", "!"),
                               ("Suggestions", "suggestion", "?")]:
        if buckets[sev]:
            lines += [f"## {title}", ""]
            for issue in buckets[sev]:
                fix = " (auto-fixable)" if issue.get("auto_fixable") else ""
                lines.append(f"- **[{marker}]** `{issue['file']}` — {issue['detail']}{fix}")
            lines.append("")
    if not all_issues:
        lines += ["All checks passed.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint the knowledge base")
    parser.add_argument("--structural-only", action="store_true", help="Skip the LLM check")
    args = parser.parse_args()

    all_issues: list[dict] = []
    for name, fn in [("Broken links", check_broken_links), ("Orphan pages", check_orphan_pages),
                     ("Orphan sources", check_orphan_sources), ("Stale articles", check_stale_articles),
                     ("Missing backlinks", check_missing_backlinks),
                     ("Sparse articles", check_sparse_articles)]:
        found = fn()
        all_issues.extend(found)
        print(f"  {name}: {len(found)} issue(s)")

    if not args.structural_only:
        found = asyncio.run(check_contradictions())
        all_issues.extend(found)
        print(f"  Contradictions (LLM): {len(found)} issue(s)")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"lint-{today_iso()}.md"
    report_path.write_text(generate_report(all_issues), encoding="utf-8")
    print(f"\nReport: {report_path}")

    state = load_state()
    state["last_lint"] = now_iso()
    save_state(state)

    errors = sum(1 for i in all_issues if i["severity"] == "error")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
