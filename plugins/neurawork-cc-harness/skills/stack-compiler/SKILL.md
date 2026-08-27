---
name: stack-compiler
description: Install per-repo product scoping + closed-pool stack selection into the current repository. Parallel agents decide which compliance capabilities actually apply to the product, rank each one's catalog components, and a human records the chosen component; a PostToolUse hook then gates every PRD and PRP plan write against those choices. Trigger when the user says "stack compiler", "install stack compiler", "product scoping", "choose the stack", "welche komponenten dürfen wir nutzen", "stack festschreiben", "gate PRDs against the chosen stack", or wants the compliance catalog narrowed to one product.
---

# Stack Compiler — Install Skill

Installs the stack-compiler engine into the current repo. Three passes plus a gate:

1. **Scope** — `scripts/scope.py` reads the tracked `<stack-dir>/product.md` and decides,
   per capability in the compliance catalog, *whether* it applies to this product and
   why. Parallel Claude Agent SDK agents; a challenge agent can refute a "not
   applicable" claim, and a mandatory-safety gate runs before anything is written.
   All-or-nothing: a failed gate writes nothing.
2. **Rank** — `scripts/rank.py` orders each still-applicable capability's catalog
   components best-fit-first with a reason per position. The component pool is closed:
   a ranking must name exactly that capability's `options`, once each.
3. **Selection** — `scripts/selection.py` renders that ranking as an editable
   **selection sheet**, reads back the component a human wrote per capability, and
   records it. No agent, no API key — the proposal already exists. Deliberately
   partial: an undecided capability stays a counted gap, never a silent omission.
4. **Gate** — a `PostToolUse` hook checks each PRD and PRP plan as it is written: a
   fast inline precheck plus a detached deep `scripts/validate.py` report in
   `<stack-dir>/reports/`. `config.json`'s `validate_mode` sets `warn` | `block` per
   document type. The gate **reads** the recorded stack, never writes it.

The engine owns **no data artifact**. Every write goes through
`<compliance-dir>/scripts/stack.py`, the single schema owner for
`catalog/stack.json`. Everything it installs lives inside the repo, never under
`.claude/`.

## Data dependency

`compliance-compiler` must be installed and its catalog built
(`catalog/capabilities.json`) for the passes and the gate to have anything to read.
The install itself succeeds either way — install order is not load-bearing. Without
the sibling, the three CLI passes exit 1 with a message and the gate reports "nothing
chosen" rather than erroring.

## Authentication

`scope.py`, `rank.py` and the deep `validate.py` use the Claude Agent SDK, which needs
`ANTHROPIC_API_KEY` (or `CLAUDE_CODE_OAUTH_TOKEN`). Subscription credentials are NOT
sanctioned for third-party plugins — public/customer installs must set an API key.
Install, scaffolding, the inline precheck and the whole of `selection.py` work without
one.

## Naming / collision note

Invoke this as `neurawork-cc-harness:stack-compiler`. Its hooks are `st-` prefixed and
register on `PostToolUse` under `matcher: "Write|Edit|MultiEdit"`, sharing that group
with the compliance engine's `co-` hook, so all four harness engines coexist in one
`.claude/settings.json`.

Not to be confused with the unrelated external `stack-tools` plugin: this skill decides
what a product **may** use; `stack-tools` reports what is **running**.

## Phase A — Recon (read-only)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/engines/stack-compiler/recon.py"
```

- `status: NOT_A_GIT_REPO` → stop; tell the user to run inside a git repo.
- `existing_dir` set → ADOPT (refresh) install; reuse that name.
- `compliance_dir` null → say the passes and the gate have nothing to read yet.
- Note `stack_state` (how many capabilities are scoped / chosen), `existing_hooks`,
  `timezone`, `clean`.

## Phase B — Ask

Use AskUserQuestion to confirm:
1. **Stack dir name** — default `stack-base` (or the detected `existing_dir`).
2. **Compliance dir** — default the detected `compliance_dir`, else `compliance-base`.

Nothing else: there is no framework subset here and no pass the installer can usefully
run (the first one needs a `product.md` a human has written).

## Phase C — Execute

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/engines/stack-compiler/install.py" \
  --stack-dir <NAME> --compliance-dir <NAME>
uv sync --directory <NAME>
```

Then tell the user to commit `<NAME>/` and `.claude/settings.json`, and relay any line
the installer printed about a missing compliance install or a `PRP_HOME` it left alone.
After install, the four commands in pass order:

- `/neurawork-cc-harness:st-scope` — writes the `product.md` template on its first run;
  fill it in, then re-run. Needs an API key.
- `/neurawork-cc-harness:st-rank` — orders each applicable capability's components.
  Needs an API key.
- `/neurawork-cc-harness:st-select` — renders the selection sheet, then records the
  filled-in choices with `--apply`. Needs no API key.
- `/neurawork-cc-harness:st-validate <document>` — the deep check the `st-` gate spawns
  automatically, on demand. Needs an API key.
