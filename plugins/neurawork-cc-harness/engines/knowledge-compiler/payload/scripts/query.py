"""Answer a question from the knowledge base via index-guided retrieval (no RAG).

The LLM reads the index, picks the relevant articles, and synthesizes an answer.
With ``--file-back`` it also files the answer as a ``knowledge/qa/`` article.

Usage:
    uv run python scripts/query.py "How do we handle auth redirects?"
    uv run python scripts/query.py "What is our error strategy?" --file-back
"""

from __future__ import annotations

import argparse
import asyncio

from config import KNOWLEDGE_DIR, QA_DIR, ROOT_DIR, load_cfg, now_iso
from utils import load_state, read_all_wiki_content, save_state


async def run_query(question: str, file_back: bool = False) -> str:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        query,
    )

    cfg = load_cfg()
    wiki_content = read_all_wiki_content()

    tools = ["Read", "Glob", "Grep"]
    file_back_block = ""
    if file_back:
        tools += ["Write", "Edit"]
        stamp = now_iso()
        file_back_block = f"""

## File Back

After answering:
1. Write a Q&A article under {QA_DIR}/ named with a slug of the question.
2. Use the Q&A format from the schema (frontmatter: title, question, consulted, filed).
3. Add a row for it to {KNOWLEDGE_DIR / 'index.md'}.
4. Append to {KNOWLEDGE_DIR / 'log.md'} a dated entry ({stamp[:10]}) noting the
   question and the articles consulted."""

    prompt = f"""You are the knowledge base query engine. Answer the question using only
the base below.

1. Read the INDEX first — every article with a one-line summary.
2. Pick 3-10 relevant articles and read them in full.
3. Synthesize a clear answer and cite sources with [[wikilinks]].
4. If the base lacks the answer, say so honestly — do not invent.

## Knowledge Base

{wiki_content}

## Question

{question}
{file_back_block}"""

    answer = ""
    cost = 0.0
    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                cwd=str(ROOT_DIR),
                system_prompt={"type": "preset", "preset": "claude_code"},
                allowed_tools=tools,
                permission_mode="acceptEdits",
                max_turns=15,
                setting_sources=[],
                strict_mcp_config=True,
                model=(cfg.get("model") or None),
            ),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        answer += block.text
            elif isinstance(message, ResultMessage):
                cost = message.total_cost_usd or 0.0
    except Exception as e:
        return f"Error querying knowledge base: {e}"

    state = load_state()
    state["query_count"] = state.get("query_count", 0) + 1
    state["total_cost"] = state.get("total_cost", 0.0) + cost
    save_state(state)
    return answer


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the knowledge base")
    parser.add_argument("question", help="The question to ask")
    parser.add_argument("--file-back", action="store_true", help="File the answer as a Q&A article")
    args = parser.parse_args()

    print(f"Question: {args.question}\n" + "-" * 60)
    print(asyncio.run(run_query(args.question, file_back=args.file_back)))


if __name__ == "__main__":
    main()
