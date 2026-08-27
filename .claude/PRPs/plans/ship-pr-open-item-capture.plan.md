# `/nw-ship-pr` — capture every open item the run surfaces, not only review findings

**Plan ID:** `ship-pr-open-item-capture`
**Source PRD:** `None`
**PRD Phase:** `None`
**Source Issue:** `None` (backlog item, `.claude/BACKLOG.md`, "ship-pr deferred #32")
**Plan Publication:** `None`

## Outcome

**Problem:** `/nw-ship-pr` persists exactly one class of knowledge: review findings. Phase 6.5
(`plugins/neurawork-cc-harness/commands/nw-ship-pr.md:357-364`) takes the `nice-to-have`
findings plus the `blocking` findings the user overrode at the gate, and writes them to the
configured sink. Everything else the run learns is spoken and then lost when the session ends:

- the **validation gate verdict** — `SKIP` with its reason, or `RED` overridden at the gate — is
  a Phase 5 talking point (`:338-339`) and a Phase 9 report bullet (`:658`) and nothing more;
- an **unverified claim** — the review workflow returned `null`/empty and the run fell back to an
  inline mini-review (`:276-278`) — is named once in the explanation and never recorded;
- **known-broken state** the explanation surfaces from session knowledge (`:341-343` explicitly
  asks the main loop to add contradictions and session context) has no sink at all;
- Phase 9's final bullet is literally `- open / deferred items.` (`:664`) — a report line with no
  writer behind it.

The proof is this repo's own backlog: three of its five checklist entries
(`$MAIN_ROOT` unresolved, `validate_commands` empty, `claudemd-lerner` never applied a log) are
not review findings of a diff — they are exactly this class of open item, and they are in
`.claude/BACKLOG.md` only because a human transcribed them by hand after the run.

**Affected user:** The repo owner shipping through `/nw-ship-pr` (and anyone adopting the
harness), who has to re-derive after every merge what the run already knew was unfinished.

**User outcome:** After a merge, the backlog contains every open item the run surfaced — the
deferred findings it already captured plus the degraded configuration, unverified claims, and
known-broken state — each carrying why it matters and where it lives, committed into the PR that
produced it.

**Invariant:** Every open item a run surfaces is, before the merge, either **written to the
configured sink** or **named in the report as deliberately not persisted, with its reason**. No
open item exists only in the transcript.

**Success signal:** Run `/nw-ship-pr` on this repo's next PR with `validate_commands` still empty
and the resulting backlog contains a "the validation gate is not configured" entry that nobody
typed. A second run on the same condition adds no duplicate.

**Approach:** No new machinery. Phase 6.5 already owns the sink, the de-dup rule, the
`<wt-root>`-anchored commit, and the first-run config write — it is missing only its **input
set**. Widen that input from "deferred findings" to "deferred items", where a review finding is
one source among four, and make Phase 5 the single place where the non-finding items are named
so that Phase 6.5 receives a settled list. Phase 9 stops being a source and becomes a readback of
what Phase 6.5 wrote plus the exclusions it named.

## Recommendation

Extend the existing capture step; do not add a second sink, a state file, or a new phase.

- **Phase 6.5 is already the right owner.** It runs before the merge for a reason the file
  documents at `:366-371`: the `backlog-file` sink writes into the working tree of the branch
  being shipped, so an entry written after the merge never reaches the PR and a
  `git worktree remove` (8.4) deletes it silently. Any second capture point would have to
  re-derive that same constraint. The file already states the rule explicitly at `:441-443`:
  *"the capture exists exactly once in this file, here — no second block in Phase 8.x."*
- **The non-finding items are all known before the gate.** The validation verdict is settled in
  Phase 4.5 (`:280-324`), the mini-review fallback in Phase 4 (`:276`), the session-knowledge
  contradictions in Phase 5 (`:341-343`), the override decision in Phase 6 (`:347-348`). Nothing
  in the new input set needs information that only exists after the merge — which is why this
  fits into the existing pre-merge slot without moving it.
