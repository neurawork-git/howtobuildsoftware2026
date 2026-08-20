# Product — `neurawork-cc-harness`

The product this stack is scoped for. The scoping agents read only this file, so
anything they need to know is written here.

## What it does

`neurawork-cc-harness` is a **Claude Code plugin**: a set of skills a developer
installs into their own git repository to keep that repository's project knowledge
current. It ships four skills — `knowledge-compiler` (distils session logs into a
per-repo knowledge base), `claudemd-lerner` (keeps the `CLAUDE.md` hierarchy and
`docs/` current), `compliance-compiler` (distils GDPR/SOC 2/ISO 27001 into a tracked
constraint catalog and validates PRP plans against it), and `stack-compiler` (scopes
that catalog to one product and gates PRD/plan writes against the chosen stack).

It is developer tooling, not a hosted service. There is no server we operate, no
account, no sign-up, no tenant, and no customer-facing UI.

## Who uses it

Software engineers, working locally in their own checkout of their own repository.
There is no end user beyond the engineer who installed it, no operator running it
on someone else's behalf, and no third party whose data passes through it.

## What data it holds

- **Local session transcripts.** The hooks read the Claude Code session transcript
  from the developer's own machine and write derived markdown and JSON **into the
  developer's own repository**, under tracked paths such as `knowledge-base/`,
  `compliance-base/catalog/`, `CLAUDE.md` and `docs/`. Nothing is written under
  `.claude/` and nothing is written outside the repository.
- **No personal data is collected, stored or processed as a product function.** The
  plugin does not hold names, email addresses, IP addresses, payment details, health
  data, location data, biometric data, telemetry or analytics. It does not identify
  or profile anyone. Whatever a developer happens to have written in their own
  session is their own file on their own disk, under their control; the plugin adds
  no store of its own and transmits nothing to us.
- **No credentials are stored.** LLM calls read `ANTHROPIC_API_KEY` or
  `CLAUDE_CODE_OAUTH_TOKEN` from the developer's environment at call time. The
  plugin never persists, logs or forwards them.
- **No user accounts, sessions, passwords, roles or permissions exist**, because
  there is no service to log in to.

## Who receives data

There is exactly one recipient, and it is the developer's own: **the Anthropic API**,
called with the developer's own credentials. The compile, extraction and scoping
agents send prompt content — the developer's own repository text and session
transcript excerpts — to that API in order to produce the derived documents. The
developer chooses the account and holds the contract with Anthropic directly.

We, the plugin authors, receive nothing: there is no telemetry endpoint, no error
reporting service, no analytics, no license check and no phone-home of any kind. No
data is passed to any other processor, sub-processor, advertiser, or affiliate,
because there is no other outbound call. Recipients cannot change per deployment —
the set is fixed by the code, not configured.

## Where it runs

Entirely on the developer's own machine, as Python (≥ 3.12) invoked by Claude Code
hooks or by the developer. There is no deployment, no hosting, no infrastructure we
run, no network service listening, and no database. The only outbound network call
is to the Anthropic API, using the developer's own credentials, to run the compile
and extraction agents.

Source code and releases live on GitHub; distribution is a marketplace manifest that
Claude Code reads. We operate neither.

## What it integrates with

- **Claude Code** — the host that loads the plugin and fires its hooks.
- **The Anthropic API / Claude Agent SDK** — for the compile, extraction and scoping
  agents, called with the developer's own credentials.
- **git** — the plugin reads repository context and writes tracked files; the
  developer commits them.

## Explicit non-goals

- Not a SaaS, not multi-tenant, not hosted.
- No user-facing authentication, authorisation or session management.
- No collection, storage or transfer of personal data.
- No processing on behalf of a customer or controller.
