"""Pure-logic tests for the kb-researcher spawn directive and both hooks' decisions.

Silence is this feature's failure mode: a hook that emits nothing is indistinguishable
from a hook that decided not to fire. These tests assert the decision itself, which is
why every hook's decision lives in an importable `build_context` rather than inline in
`main()`. No LLM, no network, no subprocess.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS = ENGINE_DIR / "payload" / "scripts"
HOOKS = ENGINE_DIR / "payload" / "hooks"

sys.path.insert(0, str(ENGINE_DIR.parent))  # engines/ for _shared, as the install provides it
sys.path.insert(0, str(SCRIPTS))

import config  # noqa: E402
import research_directive as rd  # noqa: E402


def _load_hook(filename: str):
    """Import a hook module by path — the filenames are hyphenated, so not importable."""
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_"), HOOKS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PRE_SKILL = _load_hook("pre-skill.py")
USER_PROMPT = _load_hook("user-prompt-submit.py")

DEFAULTS = {
    "research_directive": True,
    "research_skill_match": rd.DEFAULT_SKILL_MATCH,
    "research_prompt_match": rd.DEFAULT_PROMPT_MATCH,
}


class TestSkillMatching(unittest.TestCase):
    def test_research_skills_match_qualified_and_bare(self) -> None:
        for skill in ("prp-prd", "prp-core:prp-prd", "prp-plan", "prp-debug",
                      "prp-core:prp-debug"):
            with self.subTest(skill=skill):
                self.assertTrue(
                    rd.research_enabled(DEFAULTS, "research_skill_match", skill))

    def test_neighbouring_skills_do_not_match(self) -> None:
        # `prp-prd-update` is a real prp-core skill. A trailing `\b` would match it,
        # because `-` is a word boundary — hence the `$` anchor.
        for skill in ("prp-prd-update", "prp-core:prp-prd-update", "prp-commit",
                      "prp-plan-b", "prp-pr", ""):
            with self.subTest(skill=skill):
                self.assertFalse(
                    rd.research_enabled(DEFAULTS, "research_skill_match", skill))


class TestPromptMatching(unittest.TestCase):
    def test_typed_research_commands_match(self) -> None:
        for prompt in ("/prp-prd idea", "  /prp-prd", "/prp-core:prp-plan x", "/prp-debug\n"):
            with self.subTest(prompt=prompt):
                self.assertTrue(
                    rd.research_enabled(DEFAULTS, "research_prompt_match", prompt))

    def test_non_invocations_do_not_match(self) -> None:
        for prompt in ("/prp-prd-update", "see /prp-prd for context", "/prp-commit",
                       "prp-prd without a slash", ""):
            with self.subTest(prompt=prompt):
                self.assertFalse(
                    rd.research_enabled(DEFAULTS, "research_prompt_match", prompt))


class TestDegradation(unittest.TestCase):
    def test_flag_false_suppresses_a_matching_value(self) -> None:
        cfg = {**DEFAULTS, "research_directive": False}
        self.assertFalse(rd.research_enabled(cfg, "research_skill_match", "prp-core:prp-prd"))
        self.assertFalse(rd.research_enabled(cfg, "research_prompt_match", "/prp-prd x"))

    def test_uncompilable_regex_falls_back_to_the_default(self) -> None:
        cfg = {**DEFAULTS, "research_skill_match": "^([unclosed"}
        self.assertTrue(rd.research_enabled(cfg, "research_skill_match", "prp-core:prp-prd"))
        self.assertFalse(rd.research_enabled(cfg, "research_skill_match", "prp-commit"))

    def test_empty_regex_falls_back_rather_than_matching_everything(self) -> None:
        cfg = {**DEFAULTS, "research_prompt_match": ""}
        self.assertFalse(rd.research_enabled(cfg, "research_prompt_match", "anything at all"))

    def test_unknown_key_never_matches(self) -> None:
        self.assertFalse(rd.research_enabled(DEFAULTS, "nope", "/prp-prd x"))


class TestDirectiveContent(unittest.TestCase):
    def setUp(self) -> None:
        self.text = rd.directive("/repo/knowledge-base")

    def test_names_the_agent_plugin_qualified(self) -> None:
        # Another enabled plugin may export a bare `kb-researcher` written against a
        # different corpus schema; only the qualified name resolves to ours.
        self.assertIn("neurawork-cc-harness:kb-researcher", self.text)

    def test_carries_the_resolved_knowledge_dir(self) -> None:
        self.assertIn("/repo/knowledge-base", self.text)

    def test_places_the_agent_among_the_other_three_axes(self) -> None:
        for agent in ("codebase-explorer", "codebase-analyst", "web-researcher"):
            with self.subTest(agent=agent):
                self.assertIn(agent, self.text)

    def test_requires_concurrent_launch_and_a_backlink_walk(self) -> None:
        self.assertIn("SAME message", self.text)
        self.assertIn("BACKLINKS", self.text)

    def test_stays_under_the_size_ceiling(self) -> None:
        # A larger additionalContext payload is offloaded to a short preview, which would
        # silently truncate the directive.
        self.assertLessEqual(len(self.text), rd.MAX_DIRECTIVE_CHARS)


class TestHookDecisions(unittest.TestCase):
    """Both hooks decide via an importable function, so the negative paths — the ones
    that emit nothing and are therefore invisible at runtime — can be asserted."""

    def test_pre_skill_fires_only_for_a_research_skill(self) -> None:
        self.assertTrue(PRE_SKILL.build_context("Skill", {"skill": "prp-core:prp-prd"}))

    def test_pre_skill_ignores_everything_else(self) -> None:
        for tool, tool_input in (
            ("Bash", {"skill": "prp-core:prp-prd"}),   # not the Skill tool
            ("Skill", {}),                             # no skill key
            ("Skill", {"skill": ""}),                  # empty skill name
            ("Skill", {"skill": None}),                # non-string skill
            ("Skill", {"skill": "prp-core:prp-prd-update"}),  # neighbouring skill
            ("Skill", {"skill": "neurawork-cc-harness:kc-compile"}),
        ):
            with self.subTest(tool=tool, tool_input=tool_input):
                self.assertEqual(PRE_SKILL.build_context(tool, tool_input), "")

    def test_user_prompt_fires_only_on_a_typed_research_command(self) -> None:
        self.assertTrue(USER_PROMPT.build_context("/prp-prd a new thing"))
        for prompt in ("/prp-prd-update", "/prp-commit", "see /prp-prd for context", ""):
            with self.subTest(prompt=prompt):
                self.assertEqual(USER_PROMPT.build_context(prompt), "")

    def test_both_hooks_render_byte_identical_text(self) -> None:
        # One renderer, so the two paths cannot drift into disagreeing about the workflow.
        self.assertEqual(
            PRE_SKILL.build_context("Skill", {"skill": "prp-core:prp-prd"}),
            USER_PROMPT.build_context("/prp-prd a new thing"),
        )


class TestConfigDefaults(unittest.TestCase):
    def test_default_cfg_carries_the_three_research_keys(self) -> None:
        for key in ("research_directive", "research_skill_match", "research_prompt_match"):
            with self.subTest(key=key):
                self.assertIn(key, config.DEFAULT_CFG)

    def test_shipped_config_default_json_matches_default_cfg(self) -> None:
        # A fresh install writes config.default.json as the repo's config.json, so a
        # value that drifts from DEFAULT_CFG silently ships different behaviour.
        shipped = json.loads((ENGINE_DIR / "config.default.json").read_text(encoding="utf-8"))
        for key, value in shipped.items():
            with self.subTest(key=key):
                self.assertEqual(value, config.DEFAULT_CFG[key])


if __name__ == "__main__":
    unittest.main()
