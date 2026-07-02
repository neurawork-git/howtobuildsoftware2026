---
title: "Plugin and Marketplace Name Verification"
aliases: [manifest-verification, marketplace-json]
tags: [plugin, verification, convention]
sources:
  - "daily/2026-06-25.md"
created: 2026-07-02
updated: 2026-07-02
---

# Plugin and Marketplace Name Verification

Before publishing install instructions, the marketplace and plugin names were
verified against the repository's own manifest files rather than assumed. The
marketplace name `neurawork-harness` and plugin name `neurawork-cc-harness` were
confirmed against `.claude-plugin/marketplace.json` and the plugin manifests.

## Key Points

- Authoritative source for names is `.claude-plugin/marketplace.json` and the
  plugin manifests, not memory or prior documentation.
- Marketplace name: `neurawork-harness`; plugin name: `neurawork-cc-harness`.
- Verifying names against manifests prevents shipping install commands that
  silently fail because an identifier is wrong.

## Details

Install commands depend on exact identifiers — `/plugin install
neurawork-cc-harness@neurawork-harness` fails if either the plugin name or the
`@`-suffixed marketplace name is mistyped. Because these strings are opaque and
easy to get wrong, they were checked against the manifest files that define them
before being committed to the README.

This verification step underpins the corrected
[[concepts/plugin-marketplace-install]] instructions and is a general safeguard
whenever documentation references plugin identifiers.

## Related Concepts

- [[concepts/plugin-marketplace-install]] — the install commands whose names were verified
- [[concepts/readme-getting-started-vs-contributing]] — documentation these verified names were written into

## Sources

- [[daily/2026-06-25.md]] — names verified against marketplace.json and manifests
