"""Fix the component chosen for each applicable capability — the human's pass.

Reads the sibling compliance install's ``catalog/capabilities.json`` and
``catalog/stack.json``, renders the ranking pass's proposal as an editable markdown
**selection sheet**, reads the filled sheet back, and records what the human decided.

Unlike ``scope.py`` and ``rank.py`` this pass runs **no agent**: the ordering and the
reasoning already exist in ``stack.json``, so there is nothing left to infer. It needs
no API key and makes no network call — render, parse, set math, subprocess.

Only a clean gate reaches the write, and the write goes through
``<compliance_dir>/scripts/stack.py --apply-selection`` — the one schema owner for
``stack.json``. This engine creates no data artifact of its own.

The pass is deliberately resumable: a re-rendered sheet shows what is already recorded
and leaves every ``choice:`` line blank, so applying it records only what the human
wrote this time and leaves every other capability — decided or not — exactly as it was.

Named ``selection.py`` and not ``select.py``: ``scripts/`` is first on ``sys.path`` for
every script run out of it, so a module named ``select`` shadows the stdlib ``select``
that ``selectors`` — and through it ``asyncio`` — imports, breaking ``scope.py`` and
``rank.py`` at import time. Do not rename it back.

Usage:
    uv run python scripts/selection.py                # render the sheet
    uv run python scripts/selection.py --apply S.md   # record the choices it carries
    uv run python scripts/selection.py --apply S.md --dry-run   # gate + report, no write
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # install dir for _shared

import rank_lib
import selection_lib
from config import (
    REPORTS_DIR,
    ROOT_DIR,
    SHARDS_DIR,
    compliance_root,
    load_cfg,
    today_iso,
)

# _shared/ is imported inside main(): it exists next to scripts/ only in an installed
# repo, not in the plugin's payload/ tree, so the pure logic above stays importable
# (and unit-testable) straight from payload/scripts.


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record the component chosen for each applicable capability"
    )
    parser.add_argument("--apply", type=str, metavar="PATH",
                        help="Record the choices carried by a filled selection sheet")
    parser.add_argument("--dry-run", action="store_true",
                        help="With --apply: gate and report, but write nothing")
    args = parser.parse_args()

    cfg = load_cfg()
    comp = compliance_root(cfg)
    catalog_dir = comp / "catalog"
    capabilities_json = catalog_dir / "capabilities.json"
    stack_json = catalog_dir / "stack.json"
    stack_py = comp / "scripts" / "stack.py"

    if not comp.is_dir():
        print(f"No compliance install at {comp} — stack-compiler has nothing to select from. "
              "Install compliance-compiler first, or set 'compliance_dir' in config.json.")
        return 1
    if not capabilities_json.exists():
        print(f"No {capabilities_json} — run "
              f"`uv run --directory {comp.name} python scripts/capabilities.py` first")
        return 1
    if not stack_json.exists():
        print(f"No {stack_json} — run "
              f"`uv run --directory {comp.name} python scripts/stack.py --scaffold` first")
        return 1
    if not stack_py.exists():
        print(f"No {stack_py} — the compliance install is incomplete")
        return 1

    capabilities = _load_json(capabilities_json)
    stack = _load_json(stack_json)
    if not rank_lib.is_scoped(stack):
        print(f"{stack_json} carries no scoping decisions — run "
              f"`uv run --directory {ROOT_DIR.name} python scripts/scope.py` first. "
              "An unscoped stack would ask you to choose components for every capability "
              "in the catalog.")
        return 1

    universe = selection_lib.selectable_universe(stack, capabilities)
    if not universe:
        print("Every capability was scoped out of this product — nothing to select.")
        return 0

    from _shared.repo_guard import WriteGuardError, assert_in_repo_not_dotclaude
    try:
        assert_in_repo_not_dotclaude(REPORTS_DIR, ROOT_DIR.parent)
    except WriteGuardError as e:
        print(f"Refusing to write reports: {e}")
        return 1

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    generated = today_iso()

    # ── Render the sheet ──
    if not args.apply:
        sheet_path = REPORTS_DIR / f"selection-sheet-{generated}.md"
        apply_command = (f"uv run --directory {ROOT_DIR.name} python scripts/selection.py "
                         f"--apply {sheet_path}")
        sheet_path.write_text(
            selection_lib.render_sheet(universe, generated, stack_path=str(stack_json),
                                       apply_command=apply_command),
            encoding="utf-8",
        )
        chosen = sum(1 for u in universe if u["chosen"])
        unranked = [u["key"] for u in universe if not u["ranked"]]
        print(f"{len(universe)} applicable capability/-ies: {chosen} chosen, "
              f"{len(universe) - chosen} undecided.")
        print(f"sheet: {sheet_path}")
        if unranked:
            print(f"! {len(unranked)} capability/-ies carry no ranking and are listed in "
                  f"catalog order: {', '.join(unranked)}")
        print(f"Fill in the `choice:` lines, then: {apply_command}")
        return 0

    # ── Apply a filled sheet ──
    sheet_path = Path(args.apply)
    if not sheet_path.exists():
        print(f"No such selection sheet: {sheet_path} — run "
              f"`uv run --directory {ROOT_DIR.name} python scripts/selection.py` to render one.")
        return 1

    try:
        selections = selection_lib.parse_sheet(sheet_path.read_text(encoding="utf-8"), universe)
    except ValueError as e:
        print(f"{sheet_path} could not be read:")
        for problem in str(e).split("; "):
            print(f"  - {problem}")
        return 1

    if not selections:
        print(f"{sheet_path} carries no filled `choice:` line — nothing to record.")
        return 0

    policy = capabilities.get("license_policy") or {}
    gate = selection_lib.selection_gate(universe, selections, policy)
    report_path = REPORTS_DIR / f"selection-{generated}.md"
    report_path.write_text(
        selection_lib.render_select_report(universe, selections, gate, generated,
                                           sheet_path=str(sheet_path)),
        encoding="utf-8",
    )

    print(f"{len(selections)} choice(s) read from {sheet_path}. "
          f"{len(gate['pending'])} capability/-ies still undecided.")
    print(f"report: {report_path}")

    if not gate["ok"]:
        print("\nSELECTION GATE FAILED — nothing written:")
        for key in gate["unknown"]:
            print(f"  - {key}: not an applicable capability of this product")
        for key in gate["blank"]:
            print(f"  - {key}: names no component")
        for item in gate["off_pool"]:
            print(f"  - {item['key']}: {item['chosen']} is not in options "
                  f"({', '.join(item['options']) or 'none'})")
        for v in gate["violations"]:
            print(f"  - {v['key']}: {v['component']} carries {v['license']} in an "
                  f"{v['role']} role — fix capabilities.json, not this choice")
        return 1

    if args.dry_run:
        print("[DRY RUN] gate passed — stack.json not written.")
        return 0

    # ── Apply through the schema owner ──
    SHARDS_DIR.mkdir(parents=True, exist_ok=True)
    selections_path = SHARDS_DIR / "selections.json"
    selections_path.write_text(
        json.dumps(selection_lib.selections_payload(selections), indent=1,
                   ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    proc = subprocess.run(  # fixed argv, no shell; the return code is inspected below
        [sys.executable, str(stack_py), "--apply-selection", str(selections_path)],
        cwd=str(comp), capture_output=True, text=True, check=False,
    )
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        print(f"\n{stack_py.name} refused the write (exit {proc.returncode}) — "
              "stack.json is unchanged.")
        return 1

    if gate["exceptions"]:
        print(f"{len(gate['exceptions'])} chosen component(s) carry a recorded license "
              "exception — see the report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
