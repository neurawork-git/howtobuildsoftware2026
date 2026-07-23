#!/usr/bin/env python3
"""Promote this repo's audited catalog into the shipped plugin seed.

The self-hosted ``compliance-base/catalog/`` is the source of truth (it holds the
license-audited constraint catalog + derived capabilities). ``install.py`` ships a
copy of it under ``payload/catalog-seed/`` so a fresh install has a working catalog
with no LLM run. This script keeps the two in sync:

    python3 sync_catalog_seed.py            # copy compliance-base/catalog/* -> payload/catalog-seed/
    python3 sync_catalog_seed.py --check    # exit non-zero if the seed has drifted

Only the six shipped files are promoted (never .shards/, reports/, state.json).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
SEED_DIR = ENGINE_DIR / "payload" / "catalog-seed"
SEED_FILES = (
    "gdpr.json",
    "soc2.json",
    "iso27001.json",
    "capabilities.json",
    "capabilities.md",
    "index.md",
)


def _repo_root() -> Path:
    """Walk up from the engine dir to the repo root (the dir holding compliance-base/)."""
    for parent in ENGINE_DIR.parents:
        if (parent / "compliance-base" / "catalog").is_dir():
            return parent
    raise SystemExit("sync_catalog_seed: could not locate compliance-base/catalog above this engine")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="Report drift and exit non-zero instead of copying")
    args = parser.parse_args()

    src_dir = _repo_root() / "compliance-base" / "catalog"
    drift: list[str] = []

    for name in SEED_FILES:
        src = src_dir / name
        dst = SEED_DIR / name
        if not src.exists():
            print(f"  ! missing source: {src}")
            drift.append(name)
            continue
        src_bytes = src.read_bytes()
        if args.check:
            if not dst.exists() or dst.read_bytes() != src_bytes:
                drift.append(name)
        else:
            SEED_DIR.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src_bytes)
            print(f"  = synced {name}")

    if args.check:
        if drift:
            print(f"\nSEED DRIFT — payload/catalog-seed is stale for: {', '.join(drift)}")
            print("Run: python3 sync_catalog_seed.py")
            return 1
        print("seed in sync with compliance-base/catalog")
        return 0

    print(f"\nSynced {len(SEED_FILES)} files into {SEED_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