- **The line format already carries non-code items.** `:378` renders
  `` (`<file>:<line>`, ship-pr deferred #<nr>) ``, and the live backlog already contains entries
  whose location is a config file with no line (`` `.claude/ship-pr.local.md` ``) and a directory
  (`` `claudemd-lerner/scripts/` ``). Generalising that field from "file:line" to "where it
  lives" is a documentation change, not a format change — existing entries stay valid.
- **The de-dup rule needs one strengthening, and only one.** Today de-dup is exact-title
  (`:380`). That is sufficient for findings, which are per-diff. The new items include
  *recurring conditions* — an unconfigured validation gate re-surfaces on every single run — so
  their titles must be **fixed strings named in the command**, not LLM-authored prose, or the
  backlog grows a near-duplicate per merge. This is the one place where the change adds a rule
  rather than widening an input.

### Evidence

| Fact | Where |
|---|---|
| Phase 6.5 input is findings-only, and skips entirely at 0 | `commands/nw-ship-pr.md:362-364` |
| Backlog line format, and the exact-title de-dup rule | `commands/nw-ship-pr.md:378-380` |
| Capture must precede the merge (sink writes into the shipped tree) | `commands/nw-ship-pr.md:366-371` |
| "Capture exists exactly once in this file, here" | `commands/nw-ship-pr.md:441-443` |
| Validation verdict carried to Phase 5/6, no hard exit at 4.5 | `commands/nw-ship-pr.md:314-317` |
| Gate `SKIP` on absent/empty `validate_commands` is not a failure | `commands/nw-ship-pr.md:156-157`, `:311` |
| Mini-review fallback merges on a degraded review | `commands/nw-ship-pr.md:275-278` |
| Phase 5 asks the main loop to add session knowledge and mark contradictions | `commands/nw-ship-pr.md:341-343` |
| Phase 9's orphan bullet with no writer | `commands/nw-ship-pr.md:664` |
| Phase 6.5 runs only after "approve & merge" | `commands/nw-ship-pr.md:359-360` |
| Worktree cleanup deferral is decided after the merge | `commands/nw-ship-pr.md:575-577` |
| Live sink config for this repo (`backlog-file` → `.claude/BACKLOG.md`) | `.claude/ship-pr.local.md` |
| Non-code entries already live in the backlog with a path-only location | `.claude/BACKLOG.md` (checklist items 1, 3, 4) |
| Guard-invariant tests are section-scoped, never global counts | `tests/test_skill_assets.py:134-141` |
| Precedent for pinning a documented phase behaviour by keyword | `tests/test_skill_assets.py:169-181` |

### Alternatives considered

- **A second capture step after the merge (Phase 9.5).** Rejected: the file's own reasoning at
  `:366-371` — a post-merge write into the shipped tree never reaches the PR and is destroyed by
  `git worktree remove`. It would also duplicate the sink dispatch and the config write.
- **A machine-readable run-state file that Phase 9 drains.** Rejected: it introduces a second
  artifact with its own lifecycle next to `.ship-pr-state.json`, and the run already holds every
  item in context at Phase 6.5. New state buys nothing the ordering does not already give.
- **A separate backlog section for non-finding items.** Rejected: `.claude/BACKLOG.md` is one flat
  checklist whose entries already have mixed origins, and a second section doubles the de-dup
  surface for no reader benefit.

## Visuals

Where each open item is born, and where it goes — before and after.

```
BEFORE
  4    review ──(null)──► mini-review fallback ······················► spoken only
  4.5  gate ──► SKIP(reason) │ RED ·································► spoken only
  5    explanation + session knowledge ·····························► spoken only
  5    findings (nice-to-have) ─────────────┐
  6    gate: blocking overridden ───────────┤
                                            ▼
  6.5                                  [ SINK ] ──► backlog commit ──► PR
  9    report bullet "open / deferred items" ·······················► spoken only

AFTER
  4    review ──(null)──► mini-review fallback ──┐
  4.5  gate ──► SKIP(reason) │ RED ──────────────┤
  5    explanation + session knowledge ──────────┼──► Phase 5 point 7:
  5    findings (nice-to-have) ─────────────────┤     "Open items" (named, settled)
  6    gate: blocking overridden ───────────────┘              │
                                                               ▼
  6.5                                      [ SINK: deferred items ] ──► commit ──► PR
                                                               │
  8.4  worktree removal deferred ──► NAMED EXCLUSION ──────────┤
  6    cancel / fix-first ─────────► NAMED EXCLUSION ──────────┤
                                                               ▼
  9    report = readback of what 6.5 wrote + the named exclusions
```

The invariant is the last line: Phase 9 names nothing that Phase 6.5 neither wrote nor
explicitly excluded.

## Implementation Context

### Mandatory reading

- `plugins/neurawork-cc-harness/commands/nw-ship-pr.md` — the whole file. This change edits
  prose that other phases depend on by reference; the call-form rules (Phase 4, `:239-247`) and
  the `<wt-root>` anchoring rule (Phase 6.5, `:381-388`) constrain every command line written
  into it.
- `plugins/neurawork-cc-harness/tests/test_skill_assets.py` — the module docstring states what
  these tests do and do not prove (`:1-11`); the new test follows
  `test_both_worktree_cleanup_phases_carry_their_own_probe` (`:134-153`), which documents why a
  guard test must be section-scoped rather than a global count.
- `.claude/BACKLOG.md` — the live sink, and the format precedent for path-only locations.

### Existing patterns and primitives

- **The sink dispatch** (`:374-405`) already handles all three `followup_sink` values and needs
  no branching change — only its input list changes name and content.
- **The `<wt-root>` anchoring rule with the branch assertion** (`:381-393`) is the exact command
  form the backlog commit must keep; do not re-derive it.
- **The zero-item skip** (`:364`) is load-bearing against empty commits and stays verbatim in
  meaning.
- **Fixed-string titles for recurring conditions** have no precedent in this file; the closest
  analogue is the commit message at `:391`, which is a fixed template with `#<nr>` interpolated.

### Integration points

- `.claude/ship-pr.local.md` — unchanged. No new config key: the sink, the backlog path, and the
  validation commands already cover everything this change needs.
- `plugins/neurawork-cc-harness/commands/nw-ship-pr.md` frontmatter `description` (`:2`) — the
  ordered phase list already says "follow-up capture"; that word now covers more, so the line
  stays accurate and is not touched.
- `docs/ARCHITECTURE.md:31-33,57` and `plugins/CLAUDE.md:19-23` mention the command by filename
  and role only. Neither describes Phase 6.5's inputs, so neither goes stale — verified, no edit.

## Scope

### In scope

- Phase 5 gains an explicit **"Open items"** point that names the non-finding items at the moment
  they are settled.
- Phase 6.5's input widens from "deferred findings" to "deferred items", with the item shape,
  the four sources, and the location field documented.
- Fixed-string titles for the recurring mechanical items, so exact-title de-dup holds across runs.
- The two **named exclusions** (deferred worktree removal; the cancel / fix-first paths) written
  into the command as deliberate, with their reasons.
- Phase 9's report bullet becomes a readback plus the invariant statement.
- One guard-invariant test pinning the properties whose loss would be silent.

### Not building

- **No new phase, sink, state file, or config key.**
- **No change to what the review workflow returns.** `workflows/nw-ship-pr-review.js` and its
  `FINDINGS_SCHEMA` (`:57-74`) are untouched — the new items come from the command's own phases,
  not from the fan-out.
- **Not seeding `validate_commands`** in `.claude/ship-pr.local.md`. That is its own backlog item;
  this change makes the empty gate produce a backlog entry, which is the diagnosis, not the fix.
- **Not fixing the unresolved `$MAIN_ROOT`.** It appears inside Phase 6.5's first-run config write
  (`:415`), which this change edits around. It is a separate backlog item with its own fix
  (resolve it once in the ground rules); leave those lines exactly as they are.
- **No retroactive capture.** Items from past runs stay wherever a human put them.

## Delivery Considerations

- **Compatibility:** existing `.claude/BACKLOG.md` entries stay valid — the format is widened by
  documentation, not changed. `.claude/ship-pr.local.md` files in the wild need no migration.
- **Reversibility:** prompt-only. Reverting the commit restores the previous behaviour exactly;
  nothing persists that a revert would orphan.
- **Volume risk:** the change writes more backlog entries per run. The fixed-title rule for
  recurring items is the control; the zero-item skip keeps a clean run silent.
- **Documentation:** the command file is the documentation. `docs/` and `plugins/CLAUDE.md`
  describe the command's role, not its phase inputs — checked, no edit needed.

## Compliance

**Capabilities**: `soc2/change-management-secure-sdlc`, `iso27001/change-release-management-for-production`, `iso27001/secure-development-lifecycle-secure-coding`.

This change edits the repo's own change-and-release procedure — `/nw-ship-pr` is the documented
path by which work reaches the default branch — so the Change & SDLC capabilities apply even
though the artifact is prose plus one guard test. It processes no personal data, adds no data
store, no network path, and no authentication or authorisation surface; every GDPR and privacy
constraint in the catalog is therefore not applicable.

Two notes on how the change interacts with those controls:

- **Segregation of duties (SOC2-CC8-06).** A change to the shipping command is shipped *by* that
  command, which collapses author and approver unless the PR is reviewed by someone other than
  its author. Review this diff on the PR before the Phase 6 approval; do not self-approve it on
  the strength of the gate alone.
- **The change strengthens the controls it falls under.** Capturing degraded validation, an
  overridden `RED` gate, and a merge made on a fallback review turns three previously unrecorded
  control exceptions into tracked, committed entries — evidence that outlives the session.

## Implementation

### 1. Phase 5 names the open items

**Files and integration points**
- `plugins/neurawork-cc-harness/commands/nw-ship-pr.md` — Phase 5 (`:326-343`) — EDIT.

**Implementation**
- Add point **7. Open items** after the existing point 6, presented to the user with the rest of
  the explanation. It collects, by name, everything the run surfaced that is unfinished and is
  not a review finding:
  - **Degraded validation** — the Phase 4.5 verdict when it is not `GREEN`: `SKIP` with its reason
    (empty/absent `validate_commands`; a configured command that is not installed), or `RED`.
    A `RED` item is only real once the user overrides it at Phase 6 — until then the run may loop
    back and fix it — so it is listed here and confirmed in Phase 6.5.
  - **Unverified claims** — anything asserted in points 1-4 that the run did not prove. Concretely:
    the Phase 4 fallback path (`:275-278`) where the workflow returned `null`/empty and the merge
    rests on an inline mini-review.
  - **Known-broken state** — what the augmentation step (`:341-343`) surfaces from session
    knowledge: a contradiction between diff and intent, a workaround shipped knowingly, a
    subsystem the session found broken and did not fix.
- State that each open item is named as `title` / `why` / `where`, the same three fields a
  finding carries, so Phase 6.5 has one shape to write.
- State that this is the **only** collection point for non-finding items: a later phase does not
  invent new ones, it reports what was collected here.
- Keep points 1-6 untouched, including the existing "RED feeds the approval gate" sentence.

**Tests** — covered by task 4 (section-scoped assertion that Phase 5 names open items).

**Validation**
- `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests`

### 2. Phase 6.5 captures deferred items, not only deferred findings

**Files and integration points**
- `plugins/neurawork-cc-harness/commands/nw-ship-pr.md` — Phase 6.5 (`:357-443`) — EDIT.

**Implementation**
- Rewrite the input paragraph (`:362-364`) to define **deferred items** as the union of four
  sources, all settled by this point in the run:
  1. review findings with severity `nice-to-have`;
  2. review findings with severity `blocking` that the user overrode at the Phase 6 gate;
  3. the Phase 5 open items (degraded validation, unverified claims, known-broken state), with
     the `RED` gate item included only when the user chose "merge anyway";
  4. nothing else — Phase 7 and later cannot contribute, because they run after this step (and
     by design they STOP rather than defer: `:451-469`).
  Keep the skip rule verbatim in meaning: **0 deferred items → skip the step entirely** (no
  question, no write, no empty commit).
- Document the item shape as `title` / `why` / `where`, and redefine `where` as *the file, path,
  or phase the item concerns*: `file:line` for a review finding, the config or code path for an
  open item that has one, and the surfacing phase (e.g. `Phase 4.5 validation gate`) when it has
  none. Note that the rendered line at `:378` is unchanged and that the live backlog already
  contains path-only and directory-only locations.
- Generalise the rendered template's placeholders from `<finding.*>` to `<item.*>`; the line
  itself stays byte-identical in shape:
  ```
  - [ ] **<item.title>** — <item.why>  (`<item.where>`, ship-pr deferred #<nr>)
  ```
- Extend the de-dup rule (`:380`): exact-title de-dup stays, and **recurring mechanical items
  must use these fixed titles** so it actually holds across runs —
  - `the /nw-ship-pr validation gate is not configured` — `validate_commands` empty or absent;
  - `the /nw-ship-pr validation gate could not run` — commands configured, none installed;
  - `PR #<nr> was merged with a failing <command>` — a `RED` gate overridden at the gate;
  - `PR #<nr> was merged on a fallback mini-review` — the Phase 4 null/empty path.
  The first two are repo conditions and carry no PR number, so the second run after the first
  finds the title already present and appends nothing. The last two are per-PR by construction.
  Free-prose titles remain correct for the session-knowledge items, where de-dup is best-effort.
- Add the two **named exclusions**, as deliberate decisions with their reasons:
  - **A deferred worktree removal is not captured.** It is local, ephemeral state decided after
    this step (8.4, `:575-577`); the Phase 9 report prints the exact removal commands, which is
    the whole record needed. Writing it to a tracked backlog would put a machine-local chore into
    a shared file.
  - **On "fix findings first" / "fix validation failures first" / "cancel", this step does not
    run** (`:359-360`), so nothing is written. Say what happens instead: the run's report names
    the open items and states plainly that they were **not** persisted — the branch and the PR
    still exist, so the items are recoverable from the run that follows. Do not write to the sink
    on those paths: the branch may be abandoned, and a commit + push there would carry a backlog
    entry into a PR nobody merges.
- Leave the `<wt-root>` anchoring block, the branch assertion, the commit message, the
  `github-issues` and `none` branches, the first-run config write, and the two
  "deliberately unhandled points" untouched — including the `$MAIN_ROOT` reference at `:415`.

**Tests** — covered by task 4.

**Validation**
- `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests`

### 3. Phase 9 reports what was captured

**Files and integration points**
- `plugins/neurawork-cc-harness/commands/nw-ship-pr.md` — Phase 9 (`:643-664`) — EDIT.

**Implementation**
- Replace the bare `- open / deferred items.` bullet (`:664`) with a readback: **N items written
  to `<sink>`** (for `backlog-file`, the commit that carried them into the PR), plus the items
  **not** persisted by name and reason — the deferred worktree removal when there is one, and any
  item the exclusion rules covered. Keep the existing "Follow-ups" bullet (`:659-660`) as the
  sink-side count and make the new bullet the item-side account, or merge the two into one bullet
  if that reads cleaner — one of the two, not both saying the same thing twice.
- Add the closing invariant sentence to the phase: *this report names no open item that Phase 6.5
  neither wrote nor explicitly excluded; if one appears here, Phase 6.5's input set was
  incomplete.* That is what makes the report checkable instead of decorative.
- Leave the marker deletion, the validation-gate bullet, the worktree bullet, and the capture
  bullet as they are.

**Tests** — covered by task 4.

**Validation**
- `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests`

### 4. Pin the capture invariant in the asset tests

**Files and integration points**
- `plugins/neurawork-cc-harness/tests/test_skill_assets.py` — `GuardInvariantTests` (`:121-181`)
  — EDIT (add tests, change nothing existing).

**Implementation**
- Add a helper that slices a phase section out of `SHIP_PR` by its heading and the next heading,
  mirroring `test_both_worktree_cleanup_phases_carry_their_own_probe` (`:134-141`) — that test's
  own comment explains why a global count stays green while both guards are deleted, which is
  exactly the failure mode here: a file-wide search for "open items" would pass on the Phase 5
  mention alone even if Phase 6.5 stopped consuming them.
- `test_follow_up_capture_takes_open_items_not_only_findings`: the `## Phase 6.5` section names
  both the finding sources (`nice-to-have`) and the Phase 5 open items, and still states the
  zero-item skip. Failure message: what is lost if it goes — the run reverts to persisting review
  findings only.
- `test_explanation_names_open_items`: the `## Phase 5` section carries the open-items point.
- `test_recurring_capture_items_have_fixed_titles`: each of the four fixed title strings from
  task 2 appears in the `## Phase 6.5` section verbatim. This is the test that keeps de-dup
  working — an LLM-authored title silently reintroduces one duplicate per merge.
- `test_report_does_not_invent_open_items`: the `## Phase 9` section states the readback
  invariant rather than being a free-form source.
- Do not touch the four existing tests or the module docstring's claim about what these tests
  prove (`:1-11`) — it still holds: these pin prose properties, not runtime behaviour.

**Validation**
- `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests`
- `uvx ruff check` from the repo root.

### 5. Close the backlog item

**Files and integration points**
- `.claude/BACKLOG.md` — EDIT — tick the item this plan implements.

**Implementation**
- Mark `- [ ] **`/nw-ship-pr` should capture open items, not only review findings**` as done, in
  whatever form the file's convention takes (tick the box; leave the entry and its reference
  intact so the trail stays readable). Touch no other entry — the other four are separate items,
  two of which this plan deliberately does not fix.

