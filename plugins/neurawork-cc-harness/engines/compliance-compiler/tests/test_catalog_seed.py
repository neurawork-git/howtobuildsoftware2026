"""Drift guard: the shipped payload/catalog-seed must match this repo's own
compliance-base/catalog (the license-audited source of truth). No LLM, no network.

Skips gracefully when compliance-base/catalog is absent (a pure plugin checkout with
no self-host), so the test is a no-op there.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
SEED_DIR = ENGINE_DIR / "payload" / "catalog-seed"
SEED_FILES = (
    "gdpr.json",
    "soc2.json",
    "iso27001.json",
    "capabilities.json",
    "capabilities.md",
    "index.md",
)


def _source_catalog() -> Path | None:
    for parent in ENGINE_DIR.parents:
        cand = parent / "compliance-base" / "catalog"
        if cand.is_dir():
            return cand
    return None


class TestCatalogSeed(unittest.TestCase):
    def test_seed_matches_source(self) -> None:
        src = _source_catalog()
        if src is None:
            self.skipTest("no compliance-base/catalog in this checkout")
        for name in SEED_FILES:
            seeded = SEED_DIR / name
            source = src / name
            self.assertTrue(seeded.exists(), f"seed missing {name} — run sync_catalog_seed.py")
            self.assertTrue(source.exists(), f"source missing {name}")
            self.assertEqual(
                seeded.read_bytes(), source.read_bytes(),
                f"{name} drifted — run: python3 sync_catalog_seed.py",
            )


if __name__ == "__main__":
    unittest.main()
