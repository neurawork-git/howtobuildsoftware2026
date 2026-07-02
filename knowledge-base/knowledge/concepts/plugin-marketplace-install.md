---
title: "Plugin Marketplace Install Path"
aliases: [marketplace-install, plugin-install]
tags: [distribution, plugin, readme]
sources:
  - "daily/2026-06-25.md"
created: 2026-07-02
updated: 2026-07-02
---

# Plugin Marketplace Install Path

The `neurawork-cc-harness` plugin is distributed through a Claude Code plugin
marketplace, not by cloning the repository. Users install it with two slash
commands and do **not** need a local clone of the repo to use it.

## Key Points

- Install is marketplace-based: `/plugin marketplace add neurawork-git/howtobuildsoftware2026`
  followed by `/plugin install neurawork-cc-harness@neurawork-harness`.
- No `git clone` is required to *use* the plugin — cloning only applies to
  developing the harness itself.
- The commands belong inline in the README `## Install / Use` section, not
  buried behind a link to `INSTALL.md`.
- Marketplace name is `neurawork-harness`; plugin name is `neurawork-cc-harness`.

## Details

The README previously exposed the real install path only through a link to
`INSTALL.md`, leaving the misleading `git clone` block as the apparent entry
point. The fix put the two real marketplace commands directly in the
`## Install / Use` section and stated plainly that no clone is needed.

The `@neurawork-harness` suffix on the install command references the
marketplace by name, while `neurawork-cc-harness` is the plugin identifier.
Both names were confirmed against the repository manifests rather than assumed —
see [[concepts/plugin-manifest-name-verification]].

## Related Concepts

- [[concepts/readme-getting-started-vs-contributing]] — where the install path lives vs the clone instructions
- [[concepts/plugin-manifest-name-verification]] — how the marketplace and plugin names were validated

## Sources

- [[daily/2026-06-25.md]] — README install instructions were corrected to the marketplace path
