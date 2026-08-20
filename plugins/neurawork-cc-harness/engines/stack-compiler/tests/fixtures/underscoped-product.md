# Product — TicketDesk (deliberately under-scoped fixture)

**This file is a test fixture, not a real product description.** It is internally
contradictory on purpose: it asserts that no personal data is processed while
describing, in the same document, the storage of end-user email addresses, names and
support correspondence.

What it proves: **a false blanket assertion must not shrink the compliance surface.**
Scoping it must leave every capability the description actually implies applicable —
the run may not drop GDPR capabilities on the strength of the "no personal data"
sentence. Run it with

    uv run --directory stack-base python scripts/scope.py --product \
        ../plugins/neurawork-cc-harness/engines/stack-compiler/tests/fixtures/underscoped-product.md

and check the report: no personal-data capability may appear under *Not applicable*.
Revert `compliance-base/catalog/stack.json` afterwards — a passing fixture run writes
the fixture's scope hash into it.

Observed 2026-08-20: 68 of 68 capabilities stayed applicable, so nothing reached the
challenge pass. The refutation path itself is proven separately — by the unit tests
in `test_scope_lib.py` / `test_scope.py`, and by a live refutation on the real
`stack-base/product.md` (a "discloses data to no recipients" claim was refuted with a
quote naming the Anthropic API call).

## What it does

TicketDesk is a hosted customer-support product. Customers sign up, open support
tickets, and exchange messages with our support agents until the ticket is closed.

## Who uses it

End users at our customers' companies, and our own support agents. Both groups log
in with an email address and a password.

## What data it holds

**This service processes no personal data.**

The database stores, per end user: the account's full name, the email address used
to log in, a bcrypt password hash, the IP address of each login, and the full text of
every support message they have written. Attachments uploaded to a ticket — often
invoices and screenshots of the customer's own systems — are kept in object storage
for the life of the account. We also keep a seven-year archive of closed tickets for
business reporting.

## Where it runs

A multi-tenant deployment on our own cloud account, serving customers across the EU
and the US from one region. Support agents access it over the public internet.

## What it integrates with

- An email gateway, which sends ticket notifications to end users' inboxes.
- A payment provider for the customers' subscriptions.
- An analytics product that receives end-user page views together with the logged-in
  account identifier.
