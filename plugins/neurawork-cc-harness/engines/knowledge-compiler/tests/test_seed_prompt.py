"""Guard: the seed prompt binds its write targets to an absolute path, not to the cwd.

`seed.py` runs the agent with `cwd=<repo root>` but writes into
`KNOWLEDGE_DIR` (`<repo>/<kdir>/knowledge`), which it passes in a separate
"Write articles under" section. Any bare relative `knowledge/...` path in the
prompt therefore resolves one level too high — to `<repo>/knowledge/` — and
nothing catches it: `assert_in_repo_not_dotclaude` checks `KNOWLEDGE_DIR` once
before the run, never the agent's writes, and `<repo>/knowledge/` would pass
that check anyway.

Prose cannot be unit tested; this pins the one property whose loss is silent —
that the prompt never states a write target the cwd can rebind.

Stdlib only, no LLM, no network.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
PAYLOAD_PROMPT = ENGINE_DIR / "payload" / "scripts" / "seed_prompt.txt"
SEED_PY = ENGINE_DIR / "payload" / "scripts" / "seed.py"

# The section header in seed.py that carries the absolute KNOWLEDGE_DIR.
TARGET_SECTION = "## Write articles under"

# A bare `knowledge/...` write target: the word not preceded by `<kdir>/`, `/` or `.`.
BARE_KNOWLEDGE_PATH = re.compile(r"(?<![\w/.<])knowledge/")


class SeedPromptPathBindingTests(unittest.TestCase):
    def prompt(self) -> str:
        return PAYLOAD_PROMPT.read_text(encoding="utf-8")

    def test_the_prompt_states_no_cwd_relative_write_target(self) -> None:
        offenders = [
            f"line {n}: {line.strip()}"
            for n, line in enumerate(self.prompt().splitlines(), 1)
            if BARE_KNOWLEDGE_PATH.search(line)
        ]
        self.assertEqual(
            offenders,
            [],
            "seed.py runs the agent with cwd=<repo root>, so a bare `knowledge/` path "
            "resolves to <repo>/knowledge/ instead of <repo>/<kdir>/knowledge/. "
            f"Name the '{TARGET_SECTION}' section instead:\n  " + "\n  ".join(offenders),
        )

    def test_the_prompt_points_at_the_section_that_carries_the_absolute_path(self) -> None:
        # Removing the pointer would leave the write target stated nowhere the
        # instructions themselves reach.
        self.assertIn(
            TARGET_SECTION,
            self.prompt(),
            f"the prompt must name the '{TARGET_SECTION}' section that seed.py appends",
        )

    def test_seed_py_still_supplies_that_section_and_the_repo_root_cwd(self) -> None:
        # If either side moves, the pointer above becomes a dangling reference.
        source = SEED_PY.read_text(encoding="utf-8")
        self.assertIn(TARGET_SECTION, source)
        self.assertIn("{KNOWLEDGE_DIR}", source)
        self.assertIn("cwd=str(root)", source)


class SeedPromptSyncTests(unittest.TestCase):
    def test_the_self_host_copy_matches_the_payload(self) -> None:
        # The engine ships in two byte-identical copies; a fix applied to one only
        # reaches half the installs. Skip when this checkout is not the self-host.
        repo_root = ENGINE_DIR.parents[3]
        self_host = repo_root / "knowledge-base" / "scripts" / "seed_prompt.txt"
        if not self_host.exists():
            self.skipTest("not the self-hosting checkout")
        self.assertEqual(
            self_host.read_text(encoding="utf-8"),
            PAYLOAD_PROMPT.read_text(encoding="utf-8"),
            "knowledge-base/scripts/seed_prompt.txt has drifted from the payload copy",
        )


if __name__ == "__main__":
    unittest.main()
