<!--
prp-review-id: pr-20
pr: 20
base: main
head: fix/installer-auth-message
reviewed: 2026-09-02T00:00:00+02:00
reviewed_head: f93040827a75a48bab5fcf0c6c8c1d586527305b
verdict: READY TO MERGE
open_findings: 0
scopes: [code, seams, simplify]
publication: https://github.com/neurawork-git/howtobuildsoftware2026/pull/20#issuecomment-5505906006
-->

## Ready to merge

The PR changes three `print()` strings and nothing else. All three reviewers independently confirmed the same two facts that decide readiness: the credential claim is accurate (no `install.py` or payload script reads either variable — the `claude-agent-sdk` resolves credentials and accepts both), and these three lines were the last surface in the repo still naming a single credential, while `README.md`, `CLAUDE.md`, `plugins/CLAUDE.md`, `docs/INSTALL.md`, `docs/ARCHITECTURE.md`, the three `SKILL.md` files and the command docs already named both. The "subscription credentials are not sanctioned for third-party plugin use" decision in `CLAUDE.md` is untouched: it governs the auto-detected `~/.claude/.credentials.json` file, not the explicitly documented `CLAUDE_CODE_OAUTH_TOKEN` env var. No counterpart copy was left behind, nothing parses the changed output, and no test pins the old wording.

**0 blocking · 0 non-blocking**

**Validation:** Four applicable suites pass at the reviewed head (`_shared` 34, `knowledge-compiler` 15, `claudemd-lerner` 13, `compliance-compiler` 38). The `stack-compiler` and plugin-root suites named in current `CLAUDE.md` do not exist at this branch's base and are `not run`. `ruff` reports pre-existing errors on both this head and `main`; none is PR-caused.

### Findings

No findings.

<details>
<summary>Validation and reviewer coverage</summary>

#### Reviewer coverage

| Scope | Result |
|---|---|
| `code` | No additional findings |
| `seams` | No additional findings |
| `simplify` | No additional findings |

#### Validation

| Command | Result | Evidence |
|---|---|---|
| `python3 -m unittest discover -s _shared/tests` | PASS | Ran 34 tests — OK |
| `python3 -m unittest discover -s knowledge-compiler/tests` | PASS | Ran 15 tests — OK |
| `python3 -m unittest discover -s claudemd-lerner/tests` | PASS | Ran 13 tests — OK |
| `python3 -m unittest discover -s compliance-compiler/tests` | PASS | Ran 38 tests — OK |
| `python3 -m unittest discover -s stack-compiler/tests` | NOT RUN | Engine does not exist at base `8455bf7`; added later on `main` |
| `python3 -m unittest discover -s tests` (plugin root) | NOT RUN | `plugins/neurawork-cc-harness/tests/` does not exist at this head |
| `uvx ruff check` (engines root) | FAIL | 142 errors at head vs. 154 on `main`; pre-existing, none in the changed lines' rules |

#### Notes

- The branch is behind `main` (base `8455bf7`, three later commits touched these installers). A trial merge of `main` and the head produced no conflict; the three target lines are unchanged on `main`.
- `stack-compiler`, added to `main` after this branch, seeds nothing and has no equivalent credential message, so no fourth installer surface is missing.

</details>
