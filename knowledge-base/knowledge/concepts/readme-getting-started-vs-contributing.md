---
title: "README: Install/Use vs Contributing Sections"
aliases: [getting-started-vs-contributing, readme-structure]
tags: [readme, documentation, convention]
sources:
  - "daily/2026-06-25.md"
created: 2026-07-02
updated: 2026-07-02
---

# README: Install/Use vs Contributing Sections

The README separates two audiences: users who install and use the plugin, and
contributors who work on the harness source. Install/use instructions must
reflect the marketplace path, while `git clone` belongs only under Contributing.

## Key Points

- A `## Getting Started` section that told users to `git clone` was misleading —
  cloning is a contributor action, not a user action.
- The clone block was moved into `## Contributing`, since cloning only applies to
  working on the harness itself.
- A single `## Contributing` section was kept rather than splitting it into
  multiple subsections.
- End-user install steps live in `## Install / Use` and use the
  [[concepts/plugin-marketplace-install]] commands.

## Details

The confusion arose because the README's most prominent onboarding section
pointed users at a workflow (cloning) that only contributors need. Correcting
this was primarily a matter of audience placement: the same commands were valid,
but the clone instructions were relevant to a different reader than the section
implied.

The decision favored a single Contributing section over splitting the clone
guidance across multiple headings, keeping the contributor path in one place and
the user path in another.

## Related Concepts

- [[concepts/plugin-marketplace-install]] — the user-facing path that replaced the clone block
- [[concepts/plugin-manifest-name-verification]] — verifying the names used in the corrected instructions

## Sources

- [[daily/2026-06-25.md]] — clone block moved from Getting Started to Contributing
