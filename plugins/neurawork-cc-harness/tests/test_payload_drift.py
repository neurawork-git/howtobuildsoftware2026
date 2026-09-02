"""Every engine's shipped payload must match this repo's own self-host, byte for byte.

`install.py` propagates `payload/` into a self-host, but only when someone re-runs it: a
direct edit to `stack-base/scripts/` or `knowledge-base/hooks/` diverges silently until
the next install. This walk is what keeps the two copies identical in between — a payload
edit that is not mirrored, or a self-host edit that never reaches the payload, fails here
rather than shipping different behaviour to installs than this repo runs.

One walk over the `harness_probe` registry rather than a file per engine: the four are the
same comparison, and two of them (`knowledge-compiler`, `claudemd-lerner`) had no guard at
all while `stack-compiler` and `compliance-compiler` kept near-identical copies. An engine
whose self-host is absent is skipped, and the walk asserts it compared something so a
wrong path cannot pass vacuously.

**Every file counts, not only `*.py`.** `seed_prompt.txt` is payload — the bug PR #47
fixed lived in it, and a Python-only comparison would not have pinned it.

**On the self-host side only TRACKED files count**, which is what separates code from
state: a live install's `scripts/` also holds `state.json`, the completion stamp, a lock
and flush logs, all of them gitignored and none of them payload. Filtering by extension
could not tell them apart (`seed_prompt.txt` and `state.json` would both be "not `.py`"),
so the split comes from git itself. The cost is deliberate and worth naming: a file
someone drops into a self-host and never commits is invisible here — untracked is how
this guard defines "not part of the install", and an uncommitted file is not yet part of
the repository either. The reverse, a payload file gitignored in a self-host, does fail:
it goes missing from the tracked list.

`_shared/` is deliberately out of scope: it is not in `payload/` (the installer refreshes
it from `engines/_shared/`), and `VERSION` belongs to `test_selfhost_version.py`, so one
fact keeps one owner. No LLM, no network.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_ROOT.parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import harness_probe as probe

# Copied into the target next to the code, and just as able to drift.
FLAT_FILES = ("AGENTS.md", "pyproject.toml")
SUBDIRS = ("scripts", "hooks")


def _payload_files(root: Path) -> dict[str, bytes]:
    """Every file below `root`, keyed by relative path. `__pycache__` is not payload."""
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }


def _tracked_files(root: Path) -> dict[str, bytes]:
    """The same, for a live install: git-tracked files only, so state is left out."""
    out = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "-z", "--", str(root)],
                         capture_output=True, text=True, check=True)
    files = {}
    for rel in out.stdout.split("\0"):
        if not rel:
            continue
        path = REPO_ROOT / rel
        if path.is_file():  # a deleted-but-tracked path is not on disk to compare
            files[str(path.relative_to(root))] = path.read_bytes()
    return files


class TestPayloadDrift(unittest.TestCase):
    def setUp(self) -> None:
        if not (REPO_ROOT / "plugins" / PLUGIN_ROOT.name).is_dir():
            self.skipTest("not the plugin's source repo — no self-hosts to compare")
        if shutil.which("git") is None:
            self.skipTest("git not on PATH — cannot tell install code from install state")

    def test_every_self_host_matches_its_payload(self) -> None:
        compared = []
        for name, engine in probe.ENGINES.items():
            payload = PLUGIN_ROOT / "engines" / name / "payload"
            self_host = REPO_ROOT / engine.default_dir
            if not (self_host / "scripts").is_dir():
                continue  # not installed in this checkout

            for subdir in SUBDIRS:
                shipped = _payload_files(payload / subdir)
                installed = _tracked_files(self_host / subdir)
                # The file lists matter as much as the bytes: a script added on one side
                # only is exactly the drift this guard exists to catch, and comparing
                # bytes alone would pass it silently.
                self.assertEqual(
                    sorted(shipped), sorted(installed),
                    f"{name}: payload/{subdir} and {engine.default_dir}/{subdir} hold "
                    "different files",
                )
                for rel, data in shipped.items():
                    self.assertEqual(
                        data, installed[rel],
                        f"{name}: {subdir}/{rel} differs between payload and "
                        f"{engine.default_dir}",
                    )

            for flat in FLAT_FILES:
                self.assertEqual(
                    (payload / flat).read_bytes(), (self_host / flat).read_bytes(),
                    f"{name}: {flat} differs between payload and {engine.default_dir}",
                )
            compared.append(name)

        self.assertTrue(compared, "no self-host found — the walk compared nothing")


class TestSkipOutsideTheSourceRepo(unittest.TestCase):
    """The skip branch, which every run in this repo takes the other way past.

    Untested, it is the branch that would quietly swallow a wrong `REPO_ROOT`: the walk
    would skip instead of failing, and nothing would say the guard stopped guarding.
    """

    def _run(self, repo_root: Path) -> unittest.TestResult:
        module = sys.modules[TestPayloadDrift.__module__]
        result = unittest.TestResult()
        original = module.REPO_ROOT
        module.REPO_ROOT = repo_root
        try:
            module.TestPayloadDrift("test_every_self_host_matches_its_payload").run(result)
        finally:
            module.REPO_ROOT = original
        return result

    def test_a_checkout_without_the_plugin_layout_skips(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(Path(tmp))
        self.assertEqual(len(result.skipped), 1, "the walk did not skip")
        self.assertEqual(result.failures, [])
        # errors, not only failures: a walk that blew up — `git` missing, a subprocess
        # raising outside a repo — raises rather than fails, and a check that looks at
        # skips and failures alone would read the crash as a pass.
        self.assertEqual(result.errors, [])

    def test_this_repo_does_not_skip(self) -> None:
        result = self._run(REPO_ROOT)
        self.assertEqual(result.skipped, [], "the walk skipped in its own source repo")
        self.assertEqual(result.failures, [])
        self.assertEqual(result.errors, [])


if __name__ == "__main__":
    unittest.main()
