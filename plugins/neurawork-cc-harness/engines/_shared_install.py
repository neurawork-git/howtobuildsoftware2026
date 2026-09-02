"""Install-time helpers shared by every engine's ``install.py`` (pure stdlib).

Deliberately NOT inside ``_shared/``: that directory is copied verbatim into every
target repo, so anything placed there ships into an install. This module never
leaves the plugin — which is exactly what makes it the right home for the list of
``_shared/`` files that must NOT ship.

Every installer already puts ``engines/`` on ``sys.path`` for its ``_shared``
imports, so importing ``_shared_install`` from an installer needs no new mechanism.
"""

from __future__ import annotations

import shutil
from pathlib import Path

# _shared tests that assert plugin-level facts (the plugin manifest,
# <plugin>/hooks/version-check.py). Neither exists inside a target repo, so a copy
# shipped there fails with FileNotFoundError on arrival. They stay in the plugin.
PLUGIN_ONLY_SHARED_TESTS = ("test_manifest.py", "test_version_check.py")


def refresh_shared(shared_src: Path, target: Path) -> None:
    """Copy ``shared_src`` to ``<target>/_shared``, minus the plugin-only tests.

    Refreshed on every install (``_shared/`` is a single source of truth, never
    diverged per install), and any plugin-only test an older install left behind is
    removed — which is what repairs an existing install on its next ADOPT run.
    """
    shutil.copytree(shared_src, target / "_shared",
                    ignore=shutil.ignore_patterns("__pycache__", *PLUGIN_ONLY_SHARED_TESTS),
                    dirs_exist_ok=True)
    for name in PLUGIN_ONLY_SHARED_TESTS:
        stale = target / "_shared" / "tests" / name
        if stale.exists():
            stale.unlink()