**Validation**
- `git diff .claude/BACKLOG.md` shows exactly one changed line.

## Acceptance

1. **AC1 — Degraded validation reaches the sink.** A run whose Phase 4.5 gate reports `SKIP`
   because `validate_commands` is empty, and which the user approves, writes a backlog entry
   titled `the /nw-ship-pr validation gate is not configured` whose `why` names the empty key and
   the fix, committed into the PR by the existing Phase 6.5 commit.
2. **AC2 — A recurring item is written once.** A second approved run under the same unconfigured
   gate appends nothing: the exact title is already present, and the de-dup rule catches it.
3. **AC3 — An overridden failure is recorded as merged-anyway.** A run whose gate is `RED` and
   whose user chooses "merge anyway" writes `PR #<nr> was merged with a failing <command>`; a run
   whose user chooses "fix validation failures first" writes nothing at all and loops back.
4. **AC4 — A degraded review is recorded.** A run that reaches the merge via the Phase 4
   null/empty fallback writes `PR #<nr> was merged on a fallback mini-review`.
5. **AC5 — A clean run stays silent.** A run with no deferred findings, a `GREEN` gate, a normal
   review, and nothing broken in session knowledge produces zero backlog entries, no question,
   and no empty commit.
6. **AC6 — Exclusions are named, not silent.** A run that defers the worktree removal reports it
   as deliberately not captured with its reason, and writes no backlog entry for it. A cancelled
   run names its open items and states that they were not persisted.
