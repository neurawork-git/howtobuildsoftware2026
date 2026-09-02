#!/usr/bin/env node
/**
 * Plugin-level SessionStart staleness nudge.
 *
 * Runs FROM the plugin (so it has CLAUDE_PLUGIN_ROOT — the installed engine copies
 * inside a target repo do NOT, which is why this check cannot live in them). For each
 * harness engine installed in the current repo, it compares the installed VERSION
 * (stamped into <repo>/<dir>/VERSION at install time) against the plugin's currently
 * shipped VERSION (<plugin>/engines/<engine>/VERSION). When an install is behind, it
 * prints a SessionStart additionalContext note telling the user to re-run the
 * installer (ADOPT) to propagate the upgrade.
 *
 * Node + stdlib only, spawned via the hook exec form (no shell, no uv). This is the
 * one script in the plugin that must bootstrap *without* the toolchain everything
 * else depends on, so it deliberately has no interpreter to locate: `node` is on PATH
 * wherever Claude Code runs. Do not "improve" this by routing it through uv (see #5)
 * or by naming a Python interpreter (see #16) — both reintroduce a discovery step
 * this file exists to avoid.
 *
 * Silent no-op when nothing is stale or when the repo has no harness install. Never
 * raises — a hook crash must not break session start.
 */

"use strict";

const fs = require("node:fs");
const path = require("node:path");

// engine name -> unique substrings of that engine's installed hook commands in
// .claude/settings.json. Used to locate where each engine was installed (the dir
// is user-configurable, so we read it back from the command line rather than
// assuming the default dir name). Several markers per engine because the first one
// is not guaranteed to be wired: an install whose SessionStart entry was removed by
// hand is still an install, and its remaining hooks still say where it lives.
//
// This is a SECOND copy of the registry in scripts/harness_probe.py — a Node hook
// cannot import a Python module. It is kept honest by
// tests/test_version_check_registry.py, which fails if the two maps disagree on a
// single engine or marker. Register a new engine in BOTH, or the guard goes red.
const ENGINES = {
  "knowledge-compiler": [
    "hooks/session-start.py",
    "hooks/pre-compact.py",
    "hooks/session-end.py",
    "hooks/user-prompt-submit.py",
    "hooks/pre-skill.py",
  ],
  "claudemd-lerner": [
    "hooks/cl-session-start.py",
    "hooks/cl-pre-compact.py",
    "hooks/cl-session-end.py",
  ],
  "compliance-compiler": ["hooks/co-post-tooluse.py"],
  "stack-compiler": ["hooks/st-post-tooluse.py"],
};

const DIR_RE = /\$CLAUDE_PROJECT_DIR\/([^"'\s]+)/;

/** Plain object, the way the Python original tested `isinstance(x, dict)`. */
function isObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Return the install dir segment for the hook command containing `marker`. */
function installedDirFor(settings, marker) {
  const hooksObj = isObject(settings) ? settings.hooks : undefined;
  if (!isObject(hooksObj)) return null;
  for (const groups of Object.values(hooksObj)) {
    if (!Array.isArray(groups)) continue;
    for (const group of groups) {
      if (!isObject(group)) continue;
      const hooks = Array.isArray(group.hooks) ? group.hooks : [];
      for (const hook of hooks) {
        const command = String((isObject(hook) && hook.command) || "");
        if (command.includes(marker)) {
          const m = DIR_RE.exec(command);
          if (m) return m[1];
        }
      }
    }
  }
  return null;
}

/** Return the trimmed VERSION file content, or null (never throws). */
function readVersion(file) {
  try {
    return fs.readFileSync(file, "utf8").trim();
  } catch {
    return null;
  }
}

// Mirrors what Python's int() accepts here: an optional sign and digits only, so
// "2.0" and "v2" fall through to the string comparison exactly as before.
const INT_RE = /^[+-]?\d+$/;

/** True if the installed version is older than the shipped version. */
function isBehind(installed, shipped) {
  const a = String(installed).trim();
  const b = String(shipped).trim();
  if (INT_RE.test(a) && INT_RE.test(b)) return BigInt(a) < BigInt(b);
  return String(installed) !== String(shipped);
}

/** List engines whose installed VERSION is behind the shipped VERSION. */
function findStale(repoRoot, pluginRoot, settings) {
  const stale = [];
  for (const [engine, markers] of Object.entries(ENGINES)) {
    let dirname = null;
    for (const marker of markers) {
      dirname = installedDirFor(settings, marker);
      if (dirname) break;
    }
    if (!dirname) continue;
    const installed = readVersion(path.join(repoRoot, dirname, "VERSION"));
    const shipped = readVersion(path.join(pluginRoot, "engines", engine, "VERSION"));
    if (installed === null || shipped === null) continue;
    if (isBehind(installed, shipped)) {
      stale.push({ engine, dir: dirname, installed, shipped });
    }
  }
  return stale;
}

function buildNote(stale) {
  const lines = [
    "neurawork-cc-harness: an installed engine copy is behind the plugin. " +
      "Re-run the installer (ADOPT — non-destructive) to upgrade the in-repo code:",
  ];
  for (const s of stale) {
    lines.push(
      `- ${s.engine} in ${s.dir}/ is behind ` +
        `(installed ${s.installed} < shipped ${s.shipped}) — ` +
        `re-run /neurawork-cc-harness:${s.engine}`,
    );
  }
  return lines.join("\n");
}

function main() {
  try {
    const projectDir = process.env.CLAUDE_PROJECT_DIR;
    if (!projectDir) return;
    const repoRoot = projectDir;
    const pluginRoot = process.env.CLAUDE_PLUGIN_ROOT || path.resolve(__dirname, "..");

    const settingsPath = path.join(repoRoot, ".claude", "settings.json");
    let settings;
    try {
      settings = JSON.parse(fs.readFileSync(settingsPath, "utf8"));
    } catch {
      return;
    }
    if (!isObject(settings)) return;

    const stale = findStale(repoRoot, pluginRoot, settings);
    if (stale.length === 0) return;

    process.stdout.write(
      JSON.stringify({
        hookSpecificOutput: {
          hookEventName: "SessionStart",
          additionalContext: buildNote(stale),
        },
      }) + "\n",
    );
  } catch {
    // a hook crash must never break session start
  }
}

module.exports = { ENGINES, installedDirFor, readVersion, isBehind, findStale, buildNote, main };

if (require.main === module) main();
