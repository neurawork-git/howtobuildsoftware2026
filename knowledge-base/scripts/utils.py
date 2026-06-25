"""Stdlib helpers for the knowledge base: state, hashing, slugs, wikilinks.

Also hosts ``should_compile`` — the pure decision behind the SessionStart 6h
compile gate — kept here (no SDK import) so hooks and tests can use it cheaply.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from config import (
    CONCEPTS_DIR,
    CONNECTIONS_DIR,
    DAILY_DIR,
    INDEX_FILE,
    KNOWLEDGE_DIR,
    QA_DIR,
    STATE_FILE,
)


# ── State ─────────────────────────────────────────────────────────────

def load_state() -> dict:
    """Load state.json, or a fresh skeleton if absent/corrupt."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"ingested": {}, "query_count": 0, "last_lint": None, "total_cost": 0.0}


def save_state(state: dict) -> None:
    """Write state.json atomically (tmp + os.replace)."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, STATE_FILE)


# ── Hashing ───────────────────────────────────────────────────────────

def file_hash(path: Path) -> str:
    """First 16 hex chars of a file's SHA-256."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


# ── Slug / naming ─────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Filename-safe lowercase-hyphen slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


# ── Wikilinks ─────────────────────────────────────────────────────────

def extract_wikilinks(content: str) -> list[str]:
    """All ``[[targets]]`` found in markdown content."""
    return re.findall(r"\[\[([^\]]+)\]\]", content)


def wiki_article_exists(link: str) -> bool:
    """Whether a wikilink target resolves to a file under knowledge/."""
    return (KNOWLEDGE_DIR / f"{link}.md").exists()


# ── Reading the base ──────────────────────────────────────────────────

def read_wiki_index() -> str:
    """The index file, or an empty-table stub if it does not exist yet."""
    if INDEX_FILE.exists():
        return INDEX_FILE.read_text(encoding="utf-8")
    return (
        "# Knowledge Base Index\n\n"
        "| Article | Summary | Compiled From | Updated |\n"
        "|---------|---------|---------------|---------|"
    )


def list_wiki_articles() -> list[Path]:
    """Every article file across concepts/, connections/, qa/."""
    articles: list[Path] = []
    for subdir in (CONCEPTS_DIR, CONNECTIONS_DIR, QA_DIR):
        if subdir.exists():
            articles.extend(sorted(subdir.glob("*.md")))
    return articles


def read_all_wiki_content() -> str:
    """Index + every article concatenated for an LLM context window."""
    parts = [f"## INDEX\n\n{read_wiki_index()}"]
    for article in list_wiki_articles():
        rel = article.relative_to(KNOWLEDGE_DIR)
        parts.append(f"## {rel}\n\n{article.read_text(encoding='utf-8')}")
    return "\n\n---\n\n".join(parts)


def list_raw_files() -> list[Path]:
    """Every daily log file, sorted."""
    if not DAILY_DIR.exists():
        return []
    return sorted(DAILY_DIR.glob("*.md"))


# ── Index / link analysis ─────────────────────────────────────────────

def count_inbound_links(target: str, exclude_file: Path | None = None) -> int:
    """How many articles contain ``[[target]]``."""
    count = 0
    for article in list_wiki_articles():
        if article == exclude_file:
            continue
        if f"[[{target}]]" in article.read_text(encoding="utf-8"):
            count += 1
    return count


def get_article_word_count(path: Path) -> int:
    """Word count of an article body, excluding YAML frontmatter."""
    content = Path(path).read_text(encoding="utf-8")
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:]
    return len(content.split())


def build_index_entry(rel_path: str, summary: str, sources: str, updated: str) -> str:
    """A single ``index.md`` table row."""
    link = rel_path[:-3] if rel_path.endswith(".md") else rel_path
    return f"| [[{link}]] | {summary} | {sources} | {updated} |"


# ── Compile trigger gate (pure) ───────────────────────────────────────

def should_compile(
    now: float,
    last_ts: float | None,
    age_hours: float,
    has_new_daily: bool,
    in_wt: bool,
    lock_fresh: bool,
) -> bool:
    """Whether SessionStart should spawn a background compile.

    Eligible only when there is new daily content, we are NOT in a worktree, no
    fresh lock is holding, and the last compile is at least ``age_hours`` old
    (a missing last-compile stamp counts as infinitely old).
    """
    if in_wt or lock_fresh or not has_new_daily:
        return False
    if last_ts is None:
        return True
    return (now - last_ts) >= age_hours * 3600