7. **AC7 — The report is a readback.** Phase 9 names the captured items with the commit that
   carried them plus the named exclusions, and states that it introduces no open item Phase 6.5
   did not handle.
8. **AC8 — Nothing else in the lifecycle moved.** The worktree guards, the implicit-checkout
   prohibition, the workflow name resolution, and the validation-gate documentation all still
   hold — the four pre-existing guard tests pass unmodified.

## Validation

| Gate | Command or procedure | Proves |
|---|---|---|
| Plugin asset suite | `cd plugins/neurawork-cc-harness && python3 -m unittest discover -s tests` | Tasks 1-4 are present in the prose; AC8 (the four existing guards) |
| Engine suites (regression) | `cd plugins/neurawork-cc-harness/engines && python3 -m unittest discover -s _shared/tests && python3 -m unittest discover -s knowledge-compiler/tests && python3 -m unittest discover -s claudemd-lerner/tests && python3 -m unittest discover -s compliance-compiler/tests` | A prompt-only change touched no engine |
| Lint | `uvx ruff check` (repo root) | Style gate, `line-length = 100` |
| Runtime, this repo | `/nw-ship-pr` on the PR that ships this change, approved at the gate with `validate_commands` still empty | AC1, AC5, AC7 — the run's own backlog entry appears in its own PR, or the run is legitimately silent and says so |
| Runtime, second run | `/nw-ship-pr` on the next PR after this one merges, same unconfigured gate | AC2 — no duplicate entry |
| Runtime, worktree | The same run from a `/nw-worktree` sibling, choosing "Later" at the 8.4 cleanup gate | AC6 — the deferral is reported and not written |
| Manual read | `git diff plugins/neurawork-cc-harness/commands/nw-ship-pr.md` | The diff touches Phase 5, Phase 6.5's input/de-dup/exclusions, and Phase 9 only — no phase ordering changed, `$MAIN_ROOT` untouched |

