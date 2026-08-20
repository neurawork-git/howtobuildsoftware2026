---
title: "Swappable Backend Interfaces (Transcriber, Storage)"
aliases: [transcriber-interface, storage-interface, vendor-neutral-interfaces]
tags: [architecture, interfaces, portability]
sources:
  - "daily/2026-08-13.md"
created: 2026-08-20
updated: 2026-08-20
---

# Swappable Backend Interfaces (Transcriber, Storage)

GrillMe hides external service dependencies behind narrow interfaces so
providers can be swapped by configuration rather than code rewrites. Two were
defined up front: a `Transcriber` interface for speech-to-text and a `Storage`
interface for image persistence.

## Key Points

- `Transcriber` interface: Deepgram (`nova-3`) is the default; local
  `faster-whisper` is a config-switch alternative.
- `Storage` interface: images are stored on a Docker volume + filesystem with the
  path recorded in Postgres, behind an abstraction that allows a later S3 swap.
- The pattern is default-cloud-now, keep-local/self-hosted-swap-open — matching
  the app's self-hosting ambitions.

## Details

Both interfaces exist so that a vendor choice is a deployment detail, not an
architectural commitment. Speech-to-text defaults to the Deepgram `nova-3`
cloud model but can be switched to local `faster-whisper` via config, which
matters for a tool meant to be self-hostable. Image storage writes to a mounted
Docker volume and stores only the path in Postgres, leaving room to move the
bytes to S3 later without touching call sites.

Storing image paths (not blobs) in Postgres also keeps the database aligned with
its role as the source of truth for session state — see
[[concepts/postgres-source-of-truth-replayed-sessions]].

## Related Concepts

- [[concepts/grillme-app]] — the app these interfaces serve
- [[concepts/editable-transcript-before-send]] — the transcript the `Transcriber` produces
- [[concepts/postgres-source-of-truth-replayed-sessions]] — where image paths are persisted

## Sources

- [[daily/2026-08-13.md]] — Transcriber (Deepgram/faster-whisper) and Storage (filesystem/S3) interfaces defined
