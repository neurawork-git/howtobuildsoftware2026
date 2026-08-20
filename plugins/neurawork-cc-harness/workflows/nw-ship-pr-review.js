export const meta = {
  name: 'nw-ship-pr-review',
  description: 'Review and explain a PR diff: an explanation agent plus parallel review dimensions (correctness/security/quality) with adversarial verification, deduplicated into one verdict.',
  whenToUse: 'Triggered by /nw-ship-pr after commit+push+PR, before the approval gate. Returns {explanation, findings, blocking_count} to the command.',
  phases: [
    { title: 'Analyze', detail: 'read the diff → what/why/verified/risk' },
    { title: 'Review', detail: 'correctness/security/quality in parallel + adversarial verify' },
    { title: 'Synthesize', detail: 'collect confirmed findings + verdict' },
  ],
}

// args from the command: { base, head, pr, context }
// The runtime delivers `args` as a JSON STRING, not an object — `("...").head` is undefined, so
// base/head/pr/context silently fell back to their defaults (head→'HEAD') and the review diffed
// main...HEAD of the current checkout instead of the PR branch. Hence: normalise args —
// string → JSON.parse (tolerant), object → use as delivered.
let _args = args
if (typeof _args === 'string') {
  try { _args = JSON.parse(_args) } catch { _args = {} }
}
_args = _args || {}
const base = _args.base || 'main'
const head = _args.head || 'HEAD'
const prNum = _args.pr ? String(_args.pr) : null
const ctx = _args.context || ''
const range = `${base}...${head}`
if (head === 'HEAD' && !prNum) {
  log('⚠️ nw-ship-pr-review: no head/pr in args — diffing main...HEAD of the current checkout. '
    + 'If the workflow runs from a session NOT on the PR branch, it reviews the wrong diff.')
}
// Defence in depth: with a PR number, use the authoritative PR diff (`gh pr diff <nr>`) —
// checkout-/cwd-independent, immune to the session cwd; otherwise the local range diff.
const diffCmd = prNum ? `gh pr diff ${prNum}` : `git diff ${range}`
// Fresh merge-base — agents fetch base before they diff.
const fetchFirst = `First \`git fetch origin ${base} --quiet\` (fresh merge-base), then: `

// SCOPE rule: the review asks "does the PR reach its goal + does it introduce NEW defects?",
// NOT "which future/hypothetical problems could arise". Prevents diverging fix loops (too
// strict). Blocking bugs/security issues stay detected.
const SCOPE = `SCOPE RULE (follow strictly):
- Judge ONLY: (a) does the diff reach its stated goal, and (b) does it introduce a NEW real defect (regression, genuinely exploitable security hole, breakage of existing behaviour)?
- Do NOT report: hypothetical/"could-someday" problems, future extensions, style taste, pre-existing issues OUTSIDE this diff, improvement wishes without a real defect.
- When in doubt, NO finding. Better 0 than speculative.`

const EXPLAIN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['changed', 'purpose', 'verification', 'risk'],
  properties: {
    changed: { type: 'array', items: { type: 'string' }, description: '3-6 bullets: what / which areas changed' },
    purpose: { type: 'string', description: 'Which problem was solved / which feature implemented (the purpose)' },
    verification: { type: 'string', description: 'How it was verified (tests/probes with results); "not verified" when nothing ran' },
    risk: { type: 'string', description: 'Live effects / migrations / data risks / irreversible steps; "none" when there are none' },
  },
}

const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'severity', 'title', 'why'],
        properties: {
          file: { type: 'string' },
          line: { type: 'string', description: 'Line(s) or ""' },
          severity: { type: 'string', enum: ['blocking', 'nice-to-have'] },
          title: { type: 'string' },
          why: { type: 'string', description: 'Why it is a problem + a concrete fix proposal' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['real', 'reason'],
  properties: {
    real: { type: 'boolean', description: 'true only when the finding is real + relevant for THIS diff' },
    reason: { type: 'string' },
  },
}

phase('Analyze')
const explanation = await agent(
  `You explain a pull request for the repository owner, clearly and concisely.
${fetchFirst}Gather facts via Bash: \`${diffCmd}\` (the authoritative diff of this PR), \`git diff --stat ${range}\`${prNum ? `, \`gh pr view ${prNum} --json title,body,additions,deletions,files\`` : ''}.
${ctx ? `Session intent (passed as context by the command — use it as a hint, do NOT adopt it blindly, check it against the diff): ${ctx}\n` : ''}Explain:
- changed: 3-6 bullets on what / which areas were changed
- purpose: which problem was solved / which feature was implemented (the actual purpose, not just the mechanics)
- verification: which tests/probes/validations visibly ran in the diff or PR body (with results); "not verified" when nothing is discernible
- risk: live effects, DB migrations, data risks, irreversible steps; "none" when there are none`,
  { label: 'analyze:explain', phase: 'Analyze', schema: EXPLAIN_SCHEMA }
)
const goal = (explanation && explanation.purpose) || '(derive the goal from the diff)'

phase('Review')
const DIMENSIONS = [
  { key: 'correctness', prompt: 'Correctness bugs, logic errors, off-by-one, wrong assumptions, race conditions, broken idempotency' },
  { key: 'security', prompt: 'Security: hardcoded secrets/keys, injection (SQL/shell), missing authorization, unsafe defaults, credentials leaked into logs/queries' },
  { key: 'quality', prompt: 'Reuse/simplification/efficiency, dead paths, missing or swallowed error handling (silent failures), unclear altitude' },
]

const reviews = await pipeline(
  DIMENSIONS,
  (d) =>
    agent(
      `${fetchFirst}review exclusively the diff of this PR \`${diffCmd}\` under the aspect **${d.key}**: ${d.prompt}.
GOAL of this PR (measure against it): ${goal}
${SCOPE}
ONLY high-confidence findings (confidence >= 80). If there is nothing: empty list.
severity: **blocking** = breaks the PR goal OR introduces a new real defect/regression/security hole in the diff. **nice-to-have** = a small real shortcoming IN the diff, not a blocker. (Speculative/future = no finding at all.)
Per finding: file, line, severity, title, why (including a concrete fix).`,
      { label: `review:${d.key}`, phase: 'Review', schema: FINDINGS_SCHEMA }
    ),
  (review, d) =>
    parallel(
      (review.findings || []).map((f) => () =>
        agent(
          `Adversarially verify whether this review finding is real and in scope. Be strict — when uncertain, real=false.
${SCOPE}
real=false when the finding is speculative/future/pre-existing-outside-the-diff, or does not concern the PR goal.
Finding: ${JSON.stringify(f)}
Check the diff context via \`${diffCmd}\` (is it really in the diff? is it not already handled?).`,
          { label: `verify:${d.key}`, phase: 'Review', schema: VERDICT_SCHEMA }
        ).then((v) => ({ ...f, dimension: d.key, confirmed: !!(v && v.real) }))
      )
    )
)

phase('Synthesize')
const confirmed = reviews.flat().filter(Boolean).filter((f) => f.confirmed)
const blocking = confirmed.filter((f) => f.severity === 'blocking')
log(`${confirmed.length} confirmed findings (${blocking.length} blocking)`)

return {
  explanation,
  findings: confirmed,
  blocking_count: blocking.length,
  total_findings: confirmed.length,
}