The asset tests prove the prose exists, never that the run behaves. The runtime rows are the real
gate — the module docstring at `tests/test_skill_assets.py:1-11` makes the same point about this
suite generally, and it applies here.

## Risks and Decisions

| Decision or risk | Recommendation | Evidence / mitigation | Consequence if different |
|---|---|---|---|
| Where the new inputs are captured | Widen Phase 6.5; add no phase | The pre-merge constraint is documented at `:366-371` and the "exactly once" rule at `:441-443` | A post-merge capture never reaches the PR and dies with `git worktree remove` |
| Backlog noise from recurring items | Fixed title strings, pinned by a test | Exact-title de-dup already exists (`:380`); only the title's stability is new | Free prose per run = one near-duplicate per merge, and the backlog stops being readable |
| Deferred worktree removal | Named exclusion, not captured | Local, ephemeral, decided after 6.5 (`:575-577`); the report already prints the commands | Machine-local chores land in a tracked, shared file |
| Cancel / fix-first paths | Report the items, persist nothing | 6.5 runs only after approval (`:359-360`); the branch and PR survive, so the items are recoverable | A commit + push onto a possibly abandoned branch, carrying a backlog entry into a PR nobody merges |
| Where non-finding items land in the backlog | The same flat checklist | `.claude/BACKLOG.md` already mixes origins in one list | A second section doubles the de-dup surface for no reader benefit |
| `$MAIN_ROOT` unresolved inside the edited phase | Do not touch it | Separate backlog item with its own fix (resolve once in the ground rules) | Two fixes in one diff, and a ground-rule change smuggled into a capture change |
| Empty `validate_commands` in this repo | Do not seed it here | Separate backlog item; leaving it empty is what makes AC1 observable on the shipping run | Fixing it first removes this plan's best live fixture |

## Agent Notes

- This file is prose that other phases reference by number and by quoted rule. When editing
  Phase 6.5, re-read Phase 4's call-form rules (`:239-247`) and Phase 6.5's own `<wt-root>`
  anchoring argument (`:381-393`) before writing any command line — both explain refusals and
  wrong-checkout pushes that were observed in practice, not hypotheticals.
- The four fixed titles are a contract between the command and the test. Change one in either
  place and change it in both, or de-dup silently stops working while the suite stays green on the
  other three.
- This repo's current state is the fixture: `validate_commands` is empty in
  `.claude/ship-pr.local.md`, so the very run that ships this change should produce AC1's entry in
  its own PR. That is the intended demonstration — do not seed the config to make the run look
  cleaner.
