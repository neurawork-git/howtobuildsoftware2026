"""PostToolUse hook — check a written PRD or PRP plan against the recorded stack.

Fires after every tool call; fast-exits unless the tool was a Write/Edit to a live
PRD (``.claude/PRPs/prds/*.prd.md``) or plan (``.claude/PRPs/plans/**/*.plan.md``).
For such a write it runs the deterministic ``gate_lib`` precheck inline (<1s, no API
key, no network): which catalog components the document names, and what
``stack.json`` records about each — this product's choice, a contradiction of one, a
scoped-out capability, or a capability still undecided. The summary is emitted as
additionalContext, and the deep LLM ``validate.py`` is spawned detached only when the
document's content actually changed and the stack carries choices to enforce.

It runs beside ``compliance-base``'s ``co-post-tooluse.py`` and never interacts with
it: different install dir, different reports dir, a different question (component
identity, not constraint coverage).

``validate_mode: {"plan": "block"}`` additionally returns a block decision when the
document names an off-stack component. An undecided capability is pending work, never
a violation, and never blocks.

The exact PostToolUse payload field names are read defensively; on any unexpected
shape the hook no-ops rather than crashing the session.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

KDIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KDIR))                       # _shared
sys.path.insert(0, str(KDIR / "scripts"))           # config, gate_lib, rank_lib

from _shared.gitctx import checkout_roots
from _shared.hookio import child_env, read_hook_input, recursion_guard

recursion_guard()

# Resolved through the two sys.path entries above, not as a package: Claude Code invokes
# a hook by path, so `scripts/` is only on the path at runtime. Type checkers cannot
# follow that, hence the three targeted ignores — a genuinely missing import elsewhere
# in this file still fails.
import gate_lib  # type: ignore[reportMissingImports]
import scope_lib  # type: ignore[reportMissingImports]
from _shared.gitctx import in_worktree, main_checkout_root
from config import gate_mode, load_cfg, now_iso  # type: ignore[reportMissingImports]

WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}


def effective_root() -> Path:
    """Stack install dir to use — the main checkout's when inside a worktree.

    Reports and the spawn ledger must survive ``git worktree remove``, so they are
    written next to the main checkout exactly as ``compliance-base`` does with
    ``COMPLIANCE_ROOT``.
    """
    if in_worktree(str(KDIR)):
        main_root = main_checkout_root(str(KDIR))
        if main_root is not None:
            return main_root / KDIR.name
    return KDIR


def _doc_path_from(data: dict) -> str:
    tool_input = data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return ""
    return tool_input.get("file_path") or tool_input.get("path") or ""


def _load_json(path: Path) -> dict:
    """Read a JSON object, or ``{}`` if absent/corrupt. Never raises."""
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def main() -> None:
    data = read_hook_input()
    if data.get("tool_name") not in WRITE_TOOLS:
        return

    path_str = _doc_path_from(data)
    repo_root = KDIR.parent  # this install's working tree — where the catalog lives
    cfg = load_cfg()
    # Classify against every working tree the document could belong to. From a worktree
    # the store is reached through a symlink into the MAIN checkout, so the document
    # resolves outside this checkout and `relative_to(repo_root)` alone finds nothing.
    for doc_root in checkout_roots(str(KDIR), local=repo_root):
        kind = gate_lib.document_kind(path_str, doc_root, cfg)
        if kind:
            break
    else:
        return

    doc_path = Path(path_str)
    if not doc_path.is_absolute():
        doc_path = (doc_root / doc_path).resolve()
    if not doc_path.exists():
        return

    # Inputs come from the working tree the document lives in; outputs go next to the
    # main checkout. The split matters on exactly the branches this gate is for: a
    # branch that edits stack.json must be judged against its own decisions, not
    # against the ones main happens to carry — otherwise every scoping, ranking or
    # selection branch is classified against a foreign state and, with `chosen_total`
    # read as 0, never earns a validator run at all.
    root = effective_root()
    catalog_dir = repo_root / str(cfg.get("compliance_dir") or "compliance-base") / "catalog"
    try:
        text = doc_path.read_text(encoding="utf-8")
    except OSError:
        return

    capabilities = _load_json(catalog_dir / "capabilities.json")
    stack = _load_json(catalog_dir / "stack.json")
    result = gate_lib.classify(
        gate_lib.mentions(text, gate_lib.component_index(capabilities)), stack, capabilities
    )

    # Spawn the deep validator — once per document per meaningful change. The ledger
    # is written BEFORE the spawn, so two writes in the same second cannot both fire.
    state_file = root / "reports" / ".state.json"
    text_hash = scope_lib.product_hash(text)
    state = gate_lib.load_state(state_file)
    if gate_lib.should_spawn(state, str(doc_path), text_hash, result):
        try:
            gate_lib.save_state(state_file,
                                gate_lib.record_spawn(state, str(doc_path), text_hash, now_iso()))
        except OSError:
            return
        cmd = ["uv", "run", "--directory", str(root), "python",
               "scripts/validate.py", str(doc_path), "--repo-root", str(repo_root)]
        env = {**child_env(), "STACK_ROOT": str(root)}
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        except OSError:
            pass

    summary = gate_lib.render_summary(result, kind, cfg)
    output: dict = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": summary,
        }
    }
    if gate_mode(cfg, kind) == "block" and result["off_stack"]:
        output["decision"] = "block"
        output["reason"] = summary
    print(json.dumps(output))


if __name__ == "__main__":
    main()
